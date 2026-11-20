"""Фейк должен вести себя как настоящий порт — иначе тесты сценариев проверяют выдумку."""

import pytest

from app.application.errors import CampaignNotFound, KeitaroError
from app.domain.campaigns import Campaign, CampaignBlueprint, PublishedOffer
from app.domain.common.ids import CampaignId, OfferId
from app.domain.common.ids import StreamId
from app.domain.campaigns.errors import StreamNotInCampaign
from app.domain.offers.offer_ref import OfferRef
from tests.fakes.keitaro_gateway import FakeKeitaroGateway

OFFER = OfferRef(OfferId(18813), "Flexacil")


def created(fake: FakeKeitaroGateway) -> CampaignId:
    blueprint = CampaignBlueprint.create("test_x_", "promo", "AU", OFFER)
    cid = fake.create_campaign(blueprint.name)
    fake.create_offers_stream(cid, blueprint.offers_stream)
    fake.create_geo_stream(cid, blueprint.geo_stream)
    return cid


def test_created_campaign_reads_back_as_snapshot() -> None:
    fake = FakeKeitaroGateway()
    campaign = Campaign.from_keitaro(fake.get_campaign(created(fake)))

    assert [s.position for s in campaign.streams] == [1, 2]  # как в Keitaro — по позиции
    assert [(p.offer.id, p.share) for p in campaign.offers_to_publish(campaign.streams[1].id)] == [(18813, 100)]


def test_publish_replaces_stream_offers() -> None:
    fake = FakeKeitaroGateway()
    cid = created(fake)
    stream_id = fake.get_campaign(cid).streams[1].id
    other = OfferRef(OfferId(25327), "Other")

    fake.publish_offers(stream_id, [PublishedOffer(other, 100)])

    assert fake.get_campaign(cid).streams[1].offers == (PublishedOffer(other, 100),)


def test_stream_and_name_reads_follow_port_contract() -> None:
    fake = FakeKeitaroGateway()
    cid = created(fake)
    stream_id = fake.get_campaign(cid).streams[1].id
    fake.calls.clear()
    assert fake.get_campaign_name(cid) == 'test_x_promo'
    stream = fake.get_stream(stream_id)
    assert (stream.id, stream.campaign_id) == (stream_id, cid)
    assert [(o.offer.id, o.share) for o in stream.offers] == [(18813, 100)]
    assert fake.calls == ['get_campaign_name', 'get_stream']
    with pytest.raises(StreamNotInCampaign):
        fake.get_stream(StreamId(404))
    with pytest.raises(CampaignNotFound):
        fake.get_campaign_name(CampaignId(404))


def test_fail_on_and_delete() -> None:
    fake = FakeKeitaroGateway(fail_on={"create_geo_stream"})
    cid = fake.create_campaign("test_x_promo")
    with pytest.raises(KeitaroError):
        fake.create_geo_stream(cid, CampaignBlueprint.create("", "p", "AU", OFFER).geo_stream)

    fake.delete_campaign(cid)
    assert cid in fake.archived
    with pytest.raises(CampaignNotFound):
        fake.get_campaign(cid)
