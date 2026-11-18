"""Доменный сервис пересчёта весов (FR-2.11, FR-2.12)."""

from collections.abc import Sequence
from dataclasses import dataclass

from app.domain.campaigns.errors import PinnedSharesExceed100
from app.domain.common.ids import OfferId


@dataclass(frozen=True, slots=True)
class Slot:
    """Участник распределения. pinned_share=None — вес не закреплён."""

    offer_id: OfferId
    pinned_share: int | None = None


def distribute_shares(slots: Sequence[Slot]) -> dict[OfferId, int]:
    """Распределяет 100% между участниками.

    Закреплённые сохраняют свой вес, остаток делится между незакреплёнными поровну
    целыми числами; лишние единицы получают первые по порядку `slots` (34/33/33).
    Если незакреплённых нет, веса возвращаются как есть — сумму проверяют перед Push.
    """
    pinned_total = sum(s.pinned_share for s in slots if s.pinned_share is not None)
    if pinned_total > 100:
        raise PinnedSharesExceed100(pinned_total)

    free = [s for s in slots if s.pinned_share is None]
    base, extra = divmod(100 - pinned_total, len(free)) if free else (0, 0)

    result: dict[OfferId, int] = {}
    free_index = 0
    for slot in slots:
        if slot.pinned_share is not None:
            result[slot.offer_id] = slot.pinned_share
        else:
            result[slot.offer_id] = base + (1 if free_index < extra else 0)
            free_index += 1
    return result
