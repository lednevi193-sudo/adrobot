"""Поток — сущность агрегата Campaign: команды редактора и инварианты весов.

Снаружи агрегата поток меняют только через корень (Campaign). Python не умеет
«internal», поэтому это соглашение, а не запрет компилятора.
"""

from collections.abc import Sequence
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
        result = merge_published(self.assignments, snapshot.offers)
        self.assignments = result.assignments
        # Веса активных в Keitaro могут не давать 100: например, выключенный в Keitaro оффер
        # остаётся там со своим весом, а в раздачу обёртки не попадает. Тогда пересчитываем,
        # иначе Push заблокирован суммой ≠ 100, хотя пользователь ничего не менял.
        if result.needs_rebalance or sum(a.desired.share for a in self._rotation()) != 100:
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
            # отмена неопубликованного удаления: оффер вернётся, снятое закрепление — нет
            assert a.published is not None
            p = a.published
            a.desired = DesiredState(True, p.share)  # Remove снимает закрепление (Q8)
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
        """Снять закрепление. Если закреплённый вес разошёлся с Keitaro — это выбор
        «принять вес из Keitaro» (FR-2.9a): веса берутся из Keitaro, а не делятся заново."""
        a = self._get_in_rotation(offer_id)
        p = a.published
        accept_keitaro = a.desired.pinned and p is not None and p.has_pin_drift
        a.desired = replace(a.desired, pinned=False)
        if not (accept_keitaro and self._take_keitaro_shares()):
            self._rebalance()
            return
        # Принять вес из Keitaro — значит согласиться с тем, что там уже лежит. Если после этого
        # обёртка совпадает с Keitaro целиком, публиковать нечего: снятие закрепления сразу
        # становится опубликованным, иначе поток оставался бы жёлтым, а Cancel вернул бы закрепление.
        if p is not None and not any(x.is_changed for x in self.assignments if x is not a):
            a.published = replace(p, pinned=False, pinned_share=None)

    # ---------- черновик: просмотр, отмена, публикация ----------

    @property
    def has_draft(self) -> bool:
        """Поток «жёлтый»: желаемое расходится с Keitaro (FR-2.5).

        Это черновик пользователя (draft_changes) и/или закреплённый вес, который поменяли
        в Keitaro (FR-2.9a): второе Cancel не убирает — решают Push или Unpin.
        """
        return any(a.is_changed for a in self.assignments)

    def draft_changes(self) -> list[DraftChange]:
        """Что отбросит Cancel: разница между текущим и опубликованным состоянием (FR-2.10a)."""
        baseline = self._baseline()
        return [c for a in self._ordered() if (c := describe_change(a, baseline.get(a.offer.id))) is not None]

    def cancel(self) -> list[DraftChange]:
        """Откатить поток к опубликованному снимку целиком, включая закрепления (FR-2.10, Q9)."""
        changes = self.draft_changes()
        baseline = self._baseline()
        self.assignments = [a for a in self.assignments if a.published is not None]
        for a in self.assignments:
            a.desired = baseline[a.offer.id]
        return changes

    def adopt_published(self, offers: Sequence[PublishedOffer]) -> bool:
        """Черновик, который уже лежит в Keitaro, считается опубликованным.

        Так бывает, если Push в Keitaro прошёл, а сохранить это у нас не удалось (сбой БД,
        параллельная правка): Fetch не должен предлагать «отменить» уже опубликованное.
        """
        if self.kind is not StreamKind.OFFERS or not self.draft_changes():
            return False
        ours = sorted((a.offer.id, a.desired.share) for a in self._rotation())
        if not ours or ours != sorted((o.offer.id, o.share) for o in offers):
            return False
        self.mark_published()
        return True

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

    def _baseline(self) -> dict[OfferId, DesiredState]:
        """Желаемое состояние опубликованных привязок на момент последнего Push.

        Закреплённые — со своим закреплённым весом (Q7). Если он разошёлся с Keitaro,
        остальные пересчитываются, чтобы сумма осталась 100.
        """
        published = [a for a in self._ordered() if a.published is not None]
        baseline = {a.offer.id: a.published_desired() for a in published}
        # Как в sync_from_keitaro: закреплённый вес разошёлся с Keitaro или веса Keitaro не дают 100
        # (например, включили оффер, выключенный со своим весом) — пересчитать, иначе Cancel вернул бы
        # раздачу, которую нельзя опубликовать.
        in_rotation_total = sum(d.share for d in baseline.values() if d.in_rotation)
        if in_rotation_total != 100 or any(a.published is not None and a.published.has_pin_drift for a in published):
            rotation = [a.offer.id for a in published if baseline[a.offer.id].in_rotation]
            shares = distribute_shares([Slot(i, baseline[i].share if baseline[i].pinned else None) for i in rotation])
            for i in rotation:
                baseline[i] = replace(baseline[i], share=shares[i])
        return baseline

    def _take_keitaro_shares(self) -> bool:
        """Незакреплённым — веса из Keitaro, если раздача по составу та же, что в Keitaro,
        и сумма сходится в 100. Иначе False — и вызывающий делает обычный пересчёт."""
        if any(a.is_published and not a.desired.in_rotation for a in self.assignments):
            return False
        rotation = self._rotation()
        shares: dict[OfferId, int] = {}
        for a in rotation:
            if not a.is_published or a.published is None:
                return False
            shares[a.offer.id] = a.desired.share if a.desired.pinned else a.published.share
        if sum(shares.values()) != 100:
            return False
        for a in rotation:
            a.desired = replace(a.desired, share=shares[a.offer.id])
        return True

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
