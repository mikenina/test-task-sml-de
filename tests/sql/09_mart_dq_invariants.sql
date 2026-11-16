DO $$
DECLARE
  v_count bigint;
BEGIN
  -- 1. Все обязательные метрики не NULL
  SELECT count(*) INTO v_count
  FROM mart.route_card
  WHERE p25_trip IS NULL
     OR median_trip IS NULL
     OR p75_trip IS NULL
     OR avg_trip IS NULL
     OR p25_km IS NULL
     OR median_km IS NULL
     OR p75_km IS NULL
     OR reliability_level IS NULL;
  IF v_count > 0 THEN
    RAISE EXCEPTION 'mart.route_card has % rows with NULL in required metrics', v_count;
  END IF;

  -- 2. Перцентили неотрицательны и упорядочены
  SELECT count(*) INTO v_count
  FROM mart.route_card
  WHERE p25_trip <= 0
     OR median_trip <= 0
     OR p75_trip <= 0
     OR avg_trip <= 0
     OR p25_km <= 0
     OR median_km <= 0
     OR p75_km <= 0
     OR p25_trip > median_trip
     OR median_trip > p75_trip
     OR p25_km > median_km
     OR median_km > p75_km;
  IF v_count > 0 THEN
    RAISE EXCEPTION 'mart.route_card has % rows with invalid percentile values', v_count;
  END IF;

  -- 3. Гранулярность: trips_count и carriers_count
  SELECT count(*) INTO v_count
  FROM mart.route_card
  WHERE trips_count < 1
     OR carriers_count < 0
     OR carriers_count > trips_count;
  IF v_count > 0 THEN
    RAISE EXCEPTION 'mart.route_card has % rows with invalid trips_count/carriers_count', v_count;
  END IF;

  -- 4. reliability_level из допустимого множества (плюс CHECK, но тест ловит регрессию)
  SELECT count(*) INTO v_count
  FROM mart.route_card
  WHERE reliability_level NOT IN ('HIGH', 'MEDIUM', 'LOW_DATA');
  IF v_count > 0 THEN
    RAISE EXCEPTION 'mart.route_card has % rows with unknown reliability_level', v_count;
  END IF;

  -- 5. reliability_level согласован с trips_count
  SELECT count(*) INTO v_count
  FROM mart.route_card
  WHERE (reliability_level = 'LOW_DATA' AND trips_count >= 10)
     OR (reliability_level = 'MEDIUM'  AND trips_count < 10);
  IF v_count > 0 THEN
    RAISE EXCEPTION 'mart.route_card has % rows with reliability_level inconsistent with trips_count', v_count;
  END IF;

  -- 6. body_group_id из допустимого множества (0 = «Не указан», 1..5 = core.body_group.id)
  SELECT count(*) INTO v_count
  FROM mart.route_card
  WHERE body_group_id NOT BETWEEN 0 AND 5;
  IF v_count > 0 THEN
    RAISE EXCEPTION 'mart.route_card has % rows with unknown body_group_id', v_count;
  END IF;

  -- 7. weight_category из допустимого множества
  SELECT count(*) INTO v_count
  FROM mart.route_card
  WHERE weight_category NOT IN ('G20T', 'FTL', '10T', '5T', 'L5T', 'OTH');
  IF v_count > 0 THEN
    RAISE EXCEPTION 'mart.route_card has % rows with unknown weight_category', v_count;
  END IF;

  -- 8. cv_rate: NULL или >= 0
  SELECT count(*) INTO v_count
  FROM mart.route_card
  WHERE cv_rate IS NOT NULL AND cv_rate < 0;
  IF v_count > 0 THEN
    RAISE EXCEPTION 'mart.route_card has % rows with negative cv_rate', v_count;
  END IF;
END $$;