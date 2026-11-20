# Adrobot — доменная модель

Дополняет [requirements.md](requirements.md). Подход — DDD: чистый домен без зависимостей от БД и HTTP, инварианты внутри агрегатов.

## 1. Контекст и границы

- Один ограниченный контекст — «управление офферами в кампаниях Keitaro».
- Keitaro — внешняя система. Между ней и доменом стоит **Anti-Corruption Layer** (`KeitaroGateway` в `infrastructure`): переводит JSON Keitaro в объекты домена и обратно. Домен не знает про HTTP, `share`, `type: forced` и т. п.
- Идентичность сущностей — их ID в Keitaro. Поток и кампания всегда сначала существуют в Keitaro, а потом попадают к нам, поэтому суррогатные ключи не нужны.

## 2. Единый язык

Каждое имя в коде — термин бизнеса из ТЗ, видео заказчика или интерфейса Keitaro. Если в разговоре с заказчиком слово звучит иначе, чем в коде, — меняется код.

### Агрегат `campaigns/model` — то, что пользователь видит и меняет в редакторе

| В коде | Термин | Бизнес-значение |
|---|---|---|
| `Campaign` | кампания | Ссылка трекера, которую байер отдаёт в источник трафика, и потоки, решающие, куда идёт посетитель |
| `Campaign.tracker_url` | ссылка трекера | Домен + alias, например `https://kylovoa.com/VrfMdGff` |
| `Campaign.is_ours(prefix)` | наша кампания | Название с префиксом `CAMPAIGN_PREFIX` (FR-2.1, Q5). Признак виден и в самом Keitaro, отдельного флага нет |
| `Stream` | поток | Правило маршрутизации: кого, куда и в какой пропорции. Проверяются по `position` сверху вниз |
| `StreamKind.OFFERS` / `OTHER` | поток с офферами / любой другой | Первым обёртка управляет; второй (например, гео-редирект) только показывает |
| `OfferAssignment` | оффер в потоке | Конкретный оффер получает долю трафика потока. Жизненный цикл: добавлен → опубликован → удалён → архив |
| `OfferAssignment.order` | порядок оффера в потоке | Порядок в списке потока (как в Keitaro, новые — в конец). По нему раздаются лишние единицы при округлении |
| `share` | вес | Процент трафика потока; целое число, как в Keitaro |
| `in_rotation` | в раздаче | Оффер участвует в дележе трафика потока. Одно слово для желаемого и опубликованного состояния |
| `DesiredState` / `PublishedState` | как хочу / как в Keitaro | Желаемое состояние в обёртке и опубликованное в Keitaro |
| `AssignmentStatus` | состояние оффера | `active`, `pending_add`, `pending_remove`, `removed` — ровно FR-2.4 |
| `pin` / `unpin` | закрепить вес | «Этому офферу всегда N%» — сознательное решение пользователя, главнее Keitaro (FR-2.9a, Q7) |
| `has_draft`, `draft_changes()` | черновик, поток жёлтый | Неопубликованные изменения потока (FR-2.5) |
| `DraftChange` | изменение черновика | Строка в подтверждении Cancel/Fetch: «будет отменено: добавление оффера [25327] …» |
| `add_offer`, `remove_offer`, `bring_back`, `cancel` | Add offer, Remove, Bring back, Cancel | Кнопки редактора из видео |
| `offers_to_publish`, `mark_published` | Push | Что уходит в Keitaro и фиксация успешной публикации |

### `campaigns/services` — правила, которые не принадлежат одной сущности

| В коде | Бизнес-значение |
|---|---|
| `distribute_shares` | Как делится трафик: закреплённым — их вес, остальным — поровну, 34/33/33 |

### `campaigns/sync` — как обёртка узнаёт о правках, сделанных прямо в Keitaro

| В коде | Бизнес-значение |
|---|---|
| `sync_from_keitaro` | Кнопка Fetch streams |
| `KeitaroCampaign`, `KeitaroStream` | «Что сейчас в Keitaro». Keitaro — часть языка пользователя («в Keitaro сейчас 30%»), поэтому имя внешней системы здесь уместно |
| `PublishedOffer` | Строка раздачи потока в Keitaro: оффер и его вес |
| `merge_published` | Таблица FR-2.3: что происходит с оффером, который пропал из Keitaro, появился в нём и т. д. |

