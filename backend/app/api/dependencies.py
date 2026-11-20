"""Композиция зависимостей для эндпоинтов (≈ регистрация сервисов в Program.cs).

FastAPI кеширует зависимость в пределах запроса: get_db вызывается один раз, и
репозиторий с UnitOfWork получают одну и ту же Session (≈ scoped DbContext).
В тестах любую из функций подменяют через app.dependency_overrides.
"""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.application.ports import CampaignRepository, KeitaroGateway, UnitOfWork
from app.config import get_settings
from app.infrastructure.db import get_db
from app.infrastructure.keitaro import build_keitaro_gateway
from app.infrastructure.persistence.campaign_repository import SqlCampaignRepository


def get_repository(db: Annotated[Session, Depends(get_db)]) -> CampaignRepository:
    return SqlCampaignRepository(db)


def get_unit_of_work(db: Annotated[Session, Depends(get_db)]) -> UnitOfWork:
    return db  # Session и есть Unit of Work


@lru_cache
def get_keitaro() -> KeitaroGateway:
    """Один шлюз на процесс: внутри httpx.Client с пулом соединений (≈ singleton HttpClient)."""
    return build_keitaro_gateway(get_settings())


def get_prefix() -> str:
    return get_settings().campaign_prefix


Repo = Annotated[CampaignRepository, Depends(get_repository)]
Uow = Annotated[UnitOfWork, Depends(get_unit_of_work)]
Keitaro = Annotated[KeitaroGateway, Depends(get_keitaro)]
Prefix = Annotated[str, Depends(get_prefix)]
