# Платформа аналитики и прогнозирования тарифов грузоперевозок (Smart Logistics Data & ML Platform)
_Тестовое задание: Middle Data Engineer._

_Дата выполнения:_ ноябрь 2026г.

## 1. Описание репозитория

| Путь | Описание |
|-----|-------------|
| [./docker/postgres/init/01_schema.sql](./docker/postgres/init/01_schema.sql) | ddl source-бд |
| [./docker/postgres/init/02_synthetic.sql](./docker/postgres/init/02_synthetic.sql) | скрипт заполнения source-бд синтетическими данными |
| [./docker/postgres/init/03_dwh_init.sql](./docker/postgres/init/03_dwh_init.sql) | ddl DWH |
| [.env.example](.env.example) | Переменные окружения (коннект к базе и др.) |
| [./schemas/](docs/schemas/)| ER-diagrams |
| [./etl/loader_raw.py](./etl/loader_raw.py) | Реализация этапа source -> raw |
| [./etl/loader_core.py](./etl/loader_core.py) | Реализация этапа raw -> core |
| [./etl/main.py](./etl/main.py) | ETL flow |

## 2. Запуск контейнеров
```bash
cp .env.example .env
docker compose up --build -d
```
### Проверка результата

```bash
docker ps
... STATUS  NAMES
    Up      logistics-app
    Up      logistics-postgres
```

После успешного запуска контейнеров поднимается бд postgres, содержащая по одной схеме на слой.

Схема `public` содержит источник, заполненный синтетическими данными.

Остальные схемы содержат структуру слоев DWH.

```bash
docker compose exec postgres psql -U postgres -d deals_bigdata -c "\dn"
      List of schemas
  Name  | ... 
--------+---
 core   | 
 dq     | 
 mart   | 
 public | 
 raw    | 
(5 rows)
```

## 3. Запуск ETL
```bash
docker compose exec app python -m etl.main \
    --interval-start 2023-01-01 \
    --interval-end 2027-03-01
```

### Проверка результата
```bash
docker compose exec postgres psql -U postgres -d deals_bigdata -c \
    "SELECT id, status, rows_out FROM dq.etl_run_stages ORDER BY id;"
```

### Проверка витрины
```bash
docker compose exec -T postgres psql -U postgres -d deals_bigdata <<'SQL'
SELECT
    c1.name AS from_city,
    c2.name AS to_city,
    COALESCE(bg.name, 'Не указан') AS body_group,
    rc.weight_category,
    rc.month,
    rc.trips_count,
    rc.carriers_count,
    rc.median_trip,
    rc.median_km,
    rc.mom_pct,
    rc.reliability_level
FROM mart.route_card rc
JOIN core.city c1 ON c1.gc_id = rc.loading_city_gcid
JOIN core.city c2 ON c2.gc_id = rc.unloading_city_gcid
LEFT JOIN core.body_group bg ON bg.id = rc.body_group_id
WHERE rc.loading_city_gcid = 1001
  AND rc.unloading_city_gcid = 1003
ORDER BY rc.month DESC
LIMIT 10;
SQL
```

## 4. [Архитектура решения (./docs/architecture.md)](./docs/architecture.md)