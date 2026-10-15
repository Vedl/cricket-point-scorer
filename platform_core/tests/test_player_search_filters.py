"""Player points search: position / club / owner filters that combine (AND)."""

from platform_core import season_ops as so


def _room():
    return {
        "tournament_type": "UEFA Champions League 2026/27",
        "player_pool": [
            {"name": "Ridle Baku", "team": "Leipzig", "role": "Midfielder"},
            {"name": "Lamine Yamal", "team": "Barcelona", "role": "Forward"},
            {"name": "Pau Cubarsi", "team": "Barcelona", "role": "Defender"},
            {"name": "Nicolas Jackson", "team": "Bayern München", "role": "Forward"},
            {"name": "Joshua Kimmich", "team": "Bayern München", "role": "Defender"},
        ],
        "participants": [
            {"name": "A", "squad": [{"name": "Lamine Yamal", "team": "Barcelona"},
                                    {"name": "Pau Cubarsi", "team": "Barcelona"}]},
            {"name": "B", "squad": [{"name": "Ridle Baku", "team": "Leipzig"}]},
        ],
        "gameweek_scores": {
            "1": {"Lamine Yamal": 40, "Pau Cubarsi": 20, "Ridle Baku": 11,
                  "Nicolas Jackson": 30, "Joshua Kimmich": 25},
            "2": {"Lamine Yamal": 20, "Nicolas Jackson": 5},
        },
    }


def _names(rows):
    return [r["player"] for r in rows]


def test_no_filters_returns_everyone_sorted_by_points():
    assert _names(so.search_player_points(_room())) == [
        "Lamine Yamal", "Nicolas Jackson", "Joshua Kimmich", "Pau Cubarsi", "Ridle Baku"]


def test_position_filter_uses_listed_position():
    assert _names(so.search_player_points(_room(), positions=["DEF"])) == [
        "Joshua Kimmich", "Pau Cubarsi"]


def test_several_positions_match_any_of_them():
    got = _names(so.search_player_points(_room(), positions=["DEF", "MID"]))
    assert set(got) == {"Joshua Kimmich", "Pau Cubarsi", "Ridle Baku"}


def test_club_filter_reaches_unowned_players():
    # Jackson and Kimmich are owned by nobody: club still comes from the pool.
    assert _names(so.search_player_points(_room(), club="Bayern München")) == [
        "Nicolas Jackson", "Joshua Kimmich"]


def test_owner_and_free_agent_filters():
    assert _names(so.search_player_points(_room(), owner="B")) == ["Ridle Baku"]
    assert _names(so.search_player_points(_room(), owner=so.FREE_AGENTS)) == [
        "Nicolas Jackson", "Joshua Kimmich"]


def test_filters_combine_with_each_other_and_the_name_box():
    room = _room()
    assert _names(so.search_player_points(room, positions=["FWD"], club="Barcelona")) == [
        "Lamine Yamal"]
    assert _names(so.search_player_points(room, positions=["FWD"], club="Barcelona",
                                          owner="B")) == []
    assert _names(so.search_player_points(room, positions=["DEF"], query="kim")) == [
        "Joshua Kimmich"]


def test_filters_respect_the_gameweek_scope():
    assert _names(so.search_player_points(room := _room(), gameweek="2",
                                          positions=["FWD"])) == ["Lamine Yamal",
                                                                  "Nicolas Jackson"]
    assert so.search_player_points(room, gameweek="2", positions=["DEF"]) == []


def test_all_sentinels_mean_no_filter():
    rows = so.search_player_points(_room(), club=so.ALL_CLUBS, owner=so.ALL_OWNERS,
                                   positions=[])
    assert len(rows) == 5


def test_rows_carry_position_and_club():
    row = so.search_player_points(_room(), query="baku")[0]
    assert (row["position"], row["country"], row["owner"]) == ("MID", "Leipzig", "B")


def test_limit_none_returns_all_matches_for_counting():
    assert len(so.search_player_points(_room(), limit=2)) == 2
    assert len(so.search_player_points(_room(), limit=None)) == 5


def test_filter_options_follow_the_pool():
    opts = so.player_search_options(_room())
    assert opts["positions"] == ["DEF", "MID", "FWD"]
    assert opts["clubs"] == ["Barcelona", "Bayern München", "Leipzig"]
    assert opts["owners"] == [so.FREE_AGENTS, "A", "B"]
