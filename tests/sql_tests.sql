deals_bigdata=# select count(*) from core.city;
 count
-------
    40
(1 row)

deals_bigdata=# select count(*) from raw.cities;
 count
-------
    42
(1 row)

select bg.name body_group_name, array_agg(bt.name::text order by bt.name asc) body_types from core.body_type bt inner join core.body_group bg on bg.id = bt.body_group_id group by bg.name order by bg.name;
 body_group_name |                                               body_types
-----------------+--------------------------------------------------------------------------------------------------------
 Борт            | {борт,бортовая}
 Изотерм         | {изотермический}
 Прочие          | {контейнер,"контейнерная площадка",самосвал,трал,фургон,цистерна}
 Рефрижератор    | {рефрижератор,"рефрижератор мультирежимный","рефрижератор с перегородкой",рефрижератор-тушевоз}
 Тент            | {"тент бок","тент верх","тент зад и бок","тент задняя загрузка",тентованный,"тент полная растентовка"}
(5 rows)

-- нет ячеек с NULL в обязательных полях
SELECT count(*) FROM mart.route_card
WHERE p25_trip IS NULL OR median_trip IS NULL OR p75_trip IS NULL
   OR p25_km IS NULL OR median_km IS NULL OR p75_km IS NULL
   OR reliability_level IS NULL;
-- 0

-- HIGH только для свежих месяцев
SELECT DISTINCT month FROM mart.route_card
WHERE reliability_level = 'HIGH' ORDER BY month DESC;
-- только 2026-09-01 и 2026-10-01 (при as_of = 2026-10-26)

-- нет моM/yoy для первого месяца
SELECT count(*) FROM mart.route_card WHERE mom_pct IS NOT NULL AND month = '2023-09-01';
-- 0 (если это самый ранний месяц)