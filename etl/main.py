import logging
import sys
from datetime import timedelta

import psycopg2

from etl.audit import Audit
from etl.config import (
    ConfigError,
    get_as_of,
    parse_args,
    validate_run_config,
)
from etl.db import connect
from etl.loader_core import (
    load_core_price,
    load_core_price_changes,
    load_core_reference,
)
from etl.loader_mart import (
    rebuild_mart_route_card,
    rebuild_mart_route_card_partitions,
)
from etl.loader_raw import (
    load_source_to_raw,
    load_source_to_raw_changes,
)
from etl.stages import (
    STAGE_MART_ROUTE_CARD,
    STAGE_RAW_TO_CORE_PRICE,
    STAGE_RAW_TO_CORE_REFERENCE,
    STAGE_SOURCE_TO_RAW,
    STAGE_SOURCE_TO_RAW_CHANGES,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("etl")

def get_incremental_window(as_of):
    return as_of - timedelta(days=1), None

def run_stage(audit, name, fn):
    stage_id = audit.start_stage(name)
    try:
        stats = fn()
    except Exception as e:
        audit.finish_stage(stage_id, "failed", error_message=str(e))
        raise
    audit.finish_stage(stage_id, "success", **stats)
    log.info("%s: %s", name, stats)


def analyze(conn, tables):
    with conn.cursor() as cur:
        for t in tables:
            cur.execute(f"ANALYZE {t}")
    conn.commit()


def run_backfill(audit, data_conn, run_id, args, as_of):
    interval_start = args.interval_start
    interval_end = args.interval_end

    try:
        run_stage(
            audit, STAGE_SOURCE_TO_RAW,
            lambda: load_source_to_raw(
                data_conn, run_id, interval_start, interval_end,
            ),
        )
        data_conn.commit()
        analyze(data_conn, (
            "raw.prices", "raw.price_body_types", "raw.price_dates",
            "raw.cities", "raw.body_types", "raw.exchange_rates",
        ))
    except Exception:
        data_conn.rollback()
        raise

    try:
        with data_conn.cursor() as cur:
            cur.execute(
                "DELETE FROM core.price "
                "WHERE loading_date >= %s AND loading_date < %s",
                (interval_start, interval_end),
            )

        run_stage(
            audit, STAGE_RAW_TO_CORE_REFERENCE,
            lambda: load_core_reference(data_conn, run_id),
        )
        run_stage(
            audit, STAGE_RAW_TO_CORE_PRICE,
            lambda: load_core_price(data_conn, run_id, interval_start, interval_end),
        )
        data_conn.commit()
        analyze(data_conn, (
            "core.price", "core.price_body_group", "core.price_dates",
            "core.city", "core.body_group", "core.body_type",
        ))
    except Exception:
        data_conn.rollback()
        raise

    try:
        run_stage(
            audit, STAGE_MART_ROUTE_CARD,
            lambda: rebuild_mart_route_card(data_conn, as_of),
        )
        data_conn.commit()
    except Exception:
        data_conn.rollback()
        raise


def run_incremental(audit, data_conn, run_id, args, as_of):
    window_start, window_end = get_incremental_window(as_of)

    try:
        run_stage(
            audit, STAGE_SOURCE_TO_RAW_CHANGES,
            lambda: load_source_to_raw_changes(
                data_conn, run_id, window_start,
            ),
        )
        data_conn.commit()
        analyze(data_conn, (
            "raw.prices", "raw.price_body_types", "raw.price_dates",
            "raw.cities", "raw.body_types", "raw.exchange_rates",
        ))
    except Exception:
        data_conn.rollback()
        raise

    try:
        run_stage(
            audit, STAGE_RAW_TO_CORE_REFERENCE,
            lambda: load_core_reference(data_conn, run_id),
        )
        run_stage(
            audit, STAGE_RAW_TO_CORE_PRICE,
            lambda: load_core_price_changes(data_conn, run_id),
        )
        data_conn.commit()
        analyze(data_conn, (
            "core.price", "core.price_body_group", "core.price_dates",
            "core.city", "core.body_group", "core.body_type",
        ))
    except Exception:
        data_conn.rollback()
        raise

    try:
        run_stage(
            audit, STAGE_MART_ROUTE_CARD,
            lambda: rebuild_mart_route_card_partitions(data_conn, as_of),
        )
        data_conn.commit()
    except Exception:
        data_conn.rollback()
        raise

def run():
    args = parse_args()

    try:
        validate_run_config(args)
    except ConfigError as e:
        log.error("config error: %s", e)
        return 2

    as_of = get_as_of(args)

    data_conn = connect(autocommit=False)
    audit_conn = connect(autocommit=True)
    audit = Audit(audit_conn)

    try:
        if args.run_type == "backfill":
            interval_start = args.interval_start
            interval_end = args.interval_end
        else:
            interval_start, interval_end = get_incremental_window(as_of)

        audit.start_run(interval_start, interval_end, args.triggered_by,
                        run_type=args.run_type)
    except psycopg2.errors.ExclusionViolation:
        log.error(
            "another ETL run is in progress; aborting"
        )
        data_conn.close()
        audit_conn.close()
        return 1

    run_id = audit.run_id
    log.info(
        "run %s started: type=%s interval=[%s, %s) as_of=%s",
        run_id, args.run_type, interval_start, interval_end, as_of,
    )

    try:
        if args.run_type == "backfill":
            run_backfill(audit, data_conn, run_id, args, as_of)
        else:
            run_incremental(audit, data_conn, run_id, args, as_of)
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