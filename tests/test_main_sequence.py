import pytest
from unittest.mock import MagicMock
from datetime import date

from etl import main as etl_main


@pytest.fixture
def fake_conn():
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value = MagicMock()
    return conn


def _stages(audit):
    return [c.args[0] for c in audit.start_stage.call_args_list]


def _patch_common(monkeypatch):
    monkeypatch.setattr(etl_main, "connect", lambda autocommit=False: MagicMock())
    monkeypatch.setattr(etl_main, "analyze", lambda *a, **k: None)
    monkeypatch.setattr(etl_main, "load_core_reference", lambda *a, **k: {"details": {}})
    monkeypatch.setattr(etl_main, "run_ml_pipeline", lambda *a, **k: {"rows_out": 0})
    monkeypatch.setattr(etl_main, "validate_run_config", lambda a: None)
    monkeypatch.setattr(etl_main, "get_as_of", lambda a: a.as_of)


def test_backfill_stage_order(monkeypatch):
    _patch_common(monkeypatch)
    monkeypatch.setattr(etl_main, "load_source_to_raw", lambda *a, **k: {"rows_out": 0})
    monkeypatch.setattr(etl_main, "load_core_price", lambda *a, **k: {"rows_out": 0})
    monkeypatch.setattr(etl_main, "rebuild_mart_route_card", lambda *a, **k: {"rows_out": 0})

    args = MagicMock(
        run_type="backfill",
        interval_start=date(2026, 9, 1),
        interval_end=date(2026, 10, 1),
        as_of=date(2026, 10, 26),
        triggered_by="manual",
    )
    monkeypatch.setattr(etl_main, "parse_args", lambda: args)

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
    _patch_common(monkeypatch)
    monkeypatch.setattr(etl_main, "load_source_to_raw_changes", lambda *a, **k: {"rows_out": 0})
    monkeypatch.setattr(etl_main, "load_core_price_changes", lambda *a, **k: {"rows_out": 0})
    monkeypatch.setattr(etl_main, "rebuild_mart_route_card_partitions", lambda *a, **k: {"rows_out": 0})

    args = MagicMock(
        run_type="incremental",
        interval_start=None,
        interval_end=None,
        as_of=date(2026, 10, 26),
        triggered_by="manual",
    )
    monkeypatch.setattr(etl_main, "parse_args", lambda: args)

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


def test_incremental_with_custom_interval(monkeypatch):
    _patch_common(monkeypatch)
    captured = {}

    def fake_load_source(conn, run_id, window_start, window_end=None):
        captured["window_start"] = window_start
        captured["window_end"] = window_end
        return {"rows_out": 0}

    monkeypatch.setattr(etl_main, "load_source_to_raw_changes", fake_load_source)
    monkeypatch.setattr(etl_main, "load_core_price_changes", lambda *a, **k: {"rows_out": 0})
    monkeypatch.setattr(etl_main, "rebuild_mart_route_card_partitions", lambda *a, **k: {"rows_out": 0})

    args = MagicMock(
        run_type="incremental",
        interval_start=date(2026, 10, 19),
        interval_end=date(2026, 10, 26),
        as_of=date(2026, 10, 26),
        triggered_by="manual",
    )
    monkeypatch.setattr(etl_main, "parse_args", lambda: args)

    audit = MagicMock(run_id=1)
    monkeypatch.setattr(etl_main, "Audit", lambda conn: audit)

    rc = etl_main.run()
    assert rc == 0
    assert captured["window_start"] == date(2026, 10, 19)
    assert captured["window_end"] == date(2026, 10, 26)


def test_incremental_open_ended_interval(monkeypatch):
    _patch_common(monkeypatch)
    captured = {}

    def fake_load_source(conn, run_id, window_start, window_end=None):
        captured["window_start"] = window_start
        captured["window_end"] = window_end
        return {"rows_out": 0}

    monkeypatch.setattr(etl_main, "load_source_to_raw_changes", fake_load_source)
    monkeypatch.setattr(etl_main, "load_core_price_changes", lambda *a, **k: {"rows_out": 0})
    monkeypatch.setattr(etl_main, "rebuild_mart_route_card_partitions", lambda *a, **k: {"rows_out": 0})

    args = MagicMock(
        run_type="incremental",
        interval_start=date(2026, 10, 19),
        interval_end=None,
        as_of=date(2026, 10, 26),
        triggered_by="manual",
    )
    monkeypatch.setattr(etl_main, "parse_args", lambda: args)

    audit = MagicMock(run_id=1)
    monkeypatch.setattr(etl_main, "Audit", lambda conn: audit)

    rc = etl_main.run()
    assert rc == 0
    assert captured["window_start"] == date(2026, 10, 19)
    assert captured["window_end"] is None


def test_validate_rejects_backfill_without_interval():
    from etl.config import ConfigError, validate_run_config
    args = MagicMock(run_type="backfill", interval_start=None, interval_end=None, as_of=date(2026, 10, 26))
    with pytest.raises(ConfigError):
        validate_run_config(args)


def test_validate_rejects_incremental_without_as_of():
    from etl.config import ConfigError, validate_run_config
    args = MagicMock(run_type="incremental", interval_start=None, interval_end=None, as_of=None)
    with pytest.raises(ConfigError):
        validate_run_config(args)


def test_validate_rejects_incremental_interval_end_without_start():
    from etl.config import ConfigError, validate_run_config
    args = MagicMock(
        run_type="incremental",
        interval_start=None,
        interval_end=date(2026, 10, 26),
        as_of=date(2026, 10, 26),
    )
    with pytest.raises(ConfigError):
        validate_run_config(args)


def test_validate_accepts_incremental_open_ended():
    from etl.config import validate_run_config
    args = MagicMock(
        run_type="incremental",
        interval_start=date(2026, 10, 19),
        interval_end=None,
        as_of=date(2026, 10, 26),
    )
    validate_run_config(args)  # не должно бросить


def test_exclusion_violation_returns_1(monkeypatch):
    import psycopg2

    _patch_common(monkeypatch)
    monkeypatch.setattr(etl_main, "parse_args", lambda: MagicMock(
        run_type="backfill",
        interval_start=date(2026, 9, 1),
        interval_end=date(2026, 10, 1),
        as_of=date(2026, 10, 26),
        triggered_by="manual",
    ))

    audit = MagicMock()
    audit.start_run.side_effect = psycopg2.errors.ExclusionViolation()
    monkeypatch.setattr(etl_main, "Audit", lambda conn: audit)

    assert etl_main.run() == 1