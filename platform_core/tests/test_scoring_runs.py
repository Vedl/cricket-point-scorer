"""Compute runs: which links count, how a run folds into a gameweek, and failing fast.

2026-11-04: ScraperAPI ran out of credits, so every match on Render fell through
the whole fallback chain (×3 worker retries) and a run took hours. Retrying "just
the failed links" would then have REPLACED the gameweek with only those matches,
and a pasted line of team names was scraped as if it were a URL.
"""

import importlib
import sys
from pathlib import Path

import pytest

from platform_core import scoring_ops as sc

UCL = "https://www.whoscored.com/matches/{}/live/europe-champions-league-2026-2027-{}"
A = UCL.format(2029135, "barcelona-aston-villa")
B = UCL.format(2029205, "shakhtar-donetsk-sporting-cp")
C = UCL.format(2029147, "borussia-dortmund-real-betis")


# ── pasted links ─────────────────────────────────────────────────────────────

def test_only_whoscored_match_links_are_accepted():
    links, rejected = sc.split_links(
        f"{A}\n\n  {B}  \nArsenal Paris Saint-Germain Manchester City\n"
        "https://www.whoscored.com/Regions/250/Tournaments/12\n")
    assert links == [A, B]
    assert rejected == ["Arsenal Paris Saint-Germain Manchester City",
                        "https://www.whoscored.com/Regions/250/Tournaments/12"]


def test_the_same_match_pasted_twice_is_scraped_once():
    other_view = A.replace("/live/", "/show/")
    assert sc.parse_links(f"{A}\n{other_view}") == [A]


def test_match_id():
    assert sc.match_id(A) == "2029135"
    assert sc.match_id("https://whoscored.com/Matches/1953889/Live/x") == "1953889"
    assert sc.match_id("Arsenal v PSG") is None


@pytest.mark.parametrize("url,label", [
    (A, "barcelona-aston-villa"),
    ("https://www.whoscored.com/matches/1953889/live/"
     "international-fifa-world-cup-2026-mexico-south-africa", "mexico-south-africa"),
])
def test_match_label_drops_the_whole_season_prefix(url, label):
    # Splitting on "-2026-" used to leave "2027-barcelona-aston-villa".
    assert sc.match_label(url) == label


# ── folding a run into the gameweek ──────────────────────────────────────────

def _room(scores=None, matches=None):
    room = {"gameweek_scores": {}}
    if scores is not None:
        room["gameweek_scores"]["4"] = scores
    if matches is not None:
        room["gameweek_matches"] = matches
    return room


def test_first_run_saves_and_records_its_matches():
    room = _room()
    assert sc.apply_scoring_run(room, "4", {"Raphinha": 10}, ["2029135"]) == "replaced"
    assert room["gameweek_scores"]["4"] == {"Raphinha": 10}
    assert sc.gameweek_matches(room, 4) == {"2029135"}


def test_retrying_the_failed_matches_adds_them():
    room = _room({"Raphinha": 10, "Barcelona Keeper": 20}, {"4": ["2029135"]})
    action = sc.apply_scoring_run(room, "4", {"Gyökeres": 8, "Raphinha": 0}, ["2029205"])
    assert action == "added"
    assert room["gameweek_scores"]["4"] == {"Raphinha": 10, "Barcelona Keeper": 20,
                                           "Gyökeres": 8}
    assert sc.gameweek_matches(room, "4") == {"2029135", "2029205"}


def test_added_dual_position_scores_sum_per_position():
    room = _room({"Player": {"MID": 5, "FWD": 4}}, {"4": ["2029135"]})
    sc.apply_scoring_run(room, "4", {"Player": {"MID": 2, "FWD": 3}}, ["2029205"])
    assert room["gameweek_scores"]["4"]["Player"] == {"MID": 7, "FWD": 7}


def test_a_full_rerun_replaces_so_corrections_land():
    room = _room({"Raphinha": 10, "Gyökeres": 8}, {"4": ["2029135", "2029205"]})
    action = sc.apply_scoring_run(room, "4", {"Raphinha": 12, "Gyökeres": 8, "Guirassy": 6},
                                  ["2029135", "2029205", "2029147"])
    assert action == "replaced"
    assert room["gameweek_scores"]["4"] == {"Raphinha": 12, "Gyökeres": 8, "Guirassy": 6}


def test_a_partial_overlap_saves_nothing():
    stored = {"Raphinha": 10, "Gyökeres": 8}
    room = _room(dict(stored), {"4": ["2029135", "2029205"]})
    assert sc.apply_scoring_run(room, "4", {"Raphinha": 10, "Guirassy": 6},
                                ["2029135", "2029147"]) == "conflict"
    assert room["gameweek_scores"]["4"] == stored
    assert sc.gameweek_matches(room, "4") == {"2029135", "2029205"}


def test_a_gameweek_scored_before_tracking_is_replaced_like_before():
    room = _room({"Old": 3})
    assert sc.apply_scoring_run(room, "4", {"New": 5}, ["2029147"]) == "replaced"
    assert room["gameweek_scores"]["4"] == {"New": 5}


def test_firebase_array_encoding_of_the_match_record_is_read_and_rewritten():
    room = _room({"Raphinha": 10}, [None, None, None, None, ["2029135"]])
    assert sc.gameweek_matches(room, "4") == {"2029135"}
    assert sc.apply_scoring_run(room, "4", {"Gyökeres": 8}, ["2029205"]) == "added"
    assert room["gameweek_matches"] == {"4": ["2029135", "2029205"]}


