"""Изолированный демостенд: реальный HTTP API и домен, хранилище и Keitaro в памяти.

Запуск: python -m uvicorn app.demo:create_demo_app --factory --app-dir backend --port 8001
Один процесс; после перезапуска восстанавливаются исходные кампании.
"""

from collections.abc import Iterator, Sequence
from copy import deepcopy
from dataclasses import dataclass, field, replace
from itertools import count
from threading import Lock
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, FastAPI
from pydantic import BaseModel, Field, model_validator

from app.api.dependencies import get_keitaro, get_prefix, get_repository, get_unit_of_work, get_push_lease_seconds, get_keitaro_timeout
from app.application.errors import CampaignAlreadyExists, CampaignNotFound, ConcurrencyConflict, KeitaroError
from app.application.ports import CampaignSummary, InactiveStreamOffer, KeitaroStreamState
from app.domain.campaigns.errors import StreamNotInCampaign
from app.domain.campaigns import Campaign, GeoRedirectStreamSpec, KeitaroCampaign, KeitaroStream, OffersStreamSpec, PublishedOffer
from app.domain.common.ids import CampaignId, OfferId, StreamId
from app.domain.offers.offer_ref import OfferRef
from app.main import create_app

PREFIX = "demo_"
OFFERS = tuple(OfferRef(OfferId(i), name) for i, name in (
    (101, "Demo — оффер A"), (102, "Demo — оффер B"), (103, "Demo — оффер C"),
))


class DemoKeitaro:
    """Реализация порта без HTTP и реальных ключей; отдельное опубликованное состояние."""

    def __init__(self) -> None:
        self.campaigns: dict[CampaignId, KeitaroCampaign] = {}
        self.disabled_offers: dict[StreamId, set[OfferId]] = {}
        self._campaign_ids = count(100)
        self._stream_ids = count(1000)

    def list_campaigns(self) -> list[CampaignSummary]:
        return [CampaignSummary(c.id, c.name) for c in self.campaigns.values()]

    def get_campaign(self, campaign_id: CampaignId) -> KeitaroCampaign:
        if campaign_id not in self.campaigns:
            raise CampaignNotFound(campaign_id)
        campaign = self.campaigns[campaign_id]
        return replace(campaign, streams=tuple(
            replace(s, offers=tuple(o for o in s.offers if o.offer.id not in self.disabled_offers.get(s.id, set())))
            for s in campaign.streams
        ))

    def list_active_offers(self) -> Sequence[OfferRef]:
        return OFFERS

    def get_campaign_name(self, campaign_id: CampaignId) -> str:
        if campaign_id not in self.campaigns:
            raise CampaignNotFound(campaign_id)
        return self.campaigns[campaign_id].name

    def get_stream(self, stream_id: StreamId) -> KeitaroStreamState:
        for campaign in self.campaigns.values():
            stream = next((s for s in campaign.streams if s.id == stream_id), None)
            if stream is not None:
                disabled = self.disabled_offers.get(stream_id, set())
                return KeitaroStreamState(
                    stream_id, campaign.id, tuple(o for o in stream.offers if o.offer.id not in disabled),
                    tuple(InactiveStreamOffer(o.offer.id, o.share, "disabled") for o in stream.offers if o.offer.id in disabled),
                )
        raise StreamNotInCampaign(stream_id)

    def create_campaign(self, name: str) -> CampaignId:
        cid = CampaignId(next(self._campaign_ids))
        self.campaigns[cid] = KeitaroCampaign(cid, name, f"demo{cid}", None)
        return cid

    def create_geo_stream(self, campaign_id: CampaignId, spec: GeoRedirectStreamSpec) -> None:
        self._add_stream(campaign_id, spec.name, spec.position, ())

    def create_offers_stream(self, campaign_id: CampaignId, spec: OffersStreamSpec) -> None:
        self._add_stream(campaign_id, spec.name, spec.position, (PublishedOffer(spec.offer, spec.share),))

    def delete_campaign(self, campaign_id: CampaignId) -> None:
        campaign = self.campaigns.pop(campaign_id, None)
        if campaign:
            for stream in campaign.streams:
                self.disabled_offers.pop(stream.id, None)

    def publish_offers(
        self, stream_id: StreamId, offers: Sequence[PublishedOffer], *, current: KeitaroStreamState | None = None,
    ) -> None:
        """Как HTTP ACL: сохранить выключенные, если Adrobot не включает их явно."""
        sent = {o.offer.id for o in offers}
        current = current if current is not None else self.get_stream(stream_id)
        refs = {o.id: o for o in OFFERS}
        kept = tuple(PublishedOffer(refs[o.offer_id], o.share) for o in current.inactive_offers if o.offer_id not in sent)
        self.edit_offers(stream_id, (*offers, *kept), {o.offer.id for o in kept})

    def edit_offers(
        self, stream_id: StreamId, offers: Sequence[PublishedOffer], disabled: set[OfferId],
    ) -> None:
        """Ручная правка полного списка в демо-Keitaro, включая выключенные строки."""
        for cid, campaign in self.campaigns.items():
            if any(s.id == stream_id for s in campaign.streams):
                streams = tuple(replace(s, offers=tuple(offers)) if s.id == stream_id else s for s in campaign.streams)
                self.campaigns[cid] = replace(campaign, streams=streams)
                self.disabled_offers[stream_id] = set(disabled)
                return
        raise KeitaroError(f"Демопоток {stream_id} не найден", status=404)

    def _add_stream(self, campaign_id: CampaignId, name: str, position: int, offers: tuple[PublishedOffer, ...]) -> None:
        self.get_campaign(campaign_id)  # проверка существования
        campaign = self.campaigns[campaign_id]  # полный снимок с выключенными офферами
        stream = KeitaroStream(StreamId(next(self._stream_ids)), name, position, offers)
        self.campaigns[campaign_id] = replace(campaign, streams=tuple(sorted((*campaign.streams, stream), key=lambda s: s.position)))


