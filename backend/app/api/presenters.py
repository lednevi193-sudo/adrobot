"""Агрегат -> DTO для фронта. Производные поля (push_blocker, keitaro_share) считает домен."""

from collections.abc import Iterable

from app.api.schemas import (
    CampaignView,
    DraftChangeDto,
    OfferDto,
    StreamOfferView,
    StreamView,
)
from app.domain.campaigns import Campaign, DraftChange, OfferAssignment, Stream, StreamKind
from app.domain.common.errors import DomainError
from app.domain.offers.offer_ref import OfferRef


def campaign_view(c: Campaign, prefix: str) -> CampaignView:
    return CampaignView(
        id=c.id,
        name=c.name,
        alias=c.alias,
        tracker_url=c.tracker_url,
        is_ours=c.is_ours(prefix),
        has_draft=c.has_draft,
        version=c.version,
        streams=[stream_view(s) for s in c.streams],
    )


def stream_view(s: Stream) -> StreamView:
    editable = s.kind is StreamKind.OFFERS
    return StreamView(
        id=s.id,
        name=s.name,
        position=s.position,
        editable=editable,
        has_draft=s.has_draft,
        can_cancel=editable and bool(s.draft_changes()),
        push_blocker=_push_blocker(s) if editable else None,
        offers=[assignment_view(a) for a in sorted(s.assignments, key=lambda a: a.order)],
    )


def assignment_view(a: OfferAssignment) -> StreamOfferView:
    return StreamOfferView(
        id=a.offer.id,
        name=a.offer.name,
        status=a.status.value,
        share=a.desired.share,
        pinned=a.desired.pinned,
        keitaro_share=a.published.share if a.is_published and a.published else None,
    )


def offer_dto(o: OfferRef) -> OfferDto:
    return OfferDto(id=o.id, name=o.name)


def change_dtos(stream_id: int, changes: Iterable[DraftChange]) -> list[DraftChangeDto]:
    return [
        DraftChangeDto(
            stream_id=stream_id,
            offer=offer_dto(c.offer),
            kind=c.kind.value,
            share_before=c.share_before,
            share_after=c.share_after,
        )
        for c in changes
    ]


def _push_blocker(s: Stream) -> str | None:
    """Те же проверки, что делает Push (FR-2.12), — фронт не дублирует правила."""
    try:
        s.offers_to_publish()
    except DomainError as e:
        return e.message
    return None
