"""Привязка оффера к потоку: желаемое и опубликованное состояние, вычисляемый статус."""

from dataclasses import dataclass
from enum import StrEnum

from app.domain.offers.offer_ref import OfferRef


class AssignmentStatus(StrEnum):
    ACTIVE = "active"
    PENDING_ADD = "pending_add"
    PENDING_REMOVE = "pending_remove"
    REMOVED = "removed"


@dataclass(frozen=True, slots=True)
class DesiredState:
    """Что пользователь хочет видеть в Keitaro."""

    included: bool
    share: int = 0
    pinned: bool = False


@dataclass(frozen=True, slots=True)
class PublishedState:
    """Что лежит в Keitaro. present=False — оффер был опубликован, потом удалён (архив)."""

    present: bool
    share: int = 0
    pinned: bool = False


EXCLUDED = DesiredState(included=False)
ARCHIVED = PublishedState(present=False)


@dataclass(slots=True)
class OfferAssignment:
    """Сущность внутри агрегата, идентичность — offer.id в пределах потока."""

    offer: OfferRef
    seq: int  # порядок добавления: по нему раздаются лишние единицы при округлении
    desired: DesiredState
    published: PublishedState | None = None  # None — ни разу не публиковалась

    @property
    def is_published(self) -> bool:
        return self.published is not None and self.published.present

    @property
    def status(self) -> AssignmentStatus:
        if self.desired.included:
            return AssignmentStatus.ACTIVE if self.is_published else AssignmentStatus.PENDING_ADD
        return AssignmentStatus.PENDING_REMOVE if self.is_published else AssignmentStatus.REMOVED

    @property
    def is_dirty(self) -> bool:
        """Желаемое расходится с опубликованным — есть что публиковать или отменять."""
        if self.published is None or not self.published.present:
            return self.desired.included
        return self.desired != DesiredState(True, self.published.share, self.published.pinned)

    def restore_published(self) -> None:
        """Cancel для одной привязки: желаемое := опубликованное.

        Вызывать только для когда-либо опубликованных (published is not None).
        """
        assert self.published is not None
        p = self.published
        self.desired = DesiredState(True, p.share, p.pinned) if p.present else EXCLUDED

    def mark_published(self) -> None:
        """Push прошёл: опубликованное := желаемое."""
        if self.desired.included:
            self.published = PublishedState(True, self.desired.share, self.desired.pinned)
        else:
            self.published = ARCHIVED
