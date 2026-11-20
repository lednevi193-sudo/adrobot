"""Редактор потока: команды над офферами, черновик, Cancel, Push (FR-2.6 – FR-2.14).

Каждая команда возвращает кампанию целиком — фронт перерисовывает то, что прислал сервер.
"""

from fastapi import APIRouter

from app.api.dependencies import Keitaro, Prefix, Repo, Uow
from app.api.presenters import campaign_view, change_dtos
from app.api.schemas import AddOfferRequest, CampaignView, CancelResponse, DraftChangeDto, ErrorResponse, PinRequest
from app.application.editor import edit_stream
from app.application.editor.loading import load_campaign
from app.application.editor.push_stream import push_stream
from app.domain.common.ids import CampaignId, OfferId, StreamId

router = APIRouter(prefix="/campaigns/{campaign_id}/streams/{stream_id}", tags=["streams"])

OFFER = "/offers/{offer_id}"


@router.get("/draft")
def draft(campaign_id: int, stream_id: int, repo: Repo) -> list[DraftChangeDto]:
    """Что отменит Cancel — для окна подтверждения (FR-2.10a)."""
    campaign = load_campaign(repo, CampaignId(campaign_id))
    return change_dtos(stream_id, campaign.stream(StreamId(stream_id)).draft_changes())


@router.post("/offers", responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}})
def add_offer(
    campaign_id: int, stream_id: int, body: AddOfferRequest, repo: Repo, keitaro: Keitaro, uow: Uow, prefix: Prefix
) -> CampaignView:
    campaign = edit_stream.add_offer(
        repo, keitaro, uow, CampaignId(campaign_id), StreamId(stream_id), OfferId(body.offer_id)
    )
    return campaign_view(campaign, prefix)


@router.delete(OFFER)
def remove_offer(campaign_id: int, stream_id: int, offer_id: int, repo: Repo, uow: Uow, prefix: Prefix) -> CampaignView:
    ids = CampaignId(campaign_id), StreamId(stream_id), OfferId(offer_id)
    return campaign_view(edit_stream.remove_offer(repo, uow, *ids), prefix)


@router.post(OFFER + "/bring-back")
def bring_back(campaign_id: int, stream_id: int, offer_id: int, repo: Repo, uow: Uow, prefix: Prefix) -> CampaignView:
    ids = CampaignId(campaign_id), StreamId(stream_id), OfferId(offer_id)
    return campaign_view(edit_stream.bring_back(repo, uow, *ids), prefix)


@router.put(OFFER + "/pin")
def pin(
    campaign_id: int, stream_id: int, offer_id: int, repo: Repo, uow: Uow, prefix: Prefix, body: PinRequest | None = None
) -> CampaignView:
    ids = CampaignId(campaign_id), StreamId(stream_id), OfferId(offer_id)
    return campaign_view(edit_stream.pin(repo, uow, *ids, body.share if body else None), prefix)


@router.delete(OFFER + "/pin")
def unpin(campaign_id: int, stream_id: int, offer_id: int, repo: Repo, uow: Uow, prefix: Prefix) -> CampaignView:
    ids = CampaignId(campaign_id), StreamId(stream_id), OfferId(offer_id)
    return campaign_view(edit_stream.unpin(repo, uow, *ids), prefix)


@router.post("/cancel")
def cancel(campaign_id: int, stream_id: int, repo: Repo, uow: Uow, prefix: Prefix) -> CancelResponse:
    campaign, cancelled = edit_stream.cancel_stream(repo, uow, CampaignId(campaign_id), StreamId(stream_id))
    return CancelResponse(campaign=campaign_view(campaign, prefix), cancelled=change_dtos(stream_id, cancelled))


@router.post(
    "/push",
    responses={403: {"model": ErrorResponse}, 422: {"model": ErrorResponse}, 502: {"model": ErrorResponse}},
)
def push(campaign_id: int, stream_id: int, repo: Repo, keitaro: Keitaro, uow: Uow, prefix: Prefix) -> CampaignView:
    campaign = push_stream(repo, keitaro, uow, CampaignId(campaign_id), StreamId(stream_id), prefix=prefix)
    return campaign_view(campaign, prefix)
