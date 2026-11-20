"""Правила слияния опубликованного состояния Keitaro с привязками потока (FR-2.3, Q7)."""

from collections.abc import Sequence
from dataclasses import dataclass

from app.domain.campaigns.model.assignment import (
    ARCHIVED,
    EXCLUDED,
    DesiredState,
    OfferAssignment,
    PublishedState,
)
from app.domain.campaigns.sync.snapshots import PublishedOffer


@dataclass(frozen=True, slots=True)
class MergeResult:
    assignments: list[OfferAssignment]
    needs_rebalance: bool  # закреплённый вес разошёлся с Keitaro — остальные подстроить


def merge_published(
    assignments: Sequence[OfferAssignment], offers: Sequence[PublishedOffer], next_order: int
) -> MergeResult:
    """Применяет к привязкам то, что сейчас лежит в Keitaro.

    - оффер исчез из Keitaro -> в архив (removed), а не удаляется;
    - оффер есть в Keitaro -> опубликованное := Keitaro, желаемое := Keitaro,
      кроме закреплённого веса: его Keitaro не перетирает (Q7);
    - новый в Keitaro -> активная привязка в конце, в порядке Keitaro.
    """
    from_keitaro = {o.offer.id: o for o in offers}
    needs_rebalance = False
    merged: list[OfferAssignment] = []

    for a in assignments:
        ko = from_keitaro.pop(a.offer.id, None)
        if ko is None:
            if a.published is not None:  # ни разу не публиковавшуюся просто забываем
                a.published, a.desired = ARCHIVED, EXCLUDED
                merged.append(a)
            continue

        a.offer = ko.offer  # обновить снимок имени
        if a.desired.in_rotation and a.desired.pinned:
            # закреплённый вес Keitaro не перетирает (Q7); помним, какой вес закрепляли при Push,
            # чтобы повторный Fetch или Cancel вернули его, а не вес из Keitaro (FR-2.15)
            prev = a.published if a.is_published else None
            if prev is not None and prev.pinned:
                a.published = PublishedState(True, ko.share, True, prev.intended_share)
            else:
                a.published = PublishedState(True, ko.share)
            needs_rebalance |= a.desired.share != ko.share
        else:
            a.published = PublishedState(True, ko.share)
            a.desired = DesiredState(True, ko.share)
        merged.append(a)

    for i, ko in enumerate(from_keitaro.values()):
        merged.append(
            OfferAssignment(
                ko.offer, next_order + i, DesiredState(True, ko.share), PublishedState(True, ko.share)
            )
        )
    return MergeResult(merged, needs_rebalance)
