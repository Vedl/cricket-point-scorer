"""
FBref Adapter — Scrapes match report data from FBref.com

This adapter replaces the SofaScore adapter for the FIFA World Cup 2026 auction mode.
It scrapes player statistics from FBref match report pages and maps them to the
exact column format expected by football_score_calculator.py.

FBref match report URLs look like:
  https://fbref.com/en/matches/abc123/Team-A-vs-Team-B-June-11-2026-FIFA-World-Cup

The match report page contains multiple HTML tables with player stats:
  - Summary table (goals, assists, shots, passes, etc.)
  - Passing table (detailed pass stats)
  - Defense table (tackles, interceptions, clearances, etc.)
  - Possession table (carries, dribbles, etc.)
  - Goalkeeper table (saves, claims, etc.)
  - Misc table (aerials, fouls, cards, etc.)

Position Mapping (matches WhoScored/UCL convention):
  - GK -> GK
  - DF, CB, LB, RB, WB, LWB, RWB -> DEF
  - MF, CM, DM, AM, CDM, CAM -> MID
  - FW, CF, LW, RW, ST, SS -> FWD
"""

import requests
from bs4 import BeautifulSoup, Comment
import pandas as pd
import re
import time as _time

# ============================================================
# POSITION MAPPING
# ============================================================

FBREF_POSITION_MAP = {
    # Goalkeeper
    'GK': 'GK',
    
    # Defenders
    'DF': 'DEF',
    'CB': 'DEF',
    'LB': 'DEF',
    'RB': 'DEF',
    'WB': 'DEF',
    'LWB': 'DEF',
    'RWB': 'DEF',
    'FB': 'DEF',
    
    # Midfielders
    'MF': 'MID',
    'CM': 'MID',
    'DM': 'MID',
    'AM': 'MID',
    'CDM': 'MID',
    'CAM': 'MID',
    'LM': 'MID',
    'RM': 'MID',
    
    # Forwards
    'FW': 'FWD',
    'CF': 'FWD',
    'LW': 'FWD',
    'RW': 'FWD',
    'ST': 'FWD',
    'SS': 'FWD',
}

def map_fbref_position(pos_str):
    """Map FBref position string to internal format (GK/DEF/MID/FWD).
    
    FBref positions can be compound like 'DF,MF' or 'FW,MF'.
    We take the FIRST position listed as the primary position.
    """
    if not pos_str or pd.isna(pos_str):
        return 'MID'  # Default
    
    pos_str = str(pos_str).strip().upper()
    
    # Handle compound positions (e.g., "DF,MF" or "FW,MF")
    parts = [p.strip() for p in pos_str.replace(',', ' ').split()]
    
    for part in parts:
        if part in FBREF_POSITION_MAP:
            return FBREF_POSITION_MAP[part]
    
    return 'MID'  # Default fallback


# ============================================================
# HTTP REQUEST HELPER
# ============================================================

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://fbref.com/",
}

def _fetch_page(url, retries=3, delay=4):
    """Fetch an FBref page with rate-limit-aware retry logic.
    
    FBref rate limits aggressively — they return 429 if you hit them too fast.
    We retry with exponential backoff.
    """
    last_error = None
    for attempt in range(retries):
        try:
            if attempt > 0:
                wait = delay * (2 ** (attempt - 1))
                print(f"[FBref] Rate limit cooldown: waiting {wait}s before retry {attempt + 1}...")
                _time.sleep(wait)
            
            response = requests.get(url, headers=_HEADERS, timeout=30)
            
            if response.status_code == 200:
                return response.text
            elif response.status_code == 429:
                last_error = f"HTTP 429 Too Many Requests (attempt {attempt + 1})"
                print(f"[FBref] {last_error}")
                continue
            else:
                last_error = f"HTTP {response.status_code}"
                print(f"[FBref] {last_error}")
                
        except Exception as e:
            last_error = str(e)
            print(f"[FBref] Request failed: {last_error}")
    
    raise ValueError(f"[FBref] All {retries} attempts failed. Last error: {last_error}")


# ============================================================
# HTML TABLE PARSER 
# ============================================================

