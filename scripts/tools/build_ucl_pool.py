#!/usr/bin/env python3
"""Build ``ucl_2026_players.json`` from a UEFA.com squad dump.

uefa.com blocks non-browser HTTP clients (requests/curl hang), so the squads are
collected by running the snippet below in a browser sitting on the competition's
clubs page, then piping the resulting pipe-delimited rows through this script:

    python scripts/tools/build_ucl_pool.py ucl_raw.txt ucl_2026_players.json

Each input row is ``club|uefa_id|role|name|short_name|nationality|list_b`` where
``role`` is UEFA's own squad-list heading (Goalkeeper/Defender/Midfielder/Forward)
— positions come from UEFA only, never from a second source.

Browser snippet (run on https://www.uefa.com/uefachampionsleague/clubs/ — it
same-origin-fetches every league-phase club's squad page):

    const roleMap = {Goalkeepers:'Goalkeeper', Defenders:'Defender',
                     Midfielders:'Midfielder', Forwards:'Forward'};
    const clubs = [...document.querySelectorAll('h2,h3,h4')]
      .find(h => h.textContent.trim() === 'League phase')
      .closest('div, section');
    const hrefs = [...new Set([...clubs.querySelectorAll('a[href*="/clubs/"]')]
      .map(a => a.getAttribute('href')).filter(h => /\\/clubs\\/\\d+/.test(h)))];
    const rows = [];
    for (const href of hrefs) {
      const doc = new DOMParser().parseFromString(
        await (await fetch(href + 'squad/', {credentials: 'same-origin'})).text(), 'text/html');
      const club = doc.querySelector('h1, .team--name')?.textContent.trim();
      for (const h of doc.querySelectorAll('h2.squadlist--role')) {
        const role = roleMap[h.textContent.trim()];
        if (!role) continue;
        for (let n = h.nextElementSibling;
             n && !(n.tagName === 'H2' && n.classList.contains('squadlist--role'));
             n = n.nextElementSibling) {
          for (const a of n.querySelectorAll('a[href*="/players/"]')) {
            const id = (a.getAttribute('href').match(/players\\/(\\d+)/) || [])[1];
            const spans = [...a.querySelectorAll('span[slot="primary"]')]
              .map(s => s.textContent.replace(/\\s+/g, ' ').trim());
            const clean = s => (s || '').replace(/\\s*\\*\\s*$/, '').trim();
            rows.push([club, id, role, clean(a.getAttribute('title') || spans[0]),
                       clean(spans[1] || spans[0]),
                       a.querySelector('[itemprop="country"]').textContent.trim(),
                       /\\*/.test(spans.join(' ')) ? 1 : 0].join('|'));
          }
        }
      }
    }
    rows.join('\\n')
"""

from __future__ import annotations

import json
import sys
from collections import Counter

COMPETITION = "UEFA Champions League"
SEASON = "2026/27"
SOURCE = "https://www.uefa.com/uefachampionsleague/clubs/"
ROLES = {"Goalkeeper", "Defender", "Midfielder", "Forward"}


def parse(text: str) -> list[dict]:
    players, seen = [], set()
    for lineno, line in enumerate(text.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        parts = line.split("|")
        if len(parts) != 7:
            raise SystemExit(f"line {lineno}: expected 7 fields, got {len(parts)}: {line!r}")
        club, uefa_id, role, name, short, nat, list_b = (p.strip() for p in parts)
        if role not in ROLES:
            raise SystemExit(f"line {lineno}: unknown UEFA position {role!r}")
        if uefa_id in seen:
            raise SystemExit(f"line {lineno}: duplicate UEFA id {uefa_id}")
        seen.add(uefa_id)
        players.append({
            "name": name,
            "short_name": short,
            "role": role,
            "team": club,
            "nationality": nat,
            "uefa_id": uefa_id,
            "list_b": list_b == "1",
        })
    return players


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit(f"usage: {sys.argv[0]} <raw.txt> <out.json>")
    players = parse(open(sys.argv[1], encoding="utf-8").read())
    doc = {
        "competition": COMPETITION,
        "season": SEASON,
        "source": SOURCE,
        "note": "Positions are UEFA's own squad-list headings. list_b marks UEFA "
                "List B (youth) registrations, which the auction pool excludes.",
        "players": players,
    }
    with open(sys.argv[2], "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
        f.write("\n")

    clubs = Counter(p["team"] for p in players)
    print(f"{len(players)} players across {len(clubs)} clubs -> {sys.argv[2]}")
    print("  by position:", dict(Counter(p["role"] for p in players)))
    print(f"  List B (excluded from the pool): {sum(p['list_b'] for p in players)}")


if __name__ == "__main__":
    main()
