"""Squad / player-pool CSV import with validation and clear errors.

Two header-detected formats (dependency-free, stdlib ``csv`` only):

1. **Pool format** — populate a tournament's player pool (the FIFA WC path, since
   ``fifa_wc_2026_players.json`` ships empty):

       Player,Role,Team,BasePrice
       Lionel Messi,FWD,Argentina,0

2. **Roster format** — pre-assign players to participants with prices (the legacy
   ``data/gameweek1_auction_squads.csv`` shape):

       Participant,Player,Role,Team,Price
       Smudge49,Jos Buttler,WK-Batsman,England,60

Returns a :class:`ParseResult` carrying the parsed rows plus per-row errors so the
admin UI can show exactly what to fix before committing.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field


@dataclass
class PoolPlayer:
    name: str
    role: str = "Unknown"
    team: str = "Unknown"
    base_price: int = 0


@dataclass
class RosterAssignment:
    participant: str
    player: str
    role: str = "Unknown"
    team: str = "Unknown"
    price: int = 0


# In a roster CSV, a row whose player name is one of these sets the participant's
# REMAINING budget (post-auction) rather than adding a squad player.
BUDGET_KEYWORDS = {"budget", "remaining", "remaining_budget", "remaining budget", "balance"}


@dataclass
class ParseResult:
    kind: str = "unknown"                      # "pool" | "roster"
    players: list[PoolPlayer] = field(default_factory=list)
    assignments: list[RosterAssignment] = field(default_factory=list)
    budgets: dict = field(default_factory=dict)  # participant -> remaining budget
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors and self.kind in ("pool", "roster")


def _norm(s: str | None) -> str:
    return (s or "").strip()


def _to_int(value: str) -> int | None:
    v = _norm(value).replace(",", "").replace("$", "")
    if v == "":
        return 0
    try:
        return int(round(float(v)))
    except ValueError:
        return None


def _header_map(fieldnames: list[str]) -> dict[str, str]:
    """Map lowercased header -> original header for case-insensitive access."""
    return {(_norm(h).lower()): h for h in fieldnames if h is not None}


def parse_squad_csv(text: str) -> ParseResult:
    """Parse CSV text into a validated :class:`ParseResult`."""
    result = ParseResult()
    text = text.lstrip("﻿")  # strip BOM
    if not _norm(text):
        result.errors.append("The file is empty.")
        return result

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        result.errors.append("Could not read a header row.")
        return result

    headers = _header_map(list(reader.fieldnames))

    if "participant" in headers:
        result.kind = "roster"
        _parse_roster(reader, headers, result)
    elif "player" in headers:
        result.kind = "pool"
        _parse_pool(reader, headers, result)
    else:
        result.errors.append(
            "Header must contain a 'Player' column (pool format) or a "
            "'Participant' column (roster format). Found: "
            + ", ".join(reader.fieldnames)
        )
    return result


def _parse_pool(reader, headers, result: ParseResult) -> None:
    pcol = headers["player"]
    role_col = headers.get("role") or headers.get("position")
    team_col = headers.get("team") or headers.get("country")
    price_col = headers.get("baseprice") or headers.get("base_price") or headers.get("price")

    seen: set[str] = set()
    for i, row in enumerate(reader, start=2):  # row 1 is the header
        name = _norm(row.get(pcol))
        if not name:
            continue  # skip blank lines silently
        if name.lower() in seen:
            result.warnings.append(f"Row {i}: duplicate player '{name}' ignored.")
            continue
        seen.add(name.lower())

        price = _to_int(row.get(price_col, "")) if price_col else 0
        if price is None:
            result.errors.append(f"Row {i}: base price for '{name}' is not a number.")
            price = 0
        result.players.append(
            PoolPlayer(
                name=name,
                role=_norm(row.get(role_col)) or "Unknown" if role_col else "Unknown",
                team=_norm(row.get(team_col)) or "Unknown" if team_col else "Unknown",
                base_price=price,
            )
        )
    if not result.players and not result.errors:
        result.errors.append("No player rows found.")


def _parse_roster(reader, headers, result: ParseResult) -> None:
    part_col = headers["participant"]
    pcol = headers.get("player")
    if pcol is None:
        result.errors.append("Roster format requires a 'Player' column.")
        return
    role_col = headers.get("role") or headers.get("position")
    team_col = headers.get("team") or headers.get("country")
    price_col = headers.get("price")

    # Track players already assigned to a given participant to catch dupes.
    seen: set[tuple[str, str]] = set()
    for i, row in enumerate(reader, start=2):
        participant = _norm(row.get(part_col))
        player = _norm(row.get(pcol))
        if not participant and not player:
            continue
        if not participant:
            result.errors.append(f"Row {i}: missing participant for player '{player}'.")
            continue
        if not player:
            result.errors.append(f"Row {i}: missing player for participant '{participant}'.")
            continue
        price = _to_int(row.get(price_col, "")) if price_col else 0
        if price is None:
            result.errors.append(
                f"Row {i}: value for '{player}' ({participant}) is not a number."
            )
            price = 0

        # Budget row: sets the participant's remaining budget instead of a player.
        if player.lower() in BUDGET_KEYWORDS:
            result.budgets[participant] = price
            continue

        key = (participant.lower(), player.lower())
        if key in seen:
            result.warnings.append(
                f"Row {i}: '{player}' already assigned to '{participant}', ignored."
            )
            continue
        seen.add(key)
        result.assignments.append(
            RosterAssignment(
                participant=participant,
                player=player,
                role=_norm(row.get(role_col)) or "Unknown" if role_col else "Unknown",
                team=_norm(row.get(team_col)) or "Unknown" if team_col else "Unknown",
                price=price,
            )
        )
    if not result.assignments and not result.budgets and not result.errors:
        result.errors.append("No assignment rows found.")
