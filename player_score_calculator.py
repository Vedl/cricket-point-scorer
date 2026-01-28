class CricketScoreCalculator:
    def calculate_score(self, stats):
        """
        Calculates the fantasy score for a player based on their stats.
        
        Args:
            stats (dict): A dictionary containing player statistics.
        
        Returns:
            float: The calculated fantasy score.
        """
        score = 0.0 # Changed from 0 to 0.0 for consistency with original float return
        
        # --- Role Classification ---
        role = stats.get('role', 'Unknown').lower()
        is_bowler = 'bowler' in role and 'allrou' not in role # Pure bowler
        is_bowling_allrounder = 'bowling allrounder' in role
        is_wk = 'wk' in role or 'wicket' in role
        is_pure_batter = 'batsman' in role and 'wk' not in role and 'allrou' not in role
        
        # Exemption Flags
        # Bowlers and Bowling Allrounders exempt from some batting penalties
        exempt_duck_penalty = is_bowler or is_bowling_allrounder
        exempt_sr_penalty = is_bowler or is_bowling_allrounder
        
        # Lower bonus threshold for tailenders (Pure Bowlers only?)
        # Let's apply to Pure Bowlers
        run_bonus_threshold = 15 if is_bowler else 30
        
        runs = stats.get('runs', 0)
        balls = stats.get('balls_faced', 0)
        fours = stats.get('fours', 0)
        sixes = stats.get('sixes', 0)
        
        # --- Batting Points ---
        score += runs * 0.5  # 0.5 pt per run
        score += fours * 0.5 # Bonus
        score += sixes * 1.0 # Bonus
        
        # High Score Bonus (Cumulative)
        if runs >= 100:
            score += 8 # Century
        if runs >= 50:
            score += 4 # Half Century
        if runs >= run_bonus_threshold:
            score += 2 # 30 Run Bonus (or 15 for bowlers)
            
        # Duck Penalty 
        if runs == 0 and balls > 0 and (stats.get('is_batter_or_allrounder', False) or is_wk): # Added default False for is_batter_or_allrounder
            # Only applied if NOT exempt
            if not exempt_duck_penalty:
                score -= 2

        # Strike Rate Bonus/Penalty
        if balls >= 10:
            sr = (runs / balls) * 100
            if sr > 250:
                score += 5 # Super Finisher/Powerplay
            elif 200 < sr <= 250:
                score += 4 # Excellent
            elif 170 < sr <= 200:
                score += 3 
            elif 150 < sr <= 170:
                score += 2 # Reduced from 4
            elif 130 < sr <= 150:
                score += 1 # Reduced from 2
            elif 60 < sr <= 70:
                if not exempt_sr_penalty: score -= 1 # Reduced from 2
            elif 50 < sr <= 60:
                if not exempt_sr_penalty: score -= 2 # Reduced from 4
            elif sr <= 50:
                if not exempt_sr_penalty: score -= 3 # Reduced from 6

        # --- Bowling Points ---
        wickets = stats.get('wickets', 0)
        lbw_bowled = stats.get('lbw_bowled_bonus', 0)
        maidens = stats.get('maidens', 0)
        
        score += wickets * 12 # Reduced from 25
        score += lbw_bowled * 4 # Bonus (Reduced from 8)
        score += maidens * 4 # Bonus (Reduced from 12)
        
        # Wicket Haul Bonus
        if wickets >= 5:
            score += 12 # Reduced from 16
        elif wickets == 4:
            score += 8 # Reduced from 8 (?) - Let's keep 8
        elif wickets == 3:
            score += 4 # Reduced from 4 (?) - Let's keep 4
            
        # Economy Rate
        overs = stats.get('overs_bowled', 0.0)
        runs_conceded = stats.get('runs_conceded', 0)
        
        if overs >= 2.0:
            # ER Calculation
            # Standard overs: 1.1 = 1.166? No, inputs usually decimal 1.1 means 1.1 overs.
            # But Cricbuzz gives 3.5 implies 3 overs 5 balls.
            # Convert to balls for accurate Eco? 
            # Simplified: Eco = Runs / Overs (Classic calc uses decimal overs directly often, or balls)
            # Correct way: 3.5 = 3 + 5/6 = 3.833 overs.
            import math
            o_int = int(overs)
            o_dec = (overs - o_int) * 10 # .5 -> 5
            actual_overs = o_int + (o_dec / 6)
            
            if actual_overs > 0:
                eco = runs_conceded / actual_overs
                if eco < 5:
                    score += 3 # Reduced from 6
                elif 5 <= eco < 6:
                    score += 2 # Reduced from 4
                elif 6 <= eco <= 7:
                    score += 1 # Reduced from 2
                elif 10 <= eco <= 11:
                    score -= 1 # Reduced from 2
                elif 11 < eco <= 12:
                    score -= 2 # Reduced from 4
                elif eco > 12:
                    score -= 3 # Reduced from 6

        # --- Fielding Points ---
        catches = stats.get('catches', 0)
        stumpings = stats.get('stumpings', 0)
        run_outs_direct = stats.get('run_outs_direct', 0)
        run_outs_throw = stats.get('run_outs_throw', 0)
        
        score += catches * 4 # Reduced from 8
        if catches >= 3:
            score += 2 # Bonus (Reduced from 4)
            
        score += stumpings * 6 # Reduced from 12
        score += run_outs_direct * 6 # Reduced from 12
        score += run_outs_throw * 3 # Reduced from 6
            
        return score
