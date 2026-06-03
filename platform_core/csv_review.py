"""CSV roster review — fuzzy-match written player names to the tournament pool.

People write "Silva" but several players named Silva are at the World Cup. This
builds a review table so the admin confirms exactly which pool player each written
name maps to, before committing — so squads and scoring use the canonical names.
"""

from __future__ import annotations

import difflib


def build_review(assignments, pool_names: list[str]) -> list[dict]:
    """For each assignment, return a review row with the best match + candidates.

    status: "exact" (name is in the pool), "fuzzy" (close matches found), or
    "unmatched" (no candidate — admin must pick or fix).
    """
    by_lower = {n.lower(): n for n in pool_names}
    rows = []
    for a in assignments:
        written = a.player
        if written.lower() in by_lower:
            canonical = by_lower[written.lower()]
            rows.append({"participant": a.participant, "written": written,
                         "matched": canonical, "candidates": [canonical],
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
