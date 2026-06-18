"""
Football Score Calculator — FIFA World Cup 2026 Auction Mode

This is a DIRECT COPY of the scoring algorithm from ucl-point-scorer/player_score_calculator.py.
DO NOT modify the scoring coefficients or formulas. Any changes should be done via the
adapter layer (fbref_adapter.py) that feeds data into these functions.

Positional scoring functions:
  - def_score_calc: Defenders
  - mid_score_calc: Midfielders  
  - fwd_score_calc: Forwards
  - gk_score_calc:  Goalkeepers (ML model + v11 fallback)

Entry point:
  - calc_all_players_fbref(fbref_url): Fetches data from FBref and calculates scores
"""

import pandas as pd
import os

# ============================================================
# POSITIONAL SCORING FUNCTIONS (UNMODIFIED FROM UCL SCORER)
# ============================================================

def parse_minute(time_str):
    if '+' in time_str:
        base, extra = time_str.split('+')
        return int(base) + int(extra)
    return int(time_str)

def def_score_calc(df, team_score, team_conc):
    score = ( 1.9*df['Aerial Duels_Won'] - 1.5*df['Aerial Duels_Lost'] + 2.7*df['Performance_Tkl']
            - 1.6*df['Challenges_Lost'] + 2.7*df['Performance_Int'] + 1.1*df['Unnamed: 20_level_0_Clr']
            + (10-(5*team_conc)) + (3-(1.2*df['Carries_Dis'])-(0.6*(df['Performance_Fls']+df['Performance_Off']))
                               -(3.5*df['Performance_OG'])-(5*df['Unnamed: 21_level_0_Err'])) +
            df['Passes_Cmp']/9 - ((df['Passes_Att']-df['Passes_Cmp'])/4.5) + df['Unnamed: 23_level_0_KP']
            + df['Take-Ons_Succ']*2.5 - ((df['Take-Ons_Att']-df['Take-Ons_Succ'])*0.8) +
            1.1*df['Blocks_Sh'] + 1.5*df['Unnamed: 23_level_0_KP'] + 1.2*df['Performance_Crs'] +
            2.5*df['Performance_SoT'] + ((df['Performance_Sh']-df['Performance_SoT'])/2) +
            df['Unnamed: 5_level_0_Min']/30 + 10*df['Performance_Gls'] + 8*df['Performance_Ast'] +
            (-5*df['Performance_CrdR']) + (-5*df['Performance_PKcon']) + (-5*(df['Performance_PKatt']-df['Performance_PK'])) + (3*df.get('Hit_Woodwork', 0)))
    
    pk_won = df['Performance_PKwon'].values[0]
    pk_scored = df['Performance_PK'].values[0]
    
    if (pk_won == 1) and (pk_scored != 1):
        score += 6.4
    
    minutes_played = df['Unnamed: 5_level_0_Min'].values[0]

    if (minutes_played <= 45) and (team_conc == 0):
            score -= 5
    
    val = score.values[0] if isinstance(score, pd.Series) else score
    return round(val, 0)

def mid_score_calc(df, team_score, team_conc):
    score = ( 1.7*df['Aerial Duels_Won'] - 1.5*df['Aerial Duels_Lost'] + 2.6*df['Performance_Tkl']
            - 1.2*df['Challenges_Lost'] + 2.5*df['Performance_Int'] + 1.1*df['Unnamed: 20_level_0_Clr']
            + (4-(2*team_conc)+(2*team_score)) + (3-(1.1*df['Carries_Dis'])-(0.6*(df['Performance_Fls']+df['Performance_Off']))
                               -(3.3*df['Performance_OG'])-(5*df['Unnamed: 21_level_0_Err'])) +
            df['Passes_Cmp']/6.6 - ((df['Passes_Att']-df['Passes_Cmp'])/3.2) + df['Unnamed: 23_level_0_KP']
            + df['Take-Ons_Succ']*2.9 - ((df['Take-Ons_Att']-df['Take-Ons_Succ'])*0.8) +
            1.1*df['Blocks_Sh'] + 1.5*df['Unnamed: 23_level_0_KP'] + 1.2*df['Performance_Crs'] +
            2.2*df['Performance_SoT'] + ((df['Performance_Sh']-df['Performance_SoT'])/4) +
            df['Unnamed: 5_level_0_Min']/30 + 10*df['Performance_Gls'] + 8*df['Performance_Ast'] +
            (-5*df['Performance_CrdR']) + (-5*df['Performance_PKcon']) + (-5*(df['Performance_PKatt']-df['Performance_PK'])) + (3*df.get('Hit_Woodwork', 0)))
    
    pk_won = df['Performance_PKwon'].values[0]
    pk_scored = df['Performance_PK'].values[0]
    
    if (pk_won == 1) and (pk_scored != 1):
        score += 6.4
            
    val = score.values[0] if isinstance(score, pd.Series) else score
    return round(val, 0)

