"""Порт хранилища агрегатов «Кампания».

Protocol — структурная типизация: реализация не наследуется от порта и не пишет
«: ICampaignRepository», ей достаточно иметь такие же методы (утиная типизация,
проверяемая тайпчекером).
"""

from collections.abc import Sequence
from typing import Protocol

from app.domain.campaigns import Campaign
from app.domain.common.ids import CampaignId


class CampaignRepository(Protocol):
    def get(self, campaign_id: CampaignId) -> Campaign | None:
        """Агрегат целиком или None."""
        ...

    def list(self) -> Sequence[Campaign]:
        """Все кампании, новые первыми."""
        ...

    def add(self, campaign: Campaign) -> None:
        """Новый агрегат. CampaignAlreadyExists, если такой ID уже есть."""
        ...

    def save(self, campaign: Campaign) -> None:
        """Изменённый агрегат. ConcurrencyConflict, если его успели изменить параллельно."""
        ...
