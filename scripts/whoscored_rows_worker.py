"""Out-of-process single-match WhoScored row calculator.

Why this exists
---------------
The per-participant "Match Calculator" scrapes ONE WhoScored match and lists every
player's fantasy points. Doing that *inside* the long-lived Reflex web process loads
the whole heavy stack — curl_cffi / cloudscraper / tls_client (native TLS handles),
pandas, lxml, and potentially the sklearn keeper model — plus holds the multi-MB
match page in memory. On the 512 MB Render box that resident footprint never comes
back (native allocator arenas + module-level caches), so after one calculation the
web process sits near the memory ceiling and *every* request for *every* user gets
slow until a redeploy. This is the same root cause already fixed for the admin
bulk-scoring flow (see scripts/score_links_worker.py).

Running the scrape here, in a short-lived child process that **exits** when done,
means the OS reclaims all of that memory. The parent (web process) only ever sees
lightweight JSON.

Protocol
--------
stdin  : one JSON object  {"url": <match url>}
stdout : one JSON line —
           {"rows": [{"player","team","pos","score","minutes"}...], "error": null}  (success)
           {"rows": null, "error": <message>}                                       (failure)
Anything on stderr is diagnostic only.
"""

from __future__ import annotations

import json
import os
import sys

# Make the repo root importable regardless of how this script is launched.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# stdout is the protocol channel to the parent. The scrapers print chatty diagnostics
# with print() (i.e. to sys.stdout), which would interleave with — and corrupt — the
# single protocol line (worst case: the parent never parses it and the calc looks
# empty). Capture the real stdout for the protocol and route all library print() noise
# to devnull. Genuine failures still reach the parent via stderr (drained on a bad exit).
_PROTO = sys.stdout
sys.stdout = open(os.devnull, "w")


def _emit(obj: dict) -> None:
    _PROTO.write(json.dumps(obj) + "\n")
    _PROTO.flush()


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
        url = (payload.get("url") or "").strip()
    except Exception as exc:
        _emit({"rows": None, "error": f"bad input: {exc}"})
        return 2
    if not url:
        _emit({"rows": None, "error": "no url provided"})
        return 2

    # Import the scraper HERE, in the child — never in the parent web process. This is
    # what keeps the heavy stack out of the long-lived heap.
    from scoring import whoscored_points

    try:
        rows = whoscored_points(url)
    except Exception as exc:  # network / bot-block / parse
        _emit({"rows": None, "error": str(exc)})
        return 1
    _emit({"rows": rows, "error": None})
    return 0


if __name__ == "__main__":
    sys.exit(main())
