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

## 1. Настройки

```powershell
Copy-Item .env.example .env
```

В `.env` заполните `KEITARO_API_KEY` и `CAMPAIGN_PREFIX` (например, `test_ivanov_`). Остальное уже настроено на стенд и локальный Postgres. Файл `.env` в git не попадает.

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

Фронтенд — Vitest: слой API-клиента, обработка ошибок, ключевые компоненты.

```powershell
npm --prefix frontend test
```

Проверка типов без сборки:

```powershell
npm --prefix frontend run typecheck
```

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
