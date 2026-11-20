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
    ConcurrencyConflict,
    KeitaroError,
    NotOurCampaign,
    OfferNotFound,
    PushNotConfirmed,
    StreamChangedInKeitaro,
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


def test_open_syncs_when_only_pinned_share_drifted(world: World, ours: Campaign) -> None:
    """Закреплённый вес, поменянный в Keitaro, — не черновик: открытие синхронизирует кампанию (FR-2.9a)."""
    add_other(world, ours)
    edit_stream.pin(world.repo, world.uow, ours.id, offers_stream(ours), OTHER.id, 70)
    push(world, ours)
    world.keitaro.edit_stream(offers_stream(ours), [PublishedOffer(FLEXACIL, 50), PublishedOffer(OTHER, 50)])
    open_campaign(world.repo, world.keitaro, world.uow, ours.id)  # закрепление разошлось с Keitaro — поток жёлтый
    world.keitaro.edit_stream(offers_stream(ours), [PublishedOffer(FLEXACIL, 40), PublishedOffer(OTHER, 60)])

    opened = open_campaign(world.repo, world.keitaro, world.uow, ours.id)

    assert opened.keitaro_changes == []
    keitaro_shares = {a.offer.id: a.published.share for a in opened.campaign.streams[1].assignments}  # type: ignore[union-attr]
    assert keitaro_shares == {FLEXACIL.id: 40, OTHER.id: 60}
    pinned = {a.offer.id: (a.desired.share, a.desired.pinned) for a in opened.campaign.streams[1].assignments}
    assert pinned == {FLEXACIL.id: (30, False), OTHER.id: (70, True)}


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


def test_failed_push_releases_marker_without_losing_draft(world: World, ours: Campaign) -> None:
    before = add_other(world, ours)
    world.keitaro.fail_on = {'publish_offers'}
    with pytest.raises(KeitaroError):
        push(world, ours)
    after = world.repo.get(ours.id)
    assert after.push_in_progress is None
    assert after.streams == before.streams


def test_failed_cleanup_is_recoverable_after_lease_expiry(world: World, ours: Campaign, monkeypatch) -> None:
    from datetime import timedelta
    from app.application.errors import PushInProgress
    add_other(world, ours)
    real_commit = world.uow.commit
    count = 0
    def down_after_claim():
        nonlocal count
        count += 1
        if count >= 2:
            raise RuntimeError('database unavailable')
        real_commit()
    with monkeypatch.context() as patch:
        patch.setattr(world.uow, 'commit', down_after_claim)
        with pytest.raises(RuntimeError):
            push(world, ours)
    marker = world.repo.get(ours.id).push_in_progress
    assert marker is not None
    with pytest.raises(PushInProgress):
        fetch_streams(world.repo, world.keitaro, world.uow, ours.id)
    monkeypatch.setattr('app.application.editor.push_state.utc_now', lambda: marker.started_at + timedelta(minutes=6))
    recovered = fetch_streams(world.repo, world.keitaro, world.uow, ours.id)
    assert recovered.push_in_progress is None and not recovered.has_draft


def test_push_preserves_parallel_edits_of_another_stream(world: World, ours: Campaign, monkeypatch) -> None:
    from app.domain.campaigns import KeitaroStream
    sid = StreamId(9999)
    world.keitaro._add_stream(ours.id, KeitaroStream(sid, 'Another offers stream', 3, (PublishedOffer(FLEXACIL, 100),)))
    fetch_streams(world.repo, world.keitaro, world.uow, ours.id)
    add_other(world, ours)
    publish = world.keitaro.publish_offers
    def edit_during_publish(stream_id, offers, *, current=None):
        edit_stream.pin(world.repo, world.uow, ours.id, sid, FLEXACIL.id, 100)
        publish(stream_id, offers, current=current)
    monkeypatch.setattr(world.keitaro, 'publish_offers', edit_during_publish)
    result = push(world, ours)
    assert result.push_in_progress is None
    assert not result.stream(offers_stream(ours)).has_draft
    assert result.stream(sid).assignments[0].desired.pinned


