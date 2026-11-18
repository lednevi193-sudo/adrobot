"""Сценарии сущности Stream (внутри агрегата Campaign): видео заказчика + правила из requirements.md."""

import pytest

from app.domain.campaigns.errors import (
    EmptyStreamPush,
    NotAnOffersStream,
    OfferAlreadyInStream,
    OfferIsArchived,
    OfferNotIncluded,
    PinnedSharesExceed100,
    SharesDoNotSumTo100,
)
from app.domain.campaigns import (
    AssignmentStatus as S,
    ChangeKind,
    KeitaroStream,
    PublishedOffer,
    Stream,
)
from app.domain.common.ids import OfferId, StreamId
from app.domain.offers.offer_ref import OfferRef

A, B, C, D = (OfferRef(OfferId(i), name) for i, name in enumerate("ABCD", start=1))


def snapshot(*pairs: tuple[OfferRef, int]) -> KeitaroStream:
    offers = tuple(PublishedOffer(offer, share) for offer, share in pairs)
    return KeitaroStream(StreamId(10), "Offers", 2, offers)


def make_stream(*pairs: tuple[OfferRef, int]) -> Stream:
    return Stream.from_keitaro(snapshot(*pairs))


def view(stream: Stream) -> dict[str, tuple[S, int, bool]]:
    """{имя: (статус, желаемый вес, закреплён)} в порядке добавления."""
    return {
        a.offer.name: (a.status, a.desired.share, a.desired.pinned)
        for a in sorted(stream.assignments, key=lambda a: a.seq)
    }


def push(stream: Stream) -> list[tuple[str, int]]:
    sent = [(p.offer.name, p.share) for p in stream.offers_to_publish()]
    stream.mark_published()
    return sent


@pytest.fixture
def three() -> Stream:
    return make_stream((A, 34), (B, 33), (C, 33))


# ---------- загрузка ----------


def test_stream_from_keitaro_is_clean_and_active(three: Stream) -> None:
    assert not three.is_dirty
    assert view(three) == {"A": (S.ACTIVE, 34, False), "B": (S.ACTIVE, 33, False), "C": (S.ACTIVE, 33, False)}


def test_stream_without_offers_is_opaque_and_not_editable() -> None:
    stream = make_stream()
    with pytest.raises(NotAnOffersStream):
        stream.add_offer(A)


# ---------- добавление (видео: 3 -> 4 оффера по 25%) ----------


def test_add_offer_rebalances_and_makes_stream_dirty(three: Stream) -> None:
    three.add_offer(D)

    assert three.is_dirty
    assert view(three)["D"] == (S.PENDING_ADD, 25, False)
    assert [s for _, s, _ in view(three).values()] == [25, 25, 25, 25]

    assert push(three) == [("A", 25), ("B", 25), ("C", 25), ("D", 25)]
    assert not three.is_dirty
    assert view(three)["D"][0] == S.ACTIVE


def test_cannot_add_same_offer_twice(three: Stream) -> None:
    with pytest.raises(OfferAlreadyInStream):
        three.add_offer(A)


# ---------- удаление, архив, bring back (видео) ----------


def test_remove_published_offer_goes_to_zero_then_to_archive(three: Stream) -> None:
    three.remove_offer(B.id)
    assert view(three)["B"] == (S.PENDING_REMOVE, 0, False)
    assert view(three)["A"][1] + view(three)["C"][1] == 100

    assert push(three) == [("A", 50), ("C", 50)]
    assert view(three)["B"] == (S.REMOVED, 0, False)  # остался у нас в архиве


def test_archived_offer_comes_back_via_bring_back_not_add(three: Stream) -> None:
    three.remove_offer(B.id)
    push(three)

    with pytest.raises(OfferIsArchived):
        three.add_offer(B)

    three.bring_back(B.id)
    assert view(three)["B"][0] == S.PENDING_ADD
    assert push(three) == [("A", 34), ("B", 33), ("C", 33)]


def test_remove_not_yet_published_offer_forgets_it(three: Stream) -> None:
    three.add_offer(D)
    three.remove_offer(D.id)

    assert "D" not in view(three)
    assert not three.is_dirty


def test_bring_back_of_unpublished_removal_restores_clean_state(three: Stream) -> None:
    three.remove_offer(B.id)
    three.bring_back(B.id)
    assert not three.is_dirty


def test_cannot_remove_twice(three: Stream) -> None:
    three.remove_offer(A.id)
    with pytest.raises(OfferNotIncluded):
        three.remove_offer(A.id)


# ---------- закрепление (видео: 25% закреплено, остальные пересчитываются) ----------