### `campaigns/creation` — создаватор

| В коде | Бизнес-значение |
|---|---|
| `CampaignBlueprint` | Заявка на новую кампанию: имя, страны, оффер. Не агрегат — кампании ещё нет, она появится только в Keitaro |
| `GeoRedirectStreamSpec`, `OffersStreamSpec` | Стандартная схема из ТЗ: «эти страны → Google, остальные → оффер» |

### Соседние области

| В коде | Бизнес-значение |
|---|---|
| `geo/GeoCode` | Страна таргетинга — понятие таргетинга, а не кампании: нужно и создаватору, и фильтру потока |
| `offers/OfferRef` | Оффер из справочника Keitaro: мы на него ссылаемся, но не владеем им |
| `common/ids` | ID в Keitaro — идентичность всех сущностей задаёт Keitaro |

**Сознательное исключение:** `Campaign.version` — техническое поле оптимистической блокировки в доменной сущности (как `RowVersion` в сущности EF Core). Вынести его наружу агрегата можно, но это усложнило бы репозиторий без пользы для языка.

## 3. Агрегаты

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

**Оффер** — не агрегат, а внешний справочник (им владеет Keitaro). Агрегат держит снимок `OfferRef(id, name)`.

## 4. Желаемое и опубликованное состояние

У каждой привязки два снимка:

```
desired:   DesiredState(in_rotation, share, pinned)   — что видит пользователь в обёртке
published: PublishedState(in_rotation, share, pinned) — что лежит в Keitaro
           или None — привязка ни разу не публиковалась
```

Статус не хранится, а вычисляется:

| desired.in_rotation | published.in_rotation | Статус |
|---|---|---|
| ✔ | ✔ | `active` |
| ✔ | ✘ или None | `pending_add` |
| ✘ | ✔ | `pending_remove` |
| ✘ | ✘ | `removed` (архив) |

Комбинация «✘ + None» невозможна: неопубликованная привязка при удалении выбрасывается целиком.

| Операция | Реализация |
|---|---|
| Черновик (`has_draft`, поток жёлтый) | у какой-либо привязки `desired` расходится с `published` |
| Cancel | `desired := published`; привязки с `published = None` выбрасываются |
| Push (успех) | `published := desired`; исключённые → `published.in_rotation = false` (архив) |
| Список изменений для подтверждения | разница `desired` / `published` по привязкам |
| Fetch | `published :=` данные Keitaro; `desired` правится по FR-2.3; закреплённый вес не перетирается (Q7). Входные данные — снимки `KeitaroCampaign` / `KeitaroStream`, их собирает ACL |

## 5. Пересчёт весов

Доменный сервис `distribute_shares(slots)` — чистая функция:

1. Участники — офферы в раздаче (`desired.in_rotation`), в порядке потока (`order`).
2. Закреплённые сохраняют вес; сумма закреплённых > 100 → ошибка.
3. Остаток `100 − P` делится на незакреплённых поровну целыми; лишние единицы — первым по `order` (34/33/33).
4. Если незакреплённых нет — веса возвращаются как есть; сумму ≠ 100 ловит проверка перед Push.

## 6. Объекты-значения и ошибки

- `OfferRef(id, name)`, `GeoCode` (ISO-2, разбор списка через запятую), типизированные ID `OfferId`, `StreamId`, `CampaignId` (`NewType`).
- Вес — `int` с проверкой диапазона внутри агрегата. Отдельный VO `Share` сознательно не вводим: агрегат — единственное место, где вес меняется, а арифметика с обёрткой только зашумила бы код.
- Нарушение правила → подкласс `DomainError` с машинным `code` и сообщением для пользователя. API превращает их в 409/422.

## 7. Слои

