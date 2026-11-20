"""Открыть кампанию в редакторе по ID (FR-2.1): из нашей БД, а впервые — из Keitaro."""

from app.application.errors import CampaignAlreadyExists
from app.application.ports import CampaignRepository, KeitaroGateway, UnitOfWork
from app.domain.campaigns import Campaign
from app.domain.common.ids import CampaignId


def open_campaign(
    repo: CampaignRepository, keitaro: KeitaroGateway, uow: UnitOfWork, campaign_id: CampaignId
) -> Campaign:
    campaign = repo.get(campaign_id)
    if campaign is not None:
        return campaign  # черновики живут у нас — Keitaro не трогаем, обновление — через Fetch

    campaign = Campaign.from_keitaro(keitaro.get_campaign(campaign_id))  # CampaignNotFound, если нет и там
    try:
        repo.add(campaign)
        uow.commit()
    except CampaignAlreadyExists:
        # параллельный запрос открыл её раньше нас — берём его версию
        uow.rollback()
        existing = repo.get(campaign_id)
        assert existing is not None
        return existing
    return campaign
