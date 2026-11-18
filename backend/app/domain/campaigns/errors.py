"""Нарушения правил агрегата «Кампания» и создаватора."""

from app.domain.common.errors import DomainError


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

    def __init__(self, changes_count: int) -> None:
        super().__init__(
            f"В кампании есть неопубликованные изменения ({changes_count}). "
            "Синхронизация с Keitaro их отменит — подтвердите действие"
        )
        self.changes_count = changes_count


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


class OfferNotIncluded(DomainError):
    code = "offer_not_included"

    def __init__(self, offer_id: int) -> None:
        super().__init__(f"Оффер {offer_id} удалён из потока")


class OfferAlreadyIncluded(DomainError):
    code = "offer_already_included"

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
