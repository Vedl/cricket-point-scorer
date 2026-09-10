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


# --- a candidate the source already registers is a different player --------- #
def test_a_scored_name_the_source_registers_is_not_a_suspect():
    """UCL GW1 flagged Bayern's Nathaniel Brown because "Archie Brown" scored 30.
    Archie Brown is Fenerbahçe's midfielder — a real, separately registered
    player, so he is no evidence about Nathaniel at all."""
    pool = POOL + [
        {"name": "Nathaniel Brown", "role": "Defender", "team": "Bayern München"},
        {"name": "Archie Brown", "role": "Midfielder", "team": "Fenerbahçe"},
        {"name": "Bayern München Keeper", "role": "Goalkeeper", "team": "Bayern München"},
    ]
    squad = [{"name": "Nathaniel Brown", "role": "Defender", "team": "Bayern München"}]
    room = {
        "tournament_type": "UEFA Champions League 2026/27", "player_pool": pool,
        "participants": [{"name": "A", "squad": squad}],
        "gameweek_squads": {"1": {"A": {"squad": squad}}},
        "gameweek_scores": {"1": {"Bayern München Keeper": 8, "Archie Brown": 30}},
    }
    assert so.audit_unmatched_scores(room, "1") == []


def test_a_scored_name_the_source_does_NOT_register_is_the_real_signal():
    """"Maxi Araújo" appears in no squad list, which is exactly what an
    unrecognised spelling of a registered player looks like."""
    pool = POOL + [{"name": "Sporting CP Keeper", "role": "Goalkeeper", "team": "Sporting CP"}]
    squad = [{"name": "Maximiliano Araújo", "role": "Midfielder", "team": "Sporting CP"}]
    room = {
        "tournament_type": "UEFA Champions League 2026/27", "player_pool": pool,
        "participants": [{"name": "A", "squad": squad}],
        "gameweek_squads": {"1": {"A": {"squad": squad}}},
        "gameweek_scores": {"1": {"Sporting CP Keeper": 5, "Wilfried Araújo": 12}},
    }
    rows = so.audit_unmatched_scores(room, "1")
    assert len(rows) == 1 and rows[0]["player"] == "Maximiliano Araújo"


def test_registered_names_includes_keepers_dropped_from_the_pool():
    """Individual keepers are replaced by one "{Team} Keeper" entry in the pool,
    but they are still registered players and must not read as misspellings."""
    from platform_core import config_layer as cl
    room = {"tournament_type": cl.UCL_2026}
    from season_engine.names import canonical
    names = cl.registered_names(room)
    assert canonical("Joan García") in names          # Barcelona's keeper
    assert canonical("Thibaut Courtois") in names
    assert canonical("Maxi Araújo") not in names      # a WhoScored spelling
