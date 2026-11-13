def rebuild_mart_route_card(conn, as_of):
    with conn.cursor() as cur:
        cur.execute("TRUNCATE mart.route_card")

        cur.execute(
            """
            WITH base AS (
                SELECT
                    date_trunc('month', pd.price_date)::date AS month,
                    p.price_id,
                    p.loading_city_gcid,
                    p.unloading_city_gcid,
                    COALESCE(pbg.body_group_id, 0) AS body_group_id,
                    p.weight_category,
                    p.price_rub,
                    p.distance,
                    p.organization_id,
                    p.price_type
                FROM core.price p
                JOIN core.price_dates pd ON pd.price_id = p.price_id
                LEFT JOIN core.price_body_group pbg ON pbg.price_id = p.price_id
                WHERE p.outlier_mark = false
                  AND p.price_rub > 0
            ),
            agg AS (
                SELECT
                    month,
                    loading_city_gcid,
                    unloading_city_gcid,
                    body_group_id,
                    weight_category,
                    COUNT(DISTINCT price_id) AS trips_count,
                    COUNT(DISTINCT organization_id)
                        FILTER (WHERE price_type IN (3, 9)) AS carriers_count,
                    PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY price_rub) AS p25_trip,
                    PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY price_rub) AS median_trip,
                    PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY price_rub) AS p75_trip,
                    AVG(price_rub) AS avg_trip,
                    PERCENTILE_CONT(0.25) WITHIN GROUP (
                        ORDER BY price_rub / NULLIF(distance, 0)
                    ) AS p25_km,
                    PERCENTILE_CONT(0.50) WITHIN GROUP (
                        ORDER BY price_rub / NULLIF(distance, 0)
                    ) AS median_km,
                    PERCENTILE_CONT(0.75) WITHIN GROUP (
                        ORDER BY price_rub / NULLIF(distance, 0)
                    ) AS p75_km,
                    STDDEV_SAMP(price_rub) / NULLIF(AVG(price_rub), 0) AS cv_rate
                FROM base
                GROUP BY
                    month, loading_city_gcid, unloading_city_gcid,
                    body_group_id, weight_category
            ),
            with_deltas AS (
                SELECT
                    a.*,
                    CASE
                        WHEN prev.median_trip > 0
                        THEN (a.median_trip / prev.median_trip - 1) * 100
                        ELSE NULL
                    END AS mom_pct,
                    CASE
                        WHEN prev_y.median_trip > 0
                        THEN (a.median_trip / prev_y.median_trip - 1) * 100
                        ELSE NULL
                    END AS yoy_pct
                FROM agg a
                LEFT JOIN agg prev
                    ON prev.month = (a.month - INTERVAL '1 month')::date
                   AND prev.loading_city_gcid = a.loading_city_gcid
                   AND prev.unloading_city_gcid = a.unloading_city_gcid
                   AND prev.body_group_id = a.body_group_id
                   AND prev.weight_category = a.weight_category
                LEFT JOIN agg prev_y
                    ON prev_y.month = (a.month - INTERVAL '1 year')::date
                   AND prev_y.loading_city_gcid = a.loading_city_gcid
                   AND prev_y.unloading_city_gcid = a.unloading_city_gcid
                   AND prev_y.body_group_id = a.body_group_id
                   AND prev_y.weight_category = a.weight_category
            )
            INSERT INTO mart.route_card (
                month, loading_city_gcid, unloading_city_gcid,
                body_group_id, weight_category,
                trips_count, carriers_count,
                p25_trip, median_trip, p75_trip, avg_trip,
                p25_km, median_km, p75_km,
                cv_rate, mom_pct, yoy_pct, reliability_level
            )
            SELECT
                month, loading_city_gcid, unloading_city_gcid,
                body_group_id, weight_category,
                trips_count, carriers_count,
                p25_trip::numeric(14,2),
                median_trip::numeric(14,2),
                p75_trip::numeric(14,2),
                avg_trip::numeric(14,2),
                p25_km::numeric(10,2),
                median_km::numeric(10,2),
                p75_km::numeric(10,2),
                cv_rate::numeric(10,4),
                mom_pct::numeric(10,2),
                yoy_pct::numeric(10,2),
                CASE
                    WHEN trips_count >= 30
                         AND carriers_count >= 5
                         AND (%s::date - (month + INTERVAL '1 month - 1 day')::date) <= 30
                    THEN 'HIGH'
                    WHEN trips_count >= 10
                    THEN 'MEDIUM'
                    ELSE 'LOW_DATA'
                END
            FROM with_deltas
            """,
            (as_of,),
        )
        rows = cur.rowcount
    return {"rows_out": rows}