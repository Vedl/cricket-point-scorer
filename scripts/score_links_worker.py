"""Out-of-process WhoScored scoring worker.

Why this exists
---------------
"Calculate points" scrapes WhoScored and computes fantasy points for a whole
gameweek. Doing that *inside* the long-lived Reflex web process loads the entire
heavy stack — curl_cffi / cloudscraper / tls_client (native TLS handles), pandas,
lxml, and a one-off sklearn GradientBoostingRegressor fit for keeper scoring — plus
holds several multi-MB match pages and a DataFrame cache in memory. On the 512 MB
Render box that resident footprint never comes back (native allocator arenas +
module-level caches), so after one scoring run the web process sits near the memory
ceiling and *every* request for *every* user gets slow until a redeploy. (Confirmed:
a restart cleared the lag with the scores still in Firebase.)

Running the scrape here, in a short-lived child process that **exits** when the run
finishes, means the OS reclaims all of that memory. The parent (web process) only
ever sees lightweight JSON.

Protocol
--------
stdin  : one JSON object  {"links": [...], "is_football": bool, "countries": [...],
          "positions": {player: role}}
stdout : newline-delimited JSON, flushed per line —
           {"t": "progress", "done": <int>, "total": <int>}   (one per finished match)
           {"t": "result",   "totals": {<name>: <score|{pos:score}>}, "failed": [<label>...],
            "scored": [<match id>...], "reason": <why matches failed, or "">}
Anything on stderr is diagnostic only.
"""

from __future__ import annotations

import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# Make the repo root importable regardless of how this script is launched.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from platform_core import scoring_ops  # noqa: E402  (after sys.path setup)

# Match the in-process tuning the parent used to apply: a small pool overlaps the
# network waits while keeping the number of multi-MB pages in flight bounded, and
# WhoScored bot-blocks are usually transient so each match gets a few retries.
_WORKERS = 4
_RETRIES = 3

# stdout is the NDJSON protocol channel to the parent. The scrapers print chatty
# diagnostics with print() (i.e. to sys.stdout) from pool threads, which would
# interleave with — and corrupt — the protocol lines (worst case: the parent never
# parses the result line and the run looks empty). Capture the real stdout for the
# protocol and route all library print() noise to devnull. Genuine worker failures
# still reach the parent via the real stderr (which it drains on a non-zero exit).
_PROTO = sys.stdout
sys.stdout = open(os.devnull, "w")


def _emit(obj: dict) -> None:
    _PROTO.write(json.dumps(obj) + "\n")
    _PROTO.flush()


def _score_one(url: str, *, is_football: bool, countries: list[str],
               positions: dict | None = None):
    """Scrape + score a single match, retrying transient bot-blocks. Returns
    ``(per-player result dict or None, failure reason)``.

    A PERMANENT failure (ScraperAPI out of credits on a host where nothing else
    gets through) is not retried: each retry re-ran the whole fallback chain, which
    is what made a run with a dead quota take hours."""
    reason = ""
    for attempt in range(_RETRIES):
        try:
            return scoring_ops.score_one_link(
                url, is_football=is_football, countries=countries,
                positions=positions), ""
        except Exception as exc:  # network / bot-block / parse
            reason = str(exc) or type(exc).__name__
            if getattr(exc, "permanent", False):
                break
            if attempt < _RETRIES - 1:
                time.sleep(2 * (attempt + 1))
    return None, reason


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except Exception as exc:
        _emit({"t": "result", "totals": {}, "failed": [], "error": f"bad input: {exc}"})
        return 2

    links = payload.get("links") or []
    is_football = bool(payload.get("is_football"))
    countries = payload.get("countries") or []
    # Which formula scores each player — from the ROOM's pool, not the scorer's
    # World Cup fallback. See scoring_ops.registered_positions.
    positions = payload.get("positions") or None
    n = len(links)

    totals: dict = {}
    failed: list[str] = []
    scored: list[str] = []
    reasons: list[str] = []
    done = 0

    with ThreadPoolExecutor(max_workers=_WORKERS) as pool:
        futures = {
            pool.submit(_score_one, u, is_football=is_football, countries=countries,
                        positions=positions): u
            for u in links
        }
        for fut in as_completed(futures):
            url = futures[fut]
            try:
                result, reason = fut.result()
            except Exception as exc:
                result, reason = None, str(exc)
            # Merge on the main thread so the running totals need no locking.
            if result is None:
                failed.append(scoring_ops.match_label(url))
                reasons.append(reason)
            else:
                scoring_ops.merge_link_totals(totals, result)
                scored.append(scoring_ops.match_id(url))
            done += 1
            _emit({"t": "progress", "done": done, "total": n})

    # One line for the UI: the most common reason (they are usually all the same).
    reason = max(set(reasons), key=reasons.count) if reasons else ""
    _emit({"t": "result", "totals": totals, "failed": failed,
           "scored": scored, "reason": reason})
    return 0


if __name__ == "__main__":
    sys.exit(main())
