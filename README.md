# Adrobot — обёртка над трекером Keitaro

Создаватор кампаний и редактор офферов в потоках поверх Keitaro Admin API. Изменения копятся черновиком в своей БД и публикуются в Keitaro по кнопке Push.

- Требования: [docs/requirements.md](docs/requirements.md)
- Доменная модель, единый язык, HTTP API, фронтенд: [docs/domain-model.md](docs/domain-model.md)

Стек: FastAPI + SQLAlchemy 2 + Alembic + PostgreSQL (Docker) на бэкенде, Vue 3 + TypeScript + Naive UI + Vite на фронте.

## Что нужно

- Python 3.12+
- Node.js 22+ (Vite 8)
- Docker (для Postgres)

Команды ниже — для PowerShell, из корня репозитория.

## Локальное демо: три оффера и правки «в Keitaro»

После установки Python/Node-зависимостей по разделам ниже запустите:

```powershell
.\scripts\demo.ps1
```

Откройте http://127.0.0.1:8001. Скрипт собирает фронтенд и запускает отдельный
демосервер. PostgreSQL, `.env` и API-токен не нужны. Доступны три оффера
`101`, `102`, `103` и готовые кампании `demo_2_offers` и `demo_3_offers`.
Можно создавать новые кампании, добавлять и удалять офферы, закреплять веса,
выполнять Cancel, Fetch и Push. Все данные демо изолированы и сбрасываются при
перезапуске. Остановка — Ctrl+C; другой порт — `.\scripts\demo.ps1 -Port 8002`.

В меню **Демо-Keitaro** меняется опубликованное состояние отдельно от черновика
Adrobot: название кампании, состав офферов, их веса, порядок и переключатель «Включён» в каждой строке. Откройте редактор
Adrobot в другой вкладке, внесите правки в демо-Keitaro, затем вернитесь и
нажмите Fetch streams или откройте кампанию заново. Так проверяются внешние
изменения, подтверждение потери черновика и расхождение закреплённого веса.
Выключенные офферы остаются в демо-Keitaro со своим весом, но Fetch исключает их из раздачи Adrobot. Push сохраняет выключенные строки; явный Bring back + Push включает оффер снова. Можно выключить все офферы и включить их обратно. Внешние веса сохраняются как введены, без автоматического пересчёта; ограничения Push проверяет Adrobot.

Прямой запуск без повторной сборки фронтенда:

```powershell
backend\.venv\Scripts\python -m uvicorn app.demo:create_demo_app --factory --app-dir backend --host 127.0.0.1 --port 8001
```

Демо запускается одним процессом. При использовании команды выше сначала
выполните `npm --prefix frontend run build`. Для демо открывайте порт 8001:
обычный Vite на 5173 проксирует запросы на основной бэкенд 8000.

## 1. Настройки

```powershell
Copy-Item .env.example .env
```

В `.env` заполните `KEITARO_API_KEY` и `CAMPAIGN_PREFIX` (например, `test_ivanov_`). Остальное уже настроено на стенд и локальный Postgres. Файл `.env` в git не попадает.

`KEITARO_OFFERS_TTL` задаёт TTL общего кеша офферов на процесс (секунды, по умолчанию 60; 0 отключает кеш). Имена, новые офферы и изменения их активности появляются после обновления кеша, не позже TTL. Ошибки загрузки не кешируются.

`PUSH_LEASE_MINUTES` — срок отметки выполняющегося Push (по умолчанию 5 минут). Он должен быть больше четырёх HTTP-таймаутов: `PUSH_LEASE_MINUTES * 60 > 4 * KEITARO_TIMEOUT`. Перед PUT проверяется, что этот запас ещё остаётся; задержанный запрос без запаса прекращается до записи. Пока она жива, другой Push кампании, изменение публикуемого потока и Fetch получают 409 `push_in_progress`.

`CAMPAIGN_PREFIX` обязателен: с пустым значением или с плейсхолдером из `.env.example` бэкенд не стартует.

> **Стенд Keitaro общий.** Push разрешён только в кампании с вашим `CAMPAIGN_PREFIX` — бэкенд отклоняет остальные (403). Чужие кампании можно открывать и редактировать черновиком.

## 2. База данных

```powershell
docker compose up -d --wait
```

Postgres слушает `127.0.0.1:15433`, данные лежат в томе `pgdata`.

