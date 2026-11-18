import pytest

from app.domain.campaigns.errors import PinnedSharesExceed100
from app.domain.campaigns.services.weights import Slot, distribute_shares
from app.domain.common.ids import OfferId


def shares(*pinned: int | None) -> list[int]:
    """Хелпер: distribute_shares для участников 1..N, pinned[i] — закреплённый вес или None."""
    slots = [Slot(OfferId(i + 1), p) for i, p in enumerate(pinned)]
    return list(distribute_shares(slots).values())


@pytest.mark.parametrize(
    ("count", "expected"),
    [
        (1, [100]),
        (2, [50, 50]),
        (3, [34, 33, 33]),
        (4, [25, 25, 25, 25]),
        (7, [15, 15, 14, 14, 14, 14, 14]),
    ],
)
def test_equal_split_gives_extra_units_to_first(count: int, expected: list[int]) -> None:
    assert shares(*[None] * count) == expected


def test_pinned_keeps_value_and_rest_split_among_free() -> None:
    assert shares(50, None, None, None) == [50, 17, 17, 16]


def test_pinned_in_the_middle_does_not_take_extra_unit() -> None:
    assert shares(None, 25, None, None) == [25, 25, 25, 25]
    assert shares(None, 40, None) == [30, 40, 30]


def test_all_pinned_returned_as_is_even_if_sum_not_100() -> None:
    assert shares(30, 30) == [30, 30]


def test_pinned_sum_over_100_is_rejected() -> None:
    with pytest.raises(PinnedSharesExceed100):
        shares(60, 50, None)


def test_pinned_100_leaves_zero_for_free() -> None:
    assert shares(100, None, None) == [100, 0, 0]


def test_empty() -> None:
    assert shares() == []
