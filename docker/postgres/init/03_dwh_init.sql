-- ============================================================
-- Расширения
-- ============================================================
CREATE EXTENSION IF NOT EXISTS btree_gist;


-- ============================================================
-- Схемы
-- ============================================================
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS mart;
CREATE SCHEMA IF NOT EXISTS dq;

COMMENT ON SCHEMA raw IS 'Immutable snapshots источника, версионированные по run_id.';
COMMENT ON SCHEMA core IS 'Очищенные эталонные данные (без SCD).';
COMMENT ON SCHEMA mart IS 'Аналитические витрины.';
COMMENT ON SCHEMA dq IS 'Аудит ETL, карантин, статистика качества.';


-- ============================================================
-- RAW
-- ============================================================
CREATE TABLE IF NOT EXISTS raw.prices (
    LIKE public.prices INCLUDING DEFAULTS INCLUDING CONSTRAINTS,
    run_id bigint NOT NULL,
    inserted_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT pk_raw_prices PRIMARY KEY (run_id, id)
);

CREATE TABLE IF NOT EXISTS raw.cities (
    LIKE public.cities INCLUDING DEFAULTS INCLUDING CONSTRAINTS,
    run_id bigint NOT NULL,
    inserted_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT pk_raw_cities PRIMARY KEY (run_id, id)
);

CREATE TABLE IF NOT EXISTS raw.body_types (
    LIKE public.body_types INCLUDING DEFAULTS INCLUDING CONSTRAINTS,
    run_id bigint NOT NULL,
    inserted_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT pk_raw_body_types PRIMARY KEY (run_id, id)
);

CREATE TABLE IF NOT EXISTS raw.price_body_types (
    LIKE public.price_body_types INCLUDING DEFAULTS INCLUDING CONSTRAINTS,
    run_id bigint NOT NULL,
    inserted_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT pk_raw_price_body_types PRIMARY KEY (run_id, id)
);

CREATE TABLE IF NOT EXISTS raw.price_dates (
    LIKE public.price_dates INCLUDING DEFAULTS INCLUDING CONSTRAINTS,
    run_id bigint NOT NULL,
    inserted_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT pk_raw_price_dates PRIMARY KEY (run_id, id)
);

CREATE TABLE IF NOT EXISTS raw.exchange_rates (
    LIKE public.exchange_rates INCLUDING DEFAULTS INCLUDING CONSTRAINTS,
    run_id bigint NOT NULL,
    inserted_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT pk_raw_exchange_rates PRIMARY KEY (run_id, id)
);

CREATE INDEX IF NOT EXISTS idx_raw_prices_run_id_loading_date
    ON raw.prices (run_id, loading_date);


-- ============================================================
-- CORE
-- ============================================================
CREATE TABLE IF NOT EXISTS core.city (
    gc_id integer PRIMARY KEY,
    city_id bigint NOT NULL,
    name text NOT NULL,
    region text,
    latitude double precision,
    longitude double precision
);

CREATE TABLE IF NOT EXISTS core.body_group (
    id smallint PRIMARY KEY,
    name text NOT NULL UNIQUE
);

INSERT INTO core.body_group (id, name) VALUES
    (1, 'Тент'),
    (2, 'Рефрижератор'),
    (3, 'Изотерм'),
    (4, 'Борт'),
    (5, 'Прочие')
ON CONFLICT (id) DO NOTHING;

CREATE TABLE IF NOT EXISTS core.body_type (
    id integer PRIMARY KEY,
    name text NOT NULL,
    body_group_id smallint NOT NULL REFERENCES core.body_group(id)
);

