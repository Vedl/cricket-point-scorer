from typing import List, Dict, Optional
from sqlmodel import Session, select
from backend.models import Player, PlayerScore, Match, Participant, SquadPlayer
from cricbuzz_scraper import CricbuzzScraper
from player_score_calculator import CricketScoreCalculator

class GameweekProcessor:
    def __init__(self, session: Session):
        self.session = session
        self.scraper = CricbuzzScraper()
        self.calculator = CricketScoreCalculator()

    def process_match_url(self, url: str, gameweek: int):
        """
        Scrapes a match, saves player scores to DB.
        """
        # 1. Check if match exists
        match = self.session.exec(select(Match).where(Match.url == url)).first()
        if not match:
            match = Match(url=url, gameweek=gameweek, status="PROCESSED")
            self.session.add(match)
            self.session.commit()
            self.session.refresh(match)
        
        # 2. Scrape Data
        print(f"Processing GW{gameweek} Match: {url}")
        players_data = self.scraper.fetch_match_data(url)
        
        # 3. Save Scores
        for p_data in players_data:
            score = self.calculator.calculate_score(p_data)
            
            # Find or Create Player
            # Use 'get_best_match_player' logic if needed, but db lookup needs name
            # For now assume exact or fuzzy simple match.
            # We trust the scraper's name is the "System Name" if pre-scan worked.
            
            player = self.session.exec(select(Player).where(Player.name == p_data['name'])).first()
            if not player:
                # auto-create player observed in match? 
                # Yes, but role might be better from p_data
                player = Player(name=p_data['name'], role=p_data.get('role', 'Unknown'), cricbuzz_profile_url=p_data.get('profile_url'))
                self.session.add(player)
                self.session.commit()
                self.session.refresh(player)
            
            # Create/Update Score
            # Check if score exists for this match+player
            ps = self.session.exec(select(PlayerScore).where(
                PlayerScore.player_id == player.id,
                PlayerScore.match_id == match.id
            )).first()
            
            if not ps:
                ps = PlayerScore(
                    player_id=player.id, 
                    match_id=match.id,
                    points=score,
                    runs=p_data.get('runs', 0),
                    wickets=p_data.get('wickets', 0),
                    catches=p_data.get('catches', 0)
                )
                self.session.add(ps)
            else:
                # Update existing
                ps.points = score
                ps.runs = p_data.get('runs', 0)
                ps.wickets = p_data.get('wickets', 0)
                ps.catches = p_data.get('catches', 0)
                self.session.add(ps)
        
        self.session.commit()
        return len(players_data)

    def calculate_leaderboard(self, gameweek: int):
        """
        Calculates Best 11 for all participants for the given gameweek items.
        Returns a sorted leaderboard.
        """
        # 1. Get all matches for this gameweek
        matches = self.session.exec(select(Match).where(Match.gameweek == gameweek)).all()
        match_ids = [m.id for m in matches]
        
        if not match_ids:
            return []

        participants = self.session.exec(select(Participant)).all()
        leaderboard = []
        
        for p in participants:
            # Get Squad
            squad_entries = p.squad # List[SquadPlayer]
            
            squad_scores = []
            for entry in squad_entries:
                # Get Player Details
                player = entry.player
                
                # Get Score for this Gameweek (Sum of all matches in GW, effectively usually 1)
                scores = self.session.exec(select(PlayerScore).where(
                    PlayerScore.player_id == player.id,
                    PlayerScore.match_id.in_(match_ids)
                )).all()
                
                total_pts = sum(s.points for s in scores)
                
                squad_scores.append({
                    'name': player.name,
                    'role': player.role,
                    'score': total_pts,
                    'is_ir': entry.is_ir
                })
            
            # Run Best 11
            result = Best11Selector.select_best_11(squad_scores)
            
            leaderboard.append({
                "participant_id": p.id,
                "participant_name": p.name,
                "gw_points": result['total_points'],
                "best_11": result['selected_players'],
                "warnings": result['validation_notes']
            })
            
        leaderboard.sort(key=lambda x: x['gw_points'], reverse=True)
        return leaderboard

    def calculate_cumulative_leaderboard(self):
        """
        Calculates cumulative points across ALL gameweeks.
        """
        participants = self.session.exec(select(Participant)).all()
        leaderboard = []
        
        # Get all processed Matches
        # Actually simplest way is iteratively sum up all gameweek "Best 11" scores?
        # NO. The "Best 11" is calculated PER GAMEWEEK. Cumulative score is Sum(Best 11 Score of GW1 + Best 11 Score of GW2...).
        # We need to re-run best 11 for each gameweek and sum them. This is expensive but correct.
        
        # 1. Find all gameweeks that have matches
        matches = self.session.exec(select(Match)).all()
        gameweeks = set(m.gameweek for m in matches if m.status == "PROCESSED")
        
        participant_totals = {p.id: 0 for p in participants}
        
        for gw in gameweeks:
            gw_leaderboard = self.calculate_leaderboard(gw)
            for entry in gw_leaderboard:
                participant_totals[entry['participant_id']] += entry['gw_points']
                
        # Build Result
        for p in participants:
            leaderboard.append({
                "participant_id": p.id,
                "participant_name": p.name,
                "gw_points": participant_totals.get(p.id, 0), # Using same key for frontend compat
                "best_11": [] # Not relevant for cumulative
            })
            
        leaderboard.sort(key=lambda x: x['gw_points'], reverse=True)
        return leaderboard

