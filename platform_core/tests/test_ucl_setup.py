"""UEFA Champions League 2026/27 room: pool, football rules, and the bid-hold window.

The UCL room reuses the World Cup football machinery wholesale — per-team keepers,
Best-11 football ranges, cumulative-standings knockouts — with clubs standing in
for nations. These tests pin the parts that had to become tournament-agnostic.
"""

import itertools
from datetime import datetime, timedelta

import pytest

from platform_core import bidding_ops as bo
from platform_core import config_layer as cl
from platform_core import scoring_ops
from platform_core import season_ops as so
from season_engine.open_bidding import BidError

NOW = datetime(2026, 9, 10, 12, 0, 0)


# --- player pool ---------------------------------------------------------- #
def test_ucl_pool_has_all_36_league_phase_clubs():
    pool = cl.load_player_pool(cl.UCL_2026)
    assert len({p.team for p in pool}) == 36


def test_keepers_are_bought_per_club_not_individually():
    pool = cl.load_player_pool(cl.UCL_2026)
    keepers = [p for p in pool if p.role == "Goalkeeper"]
    # exactly one keeper entry per club, named "{Club} Keeper"
    assert len(keepers) == 36
    assert all(p.name == f"{p.team} Keeper" for p in keepers)
    # and no individually-named keeper survived into the pool
    assert not any(p.name == "Thibaut Courtois" for p in pool)


def test_positions_come_from_uefa_only():
    pool = cl.load_player_pool(cl.UCL_2026)
    assert {p.role for p in pool} == {"Goalkeeper", "Defender", "Midfielder", "Forward"}


def test_list_b_youth_players_are_excluded_but_still_register_their_club():
    import json
    import os
    path = os.path.join(cl.DATA_DIR, "ucl_2026_players.json")
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)["players"]
    list_b = {p["name"] for p in raw if p["list_b"] and p["role"] != "Goalkeeper"}
    assert list_b, "fixture should contain some List B outfielders"
    names = {p.name for p in cl.load_player_pool(cl.UCL_2026)}
    assert not (list_b & names)
    # A club whose keepers are all List B still gets its "{Club} Keeper" entry,
    # because the keeper line is the club's, not any one player's.
    pool = cl._build_football_pool(
        {"players": [
            {"name": "Kid Keeper", "role": "Goalkeeper", "team": "Some FC", "list_b": True},
            {"name": "Kid Winger", "role": "Forward", "team": "Some FC", "list_b": True},
        ]}, "team")
    assert [p.name for p in pool] == ["Some FC Keeper"]


def test_world_cup_pool_is_unchanged_by_the_shared_builder():
    pool = cl.load_player_pool(cl.FIFA_WC_2026)
    keepers = [p for p in pool if p.name.endswith(" Keeper")]
    assert len(keepers) == 48                      # one per nation
    assert all(p.role == "Goalkeeper" for p in keepers)


# --- football rules carry over -------------------------------------------- #
def test_ucl_room_is_a_football_room():
    assert cl.SPORT_BY_TOURNAMENT[cl.UCL_2026] == "football"
    assert scoring_ops.is_football_room({"tournament_type": cl.UCL_2026})
    assert so._is_football({"tournament_type": cl.UCL_2026})
    assert not scoring_ops.is_football_room({"tournament_type": cl.T20_WC})


# WhoScored's own team slug for each of the 36 UCL clubs, read off live WhoScored
# pages on 2026-09-06 (matchday-1 fixture URLs + team pages). UEFA's short display
# names and WhoScored's differ often enough that this map is the reference for
# `_TEAM_SLUG_ALIASES`; refresh it if WhoScored renames a club.
WHOSCORED_SLUG = {
    "AEK Athens": "aek-athens", "Arsenal": "arsenal", "Aston Villa": "aston-villa",
    "Atleti": "atletico-madrid", "B. Dortmund": "borussia-dortmund",
    "Barcelona": "barcelona", "Bayern München": "bayern-munich",
    "Bodø/Glimt": "bodoe-glimt", "Club Brugge": "club-brugge", "Como": "como",
    "Fenerbahçe": "fenerbahce", "Feyenoord": "feyenoord", "Galatasaray": "galatasaray",
    "Inter": "inter", "LASK": "lask", "Leipzig": "rb-leipzig", "Lens": "lens",
    "Lille": "lille", "Liverpool": "liverpool", "Man City": "manchester-city",
    "Man Utd": "manchester-united", "Napoli": "napoli", "Paris": "paris-saint-germain",
    "Porto": "fc-porto", "PSV": "psv-eindhoven", "Real Betis": "real-betis",
    "Real Madrid": "real-madrid", "Roma": "roma", "S. Bratislava": "slovan-bratislava",
    "Sabah": "sabah-fk", "Shakhtar": "shakhtar-donetsk", "Slavia Praha": "slavia-prague",
    "Sporting CP": "sporting-cp", "Stuttgart": "vfb-stuttgart", "Viking": "viking",
    "Villarreal": "villarreal",
}

