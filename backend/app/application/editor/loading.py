"""Загрузка агрегата для сценариев редактора."""

from app.application.errors import CampaignNotFound, ConcurrencyConflict
from app.application.ports import CampaignRepository
from app.domain.campaigns import Campaign
from app.domain.common.ids import CampaignId


def load_campaign(
    repo: CampaignRepository,
    campaign_id: CampaignId,
    expected_version: int | None = None,
) -> Campaign:
    """Кампания, уже открытая в обёртке. Ещё не открытую открывает open_campaign.

    expected_version — версия, которую видел пользователь (If-Match). Не совпала —
    кампанию успели изменить в другой вкладке: команда применилась бы не к тому,
    что пользователь подтверждал (FR-2.3a, FR-2.10a), поэтому ConcurrencyConflict.
    """
    campaign = repo.get(campaign_id)
    if campaign is None:
        raise CampaignNotFound(campaign_id)
    if expected_version is not None and expected_version != campaign.version:
        raise ConcurrencyConflict(campaign_id)
    return campaign