class Best11Selector:
    """
    Selects the Best 11 players for a gameweek based on fantasy rules.
    Rules:
    1. Max Squad Size: 19. If 19, 1 is IR (Inactive). Active Pool = 18.
    2. Best 11 must be selected from the Active Pool.
    3. Mandatory: At least 1 Wicketkeeper (WK).
    4. If no WK in squad, playing 11 has only 10 players (1 spot is 0).
    """

    @staticmethod
    def select_best_11(squad_scores: List[Dict]) -> Dict:
        """
        Selects the Best 11 players maximizing points under constraints.
        
        Constraints:
        - Squad Size: Max 18 active (1 IR excluded).
        - Team Size: 11 players (or 10 if constraints fail due to lack of players).
        
        Role Constraints:
        - WK:  1 - 4
        - BAT: 3 - 6
        - AR:  1 - 4
        - BWL: 3 - 6
        
        Algorithm:
        - Brute-force all combinations of 11 from Active Squad (~32k checks max).
        - maximize sum(points) where constraints are met.
        - Fallback: If no valid 11, return best 11 ignoring constraints (with warning).
        """
        import itertools
        
        # 1. Filter Active
        active_pool = [p for p in squad_scores if not p.get('is_ir', False)]
        
        # 2. Normalize Roles
        # Simple classifier
        def get_role_category(role_str):
            r = role_str.lower()
            if 'wk' in r or 'wicket' in r: return 'WK'
            if 'allrounder' in r: return 'AR'
            if 'bat' in r: return 'BAT'
            if 'bowl' in r: return 'BWL'
            return 'BAT' # Default fallback
            
        pool_with_cat = []
        for p in active_pool:
            p_cat = p.copy()
            p_cat['category'] = get_role_category(p.get('role', ''))
            pool_with_cat.append(p_cat)
            
        n_active = len(pool_with_cat)
        
        # Optimization: If < 11 players, return all
        if n_active <= 11:
             return {
                "total_points": sum(p['score'] for p in pool_with_cat),
                "selected_players": pool_with_cat,
                "validation_notes": ["Squad has fewer than 11 active players."]
            }

        # Brute Force Solver
        # Generate all combinations of 11
        # Since max squad is 18, C(18, 11) = 31,824. Extremely fast.
        
        best_valid_team = []
        best_valid_score = -1
        
        best_invalid_team = []
        best_invalid_score = -1
        
        # Sort pool by score desc to hopefully hit high scoring teams early (though we check all)
        pool_with_cat.sort(key=lambda x: x['score'], reverse=True)
        
        valid_ranges = {
            'WK': (1, 3),
            'BAT': (1, 4),
            'AR': (2, 6),
            'BWL': (3, 4)
        }
        
        for team in itertools.combinations(pool_with_cat, 11):
            # Check constraints
            counts = {'WK': 0, 'BAT': 0, 'AR': 0, 'BWL': 0}
            current_score = 0
            
            for p in team:
                counts[p['category']] += 1
                current_score += p['score']
            
            # Constraint Check
            is_valid = True
            for role, (min_r, max_r) in valid_ranges.items():
                if not (min_r <= counts[role] <= max_r):
                    is_valid = False
                    break
            
            if is_valid:
                if current_score > best_valid_score:
                    best_valid_score = current_score
                    best_valid_team = team
            else:
                if current_score > best_invalid_score:
                    best_invalid_score = current_score
                    best_invalid_team = team

        notes = []
        if best_valid_score != -1:
            return {
                "total_points": best_valid_score,
                "selected_players": list(best_valid_team),
                "validation_notes": [] # Clean
            }
        else:
            notes.append("Could not find a valid 11 satisfying all role constraints (WK:1-3, BAT:1-4, AR:2-6, BWL:3-4). Returned highest scoring invalid 11.")
            
            # Specific hint
            if best_invalid_team:
                counts = {'WK': 0, 'BAT': 0, 'AR': 0, 'BWL': 0}
                for p in best_invalid_team: counts[p['category']] += 1
                notes.append(f"Current composition: {counts}")
            
            return {
                "total_points": best_invalid_score if best_invalid_score != -1 else 0,
                "selected_players": list(best_invalid_team),
                "validation_notes": notes
            }
