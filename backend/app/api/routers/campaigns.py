"""Кампании: список, создаватор, открыть, Fetch streams.

Эндпоинты — обычные def: FastAPI выполняет их в пуле потоков, а синхронные
SQLAlchemy и httpx на время ожидания I/O отпускают GIL.
"""

from fastapi import APIRouter, status

from app.api.dependencies import Keitaro, Prefix, Repo, Uow
from app.api.presenters import campaign_view
from app.api.schemas import (
    CampaignSummaryDto,
    CampaignView,
    CreateCampaignRequest,
    ErrorResponse,
    FetchRequest,
    OpenCampaignResponse,
)
from app.application.creator.create_campaign import create_campaign
from app.application.editor.fetch_streams import fetch_streams
from app.application.editor.list_campaigns import list_campaigns
from app.application.editor.open_campaign import open_campaign
from app.domain.common.ids import CampaignId, OfferId

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


@router.get("")
def list_(repo: Repo, keitaro: Keitaro, prefix: Prefix, all: bool = False) -> list[CampaignSummaryDto]:
    """all=false — наши из БД обёртки (без Keitaro); all=true — все кампании стенда из Keitaro."""
    return [
        CampaignSummaryDto(id=c.id, name=c.name)
        for c in list_campaigns(repo, keitaro, prefix=prefix, only_ours=not all)
    ]


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    responses={422: {"model": ErrorResponse}, 502: {"model": ErrorResponse}},
)
def create(body: CreateCampaignRequest, repo: Repo, keitaro: Keitaro, uow: Uow, prefix: Prefix) -> CampaignView:
    campaign = create_campaign(
        repo, keitaro, uow, prefix=prefix, name=body.name, geos=body.geos, offer_id=OfferId(body.offer_id)
    )
    return campaign_view(campaign, prefix)


@router.get("/{campaign_id}", responses={404: {"model": ErrorResponse}})
def open_(campaign_id: int, repo: Repo, keitaro: Keitaro, uow: Uow, prefix: Prefix) -> OpenCampaignResponse:
    """Сверяет кампанию с Keitaro; при черновике не трогает её, а возвращает keitaro_changes."""
    opened = open_campaign(repo, keitaro, uow, CampaignId(campaign_id))
    return OpenCampaignResponse(campaign=campaign_view(opened.campaign, prefix), keitaro_changes=opened.keitaro_changes)


@router.post("/{campaign_id}/fetch", responses={409: {"model": ErrorResponse}})
def fetch(
    campaign_id: int, repo: Repo, keitaro: Keitaro, uow: Uow, prefix: Prefix, body: FetchRequest | None = None
) -> CampaignView:
    """409 campaign_has_drafts с полем changes — показать подтверждение и повторить с discard_drafts=true."""
    discard = body.discard_drafts if body else False
    return campaign_view(fetch_streams(repo, keitaro, uow, CampaignId(campaign_id), discard_drafts=discard), prefix)
