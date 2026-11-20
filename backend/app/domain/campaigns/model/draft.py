"""Черновик потока — неопубликованные изменения, которые пользователь видит в подтверждении Cancel/Fetch (FR-2.10a)."""

from dataclasses import dataclass
from enum import StrEnum

from app.domain.campaigns.model.assignment import EXCLUDED, DesiredState, OfferAssignment
from app.domain.offers.offer_ref import OfferRef


class DraftChangeKind(StrEnum):
    ADD = "add"
    REMOVE = "remove"
    PIN = "pin"
    UNPIN = "unpin"
    SHARE = "share"


@dataclass(frozen=True, slots=True)
class DraftChange:
    """Одна строка подтверждения: «будет отменено: добавление оффера [25327] …»."""

    offer: OfferRef
    kind: DraftChangeKind
    share_before: int | None
    share_after: int | None


def describe_change(a: OfferAssignment, before: DesiredState | None) -> DraftChange | None:
    """Изменение привязки относительно опубликованного состояния before или None, если изменений нет.

    before=None — привязка ни разу не публиковалась.
    """
    before = before or EXCLUDED
    after = a.desired
    if after == before:
        return None
    if not before.in_rotation:
        return DraftChange(a.offer, DraftChangeKind.ADD, None, after.share)
    if not after.in_rotation:
        return DraftChange(a.offer, DraftChangeKind.REMOVE, before.share, 0)
    if after.pinned != before.pinned:
        kind = DraftChangeKind.PIN if after.pinned else DraftChangeKind.UNPIN
    else:
        kind = DraftChangeKind.SHARE
    return DraftChange(a.offer, kind, before.share, after.share)