@dataclass
class DemoStorage:
    campaigns: dict[CampaignId, Campaign] = field(default_factory=dict)
    # Lock можно освободить в другом worker thread при завершении sync-зависимости FastAPI.
    lock: Lock = field(default_factory=Lock)


class DemoSession:
    """Repository + UnitOfWork; несохранённые изменения отбрасываются в конце запроса."""

    def __init__(self, storage: DemoStorage) -> None:
        self.storage = storage
        self.pending: dict[CampaignId, Campaign] = {}

    def get(self, campaign_id: CampaignId) -> Campaign | None:
        return deepcopy(self.pending.get(campaign_id) or self.storage.campaigns.get(campaign_id))

    def list(self) -> list[Campaign]:
        return [deepcopy(c) for _, c in sorted({**self.storage.campaigns, **self.pending}.items(), reverse=True)]

    def add(self, campaign: Campaign) -> None:
        if self.get(campaign.id) is not None:
            raise CampaignAlreadyExists(campaign.id)
        campaign.version = 1
        self.pending[campaign.id] = deepcopy(campaign)

    def save(self, campaign: Campaign) -> None:
        stored = self.get(campaign.id)
        if stored is None:
            raise CampaignNotFound(campaign.id)
        if stored.version != campaign.version:
            raise ConcurrencyConflict(campaign.id)
        campaign.version += 1
        self.pending[campaign.id] = deepcopy(campaign)

    def commit(self) -> None:
        self.storage.campaigns.update(deepcopy(self.pending))
        self.pending.clear()

    def rollback(self) -> None:
        self.pending.clear()


class DemoOfferWeight(BaseModel):
    offer_id: int
    share: int = Field(ge=0, le=100)
    state: Literal["active", "disabled"] = "active"


