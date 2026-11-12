def load_source_to_raw(conn, run_id, interval_start, interval_end):
    with conn.cursor() as cur:
        cur.execute(
            """
            DO $$
            DECLARE
                v_run_id bigint := %s;
                v_start date := %s;
                v_end date := %s;
            BEGIN
                INSERT INTO raw.cities
                SELECT c.*, v_run_id, now() FROM public.cities c;

                INSERT INTO raw.body_types
                SELECT bt.*, v_run_id, now() FROM public.body_types bt;

                INSERT INTO raw.exchange_rates
                SELECT er.*, v_run_id, now() FROM public.exchange_rates er;

                INSERT INTO raw.prices
                SELECT p.*, v_run_id, now()
                FROM public.prices p
                WHERE p.loading_date >= v_start AND p.loading_date < v_end;

                INSERT INTO raw.price_dates
                SELECT pd.*, v_run_id, now()
                FROM public.price_dates pd
                JOIN raw.prices rp
                    ON rp.run_id = v_run_id AND rp.id = pd.price_id;

                INSERT INTO raw.price_body_types
                SELECT pbt.*, v_run_id, now()
                FROM public.price_body_types pbt
                JOIN raw.prices rp
                    ON rp.run_id = v_run_id AND rp.id = pbt.price_id;
            END
            $$;
            """,
            (run_id, interval_start, interval_end),
        )

        cur.execute(
            """
            SELECT
                (SELECT count(*) FROM raw.prices           WHERE run_id = %s),
                (SELECT count(*) FROM raw.cities           WHERE run_id = %s),
                (SELECT count(*) FROM raw.body_types       WHERE run_id = %s),
                (SELECT count(*) FROM raw.price_dates      WHERE run_id = %s),
                (SELECT count(*) FROM raw.price_body_types WHERE run_id = %s),
                (SELECT count(*) FROM raw.exchange_rates   WHERE run_id = %s)
            """,
            (run_id, run_id, run_id, run_id, run_id, run_id),
        )
        prices, cities, body_types, price_dates, price_body_types, exchange_rates = cur.fetchone()

    return {
        "rows_out": prices,
        "details": {
            "prices": prices,
            "cities": cities,
            "body_types": body_types,
            "price_dates": price_dates,
            "price_body_types": price_body_types,
            "exchange_rates": exchange_rates,
        },
    }