def _parse_commented_tables(html):
    """Parse ALL tables from FBref HTML, including those inside HTML comments.
    
    FBref wraps many stat tables in <!-- ... --> comments to reduce initial page load.
    We need to extract these commented tables and parse them.
    """
    soup = BeautifulSoup(html, 'html.parser')
    tables = {}
    
    # 1. Parse visible tables
    for table in soup.find_all('table'):
        table_id = table.get('id', '')
        if table_id:
            try:
                df = pd.read_html(str(table), header=[0, 1])[0]
                tables[table_id] = df
            except Exception:
                try:
                    df = pd.read_html(str(table), header=0)[0]
                    tables[table_id] = df
                except Exception:
                    pass
    
    # 2. Parse tables hidden in HTML comments
    comments = soup.find_all(string=lambda text: isinstance(text, Comment))
    for comment in comments:
        comment_soup = BeautifulSoup(str(comment), 'html.parser')
        for table in comment_soup.find_all('table'):
            table_id = table.get('id', '')
            if table_id and table_id not in tables:
                try:
                    df = pd.read_html(str(table), header=[0, 1])[0]
                    tables[table_id] = df
                except Exception:
                    try:
                        df = pd.read_html(str(table), header=0)[0]
                        tables[table_id] = df
                    except Exception:
                        pass
    
    return tables


def _flatten_columns(df):
    """Flatten multi-level column headers into single-level 'Level0_Level1' format.
    
    FBref uses multi-level headers like ('Performance', 'Gls'), ('Passes', 'Cmp'), etc.
    We flatten these to match the column format expected by the scoring engine.
    """
    if isinstance(df.columns, pd.MultiIndex):
        new_cols = []
        for col in df.columns:
            # Join levels, skip 'Unnamed' prefixes where they're just artifacts
            parts = [str(c).strip() for c in col if str(c).strip() and 'Unnamed' not in str(c)]
            if len(parts) == 0:
                # All parts were Unnamed — use the raw column name
                new_cols.append('_'.join([str(c) for c in col]))
            elif len(parts) == 1:
                new_cols.append(parts[0])
            else:
                new_cols.append('_'.join(parts))
        df.columns = new_cols
    return df


# ============================================================
# MATCH EVENTS EXTRACTOR
# ============================================================

def _extract_match_events(soup):
    """Extract goal and substitution events from the FBref match report page.
    
    FBref stores events in the match report as div elements with class 'event'.
    We parse goals and substitutions to build the timeline for +/- calculations.
    """
    events = []
    
    # Find the events timeline / scorebox
    scorebox = soup.find('div', class_='scorebox')
    if not scorebox:
        print("[FBref] Warning: Could not find scorebox for events extraction")
        return events
    
    # Parse goal events from the summary section
    # FBref uses <div class="event"> with data inside
    for event_div in soup.find_all('div', class_='event'):
        event_text = event_div.get_text(separator='|', strip=True)
        
        # Goals
        if '⚽' in event_text or 'Goal' in event_text:
            # Try to extract player name and minute
            minute_match = re.search(r"(\d+)[''′+]?", event_text)
            if minute_match:
                events.append({
                    'time': minute_match.group(1),
                    'event_kind': 'Goal',
                    'player': event_text.split('|')[0].strip() if '|' in event_text else 'Unknown',
                    'player_on': None,
                    'player_off': None
                })
    
    # Parse substitutions from the lineup tables
    # FBref marks substitutes in the stats tables; we also look for sub events
    for sub_div in soup.find_all('div', class_='event'):
        event_text = sub_div.get_text(separator='|', strip=True)
        if '🔁' in event_text or 'Substitution' in event_text:
            minute_match = re.search(r"(\d+)[''′+]?", event_text)
            if minute_match:
                parts = event_text.split('|')
                events.append({
                    'time': minute_match.group(1),
                    'event_kind': 'Substitution',
                    'player': None,
                    'player_on': parts[1].strip() if len(parts) > 1 else 'Unknown',
                    'player_off': parts[0].strip() if len(parts) > 0 else 'Unknown'
                })
    
    return events


