import logging
import sys

import psycopg2

from etl.audit import Audit
from etl.config import ConfigError, get_as_of, parse_args, validate_interval
from etl.db import connect
from etl.loader_core import load_core_reference, load_core_price
from etl.loader_raw import (
    load_price_body_types,
    load_price_dates,
    load_prices,
    load_reference,
)
from etl.stages import (
    STAGE_CORE_PRICE,
    STAGE_CORE_REFERENCE,
    STAGE_RAW_PRICE_BODY_TYPES,
    STAGE_RAW_PRICE_DATES,
    STAGE_RAW_PRICES,
    STAGE_RAW_REFERENCE,
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
        run_stage(
            audit, STAGE_RAW_REFERENCE,
            lambda: {"details": load_reference(data_conn, run_id)},
        )
        data_conn.commit()

        run_stage(
            audit, STAGE_RAW_PRICES,
            lambda: {"rows_out": load_prices(
                data_conn, run_id, args.interval_start, args.interval_end)},
        )
        data_conn.commit()

        run_stage(
            audit, STAGE_RAW_PRICE_DATES,
            lambda: {"rows_out": load_price_dates(
                data_conn, run_id, args.interval_start, args.interval_end)},
        )
        data_conn.commit()

        run_stage(
            audit, STAGE_RAW_PRICE_BODY_TYPES,
            lambda: {"rows_out": load_price_body_types(
                data_conn, run_id, args.interval_start, args.interval_end)},
        )
        data_conn.commit()

        # ---- raw -> core ----
        try:
            with data_conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM core.price "
                    "WHERE loading_date >= %s AND loading_date < %s",
                    (args.interval_start, args.interval_end),
                )

            run_stage(
                audit, STAGE_CORE_REFERENCE,
                lambda: load_core_reference(data_conn, run_id),
            )

            run_stage(
                audit, STAGE_CORE_PRICE,
                lambda: load_core_price(
                    data_conn, run_id,
                    args.interval_start, args.interval_end, as_of),
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