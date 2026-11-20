import httpx
import pytest
from fastapi.testclient import TestClient

from app.demo import create_demo_app
from app.main import create_app


@pytest.fixture
def demo(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Demo must not access real database, settings or network")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", forbidden)
    monkeypatch.setattr("app.infrastructure.db.get_engine", forbidden)
    monkeypatch.setattr("app.api.dependencies.get_settings", forbidden)
    with TestClient(create_demo_app()) as client:
        yield client


def offers_stream(campaign):
    return next(s for s in campaign["streams"] if s["position"] == 2)


def test_demo_starts_with_three_offers_and_two_campaigns_without_external_services(demo):
    assert demo.get("/api/runtime").json() == {"mode": "demo"}
    assert demo.get("/api/health").json() == {"status": "ok", "storage": "memory", "mode": "demo"}
    assert len(demo.get("/api/offers").json()) == 3
    campaigns = demo.get("/api/campaigns").json()
    assert {c["name"] for c in campaigns} == {"demo_2_offers", "demo_3_offers"}
    for campaign in campaigns:
        view = demo.get(f"/api/campaigns/{campaign['id']}").json()["campaign"]
        offers = offers_stream(view)["offers"]
        assert len(offers) == (2 if campaign["id"] == 1 else 3)
        assert sum(o["share"] for o in offers) == 100


def test_demo_add_cancel_push_remove_and_bring_back(demo):
    base = "/api/campaigns/1/streams/12"
    added = demo.post(base + "/offers", json={"offer_id": 103}).json()
    assert [o["share"] for o in offers_stream(added)["offers"]] == [34, 33, 33]
    pinned = demo.put(base + "/offers/101/pin", json={"share": 50}).json()
    assert [o["share"] for o in offers_stream(pinned)["offers"]] == [50, 25, 25]
    snapshot = demo.get(base + "/draft").json()
    cancelled = demo.post(base + "/cancel", headers={"If-Match": str(snapshot["version"])}).json()["campaign"]
    assert not cancelled["has_draft"]
    assert len(offers_stream(cancelled)["offers"]) == 2
    added = demo.post(base + "/offers", json={"offer_id": 103}).json()
    published = demo.post(base + "/push", headers={"If-Match": str(added["version"])}).json()
    assert not published["has_draft"]
    assert [o["status"] for o in offers_stream(published)["offers"]] == ["active"] * 3
    demo.delete(base + "/offers/102")
    assert demo.post(base + "/push").status_code == 200
    fetched = demo.post("/api/campaigns/1/fetch").json()
    assert next(o["status"] for o in offers_stream(fetched)["offers"] if o["id"] == 102) == "removed"
    restored = demo.post(base + "/offers/102/bring-back").json()
    assert next(o["status"] for o in offers_stream(restored)["offers"] if o["id"] == 102) == "pending_add"
    assert demo.post(base + "/cancel").status_code == 200


def test_demo_creation_and_stale_versions(demo):
    response = demo.post("/api/campaigns", json={"name": "new", "geos": "AU,MX", "offer_id": 101})
    assert response.status_code == 201
    created = response.json()
    assert created["name"] == "demo_new"
    stream = offers_stream(created)
    base = f"/api/campaigns/{created['id']}/streams/{stream['id']}"
    assert demo.post(base + "/offers", json={"offer_id": 102}).status_code == 200
    assert demo.post(base + "/cancel", headers={"If-Match": str(created["version"])}).status_code == 409


def test_editing_in_demo_keitaro_preserves_draft_until_fetch_confirmation(demo):
    base = "/api/campaigns/1/streams/12"
    before = demo.post(base + "/offers", json={"offer_id": 103}).json()
    edit = demo.put("/api/demo/keitaro/campaigns/1", json={
        "name": "demo_renamed", "stream_id": 12,
        "offers": [{"offer_id": 102, "share": 70}, {"offer_id": 101, "share": 30}],
    })
    assert edit.status_code == 200
    opened = demo.get("/api/campaigns/1").json()
    assert opened["campaign"] == before
    assert opened["keitaro_changes"]
    warning = demo.post("/api/campaigns/1/fetch").json()
    assert warning["code"] == "campaign_has_drafts"
    fetched = demo.post("/api/campaigns/1/fetch", json={"discard_drafts": True},
                        headers={"If-Match": str(warning["version"])}).json()
    assert fetched["name"] == "demo_renamed"
    assert [(o["id"], o["share"]) for o in offers_stream(fetched)["offers"]] == [(102, 70), (101, 30)]