def fwd_score_calc(df, team_score, team_conc):
    score = ( 1.4*df['Aerial Duels_Won'] - 0.4*df['Aerial Duels_Lost'] + 2.6*df['Performance_Tkl']
            - 1*df['Challenges_Lost'] + 2.7*df['Performance_Int'] + 0.8*df['Unnamed: 20_level_0_Clr']
            + ((3*team_score)) + (5-(0.9*df['Carries_Dis'])-(0.5*(df['Performance_Fls']+df['Performance_Off']))
                               -(3.0*df['Performance_OG'])-(5*df['Unnamed: 21_level_0_Err'])) +
            df['Passes_Cmp']/6 - ((df['Passes_Att']-df['Passes_Cmp'])/8.0) + df['Unnamed: 23_level_0_KP']
            + df['Take-Ons_Succ']*3.0 - ((df['Take-Ons_Att']-df['Take-Ons_Succ'])*1.0) +
           0.8*df['Blocks_Sh'] + 1.5*df['Unnamed: 23_level_0_KP'] + 1.2*df['Performance_Crs'] +
            3.0*df['Performance_SoT'] + ((df['Performance_Sh']-df['Performance_SoT'])/3) +
            df['Unnamed: 5_level_0_Min']/30 + 10*df['Performance_Gls'] + 8*df['Performance_Ast'] +
            (-5*df['Performance_CrdR']) + (-5*df['Performance_PKcon']) + (-5*(df['Performance_PKatt']-df['Performance_PK'])) + (3*df.get('Hit_Woodwork', 0)))
    
    pk_won = df['Performance_PKwon'].values[0]
    pk_scored = df['Performance_PK'].values[0]
    
    if (pk_won == 1) and (pk_scored != 1):
        score += 6.4
    
    val = score.values[0] if isinstance(score, pd.Series) else score
    return round(val, 0)


# ============================================================
# GK ML MODEL (UNMODIFIED FROM UCL SCORER)
# ============================================================

# Global model cache to avoid reloading on every player
GK_ML_MODEL = None
MODEL_LOADED = False

def load_gk_model():
    global GK_ML_MODEL, MODEL_LOADED
    if MODEL_LOADED:
        return GK_ML_MODEL
        
    try:
        import json
        from sklearn.ensemble import GradientBoostingRegressor
        
        # Look for training data JSON (search relative to THIS file's directory)
        base_dir = os.path.dirname(os.path.abspath(__file__))
        paths = [
            os.path.join(base_dir, "gk_training_data.json"),
            os.path.join(base_dir, "scripts", "verify", "gk_training_data.json"),
            "gk_training_data.json",
        ]
        
        json_path = None
        for p in paths:
            if os.path.exists(p):
                json_path = p
                break
                
        if json_path:
            with open(json_path, 'r') as f:
                training_data = json.load(f)
            
            if training_data:
                # Convert to DataFrame
                df_train = pd.DataFrame(training_data)
                
                # Features columns matching exact order
                feature_cols = ["saves", "claims", "sweep", "rec", "clears", "acc_pass", 
                                "fail_pass", "og", "punch", "sv_inside", "poss_lost", 
                                "pk_save", "pk_faced", "gp", "ksv"]
                
                X = df_train[feature_cols]
                y = df_train['target']
                
                # Train Model On-The-Fly (Fast & Robust)
                # Parameters optimized from local training
                model = GradientBoostingRegressor(n_estimators=500, random_state=42, learning_rate=0.05)
                model.fit(X, y)
                
                GK_ML_MODEL = model
                print(f"[FootballScorer] Successfully trained GK ML Model from {json_path} (n={len(training_data)})")
            else:
                print("[FootballScorer] Training data JSON found but empty.")
        else:
            print("[FootballScorer] GK Training Data JSON not found, using v11 formula fallback.")
            
    except Exception as e:
        print(f"[FootballScorer] Failed to initialize GK ML Model: {e}")
        import traceback
        traceback.print_exc()
        
    MODEL_LOADED = True
    return GK_ML_MODEL

