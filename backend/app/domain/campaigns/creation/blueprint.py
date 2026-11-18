"""Чертёж новой кампании для создаватора (FR-1.x): что именно создать в Keitaro."""

from dataclasses import dataclass

from app.domain.campaigns.errors import InvalidCampaignName
from app.domain.geo.geo_code import GeoCode
from app.domain.offers.offer_ref import OfferRef

CAMPAIGN_NAME_MAX_LENGTH = 100
GEO_REDIRECT_URL = "https://www.google.com"


@dataclass(frozen=True, slots=True)
class GeoRedirectStreamSpec:
    """Поток 1: всех из указанных стран — редиректом на Google (FR-1.4)."""

    name: str
    position: int
    countries: tuple[GeoCode, ...]
    redirect_url: str


@dataclass(frozen=True, slots=True)
class OffersStreamSpec:
    """Поток 2: всех остальных — на выбранный оффер (FR-1.5)."""

    name: str
    position: int
    offer: OfferRef
    share: int


@dataclass(frozen=True, slots=True)
class CampaignBlueprint:
    name: str
    geos: tuple[GeoCode, ...]
    offer: OfferRef

    @classmethod
    def create(cls, prefix: str, name: str, geos: str, offer: OfferRef) -> "CampaignBlueprint":
        name = name.strip()
        if not name:
            raise InvalidCampaignName("название не может быть пустым")
        if len(name) > CAMPAIGN_NAME_MAX_LENGTH:
            raise InvalidCampaignName(f"длиннее {CAMPAIGN_NAME_MAX_LENGTH} символов")
        full_name = name if name.startswith(prefix) else f"{prefix}{name}"
        return cls(full_name, GeoCode.parse_list(geos), offer)

    @property
    def geo_stream(self) -> GeoRedirectStreamSpec:
        countries = ",".join(str(g) for g in self.geos)
        return GeoRedirectStreamSpec(f"Geo {countries} → Google", 1, self.geos, GEO_REDIRECT_URL)

    @property
    def offers_stream(self) -> OffersStreamSpec:
        return OffersStreamSpec("Offers", 2, self.offer, 100)
