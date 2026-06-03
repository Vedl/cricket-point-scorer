"""Scoring + scraping layer for the migrated app.

The legacy score calculators and schedule scrapers are already framework-free, so
they are reused as-is (PLAN.md §4 "ported as-is"). This package re-exports a clean
surface; heavy scraper deps are imported lazily so plain scoring needs only pandas.
"""

from player_score_calculator import CricketScoreCalculator

__all__ = ["CricketScoreCalculator", "football", "scrapers"]


def __getattr__(name):
    # Lazy access to optional heavy modules.
    if name == "football":
        import football_score_calculator as football
        return football
    if name == "scrapers":
        import types
        mod = types.ModuleType("scrapers")
        import cricbuzz_scraper
        mod.CricbuzzScraper = cricbuzz_scraper.CricbuzzScraper
        return mod
    raise AttributeError(name)
