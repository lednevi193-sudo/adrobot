"""Нарушения правил агрегата «Кампания» и создаватора."""

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING

from app.domain.common.errors import DomainError

if TYPE_CHECKING:  # только для аннотаций: без цикла импортов model -> errors -> model
    from app.domain.campaigns.model.draft import DraftChange


class InvalidCampaignName(DomainError):
    code = "invalid_campaign_name"

    def __init__(self, reason: str) -> None:
        super().__init__(f"Некорректное название кампании: {reason}")


class StreamNotInCampaign(DomainError):
    code = "stream_not_in_campaign"

    def __init__(self, stream_id: int) -> None:
        super().__init__(f"Потока {stream_id} нет в кампании")


class CampaignHasDrafts(DomainError):
    code = "campaign_has_drafts"

    def __init__(self, changes: "Mapping[int, Sequence[DraftChange]]") -> None:
        """changes — черновик по потокам: его UI показывает в подтверждении (FR-2.3a)."""
        self.changes = dict(changes)
        self.version: int | None = None  # версия снимка для подтверждённого Fetch
        self.changes_count = sum(len(c) for c in self.changes.values())
        super().__init__(
            f"В кампании есть неопубликованные изменения ({self.changes_count}). "
            "Синхронизация с Keitaro их отменит — подтвердите действие"
        )


class NotAnOffersStream(DomainError):
    code = "not_an_offers_stream"

    def __init__(self, stream_id: int) -> None:
        super().__init__(f"Поток {stream_id} не содержит офферов и не редактируется")


class OfferNotInStream(DomainError):
    code = "offer_not_in_stream"

    def __init__(self, offer_id: int) -> None:
        super().__init__(f"Оффера {offer_id} нет в потоке")


class OfferAlreadyInStream(DomainError):
    code = "offer_already_in_stream"

    def __init__(self, offer_id: int) -> None:
        super().__init__(f"Оффер {offer_id} уже есть в потоке")


class OfferIsArchived(DomainError):
    code = "offer_is_archived"

    def __init__(self, offer_id: int) -> None:
        super().__init__(f"Оффер {offer_id} лежит в архиве потока — верните его кнопкой Bring back")


class OfferNotInRotation(DomainError):
    code = "offer_not_in_rotation"

    def __init__(self, offer_id: int) -> None:
        super().__init__(f"Оффер {offer_id} удалён из потока")


class OfferAlreadyInRotation(DomainError):
    code = "offer_already_in_rotation"

    def __init__(self, offer_id: int) -> None:
        super().__init__(f"Оффер {offer_id} и так участвует в потоке")


class InvalidShare(DomainError):
    code = "invalid_share"

    def __init__(self, value: int) -> None:
        super().__init__(f"Вес должен быть целым числом от 0 до 100, получено {value}")


class PinnedSharesExceed100(DomainError):
    code = "pinned_shares_exceed_100"

    def __init__(self, total: int) -> None:
        super().__init__(f"Сумма закреплённых весов {total}% больше 100%")


class EmptyStreamPush(DomainError):
    code = "empty_stream_push"

    def __init__(self) -> None:
        super().__init__("В потоке не осталось офферов — опубликовать пустой поток нельзя")


class SharesDoNotSumTo100(DomainError):
    code = "shares_do_not_sum_to_100"

    def __init__(self, total: int) -> None:
        super().__init__(
            f"Сумма весов {total}%, а должна быть 100%: все офферы закреплены — "
            "поправьте закреплённые веса или открепите один из офферов"
        )
