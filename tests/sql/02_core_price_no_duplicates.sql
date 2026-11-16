DO $$
DECLARE
  v_count bigint;
BEGIN
  SELECT count(*) INTO v_count
  FROM (SELECT price_id FROM core.price GROUP BY 1 HAVING count(*) > 1) d;
  IF v_count > 0 THEN
    RAISE EXCEPTION 'core.price has % duplicate price_id', v_count;
  END IF;
END $$;