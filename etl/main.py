import logging
import sys

import psycopg2

from etl.audit import Audit
from etl.config import ConfigError, get_as_of, parse_args, validate_interval
from etl.db import connect
from etl.loader_core import load_core_price, load_core_reference
from etl.loader_mart import rebuild_mart_route_card
from etl.loader_raw import load_source_to_raw
from etl.stages import (
    STAGE_MART_ROUTE_CARD,
    STAGE_RAW_TO_CORE_PRICE,
    STAGE_RAW_TO_CORE_REFERENCE,
    STAGE_SOURCE_TO_RAW,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("etl")


def run_stage(audit, name, fn):
    stage_id = audit.start_stage(name)
    try:
        stats = fn()
    except Exception as e:
        audit.finish_stage(stage_id, "failed", error_message=str(e))
        raise
    audit.finish_stage(stage_id, "success", **stats)
    log.info("%s: %s", name, stats)


def run():
    args = parse_args()

    try:
        validate_interval(args.interval_start, args.interval_end)
    except ConfigError as e:
        log.error("config error: %s", e)
        return 2

    as_of = get_as_of()
    data_conn = connect(autocommit=False)
    audit_conn = connect(autocommit=True)
    audit = Audit(audit_conn)

    try:
        audit.start_run(args.interval_start, args.interval_end, args.triggered_by)
    except psycopg2.errors.ExclusionViolation:
        log.error(
            "another ETL run is running for an overlapping interval; aborting"
        )
        data_conn.close()
        audit_conn.close()
        return 1

    run_id = audit.run_id
    log.info(
        "run %s started: interval=[%s, %s) as_of=%s",
        run_id, args.interval_start, args.interval_end, as_of,
    )

    try:
        # ---- source -> raw ----
        try:
            run_stage(
                audit, STAGE_SOURCE_TO_RAW,
                lambda: load_source_to_raw(
                    data_conn, run_id,
                    args.interval_start, args.interval_end,
                ),
            )
            data_conn.commit()

            with data_conn.cursor() as cur:
                for t in ("prices", "price_body_types", "price_dates",
                          "cities", "body_types", "exchange_rates"):
                    cur.execute(f"ANALYZE raw.{t}")
            data_conn.commit()
        except Exception:
            data_conn.rollback()
            raise

        # ---- raw -> core ----
        try:
            with data_conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM core.price "
                    "WHERE loading_date >= %s AND loading_date < %s",
                    (args.interval_start, args.interval_end),
                )

            run_stage(
                audit, STAGE_RAW_TO_CORE_REFERENCE,
                lambda: load_core_reference(data_conn, run_id),
            )

            run_stage(
                audit, STAGE_RAW_TO_CORE_PRICE,
                lambda: load_core_price(
                    data_conn, run_id,
                    args.interval_start, args.interval_end, as_of,
                ),
            )

            data_conn.commit()
        except Exception:
            data_conn.rollback()
            raise

        # ---- ANALYZE core перед mart ----
        with data_conn.cursor() as cur:
            for t in ("price", "price_body_group", "price_dates",
                      "city", "body_group", "body_type"):
                cur.execute(f"ANALYZE core.{t}")
        data_conn.commit()

        # ---- core -> mart (full refresh) ----
        try:
            run_stage(
                audit, STAGE_MART_ROUTE_CARD,
                lambda: rebuild_mart_route_card(data_conn, as_of),
            )
            data_conn.commit()
        except Exception:
            data_conn.rollback()
            raise

    except Exception as e:
        log.exception("run %s failed", run_id)
        audit.finish_run("failed", error_message=str(e))
        data_conn.close()
        audit_conn.close()
        return 1

    audit.finish_run("success")
    log.info("run %s finished: success", run_id)
    data_conn.close()
    audit_conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(run())