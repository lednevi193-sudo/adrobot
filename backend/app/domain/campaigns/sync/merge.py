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
    assignments: Sequence[OfferAssignment], offers: Sequence[PublishedOffer]
) -> MergeResult:
    """Применяет к привязкам то, что сейчас лежит в Keitaro.

    - оффер исчез из Keitaro -> в архив (removed), а не удаляется;
    - оффер есть в Keitaro -> опубликованное := Keitaro, желаемое := Keitaro,
      кроме закреплённого веса: его Keitaro не перетирает (Q7);
    - активные привязки получают актуальный порядок Keitaro, архивные идут следом.
    """
    from_keitaro = {o.offer.id: o for o in offers}
    order = {o.offer.id: i for i, o in enumerate(offers, 1)}
    archive_order = len(offers) + 1
    needs_rebalance = False
    merged: list[OfferAssignment] = []

    for a in sorted(assignments, key=lambda a: a.order):
        ko = from_keitaro.pop(a.offer.id, None)
        if ko is None:
            if a.published is not None:  # ни разу не публиковавшуюся просто забываем
                a.published, a.desired = ARCHIVED, EXCLUDED
                a.order = archive_order
                archive_order += 1
                merged.append(a)
            continue

        a.offer = ko.offer  # обновить снимок имени
        a.order = order[ko.offer.id]
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

    for ko in from_keitaro.values():
        merged.append(
            OfferAssignment(
                ko.offer, order[ko.offer.id], DesiredState(True, ko.share), PublishedState(True, ko.share)
            )
        )
    return MergeResult(sorted(merged, key=lambda a: a.order), needs_rebalance)
