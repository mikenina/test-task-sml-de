# Платформа аналитики и прогнозирования тарифов грузоперевозок (Smart Logistics Data & ML Platform)
_Тестовое задание: Middle Data Engineer_

## 1. Запуск
```bash
cp .env.example .env
docker compose up --build -d
```
### Проверка результата
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

## 2. Запуск ETL
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