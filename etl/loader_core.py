def load_core_price(conn, run_id, interval_start, interval_end, as_of):
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM dq.quarantine_prices "
            "WHERE price_id IN (SELECT id FROM raw.prices WHERE run_id = %s)",
            (run_id,),
        )

        cur.execute(
            """
            WITH p AS (
                SELECT * FROM raw.prices WHERE run_id = %s
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
            enriched AS (
                SELECT
                    p.id AS price_id,
                    p.currency_code,
                    p.price,
                    p.distance,
                    p.total_weight,
                    p.total_volume,
                    p.nearest_rate_date,
                    (c1.gc_id IS NOT NULL) AS loading_ok,
                    (c2.gc_id IS NOT NULL) AS unloading_ok,
                    (p.currency_code = '643' OR r.value IS NOT NULL) AS rate_ok
                FROM p
                LEFT JOIN cities c1 ON c1.gc_id = p.loading_city_gcid
                LEFT JOIN cities c2 ON c2.gc_id = p.unloading_city_gcid
                LEFT JOIN rates r
                    ON r.num_code = p.currency_code
                   AND r.setting_date = p.nearest_rate_date
            )
            INSERT INTO dq.quarantine_prices (price_id, reason_code, reason_detail, payload)
            SELECT e.price_id, r.code, r.detail, to_jsonb(e)
            FROM enriched e
            CROSS JOIN LATERAL (VALUES
                ('price_non_positive', 'price <= 0',
                    (e.price IS NULL OR e.price <= 0)),
                ('price_too_low_rub', 'RUB price <= 1000',
                    (e.currency_code = '643' AND e.price > 0 AND e.price <= 1000)),
                ('distance_invalid', 'distance <= 0',
                    (e.distance <= 0)),
                ('weight_negative', 'total_weight < 0',
                    (e.total_weight < 0)),
                ('volume_negative', 'total_volume < 0',
                    (e.total_volume < 0)),
                ('city_unknown', 'loading or unloading city not in cities',
                    (NOT e.loading_ok OR NOT e.unloading_ok)),
                ('rate_missing', 'no rate on nearest_rate_date',
                    (e.currency_code <> '643' AND NOT e.rate_ok))
            ) AS r(code, detail, is_bad)
            WHERE r.is_bad
            ON CONFLICT DO NOTHING
            """,
            (run_id, run_id, run_id),
        )
        quarantined = cur.rowcount

        cur.execute(
            """
            WITH p AS (
                SELECT * FROM raw.prices WHERE run_id = %s
            ),
            cities AS (
                SELECT DISTINCT ON (gc_id) gc_id
                FROM raw.cities WHERE run_id = %s
                ORDER BY gc_id, id
            ),
            bt AS (
                SELECT id, std_id FROM raw.body_types WHERE run_id = %s
            ),
            rates AS (
                SELECT DISTINCT ON (num_code, setting_date) num_code, setting_date, value
                FROM raw.exchange_rates WHERE run_id = %s
                ORDER BY num_code, setting_date, id
            ),
            primary_body AS (
                SELECT DISTINCT ON (pbt.price_id) pbt.price_id, bt.std_id
                FROM raw.price_body_types pbt
                LEFT JOIN bt ON bt.id = pbt.body_type_id
                WHERE pbt.run_id = %s
                ORDER BY pbt.price_id, pbt.id
            ),
            enriched AS (
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
                    p.body_type,
                    p.weight_category AS raw_weight_cat,
                    p.volume_category AS raw_volume_cat,
                    c1.gc_id AS loading_ok,
                    c2.gc_id AS unloading_ok,
                    r.value AS rate_value,
                    CASE
                        WHEN p.currency_code = '643' THEN p.price
                        WHEN r.value IS NOT NULL THEN p.price * r.value
                        ELSE NULL
                    END AS price_rub,
                    CASE
                        WHEN pb.std_id = 56 THEN 'Тент'
                        WHEN pb.std_id = 4 THEN 'Рефрижератор'
                        WHEN pb.std_id = 2 THEN 'Изотерм'
                        WHEN pb.std_id = 15 THEN 'Борт'
                        WHEN pb.std_id IS NOT NULL THEN 'Прочие'
                        WHEN p.body_type IS NOT NULL THEN (
                            SELECT CASE
                                WHEN bt2.id IN (56,57,58,59,60,61) THEN 'Тент'
                                WHEN bt2.id IN (4,46,47,48) THEN 'Рефрижератор'
                                WHEN bt2.id = 2 THEN 'Изотерм'
                                WHEN bt2.id IN (1,15) THEN 'Борт'
                                ELSE 'Прочие'
                            END
                            FROM bt bt2 WHERE bt2.id = p.body_type
                        )
                        ELSE 'Не указан'
                    END AS body_group
                FROM p
                LEFT JOIN cities c1 ON c1.gc_id = p.loading_city_gcid
                LEFT JOIN cities c2 ON c2.gc_id = p.unloading_city_gcid
                LEFT JOIN rates r
                    ON r.num_code = p.currency_code
                   AND r.setting_date = p.nearest_rate_date
                LEFT JOIN primary_body pb ON pb.price_id = p.id
            )
            INSERT INTO core.price (
                price_id, loading_date,
                loading_city_gcid, unloading_city_gcid,
                distance, total_weight, total_volume,
                body_group, weight_category, volume_category,
                price, currency_code, price_rub,
                price_type, organization_id, outlier_mark
            )
            SELECT
                price_id, loading_date,
                loading_city_gcid, unloading_city_gcid,
                distance, total_weight, total_volume,
                body_group,
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
            FROM enriched
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
            """,
            (run_id, run_id, run_id, run_id, run_id),
        )
        loaded = cur.rowcount

        cur.execute(
            """
            INSERT INTO core.price_body_group (price_id, body_group)
            SELECT DISTINCT
                pbt.price_id,
                CASE
                    WHEN bt.std_id = 56 THEN 'Тент'
                    WHEN bt.std_id = 4 THEN 'Рефрижератор'
                    WHEN bt.std_id = 2 THEN 'Изотерм'
                    WHEN bt.std_id = 15 THEN 'Борт'
                    WHEN bt.std_id IS NOT NULL THEN 'Прочие'
                    ELSE 'Не указан'
                END
            FROM raw.price_body_types pbt
            LEFT JOIN raw.body_types bt
                ON bt.id = pbt.body_type_id AND bt.run_id = pbt.run_id
            JOIN core.price cp ON cp.price_id = pbt.price_id
            WHERE pbt.run_id = %s
            ON CONFLICT DO NOTHING
            """,
            (run_id,),
        )

        cur.execute(
            """
            INSERT INTO core.price_dates (price_id, price_date)
            SELECT pd.price_id, pd.price_date
            FROM raw.price_dates pd
            JOIN core.price cp ON cp.price_id = pd.price_id
            WHERE pd.run_id = %s AND pd.price_date <= %s
            ON CONFLICT DO NOTHING
            """,
            (run_id, as_of),
        )

    return {
        "rows_out": loaded,
        "rows_quarantined": quarantined,
    }