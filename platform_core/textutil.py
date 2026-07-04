"""Text helpers shared across search/matching features.

``fold`` strips accents/diacritics in any script that decomposes under NFKD
(é→e, ü→u, ł stays — handled via the extra map) and lowercases, so participants
can type "desire doue" and match "Désiré Doué".
"""

from __future__ import annotations

import unicodedata
from functools import lru_cache

# Characters that don't decompose under NFKD but are common in player names.
_EXTRA = str.maketrans({
    "ø": "o", "Ø": "o", "đ": "d", "Đ": "d", "ł": "l", "Ł": "l",
    "ß": "ss", "æ": "ae", "Æ": "ae", "œ": "oe", "Œ": "oe",
    "ð": "d", "Ð": "d", "þ": "th", "Þ": "th", "ı": "i",
})


# Memoised: search/matching folds the same ~1300 pool names over and over (every
# keystroke, every bidding refresh). The unicodedata pass is pure — a bounded
# lookup table makes repeat folds a dict hit. 16k entries ≈ a few hundred KB max.
@lru_cache(maxsize=16384)
def _fold_cached(s: str) -> str:
    s = s.translate(_EXTRA)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.lower().strip()


def fold(s: str) -> str:
    """Accent-insensitive, case-insensitive form of ``s`` for matching."""
    return _fold_cached(s or "")


def contains(haystack: str, needle: str) -> bool:
    """Accent/case-insensitive substring test."""
    return fold(needle) in fold(haystack)