def _extract_events_from_summary(html):
    """Enhanced event extraction by parsing the match summary section of FBref.
    
    FBref stores events in specific HTML patterns within the match report.
    This function parses goals and substitutions more reliably.
    """
    events = []
    soup = BeautifulSoup(html, 'html.parser')
    
    # Look for the events wrapper (typically inside #events_wrap or the scorebox)
    events_wrap = soup.find('div', id='events_wrap')
    if not events_wrap:
        # Fallback: try parsing from the page directly
        events_wrap = soup
    
    # Parse each event row
    for event_row in events_wrap.find_all('div', class_=re.compile(r'event')):
        text = event_row.get_text(separator=' ', strip=True)
        
        # Extract minute
        minute_match = re.search(r"(\d+)['′+]", text)
        minute = minute_match.group(1) if minute_match else None
        
        if not minute:
            continue
        
        # Detect event type
        if any(icon in str(event_row) for icon in ['goal', 'soccer-ball', 'own_goal']):
            # Find scorer name
            player_link = event_row.find('a')
            player_name = player_link.get_text(strip=True) if player_link else 'Unknown'
            events.append({
                'time': minute,
                'event_kind': 'Goal',
                'player': player_name,
                'player_on': None,
                'player_off': None
            })
        
        elif any(icon in str(event_row) for icon in ['substitute', 'sub_in', 'sub_out']):
            links = event_row.find_all('a')
            player_on = links[0].get_text(strip=True) if len(links) > 0 else 'Unknown'
            player_off = links[1].get_text(strip=True) if len(links) > 1 else 'Unknown'
            events.append({
                'time': minute,
                'event_kind': 'Substitution',
                'player': None,
                'player_on': player_on,
                'player_off': player_off
            })
    
    return events


# ============================================================
# STAT COLUMN MAPPING — FBref -> Internal Format
# ============================================================

def _map_outfield_stats(row, pos):
    """Map a single outfield player's FBref stats row to the internal column format
    expected by the scoring engine (def_score_calc, mid_score_calc, fwd_score_calc).
    """
    def get(col, default=0):
        """Safely get a column value, handling missing columns and NaN."""
        if col in row.index:
            val = row[col]
            if pd.isna(val):
                return default
            try:
                return float(val)
            except (ValueError, TypeError):
                return default
        return default
    
    mapped = {}
    
    # Player name
    mapped['Unnamed: 0_level_0_Player'] = row.get('Player', row.get('player', 'Unknown'))
    
    # Minutes
    mapped['Unnamed: 5_level_0_Min'] = get('Min', 0)
    
    # Position
    mapped['Pos'] = pos
    
    # Attacking
    mapped['Performance_Gls'] = get('Gls', 0)
    mapped['Performance_Ast'] = get('Ast', 0)
    mapped['Performance_Sh'] = get('Sh', 0)
    mapped['Performance_SoT'] = get('SoT', 0)
    
    # Passing
    mapped['Passes_Cmp'] = get('Cmp', 0)
    mapped['Passes_Att'] = get('Att', get('Pass_Att', 0))
    mapped['Unnamed: 23_level_0_KP'] = get('KP', 0)
    mapped['Performance_Crs'] = get('CrsPA', get('Crs', 0))
    
    # Dribbling / Possession
    mapped['Take-Ons_Succ'] = get('Succ', 0)
    mapped['Take-Ons_Att'] = get('Take-Ons_Att', get('Att_TO', get('Att.1', 0)))
    mapped['Carries_Dis'] = get('Dis', 0)
    mapped['Performance_Fls'] = get('Fls', 0)
    mapped['Performance_Off'] = get('Off', 0)
    
    # Defensive
    mapped['Performance_Tkl'] = get('Tkl', 0)
    mapped['Performance_Int'] = get('Int', 0)
    mapped['Unnamed: 20_level_0_Clr'] = get('Clr', 0)
    mapped['Blocks_Sh'] = get('ShBlocks', get('Blocks_Sh', get('BlkSh', 0)))
    mapped['Challenges_Lost'] = get('Tkl_Lost', get('Lost', 0))  # Challenges lost / dribbled past
    mapped['Unnamed: 21_level_0_Err'] = get('Err', 0)
    mapped['Performance_OG'] = get('OG', 0)
    mapped['Performance_Rec'] = get('Rec', 0)
    
    # Aerial
    mapped['Aerial Duels_Won'] = get('Won', get('Aerial_Won', 0))
    mapped['Aerial Duels_Lost'] = get('Lost_Aerial', get('Aerial_Lost', 0))
    
    # Penalties
    mapped['Performance_PKwon'] = get('PKwon', 0)
    mapped['Performance_PKcon'] = get('PKcon', 0)
    mapped['Performance_PK'] = get('PK', 0)  # Penalties scored
    mapped['Performance_PKatt'] = get('PKatt', 0)  # Penalties attempted
    
    # Discipline
    mapped['Performance_CrdY'] = get('CrdY', 0)
    mapped['Performance_CrdR'] = get('CrdR', 0)
    
    # Misc
    mapped['Hit_Woodwork'] = get('Hit_Woodwork', 0)
    
    # Metadata
    mapped['is_sub'] = False  # Will be set later based on minutes
    
    return mapped


