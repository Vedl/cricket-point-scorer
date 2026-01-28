from backend.engine import Best11Selector

def test_best11():
    print("=== Testing Best 11 Logic ===\n")
    
    # Case 1: Ideal Balanced Squad
    print("Case 1: Balanced High Scoring Squad")
    squad_1 = [
        {'name': 'WK1', 'role': 'WK', 'score': 100},
        {'name': 'Bat1', 'role': 'Bat', 'score': 90},
        {'name': 'Bat2', 'role': 'Bat', 'score': 90},
        {'name': 'Bat3', 'role': 'Bat', 'score': 90},
        {'name': 'Bat4', 'role': 'Bat', 'score': 90},
        {'name': 'AR1', 'role': 'Allrounder', 'score': 80},
        {'name': 'AR2', 'role': 'Allrounder', 'score': 80},
        {'name': 'Bowl1', 'role': 'Bowler', 'score': 70},
        {'name': 'Bowl2', 'role': 'Bowler', 'score': 70},
        {'name': 'Bowl3', 'role': 'Bowler', 'score': 70},
        {'name': 'Bowl4', 'role': 'Bowler', 'score': 10}, # 11th man (low score)
        {'name': 'BatBench', 'role': 'Bat', 'score': 5},
    ]
    # Expect: WK(1) + Bat(4) + AR(2) + Bowl(4). Valid. Total 100+360+160+220 = 840.
    res1 = Best11Selector.select_best_11(squad_1)
    print(f"Total: {res1['total_points']}")
    roles = [p.get('category') for p in res1['selected_players']]
    print(f"Roles: {roles}")
    print(f"Notes: {res1['validation_notes']}\n")
    
    # Case 2: Too Many Batters (Constraint Check)
    print("Case 2: 8 High Scoring Batters (Max Bat is 6)")
    # We have 8 batters with 100 pts. 3 Bowlers with 10 pts. 1 WK with 10 pts. 1 AR with 10 pts.
    # We MUST pick min 3 Bowlers, min 1 AR, min 1 WK.
    # Max Batters allowed is 6.
    # So we should pick: 1 WK, 1 AR, 3 Bowlers, and 6 Best Batters.
    squad_2 = (
        [{'name': f'Bat{i}', 'role': 'Bat', 'score': 100} for i in range(8)] + 
        [{'name': f'Bowl{i}', 'role': 'Bowler', 'score': 10} for i in range(3)] +
        [{'name': 'WK1', 'role': 'WK', 'score': 10}] + 
        [{'name': 'AR1', 'role': 'Allrounder', 'score': 10}]
    )
    res2 = Best11Selector.select_best_11(squad_2)
    
    # Expected: 
    # 6 Batters * 100 = 600
    # 3 Bowlers * 10 = 30
    # 1 WK * 10 = 10
    # 1 AR * 10 = 10
    # Total = 650. (Even though 2 more Batters have 100 pts, we can't pick them).
    print(f"Total: {res2['total_points']} (Exp: 650)")
    import collections
    print(f"Roles: {collections.Counter([p['category'] for p in res2['selected_players']])}")
    print(f"Notes: {res2['validation_notes']}\n")

if __name__ == "__main__":
    test_best11()
