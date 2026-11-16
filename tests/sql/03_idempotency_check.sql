DO $$
DECLARE
  v_before dq._smoke_snapshot%ROWTYPE;
  v_core_price bigint;
  v_core_bridge bigint;
  v_core_dates bigint;
  v_mart bigint;
  v_ml bigint;
  v_quarantine bigint;
BEGIN
  SELECT * INTO v_before FROM dq._smoke_snapshot LIMIT 1;
  IF v_before IS NULL THEN
    RAISE EXCEPTION 'no snapshot; run 03_idempotency_snapshot.sql first';
  END IF;

  SELECT count(*) INTO v_core_price FROM core.price;
  SELECT count(*) INTO v_core_bridge FROM core.price_body_group;
  SELECT count(*) INTO v_core_dates FROM core.price_dates;
  SELECT count(*) INTO v_mart FROM mart.route_card;
  SELECT count(*) INTO v_ml FROM mart.ml_price_predictions;

  IF v_before.core_price_cnt <> v_core_price THEN
    RAISE EXCEPTION 'core.price count changed: % -> %', v_before.core_price_cnt, v_core_price;
  END IF;
  IF v_before.core_bridge_cnt <> v_core_bridge THEN
    RAISE EXCEPTION 'core.price_body_group count changed: % -> %', v_before.core_bridge_cnt, v_core_bridge;
  END IF;
  IF v_before.core_dates_cnt <> v_core_dates THEN
    RAISE EXCEPTION 'core.price_dates count changed: % -> %', v_before.core_dates_cnt, v_core_dates;
  END IF;
  IF v_before.mart_cnt <> v_mart THEN
    RAISE EXCEPTION 'mart.route_card count changed: % -> %', v_before.mart_cnt, v_mart;
  END IF;
  IF v_before.ml_cnt <> v_ml THEN
    RAISE EXCEPTION 'mart.ml_price_predictions count changed: % -> %', v_before.ml_cnt, v_ml;
  END IF;
END $$;