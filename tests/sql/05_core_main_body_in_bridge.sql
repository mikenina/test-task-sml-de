DO $$
DECLARE
  v_count bigint;
BEGIN
  SELECT count(*) INTO v_count
  FROM core.price p
  JOIN core.body_type bt ON bt.id = p.main_body_type_id
  LEFT JOIN core.price_body_group pbg
    ON pbg.price_id = p.price_id
   AND pbg.body_group_id = bt.body_group_id
  WHERE p.main_body_type_id IS NOT NULL
    AND pbg.price_id IS NULL;
  IF v_count > 0 THEN
    RAISE EXCEPTION 'core.price has % rows with main_body_type_id not in price_body_group', v_count;
  END IF;
END $$;