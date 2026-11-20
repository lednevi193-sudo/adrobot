"""Открыть кампанию в редакторе по ID (FR-2.1) и узнать, что поменяли прямо в Keitaro.

- Впервые — импорт из Keitaro.
- Уже в обёртке, без черновика — синхронизация с Keitaro (как Fetch); в БД пишем,
  только если в Keitaro что-то изменилось.
- С черновиком — синхронизировать нельзя, не потеряв его (FR-2.3a). Кампания
  остаётся как есть, а список изменений в Keitaro уходит пользователю: решит сам,
  делать ли Fetch.
"""

from dataclasses import dataclass, field

from app.application.editor.push_state import DEFAULT_LEASE_SECONDS, utc_now
from app.application.errors import CampaignAlreadyExists, CampaignNotFound
from app.application.ports import CampaignRepository, KeitaroGateway, UnitOfWork
from app.domain.campaigns import Campaign, changes_in_keitaro
from app.domain.common.ids import CampaignId


@dataclass(frozen=True, slots=True)
class OpenedCampaign:
    campaign: Campaign
    keitaro_changes: list[str] = field(default_factory=list)  # не пусто — есть черновик и правки в Keitaro


def open_campaign(
    repo: CampaignRepository, keitaro: KeitaroGateway, uow: UnitOfWork, campaign_id: CampaignId,
    *, lease_seconds: float = DEFAULT_LEASE_SECONDS,
) -> OpenedCampaign:
    campaign = repo.get(campaign_id)
    uow.rollback()  # чтение завершено до любых вызовов Keitaro
    if campaign is None:
        return OpenedCampaign(_import(repo, keitaro, uow, campaign_id))

    if campaign.push_in_progress and campaign.push_in_progress.is_live(utc_now(), lease_seconds):
        return OpenedCampaign(campaign)

    try:
        snapshot = keitaro.get_campaign(campaign_id)
    except CampaignNotFound:
        # в Keitaro удалили (перенесли в архив), а у нас она есть: показываем то, что знаем
        return OpenedCampaign(campaign, ["кампания удалена в Keitaro"])

    changes = changes_in_keitaro(campaign, snapshot)
    if not changes:
        return OpenedCampaign(campaign)
    if campaign.draft_changes():  # не has_draft: расхождение закреплённого веса черновиком не считается
        return OpenedCampaign(campaign, changes)

    campaign.push_in_progress = None
    campaign.sync_from_keitaro(snapshot)
    repo.save(campaign)
    uow.commit()
    return OpenedCampaign(campaign)


def _import(repo: CampaignRepository, keitaro: KeitaroGateway, uow: UnitOfWork, campaign_id: CampaignId) -> Campaign:
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
