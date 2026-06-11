"""Text helpers shared across search/matching features.

``fold`` strips accents/diacritics in any script that decomposes under NFKD
(é→e, ü→u, ł stays — handled via the extra map) and lowercases, so participants
can type "desire doue" and match "Désiré Doué".
"""

from __future__ import annotations

import unicodedata

# Characters that don't decompose under NFKD but are common in player names.
_EXTRA = str.maketrans({
    "ø": "o", "Ø": "o", "đ": "d", "Đ": "d", "ł": "l", "Ł": "l",
    "ß": "ss", "æ": "ae", "Æ": "ae", "œ": "oe", "Œ": "oe",
    "ð": "d", "Ð": "d", "þ": "th", "Þ": "th", "ı": "i",
})


def fold(s: str) -> str:
    """Accent-insensitive, case-insensitive form of ``s`` for matching."""
    s = (s or "").translate(_EXTRA)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.lower().strip()


def contains(haystack: str, needle: str) -> bool:
    """Accent/case-insensitive substring test."""
    return fold(needle) in fold(haystack)
