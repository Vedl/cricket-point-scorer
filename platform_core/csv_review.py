"""CSV roster review — fuzzy-match written player names to the tournament pool.

People write "Silva" but several players named Silva are at the World Cup. This
builds a review table so the admin confirms exactly which pool player each written
name maps to, before committing — so squads and scoring use the canonical names.
"""

from __future__ import annotations

import difflib
import re


def _keeper_maps(pool_names: list[str]) -> tuple[dict, dict]:
    """From the pool, build lookups for nation-keeper entries ("Spain Keeper").

    Returns (by_full, by_country): "spain keeper" -> "Spain Keeper" and
    "spain" -> "Spain Keeper".
    """
    by_full, by_country = {}, {}
    for n in pool_names:
        if n.endswith(" Keeper"):
            country = n[: -len(" Keeper")]
            by_full[n.lower()] = n
            by_country[country.lower()] = n
    return by_full, by_country


def _keeper_match(written: str, by_full: dict, by_country: dict):
    """Map any goalkeeper phrasing to the canonical "{Country} Keeper" pool entry.

    Football keepers are owned per nation, not per player, so a CSV cell like
    "Spain Keepers", "Spain GK", "Portugal Goalkeeper" or just "Spain" must all
    resolve to that nation's single Keeper slot.
    """
    w = " ".join((written or "").strip().lower().split())
    w = re.sub(r"\bkeepers\b", "keeper", w)
    w = re.sub(r"\b(gk|goalkeeper|goalkeepers|goalie|keeping)\b", "keeper", w)
    w = " ".join(w.split())
    if w in by_full:
        return by_full[w]
    if w in by_country:                       # bare nation, e.g. "spain"
        return by_country[w]
    if w.endswith(" keeper") and w[: -len(" keeper")] in by_country:
        return by_country[w[: -len(" keeper")]]
    return None


def build_review(assignments, pool_names: list[str]) -> list[dict]:
    """For each assignment, return a review row with the best match + candidates.

    status: "exact" (name is in the pool), "fuzzy" (close matches found), or
    "unmatched" (no candidate — admin must pick or fix).
    """
    by_lower = {n.lower(): n for n in pool_names}
    kf, kc = _keeper_maps(pool_names)
    rows = []
    for a in assignments:
        written = a.player
        if written.lower() in by_lower:
            canonical = by_lower[written.lower()]
            rows.append({"participant": a.participant, "written": written,
                         "matched": canonical, "candidates": [canonical],
                         "price": a.price, "status": "exact"})
            continue
        keeper = _keeper_match(written, kf, kc)
        if keeper:
            rows.append({"participant": a.participant, "written": written,
                         "matched": keeper, "candidates": [keeper],
                         "price": a.price, "status": "exact"})
            continue
        candidates = difflib.get_close_matches(written, pool_names, n=8, cutoff=0.4)
        rows.append({
            "participant": a.participant, "written": written,
            "matched": candidates[0] if candidates else written,
            "candidates": candidates or [written],
            "price": a.price,
            "status": "fuzzy" if candidates else "unmatched",
        })
    return rows
