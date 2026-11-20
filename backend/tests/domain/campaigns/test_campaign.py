import pytest

from app.domain.campaigns import (
    AssignmentStatus,
    Campaign,
    KeitaroCampaign,
    KeitaroStream,
    PublishedOffer,
    StreamKind,
)
from app.domain.campaigns.errors import CampaignHasDrafts, NotAnOffersStream, StreamNotInCampaign
from app.domain.common.ids import CampaignId, OfferId, StreamId
from app.domain.offers.offer_ref import OfferRef

OFFER = OfferRef(OfferId(18813), "Flexacil")
OTHER = OfferRef(OfferId(25327), "Other")
GEO, OFFERS = StreamId(1), StreamId(2)


def keitaro(*offers: tuple[OfferRef, int], with_geo: bool = True) -> KeitaroCampaign:
    """Снимок кампании как после создаватора: гео-поток без офферов + поток с офферами."""
    streams = [KeitaroStream(OFFERS, "Offers", 2, tuple(PublishedOffer(o, s) for o, s in offers))]
    if with_geo:
        streams.insert(0, KeitaroStream(GEO, "Geo AU → Google", 1))
    return KeitaroCampaign(CampaignId(7), "test_x_promo", "Abc123", "https://kylovoa.com/", tuple(streams))


@pytest.fixture
def campaign() -> Campaign:
    return Campaign.from_keitaro(keitaro((OFFER, 100)))


def test_campaign_from_keitaro(campaign: Campaign) -> None:
    assert [s.kind for s in campaign.streams] == [StreamKind.OTHER, StreamKind.OFFERS]
    assert campaign.tracker_url == "https://kylovoa.com/Abc123"
    assert not campaign.has_draft


def test_commands_go_through_root(campaign: Campaign) -> None:
    campaign.add_offer(OFFERS, OTHER)

    assert campaign.has_draft
    assert list(campaign.draft_changes()) == [OFFERS]
    assert [(p.offer.id, p.share) for p in campaign.offers_to_publish(OFFERS)] == [(18813, 50), (25327, 50)]

    campaign.mark_published(OFFERS)
    assert not campaign.has_draft


def test_unknown_stream_is_rejected(campaign: Campaign) -> None:
    with pytest.raises(StreamNotInCampaign):
        campaign.add_offer(StreamId(999), OTHER)


def test_geo_stream_is_not_editable(campaign: Campaign) -> None:
    with pytest.raises(NotAnOffersStream):
        campaign.add_offer(GEO, OTHER)


def test_fetch_with_drafts_requires_confirmation(campaign: Campaign) -> None:
    campaign.add_offer(OFFERS, OTHER)

    with pytest.raises(CampaignHasDrafts) as exc:
        campaign.sync_from_keitaro(keitaro((OFFER, 100)))
    assert exc.value.changes_count == 2  # OTHER добавлен, вес OFFER 100 -> 50
    assert campaign.has_draft  # ничего не тронуто

    campaign.sync_from_keitaro(keitaro((OFFER, 100)), discard_drafts=True)
    assert not campaign.has_draft
    assert [a.offer.id for a in campaign.stream(OFFERS).assignments] == [OFFER.id]


def test_fetch_adds_new_and_drops_vanished_streams(campaign: Campaign) -> None:
    campaign.sync_from_keitaro(keitaro((OFFER, 100), with_geo=False))
    assert [s.id for s in campaign.streams] == [OFFERS]

    campaign.sync_from_keitaro(keitaro((OFFER, 100)))
    assert [s.id for s in campaign.streams] == [GEO, OFFERS]


def test_fetch_archives_offer_deleted_in_keitaro(campaign: Campaign) -> None:
    campaign.add_offer(OFFERS, OTHER)
    campaign.mark_published(OFFERS)

    campaign.sync_from_keitaro(keitaro((OTHER, 100)))

    statuses = {a.offer.id: a.status for a in campaign.stream(OFFERS).assignments}
    assert statuses == {OFFER.id: AssignmentStatus.REMOVED, OTHER.id: AssignmentStatus.ACTIVE}


def test_tracker_url() -> None:
    c = Campaign(CampaignId(1), "n", "VrfMdGff", "https://kylovoa.com/")
    assert c.tracker_url == "https://kylovoa.com/VrfMdGff"
    assert Campaign(CampaignId(1), "n", "a", None).tracker_url is None


def test_campaign_is_ours_by_name_prefix() -> None:
    assert Campaign(CampaignId(1), "test_x_promo", "a", None).is_ours("test_x_")
    assert not Campaign(CampaignId(1), "test_y_promo", "a", None).is_ours("test_x_")
    assert not Campaign(CampaignId(1), "promo", "a", None).is_ours("")  # префикс не настроен — «наших» нет


def test_fetch_with_discard_after_drift_keeps_pinned_share(campaign: Campaign) -> None:
    """FR-2.15: после повторных Fetch закреплённый вес — тот, что задал пользователь."""
    campaign.add_offer(OFFERS, OTHER)
    campaign.pin(OFFERS, OFFER.id, 70)
    campaign.mark_published(OFFERS)
    campaign.sync_from_keitaro(keitaro((OFFER, 60), (OTHER, 40)))  # руками поменяли в Keitaro
    campaign.unpin(OFFERS, OTHER.id)  # любая локальная правка — черновик
    campaign.pin(OFFERS, OTHER.id, 30)

    with pytest.raises(CampaignHasDrafts):
        campaign.sync_from_keitaro(keitaro((OFFER, 60), (OTHER, 40)))
    campaign.sync_from_keitaro(keitaro((OFFER, 60), (OTHER, 40)), discard_drafts=True)

    shares = {a.offer.id: (a.desired.share, a.desired.pinned) for a in campaign.stream(OFFERS).assignments}
    assert shares == {OFFER.id: (70, True), OTHER.id: (30, False)}


def test_fetch_adopts_draft_that_is_already_in_keitaro(campaign: Campaign) -> None:
    """Push прошёл, а сохранить не удалось: Fetch не спрашивает и не откатывает (FR-2.13)."""
    campaign.add_offer(OFFERS, OTHER)
    campaign.pin(OFFERS, OTHER.id, 70)

    campaign.sync_from_keitaro(keitaro((OFFER, 30), (OTHER, 70)))  # без discard_drafts

    assert not campaign.has_draft
    pinned = {a.offer.id: a.desired.pinned for a in campaign.stream(OFFERS).assignments}
    assert pinned == {OFFER.id: False, OTHER.id: True}
