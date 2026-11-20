"""Реализация порта CampaignRepository на SQLAlchemy + Postgres.

Репозиторий только читает и пишет агрегат; commit делает сценарий приложения
(Session — это Unit of Work, граница транзакции — сценарий, а не репозиторий).
Откат после ошибки — тоже дело сценария: репозиторий только переводит ошибки БД в ошибки приложения.
"""

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.application.errors import CampaignAlreadyExists, CampaignNotFound, ConcurrencyConflict
from app.domain.campaigns import Campaign
from app.domain.common.ids import CampaignId
from app.infrastructure.persistence.campaign_mapper import fill_record, to_domain
from app.infrastructure.persistence.records import CampaignRecord


class SqlCampaignRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, campaign_id: CampaignId) -> Campaign | None:
        record = self._session.get(CampaignRecord, campaign_id, populate_existing=True)
        return None if record is None else to_domain(record)

    def list(self) -> Sequence[Campaign]:
        records = self._session.scalars(select(CampaignRecord).order_by(CampaignRecord.id.desc()))
        return [to_domain(r) for r in records]

    def add(self, campaign: Campaign) -> None:
        record = CampaignRecord()
        fill_record(record, campaign)
        self._session.add(record)
        try:
            self._session.flush()  # INSERT сейчас, чтобы ошибку получить здесь, а не на commit
        except IntegrityError as e:
            raise CampaignAlreadyExists(campaign.id) from e
        campaign.version = record.version

    def save(self, campaign: Campaign) -> None:
        # В пределах сессии get() вернёт ту же строку из identity map (≈ отслеживание в DbContext)
        record = self._session.get(CampaignRecord, campaign.id)
        if record is None:
            raise CampaignNotFound(campaign.id)
        if record.version != campaign.version:
            raise ConcurrencyConflict(campaign.id)  # агрегат прочитан раньше последней записи

        fill_record(record, campaign)
        try:
            self._session.flush()  # UPDATE ... WHERE id = :id AND version = :прочитанная
        except StaleDataError as e:
            raise ConcurrencyConflict(campaign.id) from e
        campaign.version = record.version
