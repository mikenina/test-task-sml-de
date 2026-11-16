TRUNCATE dq._smoke_snapshot;
INSERT INTO dq._smoke_snapshot (
  core_price_cnt, core_bridge_cnt, core_dates_cnt,
  mart_cnt, ml_cnt
)
SELECT
  (SELECT count(*) FROM core.price),
  (SELECT count(*) FROM core.price_body_group),
  (SELECT count(*) FROM core.price_dates),
  (SELECT count(*) FROM mart.route_card),
  (SELECT count(*) FROM mart.ml_price_predictions);