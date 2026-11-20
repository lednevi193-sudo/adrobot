"""Кампания — корень агрегата.

Граница согласованности: потоки и привязки офферов загружаются, меняются
и сохраняются только целиком, через команды корня.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field

from app.domain.campaigns.model.draft import DraftChange
from app.domain.campaigns.sync.snapshots import KeitaroCampaign, PublishedOffer
from app.domain.campaigns.model.stream import Stream
from app.domain.campaigns.errors import CampaignHasDrafts, StreamNotInCampaign
from app.domain.common.ids import CampaignId, OfferId, StreamId
from app.domain.offers.offer_ref import OfferRef


def is_our_name(name: str, prefix: str) -> bool:
    """«Наша» кампания — название с нашим префиксом (FR-2.1, Q5). Признак виден и в самом Keitaro.

    Без настроенного префикса «наших» нет: так нельзя случайно править чужие кампании стенда (NFR-4).
    """
    return bool(prefix) and name.startswith(prefix)


@dataclass(slots=True)
class Campaign:
    id: CampaignId
    name: str
    alias: str
    domain_url: str | None
    streams: list[Stream] = field(default_factory=list)
    version: int = 0  # оптимистическая блокировка, ведёт репозиторий

    @classmethod
    def from_keitaro(cls, snapshot: KeitaroCampaign) -> "Campaign":
        campaign = cls(snapshot.id, snapshot.name, snapshot.alias, snapshot.domain_url)
        campaign.sync_from_keitaro(snapshot)
        return campaign

    @property
    def tracker_url(self) -> str | None:
        """Ссылка трекера: домен + alias (например https://kylovoa.com/VrfMdGff)."""
        if not self.domain_url:
            return None
        return f"{self.domain_url.rstrip('/')}/{self.alias}"

    def is_ours(self, prefix: str) -> bool:
        return is_our_name(self.name, prefix)

    # ---------- синхронизация (Fetch) ----------

    def sync_from_keitaro(self, snapshot: KeitaroCampaign, *, discard_drafts: bool = False) -> None:
        """Fetch: подтянуть состояние из Keitaro (FR-2.2, FR-2.3).

        Если есть черновик, без явного discard_drafts бросает CampaignHasDrafts —
        UI показывает подтверждение со списком изменений и повторяет вызов (FR-2.3a).
        Черновик, который уже лежит в Keitaro, черновиком не считается (Stream.adopt_published).
        """
        from_keitaro = {ks.id: ks for ks in snapshot.streams}
        for s in self.streams:
            if s.id in from_keitaro:
                s.adopt_published(from_keitaro[s.id].offers)

        if changes := self.draft_changes():
            if not discard_drafts:
                raise CampaignHasDrafts(changes)
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

    def cancel(self, stream_id: StreamId) -> list[DraftChange]:
        return self.stream(stream_id).cancel()

    def cancel_all(self) -> dict[StreamId, list[DraftChange]]:
        return {s.id: changes for s in self.streams if (changes := s.cancel())}

    def offers_to_publish(self, stream_id: StreamId) -> list[PublishedOffer]:
        return self.stream(stream_id).offers_to_publish()

    def mark_published(self, stream_id: StreamId) -> None:
        self.stream(stream_id).mark_published()

    def adopt_published(self, stream_id: StreamId, offers: Sequence[PublishedOffer]) -> bool:
        return self.stream(stream_id).adopt_published(offers)

    # ---------- чтение ----------

    @property
    def has_draft(self) -> bool:
        return any(s.has_draft for s in self.streams)

    def draft_changes(self) -> dict[StreamId, list[DraftChange]]:
        return {s.id: changes for s in self.streams if (changes := s.draft_changes())}

    def stream(self, stream_id: StreamId) -> Stream:
        """Поток для чтения. Менять его — только через команды корня."""
        found = next((s for s in self.streams if s.id == stream_id), None)
        if found is None:
            raise StreamNotInCampaign(stream_id)
        return found
