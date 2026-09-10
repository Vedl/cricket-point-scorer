"""Post-scoring audit: owned players whose points reached nobody.

A name the squad and the source spell differently is skipped in silence — the
team simply scores less, and nobody notices for weeks. This flags the suspects
for a human; it never reassigns points itself.
"""

from platform_core import season_ops as so

POOL = [
    {"name": "Maximiliano Araújo", "role": "Midfielder", "team": "Sporting CP"},
    {"name": "Gabriel Veiga", "role": "Midfielder", "team": "Porto"},
    {"name": "Eric García", "role": "Defender", "team": "Barcelona"},
    {"name": "Harry Kane", "role": "Forward", "team": "Bayern München"},
    {"name": "Unused Sub", "role": "Forward", "team": "Sporting CP"},
    {"name": "Sporting CP Keeper", "role": "Goalkeeper", "team": "Sporting CP"},
    {"name": "Porto Keeper", "role": "Goalkeeper", "team": "Porto"},
    {"name": "Barcelona Keeper", "role": "Goalkeeper", "team": "Barcelona"},
]


def _room(squad, scores):
    return {
        "tournament_type": "UEFA Champions League 2026/27",
        "player_pool": POOL,
        "participants": [{"name": "A", "squad": squad}],
        "gameweek_squads": {"1": {"A": {"squad": squad}}},
        "gameweek_scores": {"1": scores},
    }


def _entry(name):
    p = next(x for x in POOL if x["name"] == name)
    return {"name": name, "role": p["role"], "team": p["team"]}


def test_flags_a_player_whose_club_played_and_whose_surname_scored():
    """A spelling names.py cannot bridge — unrelated given names, same surname.
    ("Maxi"/"Maximiliano" is deliberately NOT used here: that one now resolves,
    so it would prove nothing.)"""
    room = _room([_entry("Maximiliano Araújo")],
                 {"Wilfried Araújo": 12, "Sporting CP Keeper": 5})
    rows = so.audit_unmatched_scores(room, "1")
    assert len(rows) == 1
    assert rows[0]["player"] == "Maximiliano Araújo"
    assert rows[0]["candidates"] == [{"name": "Wilfried Araújo", "points": 12}]


def test_the_shortened_given_name_case_no_longer_needs_flagging():
    """Regression guard: names.py resolves Maxi -> Maximiliano, so the audit
    should stay quiet rather than nag about a case that now works."""
    room = _room([_entry("Maximiliano Araújo")],
                 {"Maxi Araújo": 12, "Sporting CP Keeper": 5})
    assert so.audit_unmatched_scores(room, "1") == []


def test_silent_when_the_name_resolves():
    room = _room([_entry("Harry Kane")], {"Harry Kane": 30})
    assert so.audit_unmatched_scores(room, "1") == []


def test_ignores_a_player_whose_club_did_not_play():
    """No keeper line for Bayern means Bayern did not play, so a blank is normal."""
    room = _room([_entry("Harry Kane")], {"Sporting CP Keeper": 5, "Maxi Araújo": 12})
    assert so.audit_unmatched_scores(room, "1") == []


def test_ignores_a_player_who_played_but_shares_no_surname():
    """Club played, he scored nothing, nobody with his name scored — an unused
    substitute, not a spelling problem."""
    room = _room([_entry("Unused Sub")], {"Sporting CP Keeper": 5, "Someone Else": 9})
    assert so.audit_unmatched_scores(room, "1") == []


def test_a_candidate_already_owned_by_someone_is_not_a_suspect():
    room = _room([_entry("Eric García")], {"Barcelona Keeper": 4, "Fran García": 6})
    room["participants"].append({"name": "B", "squad": [
        {"name": "Fran García", "role": "Defender", "team": "Real Betis"}]})
    room["gameweek_squads"]["1"]["B"] = {"squad": room["participants"][1]["squad"]}
    assert so.audit_unmatched_scores(room, "1") == []


def test_reports_the_owner_and_the_candidate_points():
    room = _room([_entry("Eric García")], {"Barcelona Keeper": 4, "Joan García": 22})
    rows = so.audit_unmatched_scores(room, "1")
    assert len(rows) == 1
    assert rows[0]["participant"] == "A"
    assert rows[0]["team"] == "Barcelona"
    assert rows[0]["candidates"] == [{"name": "Joan García", "points": 22}]


def test_dual_position_scores_report_the_best_slot():
    room = _room([_entry("Eric García")],
                 {"Barcelona Keeper": 4, "Joan García": {"DEF": 22, "MID": 19}})
    assert so.audit_unmatched_scores(room, "1")[0]["candidates"][0]["points"] == 22


def test_an_unscored_gameweek_reports_nothing():
    assert so.audit_unmatched_scores(_room([_entry("Harry Kane")], {}), "1") == []


def test_clubs_that_played_is_read_from_the_keeper_lines():
    room = _room([], {"Sporting CP Keeper": 5, "Porto Keeper": 7, "Maxi Araújo": 12})
    assert so.clubs_that_played(room, "1") == {"Sporting CP", "Porto"}
