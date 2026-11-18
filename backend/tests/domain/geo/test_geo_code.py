import pytest

from app.domain.geo.errors import InvalidGeoCode
from app.domain.geo.geo_code import GeoCode


def test_geo_list_is_normalized() -> None:
    assert GeoCode.parse_list(" mx, au,MX ,") == (GeoCode("MX"), GeoCode("AU"))


@pytest.mark.parametrize("raw", ["", " , ", "Australia", "A1", "AUS"])
def test_invalid_geo_is_rejected(raw: str) -> None:
    with pytest.raises(InvalidGeoCode):
        GeoCode.parse_list(raw)
