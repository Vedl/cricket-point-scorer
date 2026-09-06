"""Adding players to a room that runs on a bundled tournament pool.

UEFA's published squads are the source of truth for a UCL room, but they are not
always complete, so an admin needs to add a missing player by CSV. That must ADD
to the pool — before this, uploading a one-player CSV with extend=True replaced
the room's entire pool with that one player.
"""

import pytest

from platform_core import bidding_ops as bo
from platform_core import config_layer as cl
from platform_core import scoring_ops
from platform_core.csv_import import parse_squad_csv
from platform_core.repository import apply_pool_import, RepositoryError

# Someone UEFA lists in neither the UCL nor the domestic squad.
NEW_NAME = "Jimmy Testcase"
ONE = f"Player,Role,Team\n{NEW_NAME},Forward,Inter\n"


def _room():
    return {"tournament_type": cl.UCL_2026, "participants": []}


def _names(room):
    return {p["name"] for p in bo.available_players(room, limit=5000)}


def test_adding_a_player_extends_the_bundled_pool_instead_of_replacing_it():
    room = _room()
    before = _names(room)
    assert apply_pool_import(room, parse_squad_csv(ONE), extend=True) == 1
    after = _names(room)
    assert after == before | {NEW_NAME}
    assert len(after) == len(before) + 1


def test_the_addition_is_stored_on_its_own_not_by_copying_the_pool():
    """The room document is read on every poll, so it must not gain ~886 rows."""
    room = _room()
    apply_pool_import(room, parse_squad_csv(ONE), extend=True)
    assert not room.get("player_pool")
    assert [p["name"] for p in room["extra_players"]] == [NEW_NAME]


def test_an_added_player_is_biddable_and_filterable_like_any_other():
    room = _room()
    apply_pool_import(room, parse_squad_csv(ONE), extend=True)
    inter = bo.available_players(room, country="Inter", role="Forward", limit=50)
    assert NEW_NAME in {p["name"] for p in inter}
    assert bo._player(room, NEW_NAME)["team"] == "Inter"


def test_adding_someone_already_in_the_pool_is_a_no_op():
    room = _room()
    before = len(_names(room))
    csv = "Player,Role,Team\nLautaro Martínez,Forward,Inter\n"
    assert apply_pool_import(room, parse_squad_csv(csv), extend=True) == 0
    assert len(_names(room)) == before


def test_additions_do_not_disturb_the_per_club_keeper_entries():
    room = _room()
    apply_pool_import(room, parse_squad_csv(ONE), extend=True)
    assert len(scoring_ops.fifa_countries(room)) == 36


def test_extend_false_still_replaces_the_pool_outright():
    room = _room()
    room["extra_players"] = [{"name": "Someone", "role": "Forward", "team": "Inter"}]
    assert apply_pool_import(room, parse_squad_csv(ONE), extend=False) == 1
    assert _names(room) == {NEW_NAME}
    assert room["extra_players"] == []


def test_a_room_with_its_own_uploaded_pool_still_grows_that_pool():
    room = {"tournament_type": cl.UCL_2026, "participants": [],
            "player_pool": [{"name": "Custom Guy", "role": "Forward", "team": "Inter"}]}
    apply_pool_import(room, parse_squad_csv(ONE), extend=True)
    assert {p["name"] for p in room["player_pool"]} == {"Custom Guy", NEW_NAME}
    assert not room.get("extra_players")


def test_a_roster_csv_is_still_refused_as_a_pool():
    with pytest.raises(RepositoryError):
        apply_pool_import(_room(), parse_squad_csv(
            "Participant,Player,Price\nA,Someone,5\n"), extend=True)
