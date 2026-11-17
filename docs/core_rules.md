### Правила очистки при переносе в core-слой:

| Нарушение | Код причины в dq.quarantine_prices | Комментарий |
|-----|-------------|------------|
| price <= 0 | `price_non_positive` | |
| для RUB price <= 1000 | `price_too_low_rub` | |
| distance <= 0 | `distance_invalid` | |
| total_weight < 0 | `weight_negative` | |
| total_volume < 0 | `volume_negative` | |
| отсутствие города погрузки/отгрузки в справочнике `raw.cities` | `city_unknown` | |
| Нет точного курса валют на `nearest_rate_date` | `rate_missing` | |
| поле `gc_id` в источнике городов не уникально | | оставляем гео с наименьшим id |
| `raw.prices.body_type` нет в справочнике | `body_type_unknown` | |
| неконсистентный основной кузов (`raw.prices.body_type`)* | `body_type_mismatch` | см ниже |
| !(is_fact = true AND complex = false) | | не включаем в core-слой; не попадают в dq.quarantine_prices  |
Если у одной сделки есть несколько аномалий, то в `dq.quarantine_prices` будет добавлено m строк по количеству причин.

```
В расчёт исторических рыночных показателей включаются только **фактические завершённые прямые перевозки** (`is_fact = true`, то есть `price_type IN (1, 2, 3, 4, 5, 9)`, `complex = false`) с корректными физическими параметрами (`price > 0`, `distance > 0`). Ставки торгов (`price_type = 6`, `is_fact = false`) в обязательный scope не входят.
``` 
 
### Правила унификации групп кузова
```
... У одной сделки может быть указано несколько дочерних типов кузова из 1С (или body_type IS NULL). 
... Для одной цены и одной стандартной группы кузова должна остаться только одна строка; отсутствие связи с `price_body_types` означает fallback на `prices.body_type`, а затем `Не указан`.
... Стандартизированная группа/тип кузова (body_group / body_type — рефрижераторные и специализированные кузова тарифицируются существенно выше тента и борта)
```
**Правила приведения типа кузова к стандартной группе**
- Тент (id IN (56, 57, 58, 59, 60, 61) → std_id = 56);
- Рефрижератор (id IN (4, 46, 47, 48) → std_id = 4);
- Изотерм (id = 2 → std_id = 2);
- Борт (id IN (1, 15) → std_id = 15);
- Прочие (остальные коды) 
- Не указан (NULL)

***Правила проверки консистентности типа кузова**

Реализована сверка данных источника: если выбран основной тип кузова (`raw.prices.body_type`), то он обязан присутствовать в `raw.price_body_types` (на уровне стандартной группы). |

| `raw.prices.body_type` | `raw.price_body_types` | Результат | Комментарий |
|-----|-------------|------------|------------|
| NULL | непустой | not valid | cделка уезжает в `dq.quarantine_prices` |
| NULL | пустой | valid | |
| NOT NULL | пустой | valid | fallback на `raw.prices.body_type` |
| NOT NULL | непустой + стандартные группы пересекаются | valid |
| NOT NULL | непустой + стандартные группы НЕ пересекаются | not valid | cделка уезжает в `dq.quarantine_prices` |

### Правила унификации веса и объема:

`weight_category`

| `raw.prices.weight_category` | `core.price.weight_category` |
|-----|-------------|
| >= 30 | G20T | 
| [10;30) | FTL |
| [5;10) | 10T |
| [2,5;5) | 5T |
| [0,5;2,5) | L5T |
| < 0,5 | OTH |

`volume_category`

| `raw.prices.volume_category` | `core.price.volume_category` |
|-----|-------------|
| (0;120) | FTL |
| иначе | OTH |
