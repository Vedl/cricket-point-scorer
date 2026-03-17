# Sherfane Rutherford Score Investigation

## Match Stats (from Screenshot)
*   **Runs:** 76 (Not Out)
*   **Balls:** 42
*   **4s:** 2
*   **6s:** 7
*   **Strike Rate:** 180.95

## Manual Score Calculation (Expected)
Base Scoring Rule (T20):
1.  **Runs:** 76 * 1 = 76 pts
2.  **Boundaries (4s):** 2 * 1 = 2 pts
3.  **Sixes (6s):** 7 * 2 = 14 pts
4.  **Strike Rate Bonus:**
    *   SR = 180.95
    *   If SR > 170 (and runs >= 10?): Usually +6 or similar?
    *   Need to check `player_score_calculator.py` for exact tiers.
5.  **Milestone Bonus:**
    *   Half-Century (50): usually +4 or +8?
6.  **Impact/other:** ?

**Rough Total:** 76 + 2 + 14 + (SR Bonus) + (50 Bonus) = 92 + Bonuses.
To reach 118, bonuses must be ~26 points.

## Investigation Steps
1.  Read `player_score_calculator.py` to get exact formula.
2.  Create a reproduction script `debug_rutherford.py` with the exact stats to see the breakdown.
3.  Compare with reported 118.
