"""Перевод агрегата Campaign в строку БД и обратно."""

from typing import Any

from app.domain.campaigns import (
    Campaign,
    DesiredState,
    OfferAssignment,
    PublishedState,
    PushLease,
    Stream,
    StreamKind,
)
from app.domain.common.ids import CampaignId, OfferId, StreamId
from app.domain.offers.offer_ref import OfferRef
from app.infrastructure.persistence.documents import (
    AssignmentDoc,
    DesiredDoc,
    PublishedDoc,
    PushLeaseDoc,
    StreamDoc,
    StreamsDocument,
)
from app.infrastructure.persistence.records import CampaignRecord

# ---------- домен -> БД ----------


def fill_record(record: CampaignRecord, campaign: Campaign) -> None:
    """Переписывает строку состоянием агрегата. Документ всегда пишется целиком."""
    record.id = campaign.id
    record.name = campaign.name
    record.alias = campaign.alias
    record.domain_url = campaign.domain_url
    record.streams = _to_document(campaign)


def _to_document(campaign: Campaign) -> dict[str, Any]:
    lease = campaign.push_in_progress
    doc = StreamsDocument(
        streams=[_stream_doc(s) for s in campaign.streams],
        push_in_progress=None if lease is None else PushLeaseDoc(
            stream_id=lease.stream_id, started_at=lease.started_at, token=lease.token,
        ),
    )
    return doc.model_dump(mode="json")


def _stream_doc(s: Stream) -> StreamDoc:
    return StreamDoc(
        id=s.id,
        name=s.name,
        position=s.position,
        kind=s.kind.value,
        assignments=[_assignment_doc(a) for a in s.assignments],
    )


def _assignment_doc(a: OfferAssignment) -> AssignmentDoc:
    p = a.published
    return AssignmentDoc(
        offer_id=a.offer.id,
        offer_name=a.offer.name,
        order=a.order,
        desired=DesiredDoc(in_rotation=a.desired.in_rotation, share=a.desired.share, pinned=a.desired.pinned),
        published=None
        if p is None
        else PublishedDoc(in_rotation=p.in_rotation, share=p.share, pinned=p.pinned, pinned_share=p.pinned_share),
    )


# ---------- БД -> домен ----------


def to_domain(record: CampaignRecord) -> Campaign:
    doc = StreamsDocument.model_validate(record.streams)
    return Campaign(
        id=CampaignId(record.id),
        name=record.name,
        alias=record.alias,
        domain_url=record.domain_url,
        streams=[_stream(s) for s in doc.streams],
        version=record.version,
        push_in_progress=None if doc.push_in_progress is None else PushLease(
            StreamId(doc.push_in_progress.stream_id), doc.push_in_progress.started_at, doc.push_in_progress.token,
        ),
    )


def _stream(d: StreamDoc) -> Stream:
    return Stream(
        id=StreamId(d.id),
        name=d.name,
        position=d.position,
        kind=StreamKind(d.kind),
        assignments=[_assignment(a) for a in d.assignments],
    )


def _assignment(d: AssignmentDoc) -> OfferAssignment:
    p = d.published
    return OfferAssignment(
        offer=OfferRef(OfferId(d.offer_id), d.offer_name),
        order=d.order,
        desired=DesiredState(d.desired.in_rotation, d.desired.share, d.desired.pinned),
        published=None if p is None else PublishedState(p.in_rotation, p.share, p.pinned, p.pinned_share),
    )
