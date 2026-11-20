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
