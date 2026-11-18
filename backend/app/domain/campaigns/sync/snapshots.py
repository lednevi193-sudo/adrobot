"""Снимки состояния Keitaro — неизменяемые входные данные для синхронизации.

Их собирает ACL (KeitaroGateway) из JSON Keitaro; домен не знает формата API.
"""

from dataclasses import dataclass

from app.domain.common.ids import CampaignId, StreamId
from app.domain.offers.offer_ref import OfferRef


@dataclass(frozen=True, slots=True)
class PublishedOffer:
    """Оффер с весом в том виде, в каком он лежит (или ляжет) в Keitaro."""

    offer: OfferRef
    share: int


@dataclass(frozen=True, slots=True)
class KeitaroStream:
    id: StreamId
    name: str
    position: int
    offers: tuple[PublishedOffer, ...] = ()


@dataclass(frozen=True, slots=True)
class KeitaroCampaign:
    id: CampaignId
    name: str
    alias: str
    domain_url: str | None
    streams: tuple[KeitaroStream, ...] = ()
