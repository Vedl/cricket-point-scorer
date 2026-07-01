"""Event → web-push glue.

Thin layer between the Reflex state handlers (which know the room + what just happened)
and ``platform_core.push`` (which delivers). Kept here, not in platform_core, because
it understands the room schema (participants[].user, room.admin). All sends are
fire-and-forget (push.notify_users spawns a daemon thread), so calling these from a
sync event handler never blocks the user's action — and a missing VAPID config makes
them silent no-ops.
"""

from __future__ import annotations

from platform_core import push


def _user_for_team(room: dict, team: str) -> str:
    for p in room.get("participants", []):
        if p.get("name") == team:
            return p.get("user") or ""
    return ""


def _all_room_users(room: dict) -> set[str]:
    users = set()
    if room.get("admin"):
        users.add(room["admin"])
    for p in room.get("participants", []):
        if p.get("user"):
            users.add(p["user"])
    return users


def _others(room: dict, exclude_team: str = "") -> set[str]:
    """Every room user except the one who owns ``exclude_team`` — used for room-wide
    announcements so the actor doesn't get a redundant 'so-and-so did X' about their
    own action (they get a personal confirmation instead)."""
    ex = _user_for_team(room, exclude_team)
    return {u for u in _all_room_users(room) if u and u != ex}


def outbid(room: dict, team: str, player: str, code: str) -> None:
    """The previous high bidder (`team`) just got topped on `player`."""
    user = _user_for_team(room, team)
    if user:
        push.notify_users(
            [user], "🔁 You were outbid",
            f"{player}: someone has topped your bid.",
            f"/bidding?room={code}",
        )


def signed(room: dict, team: str, player: str, amount, code: str) -> None:
    """Personal 'you won X' to the buyer + a room-wide 'team signed X' announcement."""
    user = _user_for_team(room, team)
    if user:
        push.notify_users(
            [user], "✅ Player signed",
            f"You won {player} for {amount}M.",
            f"/bidding?room={code}",
        )
    push.notify_users(
        _others(room, team), "🛒 New signing",
        f"{team} signed {player} for {amount}M.",
        f"/announcements?room={code}",
    )


def signed_many(room: dict, awarded: list[dict], code: str) -> None:
    """`awarded` is the list from bidding_ops.process_expired."""
    for a in awarded or []:
        signed(room, a.get("participant", ""), a.get("player", ""), a.get("amount", ""), code)


def market_bought(room: dict, rec: dict | None, code: str) -> None:
    """A sealed open-market bid was resolved (``rec`` from market_ops.resolve_market)."""
    if not rec:
        return
    signed(room, rec.get("participant", ""), rec.get("player", ""), rec.get("amount", ""), code)


def released(room: dict, team: str, player: str, code: str) -> None:
    push.notify_users(
        _all_room_users(room), "📤 Player released",
        f"{team} released {player}.",
        f"/squads?room={code}",
    )


def trade_done(room: dict, frm: str, to: str, code: str) -> None:
    push.notify_users(
        _all_room_users(room), "🤝 Trade completed",
        f"{frm} ↔ {to}.",
        f"/announcements?room={code}",
    )
