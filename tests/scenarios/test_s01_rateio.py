"""S01 — Rateio de compra parcelada (reference-scenarios.md; RN-005, I-06)."""

import pytest

from apps.money import Money, split_installments


@pytest.mark.parametrize(
    ("total", "count", "expected"),
    [
        (10000, 3, [3334, 3333, 3333]),
        (100000, 7, [14290] + [14285] * 6),
        (60000, 6, [10000] * 6),
    ],
)
def test_s01_resto_na_primeira_parcela(total, count, expected):
    parts = split_installments(Money(total), count)
    assert [p.cents for p in parts] == expected
    assert Money.sum(parts) == Money(total)


def test_s01_resto_na_ultima_parcela():
    parts = split_installments(Money(10000), 3, remainder_on="last")
    assert [p.cents for p in parts] == [3333, 3333, 3334]
