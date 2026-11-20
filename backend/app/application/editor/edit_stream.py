"""Команды редактора (FR-2.6 – FR-2.10). Все локальные: в Keitaro ничего не уходит до Push.

Каждая — «загрузить агрегат -> команда корня -> сохранить». Правила живут в домене,
сценарий только задаёт границу транзакции.
"""

from collections.abc import Callable
from typing import TypeVar

from app.application.editor.loading import load_campaign
from app.application.offers.search_offers import find_offer
from app.application.ports import CampaignRepository, KeitaroGateway, UnitOfWork
from app.domain.campaigns import Campaign, DraftChange
from app.domain.common.ids import CampaignId, OfferId, StreamId

T = TypeVar("T")


def edit_campaign(
    repo: CampaignRepository, uow: UnitOfWork, campaign_id: CampaignId, command: Callable[[Campaign], T]
) -> tuple[Campaign, T]:
    campaign = load_campaign(repo, campaign_id)
    result = command(campaign)  # DomainError — до save: в БД ничего не меняется
    repo.save(campaign)
    uow.commit()
    return campaign, result


def add_offer(
    repo: CampaignRepository,
    keitaro: KeitaroGateway,
    uow: UnitOfWork,
    campaign_id: CampaignId,
    stream_id: StreamId,
    offer_id: OfferId,
) -> Campaign:
    offer = find_offer(keitaro, offer_id)
    campaign, _ = edit_campaign(repo, uow, campaign_id, lambda c: c.add_offer(stream_id, offer))
    return campaign


def remove_offer(
    repo: CampaignRepository, uow: UnitOfWork, campaign_id: CampaignId, stream_id: StreamId, offer_id: OfferId
) -> Campaign:
    return edit_campaign(repo, uow, campaign_id, lambda c: c.remove_offer(stream_id, offer_id))[0]


def bring_back(
    repo: CampaignRepository, uow: UnitOfWork, campaign_id: CampaignId, stream_id: StreamId, offer_id: OfferId
) -> Campaign:
    return edit_campaign(repo, uow, campaign_id, lambda c: c.bring_back(stream_id, offer_id))[0]


def pin(
    repo: CampaignRepository,
    uow: UnitOfWork,
    campaign_id: CampaignId,
    stream_id: StreamId,
    offer_id: OfferId,
    share: int | None = None,
) -> Campaign:
    return edit_campaign(repo, uow, campaign_id, lambda c: c.pin(stream_id, offer_id, share))[0]


def unpin(
    repo: CampaignRepository, uow: UnitOfWork, campaign_id: CampaignId, stream_id: StreamId, offer_id: OfferId
) -> Campaign:
    return edit_campaign(repo, uow, campaign_id, lambda c: c.unpin(stream_id, offer_id))[0]


def cancel_stream(
    repo: CampaignRepository, uow: UnitOfWork, campaign_id: CampaignId, stream_id: StreamId
) -> tuple[Campaign, list[DraftChange]]:
    """Возвращает отменённое — для сообщения «отменено: …». Подтверждение до вызова — по draft_changes()."""
    return edit_campaign(repo, uow, campaign_id, lambda c: c.cancel(stream_id))