def test_failed_old_push_does_not_clear_another_owners_marker(world: World, ours: Campaign, monkeypatch) -> None:
    from datetime import UTC, datetime
    from app.domain.campaigns import PushLease
    add_other(world, ours)
    publish = world.keitaro.publish_offers
    def replace_owner(stream_id, offers, *, current=None):
        publish(stream_id, offers, current=current)
        campaign = world.repo.get(ours.id)
        campaign.push_in_progress = PushLease(stream_id, datetime.now(UTC), 'another-owner')
        world.repo.save(campaign)
        world.uow.commit()
    monkeypatch.setattr(world.keitaro, 'publish_offers', replace_owner)
    with pytest.raises(ConcurrencyConflict):
        push(world, ours)
    assert world.repo.get(ours.id).push_in_progress.token == 'another-owner'


def test_delayed_old_push_cannot_put_after_expiry_and_takeover(world: World, ours: Campaign, monkeypatch) -> None:
    from datetime import UTC, datetime, timedelta
    now = [datetime.now(UTC)]
    monkeypatch.setattr('app.application.editor.push_state.utc_now', lambda: now[0])
    add_other(world, ours)
    get_stream = world.keitaro.get_stream
    delayed = False
    def delayed_read(sid):
        nonlocal delayed
        snapshot = get_stream(sid)
        if not delayed:
            delayed = True
            now[0] += timedelta(minutes=6)
            pin_other(world, ours, 80)
            push_stream(world.repo, world.keitaro, world.uow, ours.id, sid, prefix=PREFIX, clock=lambda: now[0])
        return snapshot
    monkeypatch.setattr(world.keitaro, 'get_stream', delayed_read)
    with pytest.raises(ConcurrencyConflict):
        push_stream(world.repo, world.keitaro, world.uow, ours.id, offers_stream(ours), prefix=PREFIX, clock=lambda: now[0])
    assert world.keitaro.calls.count('publish_offers') == 1
    assert in_keitaro(world, ours) == {FLEXACIL.id: 20, OTHER.id: 80}
    saved = world.repo.get(ours.id)
    assert not saved.has_draft and saved.push_in_progress is None


def test_push_requires_time_reserve_before_put(world: World, ours: Campaign, monkeypatch) -> None:
    from datetime import UTC, datetime, timedelta
    now = [datetime.now(UTC)]
    add_other(world, ours)
    get_stream = world.keitaro.get_stream
    def slow_read(sid):
        now[0] += timedelta(seconds=250)  # TTL 300, оставшихся 50 с меньше резерва 80
        return get_stream(sid)
    monkeypatch.setattr(world.keitaro, 'get_stream', slow_read)
    with pytest.raises(ConcurrencyConflict):
        push_stream(world.repo, world.keitaro, world.uow, ours.id, offers_stream(ours), prefix=PREFIX, clock=lambda: now[0])
    assert 'publish_offers' not in world.keitaro.calls
    assert world.repo.get(ours.id).push_in_progress is None
    assert world.repo.get(ours.id).has_draft


def test_only_one_push_claim_wins_for_same_version(world: World, ours: Campaign, monkeypatch) -> None:
    seen = add_other(world, ours).version
    save = world.repo.save
    competing = False
    def race(campaign):
        nonlocal competing
        if not competing:
            competing = True
            push_stream(world.repo, world.keitaro, world.uow, ours.id, offers_stream(ours),
                        prefix=PREFIX, expected_version=seen)
        save(campaign)
    monkeypatch.setattr(world.repo, 'save', race)
    with pytest.raises(ConcurrencyConflict):
        push_stream(world.repo, world.keitaro, world.uow, ours.id, offers_stream(ours),
                    prefix=PREFIX, expected_version=seen)
    assert world.keitaro.calls.count('publish_offers') == 1
    assert not world.repo.get(ours.id).has_draft
    assert world.repo.get(ours.id).push_in_progress is None


