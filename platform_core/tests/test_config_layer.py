"""These run against the real legacy JSON data files in the repo root."""

from platform_core import config_layer as cl
from auction_engine import EngineConfig


def test_load_t20_pool():
    players = cl.load_player_pool(cl.T20_WC)
    assert len(players) > 100
    assert all(p.id and p.name for p in players)
    # ids are unique
    assert len({p.id for p in players}) == len(players)


def test_load_ipl_pool_has_teams():
    players = cl.load_player_pool(cl.IPL_2026)
    assert len(players) > 0
    assert any(p.team in ("CSK", "Chennai Super Kings", "RCB", "Royal Challengers Bengaluru")
               or p.team for p in players)


def test_fifa_pool_empty_by_default():
    # fifa_wc_2026_players.json ships as [] -> CSV upload path.
    assert cl.load_player_pool(cl.FIFA_WC_2026) == []


def test_default_config_cricket_no_composition():
    cfg = cl.default_config(cl.IPL_2026)
    assert isinstance(cfg, EngineConfig)
    assert cfg.composition == {}            # off by default (legacy behaviour)
    assert cfg.role_categories["Bowler"] == "BWL"
    assert cfg.max_squad == 30 and cfg.timer_seconds == 60


def test_default_config_composition_optin():
    cfg = cl.default_config(cl.IPL_2026, enforce_composition=True)
    assert "WK" in cfg.composition


def test_football_config_no_cricket_categories():
    cfg = cl.default_config(cl.FIFA_WC_2026)
    assert cfg.role_categories == {}
