"""Trading engine — player-for-player (+cash) trades with full validation.

Pure functions over room-shaped participant dicts:
    {"name", "budget", "squad": [{"name","role","team","buy_price",...}]}

A trade: ``p_from`` gives ``give_players`` + ``give_cash`` and receives
``get_players`` + ``get_cash`` from ``p_to``. Budgets and squad caps are enforced
on both sides server-side, so neither party can overspend or overfill.
"""

from __future__ import annotations

from typing import Optional


class TradeError(Exception):
    """A trade was rejected (message is user-facing)."""


def _entry(participant: dict, player_name: str) -> Optional[dict]:
    return next(
        (e for e in participant.get("squad", []) if e["name"].lower() == player_name.lower()),
        None,
    )


def validate_trade(
    p_from: dict,
    p_to: dict,
    give_players: list[str],
    get_players: list[str],
    give_cash: int = 0,
    get_cash: int = 0,
    *,
    max_squad: int = 30,
) -> list[str]:
    """Return a list of error strings (empty == valid)."""
    errors: list[str] = []
    give_cash = max(0, int(give_cash))
    get_cash = max(0, int(get_cash))

    for name in give_players:
        if _entry(p_from, name) is None:
            errors.append(f"{p_from['name']} doesn't own {name}.")
    for name in get_players:
        if _entry(p_to, name) is None:
            errors.append(f"{p_to['name']} doesn't own {name}.")

    # Net budgets after the swap.
    from_budget = p_from.get("budget", 0) - give_cash + get_cash
    to_budget = p_to.get("budget", 0) - get_cash + give_cash
    if from_budget < 0:
        errors.append(f"{p_from['name']} cannot afford {give_cash}M.")
    if to_budget < 0:
        errors.append(f"{p_to['name']} cannot afford {get_cash}M.")

    # Net squad sizes after the swap.
    from_size = len(p_from.get("squad", [])) - len(give_players) + len(get_players)
    to_size = len(p_to.get("squad", [])) - len(get_players) + len(give_players)
    if from_size > max_squad:
        errors.append(f"{p_from['name']} would exceed the squad limit ({max_squad}).")
    if to_size > max_squad:
        errors.append(f"{p_to['name']} would exceed the squad limit ({max_squad}).")

    # No donations: a trade must involve at least one player on either side.
    if not give_players and not get_players:
        errors.append("Trades must involve at least one player (no cash-only donations).")
    return errors


def apply_trade(
    p_from: dict,
    p_to: dict,
    give_players: list[str],
    get_players: list[str],
    give_cash: int = 0,
    get_cash: int = 0,
    *,
    max_squad: int = 30,
) -> dict:
    """Validate then execute the trade in place. Returns a transaction record.

    Raises :class:`TradeError` if invalid.
    """
    errors = validate_trade(p_from, p_to, give_players, get_players,
                            give_cash, get_cash, max_squad=max_squad)
    if errors:
        raise TradeError(" ".join(errors))

    give_cash = max(0, int(give_cash))
    get_cash = max(0, int(get_cash))

    # Move players (mark acquired_via=trade).
    for name in give_players:
        e = _entry(p_from, name)
        p_from["squad"].remove(e)
        e = {**e, "acquired_via": "trade"}
        p_to["squad"].append(e)
    for name in get_players:
        e = _entry(p_to, name)
        p_to["squad"].remove(e)
        e = {**e, "acquired_via": "trade"}
        p_from["squad"].append(e)

    p_from["budget"] = p_from.get("budget", 0) - give_cash + get_cash
    p_to["budget"] = p_to.get("budget", 0) - get_cash + give_cash

    return {
        "type": "trade",
        "from": p_from["name"],
        "to": p_to["name"],
        "give_players": list(give_players),
        "get_players": list(get_players),
        "give_cash": give_cash,
        "get_cash": get_cash,
    }
