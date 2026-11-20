"""Ошибки слоя приложения — не нарушения доменных правил, а сбои сценариев."""


class ApplicationError(Exception):
    code = "application_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class CampaignNotFound(ApplicationError):
    code = "campaign_not_found"

    def __init__(self, campaign_id: int) -> None:
        super().__init__(f"Кампания {campaign_id} не найдена")


class CampaignAlreadyExists(ApplicationError):
    code = "campaign_already_exists"

    def __init__(self, campaign_id: int) -> None:
        super().__init__(f"Кампания {campaign_id} уже есть в обёртке")


class KeitaroError(ApplicationError):
    """Keitaro отказал. В сообщении — текст ответа Keitaro (FR-1.8)."""

    code = "keitaro_error"

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class KeitaroUnavailable(KeitaroError):
    """Keitaro не ответил: таймаут или сетевая ошибка."""

    code = "keitaro_unavailable"


class OfferNotFound(ApplicationError):
    code = "offer_not_found"

    def __init__(self, offer_id: int) -> None:
        super().__init__(f"Оффер {offer_id} не найден среди активных офферов Keitaro")


class CampaignCreationFailed(ApplicationError):
    """Создание не удалось; созданное в Keitaro откачено (FR-1.6), если compensated."""

    code = "campaign_creation_failed"

    def __init__(self, reason: str, *, compensated: bool) -> None:
        tail = (
            "Созданная кампания перенесена в архив Keitaro."
            if compensated
            else "Откатить кампанию в Keitaro не удалось — удалите её вручную."
        )
        super().__init__(f"Кампанию создать не удалось: {reason}. {tail}")
        self.compensated = compensated


class NotOurCampaign(ApplicationError):
    code = "not_our_campaign"

    def __init__(self, campaign_id: int) -> None:
        super().__init__(
            f"Кампания {campaign_id} не наша (нет префикса CAMPAIGN_PREFIX): публиковать в неё нельзя, "
            "стенд общий"
        )


class PushNotConfirmed(ApplicationError):
    """После Push в Keitaro оказалось не то, что отправили (FR-2.13 п. 3). Черновик сохранён."""

    code = "push_not_confirmed"

    def __init__(self, stream_id: int, differences: list[str]) -> None:
        super().__init__(
            f"Keitaro принял Push потока {stream_id}, но опубликовал другое: {'; '.join(differences)}. "
            "Черновик сохранён — проверьте поток и повторите Push"
        )
        self.differences = differences


class ConcurrencyConflict(ApplicationError):
    code = "concurrency_conflict"

    def __init__(self, campaign_id: int) -> None:
        super().__init__(
            f"Кампанию {campaign_id} только что изменили в другой вкладке или другим пользователем. "
            "Обновите страницу и повторите действие"
        )
