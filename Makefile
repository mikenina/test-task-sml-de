PSQL := PGPASSWORD=$$POSTGRES_PASSWORD psql -h $$POSTGRES_HOST -U $$POSTGRES_USER -d $$POSTGRES_DB -v ON_ERROR_STOP=1
AS_OF ?= 2026-10-26
INTERVAL_START ?= 2023-10-03
INTERVAL_END ?= 2027-02-13

.PHONY: test smoke smoke-reset

test:
	python -m pytest tests/ -v

smoke:
	@echo "== reset dwh"
	$(PSQL) -c "TRUNCATE core.price CASCADE; TRUNCATE core.city CASCADE; TRUNCATE core.body_type CASCADE; TRUNCATE mart.route_card; TRUNCATE mart.ml_price_predictions; TRUNCATE dq.quarantine_prices; TRUNCATE dq.etl_run_stages CASCADE; TRUNCATE dq.etl_runs CASCADE;"
	$(PSQL) -c "TRUNCATE raw.prices; TRUNCATE raw.cities; TRUNCATE raw.body_types; TRUNCATE raw.price_body_types; TRUNCATE raw.price_dates; TRUNCATE raw.exchange_rates;"

	@echo "== backfill #1 (prerequisite)"
	python -m etl.main --run-type backfill --as-of $(AS_OF) --interval-start $(INTERVAL_START) --interval-end $(INTERVAL_END)

	@echo "== snapshot"
	$(PSQL) -c "CREATE TABLE IF NOT EXISTS dq._smoke_snapshot (captured_at timestamptz DEFAULT now(), core_price_cnt bigint, core_bridge_cnt bigint, core_dates_cnt bigint, mart_cnt bigint, ml_cnt bigint, quarantine_cnt bigint)"
	$(PSQL) -f tests/sql/03_idempotency_snapshot.sql

	@echo "== backfill #2 (idempotency)"
	python -m etl.main --run-type backfill --as-of $(AS_OF) --interval-start $(INTERVAL_START) --interval-end $(INTERVAL_END)

	@echo "== smoke checks"
	$(PSQL) -f tests/sql/01_raw_no_duplicates.sql
	$(PSQL) -f tests/sql/02_core_price_no_duplicates.sql
	$(PSQL) -f tests/sql/03_idempotency_check.sql
	$(PSQL) -f tests/sql/04_core_price_dq_invariants.sql
	$(PSQL) -f tests/sql/05_core_main_body_in_bridge.sql
	$(PSQL) -v my_as_of=$(AS_OF) -f tests/sql/06_mart_no_future_months.sql
	$(PSQL) -f tests/sql/07_core_city_dedup.sql
	$(PSQL) -f tests/sql/08_quarantine_no_duplicates.sql
	$(PSQL) -f tests/sql/09_mart_dq_invariants.sql
	@echo "smoke ok"

smoke-reset:
	$(PSQL) -c "DROP TABLE IF EXISTS dq._smoke_snapshot"