def test_external_pin_drift_and_prefix_guard_can_be_tested_locally(demo):
    base = "/api/campaigns/1/streams/12"
    demo.put(base + "/offers/101/pin", json={"share": 60})
    demo.post(base + "/push")
    body = {"name": "demo_2_offers", "stream_id": 12,
            "offers": [{"offer_id": 101, "share": 20}, {"offer_id": 102, "share": 80}]}
    assert demo.put("/api/demo/keitaro/campaigns/1", json=body).status_code == 200
    fetched = demo.post("/api/campaigns/1/fetch").json()
    first = offers_stream(fetched)["offers"][0]
    assert (first["share"], first["keitaro_share"], first["pinned"]) == (60, 20, True)
    assert demo.delete(base + "/offers/101/pin").status_code == 200
    demo.post(base + "/offers", json={"offer_id": 103})
    assert demo.put("/api/demo/keitaro/campaigns/1", json={**body, "name": "foreign_campaign"}).status_code == 200
    assert demo.post(base + "/push").status_code == 403


@pytest.mark.parametrize("rotation", [
    [{"offer_id": 101, "share": -1}],
    [{"offer_id": 101, "share": 50}, {"offer_id": 101, "share": 50}],
    [{"offer_id": 999, "share": 100}],
    [{"offer_id": 101, "share": 100, "state": "unknown"}],
])
def test_demo_keitaro_rejects_invalid_edit_without_changing_published_state(demo, rotation):
    original = demo.get("/api/demo/keitaro").json()
    assert demo.put("/api/demo/keitaro/campaigns/1", json={
        "name": "bad", "stream_id": 12, "offers": rotation,
    }).status_code == 422
    assert demo.get("/api/demo/keitaro").json() == original


def test_disabled_offer_is_retained_in_demo_keitaro_and_excluded_from_fetch(demo):
    rotation = [{"offer_id": 101, "share": 50, "state": "active"},
                {"offer_id": 102, "share": 50, "state": "disabled"}]
    response = demo.put("/api/demo/keitaro/campaigns/1", json={
        "name": "demo_disabled", "stream_id": 12, "offers": rotation,
    })
    assert response.status_code == 200
    assert response.json()["campaigns"][0]["streams"][1]["offers"] == rotation
    fetched = demo.post("/api/campaigns/1/fetch").json()
    assert fetched["name"] == "demo_disabled"
    offers = {o["id"]: o for o in offers_stream(fetched)["offers"]}
    # 102 выключен вместе со своими 50% — 101 пересчитан до 100%, иначе Push заблокирован суммой 50%
    assert (offers[101]["status"], offers[101]["share"], offers[101]["keitaro_share"]) == ("active", 100, 50)
    assert offers_stream(fetched)["push_blocker"] is None
    assert (offers[102]["status"], offers[102]["share"], offers[102]["keitaro_share"]) == ("removed", 0, None)
    assert {o["id"] for o in demo.get("/api/offers").json()} == {101, 102, 103}

    # Push сохраняет выключенную строку и её исходный вес, как настоящий HTTP ACL.
    base = "/api/campaigns/1/streams/12"
    demo.put(base + "/offers/101/pin", json={"share": 100})
    assert demo.post(base + "/push").status_code == 200
    raw = demo.get("/api/demo/keitaro").json()["campaigns"][0]["streams"][1]["offers"]
    assert raw == [{"offer_id": 101, "share": 100, "state": "active"}, rotation[1]]

    # Явный возврат через Adrobot включает тот же оффер, без дубля выключенной строки.
    demo.post(base + "/offers/102/bring-back")
    demo.delete(base + "/offers/101/pin")
    assert demo.post(base + "/push").status_code == 200
    raw = demo.get("/api/demo/keitaro").json()["campaigns"][0]["streams"][1]["offers"]
    assert raw == [{"offer_id": 101, "share": 50, "state": "active"},
                   {"offer_id": 102, "share": 50, "state": "active"}]


def test_all_offers_can_be_disabled_and_enabled_again_in_demo_keitaro(demo):
    body = {"name": "demo_2_offers", "stream_id": 12,
            "offers": [{"offer_id": 101, "share": 50, "state": "disabled"},
                       {"offer_id": 102, "share": 50, "state": "disabled"}]}
    assert demo.put("/api/demo/keitaro/campaigns/1", json=body).status_code == 200
    fetched = demo.post("/api/campaigns/1/fetch").json()
    assert all(o["status"] == "removed" for o in offers_stream(fetched)["offers"])
    body["offers"][1]["state"] = "active"
    assert demo.put("/api/demo/keitaro/campaigns/1", json=body).status_code == 200
    fetched = demo.post("/api/campaigns/1/fetch").json()
    assert [(o["id"], o["status"]) for o in offers_stream(fetched)["offers"]] == [(102, "active"), (101, "removed")]


def test_demo_instances_are_isolated_and_live_app_has_no_demo_editor(demo):
    demo.post("/api/campaigns", json={"name": "new", "geos": "AU", "offer_id": 101})
    with TestClient(create_demo_app()) as fresh:
        assert len(fresh.get("/api/campaigns").json()) == 2
    with TestClient(create_app()) as live:
        assert live.get("/api/runtime").json() == {"mode": "live"}
        assert live.get("/api/demo/keitaro").status_code == 404
