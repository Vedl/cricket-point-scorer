from platform_core import admin_ops as ao
from platform_core.csv_import import parse_squad_csv
from platform_core.csv_review import build_review
from platform_core.repository import apply_reviewed_roster


POOL = ["Thiago Silva", "Bernardo Silva", "Lionel Messi", "Kylian Mbappe"]


def test_exact_match():
    res = parse_squad_csv("Participant,Player,Price\nA,Lionel Messi,30\n")
    rows = build_review(res.assignments, POOL)
    assert rows[0]["status"] == "exact"
    assert rows[0]["matched"] == "Lionel Messi"


def test_ambiguous_silva_lists_candidates():
    res = parse_squad_csv("Participant,Player,Price\nA,Silva,20\n")
    rows = build_review(res.assignments, POOL)
    assert rows[0]["status"] in ("fuzzy", "exact")
    cands = rows[0]["candidates"]
    assert "Thiago Silva" in cands and "Bernardo Silva" in cands   # admin picks which


def test_unmatched():
    res = parse_squad_csv("Participant,Player,Price\nA,Zzzqqq,5\n")
    rows = build_review(res.assignments, POOL)
    assert rows[0]["status"] == "unmatched"


def test_apply_reviewed_roster_uses_canonical_and_csv_budget():
    room = {"tournament_type": "FIFA World Cup 2026",
            "player_pool": [{"name": "Thiago Silva", "role": "DEF", "team": "Brazil"}],
            "participants": [{"name": "A", "budget": 0, "squad": []}]}
    rows = [{"participant": "A", "matched": "Thiago Silva", "price": 25}]
    apply_reviewed_roster(room, rows, budgets={"A": 175})
    a = room["participants"][0]
    assert a["budget"] == 175                       # from CSV, not a default
    assert a["squad"][0]["name"] == "Thiago Silva"
    assert a["squad"][0]["role"] == "DEF"           # role from pool, not blank
    assert a["squad"][0]["team"] == "Brazil"


def test_boost_all():
    room = {"participants": [{"name": "A", "budget": 50}, {"name": "B", "budget": 0}]}
    assert ao.boost_all(room, 100) == 2
    assert room["participants"][0]["budget"] == 150
    assert room["participants"][1]["budget"] == 100