def test_live_push_blocks_commands_and_fetch_but_not_open(world: World, ours: Campaign) -> None:
    from datetime import UTC, datetime
    from app.application.errors import PushInProgress
    from app.domain.campaigns import PushLease
    campaign = add_other(world, ours)
    campaign.push_in_progress = PushLease(offers_stream(ours), datetime.now(UTC), 'live')
    world.repo.save(campaign)
    world.uow.commit()
    world.keitaro.calls.clear()
    with pytest.raises(PushInProgress):
        push(world, ours)
    with pytest.raises(PushInProgress):
        edit_stream.pin(world.repo, world.uow, ours.id, offers_stream(ours), OTHER.id, 80)
    with pytest.raises(PushInProgress):
        edit_stream.add_offer(world.repo, world.keitaro, world.uow, ours.id, offers_stream(ours), OTHER.id)
    with pytest.raises(PushInProgress):
        fetch_streams(world.repo, world.keitaro, world.uow, ours.id)
    assert open_campaign(world.repo, world.keitaro, world.uow, ours.id).campaign.push_in_progress.token == 'live'
    assert world.keitaro.calls == []


def test_expired_push_marker_allows_push_and_fetch_recovery(world: World, ours: Campaign) -> None:
    from datetime import UTC, datetime, timedelta
    from app.domain.campaigns import PushLease
    campaign = add_other(world, ours)
    old = datetime.now(UTC) - timedelta(minutes=6)
    campaign.push_in_progress = PushLease(offers_stream(ours), old, 'dead')
    world.repo.save(campaign)
    world.uow.commit()
    assert push(world, ours).push_in_progress is None
    changed = pin_other(world, ours, 80)
    changed.push_in_progress = PushLease(offers_stream(ours), old, 'dead-after-put')
    world.repo.save(changed)
    world.uow.commit()
    world.keitaro.edit_stream(offers_stream(ours), changed.offers_to_publish(offers_stream(ours)))
    recovered = fetch_streams(world.repo, world.keitaro, world.uow, ours.id)
    assert recovered.push_in_progress is None and not recovered.has_draft
    assert next(a for a in recovered.stream(offers_stream(ours)).assignments if a.offer.id == OTHER.id).desired.pinned


def test_push_rejects_stream_now_owned_by_another_campaign(world: World, ours: Campaign) -> None:
    from dataclasses import replace
    from app.domain.campaigns.errors import StreamNotInCampaign
    add_other(world, ours)
    original = world.keitaro.campaigns[ours.id]
    moved = original.streams[1]
    foreign = world.keitaro.create_campaign('other_campaign')
    world.keitaro.campaigns[foreign] = replace(world.keitaro.campaigns[foreign], streams=(moved,))
    world.keitaro.campaigns[ours.id] = replace(original, streams=(original.streams[0],))
    world.keitaro.calls.clear()
    with pytest.raises(StreamNotInCampaign):
        push(world, ours)
    assert 'publish_offers' not in world.keitaro.calls
    assert world.repo.get(ours.id).push_in_progress is None


def test_push_not_confirmed_keeps_draft(world: World, ours: Campaign, monkeypatch: pytest.MonkeyPatch) -> None:
    add_other(world, ours)
    monkeypatch.setattr(world.keitaro, "publish_offers", lambda stream_id, offers, current=None: None)  # Keitaro «промолчал»

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


# ---------- Push прошёл в Keitaro, а сохранить не удалось ----------


def pin_other(world: World, c: Campaign, share: int) -> Campaign:
    return edit_stream.pin(world.repo, world.uow, c.id, offers_stream(c), OTHER.id, share)


