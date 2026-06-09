"""Football Best-11 selection with the registered-vs-played position rule.

These are the scenarios that "could decide who wins the auction": a player listed in
one position who actually played another. The scorer now emits, for such a player, a
``{registered_pos: S, played_pos: S}`` map where S is the SAME registered-position
score in both slots. These tests prove the Best-11 selector then:

  * lets that player fill EITHER slot (flexibility),
  * never counts him twice,
  * always credits his registered-position score regardless of the slot he fills,
  * and uses the flexibility to field a higher-scoring legal XI than would otherwise
    be possible.

The exact "Kimmich case" from the spec is :func:`test_kimmich_fills_a_midfield_gap`.
"""

from season_engine.best11 import select_best_11, total_points

FORMATION = {"GK": (1, 1), "DEF": (3, 5), "MID": (3, 5), "FWD": (1, 3)}


def _counts(team):
    c = {}
    for p in team:
        c[p["category"]] = c.get(p["category"], 0) + 1
    return c


def _assert_legal(team):
    assert len(team) == 11
    # No player appears twice.
    names = [p["name"] for p in team]
    assert len(names) == len(set(names)), f"duplicate players: {names}"
    counts = _counts(team)
    for role, (lo, hi) in FORMATION.items():
        assert lo <= counts.get(role, 0) <= hi, f"{role}={counts.get(role,0)} out of {lo}-{hi}"


def _find(team, name):
    return next((p for p in team if p["name"] == name), None)


# --------------------------------------------------------------------------- #
# The headline scenario
# --------------------------------------------------------------------------- #
def test_kimmich_fills_a_midfield_gap():
    """Manager has 4–5 strong defenders but only 2 midfielders who played; the other
    3 got zero minutes. Kimmich is listed DEF but played MID, so he can take a MID
    slot — earning his DEFENDER points — to complete a legal, higher-scoring XI."""
    squad = (
        [{"name": "gk", "role": "GK"}]
        + [{"name": n, "role": "Defender"} for n in
           ("kimmich", "def1", "def2", "def3", "def4")]
        + [{"name": n, "role": "Midfielder"} for n in
           ("mid1", "mid2", "mid3", "mid4", "mid5")]
        + [{"name": n, "role": "Forward"} for n in ("fwd1", "fwd2", "fwd3")]
    )
    scores = {
        "gk": 5,
        # Listed DEF, played MID -> SAME score (50) available in both slots.
        "kimmich": {"DEF": 50, "MID": 50},
        "def1": 40, "def2": 38, "def3": 35, "def4": 30,
        "mid1": 45, "mid2": 44,            # mid3/4/5 played 0 minutes -> absent (0)
        "fwd1": 20, "fwd2": 18, "fwd3": 5,
    }
    team, warns = select_best_11(squad, scores, is_football=True)
    assert warns == []
    _assert_legal(team)

    kim = _find(team, "kimmich")
    assert kim is not None, "Kimmich must be in the XI"
    assert kim["category"] == "MID", "Kimmich should fill the midfield gap"
    assert kim["score"] == 50, "his points are the DEFENDER score, not a MID score"

    # Best legal XI is every real contributor with Kimmich shifted to MID.
    assert total_points(squad, scores, is_football=True) == 330


def test_kimmich_points_are_defender_points_not_played_points():
    """Even when the played (MID) position would have scored MORE, the credited score
    is the registered (DEF) one. (The scorer guarantees both dict slots are equal; here
    we still assert the selector never invents a different number.)"""
    squad = (
        [{"name": "gk", "role": "GK"}]
        + [{"name": n, "role": "Defender"} for n in ("kimmich", "d1", "d2", "d3", "d4")]
        + [{"name": n, "role": "Midfielder"} for n in ("m1", "m2", "m3", "m4", "m5")]
        + [{"name": n, "role": "Forward"} for n in ("f1", "f2", "f3")]
    )
    scores = {
        "gk": 5, "kimmich": {"DEF": 50, "MID": 50},
        "d1": 40, "d2": 38, "d3": 35, "d4": 30,
        "m1": 45, "m2": 44, "f1": 20, "f2": 18, "f3": 5,
    }
    team, _ = select_best_11(squad, scores, is_football=True)
    assert _find(team, "kimmich")["score"] == 50


# --------------------------------------------------------------------------- #
# Flex required to meet a role minimum
# --------------------------------------------------------------------------- #
def test_registered_mid_played_def_completes_back_line():
    """Only two natural defenders, so a registered MID who played DEF must drop into
    the back line (min 3 DEF) — scoring his MIDFIELDER points there."""
    squad = (
        [{"name": "gk", "role": "GK"}]
        + [{"name": n, "role": "Defender"} for n in ("def1", "def2")]
        + [{"name": "flexp", "role": "Midfielder"}]
        + [{"name": n, "role": "Midfielder"} for n in ("mid1", "mid2", "mid3", "mid4")]
        + [{"name": n, "role": "Forward"} for n in ("fwd1", "fwd2", "fwd3")]
        + [{"name": "benchMid", "role": "Midfielder"}]  # pushes unique count > 11
    )
    scores = {
        "gk": 5, "def1": 30, "def2": 28,
        "flexp": {"MID": 50, "DEF": 50},   # registered MID, played DEF
        "mid1": 48, "mid2": 46, "mid3": 44, "mid4": 42,
        "fwd1": 40, "fwd2": 38, "fwd3": 36,
    }
    team, warns = select_best_11(squad, scores, is_football=True)
    assert warns == []
    _assert_legal(team)
    flexp = _find(team, "flexp")
    assert flexp["category"] == "DEF", "must drop into defence to make the XI legal"
    assert flexp["score"] == 50
    assert total_points(squad, scores, is_football=True) == 407


