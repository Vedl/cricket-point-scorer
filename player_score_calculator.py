"""
Fantasy Cricket Score Calculator
Implements the 5-role scoring system with role-specific multipliers for:
- Batting (runs, boundaries, SR bonus, milestones, duck penalties)
- Bowling (wickets, maidens, economy formula, milestones)
- Fielding (catches, run outs, stumpings)
"""

import math

class CricketScoreCalculator:
    """
    Calculates fantasy points based on 5 distinct roles:
    - batsman: Pure batters
    - keeper: Wicket-keepers  
    - bat_ar: Batting All-Rounders
    - bowl_ar: Bowling All-Rounders
    - bowler: Pure bowlers
    """
    
    # Role normalization mapping
    ROLE_ALIASES = {
        'batsman': 'batsman',
        'batter': 'batsman',
        'batting': 'batsman',
        'bat': 'batsman',
        'keeper': 'keeper',
        'wk': 'keeper',
        'wicketkeeper': 'keeper',
        'wicket-keeper': 'keeper',
        'wicket keeper': 'keeper',
        'batting allrounder': 'bat_ar',
        'batting all-rounder': 'bat_ar',
        'bat_ar': 'bat_ar',
        'all-rounder': 'bat_ar',  # Default AR to batting AR
        'allrounder': 'bat_ar',
        'bowling allrounder': 'bowl_ar',
        'bowling all-rounder': 'bowl_ar',
        'bowl_ar': 'bowl_ar',
        'bowler': 'bowler',
        'bowling': 'bowler',
        'bowl': 'bowler',
    }
    
    def normalize_role(self, role_str):
        """Normalize role string to one of 5 canonical roles."""
        if not role_str:
            return 'batsman'  # Default
        
        role_lower = role_str.lower().strip()
        
        # Direct match
        if role_lower in self.ROLE_ALIASES:
            return self.ROLE_ALIASES[role_lower]
        
        # Substring matching for compound roles
        if 'wk' in role_lower or 'wicket' in role_lower or 'keeper' in role_lower:
            return 'keeper'
        if 'bowling' in role_lower and ('allround' in role_lower or 'all-round' in role_lower or 'all round' in role_lower):
            return 'bowl_ar'
        if 'batting' in role_lower and ('allround' in role_lower or 'all-round' in role_lower or 'all round' in role_lower):
            return 'bat_ar'
        if 'allround' in role_lower or 'all-round' in role_lower or 'all round' in role_lower:
            return 'bat_ar'  # Default allrounder to batting AR
        if 'bowl' in role_lower:
            return 'bowler'
        if 'bat' in role_lower:
            return 'batsman'
        
        return 'batsman'  # Ultimate fallback
    
    def calculate_score(self, stats):
        """
        Calculates the fantasy score for a player based on their stats.
        
        Args:
            stats (dict): Player statistics containing:
                - role: Player's role string
                - runs, balls_faced, fours, sixes: Batting stats
                - is_not_out: Boolean if player was not out
                - wickets, overs_bowled, maidens, runs_conceded: Bowling stats
                - has_hattrick: Boolean if player took a hattrick
                - catches, stumpings, run_outs_direct, run_outs_throw: Fielding stats
        
        Returns:
            float: The calculated fantasy score (not rounded - caller can decide)
        """
        total = 0.0
        role = self.normalize_role(stats.get('role', ''))
        
        # Calculate each category
        batting_pts = self._calculate_batting(stats, role)
        bowling_pts = self._calculate_bowling(stats, role)
        fielding_pts = self._calculate_fielding(stats, role)
        
        total = batting_pts + bowling_pts + fielding_pts
        
        return round(total, 2)
    
    def _calculate_batting(self, stats, role):
        """Calculate batting points based on role-specific multipliers."""
        pts = 0.0
        
        runs = stats.get('runs', 0) or 0
        balls = stats.get('balls_faced', 0) or 0
        fours = stats.get('fours', 0) or 0
        sixes = stats.get('sixes', 0) or 0
        is_not_out = stats.get('is_not_out', False)
        
        # --- Role-specific multipliers ---
        if role in ('batsman', 'keeper', 'bat_ar'):
            run_mult = 0.5
            four_pts = 2
            six_pts = 4
        elif role == 'bowl_ar':
            run_mult = 0.65
            four_pts = 3
            six_pts = 5
        else:  # bowler
            run_mult = 0.8
            four_pts = 4
            six_pts = 6
        
        # Base scoring
        pts += runs * run_mult
        pts += fours * four_pts
        pts += sixes * six_pts
        
        # --- Strike Rate Bonus (All Roles) ---
        if balls > 0:
            sr = (runs / balls) * 100
            
            if balls >= 10:
                pts += sr / 10
            elif balls >= 6:
                pts += sr / 30
            elif balls >= 3:
                pts += sr / 60
            elif balls >= 1:
                pts += sr / 100
        
        # --- "Not Out" Bonus ---
        if is_not_out:
            if balls > 40:
                pts += 20
            elif balls > 30:
                pts += 10
            elif balls > 20:
                pts += 5
            elif balls > 10:
                pts += 3
        
        # --- Milestones (Cumulative) ---
        if runs >= 50:
            pts += 10
        if runs >= 100:
            pts += 20  # Total +30 for century
        if runs >= 150:
            pts += 30  # Total +60 for 150
        
        # --- Negative Batting Points (ONLY Batsman, Keeper, Bat_AR) ---
        if role in ('batsman', 'keeper', 'bat_ar'):
            if runs == 0:
                if balls == 0:
                    pts -= 10  # Diamond Duck (0 runs, 0 balls)
                elif balls == 1:
                    pts -= 5   # Golden Duck (0 runs, 1 ball)
                elif balls > 1:
                    pts -= 3   # Regular Duck
        
        return pts
    
    def _calculate_bowling(self, stats, role):
        """Calculate bowling points with role-specific formula."""
        pts = 0.0
        
        wickets = stats.get('wickets', 0) or 0
        maidens = stats.get('maidens', 0) or 0
        overs_raw = stats.get('overs_bowled', 0.0) or 0.0
        runs_conceded = stats.get('runs_conceded', 0) or 0
        has_hattrick = stats.get('has_hattrick', False)
        
        # Convert overs from X.Y format to actual overs
        if overs_raw > 0:
            o_int = int(overs_raw)
            o_dec = (overs_raw - o_int) * 10  # e.g., 3.4 -> 4 balls
            actual_overs = o_int + (o_dec / 6)
        else:
            actual_overs = 0
        
        # --- Role-specific constants ---
        if role in ('batsman', 'keeper'):
            wicket_pts = 15
            maiden_pts = 15
            econ_constant = 80
            econ_mult = 0.7
        elif role == 'bat_ar':
            wicket_pts = 12.5
            maiden_pts = 12.5
            econ_constant = 70
            econ_mult = 0.8
        else:  # bowl_ar, bowler
            wicket_pts = 10
            maiden_pts = 10
            econ_constant = 65
            econ_mult = 0.9
        
        # Base wickets and maidens
        pts += wickets * wicket_pts
        pts += maidens * maiden_pts
        
        # --- Economy Rate Formula ---
        # Bonus = (Constant / Safe_Economy) * Overs_Bowled * Multiplier
        if actual_overs > 0:
            actual_economy = runs_conceded / actual_overs
            safe_economy = max(2.0, actual_economy)  # Safety rule
            
            econ_bonus = (econ_constant / safe_economy) * actual_overs * econ_mult
            pts += econ_bonus
        
        # --- Bowling Milestones (Cumulative) ---
        if wickets >= 3:
            pts += 10
        if wickets >= 5:
            pts += 20  # Total +30 for 5-fer
        if wickets >= 7:
            pts += 30  # Total +60 for 7-fer
        
        # --- Hattrick Bonus ---
        if has_hattrick:
            pts += 20
        
        return pts
    
    def _calculate_fielding(self, stats, role):
        """Calculate fielding points based on role."""
        pts = 0.0
        
        catches = stats.get('catches', 0) or 0
        stumpings = stats.get('stumpings', 0) or 0
        run_outs_direct = stats.get('run_outs_direct', 0) or 0
        run_outs_throw = stats.get('run_outs_throw', 0) or 0
        total_run_outs = run_outs_direct + run_outs_throw
        
        if role == 'keeper':
            # Keeper: Catches 3, Run Outs 5, Stumpings 7.5
            pts += catches * 3
            pts += total_run_outs * 5
            pts += stumpings * 7.5
        elif role == 'bowler':
            # Bowler: Catches 5, Run Outs 8, Catch bonus +10 if >= 3
            pts += catches * 5
            pts += total_run_outs * 8
            if catches >= 3:
                pts += 10
        else:
            # Batsman / Bat_AR / Bowl_AR: Catches 5, Run Outs 10, Catch bonus +10 if >= 3
            pts += catches * 5
            pts += total_run_outs * 10
            if catches >= 3:
                pts += 10
        
        return pts
    
    def get_score_breakdown(self, stats):
        """
        Returns a detailed breakdown of the score calculation.
        Useful for debugging and UI display.
        """
        role = self.normalize_role(stats.get('role', ''))
        
        return {
            'role': role,
            'batting_points': round(self._calculate_batting(stats, role), 2),
            'bowling_points': round(self._calculate_bowling(stats, role), 2),
            'fielding_points': round(self._calculate_fielding(stats, role), 2),
            'total': self.calculate_score(stats)
        }
