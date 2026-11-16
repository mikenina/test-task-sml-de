import pytest
from unittest.mock import MagicMock, patch
from datetime import date

from etl import main as etl_main


@pytest.fixture
def fake_conn():
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value = MagicMock()
    return conn


def _stages(audit):
    return [c.args[0] for c in audit.start_stage.call_args_list]


def test_backfill_stage_order(monkeypatch):
    monkeypatch.setattr(etl_main, "connect", lambda autocommit=False: MagicMock())
    monkeypatch.setattr(etl_main, "Audit", lambda conn: MagicMock(run_id=1))
    monkeypatch.setattr(etl_main, "load_source_to_raw", lambda *a, **k: {"rows_out": 0})
    monkeypatch.setattr(etl_main, "load_core_reference", lambda *a, **k: {"details": {}})
    monkeypatch.setattr(etl_main, "load_core_price", lambda *a, **k: {"rows_out": 0})
    monkeypatch.setattr(etl_main, "rebuild_mart_route_card", lambda *a, **k: {"rows_out": 0})
    monkeypatch.setattr(etl_main, "run_ml_pipeline", lambda *a, **k: {"rows_out": 0})
    monkeypatch.setattr(etl_main, "analyze", lambda *a, **k: None)

    args = MagicMock(
        run_type="backfill",
        interval_start=date(2026, 9, 1),
        interval_end=date(2026, 10, 1),
        as_of=date(2026, 10, 26),
        triggered_by="manual",
    )
    monkeypatch.setattr(etl_main, "parse_args", lambda: args)
    monkeypatch.setattr(etl_main, "validate_run_config", lambda a: None)
    monkeypatch.setattr(etl_main, "get_as_of", lambda a: a.as_of)

    audit = MagicMock(run_id=1)
    monkeypatch.setattr(etl_main, "Audit", lambda conn: audit)

    rc = etl_main.run()
    assert rc == 0
    assert _stages(audit) == [
        "source_to_raw",
        "raw_to_core.reference",
        "raw_to_core.price",
        "core_to_mart.route_card",
        "ml",
    ]


def test_incremental_stage_order(monkeypatch):
    monkeypatch.setattr(etl_main, "connect", lambda autocommit=False: MagicMock())
    monkeypatch.setattr(etl_main, "load_source_to_raw_changes", lambda *a, **k: {"rows_out": 0})
    monkeypatch.setattr(etl_main, "load_core_reference", lambda *a, **k: {"details": {}})
    monkeypatch.setattr(etl_main, "load_core_price_changes", lambda *a, **k: {"rows_out": 0})
    monkeypatch.setattr(etl_main, "rebuild_mart_route_card_partitions", lambda *a, **k: {"rows_out": 0})
    monkeypatch.setattr(etl_main, "run_ml_pipeline", lambda *a, **k: {"rows_out": 0})
    monkeypatch.setattr(etl_main, "analyze", lambda *a, **k: None)

    args = MagicMock(
        run_type="incremental",
        interval_start=None,
        interval_end=None,
        as_of=date(2026, 10, 26),
        triggered_by="manual",
    )
    monkeypatch.setattr(etl_main, "parse_args", lambda: args)
    monkeypatch.setattr(etl_main, "validate_run_config", lambda a: None)
    monkeypatch.setattr(etl_main, "get_as_of", lambda a: a.as_of)

    audit = MagicMock(run_id=1)
    monkeypatch.setattr(etl_main, "Audit", lambda conn: audit)

    rc = etl_main.run()
    assert rc == 0
    assert _stages(audit) == [
        "source_to_raw.changes",
        "raw_to_core.reference",
        "raw_to_core.price",
        "core_to_mart.route_card",
        "ml",
    ]
    audit.start_run.assert_called_once()
    _, kwargs = audit.start_run.call_args
    assert kwargs["run_type"] == "incremental"


def test_validate_rejects_backfill_without_interval():
    from etl.config import ConfigError, validate_run_config
    args = MagicMock(run_type="backfill", interval_start=None, interval_end=None, as_of=date(2026, 10, 26))
    with pytest.raises(ConfigError):
        validate_run_config(args)


def test_validate_rejects_incremental_with_interval():
    from etl.config import ConfigError, validate_run_config
    args = MagicMock(
        run_type="incremental",
        interval_start=date(2026, 9, 1),
        interval_end=date(2026, 10, 1),
        as_of=date(2026, 10, 26),
    )
    with pytest.raises(ConfigError):
        validate_run_config(args)


def test_exclusion_violation_returns_1(monkeypatch):
    import psycopg2
    from etl import main as etl_main

    monkeypatch.setattr(etl_main, "connect", lambda autocommit=False: MagicMock())
    monkeypatch.setattr(etl_main, "parse_args", lambda: MagicMock(
        run_type="backfill",
        interval_start=date(2026, 9, 1),
        interval_end=date(2026, 10, 1),
        as_of=date(2026, 10, 26),
        triggered_by="manual",
    ))
    monkeypatch.setattr(etl_main, "validate_run_config", lambda a: None)
    monkeypatch.setattr(etl_main, "get_as_of", lambda a: a.as_of)

    audit = MagicMock()
    audit.start_run.side_effect = psycopg2.errors.ExclusionViolation()
    monkeypatch.setattr(etl_main, "Audit", lambda conn: audit)

    assert etl_main.run() == 1