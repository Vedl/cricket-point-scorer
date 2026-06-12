"""Fix players stuck showing ON LOAN after a loan already returned.

Background
----------
The trade-based loan path used to snapshot a player's squad entry *after*
flagging it ``acquired_via="loan"``. When the loan auto-returned at the next
gameweek, that bad snapshot was handed back to the original owner — so the
player sat in their owner's squad permanently flagged on-loan, with NO matching
record in ``active_loans`` to ever re-correct it. (Fixed going forward in
``platform_core/market_ops.py`` + ``season_ops.py``.)

This one-off migration heals already-corrupted data: for every room, any squad
entry flagged ``acquired_via="loan"`` that has **no matching active loan** (i.e.
nobody is actually loaning that player *to* this participant right now) is an
orphan and gets reset to ``"trade"`` (a normal owned value the UI treats as
not-on-loan). Players genuinely loaned-in right now are left untouched.

It reads **fresh from Firebase** (not the local cache, which can be stale) and
writes back **one room at a time** via PATCH, so rooms it didn't touch are never
clobbered.

Usage
-----
    # safe dry-run — lists what WOULD change, writes nothing:
    python3 scripts/migrations/fix_orphaned_loans.py

    # apply the fix to Firebase:
    python3 scripts/migrations/fix_orphaned_loans.py --apply

    # restrict to one room:
    python3 scripts/migrations/fix_orphaned_loans.py --room 4MYGF1 --apply

Reads FIREBASE_DATABASE_URL / FIREBASE_SECRET(_KEY) from the environment (or a
local .env via python-dotenv if present), exactly like the app does.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request

try:  # load .env the same way the app does, if available
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

REPLACEMENT = "trade"  # any non-"loan" value clears the ON LOAN flag in the UI


def _base() -> tuple[str, str]:
    url = (os.environ.get("FIREBASE_DATABASE_URL") or "").rstrip("/")
    if not url:
        sys.exit("✗ FIREBASE_DATABASE_URL is not set — cannot reach Firebase.")
    secret = os.environ.get("FIREBASE_SECRET") or os.environ.get("FIREBASE_SECRET_KEY", "")
    return url, secret


def _get(url: str) -> object:
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.loads(resp.read().decode())


def _put(url: str, payload: object) -> None:
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"), method="PUT",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30):
        pass


def _squad(participant: dict) -> list:
    sq = participant.get("squad")
    return sq if isinstance(sq, list) else []


def _active_loan_targets(room: dict) -> set:
    """(borrower_name, player_name) pairs that are legitimately on loan RIGHT NOW."""
    targets = set()
    for loan in room.get("active_loans", []) or []:
        if isinstance(loan, dict):
            to = (loan.get("to") or "").strip().lower()
            player = (loan.get("player") or "").strip().lower()
            if to and player:
                targets.add((to, player))
    return targets


def scan_room(room: dict) -> list:
    """Return a list of orphaned-loan fixes for one room (does not mutate)."""
    legit = _active_loan_targets(room)
    fixes = []
    for p in room.get("participants", []) or []:
        if not isinstance(p, dict):
            continue
        owner = (p.get("name") or "").strip()
        for e in _squad(p):
            if not isinstance(e, dict) or e.get("acquired_via") != "loan":
                continue
            key = (owner.lower(), (e.get("name") or "").strip().lower())
            if key in legit:
                continue  # really on loan to this owner right now — leave it
            fixes.append({"owner": owner, "player": e.get("name", "?"), "entry": e})
    return fixes


def main() -> int:
    apply = "--apply" in sys.argv
    only_room = None
    if "--room" in sys.argv:
        idx = sys.argv.index("--room")
        if idx + 1 < len(sys.argv):
            only_room = sys.argv[idx + 1].upper()

    url, secret = _base()
    auth = f"?auth={secret}" if secret else ""

    # Fresh read straight from Firebase (bypasses any stale local cache).
    data = _get(f"{url}/auction_data.json{auth}")
    rooms = (data or {}).get("rooms", {}) if isinstance(data, dict) else {}

    total = 0
    changed_rooms = 0
    for code, room in rooms.items():
        if not isinstance(room, dict):
            continue
        if only_room and code.upper() != only_room:
            continue
        fixes = scan_room(room)
        if not fixes:
            continue
        changed_rooms += 1
        total += len(fixes)
        print(f"\nRoom {code} (GW{room.get('current_gameweek')}): "
              f"{len(fixes)} orphaned loan(s)")
        for fx in fixes:
            print(f"  • {fx['owner']:<22} {fx['player']:<24} "
                  f"acquired_via: loan → {REPLACEMENT}")
            fx["entry"]["acquired_via"] = REPLACEMENT  # mutate the in-memory room

        if apply:
            # Write back just this room node, leaving every other room untouched.
            _put(f"{url}/auction_data/rooms/{code}.json{auth}", room)
            print(f"  💾 Room {code} updated.")

    if total == 0:
        print("✅ No orphaned loans found — nothing to fix.")
        return 0

    print(f"\n{'APPLIED' if apply else 'WOULD FIX'} {total} entr"
          f"{'y' if total == 1 else 'ies'} across {changed_rooms} room(s).")
    if apply:
        # Bump the root version stamp so other workers' cheap _v probe notices.
        import time
        _put(f"{url}/auction_data/_v.json{auth}", int(time.time() * 1000))
        print("💾 Saved to Firebase. Bumped root version stamp.")
    else:
        print("ℹ️  Dry-run only. Re-run with --apply to write the changes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