def test_commit_failure_after_push_is_healed_by_fetch(
    world: World, ours: Campaign, monkeypatch: pytest.MonkeyPatch
) -> None:
    add_other(world, ours)
    pin_other(world, ours, 70)

    real_commit = world.uow.commit
    commit_attempts = 0

    def broken_commit() -> None:
        nonlocal commit_attempts
        commit_attempts += 1
        if commit_attempts == 2:
            raise RuntimeError("БД недоступна")
        real_commit()

    with monkeypatch.context() as m:
        m.setattr(world.uow, "commit", broken_commit)
        with pytest.raises(RuntimeError):
            push(world, ours)
    world.uow.rollback()  # конец запроса: несохранённое пропадает, как при закрытии Session
    assert in_keitaro(world, ours) == {FLEXACIL.id: 30, OTHER.id: 70}  # Keitaro уже принял
    assert world.repo.get(ours.id).has_draft  # type: ignore[union-attr]

    campaign = fetch_streams(world.repo, world.keitaro, world.uow, ours.id)  # без подтверждения

    assert not campaign.has_draft
    shares = {a.offer.id: (a.desired.share, a.desired.pinned) for a in campaign.stream(offers_stream(ours)).assignments}
    assert shares == {FLEXACIL.id: (30, False), OTHER.id: (70, True)}  # закрепление не потеряно


def test_concurrent_save_after_push_is_retried(world: World, ours: Campaign, monkeypatch: pytest.MonkeyPatch) -> None:
    add_other(world, ours)
    real_save = world.repo.save
    attempts: list[int] = []

    def save_conflicting_once(campaign: Campaign) -> None:
        attempts.append(campaign.version)
        if len(attempts) == 2:
            raise ConcurrencyConflict(campaign.id)
        real_save(campaign)

    monkeypatch.setattr(world.repo, "save", save_conflicting_once)

    campaign = push(world, ours)

    assert len(attempts) == 3
    assert not campaign.has_draft
    assert not world.repo.get(ours.id).has_draft  # type: ignore[union-attr]


def test_concurrent_change_of_pushed_stream_is_reported(
    world: World, ours: Campaign, monkeypatch: pytest.MonkeyPatch
) -> None:
    add_other(world, ours)
    real_save = world.repo.save

    def other_tab_wins(campaign: Campaign) -> None:
        if campaign.push_in_progress is not None:  # захват проходит
            real_save(campaign)
            return
        monkeypatch.setattr(world.repo, "save", real_save)
        changed = world.repo.get(campaign.id)
        changed.pin(offers_stream(ours), OTHER.id, 80)  # имитация сторонней записи в обход команд
        real_save(changed)
        world.uow.commit()
        raise ConcurrencyConflict(campaign.id)

    monkeypatch.setattr(world.repo, "save", other_tab_wins)

    with pytest.raises(ConcurrencyConflict):
        push(world, ours)
    assert world.repo.get(ours.id).has_draft  # type: ignore[union-attr]


# ---------- версия, которую видел пользователь (If-Match) ----------


def test_stale_version_is_rejected(world: World, ours: Campaign) -> None:
    seen = world.repo.get(ours.id).version  # type: ignore[union-attr]
    add_other(world, ours)  # другая вкладка

    with pytest.raises(ConcurrencyConflict):
        edit_stream.cancel_stream(world.repo, world.uow, ours.id, offers_stream(ours), expected_version=seen)
    with pytest.raises(ConcurrencyConflict):
        fetch_streams(world.repo, world.keitaro, world.uow, ours.id, discard_drafts=True, expected_version=seen)
    assert world.repo.get(ours.id).has_draft  # type: ignore[union-attr]


def test_push_rejects_campaign_renamed_outside_prefix(world: World, ours: Campaign) -> None:
    from dataclasses import replace

    add_other(world, ours)
    world.keitaro.campaigns[ours.id] = replace(world.keitaro.campaigns[ours.id], name="foreign_campaign")
    open_campaign(world.repo, world.keitaro, world.uow, ours.id)
    world.keitaro.calls.clear()

    with pytest.raises(NotOurCampaign):
        push(world, ours)

    assert "publish_offers" not in world.keitaro.calls
    assert world.repo.get(ours.id).has_draft


