"""Подключение к БД: engine (пул соединений), фабрика сессий и базовый класс моделей."""

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

engine = create_engine(get_settings().database_url, pool_pre_ping=True)

# expire_on_commit=False: после commit объекты остаются читаемыми без повторного запроса в БД.
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    """Базовый класс для всех ORM-моделей."""


def get_db() -> Iterator[Session]:
    """Зависимость FastAPI: одна сессия на запрос, закрывается в конце запроса."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
