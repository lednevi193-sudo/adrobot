"""Объекты домена -> тела запросов Keitaro. Все «магические» значения Keitaro — только здесь.

Схема потоков создаватора (FR-1.4, FR-1.5):
  гео-поток    type=forced  (перехватывает раньше остальных), schema=redirect, фильтр country/accept
  поток офферов type=regular, schema=landings (офферы без лендингов), раздача offers[]
"""

from collections.abc import Sequence
from dataclasses import dataclass

from app.domain.campaigns import GeoRedirectStreamSpec, OffersStreamSpec, PublishedOffer
from app.domain.common.ids import CampaignId


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


def stream_offers_body(offers: Sequence[PublishedOffer]) -> dict:
    """PUT /streams/{id} меняет только переданные поля (документация Keitaro)."""
    return {"offers": offers_payload(offers)}


def offers_payload(offers: Sequence[PublishedOffer]) -> list[dict]:
    return [{"offer_id": o.offer.id, "share": o.share, "state": "active"} for o in offers]
