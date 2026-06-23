#!/usr/bin/env python3
"""One-off fix: set Gakpo-lype's Gameweek 2 Injury Reserve to Nathan Aké.

Room 4MYGF1, participant "Gakpo-lype", had Pedri locked as the GW2 IR. The owner
asked for it to be Nathan Aké instead. For a LOCKED gameweek the IR that scoring
reads is NOT the live ``participant["ir"]`` — it's frozen into the snapshot at
``rooms/4MYGF1/gameweek_squads/"2"/"Gakpo-lype"/ir`` (see platform_core.season_ops
._participants_for_gameweek, which reads ``team_snap.get("ir")``). So this is the
only field we touch — exactly one surgical change, nothing else.

Why a script (not the admin UI): the normal "set IR" control writes the *live*
participant IR for the upcoming gameweek; it does not rewrite an already-locked
snapshot. Hence the targeted edit here.

Safe by default: this prints the plan and changes NOTHING unless you pass
``--commit``. Run it against the production Realtime DB by exporting the same env
the app uses:

    export FIREBASE_DATABASE_URL="https://<your-db>.firebaseio.com"
    # export FIREBASE_SECRET="..."        # only if your DB needs the legacy auth
    python scripts/migrations/set_gw2_ir_gakpo_lype.py            # dry run
    python scripts/migrations/set_gw2_ir_gakpo_lype.py --commit   # apply

Run it while the room is quiescent (no active bidding/admin actions on 4MYGF1) so a
concurrent app write can't clobber the edit. It writes through ``FirebaseStore.save``
so the document version stamp (``_v``) is bumped and the running app picks the
change up on its next refresh.
"""

from __future__ import annotations

import sys
import unicodedata
from pathlib import Path

# Allow running from anywhere (the repo root must be importable for platform_core).
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from platform_core.firebase_store import FirebaseStore

ROOM_CODE = "4MYGF1"
PARTICIPANT = "Gakpo-lype"
GAMEWEEK = "2"
NEW_IR = "Nathan Aké"
EXPECTED_OLD_IR = "Pedri"


def _norm(s: str) -> str:
    """Accent- and case-insensitive key so 'Nathan Ake' matches 'Nathan Aké'."""
    s = unicodedata.normalize("NFKD", str(s or ""))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.casefold().strip()


def _canonical_squad_name(squad: list[dict], wanted: str) -> str | None:
    """Return the player's name exactly as stored in the locked squad snapshot
    (so the IR string matches the squad entry and the score feed), or None."""
    for e in squad:
        if _norm(e.get("name")) == _norm(wanted):
            return e.get("name")
    return None


def main() -> int:
    commit = "--commit" in sys.argv[1:]

    store = FirebaseStore()
    if not store.use_remote:
        print("WARNING: FIREBASE_DATABASE_URL is not set — operating on the LOCAL "
              f"cache file only ({store.local_file_path}), not production Firebase.")

    doc = store.load()
    room = doc.get("rooms", {}).get(ROOM_CODE)
    if room is None:
        print(f"ERROR: room {ROOM_CODE} not found.")
        return 1

    gw_squads = room.get("gameweek_squads", {})
    snap = gw_squads.get(GAMEWEEK)
    if not isinstance(snap, dict):
        print(f"ERROR: no locked snapshot for gameweek {GAMEWEEK} in {ROOM_CODE}.")
        return 1

    team = snap.get(PARTICIPANT)
    if not isinstance(team, dict):
        print(f"ERROR: '{PARTICIPANT}' has no GW{GAMEWEEK} snapshot "
              f"(found: {sorted(snap.keys())}).")
        return 1

    squad = team.get("squad", []) or []
    current_ir = team.get("ir")
    canonical = _canonical_squad_name(squad, NEW_IR)

    print(f"Room {ROOM_CODE} · {PARTICIPANT} · Gameweek {GAMEWEEK}")
    print(f"  squad size       : {len(squad)}")
    print(f"  current IR       : {current_ir!r}")
    print(f"  requested new IR : {NEW_IR!r}")

    if canonical is None:
        print(f"ERROR: {NEW_IR!r} is not in {PARTICIPANT}'s locked GW{GAMEWEEK} squad — "
              "refusing to set an IR that isn't a squad member. Squad: "
              f"{[e.get('name') for e in squad]}")
        return 1

    if _norm(current_ir) == _norm(canonical):
        print(f"Nothing to do: IR is already {current_ir!r}.")
        return 0

    if current_ir is not None and _norm(current_ir) != _norm(EXPECTED_OLD_IR):
        print(f"NOTE: current IR is {current_ir!r}, not the expected "
              f"{EXPECTED_OLD_IR!r}. Proceeding to set {canonical!r} anyway.")

    print(f"  -> will set IR to: {canonical!r}")

    if not commit:
        print("\nDRY RUN — no write performed. Re-run with --commit to apply.")
        return 0

    team["ir"] = canonical
    # If this snapshot also carries the legacy key, keep the two consistent.
    if "injury_reserve" in team:
        team["injury_reserve"] = canonical

    store.save(doc)
    print(f"\n✅ Committed: {PARTICIPANT} GW{GAMEWEEK} IR is now {canonical!r}.")
    print("   (Only the gameweek_squads snapshot was changed — IR fee, budget, and "
          "the live squad are untouched.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