# The real UCL 2026/27 matchday-1 slugs as WhoScored publishes them. All 36 clubs
# appear exactly once, so this is the live smoke test for keeper attribution.
MATCHDAY_1 = [
    ("aek-athens-lask", "AEK Athens", "LASK"),
    ("barcelona-feyenoord", "Barcelona", "Feyenoord"),
    ("bayern-munich-bodoe-glimt", "Bayern München", "Bodø/Glimt"),
    ("borussia-dortmund-villarreal", "B. Dortmund", "Villarreal"),
    ("club-brugge-aston-villa", "Club Brugge", "Aston Villa"),
    ("como-rb-leipzig", "Como", "Leipzig"),
    ("fc-porto-manchester-city", "Porto", "Man City"),
    ("fenerbahce-roma", "Fenerbahçe", "Roma"),
    ("lille-real-betis", "Lille", "Real Betis"),
    ("liverpool-atletico-madrid", "Liverpool", "Atleti"),
    ("manchester-united-sabah-fk", "Man Utd", "Sabah"),
    ("napoli-arsenal", "Napoli", "Arsenal"),
    ("paris-saint-germain-slovan-bratislava", "Paris", "S. Bratislava"),
    ("psv-eindhoven-shakhtar-donetsk", "PSV", "Shakhtar"),
    ("real-madrid-inter", "Real Madrid", "Inter"),
    ("slavia-prague-lens", "Slavia Praha", "Lens"),
    ("sporting-cp-galatasaray", "Sporting CP", "Galatasaray"),
    ("vfb-stuttgart-viking", "Stuttgart", "Viking"),
]

UCL_URL = "https://www.whoscored.com/matches/1990001/live/europe-champions-league-2026-2027-"


def _clubs():
    return sorted({p.team for p in cl.load_player_pool(cl.UCL_2026)})


def test_slug_map_covers_every_club_in_the_pool():
    assert set(WHOSCORED_SLUG) == set(_clubs())


@pytest.mark.parametrize("slug, home, away", MATCHDAY_1)
def test_real_matchday_1_urls_resolve_to_the_right_club_keepers(slug, home, away):
    assert scoring_ops._keeper_aliases(UCL_URL + slug, _clubs()) == (home, away)


def test_every_possible_ucl_fixture_resolves_correctly():
    """Matchday 1 only exercises 18 of 1,260 orderings; the knockouts will pair
    clubs that never met in the league phase, so check all of them."""
    clubs = _clubs()
    wrong = []
    for home, away in itertools.permutations(clubs, 2):
        url = f"{UCL_URL}{WHOSCORED_SLUG[home]}-{WHOSCORED_SLUG[away]}"
        if scoring_ops._keeper_aliases(url, clubs) != (home, away):
            wrong.append((home, away))
    assert wrong == []


@pytest.mark.parametrize("slug, home, away", [
    # "Real Madrid" must not assemble itself out of *madrid* (Atleti) + *real*
    # (Betis) and steal the keeper line of a club that isn't even playing.
    ("atletico-madrid-real-betis", "Atleti", "Real Betis"),
    ("real-betis-atletico-madrid", "Real Betis", "Atleti"),
    # Two clubs sharing a leading word must still order home/away correctly.
    ("real-madrid-real-betis", "Real Madrid", "Real Betis"),
    ("real-betis-real-madrid", "Real Betis", "Real Madrid"),
    # "villa" is a substring of "villarreal" but a different token.
    ("villarreal-aston-villa", "Villarreal", "Aston Villa"),
    ("aston-villa-villarreal", "Aston Villa", "Villarreal"),
])
def test_overlapping_club_names_do_not_confuse_each_other(slug, home, away):
    assert scoring_ops._keeper_aliases(UCL_URL + slug, _clubs()) == (home, away)


WC_URL = "https://www.whoscored.com/matches/1953889/live/international-fifa-world-cup-2026-"


@pytest.mark.parametrize("slug, home, away", [
    ("spain-portugal", "Spain", "Portugal"),
    ("south-korea-iran", "Korea Republic", "IR Iran"),
    ("dr-congo-ivory-coast", "Congo DR", "Côte D'Ivoire"),
    # Côte d'Ivoire away: the old string-offset ranking put it home in all 47 of
    # these, silently swapping both nations' keeper scores.
    ("brazil-ivory-coast", "Brazil", "Côte D'Ivoire"),
    ("turkiye-curacao", "Türkiye", "Curaçao"),
])
def test_world_cup_nations_still_resolve(slug, home, away):
    nations = sorted({p.team for p in cl.load_player_pool(cl.FIFA_WC_2026)})
    assert scoring_ops._keeper_aliases(WC_URL + slug, nations) == (home, away)


