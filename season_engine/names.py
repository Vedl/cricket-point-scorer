"""Canonical player-name matching.

WhoScored, the player pool and squad spellings disagree in three ways:
  * diacritics  — "Yan Diomande" vs "Yan Diomandé", "Çağlar" vs "Caglar"
  * hyphens/punctuation — "Son Heung-Min" vs "Son Heungmin", "Wan-Bissaka"
  * word order — "Lee Gi-Hyuk" vs "Gihyuk Lee" (romanised surname/given swaps)

Match on a canonical form (accents stripped, punctuation removed, casefolded,
whitespace collapsed) with a word-order-independent fallback. Pure stdlib.
"""

from __future__ import annotations

import unicodedata


def canonical(name) -> str:
    """Accent-, punctuation- and case-insensitive key for matching names."""
    s = unicodedata.normalize("NFKD", str(name or ""))
    s = "".join(c for c in s if not unicodedata.combining(c))
    # Drop punctuation (hyphens, apostrophes, dots) entirely so "Heung-Min" and
    # "Heungmin" collapse together; keep alphanumerics and spaces.
    s = "".join(c if (c.isalnum() or c.isspace()) else "" for c in s)
    return " ".join(s.casefold().split())


def _sorted_key(canon: str) -> str:
    """Order-independent key: tokens of a canonical string, sorted."""
    return " ".join(sorted(canon.split()))


def build_index(mapping: dict) -> dict:
    """Turn a ``{name: value}`` dict into a match index keyed by canonical form
    AND by sorted-token form, so lookups tolerate accents, punctuation and word
    order. Earlier names win on collision."""
    index: dict = {}
    for key, value in mapping.items():
        canon = canonical(key)
        index.setdefault(canon, value)
        index.setdefault(_sorted_key(canon), value)
    return index


def lookup(index: dict, name, default=None):
    """Look ``name`` up in a :func:`build_index` result (exact canonical first,
    then word-order-independent)."""
    canon = canonical(name)
    if canon in index:
        return index[canon]
    return index.get(_sorted_key(canon), default)
