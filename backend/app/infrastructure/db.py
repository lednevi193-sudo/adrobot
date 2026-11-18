"""Подключение к БД: engine (пул соединений) и фабрика сессий."""

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

engine = create_engine(get_settings().database_url, pool_pre_ping=True)

# expire_on_commit=False: после commit объекты остаются читаемыми без повторного запроса в БД.
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """Зависимость FastAPI: одна сессия на запрос, закрывается в конце запроса."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
