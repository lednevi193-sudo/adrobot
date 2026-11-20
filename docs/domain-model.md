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
| `changes_in_keitaro` | «Что поменяли прямо в Keitaro» относительно опубликованного (черновик не в счёт) — предупреждение при открытии кампании с черновиком |

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
published: PublishedState(in_rotation, share, pinned, pinned_share) — что лежит в Keitaro;
           pinned_share — закреплённый вес последнего Push (может разойтись с share, FR-2.9a)
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
├── api/
│   ├── routers/                    health, offers, campaigns, streams — тонкие: DTO -> сценарий -> DTO
│   ├── schemas.py                  DTO запросов и ответов (CampaignView, …)
│   ├── presenters.py               агрегат -> CampaignView (push_blocker, keitaro_share)
│   ├── errors.py                   DomainError/ApplicationError -> HTTP-статус и тело {code, message}
│   └── dependencies.py             Depends: Session на запрос, шлюз Keitaro на процесс
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
│   ├── db.py                       engine, сессии (ленивые: импорт без .env)
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

Отдельной таблицы офферов нет: имя оффера хранится снимком в привязке, а поиск офферов идёт в Keitaro (FR-1.2). Для имён, поиска и проверки оффера используется общий TTL-кеш шлюза (см. § 9).

- **Схема** — миграции Alembic (`backend/migrations`), первая создаёт `campaigns`. Применить: `alembic upgrade head`.
- **Документ** описан Pydantic-моделями (`infrastructure/persistence/documents.py`) и валидируется при чтении; `schema_version` — для будущих изменений формата.
- **Конкурентная правка** — три линии защиты:
  1. короткий захват Push сохраняет `push_in_progress` и увеличивает version до первого HTTP; второй захват той же версии конфликтует, живая отметка запрещает другой Push кампании и команды публикуемого потока;
  2. версия, которую видел пользователь (`If-Match`), не совпадает с версией строки → `ConcurrencyConflict` сразу (`load_campaign`);
  3. два запроса прочитали одну версию одновременно → `UPDATE … WHERE version = :прочитанная` второго затрагивает 0 строк → `StaleDataError` → `ConcurrencyConflict`.
- **Транзакция** — короткая граница изменения БД: репозиторий делает `flush`, сценарий — `commit`/`rollback`. Push завершает захват до HTTP и открывает новую транзакцию только для фиксации; Open/Fetch завершают чтение БД до загрузки Keitaro. `SELECT FOR UPDATE` и соответствующий метод репозитория удалены.
- **Отметка Push** — `push_in_progress: {stream_id, started_at, token}` в корне JSONB-документа, либо null. В старых документах поле отсутствует и читается как None; schema_version=1, миграция БД не нужна. token определяет владельца: завершение старого запроса не снимает отметку нового.
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
        "published": {"in_rotation": true, "share": 34, "pinned": false, "pinned_share": null}}
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
| `gateway.py` | полный снимок для Open/Fetch, точечные чтения для Push, общий TTL-кеш офферов | реализация `IKeitaroApi` |

**Правила перевода из Keitaro:**
- поток в архиве (`state = deleted`) для обёртки не существует;
- в раздаче только офферы потока со `state = active` — выключенный оффер трафик не получает;
- имя оффера берётся из `GET /offers`; оффера, скрытого от ключа (Q6), там нет — имя пустое, UI показывает `[id]`;
- 404 на кампанию -> `CampaignNotFound` (стенд отдаёт HTML nginx, разметка в сообщение не попадает);
- `get_campaign_name` делает только `GET /campaigns/{id}` и возвращает имя;
- `get_stream` делает только `GET /streams/{sid}`: `id`, `campaign_id`, активные офферы с ID и весами без имён, плюс неизменяемый снимок неактивных офферов для PUT. Справочник не читается. 404 или удалённый поток -> `StreamNotInCampaign`.

