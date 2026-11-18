"""Ошибки гео-кодов."""

from app.domain.common.errors import DomainError


class InvalidGeoCode(DomainError):
    code = "invalid_geo"

    def __init__(self, raw: str) -> None:
        super().__init__(
            f"Некорректный гео-код {raw!r}: ожидается ISO-код страны из двух латинских букв, "
            "например AU или MX,AU,RO"
        )