def test_scores_typed_in_by_hand_drop_the_match_record():
    room = _room({"X": 1}, {"4": ["2029135"], "3": ["1"]})
    sc.forget_gameweek_matches(room, "4")
    assert room["gameweek_matches"] == {"3": ["1"]}


# ── failing fast ─────────────────────────────────────────────────────────────

class _Resp:
    def __init__(self, status, text):
        self.status_code, self.text = status, text


@pytest.mark.parametrize("env,enabled", [
    ({}, True),
    ({"RENDER": "true"}, False),
    ({"RENDER": "true", "WHOSCORED_IP_FALLBACKS": "1"}, True),
    ({"WHOSCORED_IP_FALLBACKS": "0"}, False),
])
def test_slow_fallbacks_are_off_on_render_unless_forced(env, enabled):
    import whoscored_adapter as wa
    assert wa._slow_fallbacks_enabled(env) is enabled


def _adapter(monkeypatch, *, render):
    import whoscored_adapter as wa
    monkeypatch.setenv("SCRAPER_API_KEY", "k")
    monkeypatch.setattr(wa, "_SLOW_FALLBACKS", not render)
    monkeypatch.setattr(wa, "_SCRAPERAPI_DEAD_REASON", None)
    return wa


def test_out_of_credits_on_render_fails_once_and_permanently(monkeypatch):
    wa = _adapter(monkeypatch, render=True)
    calls = {"scraperapi": 0, "swarm": 0}

    def fake_get(url, **kw):
        calls["scraperapi"] += 1
        return _Resp(403, "You have exhausted the API Credits available in this monthly cycle")

    def boom(*a, **kw):
        raise RuntimeError("blocked")

    monkeypatch.setattr(wa.std_requests, "get", fake_get)
    monkeypatch.setattr(wa.requests, "get", boom)
    monkeypatch.setattr(wa.tls_client, "Session", boom)
    monkeypatch.setattr(wa, "fetch_with_free_proxies",
                        lambda url: calls.__setitem__("swarm", calls["swarm"] + 1))

    for url in (A, B):
        with pytest.raises(wa.WhoScoredUnavailable) as err:
            wa.get_whoscored_stats(url)
        assert err.value.permanent
        assert "out of credits" in str(err.value)
    assert calls == {"scraperapi": 1, "swarm": 0}  # asked once, no slow fallbacks


def test_off_render_the_slow_fallbacks_still_run(monkeypatch):
    wa = _adapter(monkeypatch, render=False)
    swarm = []
    monkeypatch.setattr(wa.std_requests, "get",
                        lambda url, **kw: _Resp(403, "exhausted the API Credits"))
    monkeypatch.setattr(wa.requests, "get", lambda *a, **kw: _Resp(403, ""))
    monkeypatch.setattr(wa.tls_client, "Session", lambda **kw: (_ for _ in ()).throw(RuntimeError()))
    monkeypatch.setattr(wa, "fetch_with_free_proxies", lambda url: swarm.append(url))
    monkeypatch.setattr(wa.cloudscraper, "create_scraper",
                        lambda **kw: (_ for _ in ()).throw(RuntimeError()))
    with pytest.raises(wa.WhoScoredUnavailable) as err:
        wa.get_whoscored_stats(C)
    assert swarm == [C]
    assert not err.value.permanent


def test_a_match_not_yet_played_says_so_without_trying_fallbacks(monkeypatch):
    wa = _adapter(monkeypatch, render=False)
    swarm = []
    monkeypatch.delenv("SCRAPER_API_KEY")
    monkeypatch.setattr(wa.requests, "get", lambda *a, **kw: _Resp(
        200, "<script>var matchCentreData: null, matchCentreEventTypeJson = {}</script>"))
    monkeypatch.setattr(wa, "fetch_with_free_proxies", lambda url: swarm.append(url))
    with pytest.raises(wa.WhoScoredUnavailable, match="hasn't been played") as err:
        wa.get_whoscored_stats(C)
    assert err.value.permanent and swarm == []


@pytest.fixture
def worker(monkeypatch):
    root = Path(__file__).resolve().parents[2]
    monkeypatch.syspath_prepend(str(root / "scripts"))
    stdout = sys.stdout
    mod = importlib.import_module("score_links_worker")
    sys.stdout = stdout  # the worker redirects stdout on import
    monkeypatch.setattr(mod.time, "sleep", lambda s: None)
    return mod


def test_worker_does_not_retry_a_permanent_failure(worker, monkeypatch):
    import whoscored_adapter as wa
    calls = []

    def fail(url, **kw):
        calls.append(url)
        raise wa.WhoScoredUnavailable("ScraperAPI is out of credits for this month",
                                      permanent=True)

    monkeypatch.setattr(worker.scoring_ops, "score_one_link", fail)
    result, reason = worker._score_one(A, is_football=True, countries=[])
    assert result is None and calls == [A]
    assert reason == "ScraperAPI is out of credits for this month"


def test_worker_retries_a_transient_failure(worker, monkeypatch):
    calls = []

    def flaky(url, **kw):
        calls.append(url)
        if len(calls) < 2:
            raise ValueError("WhoScored blocked every fetch method")
        return {"Raphinha": 10}

    monkeypatch.setattr(worker.scoring_ops, "score_one_link", flaky)
    assert worker._score_one(A, is_football=True, countries=[]) == ({"Raphinha": 10}, "")
    assert len(calls) == 2