**Правила перевода в Keitaro:**
- `alias` обязателен при создании кампании (документация Keitaro) — генерируем 8 символов `[A-Za-z0-9]`, как у алиасов самого Keitaro;
- гео-поток: `type=forced`, `schema=redirect`, фильтр `country/accept`; поток офферов: `type=regular`, `schema=landings`, `offers[{offer_id, share, state}]`;
- Push — `PUT /streams/{id}` только с полем `offers`: по документации PUT меняет лишь переданные поля. До записи шлюза сценарий проверяет актуальный префикс кампании в Keitaro и наличие потока в ней.

`offers` в PUT заменяет список потока целиком. Неактивные строки сохраняются с исходными `state` и `share`, кроме офферов, которые Adrobot явно включает. `publish_offers(current=...)` получает уже прочитанный снимок, поэтому повторный GET перед PUT не нужен.

**Запросы одного Push:**

| Порядок | Запрос | Зачем |
|---|---|---|
| 1 | GET /campaigns/{id} | Временная страховка тестового стенда: проверить актуальный префикс |
| 2 | GET /streams/{sid} | Проверить существование и campaign_id; поток не меняли в Keitaro после Fetch; сохранить неактивные строки для PUT |
| 3 | PUT /streams/{sid} | Опубликовать только offers, сохранив неактивные |
| 4 | GET /streams/{sid} | Независимо сверить активные ID/share одного потока |

Итого четыре запроса, без `/offers` и `/campaigns/{id}/streams`. В боевой версии проверка имени на стенде убирается: префикс проверяется по `campaign.is_ours` из нашей БД, останется три запроса. Ответ PUT пока не используется для сверки: стенд не подтвердил его эквивалентность последующему GET. Если проверка на стенде подтвердит совпадение, сверка по ответу PUT сократит ещё один запрос.

**Кеш справочника:** один на экземпляр шлюза, то есть на процесс (`get_keitaro` кешируется). `KEITARO_OFFERS_TTL` — секунды, default 60, 0 отключает кеш. `get_campaign`, `list_active_offers` и проверка `find_offer` используют один снимок. `threading.Lock` охватывает проверку срока, загрузку и запись; часы внедряются (`time.monotonic` по умолчанию), тесты обходятся без sleep. Ошибка HTTP или разбора не кешируется: следующий вызов повторяет загрузку. Принудительного сброса нет: имя нового оффера и изменения справочника становятся видны не позже TTL.

**Сознательно не делаем:** ограничитель частоты, сетевые повторы и отступление при ошибках. POST не идемпотентен, повтор PUT остаётся явным решением вызывающего робота/пользователя.

**Тесты:** `tests/infrastructure/keitaro` — `httpx.MockTransport` (≈ свой `HttpMessageHandler`) с JSON в форме стенда; `tests/fakes/keitaro_gateway.py` — Keitaro в памяти для сценариев приложения, с `fail_on` для проверки компенсации FR-1.6.

## 10. Сценарии приложения

Сценарий — функция с явными зависимостями-портами: `push_stream(repo, keitaro, uow, campaign_id, stream_id, prefix=…)`. Внедрение — `Depends` на шаге API; классы-хендлеры в духе MediatR не вводим. Сценарий задаёт границу транзакции (`uow.commit()`), правила живут в домене.

| Сценарий | Шаги |
|---|---|
| `create_campaign` | оффер из Keitaro, `CampaignBlueprint` (ошибки формы — до Keitaro) → кампания → 2 потока → снимок → `repo.add` → commit |
| `search_offers` | активные офферы, по ID и подстроке названия, не больше 20 |
| `list_campaigns` | наши (`is_our_name`) — из нашей БД без обращения к Keitaro; все — из Keitaro; новые первыми. Наша кампания, созданная прямо в Keitaro, попадает в список после первого открытия по ID |
| `open_campaign` | впервые — импорт из Keitaro (гонка двух открытий — берём уже сохранённую). Дальше каждое открытие сверяется с Keitaro (`changes_in_keitaro`): без черновика — синхронизация как Fetch, запись в БД только при изменениях; с черновиком — кампания не трогается, список изменений уходит пользователю (`keitaro_changes`); удалённая в Keitaro — показываем то, что знаем |
| `fetch_streams` | снимок Keitaro → `sync_from_keitaro(discard_drafts)` → save. При черновике без подтверждения — `CampaignHasDrafts`, ничего не сохраняется |
| `edit_stream.*` | add (имя оффера — из Keitaro, не от клиента), remove, bring_back, pin, unpin, cancel: загрузить → команда корня → save |
| `push_stream` | короткий захват по version → 4 HTTP-запроса без транзакции → короткая фиксация опубликованного потока и снятие отметки |

