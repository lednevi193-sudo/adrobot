"""Гео-код страны."""

import re
from dataclasses import dataclass

from app.domain.geo.errors import InvalidGeoCode

_GEO_RE = re.compile(r"[A-Z]{2}")


@dataclass(frozen=True, slots=True)
class GeoCode:
    """ISO-код страны из двух латинских букв в верхнем регистре."""

    value: str

    def __post_init__(self) -> None:
        if not _GEO_RE.fullmatch(self.value):
            raise InvalidGeoCode(self.value)

    @classmethod
    def parse_list(cls, raw: str) -> tuple["GeoCode", ...]:
        """'mx, au,MX' -> (MX, AU): верхний регистр, без пробелов и дублей, порядок сохраняется."""
        codes: list[str] = []
        for part in raw.split(","):
            code = part.strip().upper()
            if code and code not in codes:
                codes.append(code)
        if not codes:
            raise InvalidGeoCode(raw)
        return tuple(cls(code) for code in codes)

    def __str__(self) -> str:
        return self.value