def gk_score_calc(df, team_score, team_conc):
    """Goalkeeper score — v12 (WhoScored-fitted).

    Least-squares fit (RMSE 0.92, MAE 0.70 over 48 known-correct GW1 keepers) on
    the stats WhoScored actually exposes. The retired ML model and v11 formula
    relied on GoalsPrevented / KeeperSaveValue / PKFaced / Rec / PossLost, which
    the scraper always reports as 0, so they were systematically wrong. Refit from
    new known-correct scores with scripts/fit_gk_scoring.py.
    """
    def _g(col):
        if col not in df:
            return 0.0
        x = df[col].values[0]
        return 0.0 if pd.isna(x) else float(x)

    saves        = _g('Performance_Saves')
    high_claims  = _g('Performance_HighClaims')
    runs_out     = _g('Performance_RunsOut')
    clearances   = _g('Unnamed: 20_level_0_Clr')
    punches      = _g('Performance_Punches')
    saves_in_box = _g('Performance_SavedInsideBox')
    passes_cmp   = _g('Passes_Cmp')
    failed_pass  = _g('Passes_Att') - passes_cmp
    minutes      = _g('Unnamed: 5_level_0_Min')
    conceded     = _g('goals_conceded')
    yellow       = _g('Performance_CrdY')
    red          = _g('Performance_CrdR')
    pk_con       = _g('Performance_PKcon')
    clean_sheet  = 1.0 if (conceded == 0 and minutes >= 60) else 0.0

    score = (
        31.430
        + 2.981 * saves
        + 2.602 * high_claims
        - 0.199 * runs_out
        + 1.052 * clearances
        + 1.750 * punches
        + 0.393 * saves_in_box
        + 0.233 * passes_cmp
        - 0.125 * failed_pass
        - 0.123 * minutes
        - 5.988 * conceded
        + 0.026 * clean_sheet
        - 1.116 * yellow
        - 1.116 * pk_con
        - 5.0 * red  # no red cards in the fit set — keep a real sending-off penalty
    )
    return round(score)


# ============================================================
# DISPATCH WRAPPER
# ============================================================

def score_calc_wrapper(pos, df, team_score, team_conc):
    if pos == "FWD":
        return fwd_score_calc(df, team_score, team_conc)
    elif pos == "MID":
        return mid_score_calc(df, team_score, team_conc)
    elif pos == "DEF":
        return def_score_calc(df, team_score, team_conc)
    elif pos == "GK":
        return gk_score_calc(df, team_score, team_conc)
    else:
        return mid_score_calc(df, team_score, team_conc)


# ============================================================
# MATCH EVENTS PROCESSOR (UNMODIFIED FROM UCL SCORER)
# ============================================================

