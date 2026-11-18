"""Нарушения доменных правил.

Каждая ошибка несёт машинный `code` (для фронта и тестов) и сообщение для пользователя.
API-слой переводит их в HTTP-ответы, домен про HTTP ничего не знает.
"""


class DomainError(Exception):
    code = "domain_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message
