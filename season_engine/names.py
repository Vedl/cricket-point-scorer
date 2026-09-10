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


def _squashed(canon: str) -> str:
    """Whitespace-free key, so a compound surname matches however it is split.

    ``canonical`` drops punctuation but keeps spaces, which only bridges a name
    the OTHER source joins up ("Heung-Min" -> "heungmin" == "Heungmin"). It still
    misses the far more common case where the other source spaces the pieces
    instead: WhoScored keys "Myles Lewis Skelly" and "Nico O Reilly" while UEFA
    writes "Myles Lewis-Skelly" and "Nico O'Reilly", so the points were silently
    orphaned. Squashing both sides makes the split irrelevant."""
    return canon.replace(" ", "")


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


_MIN_SHORT_GIVEN = 3


class _MatchIndex(dict):
    """The name->value index, with the surname table carried as an ATTRIBUTE.

    Keeping it off the mapping matters: callers iterate this index (to count
    distinct values, for instance), and a stray entry whose value is a dict both
    breaks them and silently pollutes their results.
    """

    __slots__ = ("by_surname",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.by_surname: dict = {}


def build_index(mapping: dict) -> dict:
    """Turn a ``{name: value}`` dict into a match index keyed by canonical form,
    sorted-token form, AND suffix-stripped forms, so lookups tolerate accents,
    punctuation, how a compound surname is split, word order and Jr/Junior-suffix
    disagreements. Earlier names win on collision.

    Also records, per surname, each entry's first name, so :func:`lookup` can fall
    back to matching a shortened given name (see there)."""
    index = _MatchIndex()
    given: dict = {}
    for key, value in mapping.items():
        canon = canonical(key)
        index.setdefault(canon, value)
        index.setdefault(_sorted_key(canon), value)
        index.setdefault(_squashed(canon), value)
        stripped = _strip_suffix(canon)
        if stripped != canon:
            index.setdefault(stripped, value)
            index.setdefault(_sorted_key(stripped), value)
            index.setdefault(_squashed(stripped), value)
        toks = canon.split()
        if len(toks) >= 2:
            given.setdefault(toks[-1], []).append((toks[0], value))
    index.by_surname = given
    return index


def lookup(index: dict, name, default=None):
    """Look ``name`` up in a :func:`build_index` result: exact canonical, then
    word-order-independent, then whitespace-free, then with a trailing
    Jr/Junior-type suffix removed, and finally allowing a shortened given name
    (see :func:`_match_shortened_given`)."""
    canon = canonical(name)
    for key in (canon, _sorted_key(canon), _squashed(canon)):
        if key in index:
            return index[key]
    stripped = _strip_suffix(canon)
    if stripped != canon:
        for key in (stripped, _sorted_key(stripped), _squashed(stripped)):
            if key in index:
                return index[key]
    hit = _match_shortened_given(index, canon)
    if hit is not _NO_MATCH:
        return hit
    return default


_NO_MATCH = object()


def _match_shortened_given(index: dict, canon: str):
    """Last resort: same surname, one given name a shortening of the other.

    WhoScored routinely shortens Iberian given names where UEFA spells them out —
    "Maxi Araújo" for Maximiliano Araújo, "Gabri Veiga" for Gabriel Veiga — and
    those points were being credited to nobody.

    Deliberately narrow, because crediting the WRONG player is far worse than
    crediting none: the surname must match exactly, one given name must be a
    prefix of the other, the shorter must be at least three characters, and the
    candidate must be UNIQUE. That last condition is what makes it safe — three
    Garcías played in one gameweek (Eric, Fran, Joan) and none is a prefix of
    another, so Eric García correctly matches none of them rather than guessing.
    """
    given = getattr(index, "by_surname", None)
    if not given:
        return _NO_MATCH
    toks = canon.split()
    if len(toks) < 2:
        return _NO_MATCH
    mine, surname = toks[0], toks[-1]
    hits = []
    for theirs, value in given.get(surname, []):
        short, long = sorted((mine, theirs), key=len)
        if len(short) >= _MIN_SHORT_GIVEN and short != long and long.startswith(short):
            hits.append(value)
    if len(hits) == 1:
        return hits[0]
    return _NO_MATCH
