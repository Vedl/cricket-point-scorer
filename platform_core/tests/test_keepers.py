from platform_core import config_layer as cl
from platform_core import scoring_ops as so


def test_fifa_pool_uses_team_keepers_not_individual_gks():
    pool = cl.load_player_pool(cl.FIFA_WC_2026)
    names = [p.name for p in pool]
    keepers = [n for n in names if n.endswith(" Keeper")]
    assert keepers, "expected '<Country> Keeper' entries"
    # no individual goalkeepers remain
    gks = [p for p in pool if ("gk" in p.role.lower() or "keeper" in p.role.lower())
           and not p.name.endswith(" Keeper")]
    assert gks == []


def test_keeper_alias_from_url():
    countries = ["Mexico", "South Africa", "France", "Argentina"]
    home, away = so._keeper_aliases(
        "https://www.whoscored.com/matches/1/live/fifa-world-cup-2026-mexico-south-africa",
        countries)
    assert home == "Mexico" and away == "South Africa"


def test_score_gameweek_merges_keeper(monkeypatch):
    room = {"tournament_type": "FIFA World Cup 2026",
            "player_pool": [{"name": "Mexico Keeper", "role": "Goalkeeper", "team": "Mexico"},
                            {"name": "France Keeper", "role": "Goalkeeper", "team": "France"},
                            {"name": "Lionel Messi", "role": "FWD", "team": "Argentina"}],
            "participants": []}
    import scoring
    monkeypatch.setattr(scoring, "whoscored_player_scores", lambda url: {"Lionel Messi": 40})
    monkeypatch.setattr(scoring, "whoscored_keeper_scores", lambda url: {"home": 70, "away": 12})
    totals, errors = so.score_gameweek_from_links(
        room, "1", ["https://www.whoscored.com/matches/1/live/x-mexico-france"])
    assert totals["Mexico Keeper"] == 70   # home
    assert totals["France Keeper"] == 12   # away
    assert totals["Lionel Messi"] == 40
