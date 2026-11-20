import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from app.application.errors import CampaignAlreadyExists, ConcurrencyConflict
from app.domain.campaigns import Campaign, KeitaroCampaign, KeitaroStream, PublishedOffer
from app.domain.common.ids import CampaignId, OfferId, StreamId
from app.domain.offers.offer_ref import OfferRef
from app.infrastructure.persistence.campaign_repository import SqlCampaignRepository

A, B, C = (OfferRef(OfferId(i), f"Offer {n}") for i, n in [(101, "A"), (102, "B"), (103, "C")])
CID, GEO, OFFERS = CampaignId(500), StreamId(1), StreamId(2)


def make_campaign() -> Campaign:
    snapshot = KeitaroCampaign(
        CID,
        "test_x_promo",
        "Abc123",
        "https://kylovoa.com/",
        (
            KeitaroStream(GEO, "Geo AU → Google", 1),
            KeitaroStream(OFFERS, "Offers", 2, (PublishedOffer(A, 50), PublishedOffer(B, 50))),
        ),
    )
    return Campaign.from_keitaro(snapshot)


def store(factory: sessionmaker[Session], campaign: Campaign) -> None:
    with factory() as s:
        SqlCampaignRepository(s).add(campaign)
        s.commit()


def load(factory: sessionmaker[Session]) -> Campaign:
    with factory() as s:
        campaign = SqlCampaignRepository(s).get(CID)
    assert campaign is not None
    return campaign


def test_aggregate_survives_roundtrip_with_drafts(session_factory: sessionmaker[Session]) -> None:
    campaign = make_campaign()
    campaign.pin(OFFERS, A.id, 60)
    campaign.add_offer(OFFERS, C)  # черновик: pending_add + закрепление
    campaign.remove_offer(OFFERS, B.id)

    store(session_factory, campaign)
    loaded = load(session_factory)

    assert loaded == campaign  # dataclass сравнивает все поля, включая потоки и привязки
    assert loaded.version == 1
    assert loaded.draft_changes() == campaign.draft_changes()


def test_pinned_share_published_by_us_survives_roundtrip(session_factory: sessionmaker[Session]) -> None:
    """Закреплённый вес последнего Push хранится отдельно от веса в Keitaro (Q7, FR-2.15)."""
    campaign = make_campaign()
    campaign.pin(OFFERS, A.id, 60)
    campaign.mark_published(OFFERS)
    keitaro = KeitaroStream(OFFERS, "Offers", 2, (PublishedOffer(A, 30), PublishedOffer(B, 70)))
    campaign.stream(OFFERS).sync_from_keitaro(keitaro)  # вес поменяли руками в Keitaro

    store(session_factory, campaign)
    loaded = load(session_factory)

    assert loaded == campaign
    published = next(a.published for a in loaded.stream(OFFERS).assignments if a.offer.id == A.id)
    assert published is not None and (published.share, published.pinned_share) == (30, 60)


def test_old_document_without_pinned_share_loads(session_factory: sessionmaker[Session]) -> None:
    store(session_factory, make_campaign())
    with session_factory() as s:
        s.execute(text("""
            UPDATE campaigns SET streams = jsonb_set(
                streams, '{streams,1,assignments,0,published}', '{"in_rotation": true, "share": 50, "pinned": false}'
            ) WHERE id = :id
        """), {"id": CID})
        s.commit()

    loaded = load(session_factory)
    assert loaded.stream(OFFERS).assignments[0].published.pinned_share is None  # type: ignore[union-attr]


def test_document_has_schema_version(session_factory: sessionmaker[Session]) -> None:
    store(session_factory, make_campaign())
    with session_factory() as s:
        doc = s.scalar(text("SELECT streams FROM campaigns WHERE id = :id"), {"id": CID})
    assert doc["schema_version"] == 1
    assert [st["kind"] for st in doc["streams"]] == ["other", "offers"]


