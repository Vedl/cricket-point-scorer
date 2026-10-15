"""Positional eligibility + scoring rule for football Best-11 selection.

This module encodes ONE rule the whole app must agree on (owner's spec):

    A player's POINTS are the HIGHER of the score their REGISTERED position gives
    them (the position listed in the room's pool) and the score the position they
    actually played (per WhoScored) gives them. Goalkeepers are always scored at
    their registered position.

    Where they actually played also widens which formation SLOTS they are ELIGIBLE
    to fill, and every eligible slot carries that same score.

Concrete example (the "Kimmich case"): Kimmich is listed as a DEF but plays as a
MID. He is credited with the better of his defender and midfielder scores, and in
the Best-11 he may be slotted into either a DEF slot or a MID slot — so a manager
who is short on midfielders can field him there without changing how many points
he earns.

No pandas / framework imports here — pure, exhaustively unit-tested logic that both
the scorer (``football_score_calculator``) and the display layer (``scoring``) call.
"""

from __future__ import annotations

from typing import Callable, Optional

CANONICAL = ("GK", "DEF", "MID", "FWD")


def map_role_to_pos(role_str: Optional[str]) -> Optional[str]:
    """Normalise a free-text role/position to one of GK/DEF/MID/FWD, or None.

    Mirrors the squad-database conventions (e.g. "Centre Back" -> DEF, "Striker"
    -> FWD, "CDM"/"AM" -> MID). Returns None when nothing recognisable is found, so
    callers can fall back to the position the player actually played.
    """
    r = (role_str or "").strip().lower()
    if not r:
        return None
    if "gk" in r or "keeper" in r:
        return "GK"
    if "def" in r or "back" in r or r in ("cb", "lb", "rb", "df", "wb", "lwb", "rwb"):
        return "DEF"
    if "mid" in r or r in ("cm", "dm", "cdm", "am", "cam", "mf", "dmc", "amc", "mc"):
        return "MID"
    if (
        "fwd" in r
        or "forward" in r
        or "striker" in r
        or "wing" in r
        or r in ("fw", "cf", "lw", "rw", "st", "ss")
    ):
        return "FWD"
    return None


def eligible_positions(
    registered_pos: Optional[str], match_pos: Optional[str]
) -> list[str]:
    """Formation slots a player may fill, registered position first.

    The registered position is always eligible; the position actually played is also
    eligible when it differs (and is recognised). Returns ``[]`` only when neither is
    known. Casing is normalised to the canonical GK/DEF/MID/FWD set.
    """
    reg = (registered_pos or "").strip().upper() or None
    played = (match_pos or "").strip().upper() or None
    if reg and reg not in CANONICAL:
        reg = map_role_to_pos(reg)
    if played and played not in CANONICAL:
        played = map_role_to_pos(played)

    out: list[str] = []
    if reg:
        out.append(reg)
    if played and played != reg:
        out.append(played)
    if not out and played:  # reg unknown but played known
        out.append(played)
    return out


def position_score_map(
    registered_pos: Optional[str],
    match_pos: Optional[str],
    score_fn: Callable[[str], float],
) -> dict[str, float]:
    """Return ``{position: score}`` a player contributes to the Best-11.

    ``score_fn(pos)`` computes the player's score *as if* they played ``pos`` (it
    wraps the positional scoring formulas). The KEY RULE: a player is credited with
    the HIGHER of their registered-position score and their played-position score,
    and that single number is applied to EVERY eligible slot — so a registered DEF
    who played MID earns the better of his two scores whether he ends up filling a
    DEF slot or a MID slot.

    Goalkeepers are the exception: the keeper formula is built from different stats
    (saves, claims) and is not comparable with the outfield ones, so a keeper — or an
    outfielder who went in goal — is always scored at the REGISTERED position.

    Only when the player is NOT in the squad database (registered position unknown)
    do we fall back to scoring at the position they actually played.

    Returns ``{}`` when no position is known at all (caller skips the player).
    """
    reg = (registered_pos or "").strip().upper() or None
    if reg and reg not in CANONICAL:
        reg = map_role_to_pos(registered_pos)

    slots = eligible_positions(registered_pos, match_pos)
    if not slots:
        return {}

    if reg:
        if len(slots) == 2 and "GK" not in slots:
            # Two different outfield positions: credit the better of the two.
            score = max(score_fn(pos) for pos in slots)
        else:
            score = score_fn(reg)
        return {pos: score for pos in slots}

    # Unknown player: score at the (single) position they actually played.
    return {slots[0]: score_fn(slots[0])}
