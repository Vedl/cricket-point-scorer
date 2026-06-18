"""Reverse-engineer the goalkeeper scoring formula from known-correct scores.

Scrapes each WhoScored match, extracts each side's goalkeeper stat line (the
features WhoScored actually exposes), pairs it with the admin-supplied correct
score, and least-squares fits new coefficients. The previous formula leaned on
features the scraper hardcodes to 0 (GoalsPrevented, KeeperSaveValue, PKFaced,
PKSaved, PossLost, Rec), so it was structurally miscalibrated for WhoScored input.

Run locally (scraping works): python scripts/fit_gk_scoring.py
"""

from __future__ import annotations

import sys
import numpy as np

import whoscored_adapter as wa

# (url, home_keeper_score, away_keeper_score) — home/away by URL slug order.
DATA = [
    ("https://www.whoscored.com/matches/1953853/live/international-fifa-world-cup-2026-mexico-south-africa", 33, 32),
    ("https://www.whoscored.com/matches/1976987/live/international-fifa-world-cup-2026-south-korea-czechia", 27, 23),
    ("https://www.whoscored.com/matches/1976989/live/international-fifa-world-cup-2026-canada-bosnia-and-herzegovina", 29, 27),
    ("https://www.whoscored.com/matches/1953865/live/international-fifa-world-cup-2026-usa-paraguay", 18, 10),
    ("https://www.whoscored.com/matches/1953856/live/international-fifa-world-cup-2026-qatar-switzerland", 47, 28),
    ("https://www.whoscored.com/matches/1953860/live/international-fifa-world-cup-2026-brazil-morocco", 28, 34),
    ("https://www.whoscored.com/matches/1953859/live/international-fifa-world-cup-2026-haiti-scotland", 21, 35),
    ("https://www.whoscored.com/matches/1976983/live/international-fifa-world-cup-2026-australia-turkiye", 51, 24),
    ("https://www.whoscored.com/matches/1953868/live/international-fifa-world-cup-2026-germany-curacao", 22, 2),
    ("https://www.whoscored.com/matches/1953874/live/international-fifa-world-cup-2026-netherlands-japan", 15, 22),
    ("https://www.whoscored.com/matches/1953869/live/international-fifa-world-cup-2026-ivory-coast-ecuador", 30, 26),
    ("https://www.whoscored.com/matches/1976979/live/international-fifa-world-cup-2026-sweden-tunisia", 24, 0),
    ("https://www.whoscored.com/matches/1953882/live/international-fifa-world-cup-2026-spain-cabo-verde", 27, 57),
    # NOTE: slug is belgium-egypt → home=Belgium(28), away=Egypt(36).
    ("https://www.whoscored.com/matches/1953876/live/international-fifa-world-cup-2026-belgium-egypt", 28, 36),
    ("https://www.whoscored.com/matches/1953883/live/international-fifa-world-cup-2026-saudi-arabia-uruguay", 49, 30),
    ("https://www.whoscored.com/matches/1953877/live/international-fifa-world-cup-2026-iran-new-zealand", 30, 21),
    ("https://www.whoscored.com/matches/1953888/live/international-fifa-world-cup-2026-france-senegal", 25, 27),
    ("https://www.whoscored.com/matches/1976997/live/international-fifa-world-cup-2026-iraq-norway", 11, 21),
    ("https://www.whoscored.com/matches/1953892/live/international-fifa-world-cup-2026-argentina-algeria", 27, 19),
    ("https://www.whoscored.com/matches/1953891/live/international-fifa-world-cup-2026-austria-jordan", 29, 11),
    ("https://www.whoscored.com/matches/1976991/live/international-fifa-world-cup-2026-portugal-dr-congo", 28, 23),
    ("https://www.whoscored.com/matches/1953900/live/international-fifa-world-cup-2026-england-croatia", 37, 29),
    ("https://www.whoscored.com/matches/1953901/live/international-fifa-world-cup-2026-ghana-panama", 37, 26),
    ("https://www.whoscored.com/matches/1953897/live/international-fifa-world-cup-2026-uzbekistan-colombia", 13, 21),
]