def test_save_persists_changes_and_bumps_version(session_factory: sessionmaker[Session]) -> None:
    store(session_factory, make_campaign())

    with session_factory() as s:
        repo = SqlCampaignRepository(s)
        campaign = repo.get(CID)
        assert campaign is not None
        campaign.add_offer(OFFERS, C)
        repo.save(campaign)
        s.commit()
        assert campaign.version == 2

    assert {a.offer.id for a in load(session_factory).stream(OFFERS).assignments} == {A.id, B.id, C.id}


def test_get_missing_returns_none(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as s:
        assert SqlCampaignRepository(s).get(CampaignId(404)) is None


def test_add_duplicate_is_rejected(session_factory: sessionmaker[Session]) -> None:
    store(session_factory, make_campaign())
    with session_factory() as s, pytest.raises(CampaignAlreadyExists):
        SqlCampaignRepository(s).add(make_campaign())


def test_concurrent_save_is_rejected(session_factory: sessionmaker[Session]) -> None:
    """Два запроса прочитали v1; первый сохранил v2; второй должен получить конфликт, а не затереть."""
    store(session_factory, make_campaign())

    with session_factory() as s1, session_factory() as s2:
        repo1, repo2 = SqlCampaignRepository(s1), SqlCampaignRepository(s2)
        first, second = repo1.get(CID), repo2.get(CID)
        assert first is not None and second is not None

        first.add_offer(OFFERS, C)
        repo1.save(first)
        s1.commit()

        second.remove_offer(OFFERS, A.id)
        with pytest.raises(ConcurrencyConflict):
            repo2.save(second)

    assert {a.offer.id for a in load(session_factory).stream(OFFERS).assignments} == {A.id, B.id, C.id}


def test_stale_aggregate_is_rejected(session_factory: sessionmaker[Session]) -> None:
    """Агрегат, прочитанный до последней записи, сохранить нельзя (версия разошлась)."""
    store(session_factory, make_campaign())
    stale = load(session_factory)  # version 1

    with session_factory() as s:
        repo = SqlCampaignRepository(s)
        fresh = repo.get(CID)
        assert fresh is not None
        fresh.add_offer(OFFERS, C)
        repo.save(fresh)
        s.commit()  # в БД version 2

    with session_factory() as s, pytest.raises(ConcurrencyConflict):
        stale.remove_offer(OFFERS, A.id)
        SqlCampaignRepository(s).save(stale)


def test_push_releases_transaction_and_row_lock_during_keitaro(session_factory: sessionmaker[Session], monkeypatch) -> None:
    from app.application.editor.edit_stream import pin
    from app.application.editor.push_stream import push_stream
    from app.application.errors import PushInProgress
    from tests.fakes.keitaro_gateway import FakeKeitaroGateway

    campaign = make_campaign()
    campaign.pin(OFFERS, B.id, 70)
    store(session_factory, campaign)
    gateway = FakeKeitaroGateway(campaigns={CID: KeitaroCampaign(
        CID, campaign.name, campaign.alias, campaign.domain_url,
        (KeitaroStream(OFFERS, "Offers", 2, (PublishedOffer(A, 50), PublishedOffer(B, 50))),),
    )})
    probed = False
    with session_factory() as session:
        def checked(method):
            def call(*args, **kwargs):
                nonlocal probed
                assert not session.in_transaction(), "HTTP must run outside a database transaction"
                with session_factory() as other:
                    other.execute(text("SELECT id FROM campaigns WHERE id=:id FOR UPDATE NOWAIT"), {"id": CID})
                    other.rollback()
                if not probed:
                    probed = True
                    with session_factory() as other, pytest.raises(ConcurrencyConflict):
                        push_stream(SqlCampaignRepository(other), gateway, other, CID, OFFERS,
                                    prefix="test_x_", expected_version=campaign.version)
                    with session_factory() as other, pytest.raises(PushInProgress):
                        push_stream(SqlCampaignRepository(other), gateway, other, CID, OFFERS, prefix="test_x_")
                    with session_factory() as other, pytest.raises(PushInProgress):
                        pin(SqlCampaignRepository(other), other, CID, OFFERS, B.id, 80)
                return method(*args, **kwargs)
            return call
        for name in ('get_campaign_name', 'get_stream', 'publish_offers'):
            monkeypatch.setattr(gateway, name, checked(getattr(gateway, name)))
        result = push_stream(SqlCampaignRepository(session), gateway, session, CID, OFFERS,
                             prefix="test_x_", expected_version=campaign.version)
        assert not session.in_transaction()
    assert probed and result.push_in_progress is None and not result.has_draft
    assert gateway.calls.count('publish_offers') == 1
    assert {o.offer.id: o.share for o in gateway.get_campaign(CID).streams[0].offers} == {A.id: 30, B.id: 70}


def test_load_refreshes_previously_read_record(session_factory: sessionmaker[Session]) -> None:
    from app.infrastructure.persistence.records import CampaignRecord

    store(session_factory, make_campaign())
    with session_factory() as first, session_factory() as second:
        cached = first.get(CampaignRecord, CID)  # retain identity-map entry
        changed = SqlCampaignRepository(second).get(CID)
        changed.pin(OFFERS, A.id, 60)
        SqlCampaignRepository(second).save(changed)
        second.commit()
        fresh = SqlCampaignRepository(first).get(CID)
        assert fresh.version == cached.version == changed.version
        assert fresh.stream(OFFERS).assignments[0].desired.share == 60



def test_push_marker_survives_document_roundtrip(session_factory: sessionmaker[Session]) -> None:
    from datetime import UTC, datetime
    from app.domain.campaigns import PushLease
    campaign = make_campaign()
    campaign.push_in_progress = PushLease(OFFERS, datetime(2026, 11, 20, tzinfo=UTC), 'owner-token')
    store(session_factory, campaign)
    assert load(session_factory) == campaign


def test_old_document_without_push_marker_loads(session_factory: sessionmaker[Session]) -> None:
    store(session_factory, make_campaign())
    with session_factory() as session:
        session.execute(text("UPDATE campaigns SET streams=streams - 'push_in_progress' WHERE id=:id"), {'id': CID})
        session.commit()
    assert load(session_factory).push_in_progress is None


def test_only_one_push_claim_can_save_the_same_version(session_factory: sessionmaker[Session]) -> None:
    from datetime import UTC, datetime
    from app.domain.campaigns import PushLease
    store(session_factory, make_campaign())
    with session_factory() as first, session_factory() as second:
        repo1, repo2 = SqlCampaignRepository(first), SqlCampaignRepository(second)
        a, b = repo1.get(CID), repo2.get(CID)
        a.push_in_progress = PushLease(OFFERS, datetime.now(UTC), 'first')
        b.push_in_progress = PushLease(OFFERS, datetime.now(UTC), 'second')
        repo1.save(a)
        first.commit()
        with pytest.raises(ConcurrencyConflict):
            repo2.save(b)
    assert load(session_factory).push_in_progress.token == 'first'


@pytest.mark.parametrize('operation', ['open', 'fetch'])
def test_loading_keitaro_does_not_hold_read_transaction(session_factory: sessionmaker[Session], operation) -> None:
    from app.application.editor.open_campaign import open_campaign
    from app.application.editor.fetch_streams import fetch_streams
    from tests.fakes.keitaro_gateway import FakeKeitaroGateway
    campaign = make_campaign()
    store(session_factory, campaign)
    gateway = FakeKeitaroGateway(campaigns={CID: KeitaroCampaign(
        CID, campaign.name, campaign.alias, campaign.domain_url,
        (KeitaroStream(GEO, 'Geo AU → Google', 1), KeitaroStream(OFFERS, 'Offers', 2, (PublishedOffer(A, 50), PublishedOffer(B, 50)))),
    )})
    with session_factory() as session:
        original = gateway.get_campaign
        def checked(cid):
            assert not session.in_transaction()
            return original(cid)
        gateway.get_campaign = checked
        call = open_campaign if operation == 'open' else fetch_streams
        call(SqlCampaignRepository(session), gateway, session, CID)
