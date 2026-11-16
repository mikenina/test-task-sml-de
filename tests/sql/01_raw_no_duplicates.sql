DO $$
DECLARE
    v_count bigint;
BEGIN
    SELECT count(*) INTO v_count FROM (
        SELECT run_id, id FROM raw.prices GROUP BY 1,2 HAVING count(*) > 1
        UNION ALL
        SELECT run_id, id FROM raw.cities GROUP BY 1,2 HAVING count(*) > 1
        UNION ALL
        SELECT run_id, id FROM raw.body_types GROUP BY 1,2 HAVING count(*) > 1
        UNION ALL
        SELECT run_id, id FROM raw.price_body_types GROUP BY 1,2 HAVING count(*) > 1
        UNION ALL
        SELECT run_id, id FROM raw.price_dates GROUP BY 1,2 HAVING count(*) > 1
        UNION ALL
        SELECT run_id, id FROM raw.exchange_rates GROUP BY 1,2 HAVING count(*) > 1
    ) d;
    IF v_count > 0 THEN
        RAISE EXCEPTION 'raw.* has % duplicate rows by (run_id, id)', v_count;
    END IF;
END $$;