```
app/
├── domain/          чистый Python: агрегаты, VO, distribute_shares, ошибки
├── application/     сценарии (CreateCampaign, FetchStreams, EditStream, PushStream) и порты (Protocol)
├── infrastructure/  SQLAlchemy-таблицы, репозитории, Keitaro-клиент (ACL)
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
│   ├── ports/                      один порт — один модуль (Protocol)
│   │   ├── campaign_repository.py  CampaignRepository
│   │   ├── keitaro_gateway.py      KeitaroGateway, CampaignSummary
│   │   └── unit_of_work.py         UnitOfWork (commit/rollback) — Session подходит как есть
│   ├── creator/create_campaign.py  создаватор с компенсацией (раздел 10)
│   ├── offers/search_offers.py     автодополнение и поиск выбранного оффера
│   ├── editor/                     list, open, fetch, edit (команды), push
│   └── errors.py                   ConcurrencyConflict, CampaignNotFound, KeitaroError, …
├── infrastructure/
│   ├── db.py                       engine, сессии
│   ├── keitaro/                    ACL к Keitaro (раздел 9)
│   │   ├── client.py               транспорт: заголовки, таймаут, ошибки -> KeitaroError
│   │   ├── schemas.py              форма ответов Keitaro (Pydantic, только нужные поля)
│   │   ├── from_keitaro.py         JSON -> снимки домена
│   │   ├── to_keitaro.py           спецификации домена -> тела запросов
│   │   └── gateway.py              HttpKeitaroGateway — реализация порта
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
        │   ├── assignment.py       оффер в потоке: желаемое/опубликованное состояние, статус
        │   └── draft.py            черновик: DraftChange — строка подтверждения Cancel/Fetch
        ├── services/
        │   └── weights.py          distribute_shares — пересчёт весов
        ├── sync/
        │   ├── snapshots.py        снимки Keitaro — вход синхронизации
        │   └── merge.py            правила слияния с Keitaro (FR-2.3, Q7)
        └── creation/
            └── blueprint.py        чертёж новой кампании для создаватора
```

Тесты повторяют эту раскладку: `tests/domain/campaigns/…`, `tests/infrastructure/keitaro/…`. Сценарии — `tests/application/…` на фейках портов (`tests/fakes/`).

## 8. Хранение

Агрегат кампании — одна строка: данные кампании в колонках, потоки с привязками — документом в JSONB. Репозиторий переводит строку в агрегат и обратно и всегда записывает документ целиком.

```
campaigns  (id = keitaro_id PK, name, alias, domain_url,
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
    {"id": 1322881, "name": "Geo AU → Google", "position": 1, "kind": "other", "assignments": []},
    {"id": 1322882, "name": "Offers", "position": 2, "kind": "offers",
     "assignments": [
       {"offer_id": 18813, "offer_name": "Flexacil …", "order": 1,
        "desired":   {"in_rotation": true, "share": 50, "pinned": true},
        "published": {"in_rotation": true, "share": 34, "pinned": false}}
     ]}
  ]
}
```

Почему JSONB, а не таблицы потоков и привязок: агрегат небольшой (единицы потоков, десятки офферов), сохраняется целиком, запросов «поперёк» агрегатов по потокам и офферам нет. Почему не MongoDB: стек ТЗ — SQLAlchemy; реляционные части (FK, UNIQUE, транзакции, версия) остаются в Postgres.

## 9. Keitaro ACL

Порт `KeitaroGateway` (`application/ports`) говорит на языке домена: снимки `KeitaroCampaign`, спецификации потоков из `CampaignBlueprint`, `PublishedOffer`. Реализация `HttpKeitaroGateway` (`infrastructure/keitaro`) — единственное место, которое знает про HTTP, JSON и значения Keitaro.

| Слой ACL | Ответственность | Аналог в .NET |
|---|---|---|
| `client.py` | `httpx.Client` с `base_url`, `Api-Key`, явным `User-Agent`, таймаутом; 4xx/5xx -> `KeitaroError` с текстом Keitaro, таймаут/сеть -> `KeitaroUnavailable` | typed `HttpClient` + `DelegatingHandler` |
| `schemas.py` | Pydantic-модели ответов, `extra="ignore"`: новые поля Keitaro чтение не ломают, пропавшие нужные — `KeitaroError` «неожиданный формат» | DTO для `ReadFromJsonAsync` |
| `from_keitaro.py`, `to_keitaro.py` | перевод в обе стороны | AutoMapper-профили, только руками |
| `gateway.py` | сборка снимка из нескольких запросов: кампания + потоки + справочник офферов (имена) | реализация `IKeitaroApi` |

