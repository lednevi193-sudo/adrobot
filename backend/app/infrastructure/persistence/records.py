"""Модели хранения (records) — форма строк в БД, а не доменные объекты.

Домен про них не знает; переводом строка <-> агрегат занимается campaign_mapper.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.persistence.base import Base


class CampaignRecord(Base):
    """Агрегат «Кампания» целиком: данные кампании в колонках, потоки — JSONB-документом."""

    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)  # ID в Keitaro
    name: Mapped[str] = mapped_column(String(255))
    alias: Mapped[str] = mapped_column(String(255))
    domain_url: Mapped[str | None] = mapped_column(String(255))
    streams: Mapped[dict[str, Any]] = mapped_column(JSONB)
    version: Mapped[int] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Оптимистическая блокировка (≈ RowVersion): каждый UPDATE идёт с условием
    # WHERE version = <прочитанная>, а version увеличивается на 1.
    __mapper_args__ = {"version_id_col": version}
