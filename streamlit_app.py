import streamlit as st
import pandas as pd
from cricbuzz_scraper import CricbuzzScraper
from player_score_calculator import CricketScoreCalculator

# Page Config
st.set_page_config(page_title="Fantasy Cricket Points Explorer", page_icon="🏏", layout="wide")

# Title & Description
st.title("🏏 Fantasy Cricket Points Calculator")
st.markdown("""
Calculate fantasy points instantly from any **Cricbuzz Scorecard URL**.
This app uses a custom **Role-Based Scoring System** that ensures fairness for Bowlers and All-rounders.
""")

# Input
url = st.text_input("Enter Cricbuzz Scorecard URL", placeholder="https://www.cricbuzz.com/live-cricket-scorecard/...")

if st.button("Calculate Points", type="primary"):
    if not url:
        st.error("Please enter a URL first.")
    else:
        with st.spinner("Fetching match data..."):
            try:
                # Initialize Logic
                scraper = CricbuzzScraper()
                calculator = CricketScoreCalculator()
                
                # Fetch Data
                players = scraper.fetch_match_data(url)
                
                if not players:
                    st.error("Could not fetch player data. Please check the URL.")
                else:
                    # Calculate Scores
                    results = []
                    for p in players:
                        score = calculator.calculate_score(p)
                        results.append({
                            "Player": p['name'],
                            "Role": p.get('role', 'Unknown'),
                            "Points": score,
                            "Runs": p.get('stats', {}).get('runs', p.get('runs', 0)),
                            "Wickets": p.get('stats', {}).get('wickets', p.get('wickets', 0)),
                            "Catches": p.get('stats', {}).get('catches', p.get('catches', 0))
                        })
                    
                    # Create DataFrame
                    df = pd.DataFrame(results)
                    df = df.sort_values(by="Points", ascending=False).reset_index(drop=True)
                    
                    # Display Leaderboard
                    st.subheader("🏆 Leaderboard")
                    
                    # Highlight Top 3
                    top_3 = df.head(3)
                    cols = st.columns(3)
                    medals = ["🥇", "🥈", "🥉"]
                    
                    for i, (index, row) in enumerate(top_3.iterrows()):
                        with cols[i]:
                            st.metric(label=f"{medals[i]} {row['Player']}", value=f"{row['Points']} pts", delta=row['Role'])
                    
                    # Full Table
                    st.dataframe(
                        df,
                        column_config={
                            "Points": st.column_config.NumberColumn(format="%d"),
                        },
                        use_container_width=True,
                        height=600
                    )
                    
            except Exception as e:
                st.error(f"An error occurred: {e}")

# Sidebar Rules
with st.sidebar:
    st.header("ℹ️ Scoring Rules")
    st.markdown("""
    **Batting**
    - Run: +0.5
    - Boundary: +0.5
    - Six: +1
    - 50 Bonus: +4
    - 100 Bonus: +8 (Cumulative)
    
    **Bowling**
    - Wicket: +12
    - LBW/Bowled: +4
    - Maiden: +4
    - 3 Wkts: +4
    - 5 Wkts: +12
    
    **Role-Based Fairness**
    - **Bowlers** are exempt from Duck (-2) and negative Strike Rate penalties.
    - **Power Hitting**: SR > 200 (+3) and SR > 250 (+5).
    """)
