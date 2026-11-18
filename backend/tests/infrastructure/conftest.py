"""Интеграционные тесты хранения: настоящий Postgres из docker-compose, отдельная БД adrobot_test.

Схема создаётся теми же миграциями Alembic, что и в dev/prod, — заодно проверяются миграции.
Если Postgres не запущен, тесты этого пакета пропускаются (skip), а не падают.
"""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://adrobot:adrobot@127.0.0.1:15433/adrobot_test"
)
BACKEND_DIR = Path(__file__).resolve().parents[2]


def _ensure_database(url: str) -> None:
    """CREATE DATABASE, если её нет (подключаемся к служебной БД postgres)."""
    target = make_url(url)
    admin = create_engine(target.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            exists = conn.scalar(text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": target.database})
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{target.database}"'))
    finally:
        admin.dispose()


def _migrate(url: str) -> None:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    cfg.set_main_option("sqlalchemy.url", url)
    cfg.attributes["configure_logger"] = False  # не перенастраивать логирование pytest
    command.upgrade(cfg, "head")


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    try:
        _ensure_database(TEST_DATABASE_URL)
    except OperationalError as e:
        pytest.skip(f"Postgres недоступен ({TEST_DATABASE_URL}): запустите docker compose up -d. {e.orig}")
    _migrate(TEST_DATABASE_URL)
    eng = create_engine(TEST_DATABASE_URL)
    yield eng
    eng.dispose()


@pytest.fixture
def session_factory(engine: Engine) -> Iterator[sessionmaker[Session]]:
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE campaigns"))  # каждый тест — с чистой таблицы
    yield sessionmaker(bind=engine, expire_on_commit=False)
