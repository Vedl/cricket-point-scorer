"""Room admin permission.

The UI hides admin controls, but a Reflex event handler is reachable over the
websocket whether or not anything rendered it — so the check has to live in the
handler. These pin the rule itself; the state layer calls into it.
"""

import pytest

from platform_core.authz import NotAuthorized, is_room_admin, require_room_admin

ROOM = {"admin": "Ladda CC", "participants": [{"name": "T", "user": "naman"}]}


def test_only_the_recorded_admin_qualifies():
    assert is_room_admin(ROOM, "Ladda CC")
    assert not is_room_admin(ROOM, "naman")


def test_membership_of_the_room_grants_nothing():
    """Being a participant is not being the admin."""
    assert not is_room_admin(ROOM, "naman")


def test_admin_of_another_room_is_not_admin_here():
    """The bug that started this: RoomState kept is_admin from a room the user
    really does administer, and carried it into one they do not."""
    other = {"admin": "naman"}
    assert is_room_admin(other, "naman")
    assert not is_room_admin(ROOM, "naman")


@pytest.mark.parametrize("user", ["", None, "ladda cc", "LADDA CC", "Ladda CC "])
def test_blank_or_near_miss_usernames_are_refused(user):
    assert not is_room_admin(ROOM, user)


def test_require_raises_for_non_admin_and_passes_for_admin():
    require_room_admin(ROOM, "Ladda CC")
    with pytest.raises(NotAuthorized):
        require_room_admin(ROOM, "naman")


def test_a_room_with_no_admin_recorded_admits_nobody():
    assert not is_room_admin({}, "anyone")
    assert not is_room_admin({"admin": None}, None)