**Правила перевода из Keitaro:**
- поток в архиве (`state = deleted`) для обёртки не существует;
- в раздаче только офферы потока со `state = active` — выключенный оффер трафик не получает;
- имя оффера берётся из `GET /offers`; оффера, скрытого от ключа (Q6), там нет — имя пустое, UI показывает `[id]`;
- 404 на кампанию -> `CampaignNotFound` (стенд отдаёт HTML nginx, разметка в сообщение не попадает).

**Правила перевода в Keitaro:**
- `alias` обязателен при создании кампании (документация Keitaro) — генерируем 8 символов `[A-Za-z0-9]`, как у алиасов самого Keitaro;
- гео-поток: `type=forced`, `schema=redirect`, фильтр `country/accept`; поток офферов: `type=regular`, `schema=landings`, `offers[{offer_id, share, state}]`;
- Push — `PUT /streams/{id}` только с полем `offers`: по документации PUT меняет лишь переданные поля.

**Не подтверждено документацией** (проверить на своей кампании, шаг 8): заменяет ли `offers` в PUT список целиком, то есть удаляются ли неперечисленные офферы. До проверки страхует сверка после Push (FR-2.13, п. 3).

**Сознательно не делаем:** повторы запросов (POST не идемпотентен, а повтор PUT с весами оставим пользователю — кнопка Push), кеш справочника офферов (один запрос на Fetch).

**Тесты:** `tests/infrastructure/keitaro` — `httpx.MockTransport` (≈ свой `HttpMessageHandler`) с JSON в форме стенда; `tests/fakes/keitaro_gateway.py` — Keitaro в памяти для сценариев приложения, с `fail_on` для проверки компенсации FR-1.6.

## 10. Сценарии приложения

Сценарий — функция с явными зависимостями-портами: `push_stream(repo, keitaro, uow, campaign_id, stream_id, prefix=…)`. Внедрение — `Depends` на шаге API; классы-хендлеры в духе MediatR не вводим. Сценарий задаёт границу транзакции (`uow.commit()`), правила живут в домене.

| Сценарий | Шаги |
|---|---|
| `create_campaign` | оффер из Keitaro, `CampaignBlueprint` (ошибки формы — до Keitaro) → кампания → 2 потока → снимок → `repo.add` → commit |
| `search_offers` | активные офферы, по ID и подстроке названия, не больше 20 |
| `list_campaigns` | список из Keitaro, по умолчанию только наши (`is_our_name`), новые первыми |
| `open_campaign` | из БД; впервые — из Keitaro с сохранением; гонка двух открытий — берём уже сохранённую |
| `fetch_streams` | снимок Keitaro → `sync_from_keitaro(discard_drafts)` → save. При черновике без подтверждения — `CampaignHasDrafts`, ничего не сохраняется |
| `edit_stream.*` | add (имя оффера — из Keitaro, не от клиента), remove, bring_back, pin, unpin, cancel: загрузить → команда корня → save |
| `push_stream` | только наша кампания → `offers_to_publish` → `publish_offers` → повторное чтение и сверка → `mark_published` → save |

**Решения:**
- **Создание — сага с компенсацией.** Распределённой транзакции между Keitaro и Postgres нет. Любой сбой после создания кампании (поток, повторное чтение, наша БД) → `rollback` + перенос кампании в архив Keitaro → `CampaignCreationFailed`. Если и компенсация не удалась — сообщение просит удалить кампанию вручную.
- **Push — сначала Keitaro, потом БД.** Keitaro принял, а наш commit упал → поток остаётся жёлтым, ближайший Fetch выровняет его, закреплённые веса сохранятся (Q7).
- **Сверка после Push (FR-2.13 п. 3)** не сошлась → `PushNotConfirmed` со списком расхождений, черновик не трогаем, поток жёлтый.
- **Push только в наши кампании** (`NotOurCampaign`): стенд общий (NFR-4). Чужие кампании можно открыть, синхронизировать и редактировать черновиком, но не публиковать. Без `CAMPAIGN_PREFIX` «наших» нет вовсе.
- Команды редактора Keitaro не трогают и проверку «наша ли» не делают: черновик безвреден.

**Тесты:** `tests/fakes/campaign_repository.py` — репозиторий в памяти с семантикой Session: записи видны после commit, rollback их выбрасывает, `get` отдаёт копию, версии как у `version_id_col`. Поэтому тесты проверяют и «в БД ничего не попало», а не только вызовы.
