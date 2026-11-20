"""Черновик потока — неопубликованные изменения, которые пользователь видит в подтверждении Cancel/Fetch (FR-2.10a)."""

from dataclasses import dataclass
from enum import StrEnum

from app.domain.campaigns.model.assignment import AssignmentStatus, OfferAssignment
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


def describe_change(a: OfferAssignment) -> DraftChange | None:
    """Изменение привязки относительно опубликованного или None, если изменений нет."""
    if not a.is_changed:
        return None
    match a.status:
        case AssignmentStatus.PENDING_ADD:
            return DraftChange(a.offer, DraftChangeKind.ADD, None, a.desired.share)
        case AssignmentStatus.PENDING_REMOVE:
            assert a.published is not None
            return DraftChange(a.offer, DraftChangeKind.REMOVE, a.published.share, 0)

    assert a.published is not None  # ACTIVE: поменялся вес и/или закрепление
    if a.desired.pinned != a.published.pinned:
        kind = DraftChangeKind.PIN if a.desired.pinned else DraftChangeKind.UNPIN
    else:
        kind = DraftChangeKind.SHARE
    return DraftChange(a.offer, kind, a.published.share, a.desired.share)
