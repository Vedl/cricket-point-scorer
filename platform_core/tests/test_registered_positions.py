"""Which formula scores a player must come from the room being scored.

A lost aerial duel costs a midfielder 1.5 and a forward 0.4, so the registered
position is not cosmetic. The scorer's built-in fallback is the World Cup squad
file; for a UCL room it knows almost nobody, and those players were silently
scored on whatever position WhoScored recorded them playing.
"""

import json
import os

from platform_core import config_layer as cl
from platform_core import scoring_ops
from season_engine.names import canonical


def test_positions_come_from_the_rooms_own_pool():
    room = {"tournament_type": cl.UCL_2026}
    pos = scoring_ops.registered_positions(room)
    assert pos["Abdallah Sima"] == "Forward"        # Lens; WhoScored played him MID
    assert len(pos) == len(cl.load_player_pool(cl.UCL_2026))


def test_the_world_cup_file_would_not_have_covered_them():
    """The regression this guards: most UCL players are absent from the fallback."""
    path = os.path.join(cl.DATA_DIR, "fifa_wc_2026_players.json")
    with open(path, encoding="utf-8") as f:
        wc = {canonical(p["name"]) for p in json.load(f) if p.get("name")}
    ucl = {canonical(p.name) for p in cl.load_player_pool(cl.UCL_2026)}
    assert len(ucl - wc) > 500, "fixture assumption: most UCL players aren't in the WC file"
    assert canonical("Abdallah Sima") not in wc


def test_a_custom_room_pool_is_used_verbatim():
    room = {"tournament_type": cl.UCL_2026, "player_pool": [
        {"name": "Someone", "role": "Defender", "team": "Inter"}]}
    assert scoring_ops.registered_positions(room) == {"Someone": "Defender"}


def test_players_added_to_a_room_are_included():
    room = {"tournament_type": cl.UCL_2026,
            "extra_players": [{"name": "Late Signing", "role": "Forward", "team": "Inter"}]}
    assert scoring_ops.registered_positions(room)["Late Signing"] == "Forward"


def test_a_cricket_room_supplies_no_football_positions():
    from platform_core.scoring_ops import is_football_room
    room = {"tournament_type": cl.T20_WC}
    assert not is_football_room(room)


def test_scoring_passes_positions_through_to_the_scorer(monkeypatch):
    """The map must actually reach whoscored_player_scores, not just be built."""
    seen = {}

    def fake(url, positions=None):
        seen["positions"] = positions
        return {"Abdallah Sima": 24}

    import scoring
    monkeypatch.setattr(scoring, "whoscored_player_scores", fake)
    monkeypatch.setattr(scoring, "whoscored_keeper_scores", lambda url: {})
    out = scoring_ops.score_one_link("http://x", is_football=True, countries=[],
                                     positions={"Abdallah Sima": "Forward"})
    assert seen["positions"] == {"Abdallah Sima": "Forward"}
    assert out == {"Abdallah Sima": 24}