def process_match_events(match_events, df_home, df_away, match_duration=90):
    """
    Processes match events and returns a DataFrame with player statistics.
    Fixed to handle 0-minute bench players correctly.
    
    Args:
        match_events: List of match event dicts (goals, subs)
        df_home: DataFrame of home team players
        df_away: DataFrame of away team players
        match_duration: Total match duration in minutes (90 for normal, 120 for extra time)
    """
    # Combine home and away players into sets for team assignments
    team_home_players = set(df_home['Unnamed: 0_level_0_Player'].str.strip())
    team_away_players = set(df_away['Unnamed: 0_level_0_Player'].str.strip())
    
    # Create lookups for substitute status
    home_subs = set(df_home[df_home['is_sub'] == True]['Unnamed: 0_level_0_Player'].str.strip())
    away_subs = set(df_away[df_away['is_sub'] == True]['Unnamed: 0_level_0_Player'].str.strip())
    all_subs = home_subs.union(away_subs)

    def get_team(player_name):
        if player_name in team_home_players:
            return 'Home'
        elif player_name in team_away_players:
            return 'Away'
        else:
            return 'Unknown'

    def parse_time(time_str):
        if '+' in time_str:
            base_minute = time_str.split('+')[0]
            return int(base_minute)
        elif ':' in time_str:
            base_minute = time_str.split(':')[0]
            return int(base_minute)
        else:
            return int(time_str)

    # Build a scoreline timeline
    scoreline_timeline = [{'minute': 0, 'home_goals': 0, 'away_goals': 0}]
    current_home_goals = 0
    current_away_goals = 0

    # Collect goal events and sort them by time
    for event in match_events:
        if event['event_kind'] == 'Goal':
            minute = parse_time(event['time'])
            scorer = event['player']
            scoring_team = get_team(scorer)

            if scoring_team == 'Home':
                current_home_goals += 1
            elif scoring_team == 'Away':
                current_away_goals += 1

            scoreline_timeline.append({
                'minute': minute,
                'home_goals': current_home_goals,
                'away_goals': current_away_goals
            })

    # Ensure the final scoreline is included — use actual match duration
    match_end_time = match_duration
    if scoreline_timeline[-1]['minute'] < match_end_time:
        scoreline_timeline.append({
            'minute': match_end_time,
            'home_goals': current_home_goals,
            'away_goals': current_away_goals
        })

    def get_scoreline_before_minute(minute):
        for entry in reversed(scoreline_timeline):
            if entry['minute'] <= minute:
                return entry
        return {'home_goals': 0, 'away_goals': 0}

    # Build player intervals based on substitutions
    players = {}

    for event in match_events:
        event_kind = event['event_kind']
        minute = parse_time(event['time'])

        if event_kind == 'Substitution':
            player_on = event['player_on']
            player_off = event['player_off']

            players[player_on] = {
                'team': get_team(player_on),
                'on_time': minute,
                'off_time': match_end_time
            }

            if player_off in players:
                players[player_off]['off_time'] = minute
            else:
                players[player_off] = {
                    'team': get_team(player_off),
                    'on_time': 0,
                    'off_time': minute
                }

    # Add players who played full match OR sat on bench
    all_players = set(df_home['Unnamed: 0_level_0_Player'].tolist() + df_away['Unnamed: 0_level_0_Player'].tolist())
    
    for player in all_players:
        if player not in players:
            if player in all_subs:
                players[player] = {
                    'team': get_team(player),
                    'on_time': 0,
                    'off_time': 0
                }
            else:
                players[player] = {
                    'team': get_team(player),
                    'on_time': 0,
                    'off_time': match_end_time
                }

    # Calculate goals scored and conceded for each player
    player_stats = []
    final_scoreline = scoreline_timeline[-1]

    for player, data in players.items():
        team = data['team']
        on_time = data['on_time']
        off_time = data['off_time']
        minutes_played = off_time - on_time

        goals_scored = 0
        goals_conceded = 0
        
        if minutes_played > 0:
            scoreline_before_on = get_scoreline_before_minute(on_time)
            scoreline_before_off = get_scoreline_before_minute(off_time)

            if on_time == 0 and off_time == match_end_time:
                goals_scored = final_scoreline['home_goals'] if team == 'Home' else final_scoreline['away_goals']
                goals_conceded = final_scoreline['away_goals'] if team == 'Home' else final_scoreline['home_goals']
            elif on_time == 0:
                goals_scored = scoreline_before_off['home_goals'] if team == 'Home' else scoreline_before_off['away_goals']
                goals_conceded = scoreline_before_off['away_goals'] if team == 'Home' else scoreline_before_off['home_goals']
            elif off_time == match_end_time:
                goals_scored = (final_scoreline['home_goals'] - scoreline_before_on['home_goals']) if team == 'Home' else (final_scoreline['away_goals'] - scoreline_before_on['away_goals'])
                goals_conceded = (final_scoreline['away_goals'] - scoreline_before_on['away_goals']) if team == 'Home' else (final_scoreline['home_goals'] - scoreline_before_on['home_goals'])
            else:
                goals_scored = (scoreline_before_off['home_goals'] - scoreline_before_on['home_goals']) if team == 'Home' else (scoreline_before_off['away_goals'] - scoreline_before_on['away_goals'])
                goals_conceded = (scoreline_before_off['away_goals'] - scoreline_before_on['away_goals']) if team == 'Home' else (scoreline_before_off['home_goals'] - scoreline_before_on['home_goals'])

        player_stats.append({
            'Unnamed: 0_level_0_Player': player,
            'minutes_played': minutes_played,
            'goals_scored': goals_scored,
            'goals_conceded': goals_conceded
        })

    df_match_stats = pd.DataFrame(player_stats)

    df_home = df_home.merge(df_match_stats, on='Unnamed: 0_level_0_Player', how='left')
    df_away = df_away.merge(df_match_stats, on='Unnamed: 0_level_0_Player', how='left')

    final_df = pd.concat([df_home, df_away], ignore_index=True)

    final_df['minutes_played'] = final_df['minutes_played'].fillna(0)
    final_df['goals_scored'] = final_df['goals_scored'].fillna(0)
    final_df['goals_conceded'] = final_df['goals_conceded'].fillna(0)

    return final_df