**Решения:**
- **Создание — сага с компенсацией.** Распределённой транзакции между Keitaro и Postgres нет. Любой сбой после создания кампании (поток, повторное чтение, наша БД) → `rollback` + перенос кампании в архив Keitaro → `CampaignCreationFailed`. Если и компенсация не удалась — сообщение просит удалить кампанию вручную.
- **Push — двухфазная работа с БД, HTTP между фазами.**
  1. Обычный get, expected_version, префикс из БД, `offers_to_publish`, проверка отсутствия живого Push. Записать `{stream_id, started_at, token}`, save + commit. SQL-версия растёт: два захвата одной версии не могут оба пройти. Соединение возвращается в пул.
  2. Вне транзакции: временная проверка имени Keitaro, чтение одного потока с проверкой campaign_id, PUT с сохранёнными неактивными строками, повторный GET того же потока и сверка. Полный снимок кампании и каталог офферов здесь не нужны (точные запросы — § 9). После чтения потока, перед PUT, проверяется оставшееся время захвата: должен оставаться запас четырёх HTTP-таймаутов на запись и сверку; иначе запрос прекращается с ConcurrencyConflict до PUT.
  3. Перечитать свежую кампанию, проверить владельца и совпадение текущей раздачи с отправленной, `mark_published`, снять отметку, save + commit. Правки других потоков сохраняются. При гонке save — rollback, перечитать и принять публикацию через `adopt_published`, если раздача совпадает; иначе ConcurrencyConflict.
  4. При ошибке — rollback и отдельная короткая транзакция снимает только отметку своего token, черновик не меняется. Если БД недоступна и снять отметку нельзя, исходная ошибка сохраняется, событие пишется в лог, отметка истекает по TTL.
  5. `PUSH_LEASE_MINUTES` (default 5) определяет срок живой отметки; конфигурация требует `minutes * 60 > 4 * KEITARO_TIMEOUT`, чтобы захват не истекал в штатном окне HTTP. Зависшая после смерти процесса отметка старше TTL не блокирует новый Push или редактор. Fetch снимает её и через `adopt_published` принимает уже отправленный черновик без потери pin. Пока отметка жива, другой Push этой кампании, изменение этого потока и Fetch получают 409 `push_in_progress`; Open отдаёт сохранённый агрегат без автосинхронизации. Команды других потоков разрешены.
- Захват и снятие отметки повышают version даже при неудачном Push. Робот после ошибки перечитывает актуальную кампанию перед следующим запросом с If-Match. Повторов HTTP автоматически нет.
- **Жёлтый поток ≠ черновик.** `has_draft` — желаемое расходится с Keitaro; `draft_changes()` — только то, что отменит Cancel. Разница — закреплённый вес, который поменяли руками в Keitaro (FR-2.9a): Cancel и Fetch его не трогают, решают Push или Unpin (Unpin в этом случае принимает веса из Keitaro).
- **Поток поменяли в Keitaro после последнего Fetch** → `StreamChangedInKeitaro` (409, + `differences`), в Keitaro ничего не пишется. Перед PUT активные офферы и веса потока из шага 2 сравниваются с опубликованным состоянием привязок (то, что обёртка видела при последнем Fetch или Push). Keitaro не умеет «записать, только если не изменилось», поэтому окно между шагами 2 и 3 остаётся, но оно сужается с «от Fetch до Push» до долей секунды. Расхождение закреплённого веса ложной тревоги не даёт: Fetch уже записал вес Keitaro в опубликованное.
- **Сверка после Push (FR-2.13 п. 3)** не сошлась → `PushNotConfirmed` со списком расхождений, черновик не трогаем, поток жёлтый.
- **Push только в наши кампании** (`NotOurCampaign`): стенд общий (NFR-4). Чужие кампании можно открыть, синхронизировать и редактировать черновиком, но не публиковать. Без `CAMPAIGN_PREFIX` «наших» нет вовсе.
- Команды редактора Keitaro не трогают и проверку «наша ли» не делают: черновик безвреден.