CREATE TABLE IF NOT EXISTS core.price (
    price_id bigint PRIMARY KEY,
    loading_date date NOT NULL,
    loading_city_gcid integer NOT NULL,
    unloading_city_gcid integer NOT NULL,
    distance double precision NOT NULL,
    total_weight double precision NOT NULL,
    total_volume double precision NOT NULL,
    main_body_type_id integer REFERENCES core.body_type(id),
    weight_category varchar(4) NOT NULL,
    volume_category varchar(4) NOT NULL,
    price double precision NOT NULL,
    currency_code varchar(3) NOT NULL,
    price_rub double precision NOT NULL,
    price_type smallint NOT NULL,
    organization_id integer,
    outlier_mark boolean NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_core_price_loading_date
    ON core.price (loading_date);

CREATE TABLE IF NOT EXISTS core.price_body_group (
    price_id bigint NOT NULL
        REFERENCES core.price(price_id) ON DELETE CASCADE,
    body_group_id smallint NOT NULL
        REFERENCES core.body_group(id),
    PRIMARY KEY (price_id, body_group_id)
);

CREATE TABLE IF NOT EXISTS core.price_dates (
    price_id bigint NOT NULL
        REFERENCES core.price(price_id) ON DELETE CASCADE,
    price_date date NOT NULL,
    PRIMARY KEY (price_id, price_date)
);

CREATE TABLE IF NOT EXISTS mart.route_card (
    month date NOT NULL,
    loading_city_gcid integer NOT NULL,
    unloading_city_gcid integer NOT NULL,
    body_group_id smallint NOT NULL,
    weight_category varchar(4) NOT NULL,

    trips_count bigint NOT NULL,
    carriers_count bigint NOT NULL,

    p25_trip numeric(14,2) NOT NULL,
    median_trip numeric(14,2) NOT NULL,
    p75_trip numeric(14,2) NOT NULL,
    avg_trip numeric(14,2) NOT NULL,

    p25_km numeric(10,2) NOT NULL,
    median_km numeric(10,2) NOT NULL,
    p75_km numeric(10,2) NOT NULL,

    cv_rate numeric(10,4),
    mom_pct numeric(10,2),
    yoy_pct numeric(10,2),

    reliability_level varchar(10) NOT NULL
        CONSTRAINT ck_route_card_reliability
        CHECK (reliability_level IN ('HIGH', 'MEDIUM', 'LOW_DATA')),

    CONSTRAINT pk_route_card PRIMARY KEY (
        month, loading_city_gcid, unloading_city_gcid,
        body_group_id, weight_category
    )
);

COMMENT ON COLUMN mart.route_card.body_group_id IS
    'body_group_id = 0 = «Не указан»; 1..5 соответствует core.body_group.id.';

CREATE INDEX IF NOT EXISTS idx_route_card_route
    ON mart.route_card (loading_city_gcid, unloading_city_gcid, body_group_id, weight_category, month);

-- ============================================================
-- DQ
-- ============================================================
CREATE TABLE IF NOT EXISTS dq.etl_runs (
    id bigserial PRIMARY KEY,
    run_type varchar(15) NOT NULL DEFAULT 'backfill'
        CONSTRAINT ck_etl_runs_run_type
        CHECK (run_type IN ('backfill', 'incremental')),
    run_started_at timestamptz NOT NULL DEFAULT now(),
    run_finished_at timestamptz,
    data_interval_start date NOT NULL,
    data_interval_end date,
    status varchar(10) NOT NULL DEFAULT 'running'
        CONSTRAINT ck_etl_runs_status
        CHECK (status IN ('running', 'success', 'failed')),
    triggered_by varchar(10) NOT NULL DEFAULT 'manual'
        CONSTRAINT ck_etl_runs_triggered_by
        CHECK (triggered_by IN ('manual')),
    error_message text,
    inserted_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT etl_runs_single_running
        EXCLUDE USING gist ((1) WITH =) WHERE (status = 'running')
);

CREATE TABLE IF NOT EXISTS dq.etl_run_stages (
    id bigserial PRIMARY KEY,
    run_id bigint NOT NULL
        REFERENCES dq.etl_runs(id) ON DELETE CASCADE,
    stage_name text NOT NULL,
    stage_started_at timestamptz NOT NULL DEFAULT now(),
    stage_finished_at timestamptz,
    status varchar(10) NOT NULL DEFAULT 'running'
        CONSTRAINT ck_etl_run_stages_status
        CHECK (status IN ('running', 'success', 'failed')),
    rows_in bigint,
    rows_out bigint,
    rows_quarantined bigint,
    details jsonb,
    error_message text,
    inserted_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_etl_run_stages_run_id_stage_name UNIQUE (run_id, stage_name)
);

CREATE TABLE IF NOT EXISTS dq.quarantine_prices (
    price_id bigint NOT NULL,
    run_id bigint NOT NULL
        REFERENCES dq.etl_runs(id) ON DELETE CASCADE,
    reason_code varchar(30) NOT NULL,
    reason_detail text,
    payload jsonb,
    inserted_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (run_id, price_id, reason_code)
);