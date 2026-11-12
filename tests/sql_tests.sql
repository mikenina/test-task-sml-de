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