def test_pinned_share_survives_add_remove_and_bring_back() -> None:
    stream = make_stream((A, 25), (B, 25), (C, 25), (D, 25))
    stream.pin(A.id)

    stream.remove_offer(B.id)
    assert view(stream)["A"] == (S.ACTIVE, 25, True)
    assert [view(stream)[n][1] for n in "CD"] == [38, 37]

    push(stream)
    stream.bring_back(B.id)
    assert [view(stream)[n][1] for n in "ABCD"] == [25, 25, 25, 25]
    assert view(stream)["A"][2] is True


def test_pin_with_manual_value(three: Stream) -> None:
    three.pin(A.id, 50)
    assert [s for _, s, _ in view(three).values()] == [50, 25, 25]
    assert three.pending_changes()[0].kind == ChangeKind.PIN


def test_pinned_total_over_100_is_rejected(three: Stream) -> None:
    three.pin(A.id, 60)
    with pytest.raises(PinnedSharesExceed100):
        three.pin(B.id, 50)


def test_unpin_returns_to_equal_split(three: Stream) -> None:
    three.pin(A.id, 50)
    push(three)
    three.unpin(A.id)
    assert [s for _, s, _ in view(three).values()] == [34, 33, 33]


def test_removing_pinned_offer_drops_pin(three: Stream) -> None:
    three.pin(A.id, 50)
    push(three)
    three.remove_offer(A.id)
    push(three)
    three.bring_back(A.id)
    assert view(three)["A"] == (S.PENDING_ADD, 34, False)


# ---------- инварианты публикации ----------


def test_cannot_push_empty_stream() -> None:
    stream = make_stream((A, 100))
    stream.remove_offer(A.id)
    with pytest.raises(EmptyStreamPush):
        stream.offers_to_publish()


def test_cannot_push_when_all_pinned_and_sum_not_100() -> None:
    stream = make_stream((A, 50), (B, 50))
    stream.pin(A.id, 30)  # B подстроится до 70
    stream.pin(B.id)
    stream.unpin(A.id)
    stream.pin(A.id, 20)  # B закреплён на 70 -> сумма 90
    with pytest.raises(SharesDoNotSumTo100):
        stream.offers_to_publish()


# ---------- Cancel и список изменений ----------


def test_cancel_reverts_everything_including_pins(three: Stream) -> None:
    before = view(three)
    three.add_offer(D)
    three.remove_offer(B.id)
    three.pin(A.id, 50)

    changes = {c.offer.name: c.kind for c in three.cancel()}

    assert changes == {"A": ChangeKind.PIN, "B": ChangeKind.REMOVE, "C": ChangeKind.SHARE, "D": ChangeKind.ADD}
    assert view(three) == before
    assert not three.is_dirty


def test_cancel_returns_brought_back_offer_to_archive(three: Stream) -> None:
    three.remove_offer(B.id)
    push(three)
    three.bring_back(B.id)

    three.cancel()
    assert view(three)["B"] == (S.REMOVED, 0, False)


# ---------- Fetch: синхронизация с Keitaro (FR-2.3, Q7) ----------


def test_offer_deleted_in_keitaro_goes_to_archive(three: Stream) -> None:
    three.sync_from_keitaro(snapshot((A, 50), (C, 50)))

    assert view(three)["B"] == (S.REMOVED, 0, False)
    assert not three.is_dirty


def test_offer_added_in_keitaro_appears_as_active(three: Stream) -> None:
    three.sync_from_keitaro(snapshot((A, 25), (B, 25), (C, 25), (D, 25)))

    assert view(three)["D"] == (S.ACTIVE, 25, False)
    assert not three.is_dirty


def test_archived_offer_returned_in_keitaro_becomes_active(three: Stream) -> None:
    three.sync_from_keitaro(snapshot((A, 50), (C, 50)))
    three.sync_from_keitaro(snapshot((A, 34), (B, 33), (C, 33)))
    assert view(three)["B"] == (S.ACTIVE, 33, False)


def test_pinned_share_wins_over_manual_change_in_keitaro(three: Stream) -> None:
    three.pin(A.id, 50)
    push(three)  # в Keitaro 50/25/25

    three.sync_from_keitaro(snapshot((A, 20), (B, 40), (C, 40)))

    assert three.is_dirty
    assert [s for _, s, _ in view(three).values()] == [50, 25, 25]
    a = next(x for x in three.assignments if x.offer.id == A.id)
    assert a.published is not None and a.published.share == 20  # подсказка «в Keitaro сейчас 20%»


def test_sync_refreshes_offer_name(three: Stream) -> None:
    renamed = OfferRef(A.id, "A v2")
    three.sync_from_keitaro(snapshot((renamed, 34), (B, 33), (C, 33)))
    assert "A v2" in view(three)