def test_push_rejects_stream_no_longer_in_campaign(world: World, ours: Campaign) -> None:
    from dataclasses import replace
    from app.domain.campaigns.errors import StreamNotInCampaign

    add_other(world, ours)
    current = world.keitaro.campaigns[ours.id]
    world.keitaro.campaigns[ours.id] = replace(current, streams=(current.streams[0],))
    world.keitaro.calls.clear()
    with pytest.raises(StreamNotInCampaign):
        push(world, ours)
    assert "publish_offers" not in world.keitaro.calls


def test_current_version_is_accepted(world: World, ours: Campaign) -> None:
    campaign = add_other(world, ours)
    cancelled = edit_stream.cancel_stream(
        world.repo, world.uow, ours.id, offers_stream(ours), expected_version=campaign.version
    )[1]
    assert [c.offer.id for c in cancelled] == [FLEXACIL.id, OTHER.id]


# ---------- поток поменяли в Keitaro между Fetch и Push ----------


def test_push_does_not_overwrite_change_made_in_keitaro_after_fetch(world: World, ours: Campaign) -> None:
    add_other(world, ours)  # черновик 50/50
    world.keitaro.edit_stream(offers_stream(ours), [PublishedOffer(FLEXACIL, 70), PublishedOffer(OTHER, 30)])
    world.keitaro.calls.clear()

    with pytest.raises(StreamChangedInKeitaro) as exc:
        push(world, ours)

    assert exc.value.differences == [
        f"в Keitaro у оффера [{FLEXACIL.id}] вес 100% → 70%",
        f"в Keitaro добавлен или включён оффер [{OTHER.id}] (30%)",
    ]
    assert "publish_offers" not in world.keitaro.calls
    assert in_keitaro(world, ours) == {FLEXACIL.id: 70, OTHER.id: 30}  # правка в Keitaro цела
    stored = world.repo.get(ours.id)
    assert stored is not None and stored.has_draft and stored.push_in_progress is None


def test_push_after_fetch_publishes_again(world: World, ours: Campaign) -> None:
    world.keitaro.edit_stream(offers_stream(ours), [PublishedOffer(FLEXACIL, 70), PublishedOffer(OTHER, 30)])
    fetch_streams(world.repo, world.keitaro, world.uow, ours.id)
    edit_stream.pin(world.repo, world.uow, ours.id, offers_stream(ours), OTHER.id, 60)

    push(world, ours)

    assert in_keitaro(world, ours) == {FLEXACIL.id: 40, OTHER.id: 60}


def test_pin_drift_is_not_reported_as_change_in_keitaro(world: World, ours: Campaign) -> None:
    """Закреплённый вес поменяли в Keitaro, Fetch это уже увидел — Push возвращает закреплённый вес."""
    add_other(world, ours)
    pin_other(world, ours, 70)
    push(world, ours)
    world.keitaro.edit_stream(offers_stream(ours), [PublishedOffer(FLEXACIL, 50), PublishedOffer(OTHER, 50)])
    fetch_streams(world.repo, world.keitaro, world.uow, ours.id)

    push(world, ours)

    assert in_keitaro(world, ours) == {FLEXACIL.id: 30, OTHER.id: 70}


def test_user_can_push_over_change_in_keitaro_without_losing_draft(world: World, ours: Campaign) -> None:
    add_other(world, ours)  # черновик 50/50
    world.keitaro.edit_stream(offers_stream(ours), [PublishedOffer(FLEXACIL, 70), PublishedOffer(OTHER, 30)])
    with pytest.raises(StreamChangedInKeitaro):
        push(world, ours)

    campaign = push_stream(
        world.repo, world.keitaro, world.uow, ours.id, offers_stream(ours), prefix=PREFIX,
        overwrite_keitaro_changes=True,
    )

    assert in_keitaro(world, ours) == {FLEXACIL.id: 50, OTHER.id: 50}
    assert not campaign.has_draft

