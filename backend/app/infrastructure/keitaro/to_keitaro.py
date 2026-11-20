"""Объекты домена -> тела запросов Keitaro. Все «магические» значения Keitaro — только здесь.

Схема потоков создаватора (FR-1.4, FR-1.5):
  гео-поток    type=forced  (перехватывает раньше остальных), schema=redirect, фильтр country/accept
  поток офферов type=regular, schema=landings (офферы без лендингов), раздача offers[]
"""

from collections.abc import Sequence
from dataclasses import dataclass

from app.domain.campaigns import GeoRedirectStreamSpec, OffersStreamSpec, PublishedOffer
from app.domain.common.ids import CampaignId
from app.infrastructure.keitaro.schemas import ACTIVE, KeitaroStreamOfferJson


@dataclass(frozen=True, slots=True)
class CampaignPlacement:
    """Куда Keitaro кладёт новые кампании: домен, группа, источник трафика (FR-1.3, .env)."""

    domain_id: int
    group_id: int
    traffic_source_id: int


def campaign_body(name: str, alias: str, placement: CampaignPlacement) -> dict:
    return {
        "name": name,
        "alias": alias,  # обязателен в Keitaro: это путь в ссылке трекера
        "type": "position",  # потоки проверяются по позиции сверху вниз
        "state": "active",
        "domain_id": placement.domain_id,
        "group_id": placement.group_id,
        "traffic_source_id": placement.traffic_source_id,
    }


def geo_stream_body(campaign_id: CampaignId, spec: GeoRedirectStreamSpec) -> dict:
    return {
        "campaign_id": campaign_id,
        "name": spec.name,
        "position": spec.position,
        "type": "forced",
        "schema": "redirect",
        "action_type": "http",
        "action_payload": spec.redirect_url,
        "state": "active",
        "filters": [{"name": "country", "mode": "accept", "payload": [str(g) for g in spec.countries]}],
    }


def offers_stream_body(campaign_id: CampaignId, spec: OffersStreamSpec) -> dict:
    return {
        "campaign_id": campaign_id,
        "name": spec.name,
        "position": spec.position,
        "type": "regular",
        "schema": "landings",
        "action_type": "http",
        "state": "active",
        "offers": offers_payload([PublishedOffer(spec.offer, spec.share)]),
    }


def stream_offers_body(
    offers: Sequence[PublishedOffer], current: Sequence[KeitaroStreamOfferJson] = ()
) -> dict:
    """PUT /streams/{id} меняет только переданные поля (документация Keitaro), но offers[] — целиком.

    current — то, что сейчас лежит в потоке Keitaro: неактивные офферы оттуда сохраняются
    с исходными state и share. Если такой оффер есть среди публикуемых, побеждает публикуемый.
    """
    sent = {o.offer.id for o in offers}
    kept = [
        {"offer_id": o.offer_id, "share": o.share, "state": o.state}
        for o in current
        if o.state != ACTIVE and o.offer_id not in sent
    ]
    return {"offers": offers_payload(offers) + kept}


def offers_payload(offers: Sequence[PublishedOffer]) -> list[dict]:
    return [{"offer_id": o.offer.id, "share": o.share, "state": ACTIVE} for o in offers]
