DO $$
DECLARE
  v_as_of date := COALESCE(current_setting('my_as_of', true)::date, '2026-10-26'::date);
  v_count bigint;
BEGIN
  SELECT count(*) INTO v_count
  FROM mart.route_card
  WHERE month > date_trunc('month', v_as_of)::date;
  IF v_count > 0 THEN
    RAISE EXCEPTION 'mart.route_card has % rows with month > as_of month', v_count;
  END IF;
END $$;