class DemoKeitaroEdit(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    stream_id: int
    offers: list[DemoOfferWeight]

    @model_validator(mode="after")
    def valid_rotation(self) -> "DemoKeitaroEdit":
        self.name = self.name.strip()
        if not self.name:
            raise ValueError("Название не может быть пустым")
        ids = [o.offer_id for o in self.offers]
        if len(ids) != len(set(ids)) or not set(ids) <= {o.id for o in OFFERS}:
            raise ValueError("Выберите разные офферы из демосправочника")
        return self


def create_demo_app() -> FastAPI:
    """Каждый экземпляр приложения получает свои три оффера и две исходные кампании."""
    gateway, storage = DemoKeitaro(), DemoStorage()
    for cid, shares in ((1, (50, 50)), (2, (34, 33, 33))):
        snapshot = KeitaroCampaign(
            CampaignId(cid), f"{PREFIX}{len(shares)}_offers", f"demo{cid}", None,
            (
                KeitaroStream(StreamId(cid * 10 + 1), "Geo → Google (demo)", 1),
                KeitaroStream(StreamId(cid * 10 + 2), "Offers", 2,
                              tuple(PublishedOffer(offer, share) for offer, share in zip(OFFERS, shares))),
            ),
        )
        gateway.campaigns[snapshot.id] = snapshot
        campaign = Campaign.from_keitaro(snapshot)
        campaign.version = 1
        storage.campaigns[campaign.id] = campaign

    def session() -> Iterator[DemoSession]:
        with storage.lock:
            unit = DemoSession(storage)
            try:
                yield unit
            finally:
                unit.rollback()

    def repository(unit: Annotated[DemoSession, Depends(session)]) -> DemoSession:
        return unit

    def published_state() -> dict:
        return {
            "offers": [{"id": o.id, "name": o.name} for o in OFFERS],
            "campaigns": [
                {"id": c.id, "name": c.name, "streams": [
                    {"id": s.id, "name": s.name, "position": s.position,
                     "offers": [{"offer_id": o.offer.id, "share": o.share,
                                 "state": "disabled" if o.offer.id in gateway.disabled_offers.get(s.id, set()) else "active"}
                                for o in s.offers]}
                    for s in c.streams
                ]}
                for c in sorted(gateway.campaigns.values(), key=lambda c: c.id)
            ],
        }

    router = APIRouter(prefix="/demo/keitaro", tags=["demo-keitaro"])

    @router.get("")
    def read_published(_: Annotated[DemoSession, Depends(session)]) -> dict:
        return published_state()

    @router.put("/campaigns/{campaign_id}")
    def edit_published(
        campaign_id: int, body: DemoKeitaroEdit, _: Annotated[DemoSession, Depends(session)],
    ) -> dict:
        campaign = gateway.get_campaign(CampaignId(campaign_id))
        if not any(s.id == body.stream_id for s in campaign.streams):
            from app.domain.campaigns.errors import StreamNotInCampaign
            raise StreamNotInCampaign(body.stream_id)
        offers = {o.id: o for o in OFFERS}
        gateway.edit_offers(
            StreamId(body.stream_id),
            [PublishedOffer(offers[o.offer_id], o.share) for o in body.offers],
            {OfferId(o.offer_id) for o in body.offers if o.state == "disabled"},
        )
        gateway.campaigns[campaign.id] = replace(gateway.campaigns[campaign.id], name=body.name)
        # Меняется только «Keitaro»: агрегат и черновик Adrobot остаются прежними.
        return published_state()

    app = create_app(demo=True, additional_routers=(router,))
    app.dependency_overrides[get_repository] = repository
    app.dependency_overrides[get_unit_of_work] = repository
    app.dependency_overrides[get_keitaro] = lambda: gateway
    app.dependency_overrides[get_prefix] = lambda: PREFIX
    app.dependency_overrides[get_push_lease_seconds] = lambda: 300.0
    app.dependency_overrides[get_keitaro_timeout] = lambda: 20.0
    return app
