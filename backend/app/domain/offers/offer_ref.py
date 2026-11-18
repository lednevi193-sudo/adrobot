"""Ссылка на оффер из внешнего справочника Keitaro."""

from dataclasses import dataclass

from app.domain.common.ids import OfferId


@dataclass(frozen=True, slots=True)
class OfferRef:
    """ID оффера и снимок его имени для отображения. Офферами владеет Keitaro."""

    id: OfferId
    name: str
