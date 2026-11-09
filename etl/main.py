import argparse
import logging
import os
import sys
from datetime import date

import psycopg2

from etl.audit import Audit
from etl.loader import load_prices, load_price_dates, load_price_body_types, load_reference
from etl.stages import (
    STAGE_RAW_PRICES,
    STAGE_RAW_PRICE_DATES,
    STAGE_RAW_PRICE_BODY_TYPES,
    STAGE_RAW_REFERENCE,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("etl")


def connect(autocommit=False):
    conn = psycopg2.connect(
        host=os.environ.get("POSTGRES_HOST", "postgres"),
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    )
    conn.autocommit = autocommit
    return conn


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval-start", required=True, type=date.fromisoformat)
    parser.add_argument("--interval-end", required=True, type=date.fromisoformat)
    parser.add_argument("--triggered-by", default="manual")
    return parser.parse_args()


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
    if args.interval_start >= args.interval_end:
        raise SystemExit(
            f"interval_start ({args.interval_start}) must be < "
            f"interval_end ({args.interval_end})"
        )

    data_conn = connect()
    audit_conn = connect(autocommit=True)
    audit = Audit(audit_conn)
    audit.start_run(args.interval_start, args.interval_end, args.triggered_by)
    log.info(
        "run %s started: interval=[%s, %s)",
        audit.run_id, args.interval_start, args.interval_end,
    )

    try:
        run_stage(
            audit, STAGE_RAW_PRICES,
            lambda: {"rows_out": load_prices(data_conn, args.interval_start, args.interval_end)},
        )
        run_stage(
            audit, STAGE_RAW_PRICE_DATES,
            lambda: {"rows_out": load_price_dates(data_conn, args.interval_start, args.interval_end)},
        )
        run_stage(
            audit, STAGE_RAW_PRICE_BODY_TYPES,
            lambda: {"rows_out": load_price_body_types(data_conn, args.interval_start, args.interval_end)},
        )

        data_conn.commit()

        run_stage(
            audit, STAGE_RAW_REFERENCE,
            lambda: {"details": load_reference(data_conn)},
        )

        data_conn.commit()
    except Exception as e:
        data_conn.rollback()
        log.exception("run %s failed", audit.run_id)
        audit.finish_run("failed", error_message=str(e))
        data_conn.close()
        audit_conn.close()
        return 1

    audit.finish_run("success")
    log.info("run %s finished: success", audit.run_id)
    data_conn.close()
    audit_conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(run())