# Feature name -> how to read it from a GK row dict. Only WhoScored-available stats.
FEATURES = [
    "saves", "high_claims", "runs_out", "clearances", "punches", "saves_in_box",
    "passes_cmp", "failed_passes", "minutes", "goals_conceded", "clean_sheet",
    "yellow", "red", "pk_con",
]


def _gk_features_for_side(df, team_label: str):
    """Aggregate the GK(s) for one side into a single feature vector (handles a
    keeper substitution: sum counting stats + minutes, clean sheet only if the
    side conceded nothing)."""
    rows = df[(df["Pos"] == "GK") & (df["Team"] == team_label)]
    if rows.empty:
        return None
    s = lambda col: float(rows[col].sum())
    minutes = s("minutes_played")
    conceded = s("goals_conceded")
    return {
        "saves": s("Performance_Saves"),
        "high_claims": s("Performance_HighClaims"),
        "runs_out": s("Performance_RunsOut"),
        "clearances": s("Unnamed: 20_level_0_Clr"),
        "punches": s("Performance_Punches"),
        "saves_in_box": s("Performance_SavedInsideBox"),
        "passes_cmp": s("Passes_Cmp"),
        "failed_passes": s("Passes_Att") - s("Passes_Cmp"),
        "minutes": minutes,
        "goals_conceded": conceded,
        "clean_sheet": 1.0 if (conceded == 0 and minutes >= 60) else 0.0,
        "yellow": s("Performance_CrdY"),
        "red": s("Performance_CrdR"),
        "pk_con": s("Performance_PKcon"),
    }


def main():
    X, y, labels = [], [], []
    for url, home_score, away_score in DATA:
        try:
            df = wa.get_whoscored_stats(url)
        except Exception as exc:
            print(f"[skip] {url[-40:]}: {exc}")
            continue
        for team_label, score in (("Home", home_score), ("Away", away_score)):
            feats = _gk_features_for_side(df, team_label)
            if feats is None:
                print(f"[warn] no {team_label} GK for {url[-40:]}")
                continue
            X.append([feats[f] for f in FEATURES])
            y.append(score)
            labels.append(f"{url.split('-2026-')[-1]} {team_label}")

    X = np.array(X, dtype=float)
    y = np.array(y, dtype=float)
    print(f"\nFitted on {len(y)} keepers, {len(FEATURES)} features.\n")

    # Least squares with intercept.
    A = np.column_stack([np.ones(len(X)), X])
    coef, *_ = np.linalg.lstsq(A, y, rcond=None)
    intercept, weights = coef[0], coef[1:]
    pred = A @ coef
    rmse = float(np.sqrt(np.mean((pred - y) ** 2)))
    mae = float(np.mean(np.abs(pred - y)))

    print(f"intercept = {intercept:+.3f}")
    for name, w in zip(FEATURES, weights):
        print(f"  {name:16s} {w:+.3f}")
    print(f"\nRMSE = {rmse:.2f}  MAE = {mae:.2f}\n")

    order = np.argsort(-np.abs(pred - y))
    print("Largest misses (pred vs actual):")
    for i in order[:10]:
        print(f"  {labels[i]:48s} pred={pred[i]:5.1f}  actual={y[i]:4.0f}  d={pred[i]-y[i]:+.1f}")

    # Emit a ready-to-paste Python formula.
    print("\n--- new gk formula (paste into football_score_calculator) ---")
    print(f"score = {intercept:.3f}")
    src = {
        "saves": "df['Performance_Saves']", "high_claims": "df['Performance_HighClaims']",
        "runs_out": "df['Performance_RunsOut']", "clearances": "df['Unnamed: 20_level_0_Clr']",
        "punches": "df['Performance_Punches']", "saves_in_box": "df['Performance_SavedInsideBox']",
        "passes_cmp": "df['Passes_Cmp']", "failed_passes": "(df['Passes_Att'] - df['Passes_Cmp'])",
        "minutes": "df['Unnamed: 5_level_0_Min']", "goals_conceded": "df['goals_conceded']",
        "clean_sheet": "clean_sheet", "yellow": "df['Performance_CrdY']",
        "red": "df['Performance_CrdR']", "pk_con": "df['Performance_PKcon']",
    }
    for name, w in zip(FEATURES, weights):
        print(f"    + ({w:.3f}) * {src[name]}")


if __name__ == "__main__":
    sys.exit(main())
