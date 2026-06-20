import re
import json
import pandas as pd
from curl_cffi import requests
import cloudscraper
import tls_client
import concurrent.futures
import requests as std_requests
from bs4 import BeautifulSoup
import time
import os

POS_MAP = {'GK':'GK','DR':'DEF','DC':'DEF','DL':'DEF','DMR':'DEF','DML':'DEF',
           'MC':'MID','DMC':'MID','AMC':'MID','MR':'MID','ML':'MID',
           'AMR':'MID','AML':'MID','FW':'FWD','FWR':'FWD','FWL':'FWD','Sub':'MID'}

# Scrape-once cache: a match is scraped twice per scoring run (outfield players +
# keepers both call get_whoscored_stats). Memoising by URL halves the network +
# parse work. Entries carry a short TTL because a match scraped while its stats are
# still PRELIMINARY (live / just-finished) must not be frozen forever — that froze a
# thin early stat line and made re-runs keep returning a stale (too-low) score until
# the server restarted. The dedupe a single scoring run needs happens within seconds,
# so a short TTL keeps that benefit while letting a re-run minutes later pick up
# WhoScored's finalised stats. Bounded so it can't grow without limit on the server.
_STATS_CACHE = {}
_STATS_CACHE_ORDER = []
_STATS_CACHE_MAX = 64
_STATS_CACHE_TTL = 600  # seconds (10 min)


def _stats_cache_put(url, df):
    _STATS_CACHE[url] = (df, time.time())
    _STATS_CACHE_ORDER.append(url)
    if len(_STATS_CACHE_ORDER) > _STATS_CACHE_MAX:
        _STATS_CACHE.pop(_STATS_CACHE_ORDER.pop(0), None)

def sum_stat(sd):
    if not sd or not isinstance(sd, dict): return 0
    return sum(float(v) for v in sd.values())

def test_proxy(proxy_url, target_url):
    proxies = {"http": f"http://{proxy_url}", "https": f"http://{proxy_url}"}
    try:
        r = requests.get(target_url, impersonate='chrome120', proxies=proxies, timeout=10)
        m = re.search(r'matchCentreData:\s*(\{"playerIdNameDictionary.*?\})\s*,\s*matchCentreEventTypeJson', r.text, re.DOTALL)
        if r.status_code == 200 and m:
            return r.text
    except:
        pass
    return None

# Concurrency is deliberately small: each worker downloads a full multi-MB
# WhoScored page and holds it in memory (plus a native curl/TLS handle). The old
# value of 50 meant ~50 multi-MB pages in flight at once, which blew past the
# instance memory limit and got the whole web service OOM-killed/restarted on
# Render. Keep this low so peak memory stays bounded (a handful of pages at a time).
_PROXY_SWARM_WORKERS = 4
_PROXY_SWARM_LIMIT = 30


def fetch_with_free_proxies(url):
    print("[WhoScoredAdapter] Fetching free proxies from ProxyScrape...")
    try:
        r = std_requests.get('https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=5000&country=all&ssl=all&anonymity=all', timeout=10)
        proxy_list = r.text.strip().splitlines()[:_PROXY_SWARM_LIMIT]
    except:
        return None

    print(f"[WhoScoredAdapter] Testing {len(proxy_list)} proxies ({_PROXY_SWARM_WORKERS} at a time)...")
    result = None
    with concurrent.futures.ThreadPoolExecutor(max_workers=_PROXY_SWARM_WORKERS) as executor:
        futures = {executor.submit(test_proxy, p, url): p for p in proxy_list}
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res:
                print(f"[WhoScoredAdapter] Success with proxy {futures[future]}!")
                result = res
                # Cancel queued futures so we don't keep downloading pages we'll discard.
                executor.shutdown(wait=False, cancel_futures=True)
                break
    return result

