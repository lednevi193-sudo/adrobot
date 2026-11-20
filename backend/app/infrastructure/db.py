"""Подключение к БД: engine (пул соединений) и фабрика сессий.

Создаются лениво, при первом запросе: импорт приложения (и тесты на фейках)
не требует настроек БД.
"""

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings


@lru_cache
def get_engine() -> Engine:
    return create_engine(get_settings().database_url, pool_pre_ping=True)


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    # expire_on_commit=False: после commit объекты остаются читаемыми без повторного запроса в БД.
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """Зависимость FastAPI: одна сессия на запрос, закрывается в конце запроса."""
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()
