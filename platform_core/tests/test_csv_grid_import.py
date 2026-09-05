"""Wide "visual grid" roster CSVs — the shape exported from the league's spreadsheet.

Team names sit in row 1 as (name, price) column pairs, signings fill the rows
below, and a footer row carries each team's remaining budget.
"""

import collections

from platform_core.csv_import import parse_squad_csv
from platform_core.csv_review import build_review, flag_duplicates
from platform_core.repository import apply_reviewed_roster

GRID = (
    "Ladda,,Adnan,,Nikhil,\n"
    ",,,,,\n"
    "Vitinha,70,Rodri,55,Pedri,65\n"
    "Raphinha,40,Endrick,20,Marquinhos,35\n"
    ",,Gavi,15,,\n"
    ",,,,,\n"
    ",39,,21,,32\n"
)

POOL = ["Vitinha", "Raphinha", "Rodri", "Endrick", "Gavi", "Pedri", "Marquinhos",
        "Real Madrid Keeper", "Barcelona Keeper"]


def _room(tournament="UEFA Champions League 2026/27"):
    return {"tournament_type": tournament, "player_pool":
            [{"name": n, "role": "Midfielder", "team": "Barcelona"} for n in POOL],
            "participants": []}


def test_grid_csv_parses_teams_signings_and_budgets():
    res = parse_squad_csv(GRID)
    assert res.kind == "roster" and res.ok
    assert res.budgets == {"Ladda": 39, "Adnan": 21, "Nikhil": 32}
    assert collections.Counter(a.participant for a in res.assignments) == {
        "Adnan": 3, "Ladda": 2, "Nikhil": 2}


def test_budget_footer_is_found_by_shape_not_row_number():
    """The sheet is re-exported with different numbers of trailing blank rows;
    the footer must still be recognised wherever it lands."""
    base = parse_squad_csv(GRID).budgets
    rows = GRID.rstrip("\n").split("\n")
    padded = "\n".join(rows[:-1] + [",,,,,"] * 9 + [rows[-1]])
    tight = "\n".join(rows[:5] + [rows[-1]])
    assert parse_squad_csv(padded).budgets == base
    assert parse_squad_csv(tight).budgets == base


def test_import_creates_unclaimed_teams_with_csv_budgets():
    res = parse_squad_csv(GRID)
    room = _room()
    rows = [{"participant": r["participant"], "matched": r["matched"], "price": r["price"]}
            for r in build_review(res.assignments, POOL)]
    applied, skipped = apply_reviewed_roster(room, rows, res.budgets)
    assert applied == 7 and skipped == []
    by = {p["name"]: p for p in room["participants"]}
    assert set(by) == {"Ladda", "Adnan", "Nikhil"}
    assert {n: p["budget"] for n, p in by.items()} == {"Ladda": 39, "Adnan": 21, "Nikhil": 32}
    # teams arrive unclaimed — the admin hands out PINs afterwards
    assert all(p["user"] is None and p["pin"] is None for p in by.values())
    # role/team come from the room's pool so scoring can find them
    assert by["Ladda"]["squad"][0]["role"] == "Midfielder"


# --- one player, one owner ------------------------------------------------- #
def test_two_rows_claiming_one_player_are_flagged_for_the_admin():
    rows = [{"participant": "A", "matched": "Pedri", "status": "fuzzy"},
            {"participant": "B", "matched": "Pedri", "status": "fuzzy"},
            {"participant": "B", "matched": "Gavi", "status": "exact"}]
    assert flag_duplicates(rows) == 1
    assert [r["status"] for r in rows] == ["fuzzy", "duplicate", "exact"]


def test_repicking_a_flagged_row_clears_it():
    rows = [{"participant": "A", "matched": "Pedri", "status": "fuzzy"},
            {"participant": "B", "matched": "Pedri", "status": "duplicate"}]
    rows[1]["matched"] = "Gavi"
    assert flag_duplicates(rows) == 0
    assert rows[1]["status"] == "confirmed"


def test_commit_never_gives_one_player_two_owners():
    room = _room()
    rows = [{"participant": "A", "matched": "Pedri", "price": 60},
            {"participant": "B", "matched": "Pedri", "price": 55},
            {"participant": "B", "matched": "Gavi", "price": 20}]
    applied, skipped = apply_reviewed_roster(room, rows, budgets={"A": 40, "B": 25})
    assert applied == 2
    assert skipped == [{"participant": "B", "player": "Pedri", "owned_by": "A"}]
    owners = collections.Counter(
        e["name"] for p in room["participants"] for e in p["squad"])
    assert owners == {"Pedri": 1, "Gavi": 1}


def test_a_player_already_on_someone_else_squad_is_not_reassigned():
    room = _room()
    room["participants"] = [{"name": "A", "budget": 10, "squad": [
        {"name": "Pedri", "role": "Midfielder", "team": "Barcelona", "buy_price": 60}]}]
    applied, skipped = apply_reviewed_roster(
        room, [{"participant": "B", "matched": "Pedri", "price": 55}], budgets={})
    assert applied == 0 and skipped[0]["owned_by"] == "A"
