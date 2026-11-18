# Adrobot — доменная модель

Дополняет [requirements.md](requirements.md). Подход — DDD: чистый домен без зависимостей от БД и HTTP, инварианты внутри агрегатов.

## 1. Контекст и границы

- Один ограниченный контекст — «управление офферами в кампаниях Keitaro».
- Keitaro — внешняя система. Между ней и доменом стоит **Anti-Corruption Layer** (`KeitaroGateway` в `infrastructure`): переводит JSON Keitaro в объекты домена и обратно. Домен не знает про HTTP, `share`, `type: forced` и т. п.
- Идентичность сущностей — их ID в Keitaro. Поток и кампания всегда сначала существуют в Keitaro, а потом попадают к нам, поэтому суррогатные ключи не нужны.

## 2. Агрегаты

Один агрегат — **Campaign** (кампания), корень `Campaign`:

```
Campaign (корень)
└── Stream (сущность)            — потоки кампании, по position
    └── OfferAssignment (сущность) — привязки офферов
```

| Уровень | Инварианты |
|---|---|
| Campaign | Fetch при черновиках требует явного подтверждения (`discard_drafts`), иначе `CampaignHasDrafts`; потоки, исчезнувшие из Keitaro, уходят из агрегата |
| Stream | один оффер в потоке не больше одного раза; сумма весов участников = 100 (если есть незакреплённые); сумма закреплённых ≤ 100; редактировать можно только поток с офферами |

Снаружи агрегат меняется только через команды корня: `campaign.add_offer(stream_id, offer)`, `pin(...)`, `cancel(stream_id)`, `sync_from_keitaro(...)` и т. д. Корень находит поток и делегирует ему. `campaign.stream(id)` отдаёт поток только для чтения — Python не умеет `internal`, поэтому это соглашение.

Почему корень — кампания: Fetch синхронизирует кампанию целиком — это одна операция над одним агрегатом, и правило «сначала подтвердить отмену черновиков» живёт в корне, а не в сценарии приложения. Цена — одна версия на всю кампанию: правки разных потоков одной кампании конкурируют за версию (для этого приложения приемлемо).

**Оффер** — не агрегат, а внешний справочник (им владеет Keitaro). Агрегат держит снимок `OfferRef(id, name)`; таблица `offers` — кеш для поиска.

## 3. Желаемое и опубликованное состояние

У каждой привязки два снимка:

```
desired:   DesiredState(included, share, pinned)     — что видит пользователь в обёртке
published: PublishedState(present, share, pinned)    — что лежит в Keitaro
           или None — привязка ни разу не публиковалась
```

Статус не хранится, а вычисляется:

| desired.included | published | Статус |
|---|---|---|
| ✔ | present | `active` |
| ✔ | None или не present | `pending_add` |
| ✘ | present | `pending_remove` |
| ✘ | не present | `removed` (архив) |

Комбинация «✘ + None» невозможна: неопубликованная привязка при удалении выбрасывается целиком.

| Операция | Реализация |
|---|---|
| Поток жёлтый | у какой-либо привязки `desired` расходится с `published` |
| Cancel | `desired := published`; привязки с `published = None` выбрасываются |
| Push (успех) | `published := desired`; исключённые → `present = false` (архив) |
| Список изменений для подтверждения | разница `desired` / `published` по привязкам |
| Fetch | `published :=` данные Keitaro; `desired` правится по FR-2.3; закреплённый вес не перетирается (Q7). Входные данные — снимки `KeitaroCampaign` / `KeitaroStream`, их собирает ACL |

## 4. Пересчёт весов

Доменный сервис `distribute_shares(slots)` — чистая функция:

1. Участники — привязки с `desired.included`, в порядке `seq` (порядок добавления).
2. Закреплённые сохраняют вес; сумма закреплённых > 100 → ошибка.
3. Остаток `100 − P` делится на незакреплённых поровну целыми; лишние единицы — первым по `seq` (34/33/33).
4. Если незакреплённых нет — веса возвращаются как есть; сумму ≠ 100 ловит проверка перед Push.

## 5. Объекты-значения и ошибки

- `OfferRef(id, name)`, `GeoCode` (ISO-2, разбор списка через запятую), типизированные ID `OfferId`, `StreamId`, `CampaignId` (`NewType`).
- Вес — `int` с проверкой диапазона внутри агрегата. Отдельный VO `Share` сознательно не вводим: агрегат — единственное место, где вес меняется, а арифметика с обёрткой только зашумила бы код.
- Нарушение правила → подкласс `DomainError` с машинным `code` и сообщением для пользователя. API превращает их в 409/422.

## 6. Слои

```
app/
├── domain/          чистый Python: агрегаты, VO, distribute_shares, ошибки
├── application/     сценарии (CreateCampaign, FetchStreams, EditStream, PushStream) и порты (Protocol)
├── infrastructure/  SQLAlchemy-таблицы, репозитории, Keitaro-клиент (ACL), фейковый Keitaro
└── api/             FastAPI-роутеры, Pydantic-DTO
```