# ============================================================
# ENTRY POINT — FBREF-BASED SCORING
# ============================================================

def calc_all_players_fbref(fbref_url):
    """Calculate fantasy scores for all players in a match using FBref data.
    
    Args:
        fbref_url: FBref match report URL
                   (e.g., https://fbref.com/en/matches/abc123/...)
    
    Returns:
        DataFrame with columns: name, score, pos (+ all raw stats)
    """
    import fbref_adapter
    
    try:
        merged_df, match_events = fbref_adapter.get_player_stats_df(fbref_url)
    except Exception as e:
        print(f"[FootballScorer] Error fetching FBref data: {e}")
        return pd.DataFrame()

    # Split back to home/away for the existing logic processor
    df_home = merged_df[merged_df['Team'] == 'Home'].copy()
    df_away = merged_df[merged_df['Team'] == 'Away'].copy()
    
    # Process match events (goals, subs) to calculate +/- metrics
    final_df_with_plus_minus = process_match_events(match_events, df_home, df_away)
    
    scores = []
    
    for index, row in final_df_with_plus_minus.iterrows():
        name = row['Unnamed: 0_level_0_Player']
        pos = row['Pos']
        
        df = final_df_with_plus_minus[final_df_with_plus_minus['Unnamed: 0_level_0_Player'] == name]
        
        if df.empty:
            continue
            
        if len(df) > 1:
            print(f"[FootballScorer] Warning: Duplicate entries for {name}. Using first one.")
            df = df.iloc[[0]]
            
        minutes_played = df['minutes_played'].values[0]
        
        # Unused subs (0 minutes) don't score
        if minutes_played == 0:
            continue
            
        t_score = df['goals_scored'].values[0]
        t_conc = df['goals_conceded'].values[0]
        
        score = 0
        try:
            score = score_calc_wrapper(pos, df, t_score, t_conc)
        except Exception as e:
            print(f"[FootballScorer] Error calculating score for {name} ({pos}): {e}")
            score = 0
            
        scores.append([name, score, pos])
    
    if not scores:
        return pd.DataFrame(columns=["name", "score", "pos"])

    scores_df = pd.DataFrame(scores, columns=["name", "score", "pos"])
    
    stacked_df = final_df_with_plus_minus.merge(
        scores_df, left_on='Unnamed: 0_level_0_Player', right_on='name', how='inner'
    )
    
    stacked_df['score'] = stacked_df['score'].astype(int)
    
    return stacked_df


