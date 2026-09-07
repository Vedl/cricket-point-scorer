"""Who is allowed to do what in a room.

The UI hides admin controls from non-admins, but hiding a button is not a
permission check: a Reflex event handler is reachable over the websocket whether
or not anything rendered it. Every handler that mutates a room on the admin's
behalf must call :func:`require_room_admin` itself.

This is deliberately framework-free so it can be unit-tested without Reflex.
"""

from __future__ import annotations


class NotAuthorized(Exception):
    """The acting user may not perform this action (message is user-facing)."""


def is_room_admin(room: dict, user: str) -> bool:
    """True only for the account recorded as the room's admin at creation.

    ``room["admin"]`` is written once, by ``_new_room``, and nothing else in the
    codebase updates it — so there is exactly one admin per room and no way to
    grant the role to someone else.
    """
    if not user or not isinstance(room, dict):
        return False
    return room.get("admin") == user


def require_room_admin(room: dict, user: str) -> None:
    if not is_room_admin(room, user):
        raise NotAuthorized("Only the room admin can do that.")
