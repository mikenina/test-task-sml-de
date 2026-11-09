CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS mart;
CREATE SCHEMA IF NOT EXISTS dq;

CREATE TABLE IF NOT EXISTS raw.prices (
    LIKE public.prices INCLUDING DEFAULTS
);
CREATE TABLE IF NOT EXISTS raw.cities (
    LIKE public.cities INCLUDING DEFAULTS
);
CREATE TABLE IF NOT EXISTS raw.body_types (
    LIKE public.body_types INCLUDING DEFAULTS
);
CREATE TABLE IF NOT EXISTS raw.price_body_types (
    LIKE public.price_body_types INCLUDING DEFAULTS
);
CREATE TABLE IF NOT EXISTS raw.price_dates (
    LIKE public.price_dates INCLUDING DEFAULTS
);
CREATE TABLE IF NOT EXISTS raw.exchange_rates (
    LIKE public.exchange_rates INCLUDING DEFAULTS
);

CREATE TABLE IF NOT EXISTS dq.quarantine_prices (
    price_id bigint NOT NULL,
    reason_code varchar(20) NOT NULL,
    reason_detail text,
    payload jsonb,
    inserted_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (price_id, reason_code)
);

CREATE INDEX IF NOT EXISTS idx_quarantine_prices_reason_code
    ON dq.quarantine_prices (reason_code);

CREATE TABLE IF NOT EXISTS dq.etl_runs (
    id                  bigserial    PRIMARY KEY,

    -- Тип прогона. incremental зарезервирован под CDC по updated_at,
    -- в тестовом задании не реализован (см. README).
    run_type            varchar(15)  NOT NULL DEFAULT 'backfill'
                        CONSTRAINT ck_etl_runs_run_type
                        CHECK (run_type IN ('backfill', 'incremental')),

    -- Wall clock: когда физически шёл прогон
    run_started_at      timestamptz  NOT NULL DEFAULT now(),
    run_finished_at     timestamptz,

    -- Логическое окно данных: полуоткрытый интервал [start, end) по loading_date
    -- Валидация (start < end) — в etl/config.py, не в БД:
    -- аудит не должен падать из-за кривых параметров запуска.
    data_interval_start date         NOT NULL,
    data_interval_end   date         NOT NULL,

    -- Итог прогона
    status              varchar(10)  NOT NULL DEFAULT 'running'
                        CONSTRAINT ck_etl_runs_status
                        CHECK (status IN ('running', 'success', 'failed', 'partial')),

    -- Кто инициировал прогон
    triggered_by        varchar(10)  NOT NULL DEFAULT 'manual'
                        CONSTRAINT ck_etl_runs_triggered_by
                        CHECK (triggered_by IN ('manual', 'airflow', 'ci')),

    -- Заполняется только при status = 'failed'
    error_message       text
);

COMMENT ON TABLE  dq.etl_runs IS
    'Шапка прогона ETL. Одна строка = один запуск. '
    'data_interval_* — полуоткрытый интервал [start, end) по loading_date; '
    'run_started_at / run_finished_at — wall clock. '
    'Валидация интервала — в etl/config.py, не в БД.';

COMMENT ON COLUMN dq.etl_runs.run_type            IS 'backfill | incremental (incremental зарезервирован под CDC, в тесте не реализован)';
COMMENT ON COLUMN dq.etl_runs.run_started_at      IS 'Wall clock: когда начался прогон ETL.';
COMMENT ON COLUMN dq.etl_runs.run_finished_at     IS 'Wall clock: когда закончился прогон. NULL — упал или ещё идёт.';
COMMENT ON COLUMN dq.etl_runs.data_interval_start IS 'Логическое окно данных: нижняя граница loading_date (включительно).';
COMMENT ON COLUMN dq.etl_runs.data_interval_end   IS 'Логическое окно данных: верхняя граница loading_date (не включается).';
COMMENT ON COLUMN dq.etl_runs.status              IS 'running | success | failed | partial';
COMMENT ON COLUMN dq.etl_runs.triggered_by        IS 'manual | airflow | ci';
COMMENT ON COLUMN dq.etl_runs.error_message       IS 'Текст исключения, если status = failed.';

