"""Gameweek score keys must be storable in Firebase.

Firebase Realtime Database rejects . $ # [ ] / in a key, and the app writes the
whole document in one PUT — so a single bad key fails the entire save with a 400
and loses every other change in it. UEFA's club short names put those characters
straight into the per-club keeper entries, so this only shows up in a club
competition; the World Cup pool contains none.
"""

import pytest

from platform_core import config_layer as cl
from platform_core import season_ops as so
from platform_core.scoring_ops import merge_link_totals, safe_score_key
from season_engine.names import build_index, lookup

ILLEGAL = set('.$#[]/')
AFFECTED = ["B. Dortmund Keeper", "S. Bratislava Keeper", "Bodø/Glimt Keeper",
            "Jerry St. Juste"]


@pytest.mark.parametrize("name", AFFECTED)
def test_illegal_names_are_made_storable(name):
    assert set(name) & ILLEGAL, "fixture should actually contain an illegal char"
    assert not (set(safe_score_key(name)) & ILLEGAL)


@pytest.mark.parametrize("name", AFFECTED)
def test_a_squad_holding_the_original_name_still_scores(name):
    """Nothing is lost by rewriting the key: lookups canonicalise away
    punctuation and how a name is split, so the squad entry still resolves."""
    index = build_index({safe_score_key(name): 42})
    assert lookup(index, name) == 42


def test_ordinary_names_are_untouched():
    for name in ["Erling Haaland", "N'Golo Kanté", "Vinícius Júnior", "Bodø/Glimt"[:4]]:
        assert safe_score_key(name) == name


def test_the_scraper_merge_step_sanitises():
    totals = {}
    merge_link_totals(totals, {"B. Dortmund Keeper": 29, "Erling Haaland": 12})
    assert set(totals) == {"B Dortmund Keeper", "Erling Haaland"}


def test_merge_still_accumulates_across_matches():
    totals = {}
    merge_link_totals(totals, {"B. Dortmund Keeper": 10})
    merge_link_totals(totals, {"B. Dortmund Keeper": 5})
    assert totals["B Dortmund Keeper"] == 15


def test_set_gameweek_scores_sanitises_every_path():
    room = {}
    so.set_gameweek_scores(room, "1", {"B. Dortmund Keeper": 29, "Jerry St. Juste": 7})
    stored = room["gameweek_scores"]["1"]
    assert not any(set(k) & ILLEGAL for k in stored)
    assert stored == {"B Dortmund Keeper": 29, "Jerry St Juste": 7}


def test_no_pool_name_can_produce_an_unstorable_key():
    """Guards the whole pool, not just the four known names — a future squad
    refresh could introduce another club whose short name has a dot."""
    for tournament in (cl.UCL_2026, cl.FIFA_WC_2026):
        for p in cl.load_player_pool(tournament):
            assert not (set(safe_score_key(p.name)) & ILLEGAL), p.name


def test_sanitising_never_collides_two_distinct_pool_players():
    """Two names must not collapse onto one key, or their points would merge."""
    for tournament in (cl.UCL_2026, cl.FIFA_WC_2026):
        keys = [safe_score_key(p.name) for p in cl.load_player_pool(tournament)]
        assert len(keys) == len(set(keys))
