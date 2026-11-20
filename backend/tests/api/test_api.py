"""Контракт HTTP: маршруты, форма CampaignView и перевод ошибок в статусы."""

import pytest
from fastapi.testclient import TestClient

from app.domain.campaigns import PublishedOffer
from tests.application.world import FLEXACIL, OTHER, World


@pytest.fixture
def created(client: TestClient) -> dict:
    r = client.post("/api/campaigns", json={"name": "promo", "geos": "mx,au", "offer_id": FLEXACIL.id})
    assert r.status_code == 201, r.text
    return r.json()


def url(c: dict, tail: str = "") -> str:
    return f"/api/campaigns/{c['id']}/streams/{c['streams'][1]['id']}{tail}"


# ---------- создаватор и справочник ----------


def test_create_returns_campaign_view(created: dict) -> None:
    assert created["name"] == "test_x_promo"
    assert created["is_ours"] and not created["has_draft"]
    assert created["tracker_url"].startswith("https://kylovoa.com/")
    geo, offers = created["streams"]
    assert (geo["name"], geo["editable"], geo["push_blocker"]) == ("Geo MX,AU → Google", False, None)
    assert offers["offers"] == [
        {"id": FLEXACIL.id, "name": FLEXACIL.name, "status": "active", "share": 100, "pinned": False, "keitaro_share": 100}
    ]


def test_create_validation_error_is_422(client: TestClient) -> None:
    r = client.post("/api/campaigns", json={"name": "promo", "geos": "Mexico", "offer_id": FLEXACIL.id})
    assert r.status_code == 422
    assert r.json()["code"] == "invalid_geo"


def test_create_compensated_failure_is_502(client: TestClient, world: World) -> None:
    world.keitaro.fail_on = {"create_offers_stream"}
    r = client.post("/api/campaigns", json={"name": "promo", "geos": "AU", "offer_id": FLEXACIL.id})
    assert r.status_code == 502
    assert r.json()["code"] == "campaign_creation_failed"


def test_search_offers(client: TestClient) -> None:
    assert client.get("/api/offers", params={"q": "flex"}).json() == [{"id": FLEXACIL.id, "name": FLEXACIL.name}]


def test_list_ours_and_all(client: TestClient, world: World, created: dict) -> None:
    world.keitaro.create_campaign("test_y_their")
    assert [c["id"] for c in client.get("/api/campaigns").json()] == [created["id"]]
    assert len(client.get("/api/campaigns", params={"all": True}).json()) == 2


def test_open_unknown_is_404(client: TestClient) -> None:
    r = client.get("/api/campaigns/404")
    assert (r.status_code, r.json()["code"]) == (404, "campaign_not_found")


# ---------- редактор ----------


def test_editor_flow_add_pin_push(client: TestClient, world: World, created: dict) -> None:
    c = client.post(url(created, "/offers"), json={"offer_id": OTHER.id}).json()
    stream = c["streams"][1]
    assert c["has_draft"] and stream["has_draft"]
    assert [(o["status"], o["share"]) for o in stream["offers"]] == [("active", 50), ("pending_add", 50)]

    c = client.put(url(created, f"/offers/{FLEXACIL.id}/pin"), json={"share": 70}).json()
    assert [o["share"] for o in c["streams"][1]["offers"]] == [70, 30]

    draft = client.get(url(created, "/draft")).json()
    assert {d["kind"] for d in draft} == {"pin", "add"}

    c = client.post(url(created, "/push")).json()
    assert not c["has_draft"]
    assert [o["keitaro_share"] for o in c["streams"][1]["offers"]] == [70, 30]


def test_remove_and_bring_back(client: TestClient, created: dict) -> None:
    c = client.delete(url(created, f"/offers/{FLEXACIL.id}")).json()
    stream = c["streams"][1]
    assert stream["offers"][0]["status"] == "pending_remove"
    assert stream["push_blocker"]  # пустой поток публиковать нельзя (FR-2.12)

    assert client.post(url(created, "/push")).status_code == 422

    c = client.post(url(created, f"/offers/{FLEXACIL.id}/bring-back")).json()
    assert not c["has_draft"]


def test_cancel_returns_discarded(client: TestClient, created: dict) -> None:
    client.post(url(created, "/offers"), json={"offer_id": OTHER.id})
    r = client.post(url(created, "/cancel")).json()
    assert not r["campaign"]["has_draft"]
    assert {d["kind"] for d in r["cancelled"]} == {"add", "share"}


def test_rule_violation_is_422(client: TestClient, created: dict) -> None:
    r = client.post(url(created, "/offers"), json={"offer_id": FLEXACIL.id})
    assert (r.status_code, r.json()["code"]) == (422, "offer_already_in_stream")


def test_unknown_stream_is_404(client: TestClient, created: dict) -> None:
    r = client.post(f"/api/campaigns/{created['id']}/streams/1/offers", json={"offer_id": OTHER.id})
    assert r.status_code == 404


# ---------- Fetch с черновиком (FR-2.3a) ----------


def test_fetch_with_draft_is_409_with_changes(client: TestClient, world: World, created: dict) -> None:
    client.post(url(created, "/offers"), json={"offer_id": OTHER.id})

    r = client.post(f"/api/campaigns/{created['id']}/fetch")
    assert r.status_code == 409
    body = r.json()
    assert body["code"] == "campaign_has_drafts"
    assert {(d["offer"]["id"], d["kind"]) for d in body["changes"]} == {(FLEXACIL.id, "share"), (OTHER.id, "add")}

    r = client.post(f"/api/campaigns/{created['id']}/fetch", json={"discard_drafts": True})
    assert r.status_code == 200 and not r.json()["has_draft"]


def test_fetch_shows_keitaro_share_of_pinned_offer(client: TestClient, world: World, created: dict) -> None:
    client.post(url(created, "/offers"), json={"offer_id": OTHER.id})
    client.put(url(created, f"/offers/{FLEXACIL.id}/pin"), json={"share": 70})
    client.post(url(created, "/push"))
    world.keitaro.edit_stream(created["streams"][1]["id"], [PublishedOffer(FLEXACIL, 20), PublishedOffer(OTHER, 80)])

    offers = client.post(f"/api/campaigns/{created['id']}/fetch").json()["streams"][1]["offers"]

    assert [(o["share"], o["keitaro_share"]) for o in offers] == [(70, 20), (30, 80)]  # «в Keitaro сейчас 20%»


# ---------- Push ----------


def test_push_not_confirmed_is_502_with_differences(
    client: TestClient, world: World, created: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    client.post(url(created, "/offers"), json={"offer_id": OTHER.id})
    monkeypatch.setattr(world.keitaro, "publish_offers", lambda stream_id, offers: None)

    r = client.post(url(created, "/push"))
    assert r.status_code == 502
    assert r.json()["code"] == "push_not_confirmed" and r.json()["differences"]


def test_push_to_foreign_is_403(client: TestClient, world: World) -> None:
    cid = world.keitaro.create_campaign("test_y_their")
    client.get(f"/api/campaigns/{cid}")
    r = client.post(f"/api/campaigns/{cid}/streams/1/push")
    assert (r.status_code, r.json()["code"]) == (403, "not_our_campaign")


def test_keitaro_down_is_504(client: TestClient, world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.application.errors import KeitaroUnavailable

    def down() -> list:
        raise KeitaroUnavailable("Keitaro не ответил вовремя")

    monkeypatch.setattr(world.keitaro, "list_active_offers", down)
    assert client.get("/api/offers").status_code == 504
