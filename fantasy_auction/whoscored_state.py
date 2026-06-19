"""WhoScored match points calculator — available to every logged-in participant."""

from __future__ import annotations

import asyncio
import json
import os
import sys

import reflex as rx

from .state import AppState

# The single-match calculator scrapes WhoScored in a SHORT-LIVED CHILD PROCESS (see
# scripts/whoscored_rows_worker.py) instead of in this long-lived web process. The
# scrape stack — curl_cffi / cloudscraper / tls_client (native TLS), pandas, and the
# sklearn keeper model — plus the multi-MB match page would otherwise load into the web
# heap and never return to the OS on the 512 MB Render box, leaving every request slow
# for everyone until a redeploy. The child exits when done, so the kernel reclaims all
# of it; the web process only handles lightweight JSON. (Same fix as the admin
# bulk-scoring flow — see fantasy_auction/season_state.run_whoscored_scoring.)
_ROWS_WORKER = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "scripts", "whoscored_rows_worker.py",
)
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


async def _scrape_rows(url: str) -> tuple[list[dict] | None, str | None]:
    """Scrape one match's per-player rows in a child process.

    Returns ``(rows, None)`` on success (``rows`` may be an empty list when the match
    had no player data) or ``(None, error)`` if the child couldn't read the match.
    """
    payload = json.dumps({"url": url})
    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, _ROWS_WORKER,
            cwd=_REPO_ROOT,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, err = await proc.communicate(payload.encode())
    except Exception as exc:
        return None, str(exc)
    rows = None
    err_msg = None
    for line in out.splitlines():
        try:
            msg = json.loads(line.decode())
        except ValueError:
            continue
        if not isinstance(msg, dict):
            continue
        if msg.get("error"):
            err_msg = str(msg["error"])
        if msg.get("rows") is not None:
            rows = msg["rows"]
    if rows is not None:
        return rows, None
    if err_msg:
        return None, err_msg
    tail = err.decode(errors="replace")[-400:].strip()
    return None, tail or f"worker exited with code {proc.returncode}"


class WhoScoredState(rx.State):
    url: str = ""
    running: bool = False
    error: str = ""
    results: list[dict[str, str]] = []
    count: int = 0
    room_code: str = ""

    @rx.event
    def set_field(self, name: str, value):
        setattr(self, name, value)

    @rx.event
    async def guard(self):
        app = await self.get_state(AppState)
        for _ in range(60):  # allow either a member or a hydrated spectator session
            if app.auth_user or app.is_hydrated:
                break
            await asyncio.sleep(0.05)
        if not app.auth_user and not app.spectating:
            return rx.redirect("/")
        self.room_code = (self.router._page.params.get("room", "") or "").upper()

    @rx.event(background=True)
    async def run(self):
        async with self:
            if self.running:
                return
            self.running = True
            self.error = ""
            self.results = []
            self.count = 0
            url = self.url.strip()
        if not url:
            async with self:
                self.running = False
                self.error = "Paste a WhoScored match link first."
            return
        rows, err = await _scrape_rows(url)
        async with self:
            self.running = False
            if rows is None:
                self.error = f"Couldn't read that match (WhoScored may be blocking): {err}"
            elif not rows:
                self.error = "No player data found at that link."
            else:
                self.results = [
                    {"player": r["player"], "team": r["team"], "pos": r["pos"],
                     "score": str(r["score"]), "minutes": str(r["minutes"])}
                    for r in rows
                ]
                self.count = len(rows)
