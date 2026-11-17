def load_core_reference(conn, run_id):
    with conn.cursor() as cur:
        cur.execute(
            """
            WITH dedup AS (
                SELECT DISTINCT ON (gc_id)
                    gc_id,
                    id AS city_id,
                    name,
                    NULLIF(TRIM(split_part(full_name_local, ',', 2)), '') AS region,
                    latitude,
                    longitude
                FROM raw.cities
                WHERE run_id = %s
                ORDER BY gc_id, id
            )
            INSERT INTO core.city (gc_id, city_id, name, region, latitude, longitude)
            SELECT gc_id, city_id, name, region, latitude, longitude
            FROM dedup
            ON CONFLICT (gc_id) DO UPDATE SET
                city_id = EXCLUDED.city_id,
                name = EXCLUDED.name,
                region = EXCLUDED.region,
                latitude = EXCLUDED.latitude,
                longitude = EXCLUDED.longitude
            """,
            (run_id,),
        )
        city_count = cur.rowcount

        cur.execute(
            """
            INSERT INTO core.body_type (id, name, body_group_id)
            SELECT
                bt.id,
                bt.name,
                CASE
                    WHEN bt.std_id = 56 THEN 1
                    WHEN bt.std_id = 4  THEN 2
                    WHEN bt.std_id = 2  THEN 3
                    WHEN bt.std_id = 15 THEN 4
                    ELSE 5
                END
            FROM raw.body_types bt
            WHERE run_id = %s
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                body_group_id = EXCLUDED.body_group_id
            """,
            (run_id,),
        )
        bt_count = cur.rowcount

    return {"details": {"cities": city_count, "body_types": bt_count}}


DQ_RULES = (
    ("price_non_positive", "price <= 0",
     "(e.price IS NULL OR e.price <= 0)"),
    ("price_too_low_rub", "RUB price <= 1000",
     "(e.currency_code = '643' AND e.price > 0 AND e.price <= 1000)"),
    ("distance_invalid", "distance <= 0",
     "(e.distance <= 0)"),
    ("weight_negative", "total_weight < 0",
     "(e.total_weight < 0)"),
    ("volume_negative", "total_volume < 0",
     "(e.total_volume < 0)"),
    ("city_unknown", "loading or unloading city not in cities",
     "(NOT e.loading_ok OR NOT e.unloading_ok)"),
    ("rate_missing", "no rate on nearest_rate_date",
     "(e.currency_code <> '643' AND NOT e.rate_ok)"),
    ("body_type_unknown", "prices.body_type not in core.body_type",
     "e.body_type_unknown"),
    ("body_type_mismatch", "price_body_types non-empty but does not contain main body group",
     "e.body_type_mismatch"),
)