## 3. Бэкенд

```powershell
python -m venv backend\.venv
```

```powershell
backend\.venv\Scripts\python -m pip install -r backend\requirements-dev.txt
```

```powershell
cd backend; .venv\Scripts\python -m alembic upgrade head; cd ..
```

```powershell
backend\.venv\Scripts\python -m uvicorn app.main:app --app-dir backend --reload --port 8000
```

Swagger — http://127.0.0.1:8000/docs, проверка БД — http://127.0.0.1:8000/api/health.

## 4. Фронтенд

```powershell
npm --prefix frontend install
```

Разработка (бэкенд должен быть запущен — Vite проксирует `/api` на `127.0.0.1:8000`):

```powershell
npm --prefix frontend run dev
```

Открыть http://127.0.0.1:5173.

Сборка: собранную статику (`frontend/dist`) раздаёт сам FastAPI — после сборки всё приложение доступно на http://127.0.0.1:8000.

```powershell
npm --prefix frontend run build
```

## Тесты

Бэкенд — домен, сценарии, HTTP API на фейках, ACL Keitaro на заглушке HTTP. `.env` для тестов не нужен. Тесты хранения работают с настоящим Postgres из `docker compose` (отдельная БД `adrobot_test`); если он не запущен, они пропускаются.

```powershell
cd backend; .venv\Scripts\python -m pytest; cd ..
```

Для другой отдельной тестовой БД задайте `$env:TEST_DATABASE_URL = '<URL тестовой БД>'` перед pytest. Тесты не читают `.env`.

Фронтенд — Vitest: слой API-клиента, обработка ошибок, ключевые компоненты.

```powershell
npm --prefix frontend test
```

Проверка типов без сборки:

```powershell
npm --prefix frontend run typecheck
```

## Ревью в Codex

Навык `cr` находится в `.agents/skills/cr` и адаптирован из команды Claude Code.
В чате Codex: `$cr project lang:ru` — проверить весь текущий проект;
`$cr uncommitted lang:ru` — незакоммиченные изменения;
`$cr pr:main lang:ru` — изменения ветки относительно `main`.
Обычный запуск только сообщает замечания. Для исправлений явно укажите `fix`,
например `$cr fix uncommitted lang:ru`. Отчёты и журналы сохраняются локально
в `.codex/reviews/` и не попадают в git.

## Конкурентная правка

`CampaignView.version` — версия кампании. Команды редактора и Fetch принимают её в заголовке `If-Match`: если кампанию успели изменить в другой вкладке, ответ — 409 `concurrency_conflict`, и подтверждение (Cancel, Fetch с `discard_drafts`) не применится к черновику, которого пользователь не видел. Заголовок необязателен. Ответ `/draft` содержит `{version, changes}`, а ошибка Fetch с черновиком — `version` вместе с `changes`. Подтверждение отправляет именно версию показанного списка. Push использует короткий захват по версии, запросы Keitaro вне транзакции и короткую фиксацию результата. Соединение БД во время HTTP не удерживается; SELECT FOR UPDATE не используется. Отметка хранится в JSONB, миграция не требуется. Захват и снятие отметки повышают версию даже при ошибке Push: робот после ошибки перечитывает актуальное состояние.

Push делает четыре запроса: `GET /campaigns/{id}` (временная проверка названия на стенде), `GET /streams/{sid}`, `PUT /streams/{sid}`, повторный `GET /streams/{sid}` для сверки. Справочник офферов и список потоков кампании не запрашиваются. В боевой версии временную проверку имени можно убрать, оставив проверку по нашей БД: останется три запроса. Использование ответа PUT для сверки — отдельная возможная оптимизация после проверки на стенде; сейчас ответ PUT не считается подтверждением публикации.

## Структура

```
backend/app/
  domain/          агрегат «Кампания», веса, синхронизация с Keitaro — без БД и HTTP
  application/     сценарии: создаватор, редактор, порты (интерфейсы) к БД и Keitaro
  infrastructure/  Postgres (SQLAlchemy, Alembic), ACL к Keitaro (httpx)
  api/             FastAPI: роутеры, DTO, перевод ошибок в HTTP
  spa.py           раздача frontend/dist
frontend/src/
  shared/          HTTP-клиент, ApiError, общие компоненты
  offers/          автодополнение офферов
  creator/         создаватор
  editor/          список кампаний и редактор потоков
```