def test_knockout_ladder_cuts_19_teams_to_16_then_8_then_4():
    """Owner's rule: only the top 16 reach the round-of-16 gameweek, top 8 the
    quarters, and so on — ranked on cumulative standings."""
    parts, scores = [], {}
    for i in range(19):
        parts.append({"name": f"T{i}", "squad": [
            {"name": f"p{i}", "role": "Forward", "team": "Arsenal", "buy_price": 10}]})
        scores[f"p{i}"] = 100 - i          # T0 best, T18 worst
    room = {"tournament_type": cl.UCL_2026, "participants": parts,
            "gameweek_scores": {"8": scores}}

    elim, released = so.eliminate_below_position(room, "8", keep_top=16)
    assert set(elim) == {"T16", "T17", "T18"}
    assert {"p16", "p17", "p18"} <= {p["name"] for p in room["unsold_players"]}
    assert set(released) == {"p16", "p17", "p18"}

    room["gameweek_scores"]["R16"] = scores
    assert set(so.eliminate_below_position(room, "R16", keep_top=8)[0]) == \
        {f"T{i}" for i in range(8, 16)}

    room["gameweek_scores"]["QF"] = scores
    assert set(so.eliminate_below_position(room, "QF", keep_top=4)[0]) == \
        {"T4", "T5", "T6", "T7"}
    assert len(so.eliminated_names(room)) == 15      # 4 survivors of 19


# --- bid hold window ------------------------------------------------------ #
def test_hold_is_12h_before_gw1_and_24h_after():
    assert bo.bid_hold_hours({}, NOW) == 12
    assert bo.bid_hold_hours({"gameweek_deadlines": {"1": "2026-09-15T18:00"}}, NOW) == 12
    assert bo.bid_hold_hours({"gameweek_deadlines": {"1": "2026-09-09T18:00"}}, NOW) == 24
    assert bo.bid_hold_hours({"gameweek_squads": {"1": {}}}, NOW) == 24
    assert bo.bid_hold_hours({"current_gameweek": 3}, NOW) == 24


def test_admin_can_override_each_side_independently():
    room = {}
    assert bo.set_bid_hold_hours(room, 6, pre_gw1=True) == 6
    assert bo.set_bid_hold_hours(room, 48) == 48
    assert bo.bid_hold_hours(room, NOW) == 6                      # still before GW1
    room["gameweek_squads"] = {"1": {}}
    assert bo.bid_hold_hours(room, NOW) == 48


@pytest.mark.parametrize("bad", [0, -3, 200, "", None, "soon"])
def test_admin_override_rejects_nonsense(bad):
    with pytest.raises(BidError):
        bo.set_bid_hold_hours({}, bad)


def test_stored_junk_falls_back_to_the_default():
    assert bo.bid_hold_hours({"gameweek_squads": {"1": {}}, "bid_hold_hours": "nope"}, NOW) == 24
    assert bo.bid_hold_hours({"pre_gw1_bid_hold_hours": 0}, NOW) == 12


def _bid_room(deadline, **extra):
    room = {
        "tournament_type": cl.UCL_2026,
        "player_pool": [{"name": "Haaland", "role": "Forward", "team": "Man City"}],
        "participants": [{"name": "A", "budget": 100, "squad": []}],
        "bidding_deadline": deadline.isoformat(),
    }
    room.update(extra)
    return room


def test_a_bid_expires_after_the_active_hold_window():
    far = NOW + timedelta(days=30)
    room = _bid_room(far)                       # before GW1 -> 12h
    bo.place(room, "A", "Haaland", 10, NOW)
    assert room["open_bids"]["Haaland"]["expires"] == (NOW + timedelta(hours=12)).isoformat()

    room = _bid_room(far, gameweek_squads={"1": {}})     # after GW1 -> 24h
    bo.place(room, "A", "Haaland", 10, NOW)
    assert room["open_bids"]["Haaland"]["expires"] == (NOW + timedelta(hours=24)).isoformat()

    room = _bid_room(far, pre_gw1_bid_hold_hours=3)      # admin override
    bo.place(room, "A", "Haaland", 10, NOW)
    assert room["open_bids"]["Haaland"]["expires"] == (NOW + timedelta(hours=3)).isoformat()


def test_hold_never_runs_past_the_bidding_deadline():
    deadline = NOW + timedelta(hours=2)         # sooner than the 12h hold
    room = _bid_room(deadline)
    bo.place(room, "A", "Haaland", 10, NOW)
    assert room["open_bids"]["Haaland"]["expires"] == deadline.isoformat()


def test_raising_a_bid_restarts_the_hold_clock():
    room = _bid_room(NOW + timedelta(days=30))
    bo.place(room, "A", "Haaland", 10, NOW)
    later = NOW + timedelta(hours=5)
    bo.place(room, "A", "Haaland", 15, later)
    assert room["open_bids"]["Haaland"]["expires"] == (later + timedelta(hours=12)).isoformat()


def test_bid_is_awarded_once_the_hold_window_elapses():
    room = _bid_room(NOW + timedelta(days=30))
    bo.place(room, "A", "Haaland", 10, NOW)
    assert bo.process_expired(room, NOW + timedelta(hours=11)) == []
    awarded = bo.process_expired(room, NOW + timedelta(hours=12))
    assert [a["player"] for a in awarded] == ["Haaland"]
    assert room["participants"][0]["squad"][0]["name"] == "Haaland"
