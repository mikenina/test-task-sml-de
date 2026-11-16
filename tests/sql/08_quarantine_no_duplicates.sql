DO $$
DECLARE
  v_count bigint;
BEGIN
  SELECT count(*) INTO v_count
  FROM (
    SELECT run_id, price_id, reason_code
    FROM dq.quarantine_prices
    GROUP BY 1,2,3 HAVING count(*) > 1
  ) d;
  IF v_count > 0 THEN
    RAISE EXCEPTION 'dq.quarantine_prices has % duplicates by (run_id, price_id, reason_code)', v_count;
  END IF;
END $$;