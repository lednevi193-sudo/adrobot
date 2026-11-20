"""Поток — сущность агрегата Campaign: команды редактора и инварианты весов.

Снаружи агрегата поток меняют только через корень (Campaign). Python не умеет
«internal», поэтому это соглашение, а не запрет компилятора.
"""

from dataclasses import dataclass, field, replace
from enum import StrEnum

from app.domain.campaigns.model.assignment import EXCLUDED, DesiredState, OfferAssignment
from app.domain.campaigns.model.draft import DraftChange, describe_change
from app.domain.campaigns.sync.snapshots import KeitaroStream, PublishedOffer
from app.domain.campaigns.sync.merge import merge_published
from app.domain.campaigns.errors import (
    EmptyStreamPush,
    InvalidShare,
    NotAnOffersStream,
    OfferAlreadyInRotation,
    OfferAlreadyInStream,
    OfferIsArchived,
    OfferNotInRotation,
    OfferNotInStream,
    PinnedSharesExceed100,
    SharesDoNotSumTo100,
)
from app.domain.common.ids import OfferId, StreamId
from app.domain.offers.offer_ref import OfferRef
from app.domain.campaigns.services.weights import Slot, distribute_shares


class StreamKind(StrEnum):
    OFFERS = "offers"  # поток с офферами — им управляет обёртка
    OTHER = "other"  # любой другой поток (например, гео-редирект) — только показываем


@dataclass(slots=True)
class Stream:
    id: StreamId
    name: str
    position: int
    kind: StreamKind
    assignments: list[OfferAssignment] = field(default_factory=list)

    # ---------- синхронизация с Keitaro ----------

    @classmethod
    def from_keitaro(cls, snapshot: KeitaroStream) -> "Stream":
        stream = cls(snapshot.id, snapshot.name, snapshot.position, StreamKind.OTHER)
        stream.sync_from_keitaro(snapshot)
        return stream

    def sync_from_keitaro(self, snapshot: KeitaroStream) -> None:
        """Черновик к этому моменту должен быть отменён — за этим следит корень (FR-2.3a)."""
        self.name, self.position = snapshot.name, snapshot.position
        if snapshot.offers:
            self.kind = StreamKind.OFFERS
        result = merge_published(self.assignments, snapshot.offers, self._next_order())
        self.assignments = result.assignments
        if result.needs_rebalance:
            self._rebalance()

    # ---------- команды редактора ----------

    def add_offer(self, offer: OfferRef) -> None:
        self._require_editable()
        existing = self._find(offer.id)
        if existing is not None:
            raise OfferAlreadyInStream(offer.id) if existing.desired.in_rotation else OfferIsArchived(offer.id)
        self.assignments.append(OfferAssignment(offer, self._next_order(), DesiredState(True)))
        self._rebalance()

    def remove_offer(self, offer_id: OfferId) -> None:
        a = self._get_in_rotation(offer_id)
        if a.published is None:
            self.assignments.remove(a)  # никогда не было в Keitaro — просто забываем
        else:
            a.desired = EXCLUDED  # закрепление снимается (Q8)
        self._rebalance()

    def bring_back(self, offer_id: OfferId) -> None:
        self._require_editable()
        a = self._get(offer_id)
        if a.desired.in_rotation:
            raise OfferAlreadyInRotation(offer_id)
        if a.is_published:
            # отмена ещё не опубликованного удаления: вернуть как было в Keitaro
            assert a.published is not None
            p = a.published
            keep_pin = p.pinned and self._pinned_total(exclude=a) + p.share <= 100
            a.desired = DesiredState(True, p.share, keep_pin)
        else:
            a.desired = DesiredState(True)  # из архива — незакреплённым (Q8)
        self._rebalance()

    def pin(self, offer_id: OfferId, share: int | None = None) -> None:
        """Закрепить вес: текущий (share=None) или заданный вручную (FR-2.9)."""
        a = self._get_in_rotation(offer_id)
        value = a.desired.share if share is None else share
        if not 0 <= value <= 100:
            raise InvalidShare(value)
        total = self._pinned_total(exclude=a) + value
        if total > 100:
            raise PinnedSharesExceed100(total)
        a.desired = DesiredState(True, value, pinned=True)
        self._rebalance()

    def unpin(self, offer_id: OfferId) -> None:
        a = self._get_in_rotation(offer_id)
        a.desired = replace(a.desired, pinned=False)
        self._rebalance()

    # ---------- черновик: просмотр, отмена, публикация ----------

    @property
    def has_draft(self) -> bool:
        """Поток «жёлтый»: есть неопубликованные изменения (FR-2.5)."""
        return any(a.is_changed for a in self.assignments)

    def draft_changes(self) -> list[DraftChange]:
        return [c for a in self._ordered() if (c := describe_change(a)) is not None]

    def cancel(self) -> list[DraftChange]:
        """Откатить поток к опубликованному снимку целиком, включая закрепления (FR-2.10, Q9)."""
        changes = self.draft_changes()
        self.assignments = [a for a in self.assignments if a.published is not None]
        for a in self.assignments:
            a.restore_published()
        return changes

    def offers_to_publish(self) -> list[PublishedOffer]:
        """Что отправить в Keitaro при Push. Проверяет инварианты публикации (FR-2.12)."""
        self._require_editable()
        rotation = self._rotation()
        if not rotation:
            raise EmptyStreamPush()
        total = sum(a.desired.share for a in rotation)
        if total != 100:
            raise SharesDoNotSumTo100(total)
        return [PublishedOffer(a.offer, a.desired.share) for a in rotation]

    def mark_published(self) -> None:
        self.assignments = [a for a in self.assignments if a.desired.in_rotation or a.published is not None]
        for a in self.assignments:
            a.mark_published()

    # ---------- внутреннее ----------

    def _rebalance(self) -> None:
        rotation = self._rotation()
        shares = distribute_shares(
            [Slot(a.offer.id, a.desired.share if a.desired.pinned else None) for a in rotation]
        )
        for a in rotation:
            a.desired = replace(a.desired, share=shares[a.offer.id])

    def _ordered(self) -> list[OfferAssignment]:
        return sorted(self.assignments, key=lambda a: a.order)

    def _rotation(self) -> list[OfferAssignment]:
        """Офферы, между которыми делится трафик потока, в порядке потока."""
        return [a for a in self._ordered() if a.desired.in_rotation]

    def _pinned_total(self, exclude: OfferAssignment) -> int:
        return sum(a.desired.share for a in self._rotation() if a.desired.pinned and a is not exclude)

    def _next_order(self) -> int:
        return max((a.order for a in self.assignments), default=0) + 1

    def _find(self, offer_id: OfferId) -> OfferAssignment | None:
        return next((a for a in self.assignments if a.offer.id == offer_id), None)

    def _get(self, offer_id: OfferId) -> OfferAssignment:
        a = self._find(offer_id)
        if a is None:
            raise OfferNotInStream(offer_id)
        return a

    def _get_in_rotation(self, offer_id: OfferId) -> OfferAssignment:
        self._require_editable()
        a = self._get(offer_id)
        if not a.desired.in_rotation:
            raise OfferNotInRotation(offer_id)
        return a

    def _require_editable(self) -> None:
        if self.kind is not StreamKind.OFFERS:
            raise NotAnOffersStream(self.id)
