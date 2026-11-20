"""ACL: JSON Keitaro (форма — как на стенде 20.11.2026) <-> снимки и спецификации домена."""

import pytest

from app.application.errors import CampaignNotFound, KeitaroError
from app.domain.campaigns import CampaignBlueprint, PublishedOffer
from app.domain.common.ids import CampaignId, OfferId, StreamId
from app.domain.offers.offer_ref import OfferRef
from tests.infrastructure.keitaro.stub import KeitaroStub

CID = 216714
FLEXACIL = OfferRef(OfferId(18813), "18813 Flexacil")

CAMPAIGN = {
    "id": CID, "alias": "VrfMdGff", "name": "test_x_promo", "type": "position", "state": "active",
    "domain": "https://kylovoa.com/", "domain_id": 1813, "group": "FORTESTS", "cookies_ttl": 24,
}
GEO_STREAM = {
    "id": 1332011, "type": "forced", "name": "Geo RO → Google", "campaign_id": CID, "position": 1,
    "state": "active", "schema": "redirect", "action_type": "http", "action_payload": "https://www.google.com",
    "filters": [{"id": 1, "name": "country", "mode": "accept", "payload": ["RO"]}], "offers": [],
}
OFFERS_STREAM = {
    "id": 1332012, "type": "regular", "name": "Offers", "campaign_id": CID, "position": 2, "state": "active",
    "schema": "landings", "filters": [],
    "offers": [
        {"id": 1, "stream_id": 1332012, "offer_id": 18813, "state": "active", "share": 60},
        {"id": 2, "stream_id": 1332012, "offer_id": 25327, "state": "active", "share": 40},  # скрыт от ключа (Q6)
        {"id": 3, "stream_id": 1332012, "offer_id": 17210, "state": "disabled", "share": 0},
    ],
}
OFFERS = [
    {"id": 18813, "name": "18813 Flexacil", "state": "active", "group_id": 7183},
    {"id": 99, "name": "Old offer", "state": "archived"},
]


@pytest.fixture
def stub() -> KeitaroStub:
    s = KeitaroStub()
    s.on("GET", f"/campaigns/{CID}", CAMPAIGN)
    s.on("GET", f"/campaigns/{CID}/streams", [OFFERS_STREAM, GEO_STREAM])  # порядок ответа не важен
    s.on("GET", "/offers", OFFERS)
    return s


# ---------- чтение ----------


def test_get_campaign_builds_snapshot(stub: KeitaroStub) -> None:
    c = stub.gateway().get_campaign(CampaignId(CID))

    assert (c.id, c.name, c.alias, c.domain_url) == (CID, "test_x_promo", "VrfMdGff", "https://kylovoa.com/")
    assert [(s.id, s.position, s.name) for s in c.streams] == [
        (1332011, 1, "Geo RO → Google"),
        (1332012, 2, "Offers"),
    ]
    assert c.streams[0].offers == ()
    assert c.streams[1].offers == (
        PublishedOffer(FLEXACIL, 60),
        PublishedOffer(OfferRef(OfferId(25327), ""), 40),  # имя неизвестно — только [id]
    )  # выключенный в Keitaro оффер в раздаче не участвует


def test_deleted_streams_are_skipped(stub: KeitaroStub) -> None:
    stub.on("GET", f"/campaigns/{CID}/streams", [GEO_STREAM, {**OFFERS_STREAM, "state": "deleted"}])
    assert [s.id for s in stub.gateway().get_campaign(CampaignId(CID)).streams] == [1332011]


def test_missing_campaign_is_not_found() -> None:
    with pytest.raises(CampaignNotFound):
        KeitaroStub().gateway().get_campaign(CampaignId(404))


def test_unexpected_payload_is_reported_not_crashing(stub: KeitaroStub) -> None:
    stub.on("GET", f"/campaigns/{CID}", {"id": CID})  # нет name/alias
    with pytest.raises(KeitaroError, match="Неожиданный формат"):
        stub.gateway().get_campaign(CampaignId(CID))


def test_list_active_offers_hides_inactive(stub: KeitaroStub) -> None:
    assert stub.gateway().list_active_offers() == [FLEXACIL]


def test_list_campaigns() -> None:
    stub = KeitaroStub()
    stub.on("GET", "/campaigns", [CAMPAIGN])
    assert [(c.id, c.name) for c in stub.gateway().list_campaigns()] == [(CID, "test_x_promo")]


# ---------- создаватор (FR-1.3 – FR-1.5) ----------


def test_create_campaign_uses_placement_and_alias() -> None:
    stub = KeitaroStub()
    stub.on("POST", "/campaigns", {**CAMPAIGN, "id": 777})

    assert stub.gateway().create_campaign("test_x_new") == 777
    assert stub.body() == {
        "name": "test_x_new", "alias": "Abc12345", "type": "position", "state": "active",
        "domain_id": 1813, "group_id": 10332, "traffic_source_id": 836,
    }


def test_create_streams_from_blueprint() -> None:
    stub = KeitaroStub()
    stub.on("POST", "/streams", {"id": 1})
    blueprint = CampaignBlueprint.create("test_x_", "promo", "mx, au", FLEXACIL)
    gateway = stub.gateway()

    gateway.create_geo_stream(CampaignId(777), blueprint.geo_stream)
    gateway.create_offers_stream(CampaignId(777), blueprint.offers_stream)

    geo, offers = stub.body(0), stub.body(1)
    assert geo == {
        "campaign_id": 777, "name": "Geo MX,AU → Google", "position": 1, "type": "forced",
        "schema": "redirect", "action_type": "http", "action_payload": "https://www.google.com",
        "state": "active", "filters": [{"name": "country", "mode": "accept", "payload": ["MX", "AU"]}],
    }
    assert offers == {
        "campaign_id": 777, "name": "Offers", "position": 2, "type": "regular", "schema": "landings",
        "action_type": "http", "state": "active",
        "offers": [{"offer_id": 18813, "share": 100, "state": "active"}],
    }


def test_delete_campaign() -> None:
    stub = KeitaroStub()
    stub.on("DELETE", "/campaigns/777", None)
    stub.gateway().delete_campaign(CampaignId(777))
    assert [(r.method, r.url.path) for r in stub.requests] == [("DELETE", "/admin_api/v1/campaigns/777")]


# ---------- Push (FR-2.13) ----------


def test_publish_offers_sends_only_offers_field() -> None:
    stub = KeitaroStub()
    stub.on("PUT", "/streams/1332012", OFFERS_STREAM)

    stub.gateway().publish_offers(
        StreamId(1332012), [PublishedOffer(FLEXACIL, 50), PublishedOffer(OfferRef(OfferId(25327), ""), 50)]
    )

    assert stub.body() == {
        "offers": [
            {"offer_id": 18813, "share": 50, "state": "active"},
            {"offer_id": 25327, "share": 50, "state": "active"},
        ]
    }