`Session` SQLAlchemy — уже Unit of Work, отдельный класс поверх неё не вводим.

Раскладка: папки по областям, внутри агрегата — по роли; один модуль — одна ответственность:

```
app/
├── config.py                       настройки из .env
├── main.py                         сборка приложения FastAPI
├── api/                            HTTP: роутеры, DTO
├── application/
│   ├── ports.py                    CampaignRepository (Protocol)
│   └── errors.py                   ConcurrencyConflict, CampaignNotFound, …
├── infrastructure/
│   ├── db.py                       engine, сессии
│   └── persistence/
│       ├── base.py                 Base + правила именования ограничений
│       ├── records.py              CampaignRecord — строка таблицы campaigns
│       ├── documents.py            схема JSONB-документа (Pydantic)
│       ├── campaign_mapper.py      строка <-> агрегат
│       └── campaign_repository.py  SqlCampaignRepository
└── domain/
    ├── common/
    │   ├── ids.py                  OfferId, StreamId, CampaignId
    │   └── errors.py               базовый DomainError
    ├── offers/
    │   └── offer_ref.py            OfferRef — ссылка на внешний справочник
    ├── geo/
    │   ├── geo_code.py             GeoCode
    │   └── errors.py
    └── campaigns/                  агрегат; публичный API — campaigns/__init__.py
        ├── errors.py
        ├── model/
        │   ├── campaign.py         корень: команды, Fetch, подтверждение черновиков
        │   ├── stream.py           сущность: команды редактора, инварианты весов, Cancel/Push
        │   └── assignment.py       привязка: желаемое/опубликованное состояние, статус
        ├── services/
        │   ├── weights.py          distribute_shares — пересчёт весов
        │   └── changes.py          описание изменений для подтверждений
        ├── sync/
        │   ├── snapshots.py        снимки Keitaro — вход синхронизации
        │   └── merge.py            правила слияния с Keitaro (FR-2.3, Q7)
        └── creation/
            └── blueprint.py        чертёж новой кампании для создаватора
```

Тесты повторяют эту раскладку: `tests/domain/campaigns/…`, `tests/domain/geo/…`.

## 7. Хранение

Агрегат кампании — одна строка: данные кампании в колонках, потоки с привязками — документом в JSONB. Репозиторий переводит строку в агрегат и обратно и всегда записывает документ целиком.

```
campaigns  (id = keitaro_id PK, name, alias, domain_url, created_by_us,
            streams JSONB,
            version,                -- оптимистическая блокировка (version_id_col)
            created_at, updated_at)
```

Отдельной таблицы офферов нет: имя оффера хранится снимком в привязке, а поиск офферов идёт в Keitaro (FR-1.2). Кеш справочника добавим, только если поиск в Keitaro окажется медленным.

- **Схема** — миграции Alembic (`backend/migrations`), первая создаёт `campaigns`. Применить: `alembic upgrade head`.
- **Документ** описан Pydantic-моделями (`infrastructure/persistence/documents.py`) и валидируется при чтении; `schema_version` — для будущих изменений формата.
- **Оптимистическая блокировка** — две линии защиты:
  1. версия агрегата, прочитанная раньше, не совпадает с версией строки → `ConcurrencyConflict` сразу;
  2. два запроса прочитали одну версию одновременно → `UPDATE … WHERE version = :прочитанная` второго затрагивает 0 строк → `StaleDataError` → `ConcurrencyConflict`.
- **Транзакция** — граница сценария приложения: репозиторий делает `flush` (чтобы ошибки всплывали в нём), `commit` — сценарий.
- **Интеграционные тесты** (`tests/infrastructure`) идут на отдельной БД `adrobot_test` в том же контейнере, схема создаётся теми же миграциями; без запущенного Postgres тесты пропускаются.

```json
{
  "schema_version": 1,
  "streams": [
    {"id": 1322881, "name": "Geo AU → Google", "position": 1, "kind": "opaque", "assignments": []},
    {"id": 1322882, "name": "Offers", "position": 2, "kind": "offers",
     "assignments": [
       {"offer_id": 18813, "offer_name": "Flexacil …", "seq": 1,
        "desired":   {"included": true, "share": 50, "pinned": true},
        "published": {"present": true,  "share": 34, "pinned": false}}
     ]}
  ]
}
```

Почему JSONB, а не таблицы потоков и привязок: агрегат небольшой (единицы потоков, десятки офферов), сохраняется целиком, запросов «поперёк» агрегатов по потокам и офферам нет. Почему не MongoDB: стек ТЗ — SQLAlchemy; реляционные части (FK, UNIQUE, транзакции, версия) остаются в Postgres.
