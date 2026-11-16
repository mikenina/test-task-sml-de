DO $$
DECLARE
  v_count bigint;
BEGIN
  SELECT count(*) INTO v_count
  FROM core.price
  WHERE price_rub IS NULL
    OR distance <= 0
    OR total_weight < 0
    OR total_volume < 0
    OR price <= 0
    OR (currency_code = '643' AND price <= 1000);
  IF v_count > 0 THEN
    RAISE EXCEPTION 'core.price has % rows violating DQ invariants', v_count;
  END IF;

  SELECT count(*) INTO v_count
  FROM core.price p
  WHERE NOT EXISTS (
    SELECT 1 FROM core.price_dates pd WHERE pd.price_id = p.price_id
  );
  IF v_count > 0 THEN
    RAISE EXCEPTION 'core.price has % rows without price_dates', v_count;
  END IF;
END $$;