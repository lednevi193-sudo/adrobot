"""Описание неопубликованных изменений — для подтверждения Cancel/Fetch (FR-2.10a)."""

from dataclasses import dataclass
from enum import StrEnum

from app.domain.campaigns.model.assignment import AssignmentStatus, OfferAssignment
from app.domain.offers.offer_ref import OfferRef


class ChangeKind(StrEnum):
    ADD = "add"
    REMOVE = "remove"
    PIN = "pin"
    UNPIN = "unpin"
    SHARE = "share"


@dataclass(frozen=True, slots=True)
class Change:
    offer: OfferRef
    kind: ChangeKind
    share_before: int | None
    share_after: int | None


def describe_change(a: OfferAssignment) -> Change | None:
    """Одно изменение на привязку или None, если она совпадает с опубликованной."""
    if not a.is_dirty:
        return None
    match a.status:
        case AssignmentStatus.PENDING_ADD:
            return Change(a.offer, ChangeKind.ADD, None, a.desired.share)
        case AssignmentStatus.PENDING_REMOVE:
            assert a.published is not None
            return Change(a.offer, ChangeKind.REMOVE, a.published.share, 0)

    assert a.published is not None  # ACTIVE: поменялся вес и/или закрепление
    if a.desired.pinned != a.published.pinned:
        kind = ChangeKind.PIN if a.desired.pinned else ChangeKind.UNPIN
    else:
        kind = ChangeKind.SHARE
    return Change(a.offer, kind, a.published.share, a.desired.share)
