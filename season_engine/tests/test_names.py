"""Name-matching tests, incl. the Jr/Junior-suffix disagreement between the player
pool ("Neymar Jr") and WhoScored ("Neymar") that scored such players 0 in Best-11."""

from season_engine.names import build_index, canonical, lookup


def test_accents_and_punctuation():
    idx = build_index({"Yan Diomandé": 5, "Son Heung-Min": 8})
    assert lookup(idx, "Yan Diomande") == 5
    assert lookup(idx, "Son Heungmin") == 8


def test_word_order_independent():
    idx = build_index({"Gihyuk Lee": 4})
    assert lookup(idx, "Lee Gi-Hyuk") == 4


def test_trailing_jr_suffix_matches_both_directions():
    # Pool stores "Neymar Jr"; WhoScored scores key "Neymar".
    idx = build_index({"Neymar": 15})
    assert lookup(idx, "Neymar Jr", 0) == 15
    assert lookup(idx, "Neymar Junior", 0) == 15
    # Reverse: scores carry the suffix, squad does not.
    idx2 = build_index({"Neymar Jr": 20})
    assert lookup(idx2, "Neymar", 0) == 20


def test_vinicius_junior_suffix():
    idx = build_index({"Vinicius Junior": 12})
    assert lookup(idx, "Vinicius", 0) == 12


def test_leading_junior_is_not_stripped():
    # "Junior Firpo" — "Junior" is the given name, not a suffix; must not collapse.
    idx = build_index({"Junior Firpo": 7, "Firpo Other": 3})
    assert lookup(idx, "Junior Firpo") == 7
    # A bare "Firpo" must NOT spuriously match "Junior Firpo".
    assert lookup(idx, "Firpo", 0) == 0


def test_nordic_letters_that_dont_decompose_under_nfkd():
    # WhoScored keys "Martin Ødegaard" / "Alexander Sørloth" (Ø/ø), but the pool/squad
    # store plain "Odegaard" / "Sorloth". Ø/ø do NOT decompose under NFKD, so an
    # accent-strip alone left them mismatched → those players scored 0 in Best-11.
    idx = build_index({"Martin Ødegaard": 43, "Alexander Sørloth": 19})
    assert lookup(idx, "Martin Odegaard", 0) == 43
    assert lookup(idx, "Alexander Sorloth", 0) == 19
    # And the reverse direction, plus a few other non-decomposing letters.
    assert canonical("Ødegaard") == canonical("Odegaard")
    assert canonical("Łukasz") == canonical("Lukasz")
    assert canonical("Straße") == canonical("Strasse")


def test_single_token_suffix_not_emptied():
    # Defensive: a name that is only a suffix token stays intact (no empty key).
    assert canonical("Jr") == "jr"
    idx = build_index({"Jr": 1})
    assert lookup(idx, "Jr") == 1


# --- compound surnames split differently by each source -------------------- #
def test_compound_surname_matches_however_it_is_split():
    """WhoScored spaces the pieces where UEFA hyphenates or apostrophises, e.g.
    "Myles Lewis Skelly" vs "Myles Lewis-Skelly" and "Nico O Reilly" vs "Nico
    O'Reilly". Dropping punctuation alone left those different keys, so the
    players' points were never credited to their owner."""
    pool = ["Myles Lewis-Skelly", "Nico O’Reilly", "Aaron Wan-Bissaka",
            "Warren Zaïre-Emery", "Rayan Aït-Nouri", "Son Heung-Min"]
    index = build_index({n: n for n in pool})
    whoscored = ["Myles Lewis Skelly", "Nico O Reilly", "Aaron Wan Bissaka",
                 "Warren Zaire Emery", "Rayan Ait Nouri", "Son Heungmin"]
    assert [lookup(index, w) for w in whoscored] == pool


def test_squashing_does_not_merge_genuinely_different_players():
    index = build_index({"Luis Diaz": "a", "Luis Suarez": "b"})
    assert lookup(index, "Luis Diaz") == "a"
    assert lookup(index, "Luis Suarez") == "b"
    assert lookup(index, "Diego Costa") is None
