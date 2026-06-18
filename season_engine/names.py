"""Canonical player-name matching.

WhoScored frequently returns names without the diacritics the player pool uses
("Yan Diomande" vs "Yan Diomandé", "Sane" vs "Sané"), so exact/``.lower()``
matching drops those players' points and ownership. Match on a canonical form:
accents stripped, casefolded, whitespace collapsed. Pure stdlib, no framework.
"""

from __future__ import annotations

import unicodedata


def canonical(name) -> str:
    """Accent-insensitive, case-insensitive key for matching player names."""
    s = unicodedata.normalize("NFKD", str(name or ""))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.casefold().split())
