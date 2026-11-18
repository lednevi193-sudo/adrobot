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


class ConcurrencyConflict(ApplicationError):
    code = "concurrency_conflict"

    def __init__(self, campaign_id: int) -> None:
        super().__init__(
            f"Кампанию {campaign_id} только что изменили в другой вкладке или другим пользователем. "
            "Обновите страницу и повторите действие"
        )