# ============================================================
# ENTRY POINT — WHOSCORED-BASED SCORING
# ============================================================

def calc_all_players_whoscored(ws_url, registered_positions=None):
    """Calculate fantasy scores for all players in a match using WhoScored data.

    ``registered_positions`` maps player name -> registered role (e.g. "Defender").
    When omitted it is loaded from ``fifa_wc_2026_players.json``. It is the source of
    truth for HOW a player is scored (see the registered-position rule below); tests
    pass it explicitly.
    """
    import whoscored_adapter
    import json
    from pathlib import Path

    # Removed try-catch to allow exception to bubble up
    df_players = whoscored_adapter.get_whoscored_stats(ws_url)

    if df_players.empty:
        return pd.DataFrame(columns=["Player", "Team", "Position", "Score", "minutes_played"])

    # Load registered squad positions (unless the caller supplied them).
    if registered_positions is None:
        players_file = Path(__file__).parent / "fifa_wc_2026_players.json"
        registered_positions = {}
        if players_file.exists():
            try:
                with open(players_file, "r") as f:
                    players_data = json.load(f)
                for p in players_data:
                    if isinstance(p, dict) and "name" in p:
                        registered_positions[p["name"]] = p.get("role", "")
            except Exception as e:
                print(f"[FootballScorer] Error loading players database: {e}")

    from scoring.positions import map_role_to_pos, position_score_map

    scores = []

    for index, row in df_players.iterrows():
        name = row['Unnamed: 0_level_0_Player']
        pos_match = row['Pos']

        # We wrap in DF because score_calc_wrapper expects it
        df_row = pd.DataFrame([row])

        minutes_played = row['minutes_played']
        if minutes_played == 0:
            continue

        t_score = row['goals_scored']
        t_conc = row['goals_conceded']

        pos_reg = map_role_to_pos(registered_positions.get(name, ""))

        # KEY RULE: a player's POINTS are always computed from their REGISTERED
        # position; the position they actually played only adds an extra ELIGIBLE
        # Best-11 slot carrying that SAME registered-position score. (Kimmich, a
        # listed DEF playing MID, earns his defender points but may fill a MID slot.)
        # Players not in the squad DB fall back to scoring at their played position.
        def _score_for(pos, _df=df_row, _ts=t_score, _tc=t_conc, _name=name):
            try:
                return score_calc_wrapper(pos, _df, _ts, _tc)
            except Exception as e:
                print(f"[FootballScorer] Error scoring {_name} as {pos}: {e}")
                return 0

        pos_scores = position_score_map(pos_reg, pos_match, _score_for)
        for pos, sc in pos_scores.items():
            scores.append([name, sc, pos])
        if pos_reg and pos_match and pos_match != pos_reg:
            print(f"[FootballScorer] {name}: scored as registered {pos_reg} "
                  f"({pos_scores.get(pos_reg)} pts), also eligible at played {pos_match}")

    if not scores:
        return pd.DataFrame(columns=["Player", "Team", "Position", "Score", "minutes_played"])

    scores_df = pd.DataFrame(scores, columns=["name", "score", "pos"])
    
    stacked_df = df_players.merge(
        scores_df, 
        left_on='Unnamed: 0_level_0_Player', 
        right_on='name', 
        how='left'
    )
    
    stacked_df.drop(columns=['Pos', 'name'], inplace=True, errors='ignore')
    stacked_df.rename(columns={'Unnamed: 0_level_0_Player': 'Player', 'score': 'Score', 'pos': 'Position'}, inplace=True)
    
    cols = ['Player', 'Team', 'Position', 'Score', 'minutes_played']
    remaining_cols = [c for c in stacked_df.columns if c not in cols]
    final_df = stacked_df[cols + remaining_cols]
    
    return final_df


