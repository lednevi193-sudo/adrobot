"""Автодополнение офферов (FR-1.2)."""

from app.application.offers.search_offers import SEARCH_LIMIT, search_offers
from app.domain.common.ids import OfferId
from app.domain.offers.offer_ref import OfferRef
from tests.application.world import FLEXACIL, OTHER, World


def test_search_by_id_and_name_ignoring_case(world: World) -> None:
    assert search_offers(world.keitaro, "188") == [FLEXACIL]
    assert search_offers(world.keitaro, "  flexACIL ") == [FLEXACIL]
    assert search_offers(world.keitaro, "") == [FLEXACIL, OTHER]
    assert search_offers(world.keitaro, "nothing") == []


def test_search_is_limited(world: World) -> None:
    world.keitaro.offers = [OfferRef(OfferId(i), f"Offer {i}") for i in range(1, 50)]
    assert len(search_offers(world.keitaro, "offer")) == SEARCH_LIMIT
