"""Кампания — корень агрегата.

Граница согласованности: потоки и привязки офферов загружаются, меняются
и сохраняются только целиком, через команды корня.
"""

from dataclasses import dataclass, field

from app.domain.campaigns.services.changes import Change
from app.domain.campaigns.sync.snapshots import KeitaroCampaign, PublishedOffer
from app.domain.campaigns.model.stream import Stream
from app.domain.campaigns.errors import CampaignHasDrafts, StreamNotInCampaign
from app.domain.common.ids import CampaignId, OfferId, StreamId
from app.domain.offers.offer_ref import OfferRef


@dataclass(slots=True)
class Campaign:
    id: CampaignId
    name: str
    alias: str
    domain_url: str | None
    created_by_us: bool = False
    streams: list[Stream] = field(default_factory=list)
    version: int = 0  # оптимистическая блокировка, ведёт репозиторий

    @classmethod
    def from_keitaro(cls, snapshot: KeitaroCampaign, *, created_by_us: bool = False) -> "Campaign":
        campaign = cls(snapshot.id, snapshot.name, snapshot.alias, snapshot.domain_url, created_by_us)
        campaign.sync_from_keitaro(snapshot)
        return campaign

    @property
    def tracker_url(self) -> str | None:
        """Ссылка трекера: домен + alias (например https://kylovoa.com/VrfMdGff)."""
        if not self.domain_url:
            return None
        return f"{self.domain_url.rstrip('/')}/{self.alias}"

    # ---------- синхронизация (Fetch) ----------

    def sync_from_keitaro(self, snapshot: KeitaroCampaign, *, discard_drafts: bool = False) -> None:
        """Fetch: подтянуть состояние из Keitaro (FR-2.2, FR-2.3).

        Если есть черновики, без явного discard_drafts бросает CampaignHasDrafts —
        UI показывает подтверждение со списком изменений и повторяет вызов (FR-2.3a).
        """
        if self.is_dirty:
            if not discard_drafts:
                raise CampaignHasDrafts(sum(len(c) for c in self.pending_changes().values()))
            self.cancel_all()

        self.name, self.alias, self.domain_url = snapshot.name, snapshot.alias, snapshot.domain_url
        current = {s.id: s for s in self.streams}
        synced: list[Stream] = []
        for ks in snapshot.streams:
            stream = current.get(ks.id)
            if stream is None:
                stream = Stream.from_keitaro(ks)
            else:
                stream.sync_from_keitaro(ks)
            synced.append(stream)
        # потоки, которых больше нет в Keitaro, уходят из агрегата
        self.streams = sorted(synced, key=lambda s: s.position)

    # ---------- команды редактора: делегируют потоку ----------

    def add_offer(self, stream_id: StreamId, offer: OfferRef) -> None:
        self.stream(stream_id).add_offer(offer)

    def remove_offer(self, stream_id: StreamId, offer_id: OfferId) -> None:
        self.stream(stream_id).remove_offer(offer_id)

    def bring_back(self, stream_id: StreamId, offer_id: OfferId) -> None:
        self.stream(stream_id).bring_back(offer_id)

    def pin(self, stream_id: StreamId, offer_id: OfferId, share: int | None = None) -> None:
        self.stream(stream_id).pin(offer_id, share)

    def unpin(self, stream_id: StreamId, offer_id: OfferId) -> None:
        self.stream(stream_id).unpin(offer_id)

    def cancel(self, stream_id: StreamId) -> list[Change]:
        return self.stream(stream_id).cancel()

    def cancel_all(self) -> dict[StreamId, list[Change]]:
        return {s.id: changes for s in self.streams if (changes := s.cancel())}

    def offers_to_publish(self, stream_id: StreamId) -> list[PublishedOffer]:
        return self.stream(stream_id).offers_to_publish()

    def mark_published(self, stream_id: StreamId) -> None:
        self.stream(stream_id).mark_published()

    # ---------- чтение ----------

    @property
    def is_dirty(self) -> bool:
        return any(s.is_dirty for s in self.streams)

    def pending_changes(self) -> dict[StreamId, list[Change]]:
        return {s.id: changes for s in self.streams if (changes := s.pending_changes())}

    def stream(self, stream_id: StreamId) -> Stream:
        """Поток для чтения. Менять его — только через команды корня."""
        found = next((s for s in self.streams if s.id == stream_id), None)
        if found is None:
            raise StreamNotInCampaign(stream_id)
        return found
