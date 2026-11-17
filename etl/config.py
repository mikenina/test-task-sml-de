import argparse
import os
from datetime import date


class ConfigError(ValueError):
    """Ошибка валидации параметров запуска ETL."""


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-type", choices=["backfill", "incremental"],
                        default="backfill")
    parser.add_argument(
        "--interval-start", type=date.fromisoformat,
        help="backfill: обязателен, нижняя граница loading_date. "
             "incremental: опционален, нижняя граница updated_at "
             "(по умолчанию as_of - 1 day)",
    )
    parser.add_argument(
        "--interval-end", type=date.fromisoformat,
        help="backfill: обязателен, верхняя граница loading_date. "
             "incremental: опционален, верхняя граница updated_at "
             "(по умолчанию NULL — открыто вправо)",
    )
    parser.add_argument("--as-of", type=date.fromisoformat,
                        help="дата среза для mart и ML")
    parser.add_argument("--triggered-by", default="manual",
                        choices=["manual", "auto"])
    return parser.parse_args()

def validate_run_config(args):
    if args.run_type == "backfill":
        if not args.as_of:
            raise ConfigError("backfill requires --as-of")
        if not args.interval_start or not args.interval_end:
            raise ConfigError(
                "backfill requires --interval-start and --interval-end"
            )
        if args.interval_start >= args.interval_end:
            raise ConfigError(
                f"interval_start ({args.interval_start}) must be < "
                f"interval_end ({args.interval_end})"
            )
        delta = (args.interval_end - args.interval_start).days
        if delta < 1:
            raise ConfigError(f"interval must be >= 1 day, got {delta}")
        if delta > 5 * 365 + 1:
            raise ConfigError(f"interval must be <= 5 years, got {delta} days")
    elif args.run_type == "incremental":
        if not args.as_of:
            raise ConfigError("incremental requires --as-of")

        if args.interval_start is None and args.interval_end is not None:
            raise ConfigError(
                "incremental: --interval-end requires --interval-start"
            )

        if (args.interval_start is not None
                and args.interval_end is not None
                and args.interval_start >= args.interval_end):
            raise ConfigError(
                f"interval_start ({args.interval_start}) must be < "
                f"interval_end ({args.interval_end})"
            )


def get_as_of(args):
    if args.as_of:
        return args.as_of
