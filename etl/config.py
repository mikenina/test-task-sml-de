import argparse
import os
from datetime import date


class ConfigError(ValueError):
    pass


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval-start", required=True, type=date.fromisoformat)
    parser.add_argument("--interval-end", required=True, type=date.fromisoformat)
    parser.add_argument("--triggered-by", default="manual", choices=["manual"])
    return parser.parse_args()


def validate_interval(start, end):
    if start >= end:
        raise ConfigError(
            f"interval_start ({start}) must be < interval_end ({end})"
        )
    delta = (end - start).days
    if delta < 1:
        raise ConfigError(f"interval must be >= 1 day, got {delta}")
    if delta > 5 * 365 + 1:
        raise ConfigError(f"interval must be <= 5 years, got {delta} days")


def get_as_of():
    return date.fromisoformat(os.environ.get("AS_OF", "2026-10-26"))