def get_whoscored_stats(ws_url, force_refresh=False):
    cached = _STATS_CACHE.get(ws_url)
    if cached is not None and not force_refresh:
        df, cached_at = cached
        if (time.time() - cached_at) < _STATS_CACHE_TTL:
            return df.copy()
    print(f"[WhoScoredAdapter] Fetching data from: {ws_url}")

    m = None
    if ws_url.startswith("file://"):
        file_path = ws_url.replace("file://", "")
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                html_text = f.read()
            m = re.search(r'matchCentreData:\s*(\{"playerIdNameDictionary.*?\})\s*,\s*matchCentreEventTypeJson', html_text, re.DOTALL)
        except Exception as e:
            print(f"[WhoScoredAdapter] Error reading local file {file_path}: {e}")
    
    # Check for ScraperAPI key in Streamlit secrets to bypass Cloudflare on Streamlit Cloud
    if not m:
        scraper_api_key = os.environ.get("SCRAPER_API_KEY")
            
        if scraper_api_key:
            print("[WhoScoredAdapter] Using ScraperAPI to bypass Cloudflare...")
            proxy_url = f"http://api.scraperapi.com?api_key={scraper_api_key}&url={ws_url}"
            try:
                r = std_requests.get(proxy_url, timeout=30)
                m = re.search(r'matchCentreData:\s*(\{"playerIdNameDictionary.*?\})\s*,\s*matchCentreEventTypeJson', r.text, re.DOTALL)
            except:
                pass
        
        if not m:
            try:
                r = requests.get(ws_url, impersonate='chrome120', timeout=15)
                m = re.search(r'matchCentreData:\s*(\{"playerIdNameDictionary.*?\})\s*,\s*matchCentreEventTypeJson', r.text, re.DOTALL)
            except:
                pass
                
        if not m:
            print("[WhoScoredAdapter] curl_cffi failed. Trying tls_client fallback...")
            try:
                session = tls_client.Session(client_identifier="chrome_120", random_tls_extension_order=True)
                r = session.get(ws_url, timeout_seconds=15)
                m = re.search(r'matchCentreData:\s*(\{"playerIdNameDictionary.*?\})\s*,\s*matchCentreEventTypeJson', r.text, re.DOTALL)
            except:
                pass
                
        if not m:
            print("[WhoScoredAdapter] tls_client failed. Launching Multithreaded Free Proxy Swarm...")
            html_text = fetch_with_free_proxies(ws_url)
            if html_text:
                m = re.search(r'matchCentreData:\s*(\{"playerIdNameDictionary.*?\})\s*,\s*matchCentreEventTypeJson', html_text, re.DOTALL)
            
        if not m:
            print("[WhoScoredAdapter] Free proxies failed. Falling back to cloudscraper...")
            try:
                scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})
                r = scraper.get(ws_url, timeout=15)
                m = re.search(r'matchCentreData:\s*(\{"playerIdNameDictionary.*?\})\s*,\s*matchCentreEventTypeJson', r.text, re.DOTALL)
            except:
                pass
            
        if not m:
            raise ValueError(f"Could not extract matchCentreData from the WhoScored page. All bypass methods failed.")

        
    data = json.loads(m.group(1))
    
    pdict = data.get('playerIdNameDictionary', {})
    events = data.get('events', [])
    ft = data.get('ftScore', '0:0').split(':')
    
    # Detect extra time by checking whether any event actually occurred in an
    # extra-time period. This is far more reliable than relying on `etScore`,
    # which WhoScored often includes (as "" or "0:0") even for 90-minute matches.
    ET_PERIODS = {'FirstPeriodOfExtraTime', 'SecondPeriodOfExtraTime',
                  'ExtraFirstHalf', 'ExtraSecondHalf'}
    periods_played = {e.get('period', {}).get('displayName', '') for e in events}
    has_extra_time = bool(periods_played & ET_PERIODS)

    # Fallback: only trust maxMinute if it clearly exceeds a full 90 + stoppage
    # (regular time can reach ~100' with stoppage, so require a high threshold).
    max_minute = data.get('maxMinute', 90)
    if max_minute > 105 and not has_extra_time:
        has_extra_time = True

    match_duration = 120 if has_extra_time else 90

    print(f"[WhoScoredAdapter] Extra time: {has_extra_time}, match duration: {match_duration} min (periods: {sorted(periods_played)})")
    
    exp_mins = data.get('expandedMinutes', {})
    expanded_to_real = {}
    for period, mapping in exp_mins.items():
        for real_min, exp_min in mapping.items():
            expanded_to_real[exp_min] = int(real_min)
            
    home_id, away_id = data['home']['teamId'], data['away']['teamId']
    
    player_ev = {}
    goal_events = []
    pending_pk_winners = {}  # team_id -> [player_name, ...] FIFO of players who won a penalty

    # Clearance off the line: WhoScored does NOT emit a dedicated event type for this.
    # Verified against real match data (e.g. Katic, CAN v BIH, 2026 WC): the blocked
    # shot — the SHOOTER's `SavedShot` event — carries a `SavedOffline` qualifier, and
    # the defender who cleared it off the line is that shot's *opposite-related* event
    # (a `Save` carrying `OutfielderBlock`). Pre-scan the shots to collect the defender
    # events' (period, eventId) keys so we can credit them in the main loop. Keyed by
    # (period, eventId) because `eventId` is only unique within a period, not globally.
    offline_clearance_keys = set()
    for e in events:
        if not any(q.get('type', {}).get('displayName', '') == 'SavedOffline'
                   for q in e.get('qualifiers', [])):
            continue
        period = e.get('period', {}).get('displayName', '')
        for q in e.get('qualifiers', []):
            if q.get('type', {}).get('displayName', '') == 'OppositeRelatedEvent' and q.get('value') is not None:
                try:
                    offline_clearance_keys.add((period, int(q['value'])))
                except (TypeError, ValueError):
                    pass

    for e in events:
        # Skip penalty shootout events — they should NOT count towards player stats
        event_period = e.get('period', {}).get('displayName', '')
        if event_period == 'PenaltyShootout':
            continue
        
        pid = str(int(e.get('playerId', 0))) if e.get('playerId') else None
        if not pid: continue
        name = pdict.get(pid, '?')
        if name not in player_ev:
            player_ev[name] = {'goals':0,'assists':0,'og':0,'yellow':0,'red':0,'crosses':0,
                              'pk_scored':0,'pk_att':0,'pk_won':0,'pk_con':0,'pk_assist':0,
                              'woodwork':0,'clearance_off_line':0,'last_man_tackle':0,
                              'keeper_sweeper':0,'punches':0,'saves_in_box':0}
        
        t = e.get('type',{}).get('displayName','')
        quals = [q.get('type',{}).get('displayName','') for q in e.get('qualifiers',[])]
        outcome = e.get('outcomeType',{}).get('displayName','')
        
        if e.get('isGoal'):
            goal_events.append({'minute': e.get('minute', 0), 'teamId': e.get('teamId'), 'isOG': 'OwnGoal' in quals})
            if 'OwnGoal' in quals:
                player_ev[name]['og'] += 1
            else:
                player_ev[name]['goals'] += 1
                if 'Penalty' in quals:
                    player_ev[name]['pk_scored'] += 1
                    player_ev[name]['pk_att'] += 1
                    # If a different player won this penalty, give them an assist.
                    # Only fires when the penalty is actually scored (this block).
                    team_id = e.get('teamId')
                    pending = pending_pk_winners.get(team_id, [])
                    if pending:
                        pk_winner = pending.pop(0)
                        if pk_winner != name:
                            if pk_winner not in player_ev:
                                player_ev[pk_winner] = {'goals':0,'assists':0,'og':0,'yellow':0,'red':0,'crosses':0,
                                                        'pk_scored':0,'pk_att':0,'pk_won':0,'pk_con':0,'pk_assist':0,
                                                        'woodwork':0,'clearance_off_line':0,'last_man_tackle':0,
                                                        'keeper_sweeper':0,'punches':0,'saves_in_box':0}
                            player_ev[pk_winner]['pk_assist'] += 1
                            player_ev[pk_winner]['assists'] += 1
                # Credit the assist from the GOAL event's relatedPlayerId whenever the
                # goal is flagged 'Assisted'. The old check looked for
                # 'IntentionalGoalAssist' on the assisting PASS, but Opta omits that
                # qualifier when the scorer adds individual play (dribble) before
                # finishing — so those assists were silently dropped (e.g. Elliot
                # Anderson -> Bellingham, tagged ShotAssist/BigChance, not Intentional).
                # The goal's relatedPlayerId points at the assister in every case.
                if 'Assisted' in quals and e.get('relatedPlayerId'):
                    aname = pdict.get(str(int(e['relatedPlayerId'])))
                    if aname:
                        if aname not in player_ev:
                            player_ev[aname] = {'goals':0,'assists':0,'og':0,'yellow':0,'red':0,'crosses':0,
                                                'pk_scored':0,'pk_att':0,'pk_won':0,'pk_con':0,'pk_assist':0,
                                                'woodwork':0,'clearance_off_line':0,'last_man_tackle':0,
                                                'keeper_sweeper':0,'punches':0,'saves_in_box':0}
                        player_ev[aname]['assists'] += 1
        
        if t == 'Card':
            if 'Yellow' in quals: player_ev[name]['yellow'] += 1
            elif 'Red' in quals: player_ev[name]['red'] += 1
            
        if 'Cross' in quals: player_ev[name]['crosses'] += 1
        
        if t == 'Foul' and 'Penalty' in quals:
            if outcome == 'Successful':
                player_ev[name]['pk_won'] += 1
                # Queue this player as the penalty winner so we can credit an assist
                # if a teammate subsequently scores the spot-kick.
                pending_pk_winners.setdefault(e.get('teamId'), []).append(name)
            elif outcome == 'Unsuccessful':
                player_ev[name]['pk_con'] += 1

        if t == 'ShotOnPost': player_ev[name]['woodwork'] += 1
        # Clearance off the line — credit the defender whose event is the opposite-related
        # event of a shot tagged `SavedOffline` (see pre-scan above). There is no
        # `ClearanceOffLine` event type in WhoScored's feed. The `OutfielderBlock`
        # guard is required because `eventId` is not unique even within a period, so the
        # (period, eventId) key alone can match an unrelated event; the off-the-line
        # clearer always carries `OutfielderBlock`, which pins it to the right event.
        if (event_period, e.get('eventId')) in offline_clearance_keys and 'OutfielderBlock' in quals:
            player_ev[name]['clearance_off_line'] += 1
        # Last man tackle — verified qualifier name is `LastMan` (not `LastManTackle`),
        # e.g. Bardakci (TUR v PAR, 2026 WC) min 54: Tackle / Unsuccessful / ['LastMan'].
        if t == 'Tackle' and 'LastMan' in quals: player_ev[name]['last_man_tackle'] += 1
        if t == 'KeeperSweeper': player_ev[name]['keeper_sweeper'] += 1
        if t == 'Punch': player_ev[name]['punches'] += 1
        if t == 'Save' and 'KeeperSaveInTheBox' in quals: player_ev[name]['saves_in_box'] += 1

    results = []
    
    for team_key, team_id in [('home', home_id), ('away', away_id)]:
        team_name = data[team_key]['name']
        
        for p in data[team_key]['players']:
            name = p['name']
            pos = POS_MAP.get(p.get('position','Sub'), 'MID')
            is_starter = p.get('isFirstEleven', False)
            
            sub_in_exp = p.get('subbedInExpandedMinute')
            sub_out_exp = p.get('subbedOutExpandedMinute')
            
            if is_starter:
                start = 0
                end = expanded_to_real.get(sub_out_exp, sub_out_exp) if sub_out_exp else 200 # 200 represents final whistle
            elif sub_in_exp:
                start = expanded_to_real.get(sub_in_exp, sub_in_exp)
                end = expanded_to_real.get(sub_out_exp, sub_out_exp) if sub_out_exp else 200
            else: 
                continue
                
            # Use actual match duration (90 or 120) instead of hard-coded 90
            minutes = max(0, min(end, match_duration) - min(start, match_duration))
            
            gs, gc = 0, 0
            for g in goal_events:
                if g['minute'] >= start and g['minute'] < end:
                    if g['isOG']:
                        if g['teamId'] == team_id: gc += 1
                        else: gs += 1
                    else:
                        if g['teamId'] == team_id: gs += 1
                        else: gc += 1
            
            stats = p.get('stats', {})
            ev = player_ev.get(name, {})
            
            row = {
                'Unnamed: 0_level_0_Player': name,
                'Team': 'Home' if team_key == 'home' else 'Away',
                'Pos': pos,
                'Unnamed: 5_level_0_Min': minutes,
                'minutes_played': minutes,
                'goals_scored': gs,
                'goals_conceded': gc,
                
                'Aerial Duels_Won': sum_stat(stats.get('aerialsWon',{})),
                'Aerial Duels_Lost': sum_stat(stats.get('aerialsTotal',{})) - sum_stat(stats.get('aerialsWon',{})),
                'Performance_Tkl': sum_stat(stats.get('tackleSuccessful',{})), 
                'Challenges_Lost': sum_stat(stats.get('dribbledPast',{})),
                'Performance_Int': sum_stat(stats.get('interceptions',{})),
                'Unnamed: 20_level_0_Clr': sum_stat(stats.get('clearances',{})),
                'Carries_Dis': sum_stat(stats.get('dispossessed',{})),
                'Performance_Fls': sum_stat(stats.get('foulsCommited',{})),
                'Performance_Off': sum_stat(stats.get('offsidesCaught',{})),
                'Passes_Cmp': sum_stat(stats.get('passesAccurate',{})),
                'Passes_Att': sum_stat(stats.get('passesTotal',{})),
                'Unnamed: 23_level_0_KP': sum_stat(stats.get('passesKey',{})),
                'Take-Ons_Succ': sum_stat(stats.get('dribblesWon',{})),
                'Take-Ons_Att': sum_stat(stats.get('dribblesAttempted',{})),
                'Blocks_Sh': sum_stat(stats.get('shotsBlocked',{})),
                'Performance_Sh': sum_stat(stats.get('shotsTotal',{})),
                'Performance_SoT': sum_stat(stats.get('shotsOnTarget',{})),
                'Performance_Crs': ev.get('crosses', 0),
                'Performance_Gls': ev.get('goals', 0), 
                'Performance_Ast': ev.get('assists', 0),
                'Performance_CrdY': ev.get('yellow', 0), 
                'Performance_CrdR': ev.get('red', 0),
                'Performance_OG': ev.get('og', 0), 
                'Unnamed: 21_level_0_Err': sum_stat(stats.get('errors',{})),
                'Performance_PKwon': ev.get('pk_won',0), 
                'Performance_PKcon': ev.get('pk_con',0),
                'Performance_PK': ev.get('pk_scored',0), 
                'Performance_PKatt': ev.get('pk_att',0),
                'Hit_Woodwork': ev.get('woodwork',0),
                'Off_the_Line': ev.get('clearance_off_line', 0),
                'Last_Man_Tackle': ev.get('last_man_tackle', 0),
                'Performance_PKassist': ev.get('pk_assist', 0),
                'Performance_Saves': sum_stat(stats.get('totalSaves',{})),
                'Performance_HighClaims': sum_stat(stats.get('claimsHigh',{})),
                'Performance_RunsOut': ev.get('keeper_sweeper',0),
                'Performance_Punches': ev.get('punches',0),
                'Performance_SavedInsideBox': ev.get('saves_in_box',0),
                'Performance_PossLost': 0, 'Performance_PKSaved': 0, 'Performance_PKFaced': 0,
                'Performance_GoalsPrevented': 0, 'Performance_KeeperSaveValue': 0, 'Performance_Rec': 0,
            }
            results.append(row)
            
    df = pd.DataFrame(results)
    _stats_cache_put(ws_url, df)
    return df.copy()
