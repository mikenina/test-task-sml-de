DO $$
DECLARE
  v_raw_gc bigint;
  v_raw_distinct_gc bigint;
  v_dup_raw bigint;
  v_core bigint;
  v_last_run bigint;
BEGIN
  SELECT max(id) INTO v_last_run
  FROM dq.etl_runs WHERE status = 'success';

  SELECT count(*), count(DISTINCT gc_id) INTO v_raw_gc, v_raw_distinct_gc
  FROM raw.cities WHERE run_id = v_last_run;

  IF v_raw_gc = v_raw_distinct_gc THEN
    RAISE EXCEPTION 'raw.cities has no duplicated gc_id; test expects duplicates (Москва, Казань)';
  END IF;

  SELECT count(*) INTO v_dup_raw
  FROM (
    SELECT gc_id FROM raw.cities
    WHERE run_id = v_last_run
    GROUP BY gc_id HAVING count(*) > 1
  ) d;
  IF v_dup_raw < 2 THEN
    RAISE EXCEPTION 'raw.cities has % duplicated gc_id, expected at least 2', v_dup_raw;
  END IF;

  SELECT count(*) INTO v_core FROM core.city;
  IF v_core <> v_raw_distinct_gc THEN
    RAISE EXCEPTION 'core.city has % rows, expected % (distinct gc_id in raw)', v_core, v_raw_distinct_gc;
  END IF;

  SELECT count(*) INTO v_core
  FROM (SELECT gc_id FROM core.city GROUP BY gc_id HAVING count(*) > 1) d;
  IF v_core > 0 THEN
    RAISE EXCEPTION 'core.city has % duplicated gc_id', v_core;
  END IF;
END $$;