"""JSON Keitaro -> снимки домена. Здесь решается, что из Keitaro считается «опубликованным»."""

from collections.abc import Mapping

from app.application.ports import CampaignSummary
from app.domain.campaigns import KeitaroCampaign, KeitaroStream, PublishedOffer
from app.domain.common.ids import CampaignId, OfferId, StreamId
from app.domain.offers.offer_ref import OfferRef
from app.infrastructure.keitaro.schemas import (
    ACTIVE,
    DELETED,
    KeitaroCampaignJson,
    KeitaroOfferJson,
    KeitaroStreamJson,
)

OfferNames = Mapping[int, str]


def campaign_summary(c: KeitaroCampaignJson) -> CampaignSummary:
    return CampaignSummary(CampaignId(c.id), c.name)


def campaign_snapshot(
    c: KeitaroCampaignJson, streams: list[KeitaroStreamJson], offer_names: OfferNames
) -> KeitaroCampaign:
    """Поток в архиве Keitaro (state = deleted) для обёртки не существует."""
    live = [s for s in streams if s.state != DELETED]
    return KeitaroCampaign(
        id=CampaignId(c.id),
        name=c.name,
        alias=c.alias,
        domain_url=c.domain,
        streams=tuple(stream_snapshot(s, offer_names) for s in sorted(live, key=lambda s: s.position)),
    )


def stream_snapshot(s: KeitaroStreamJson, offer_names: OfferNames) -> KeitaroStream:
    """В раздаче только офферы с state = active: выключенный в Keitaro оффер трафик не получает.

    Имя берётся из справочника офферов; оффера, скрытого от ключа API (Q6), там нет —
    тогда имя пустое, и UI показывает только [id].
    """
    offers = tuple(
        PublishedOffer(OfferRef(OfferId(o.offer_id), offer_names.get(o.offer_id, "")), o.share)
        for o in s.offers
        if o.state == ACTIVE
    )
    return KeitaroStream(StreamId(s.id), s.name, s.position, offers)


def offer_ref(o: KeitaroOfferJson) -> OfferRef:
    return OfferRef(OfferId(o.id), o.name)
