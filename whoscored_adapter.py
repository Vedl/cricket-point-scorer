import re
import json
import pandas as pd
from curl_cffi import requests
import cloudscraper
from bs4 import BeautifulSoup
import time

POS_MAP = {'GK':'GK','DR':'DEF','DC':'DEF','DL':'DEF','DMR':'DEF','DML':'DEF',
           'MC':'MID','DMC':'MID','AMC':'MID','MR':'MID','ML':'MID',
           'AMR':'MID','AML':'MID','FW':'FWD','FWR':'FWD','FWL':'FWD','Sub':'MID'}

def sum_stat(sd):
    if not sd or not isinstance(sd, dict): return 0
    return sum(float(v) for v in sd.values())

def get_whoscored_stats(ws_url):
    print(f"[WhoScoredAdapter] Fetching data from: {ws_url}")
    
    r = requests.get(ws_url, impersonate='chrome120', timeout=15)
    
    m = re.search(r'matchCentreData:\s*(\{"playerIdNameDictionary.*?\})\s*,\s*matchCentreEventTypeJson', r.text, re.DOTALL)
    if not m:
        print(f"[WhoScoredAdapter] curl_cffi failed (Status: {r.status_code}). Falling back to cloudscraper...")
        scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})
        r = scraper.get(ws_url, timeout=15)
        m = re.search(r'matchCentreData:\s*(\{"playerIdNameDictionary.*?\})\s*,\s*matchCentreEventTypeJson', r.text, re.DOTALL)
        if not m:
            raise ValueError(f"Could not extract matchCentreData from the WhoScored page. Status: {r.status_code}. Response snippet: {r.text[:200]}")
        
    data = json.loads(m.group(1))
    
    pdict = data.get('playerIdNameDictionary', {})
    events = data.get('events', [])
    ft = data.get('ftScore', '0:0').split(':')
    
    exp_mins = data.get('expandedMinutes', {})
    expanded_to_real = {}
    for period, mapping in exp_mins.items():
        for real_min, exp_min in mapping.items():
            expanded_to_real[exp_min] = int(real_min)
            
    home_id, away_id = data['home']['teamId'], data['away']['teamId']
    
    player_ev = {}
    goal_events = []
    
    for e in events:
        pid = str(int(e.get('playerId', 0))) if e.get('playerId') else None
        if not pid: continue
        name = pdict.get(pid, '?')
        if name not in player_ev:
            player_ev[name] = {'goals':0,'assists':0,'og':0,'yellow':0,'red':0,'crosses':0,
                              'pk_scored':0,'pk_att':0,'pk_won':0,'pk_con':0,'woodwork':0,
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
                    
        if 'IntentionalGoalAssist' in quals: player_ev[name]['assists'] += 1
        
        if t == 'Card':
            if 'Yellow' in quals: player_ev[name]['yellow'] += 1
            elif 'Red' in quals: player_ev[name]['red'] += 1
            
        if 'Cross' in quals: player_ev[name]['crosses'] += 1
        
        if t == 'Foul' and 'Penalty' in quals:
            if outcome == 'Successful': player_ev[name]['pk_won'] += 1
            elif outcome == 'Unsuccessful': player_ev[name]['pk_con'] += 1
            
        if t == 'ShotOnPost': player_ev[name]['woodwork'] += 1
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
                end = min(expanded_to_real.get(sub_out_exp, sub_out_exp), 90) if sub_out_exp else 90
            elif sub_in_exp:
                start = min(expanded_to_real.get(sub_in_exp, sub_in_exp), 90)
                end = min(expanded_to_real.get(sub_out_exp, sub_out_exp), 90) if sub_out_exp else 90
            else: 
                continue
                
            minutes = max(0, end - start)
            if minutes <= 0: continue
            
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
    return df
