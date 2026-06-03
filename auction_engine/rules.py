"""Bid-increment and validation rules, ported verbatim from the legacy app.

Legacy reference (`streamlit_app.py` lines ~1019-1061):

    if current_bid >= 100:   increment = 10
    elif current_bid >= 50:  increment = 5
    else:                    increment = 1
    min_bid = max(5, current_bid + increment)

    # increment legality on the submitted amount:
    if bid_amount > 100 and bid_amount % 10 != 0:   invalid
    elif bid_amount >= 50 and bid_amount % 5 != 0:  invalid

These are kept as free functions so they can be unit-tested in isolation and reused
by the UI to render min-bid hints.
"""

from __future__ import annotations


def increment_for(current_bid: int) -> int:
    """The bid step at a given current bid level."""
    if current_bid >= 100:
        return 10
    if current_bid >= 50:
        return 5
    return 1


def min_next_bid(current_bid: int, floor: int = 5) -> int:
    """Smallest legal next bid given the current bid.

    With no bids yet (``current_bid == 0``) this is ``max(floor, 1)`` i.e. the
    ``floor`` (legacy first-bid minimum of 5).
    """
    return max(floor, current_bid + increment_for(current_bid))


def increment_is_legal(amount: int) -> bool:
    """Whether ``amount`` respects the coarse-increment rule for its size.

    Bids above 100 must be multiples of 10; bids of 50 or more must be multiples
    of 5. (Below 50 any whole number is allowed.) Matches legacy exactly,
    including the ``> 100`` / ``>= 50`` boundaries.
    """
    if amount > 100 and amount % 10 != 0:
        return False
    if amount >= 50 and amount % 5 != 0:
        return False
    return True


def increment_error_message(amount: int) -> str | None:
    """Human-readable reason ``amount`` is an illegal increment, or ``None``."""
    if amount > 100 and amount % 10 != 0:
        return "Bids above 100 must be in increments of 10."
    if amount >= 50 and amount % 5 != 0:
        return "Bids of 50 or above must be in increments of 5."
    return None