**Тесты:** `tests/fakes/campaign_repository.py` — репозиторий в памяти с семантикой Session: записи видны после commit, rollback их выбрасывает, `get` отдаёт копию, версии как у `version_id_col`. Поэтому тесты проверяют и «в БД ничего не попало», а не только вызовы.

## 11. HTTP API

Все маршруты под `/api`, Swagger — `/docs`. Команды редактора возвращают `CampaignView` целиком: фронт перерисовывает присланное, своего состояния не держит.

| Маршрут | Сценарий |
|---|---|
| `GET /offers?q=` | автодополнение |
| `GET /campaigns?all=false` | список: наши — из БД, `all=true` — все из Keitaro |
| `POST /campaigns` → 201 | создаватор |
| `GET /campaigns/{id}` → `{campaign, keitaro_changes}` | открыть со сверкой с Keitaro |
| `POST /campaigns/{id}/fetch` `{discard_drafts}` | Fetch streams |
| `GET …/streams/{sid}/draft` | `{version, changes}` для подтверждения Cancel |
| `POST …/streams/{sid}/offers`, `DELETE …/offers/{oid}` | Add, Remove |
| `POST …/offers/{oid}/bring-back` | Bring back |
| `PUT` / `DELETE …/offers/{oid}/pin` | Pin / Unpin |
| `POST …/streams/{sid}/cancel`, `POST …/streams/{sid}/push` | Cancel, Push |
| `GET /health` | приложение живо и видит БД (503, если нет) |

`CampaignView.version` — версия кампании. Fetch и все команды редактора принимают её в заголовке `If-Match` (необязательно): версия устарела → 409 `concurrency_conflict`. Так подтверждение Cancel и Fetch с `discard_drafts` отбрасывает ровно тот черновик, который пользователь видел (FR-2.3a, FR-2.10a). `/draft` возвращает `{version, changes}`, ошибка `campaign_has_drafts` при Fetch включает `version`; окно сохраняет эту версию и отправляет её при подтверждении, даже если позже пришёл другой ответ.

`StreamView.push_blocker` — сообщение правила FR-2.12, если Push сейчас невозможен (считается тем же `offers_to_publish`, фронт правила не дублирует). `StreamOfferView.keitaro_share` — вес в Keitaro для подсказки FR-2.9a.

| Ошибка | HTTP |
|---|---|
| `DomainError` (правило нарушено) | 422 |
| `CampaignHasDrafts` (+ `changes` для окна подтверждения) | 409 |
| `ConcurrencyConflict`, `CampaignAlreadyExists` | 409 |
| `PushInProgress` (`push_in_progress`, «Push потока уже выполняется») | 409 |
| `StreamChangedInKeitaro` (+ `differences`: что поменяли в Keitaro после Fetch) | 409 |
| `CampaignNotFound`, `OfferNotFound`, `StreamNotInCampaign`, `OfferNotInStream` | 404 |
| `NotOurCampaign` | 403 |
| `KeitaroError`, `CampaignCreationFailed`, `PushNotConfirmed` (+ `differences`) | 502 |
| `KeitaroUnavailable` | 504 |
| прочие `ApplicationError` | 500 |

Эндпоинты — обычные `def`: FastAPI выполняет их в пуле потоков, синхронные SQLAlchemy и httpx на время I/O отпускают GIL. Тесты (`tests/api`) — `TestClient` с `app.dependency_overrides` на фейки (≈ `WebApplicationFactory`).

## 12. Фронтенд

