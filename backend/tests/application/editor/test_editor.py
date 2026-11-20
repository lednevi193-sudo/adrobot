"""Сценарии редактора: открыть, Fetch, команды, Push (FR-2.1 – FR-2.14)."""

import pytest

from app.application.creator.create_campaign import create_campaign
from app.application.editor import edit_stream
from app.application.editor.fetch_streams import fetch_streams
from app.application.editor.list_campaigns import list_campaigns
from app.application.editor.open_campaign import open_campaign
from app.application.editor.push_stream import push_stream
from app.application.errors import (
    CampaignNotFound,
    KeitaroError,
    NotOurCampaign,
    OfferNotFound,
    PushNotConfirmed,
)
from app.domain.campaigns import AssignmentStatus, Campaign, PublishedOffer
from app.domain.campaigns.errors import CampaignHasDrafts, EmptyStreamPush, InvalidShare
from app.domain.common.ids import CampaignId, OfferId, StreamId
from tests.application.world import FLEXACIL, OTHER, PREFIX, World


@pytest.fixture
def ours(world: World) -> Campaign:
    """Кампания из создаватора: гео-поток + поток Offers с FLEXACIL 100%."""
    return create_campaign(
        world.repo, world.keitaro, world.uow, prefix=PREFIX, name="promo", geos="AU", offer_id=FLEXACIL.id
    )


def offers_stream(c: Campaign) -> StreamId:
    return c.streams[1].id


def in_keitaro(world: World, c: Campaign) -> dict[int, int]:
    stream = world.keitaro.get_campaign(c.id).streams[1]
    return {o.offer.id: o.share for o in stream.offers}


def push(world: World, c: Campaign) -> Campaign:
    return push_stream(world.repo, world.keitaro, world.uow, c.id, offers_stream(c), prefix=PREFIX)


def add_other(world: World, c: Campaign) -> Campaign:
    return edit_stream.add_offer(world.repo, world.keitaro, world.uow, c.id, offers_stream(c), OTHER.id)


# ---------- список и открытие (FR-2.1) ----------


def test_list_shows_ours_by_default(world: World, ours: Campaign) -> None:
    foreign = world.keitaro.create_campaign("test_y_their")

    assert [c.id for c in list_campaigns(world.repo, world.keitaro, prefix=PREFIX)] == [ours.id]
    assert [c.id for c in list_campaigns(world.repo, world.keitaro, prefix=PREFIX, only_ours=False)] == [
        foreign,
        ours.id,
    ]


def test_ours_are_listed_from_our_db_without_keitaro(world: World, ours: Campaign) -> None:
    opened_foreign = world.keitaro.create_campaign("test_y_their")
    open_campaign(world.repo, world.keitaro, world.uow, opened_foreign)
    made_in_keitaro = world.keitaro.create_campaign(PREFIX + "manual")
    world.keitaro.calls.clear()

    assert [c.id for c in list_campaigns(world.repo, world.keitaro, prefix=PREFIX)] == [ours.id]
    assert world.keitaro.calls == []

    open_campaign(world.repo, world.keitaro, world.uow, made_in_keitaro)  # открыли по ID — появилась в списке
    assert [c.id for c in list_campaigns(world.repo, world.keitaro, prefix=PREFIX)] == [made_in_keitaro, ours.id]


def test_open_any_campaign_imports_it_once(world: World) -> None:
    cid = world.keitaro.create_campaign("test_y_their")

    opened = open_campaign(world.repo, world.keitaro, world.uow, cid)
    commits = world.uow.commits
    again = open_campaign(world.repo, world.keitaro, world.uow, cid)

    assert opened == again
    assert again.keitaro_changes == []
    assert world.keitaro.calls.count("get_campaign") == 2  # каждое открытие сверяется с Keitaro
    assert world.uow.commits == commits  # изменений нет — в БД не пишем


def test_open_unknown_campaign(world: World) -> None:
    with pytest.raises(CampaignNotFound):
        open_campaign(world.repo, world.keitaro, world.uow, CampaignId(404))


def test_open_without_draft_syncs_changes_made_in_keitaro(world: World, ours: Campaign) -> None:
    world.keitaro.edit_stream(offers_stream(ours), [PublishedOffer(FLEXACIL, 60), PublishedOffer(OTHER, 40)])

    opened = open_campaign(world.repo, world.keitaro, world.uow, ours.id)

    assert opened.keitaro_changes == []
    shares = [(a.offer.id, a.desired.share, a.status) for a in opened.campaign.streams[1].assignments]
    assert shares == [(FLEXACIL.id, 60, AssignmentStatus.ACTIVE), (OTHER.id, 40, AssignmentStatus.ACTIVE)]
    assert world.repo.get(ours.id) == opened.campaign  # сохранено


def test_open_with_draft_reports_keitaro_changes_and_keeps_draft(world: World, ours: Campaign) -> None:
    drafted = edit_stream.remove_offer(world.repo, world.uow, ours.id, offers_stream(ours), FLEXACIL.id)
    world.keitaro.edit_stream(offers_stream(ours), [PublishedOffer(FLEXACIL, 70), PublishedOffer(OTHER, 30)])

    opened = open_campaign(world.repo, world.keitaro, world.uow, ours.id)

    assert opened.campaign == drafted  # черновик не тронут
    assert opened.keitaro_changes == [
        f"поток «{ours.streams[1].name}»: вес оффера [{FLEXACIL.id}] {FLEXACIL.name} 100% → 70%",
        f"поток «{ours.streams[1].name}»: добавлен оффер [{OTHER.id}] {OTHER.name} (30%)",
    ]


