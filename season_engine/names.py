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

# Letters that DON'T decompose under NFKD, so an accent-strip alone leaves them
# mismatched — e.g. WhoScored keys "Martin Ødegaard" / "Alexander Sørloth" while the
# pool/squad store "Martin Odegaard" / "Alexander Sorloth". Transliterate these
# explicitly BEFORE normalising. (Mirrors platform_core.textutil.fold.)
_TRANSLIT = str.maketrans({
    "ø": "o", "Ø": "o", "đ": "d", "Đ": "d", "ł": "l", "Ł": "l",
    "ß": "ss", "æ": "ae", "Æ": "ae", "œ": "oe", "Œ": "oe",
    "ð": "d", "Ð": "d", "þ": "th", "Þ": "th", "ı": "i",
})

# Genuine transliteration disagreements — different letter sequences, not accent/
# punctuation/order variants, so no general rule can bridge them. Verified against
# real WC 2026 data (room 4MYGF1): pool/squad stored "Mohanad Lashin" and "Marawan
# Attia"; WhoScored keys them "Mohanad Lasheen" and "Marwan Attia". Both players'
# points were silently orphaned (never credited to their owning team) until added
# here. Keys are the pool/squad (wrong) canonical form; values are WhoScored's.
_NAME_ALIASES = {
    "mohanad lashin": "mohanad lasheen",
    "marawan attia": "marwan attia",
}


def canonical(name) -> str:
    """Accent-, punctuation- and case-insensitive key for matching names."""
    s = str(name or "").translate(_TRANSLIT)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    # Drop punctuation (hyphens, apostrophes, dots) entirely so "Heung-Min" and
    # "Heungmin" collapse together; keep alphanumerics and spaces.
    s = "".join(c if (c.isalnum() or c.isspace()) else "" for c in s)
    canon = " ".join(s.casefold().split())
    return _NAME_ALIASES.get(canon, canon)


def _sorted_key(canon: str) -> str:
    """Order-independent key: tokens of a canonical string, sorted."""
    return " ".join(sorted(canon.split()))


# Generational / honorific suffixes that sources disagree on: the player pool stores
# "Neymar Jr" while WhoScored keys him "Neymar"; likewise "Vinicius Junior" vs
# "Vinicius". Only stripped when TRAILING, so a real leading name ("Junior Firpo") is
# left untouched.
_NAME_SUFFIXES = {"jr", "jnr", "junior", "sr", "snr", "senior", "ii", "iii", "iv"}


def _strip_suffix(canon: str) -> str:
    """Drop trailing generational suffix tokens (never the only token)."""
    toks = canon.split()
    while len(toks) > 1 and toks[-1] in _NAME_SUFFIXES:
        toks.pop()
    return " ".join(toks)


def build_index(mapping: dict) -> dict:
    """Turn a ``{name: value}`` dict into a match index keyed by canonical form,
    sorted-token form, AND suffix-stripped forms, so lookups tolerate accents,
    punctuation, word order and Jr/Junior-suffix disagreements. Earlier names win
    on collision."""
    index: dict = {}
    for key, value in mapping.items():
        canon = canonical(key)
        index.setdefault(canon, value)
        index.setdefault(_sorted_key(canon), value)
        stripped = _strip_suffix(canon)
        if stripped != canon:
            index.setdefault(stripped, value)
            index.setdefault(_sorted_key(stripped), value)
    return index


def lookup(index: dict, name, default=None):
    """Look ``name`` up in a :func:`build_index` result: exact canonical, then
    word-order-independent, then with a trailing Jr/Junior-type suffix removed."""
    canon = canonical(name)
    for key in (canon, _sorted_key(canon)):
        if key in index:
            return index[key]
    stripped = _strip_suffix(canon)
    if stripped != canon:
        for key in (stripped, _sorted_key(stripped)):
            if key in index:
                return index[key]
    return default