def _load_core_price(conn, run_id, price_filter_sql, price_filter_params):
    with conn.cursor() as cur:
        cur.execute(
            f"""
            CREATE TEMP TABLE enriched_dq ON COMMIT DROP AS
            WITH p AS (
                SELECT * FROM raw.prices
                WHERE run_id = %s AND {price_filter_sql}
            ),
            cities AS (
                SELECT DISTINCT ON (gc_id) gc_id
                FROM raw.cities WHERE run_id = %s
                ORDER BY gc_id, id
            ),
            rates AS (
                SELECT DISTINCT ON (num_code, setting_date) num_code, setting_date, value
                FROM raw.exchange_rates WHERE run_id = %s
                ORDER BY num_code, setting_date, id
            ),
            pbt_agg AS (
                SELECT
                    pbt.price_id,
                    array_agg(cbt.body_group_id)
                        FILTER (WHERE cbt.body_group_id IS NOT NULL) AS groups
                FROM raw.price_body_types pbt
                LEFT JOIN core.body_type cbt ON cbt.id = pbt.body_type_id
                WHERE pbt.run_id = %s
                GROUP BY pbt.price_id
            )
            SELECT
                p.id AS price_id,
                p.loading_date,
                p.loading_city_gcid,
                p.unloading_city_gcid,
                p.distance,
                p.total_weight,
                p.total_volume,
                p.price,
                p.currency_code,
                p.price_type,
                p.organization_id,
                p.outlier_mark,
                p.is_fact,
                p.complex,
                p.weight_category AS raw_weight_cat,
                p.volume_category AS raw_volume_cat,
                mbt.id AS main_body_type_id,
                (p.body_type IS NOT NULL AND mbt.id IS NULL) AS body_type_unknown,
                (c1.gc_id IS NOT NULL) AS loading_ok,
                (c2.gc_id IS NOT NULL) AS unloading_ok,
                r.value AS rate_value,
                (p.currency_code = '643' OR r.value IS NOT NULL) AS rate_ok,
                CASE
                    WHEN p.currency_code = '643' THEN p.price
                    WHEN r.value IS NOT NULL THEN p.price * r.value
                    ELSE NULL
                END AS price_rub,
                (COALESCE(pa.groups, '{{}}'::smallint[]) <> '{{}}'::smallint[]
                 AND NOT COALESCE(mbt.body_group_id = ANY(pa.groups), false))
                    AS body_type_mismatch
            FROM p
            LEFT JOIN core.body_type mbt ON mbt.id = p.body_type
            LEFT JOIN cities c1 ON c1.gc_id = p.loading_city_gcid
            LEFT JOIN cities c2 ON c2.gc_id = p.unloading_city_gcid
            LEFT JOIN rates r
                ON r.num_code = p.currency_code
               AND r.setting_date = p.nearest_rate_date
            LEFT JOIN pbt_agg pa ON pa.price_id = p.id
            """,
            (run_id, *price_filter_params, run_id, run_id, run_id),
        )

        quarantined = 0
        for code, detail, cond in DQ_RULES:
            cur.execute(
                f"""
                INSERT INTO dq.quarantine_prices
                    (run_id, price_id, reason_code, reason_detail, payload)
                SELECT %s, e.price_id, %s, %s, to_jsonb(e)
                FROM enriched_dq e
                WHERE {cond}
                ON CONFLICT DO NOTHING
                """,
                (run_id, code, detail),
            )
            quarantined += cur.rowcount

        cur.execute(
            """
            INSERT INTO core.price (
                price_id, loading_date, loading_city_gcid, unloading_city_gcid,
                distance, total_weight, total_volume,
                main_body_type_id,
                weight_category, volume_category,
                price, currency_code, price_rub,
                price_type, organization_id, outlier_mark
            )
            SELECT
                price_id, loading_date, loading_city_gcid, unloading_city_gcid,
                distance, total_weight, total_volume,
                main_body_type_id,
                COALESCE(raw_weight_cat, CASE
                    WHEN round(total_weight::numeric, 1) >= 30 THEN 'G20T'
                    WHEN round(total_weight::numeric, 1) >= 10 THEN 'FTL'
                    WHEN round(total_weight::numeric, 1) >= 5 THEN '10T'
                    WHEN round(total_weight::numeric, 1) >= 2.5 THEN '5T'
                    WHEN round(total_weight::numeric, 1) >= 0.5 THEN 'L5T'
                    ELSE 'OTH'
                END),
                COALESCE(raw_volume_cat, CASE
                    WHEN total_volume > 0 AND total_volume <= 120 THEN 'FTL'
                    ELSE 'OTH'
                END),
                price, currency_code, price_rub,
                price_type, organization_id, outlier_mark
            FROM enriched_dq
            WHERE is_fact = true
              AND complex = false
              AND price > 0
              AND distance > 0
              AND total_weight >= 0
              AND total_volume >= 0
              AND loading_ok IS NOT NULL
              AND unloading_ok IS NOT NULL
              AND (currency_code = '643' OR rate_value IS NOT NULL)
              AND NOT (currency_code = '643' AND price <= 1000)
              AND price_rub IS NOT NULL
              AND NOT body_type_unknown
              AND NOT body_type_mismatch
            ON CONFLICT (price_id) DO UPDATE SET
                loading_date = EXCLUDED.loading_date,
                loading_city_gcid = EXCLUDED.loading_city_gcid,
                unloading_city_gcid = EXCLUDED.unloading_city_gcid,
                distance = EXCLUDED.distance,
                total_weight = EXCLUDED.total_weight,
                total_volume = EXCLUDED.total_volume,
                main_body_type_id = EXCLUDED.main_body_type_id,
                weight_category = EXCLUDED.weight_category,
                volume_category = EXCLUDED.volume_category,
                price = EXCLUDED.price,
                currency_code = EXCLUDED.currency_code,
                price_rub = EXCLUDED.price_rub,
                price_type = EXCLUDED.price_type,
                organization_id = EXCLUDED.organization_id,
                outlier_mark = EXCLUDED.outlier_mark
            """,
        )
        loaded = cur.rowcount

        cur.execute(
            """
            DELETE FROM core.price_body_group
            WHERE price_id IN (SELECT price_id FROM enriched_dq)
            """
        )
        cur.execute(
            """
            INSERT INTO core.price_body_group (price_id, body_group_id)
            SELECT DISTINCT pbt.price_id, cbt.body_group_id
            FROM raw.price_body_types pbt
            JOIN core.body_type cbt ON cbt.id = pbt.body_type_id
            JOIN core.price cp ON cp.price_id = pbt.price_id
            WHERE pbt.run_id = %s
              AND pbt.price_id IN (SELECT price_id FROM enriched_dq)

            UNION

            SELECT cp.price_id, cbt.body_group_id
            FROM core.price cp
            JOIN core.body_type cbt ON cbt.id = cp.main_body_type_id
            WHERE cp.main_body_type_id IS NOT NULL
              AND cp.price_id IN (SELECT price_id FROM enriched_dq)
              AND NOT EXISTS (
                  SELECT 1 FROM raw.price_body_types pbt
                  WHERE pbt.price_id = cp.price_id AND pbt.run_id = %s
              )
            ON CONFLICT DO NOTHING
            """,
            (run_id, run_id),
        )

        cur.execute(
            """
            DELETE FROM core.price_dates
            WHERE price_id IN (SELECT price_id FROM enriched_dq)
            """
        )
        cur.execute(
            """
            INSERT INTO core.price_dates (price_id, price_date)
            SELECT pd.price_id, pd.price_date
            FROM raw.price_dates pd
            JOIN core.price cp ON cp.price_id = pd.price_id
            WHERE pd.run_id = %s
              AND pd.price_id IN (SELECT price_id FROM enriched_dq)
            ON CONFLICT DO NOTHING
            """,
            (run_id,),
        )

    return {
        "rows_out": loaded,
        "rows_quarantined": quarantined,
    }


def load_core_price(conn, run_id, interval_start, interval_end):
    return _load_core_price(
        conn, run_id,
        price_filter_sql="loading_date >= %s AND loading_date < %s",
        price_filter_params=(interval_start, interval_end),
    )


def load_core_price_changes(conn, run_id):
    return _load_core_price(
        conn, run_id,
        price_filter_sql="true",
        price_filter_params=(),
    )