"""Tests for bid-increment rules (ported verbatim from the legacy app)."""

import pytest

from auction_engine.rules import (
    increment_error_message,
    increment_for,
    increment_is_legal,
    min_next_bid,
)


@pytest.mark.parametrize(
    "current,expected",
    [(0, 1), (5, 1), (49, 1), (50, 5), (75, 5), (99, 5), (100, 10), (250, 10)],
)
def test_increment_for(current, expected):
    assert increment_for(current) == expected


@pytest.mark.parametrize(
    "current,expected",
    [
        (0, 5),    # first bid: max(5, 0+1)
        (4, 5),    # max(5, 4+1) == 5
        (5, 6),    # max(5, 5+1)
        (49, 50),  # 49+1
        (50, 55),  # 50+5
        (95, 100),
        (100, 110),
    ],
)
def test_min_next_bid(current, expected):
    assert min_next_bid(current) == expected


@pytest.mark.parametrize(
    "amount,legal",
    [
        (5, True),
        (49, True),     # below 50, any integer ok
        (50, True),     # multiple of 5
        (52, False),    # >=50 must be multiple of 5
        (55, True),
        (100, True),
        (105, False),   # >100 must be multiple of 10
        (110, True),
        (101, False),
    ],
)
def test_increment_is_legal(amount, legal):
    assert increment_is_legal(amount) is legal


def test_increment_error_message():
    assert "increments of 10" in increment_error_message(105)
    assert "increments of 5" in increment_error_message(52)
    assert increment_error_message(55) is None
