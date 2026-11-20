"""FakeKeitaroGateway — Keitaro в памяти для тестов сценариев приложения.

Ведёт себя как стенд на уровне порта: выдаёт ID, хранит потоки и раздачу офферов,
умеет «упасть» на нужном методе (fail_on) — для проверки компенсации FR-1.6.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field, replace
from itertools import count

from app.application.errors import CampaignNotFound, KeitaroError
from app.application.ports import CampaignSummary
from app.domain.campaigns import (
    GeoRedirectStreamSpec,
    KeitaroCampaign,
    KeitaroStream,
    OffersStreamSpec,
    PublishedOffer,
)
from app.domain.common.ids import CampaignId, StreamId
from app.domain.offers.offer_ref import OfferRef

DOMAIN_URL = "https://kylovoa.com/"


@dataclass
class FakeKeitaroGateway:
    offers: list[OfferRef] = field(default_factory=list)
    fail_on: set[str] = field(default_factory=set)
    campaigns: dict[CampaignId, KeitaroCampaign] = field(default_factory=dict)
    archived: set[CampaignId] = field(default_factory=set)
    calls: list[str] = field(default_factory=list)
    _ids: Iterable[int] = field(default_factory=lambda: count(1000))

    # ---------- чтение ----------

    def list_campaigns(self) -> list[CampaignSummary]:
        self._call("list_campaigns")
        return [CampaignSummary(c.id, c.name) for c in self.campaigns.values()]

    def get_campaign(self, campaign_id: CampaignId) -> KeitaroCampaign:
        self._call("get_campaign")
        if campaign_id not in self.campaigns:
            raise CampaignNotFound(campaign_id)
        return self.campaigns[campaign_id]

    def list_active_offers(self) -> list[OfferRef]:
        self._call("list_active_offers")
        return list(self.offers)

    # ---------- создаватор ----------

    def create_campaign(self, name: str) -> CampaignId:
        self._call("create_campaign")
        cid = CampaignId(next(self._ids))
        self.campaigns[cid] = KeitaroCampaign(cid, name, f"alias{cid}", DOMAIN_URL)
        return cid

    def create_geo_stream(self, campaign_id: CampaignId, spec: GeoRedirectStreamSpec) -> None:
        self._call("create_geo_stream")
        self._add_stream(campaign_id, KeitaroStream(StreamId(next(self._ids)), spec.name, spec.position))

    def create_offers_stream(self, campaign_id: CampaignId, spec: OffersStreamSpec) -> None:
        self._call("create_offers_stream")
        offers = (PublishedOffer(spec.offer, spec.share),)
        self._add_stream(campaign_id, KeitaroStream(StreamId(next(self._ids)), spec.name, spec.position, offers))

    def delete_campaign(self, campaign_id: CampaignId) -> None:
        self._call("delete_campaign")
        self.campaigns.pop(campaign_id, None)
        self.archived.add(campaign_id)

    # ---------- редактор ----------

    def publish_offers(self, stream_id: StreamId, offers: Sequence[PublishedOffer]) -> None:
        self._call("publish_offers")
        self.edit_stream(stream_id, offers)

    # ---------- для тестов: «правка руками в админке Keitaro» ----------

    def edit_stream(self, stream_id: StreamId, offers: Sequence[PublishedOffer]) -> None:
        for cid, c in self.campaigns.items():
            if any(s.id == stream_id for s in c.streams):
                streams = tuple(replace(s, offers=tuple(offers)) if s.id == stream_id else s for s in c.streams)
                self.campaigns[cid] = replace(c, streams=streams)
                return
        raise KeitaroError(f"Поток {stream_id} не найден", status=404)

    # ---------- внутреннее ----------

    def _add_stream(self, campaign_id: CampaignId, stream: KeitaroStream) -> None:
        c = self.campaigns[campaign_id]
        streams = sorted((*c.streams, stream), key=lambda s: s.position)
        self.campaigns[campaign_id] = replace(c, streams=tuple(streams))

    def _call(self, method: str) -> None:
        self.calls.append(method)
        if method in self.fail_on:
            raise KeitaroError(f"Keitaro отклонил {method} (фейк)", status=500)
