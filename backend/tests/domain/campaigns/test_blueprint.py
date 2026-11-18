import pytest

from app.domain.campaigns import CampaignBlueprint
from app.domain.campaigns.errors import InvalidCampaignName
from app.domain.common.ids import OfferId
from app.domain.offers.offer_ref import OfferRef

OFFER = OfferRef(OfferId(18813), "Flexacil")


def test_blueprint_builds_two_streams() -> None:
    bp = CampaignBlueprint.create("test_x_", "  promo ", "au,mx", OFFER)

    assert bp.name == "test_x_promo"
    geo = bp.geo_stream
    assert (geo.position, geo.redirect_url) == (1, "https://www.google.com")
    assert [str(g) for g in geo.countries] == ["AU", "MX"]
    offers = bp.offers_stream
    assert (offers.position, offers.offer, offers.share) == (2, OFFER, 100)


def test_prefix_is_not_duplicated() -> None:
    assert CampaignBlueprint.create("test_x_", "test_x_promo", "AU", OFFER).name == "test_x_promo"


@pytest.mark.parametrize("name", ["", "   ", "x" * 101])
def test_invalid_name_is_rejected(name: str) -> None:
    with pytest.raises(InvalidCampaignName):
        CampaignBlueprint.create("p_", name, "AU", OFFER)