def test_open_campaign_deleted_in_keitaro_shows_what_we_know(world: World, ours: Campaign) -> None:
    world.keitaro.delete_campaign(ours.id)

    opened = open_campaign(world.repo, world.keitaro, world.uow, ours.id)

    assert opened.campaign == world.repo.get(ours.id)
    assert opened.keitaro_changes == ["кампания удалена в Keitaro"]


# ---------- команды: локальные, Keitaro не трогают ----------


def test_edit_is_saved_as_draft_and_keitaro_untouched(world: World, ours: Campaign) -> None:
    edited = add_other(world, ours)

    stored = world.repo.get(ours.id)
    assert stored is not None and stored.has_draft
    assert stored == edited
    assert in_keitaro(world, ours) == {FLEXACIL.id: 100}


def test_added_offer_name_comes_from_keitaro(world: World, ours: Campaign) -> None:
    edited = add_other(world, ours)
    assert edited.stream(offers_stream(ours)).assignments[-1].offer == OTHER

    with pytest.raises(OfferNotFound):
        edit_stream.add_offer(world.repo, world.keitaro, world.uow, ours.id, offers_stream(ours), OfferId(1))


def test_domain_error_saves_nothing(world: World, ours: Campaign) -> None:
    before = world.repo.get(ours.id)

    with pytest.raises(InvalidShare):
        edit_stream.pin(world.repo, world.uow, ours.id, offers_stream(ours), FLEXACIL.id, 101)

    assert world.repo.get(ours.id) == before


def test_empty_stream_is_not_pushed(world: World, ours: Campaign) -> None:
    edit_stream.remove_offer(world.repo, world.uow, ours.id, offers_stream(ours), FLEXACIL.id)

    with pytest.raises(EmptyStreamPush):
        push(world, ours)
    assert in_keitaro(world, ours) == {FLEXACIL.id: 100}


def test_cancel_returns_what_was_discarded(world: World, ours: Campaign) -> None:
    add_other(world, ours)

    campaign, changes = edit_stream.cancel_stream(world.repo, world.uow, ours.id, offers_stream(ours))

    assert {c.offer.id for c in changes} == {FLEXACIL.id, OTHER.id}
    assert not campaign.has_draft


# ---------- Fetch (FR-2.2, FR-2.3a) ----------


def test_fetch_picks_up_manual_change_in_keitaro(world: World, ours: Campaign) -> None:
    world.keitaro.edit_stream(offers_stream(ours), [PublishedOffer(FLEXACIL, 60), PublishedOffer(OTHER, 40)])

    campaign = fetch_streams(world.repo, world.keitaro, world.uow, ours.id)

    shares = {a.offer.id: a.desired.share for a in campaign.stream(offers_stream(ours)).assignments}
    assert shares == {FLEXACIL.id: 60, OTHER.id: 40}
    assert not campaign.has_draft


def test_fetch_with_draft_needs_confirmation(world: World, ours: Campaign) -> None:
    add_other(world, ours)

    with pytest.raises(CampaignHasDrafts):
        fetch_streams(world.repo, world.keitaro, world.uow, ours.id)
    assert world.repo.get(ours.id).has_draft  # type: ignore[union-attr]  # ничего не потеряно

    campaign = fetch_streams(world.repo, world.keitaro, world.uow, ours.id, discard_drafts=True)
    assert not campaign.has_draft


# ---------- Push (FR-2.13, FR-2.14) ----------


def test_push_publishes_and_clears_draft(world: World, ours: Campaign) -> None:
    add_other(world, ours)

    campaign = push(world, ours)

    assert in_keitaro(world, ours) == {FLEXACIL.id: 50, OTHER.id: 50}
    assert not campaign.has_draft
    assert world.repo.get(ours.id) == campaign
    statuses = {a.offer.id: a.status for a in campaign.stream(offers_stream(ours)).assignments}
    assert statuses == {FLEXACIL.id: AssignmentStatus.ACTIVE, OTHER.id: AssignmentStatus.ACTIVE}


def test_push_failure_keeps_draft(world: World, ours: Campaign) -> None:
    add_other(world, ours)
    world.keitaro.fail_on = {"publish_offers"}

    with pytest.raises(KeitaroError):
        push(world, ours)
    assert world.repo.get(ours.id).has_draft  # type: ignore[union-attr]


def test_push_not_confirmed_keeps_draft(world: World, ours: Campaign, monkeypatch: pytest.MonkeyPatch) -> None:
    add_other(world, ours)
    monkeypatch.setattr(world.keitaro, "publish_offers", lambda stream_id, offers: None)  # Keitaro «промолчал»

    with pytest.raises(PushNotConfirmed) as exc:
        push(world, ours)

    assert exc.value.differences == [
        f"у оффера [{FLEXACIL.id}] вес 100% вместо 50%",
        f"оффера [{OTHER.id}] нет в потоке",
    ]
    assert world.repo.get(ours.id).has_draft  # type: ignore[union-attr]


def test_push_to_foreign_campaign_is_forbidden(world: World) -> None:
    cid = world.keitaro.create_campaign("test_y_their")
    campaign = open_campaign(world.repo, world.keitaro, world.uow, cid).campaign

    with pytest.raises(NotOurCampaign):
        push_stream(world.repo, world.keitaro, world.uow, cid, StreamId(1), prefix=PREFIX)
    assert "publish_offers" not in world.keitaro.calls
    assert campaign.streams == []