Vue 3 + TypeScript + Naive UI, сборка Vite (`frontend/`). Фронт — тонкий клиент HTTP API из раздела 11: правил домена (веса, состояния, «жёлтый ли поток», `push_blocker`) в нём нет, он только показывает присланный `CampaignView`.

```
frontend/src/
  shared/api/   http.ts (единственный fetch, ≈ typed HttpClient), apiError.ts (ApiError{status, code, message, body}), errorTitle.ts
  shared/ui/    ErrorAlert — заголовок по статусу, message бэкенда, differences после Push
  offers/       OfferPicker — автодополнение «[id] name» для создаватора и Add offer
  creator/      CreatorPage, fieldErrors (code -> поле формы)
  editor/       api/ (DTO 1:1 со schemas.py, клиенты), useCampaignEditor, list/, page/, stream/, draft/
frontend/tests/ повторяет src/
```

| Решение | Почему |
|---|---|
| Состояние редактора — composable `useCampaignEditor` (≈ scoped-сервис страницы), без глобального store | Источник истины — сервер: каждая команда возвращает `CampaignView`, composable кладёт его в один `ref` |
| DTO описаны вручную в `editor/api/types.ts` | Контракт маленький; генератор (≈ NSwag) не окупается |
| Ошибка API — `ApiError` с `code` из тела | Логика фронта ветвится по `code` (`campaign_has_drafts`, `invalid_geo`…), текст для пользователя — `message` бэкенда |
| Fetch при черновике: 409 → окно со списком `changes` → повтор с `discard_drafts: true` | FR-2.3a; то же окно (`ConfirmDiscardModal`) — для Cancel по `GET …/draft` (FR-2.10a) |
| Маршруты `/campaigns`, `/campaigns/:id`, `/create` | Список — часть редактора (FR-2.1), как `list_campaigns` в `application/editor` |

**Запуск.** Разработка: бэкенд на :8000 и `npm --prefix frontend run dev` (Vite на :5173 проксирует `/api` на FastAPI). Прод: `npm --prefix frontend run build`, и `frontend/dist` раздаёт сам FastAPI (`app/spa.py`, ≈ `UseStaticFiles` + `MapFallbackToFile`): файл из `dist` или `index.html` для маршрутов SPA; `/api/*` и `/docs` не перехватываются. Тесты — `npm --prefix frontend test` (Vitest + Vue Test Utils, jsdom).


## 13. Локальный деморежим

Отдельная фабрика `app.demo:create_demo_app` использует те же сценарии, домен,
HTTP API и фронтенд. Порты Keitaro, Repository и UnitOfWork заменены локальными
реализациями в памяти; `.env`, PostgreSQL и сетевой Keitaro не используются.
Каждый экземпляр приложения начинает с трёх офферов и двух кампаний (2/3 оффера).
Операции сериализуются блокировкой демохранилища, несохранённые данные запроса
отбрасываются, версии агрегатов проверяются. Запуск — один процесс; перезапуск
сбрасывает состояние. Инструкция — в README.

`GET /api/runtime` сообщает `mode: live|demo` для баннера и меню. Только демофабрика
регистрирует `GET /api/demo/keitaro` и `PUT /api/demo/keitaro/campaigns/{id}`:
состав/веса/порядок офферов и имя кампании меняются в опубликованном состоянии,
не затрагивая агрегат Adrobot и его черновик. Страница `/demo/keitaro` имитирует
ручное изменение в админке: затем обычные Open/Fetch выявляют и сливают изменения.
Это стенд для проверки поведения приложения, без перенаправления реального трафика.

В демо-Keitaro каждая строка потока имеет `state: active|disabled` (по умолчанию active для прежних запросов). Полный список сохраняет выключенные офферы и их веса; порт Keitaro отдаёт домену только active, как HTTP ACL. Push сохраняет выключенные строки, кроме явно возвращаемых Adrobot офферов: они включаются без дубля. Внешняя правка допускает любую сумму весов, чтобы переключение состояния не изменяло сохранённые веса; правила публикации по-прежнему проверяет домен Adrobot.
