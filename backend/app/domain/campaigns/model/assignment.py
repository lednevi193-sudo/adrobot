"""Оффер в потоке: желаемое и опубликованное состояние, вычисляемый статус."""

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
    """Как пользователь хочет видеть оффер в Keitaro."""

    in_rotation: bool  # участвует в раздаче трафика потока
    share: int = 0
    pinned: bool = False


@dataclass(frozen=True, slots=True)
class PublishedState:
    """Как оффер сейчас стоит в Keitaro. in_rotation=False — был опубликован, потом удалён (архив)."""

    in_rotation: bool
    share: int = 0
    pinned: bool = False


EXCLUDED = DesiredState(in_rotation=False)
ARCHIVED = PublishedState(in_rotation=False)


@dataclass(slots=True)
class OfferAssignment:
    """Сущность внутри агрегата, идентичность — offer.id в пределах потока."""

    offer: OfferRef
    order: int  # порядок оффера в потоке: по нему раздаются лишние единицы при округлении
    desired: DesiredState
    published: PublishedState | None = None  # None — ни разу не публиковался

    @property
    def is_published(self) -> bool:
        return self.published is not None and self.published.in_rotation

    @property
    def status(self) -> AssignmentStatus:
        if self.desired.in_rotation:
            return AssignmentStatus.ACTIVE if self.is_published else AssignmentStatus.PENDING_ADD
        return AssignmentStatus.PENDING_REMOVE if self.is_published else AssignmentStatus.REMOVED

    @property
    def is_changed(self) -> bool:
        """Желаемое расходится с опубликованным — привязка входит в черновик потока."""
        if self.published is None or not self.published.in_rotation:
            return self.desired.in_rotation
        return self.desired != DesiredState(True, self.published.share, self.published.pinned)

    def restore_published(self) -> None:
        """Cancel для одной привязки: желаемое := опубликованное.

        Вызывать только для когда-либо опубликованных (published is not None).
        """
        assert self.published is not None
        p = self.published
        self.desired = DesiredState(True, p.share, p.pinned) if p.in_rotation else EXCLUDED

    def mark_published(self) -> None:
        """Push прошёл: опубликованное := желаемое."""
        if self.desired.in_rotation:
            self.published = PublishedState(True, self.desired.share, self.desired.pinned)
        else:
            self.published = ARCHIVED