def _map_gk_stats(row, pos='GK'):
    """Map a goalkeeper's FBref stats row to the internal column format.
    
    GK stats come from FBref's dedicated keeper stats table.
    """
    def get(col, default=0):
        if col in row.index:
            val = row[col]
            if pd.isna(val):
                return default
            try:
                return float(val)
            except (ValueError, TypeError):
                return default
        return default
    
    # Start with outfield stats (for shared columns)
    mapped = _map_outfield_stats(row, pos)
    
    # Override / add GK-specific columns
    mapped['Performance_Saves'] = get('Saves', get('SoTA', 0))
    mapped['Performance_Punches'] = get('PKsFaced', 0)  # FBref doesn't have punches directly
    mapped['Performance_HighClaims'] = get('HighClaims', 0)
    mapped['Performance_RunsOut'] = get('Sweeper', get('#OPA', 0))
    mapped['Performance_PKSaved'] = get('PKsv', get('PKSaved', 0))
    mapped['Performance_GK_GoalsConceded'] = get('GA', 0)
    
    # Advanced GK stats (may not be available on FBref — default to 0)
    mapped['Performance_SavedInsideBox'] = get('SavedInsideBox', 0)
    mapped['Performance_PossLost'] = get('PossLost', 0)
    mapped['Performance_PKFaced'] = get('PKsFaced', get('PKatt_gk', 0))
    mapped['Performance_GoalsPrevented'] = get('PSxG+/-', 0)  # FBref's Post-Shot xG +/- is Goals Prevented
    mapped['Performance_KeeperSaveValue'] = get('KeeperSaveValue', 0)
    
    return mapped


# ============================================================
# MAIN SCRAPER — Parse FBref Match Report
# ============================================================

