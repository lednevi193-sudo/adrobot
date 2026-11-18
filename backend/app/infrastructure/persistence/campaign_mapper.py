"""Перевод агрегата Campaign в строку БД и обратно."""

from typing import Any

from app.domain.campaigns import (
    Campaign,
    DesiredState,
    OfferAssignment,
    PublishedState,
    Stream,
    StreamKind,
)
from app.domain.common.ids import CampaignId, OfferId, StreamId
from app.domain.offers.offer_ref import OfferRef
from app.infrastructure.persistence.documents import (
    AssignmentDoc,
    DesiredDoc,
    PublishedDoc,
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
    record.created_by_us = campaign.created_by_us
    record.streams = _to_document(campaign)


def _to_document(campaign: Campaign) -> dict[str, Any]:
    doc = StreamsDocument(streams=[_stream_doc(s) for s in campaign.streams])
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
        seq=a.seq,
        desired=DesiredDoc(included=a.desired.included, share=a.desired.share, pinned=a.desired.pinned),
        published=None if p is None else PublishedDoc(present=p.present, share=p.share, pinned=p.pinned),
    )


# ---------- БД -> домен ----------


def to_domain(record: CampaignRecord) -> Campaign:
    doc = StreamsDocument.model_validate(record.streams)
    return Campaign(
        id=CampaignId(record.id),
        name=record.name,
        alias=record.alias,
        domain_url=record.domain_url,
        created_by_us=record.created_by_us,
        streams=[_stream(s) for s in doc.streams],
        version=record.version,
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
        seq=d.seq,
        desired=DesiredState(d.desired.included, d.desired.share, d.desired.pinned),
        published=None if p is None else PublishedState(p.present, p.share, p.pinned),
    )
