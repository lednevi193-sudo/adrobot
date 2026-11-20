"""Сверка опубликованного состояния обёртки со снимком Keitaro (открытие кампании с черновиком)."""

from dataclasses import replace

from app.domain.campaigns import Campaign, KeitaroStream, changes_in_keitaro
from app.domain.common.ids import StreamId
from tests.domain.campaigns.test_campaign import OFFER, OFFERS, OTHER, keitaro


def test_same_as_keitaro_no_changes() -> None:
    snapshot = keitaro((OFFER, 100))
    assert changes_in_keitaro(Campaign.from_keitaro(snapshot), snapshot) == []


def test_offer_reorder_is_detected_and_synced() -> None:
    campaign = Campaign.from_keitaro(keitaro((OFFER, 50), (OTHER, 50)))
    reordered = keitaro((OTHER, 50), (OFFER, 50))
    assert any("порядок" in change for change in changes_in_keitaro(campaign, reordered))
    campaign.sync_from_keitaro(reordered)
    assert changes_in_keitaro(campaign, reordered) == []
    assert [a.offer.id for a in sorted(campaign.stream(OFFERS).assignments, key=lambda a: a.order)] == [OTHER.id, OFFER.id]


def test_draft_is_not_a_keitaro_change() -> None:
    snapshot = keitaro((OFFER, 100))
    campaign = Campaign.from_keitaro(snapshot)
    campaign.add_offer(OFFERS, OTHER)  # черновик обёртки, в Keitaro его нет — это не «изменение в Keitaro»

    assert changes_in_keitaro(campaign, snapshot) == []


def test_offer_changes_in_stream() -> None:
    campaign = Campaign.from_keitaro(keitaro((OFFER, 60), (OTHER, 40)))

    assert changes_in_keitaro(campaign, keitaro((OFFER, 100))) == [
        "поток «Offers»: вес оффера [18813] Flexacil 60% → 100%",
        "поток «Offers»: удалён оффер [25327] Other",
    ]


def test_stream_and_campaign_changes() -> None:
    campaign = Campaign.from_keitaro(keitaro((OFFER, 100)))
    changed = keitaro((OFFER, 100), with_geo=False)
    offers = replace(changed.streams[0], name="Main", position=1)
    changed = replace(
        changed,
        name="test_x_renamed",
        alias="New",
        streams=(offers, KeitaroStream(StreamId(3), "Fallback", 2)),
    )

    assert changes_in_keitaro(campaign, changed) == [
        "кампания переименована: «test_x_promo» → «test_x_renamed»",
        "изменилась ссылка трекера",
        "поток «Offers» переименован в «Main»",
        "поток «Main» перемещён на позицию 1",
        "новый поток «Fallback»",
        "поток «Geo AU → Google» удалён",
    ]


def test_new_offer_in_keitaro() -> None:
    campaign = Campaign.from_keitaro(keitaro((OFFER, 100)))
    assert changes_in_keitaro(campaign, keitaro((OFFER, 50), (OTHER, 50)))[-1] == (
        "поток «Offers»: добавлен оффер [25327] Other (50%)"
    )
