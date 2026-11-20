"""Fetch streams (FR-2.2, FR-2.3, FR-2.3a): подтянуть потоки из Keitaro в обёртку."""

from app.application.editor.loading import load_campaign
from app.application.editor.push_state import DEFAULT_LEASE_SECONDS, ensure_available
from app.application.ports import CampaignRepository, KeitaroGateway, UnitOfWork
from app.domain.campaigns import Campaign
from app.domain.campaigns.errors import CampaignHasDrafts
from app.domain.common.ids import CampaignId


def fetch_streams(
    repo: CampaignRepository,
    keitaro: KeitaroGateway,
    uow: UnitOfWork,
    campaign_id: CampaignId,
    *,
    discard_drafts: bool = False,
    expected_version: int | None = None,
    lease_seconds: float = DEFAULT_LEASE_SECONDS,
) -> Campaign:
    """При черновике без discard_drafts — CampaignHasDrafts, ничего не сохраняется.

    UI показывает подтверждение со списком (campaign.draft_changes()) и повторяет вызов
    с discard_drafts=True.
    """
    campaign = load_campaign(repo, campaign_id, expected_version)
    ensure_available(campaign, lease_seconds=lease_seconds)
    uow.rollback()  # закрыть чтение БД до сетевых запросов; агрегат — отдельная копия
    try:
        campaign.sync_from_keitaro(keitaro.get_campaign(campaign_id), discard_drafts=discard_drafts)
    except CampaignHasDrafts as error:
        error.version = campaign.version
        raise
    repo.save(campaign)
    uow.commit()
    return campaign
