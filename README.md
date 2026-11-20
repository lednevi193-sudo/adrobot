# Adrobot — обёртка над Keitaro

Создаватор кампаний и редактор потоков с офферами поверх Keitaro Admin API.
Что и зачем — [docs/requirements.md](docs/requirements.md), как устроено — [docs/domain-model.md](docs/domain-model.md).

**Статус:** готов backend (FastAPI, HTTP API). Фронтенд (Vue 3 + Vite, NFR-1) ещё не начат — пока работа идёт через Swagger.

## Требования

- Python ≥ 3.12
- Docker (локальный Postgres)

## Запуск

Из корня репозитория:

```bash
cp .env.example .env        # заполнить KEITARO_API_KEY и CAMPAIGN_PREFIX
docker compose up -d --wait # Postgres на 127.0.0.1:15433
```

Дальше — из `backend/` (там `alembic.ini` и `pyproject.toml`; `.env` читается из корня репозитория):

```bash
cd backend
python -m venv .venv
.venv/Scripts/pip install -r requirements-dev.txt   # Linux/macOS: .venv/bin/pip
.venv/Scripts/alembic upgrade head
.venv/Scripts/uvicorn app.main:app --reload
```

- Swagger: http://localhost:8000/docs
- Проверка: http://localhost:8000/api/health

`CAMPAIGN_PREFIX` обязателен: стенд Keitaro общий, обёртка показывает и публикует только кампании со своим префиксом.
Без него (или с плейсхолдером из `.env.example`) приложение не стартует.

## Тесты

```bash
cd backend
.venv/Scripts/pytest
```

- `.env` для тестов не нужен: настройки подменяются в `tests/conftest.py`.
- Интеграционные тесты хранения (`tests/infrastructure`) идут на БД `adrobot_test` в Postgres из docker compose
  (создаётся автоматически, адрес — `TEST_DATABASE_URL`). Если Postgres не запущен, они пропускаются (skip).
- Остальные тесты работают на фейках портов, без сети и БД.

## Конкурентная правка

`CampaignView.version` — версия кампании. Команды редактора и Fetch принимают её в заголовке `If-Match`:
если кампанию успели изменить в другой вкладке, ответ — 409 `concurrency_conflict`, и подтверждение
(Cancel, Fetch с `discard_drafts`) не применится к черновику, которого пользователь не видел.