# --------------------------------------------------------------------------- #
# Robustness: no double counting, ranges respected, two flex players
# --------------------------------------------------------------------------- #
def test_dual_position_football_player_counted_once():
    squad = (
        [{"name": "gk", "role": "GK"}]
        + [{"name": n, "role": "Defender"} for n in ("d1", "d2", "d3", "d4", "d5")]
        + [{"name": n, "role": "Midfielder"} for n in ("m1", "m2", "m3", "m4", "m5")]
        + [{"name": n, "role": "Forward"} for n in ("f1", "f2", "f3")]
    )
    scores = {p["name"]: 10 for p in squad}
    scores["d1"] = {"DEF": 60, "MID": 60}   # eligible in two slots
    team, _ = select_best_11(squad, scores, is_football=True)
    assert sum(1 for p in team if p["name"] == "d1") <= 1
    _assert_legal(team)


def test_two_flex_players_fill_two_different_gaps():
    """Two registered defenders both played midfield. With only two natural mids and
    one natural defender, the pair must cover both the DEF and MID minimums between
    them — and each appears exactly once."""
    squad = (
        [{"name": "gk", "role": "GK"}]
        + [{"name": "flexA", "role": "Defender"}, {"name": "flexB", "role": "Defender"}]
        + [{"name": "def1", "role": "Defender"}]
        + [{"name": n, "role": "Midfielder"} for n in ("mid1", "mid2")]
        + [{"name": n, "role": "Forward"} for n in ("fwd1", "fwd2", "fwd3")]
        + [{"name": "benchDef", "role": "Defender"},
           {"name": "benchMid", "role": "Midfielder"},
           {"name": "benchFwd", "role": "Forward"}]  # zero-score bench -> unique > 11
    )
    scores = {
        "gk": 5,
        "flexA": {"DEF": 50, "MID": 50}, "flexB": {"DEF": 49, "MID": 49},
        "def1": 40, "mid1": 45, "mid2": 44,
        "fwd1": 30, "fwd2": 28, "fwd3": 26,
    }
    team, warns = select_best_11(squad, scores, is_football=True)
    assert warns == []
    _assert_legal(team)
    assert sum(1 for p in team if p["name"] == "flexA") == 1
    assert sum(1 for p in team if p["name"] == "flexB") == 1
    # Both flex players are used (each worth 50/49 in any slot) — max legal total.
    assert total_points(squad, scores, is_football=True) == 317


def test_flex_does_not_break_gk_constraint():
    """Flexibility never lets a registered DEF/MID masquerade as the keeper."""
    squad = (
        [{"name": "gk1", "role": "GK"}, {"name": "gk2", "role": "GK"}]
        + [{"name": n, "role": "Defender"} for n in ("d1", "d2", "d3", "d4", "d5")]
        + [{"name": n, "role": "Midfielder"} for n in ("m1", "m2", "m3")]
        + [{"name": n, "role": "Forward"} for n in ("f1", "f2")]
    )  # 12 unique players -> the range-enforcing selection path runs
    scores = {p["name"]: 10 for p in squad}
    scores["d1"] = {"DEF": 99, "MID": 99}
    team, _ = select_best_11(squad, scores, is_football=True)
    assert _counts(team).get("GK", 0) == 1


# --------------------------------------------------------------------------- #
# End-to-end shape (as produced by scoring.whoscored_player_scores)
# --------------------------------------------------------------------------- #
def test_end_to_end_gameweek_scores_shape():
    """Feed a gameweek_scores-shaped dict (plain numbers for single-position players,
    equal-valued {pos: score} dicts for dual-position players) straight into the
    selector, exactly as the live pipeline stores it."""
    squad = (
        [{"name": "gk", "role": "Goalkeeper"}]
        + [{"name": n, "role": "Centre Back"} for n in ("cb1", "cb2", "cb3", "cb4")]
        + [{"name": n, "role": "Central Midfield"} for n in ("cm1", "cm2")]
        + [{"name": n, "role": "Striker"} for n in ("st1", "st2")]
        + [{"name": n, "role": "Right Back"} for n in ("rb1",)]
        + [{"name": "benchA", "role": "Central Midfield"},
           {"name": "benchB", "role": "Striker"}]
    )
    gameweek_scores = {
        "gk": 6,
        "cb1": 41, "cb2": 39, "cb3": 33,
        "cb4": {"DEF": 28, "MID": 28},   # CB who played in midfield
        "rb1": 22,
        "cm1": 47, "cm2": 12,
        "st1": 31, "st2": 9,
    }
    team, warns = select_best_11(squad, gameweek_scores, is_football=True)
    assert warns == []
    _assert_legal(team)
    # The flexible CB scores 28 wherever it is slotted.
    flex = _find(team, "cb4")
    if flex is not None:
        assert flex["score"] == 28


def test_no_goalkeeper_falls_back_with_warning():
    squad = (
        [{"name": n, "role": "Defender"} for n in ("d1", "d2", "d3", "d4", "d5")]
        + [{"name": n, "role": "Midfielder"} for n in ("m1", "m2", "m3", "m4", "m5")]
        + [{"name": n, "role": "Forward"} for n in ("f1", "f2", "f3")]
    )
    scores = {p["name"]: 10 for p in squad}
    team, warns = select_best_11(squad, scores, is_football=True)
    assert warns and "Could not satisfy" in warns[0]
    assert any(p["name"].startswith("[Empty GK") for p in team)
    assert len(team) == 11