CREATE INDEX IF NOT EXISTS idx_etl_runs_run_started_at
    ON dq.etl_runs (run_started_at DESC);

CREATE INDEX IF NOT EXISTS idx_etl_runs_data_interval
    ON dq.etl_runs (data_interval_start, data_interval_end);


-- ============================================================
-- dq.etl_run_stages — детализация по стадиям прогона
-- Одна строка = одна стадия внутри прогона.
-- stage_name — свободный text: конвенция <from>_to_<to>.<object>,
-- список стадий будет расти (Airflow, ClickHouse), CHECK не ставим.
-- ============================================================
CREATE TABLE IF NOT EXISTS dq.etl_run_stages (
    id                  bigserial    PRIMARY KEY,
    run_id              bigint       NOT NULL
                        REFERENCES dq.etl_runs(id) ON DELETE CASCADE,

    -- 'source_to_raw.prices', 'source_to_raw.reference',
    -- 'raw_to_core.fact_price', 'core_to_mart.mart_route_card', 'ml.train', 'ml.predict'
    stage_name          text         NOT NULL,

    stage_started_at    timestamptz  NOT NULL DEFAULT now(),
    stage_finished_at   timestamptz,

    status              varchar(10)  NOT NULL DEFAULT 'running'
                        CONSTRAINT ck_etl_run_stages_status
                        CHECK (status IN ('running', 'success', 'failed', 'skipped', 'unknown')),

    rows_in             bigint,
    rows_out            bigint,
    rows_quarantined    bigint,

    -- Для стадии source_to_raw.reference:
    --   {"cities": 42, "body_types": 17, "price_body_types": 312000, "exchange_rates": 890}
    -- Для raw_to_core.fact_price:
    --   {"quarantine_by_reason": {"rate_missing": 1247, "price_too_low_rub": 147}}
    details             jsonb,

    error_message       text,

    CONSTRAINT uq_etl_run_stages_run_id_stage_name UNIQUE (run_id, stage_name)
);

COMMENT ON TABLE  dq.etl_run_stages IS
    'Детализация прогона ETL по стадиям. stage_name — свободный text, '
    'конвенция <from>_to_<to>.<object>. Справочники логируются одной стадией '
    'source_to_raw.reference с counts в details.';

COMMENT ON COLUMN dq.etl_run_stages.stage_name        IS 'Например: source_to_raw.prices, source_to_raw.reference, raw_to_core.fact_price, core_to_mart.mart_route_card, ml.train, ml.predict';
COMMENT ON COLUMN dq.etl_run_stages.stage_started_at  IS 'Wall clock: когда началась стадия.';
COMMENT ON COLUMN dq.etl_run_stages.stage_finished_at IS 'Wall clock: когда закончилась стадия. NULL — упала или ещё идёт.';
COMMENT ON COLUMN dq.etl_run_stages.status            IS 'running | success | failed | skipped | unknown (unknown — после reconciliation-свипа зависших running)';
COMMENT ON COLUMN dq.etl_run_stages.rows_in           IS 'Сколько строк прочитано из источника (для source_to_raw.*).';
COMMENT ON COLUMN dq.etl_run_stages.rows_out          IS 'Сколько строк записано в целевую таблицу.';
COMMENT ON COLUMN dq.etl_run_stages.rows_quarantined  IS 'Сколько строк ушло в dq.quarantine_prices.';
COMMENT ON COLUMN dq.etl_run_stages.details           IS 'Произвольная статистика стадии: quarantine_by_reason, counts по справочникам и т.п.';
COMMENT ON COLUMN dq.etl_run_stages.error_message     IS 'Текст исключения, если status = failed.';

CREATE INDEX IF NOT EXISTS idx_etl_run_stages_run_id
    ON dq.etl_run_stages (run_id);

CREATE INDEX IF NOT EXISTS idx_etl_run_stages_stage_name
    ON dq.etl_run_stages (stage_name);

CREATE INDEX IF NOT EXISTS idx_etl_run_stages_status_started_at
    ON dq.etl_run_stages (status, stage_started_at)
    WHERE status = 'running';
