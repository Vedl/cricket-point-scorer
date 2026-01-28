from typing import List, Dict
import itertools

class Best11Selector:
    @staticmethod
    def select_best_11(squad_scores: List[Dict]) -> Dict:
        active_pool = [p for p in squad_scores if not p.get('is_ir', False)]
        
        def get_role_category(role_str):
            r = role_str.lower()
            if 'wk' in r or 'wicket' in r: return 'WK'
            if 'allrounder' in r: return 'AR'
            if 'bat' in r: return 'BAT'
            if 'bowl' in r: return 'BWL'
            return 'BAT' 
            
        pool_with_cat = []
        for p in active_pool:
            p_cat = p.copy()
            p_cat['category'] = get_role_category(p.get('role', ''))
            pool_with_cat.append(p_cat)
            
        valid_ranges = {
            'WK': (1, 4),
            'BAT': (3, 6),
            'AR': (1, 4),
            'BWL': (3, 6)
        }
        
        best_team = []
        best_score = -1
        found_valid = False
        
        pool_with_cat.sort(key=lambda x: x['score'], reverse=True)
        
        print(f"Pool Size: {len(pool_with_cat)}")
        for p in pool_with_cat:
            print(f"  {p['name']} ({p['category']}): {p['score']}")

        combo_count = 0
        valid_count = 0
        
        for team in itertools.combinations(pool_with_cat, 11):
            combo_count += 1
            counts = {'WK': 0, 'BAT': 0, 'AR': 0, 'BWL': 0}
            current_score = 0
            
            for p in team:
                counts[p['category']] += 1
                current_score += p['score']
            
            is_valid = True
            fail_reason = ""
            for role, (min_r, max_r) in valid_ranges.items():
                if not (min_r <= counts[role] <= max_r):
                    is_valid = False
                    fail_reason = f"{role}: {counts[role]} not in {min_r}-{max_r}"
                    break
            
            if is_valid:
                valid_count += 1
                found_valid = True
                if current_score > best_score:
                    best_score = current_score
                    best_team = team
                    print(f"Found BETTER Valid: Score {best_score} | Comp: {counts}")
            
            if not found_valid and current_score > best_score:
                 best_score = current_score
                 best_team = team
                 # print(f"New Best Invalid: Score {best_score} | Reason: {fail_reason}")

        print(f"Checked {combo_count} combos. Found {valid_count} valid.")
        return {"total_points": best_score}

def test():
    squad_2 = (
        [{'name': f'Bat{i}', 'role': 'Bat', 'score': 100} for i in range(8)] + 
        [{'name': f'Bowl{i}', 'role': 'Bowler', 'score': 10} for i in range(3)] +
        [{'name': 'WK1', 'role': 'WK', 'score': 10}] + 
        [{'name': 'AR1', 'role': 'Allrounder', 'score': 10}]
    )
    Best11Selector.select_best_11(squad_2)

if __name__ == "__main__":
    test()