def _parse_match_report(html, url):
    """Parse an FBref match report page and extract player statistics.
    
    Returns:
        (merged_df, match_events): Tuple of DataFrame with all player stats
                                    and list of match events (goals, subs)
    """
    soup = BeautifulSoup(html, 'html.parser')
    tables = _parse_commented_tables(html)
    
    print(f"[FBref] Found {len(tables)} tables: {list(tables.keys())}")
    
    # Identify home and away summary tables
    # FBref uses IDs like 'stats_{team_id}_summary' for each team
    summary_tables = {k: v for k, v in tables.items() if 'summary' in k.lower()}
    passing_tables = {k: v for k, v in tables.items() if 'passing' in k.lower() and 'types' not in k.lower()}
    defense_tables = {k: v for k, v in tables.items() if 'defense' in k.lower()}
    possession_tables = {k: v for k, v in tables.items() if 'possession' in k.lower()}
    misc_tables = {k: v for k, v in tables.items() if 'misc' in k.lower()}
    keeper_tables = {k: v for k, v in tables.items() if 'keeper' in k.lower()}
    
    # Get the two summary tables (home and away)
    summary_keys = sorted(summary_tables.keys())
    
    if len(summary_keys) < 2:
        # Fallback: try finding tables by pattern
        print(f"[FBref] Warning: Expected 2 summary tables, found {len(summary_keys)}. Trying fallback...")
        # Try broader search
        summary_keys = [k for k in tables.keys() if re.search(r'stats_\w+_summary', k)]
        if len(summary_keys) < 2:
            raise ValueError(f"[FBref] Could not find two team summary tables. Available: {list(tables.keys())}")
    
    home_key = summary_keys[0]
    away_key = summary_keys[1]
    
    print(f"[FBref] Home summary table: {home_key}")
    print(f"[FBref] Away summary table: {away_key}")
    
    all_players = []
    
    for team_idx, (team_key, team_label) in enumerate([(home_key, 'Home'), (away_key, 'Away')]):
        df_summary = _flatten_columns(tables[team_key].copy())
        
        # Remove the totals row (usually the last row)
        df_summary = df_summary[df_summary['Player'].notna() & (df_summary['Player'] != '')]
        df_summary = df_summary[~df_summary['Player'].str.contains('Total', na=False, case=False)]
        
        # Try to find corresponding detail tables for this team
        team_id_match = re.search(r'stats_(\w+)_summary', team_key)
        team_id = team_id_match.group(1) if team_id_match else None
        
        # Merge in additional stats from other tables if available
        detail_tables = {}
        if team_id:
            for table_type in ['passing', 'defense', 'possession', 'misc', 'keeper']:
                detail_key = f'stats_{team_id}_{table_type}'
                if detail_key in tables:
                    detail_tables[table_type] = _flatten_columns(tables[detail_key].copy())
        
        # Process each player row
        for _, row in df_summary.iterrows():
            player_name = str(row.get('Player', '')).strip()
            if not player_name or player_name.lower() == 'total':
                continue
            
            # Get position
            pos_raw = str(row.get('Pos', 'MF')).strip()
            pos = map_fbref_position(pos_raw)
            
            # Merge detail stats into this row
            merged_row = row.copy()
            for table_type, detail_df in detail_tables.items():
                detail_df_clean = detail_df[detail_df['Player'].notna()]
                player_detail = detail_df_clean[detail_df_clean['Player'].str.strip() == player_name]
                if not player_detail.empty:
                    for col in player_detail.columns:
                        if col not in merged_row.index or pd.isna(merged_row.get(col)):
                            merged_row[col] = player_detail.iloc[0][col]
            
            # Map to internal format
            if pos == 'GK':
                mapped = _map_gk_stats(merged_row, pos)
            else:
                mapped = _map_outfield_stats(merged_row, pos)
            
            # Detect substitutes (players with Min < 90 who aren't in the starting XI)
            minutes = mapped.get('Unnamed: 5_level_0_Min', 0)
            # FBref marks subs with a note — we'll detect based on their position in the table
            # Players after the 11th row are typically subs
            # But more reliably: check if their 'Min' cell has any sub indicator
            
            mapped['Team'] = team_label
            all_players.append(mapped)
    
    # Mark substitutes based on ordering (first 11 are starters per team)
    home_players = [p for p in all_players if p['Team'] == 'Home']
    away_players = [p for p in all_players if p['Team'] == 'Away']
    
    for players in [home_players, away_players]:
        for i, p in enumerate(players):
            if i >= 11:
                p['is_sub'] = True
    
    merged_df = pd.DataFrame(all_players)
    
    # Extract match events
    events = _extract_events_from_summary(html)
    if not events:
        events = _extract_match_events(soup)
    
    print(f"[FBref] Parsed {len(all_players)} players, {len(events)} events")
    
    return merged_df, events


# ============================================================
# PUBLIC API
# ============================================================

def get_player_stats_df(fbref_url):
    """Fetch and parse player statistics from an FBref match report URL.
    
    Args:
        fbref_url: Full URL to an FBref match report page
                   e.g., https://fbref.com/en/matches/abc123/...
    
    Returns:
        Tuple of (DataFrame, list[dict]):
            - DataFrame with all player stats in internal column format
            - List of match event dicts for goals/substitutions
    """
    print(f"[FBref] Fetching match report: {fbref_url}")
    
    html = _fetch_page(fbref_url)
    
    merged_df, events = _parse_match_report(html, fbref_url)
    
    return merged_df, events
