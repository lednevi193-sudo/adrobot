"""Загрузка агрегата для сценариев редактора."""

from app.application.errors import CampaignNotFound
from app.application.ports import CampaignRepository
from app.domain.campaigns import Campaign
from app.domain.common.ids import CampaignId


def load_campaign(repo: CampaignRepository, campaign_id: CampaignId) -> Campaign:
    """Кампания, уже открытая в обёртке. Ещё не открытую открывает open_campaign."""
    campaign = repo.get(campaign_id)
    if campaign is None:
        raise CampaignNotFound(campaign_id)
    return campaign
