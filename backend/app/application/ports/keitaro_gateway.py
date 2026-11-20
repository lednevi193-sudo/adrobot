"""Порт к Keitaro — то, что сценариям нужно от внешней системы, на языке домена.

Реализация (ACL) живёт в infrastructure/keitaro: она знает про HTTP, JSON Keitaro,
`schema: redirect`, `type: forced` и ID домена/группы/источника из настроек.
Сценарии про это не знают — как код за `IKeitaroApi`, не видящий HttpClient.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from app.domain.campaigns import (
    GeoRedirectStreamSpec,
    KeitaroCampaign,
    OffersStreamSpec,
    PublishedOffer,
)
from app.domain.common.ids import CampaignId, StreamId
from app.domain.offers.offer_ref import OfferRef


@dataclass(frozen=True, slots=True)
class CampaignSummary:
    """Строка списка кампаний в редакторе (FR-2.1) — без потоков."""

    id: CampaignId
    name: str


class KeitaroGateway(Protocol):
    """Все методы при сбое Keitaro бросают KeitaroError (или KeitaroUnavailable)."""

    # ---------- чтение ----------

    def list_campaigns(self) -> Sequence[CampaignSummary]:
        """Все кампании Keitaro, какие видит ключ."""
        ...

    def get_campaign(self, campaign_id: CampaignId) -> KeitaroCampaign:
        """Кампания с потоками и офферами в них. CampaignNotFound, если в Keitaro её нет."""
        ...

    def list_active_offers(self) -> Sequence[OfferRef]:
        """Офферы справочника, которые можно ставить в поток (state = active)."""
        ...

    # ---------- создаватор ----------

    def create_campaign(self, name: str) -> CampaignId:
        """Пустая кампания с доменом, группой и источником из настроек (FR-1.3)."""
        ...

    def create_geo_stream(self, campaign_id: CampaignId, spec: GeoRedirectStreamSpec) -> None:
        """Поток «страны → редирект» (FR-1.4)."""
        ...

    def create_offers_stream(self, campaign_id: CampaignId, spec: OffersStreamSpec) -> None:
        """Поток с офферами (FR-1.5)."""
        ...

    def delete_campaign(self, campaign_id: CampaignId) -> None:
        """Убрать кампанию — компенсация неудачного создания (FR-1.6). В Keitaro это перенос в архив."""
        ...

    # ---------- редактор ----------

    def publish_offers(self, stream_id: StreamId, offers: Sequence[PublishedOffer]) -> None:
        """Push: заменить раздачу потока в Keitaro этим списком офферов с весами (FR-2.13)."""
        ...
