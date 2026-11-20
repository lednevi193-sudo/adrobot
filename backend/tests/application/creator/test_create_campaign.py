"""Создаватор: FR-1.3 – FR-1.8, компенсация FR-1.6."""

import pytest

from app.application.creator.create_campaign import create_campaign
from app.application.errors import CampaignCreationFailed, OfferNotFound
from app.domain.common.ids import OfferId
from app.domain.geo.errors import InvalidGeoCode
from tests.application.world import FLEXACIL, PREFIX, World


def create(world: World, *, geos: str = "mx, au", offer_id: int = FLEXACIL.id):
    return create_campaign(
        world.repo, world.keitaro, world.uow, prefix=PREFIX, name="promo", geos=geos, offer_id=OfferId(offer_id)
    )


def test_creates_campaign_with_two_streams_and_saves_it(world: World) -> None:
    campaign = create(world)

    assert campaign.name == "test_x_promo"
    assert [(s.position, s.name) for s in campaign.streams] == [(1, "Geo MX,AU → Google"), (2, "Offers")]
    assert world.repo.get(campaign.id) == campaign
    assert world.uow.commits == 1


def test_form_errors_never_reach_keitaro(world: World) -> None:
    with pytest.raises(InvalidGeoCode):
        create(world, geos="Mexico")
    with pytest.raises(OfferNotFound):
        create(world, offer_id=1)
    assert "create_campaign" not in world.keitaro.calls


@pytest.mark.parametrize("failing", ["create_geo_stream", "create_offers_stream", "get_campaign"])
def test_failure_after_campaign_created_is_compensated(world: World, failing: str) -> None:
    world.keitaro.fail_on = {failing}

    with pytest.raises(CampaignCreationFailed) as exc:
        create(world)

    assert exc.value.compensated
    assert world.keitaro.campaigns == {}  # полусобранной кампании в Keitaro нет
    assert world.keitaro.archived
    assert world.repo.list() == []


def test_failure_of_our_database_is_compensated_too(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    def broken_commit() -> None:
        raise RuntimeError("database is down")

    monkeypatch.setattr(world.uow, "commit", broken_commit)

    with pytest.raises(CampaignCreationFailed, match="database is down"):
        create(world)
    assert world.keitaro.campaigns == {}
    assert world.uow.rollbacks == 1


def test_failed_compensation_is_reported(world: World) -> None:
    world.keitaro.fail_on = {"create_offers_stream", "delete_campaign"}

    with pytest.raises(CampaignCreationFailed, match="удалите её вручную") as exc:
        create(world)
    assert not exc.value.compensated
