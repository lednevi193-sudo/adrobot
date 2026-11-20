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
    """Как оффер сейчас стоит в Keitaro. in_rotation=False — был опубликован, потом удалён (архив).

    share — вес в Keitaro. pinned_share — закреплённый вес, который обёртка опубликовала
    последним Push. Обычно они равны; разойтись могут, если вес поменяли руками в Keitaro:
    тогда закреплённый вес главнее (Q7, FR-2.9a), и Cancel/Fetch возвращают именно его.
    """

    in_rotation: bool
    share: int = 0
    pinned: bool = False
    pinned_share: int | None = None

    @property
    def intended_share(self) -> int:
        """Вес, который обёртка считает опубликованным: закреплённый, если он есть, иначе из Keitaro."""
        return self.pinned_share if self.pinned and self.pinned_share is not None else self.share

    @property
    def has_pin_drift(self) -> bool:
        """Закреплённый вес разошёлся с Keitaro (FR-2.9a)."""
        return self.in_rotation and self.pinned and self.intended_share != self.share


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
        """Желаемое расходится с тем, что лежит в Keitaro, — поток «жёлтый» (FR-2.5).

        Сюда входит и расхождение закреплённого веса с Keitaro (FR-2.9a), которое
        не является черновиком пользователя: Cancel его не убирает.
        """
        if self.published is None or not self.published.in_rotation:
            return self.desired.in_rotation
        return self.desired != DesiredState(True, self.published.share, self.published.pinned)

    def published_desired(self) -> DesiredState:
        """Желаемое состояние на момент последнего Push (с закреплённым весом, Q7) — к нему откатывает Cancel.

        Вызывать только для когда-либо опубликованных (published is not None).
        """
        assert self.published is not None
        p = self.published
        return DesiredState(True, p.intended_share, p.pinned) if p.in_rotation else EXCLUDED

    def mark_published(self) -> None:
        """Push прошёл: опубликованное := желаемое."""
        d = self.desired
        if d.in_rotation:
            self.published = PublishedState(True, d.share, d.pinned, d.share if d.pinned else None)
        else:
            self.published = ARCHIVED
