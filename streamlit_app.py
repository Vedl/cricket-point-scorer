import streamlit as st
import pandas as pd
import json
import os
from cricbuzz_scraper import CricbuzzScraper
from player_score_calculator import CricketScoreCalculator

# --- Page Config ---
st.set_page_config(page_title="Fantasy Cricket Auction Platform", page_icon="🏏", layout="wide")

# --- Data File Paths ---
DATA_DIR = os.path.dirname(os.path.abspath(__file__))
AUCTION_DATA_FILE = os.path.join(DATA_DIR, "auction_data.json")
PLAYERS_DB_FILE = os.path.join(DATA_DIR, "players_database.json")

# --- Load/Save Functions for Persistence ---
def load_auction_data():
    """Load auction data from JSON file."""
    if os.path.exists(AUCTION_DATA_FILE):
        try:
            with open(AUCTION_DATA_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return {"participants": [], "gameweek_scores": {}}

def save_auction_data(data):
    """Save auction data to JSON file."""
    with open(AUCTION_DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def load_players_database():
    """Load master player database."""
    if os.path.exists(PLAYERS_DB_FILE):
        try:
            with open(PLAYERS_DB_FILE, 'r') as f:
                data = json.load(f)
                return data.get("players", [])
        except:
            pass
    return []

# --- Initialize Data ---
auction_data = load_auction_data()
players_db = load_players_database()

# Create lookup dict for quick role finding
player_role_lookup = {p['name']: p['role'] for p in players_db}
player_names = [p['name'] for p in players_db]

# --- Navigation ---
st.sidebar.title("🏏 T20 WC Auction")
page = st.sidebar.radio("Navigation", ["📊 Calculator", "🎯 Auction Room", "⚙️ Gameweek Admin", "🏆 Standings"])

# =====================================
# PAGE 1: Calculator (Original)
# =====================================
if page == "📊 Calculator":
    st.title("🏏 Fantasy Cricket Points Calculator")
    st.markdown("""
    Calculate fantasy points instantly from any **Cricbuzz Scorecard URL**.
    This app uses a custom **Role-Based Scoring System** that ensures fairness for Bowlers and All-rounders.
    """)
    
    url = st.text_input("Enter Cricbuzz Scorecard URL", placeholder="https://www.cricbuzz.com/live-cricket-scorecard/...")
    
    if st.button("Calculate Points", type="primary"):
        if not url:
            st.error("Please enter a URL first.")
        else:
            with st.spinner("Fetching match data..."):
                try:
                    scraper = CricbuzzScraper()
                    calculator = CricketScoreCalculator()
                    players = scraper.fetch_match_data(url)
                    
                    if not players:
                        st.error("Could not fetch player data. Please check the URL.")
                    else:
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
                        
                        df = pd.DataFrame(results)
                        df = df.sort_values(by="Points", ascending=False).reset_index(drop=True)
                        
                        st.subheader("🏆 Leaderboard")
                        top_3 = df.head(3)
                        cols = st.columns(3)
                        medals = ["🥇", "🥈", "🥉"]
                        
                        for i, (index, row) in enumerate(top_3.iterrows()):
                            with cols[i]:
                                st.metric(label=f"{medals[i]} {row['Player']}", value=f"{row['Points']} pts", delta=row['Role'])
                        
                        st.dataframe(df, use_container_width=True, height=600)
                        
                except Exception as e:
                    st.error(f"An error occurred: {e}")

# =====================================
# PAGE 2: Auction Room
# =====================================
elif page == "🎯 Auction Room":
    st.title("🎯 Auction Room")
    st.markdown("Manage participants and their squads for the T20 World Cup Fantasy League.")
    
    # --- RESET BUTTONS ---
    st.sidebar.divider()
    st.sidebar.subheader("⚠️ Admin Actions")
    
    if st.sidebar.button("🔄 Reset All Data", type="secondary"):
        auction_data = {"participants": [], "gameweek_scores": {}}
        save_auction_data(auction_data)
        st.sidebar.success("All data has been reset!")
        st.rerun()
    
    # --- Add Participant ---
    st.subheader("👤 Add New Participant")
    new_name = st.text_input("Participant Name", key="new_participant")
    if st.button("Add Participant"):
        participant_names = [p['name'] for p in auction_data['participants']]
        if new_name and new_name not in participant_names:
            auction_data['participants'].append({'name': new_name, 'squad': [], 'ir_player': None})
            save_auction_data(auction_data)
            st.success(f"Added {new_name}!")
            st.rerun()
        elif new_name:
            st.warning("Participant already exists.")
    
    st.divider()
    
    # --- Manage Squads ---
    st.subheader("📋 Manage Squads")
    
    if not auction_data['participants']:
        st.info("No participants yet. Add some above!")
    else:
        participant_names = [p['name'] for p in auction_data['participants']]
        selected_participant = st.selectbox("Select Participant", participant_names)
        participant = next((p for p in auction_data['participants'] if p['name'] == selected_participant), None)
        
        if participant:
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.markdown(f"**Squad Size:** {len(participant['squad'])}/19")
                if participant.get('ir_player'):
                    st.warning(f"🚑 Injury Reserve: {participant['ir_player']}")
                
                # Add Player to Squad - AUTO SUGGEST
                st.markdown("**Add Player to Squad**")
                
                # Filter out players already in any squad
                all_drafted_players = []
                for p in auction_data['participants']:
                    all_drafted_players.extend([pl['name'] for pl in p['squad']])
                
                available_players = [name for name in player_names if name not in all_drafted_players]
                
                if available_players:
                    selected_player = st.selectbox(
                        "Search Player (type to filter)",
                        options=[""] + available_players,
                        format_func=lambda x: f"{x} ({player_role_lookup.get(x, 'Unknown')})" if x else "Select a player...",
                        key="player_selector"
                    )
                    
                    if selected_player:
                        role = player_role_lookup.get(selected_player, "Unknown")
                        st.info(f"**{selected_player}** - Role: **{role}**")
                        
                        if st.button("➕ Add to Squad", type="primary"):
                            if len(participant['squad']) >= 19:
                                st.error("Squad is full (19 players max)!")
                            else:
                                participant['squad'].append({'name': selected_player, 'role': role})
                                save_auction_data(auction_data)
                                st.success(f"Added {selected_player} to {selected_participant}'s squad!")
                                st.rerun()
                else:
                    st.warning("All players have been drafted!")
                
                # Reset Squad Button
                st.divider()
                if st.button(f"🗑️ Reset {selected_participant}'s Squad", type="secondary"):
                    participant['squad'] = []
                    participant['ir_player'] = None
                    save_auction_data(auction_data)
                    st.success(f"Reset {selected_participant}'s squad!")
                    st.rerun()
            
            with col2:
                st.markdown("**Current Squad**")
                if participant['squad']:
                    squad_df = pd.DataFrame(participant['squad'])
                    st.dataframe(squad_df, use_container_width=True, hide_index=True)
                    
                    # Set Injury Reserve
                    if len(participant['squad']) == 19:
                        st.markdown("**Set Injury Reserve**")
                        ir_options = [p['name'] for p in participant['squad']]
                        ir_selection = st.selectbox("Select IR Player", ir_options, key=f"ir_{selected_participant}")
                        if st.button("Set as IR"):
                            participant['ir_player'] = ir_selection
                            save_auction_data(auction_data)
                            st.success(f"{ir_selection} is now on Injury Reserve.")
                            st.rerun()
                    
                    # Remove individual player
                    st.divider()
                    st.markdown("**Remove Player**")
                    remove_options = [p['name'] for p in participant['squad']]
                    player_to_remove = st.selectbox("Select Player to Remove", remove_options, key="remove_player")
                    if st.button("❌ Remove from Squad"):
                        participant['squad'] = [p for p in participant['squad'] if p['name'] != player_to_remove]
                        if participant.get('ir_player') == player_to_remove:
                            participant['ir_player'] = None
                        save_auction_data(auction_data)
                        st.success(f"Removed {player_to_remove}!")
                        st.rerun()
                else:
                    st.info("No players in squad yet.")
    
    # --- Participants Overview ---
    st.divider()
    st.subheader("📊 All Participants")
    if auction_data['participants']:
        overview_data = []
        for p in auction_data['participants']:
            overview_data.append({
                "Name": p['name'],
                "Squad Size": len(p['squad']),
                "WK": len([pl for pl in p['squad'] if pl['role'] == 'WK']),
                "Bat": len([pl for pl in p['squad'] if pl['role'] == 'Bat']),
                "AR": len([pl for pl in p['squad'] if pl['role'] == 'AR']),
                "Bowl": len([pl for pl in p['squad'] if pl['role'] == 'Bowl']),
                "IR": p.get('ir_player') or "-"
            })
        st.dataframe(pd.DataFrame(overview_data), use_container_width=True, hide_index=True)
        
        # Delete Participant Button
        st.divider()
        st.subheader("🗑️ Delete Participant")
        del_participant = st.selectbox("Select Participant to Delete", [p['name'] for p in auction_data['participants']], key="del_participant")
        if st.button("Delete Participant", type="secondary"):
            auction_data['participants'] = [p for p in auction_data['participants'] if p['name'] != del_participant]
            save_auction_data(auction_data)
            st.success(f"Deleted {del_participant}!")
            st.rerun()

# =====================================
# PAGE 3: Gameweek Admin
# =====================================
elif page == "⚙️ Gameweek Admin":
    st.title("⚙️ Gameweek Admin")
    st.markdown("Process match data and calculate points for each gameweek.")
    
    gameweek_num = st.number_input("Gameweek Number", min_value=1, max_value=10, value=1)
    urls_input = st.text_area("Match URLs (one per line)", height=200, placeholder="https://www.cricbuzz.com/live-cricket-scorecard/...\nhttps://www.cricbuzz.com/live-cricket-scorecard/...")
    
    if st.button("🚀 Process Gameweek", type="primary"):
        urls = [u.strip() for u in urls_input.split('\n') if u.strip()]
        
        if not urls:
            st.error("Please enter at least one URL.")
        else:
            scraper = CricbuzzScraper()
            calculator = CricketScoreCalculator()
            all_scores = {}
            
            progress = st.progress(0)
            status = st.empty()
            
            for i, url in enumerate(urls):
                status.text(f"Processing match {i+1}/{len(urls)}...")
                try:
                    players = scraper.fetch_match_data(url)
                    for p in players:
                        score = calculator.calculate_score(p)
                        name = p['name']
                        if name in all_scores:
                            all_scores[name] += score
                        else:
                            all_scores[name] = score
                except Exception as e:
                    st.warning(f"Error processing {url}: {e}")
                
                progress.progress((i + 1) / len(urls))
            
            # Store in persistent data
            auction_data['gameweek_scores'][str(gameweek_num)] = all_scores
            save_auction_data(auction_data)
            
            status.text("✅ Processing Complete!")
            st.success(f"Gameweek {gameweek_num} processed! {len(all_scores)} players scored.")
            
            # Show preview
            st.subheader("📊 Scores Preview")
            scores_df = pd.DataFrame([{"Player": k, "Points": v} for k, v in all_scores.items()])
            scores_df = scores_df.sort_values(by="Points", ascending=False)
            st.dataframe(scores_df.head(20), use_container_width=True, hide_index=True)
    
    # Show processed gameweeks
    st.divider()
    st.subheader("📅 Processed Gameweeks")
    if auction_data.get('gameweek_scores'):
        for gw, scores in auction_data['gameweek_scores'].items():
            st.write(f"**Gameweek {gw}**: {len(scores)} players scored")
        
        # Reset gameweek scores button
        if st.button("🔄 Reset All Gameweek Scores", type="secondary"):
            auction_data['gameweek_scores'] = {}
            save_auction_data(auction_data)
            st.success("All gameweek scores have been reset!")
            st.rerun()
    else:
        st.info("No gameweeks processed yet.")

# =====================================
# PAGE 4: Standings
# =====================================
elif page == "🏆 Standings":
    st.title("🏆 League Standings")
    
    # Gameweek Selector
    available_gws = list(auction_data.get('gameweek_scores', {}).keys())
    
    if not available_gws:
        st.info("No gameweeks have been processed yet. Go to Gameweek Admin to process matches.")
    else:
        view_mode = st.radio("View", ["Overall (Cumulative)", "By Gameweek"], horizontal=True)
        
        if view_mode == "By Gameweek":
            selected_gw = st.selectbox("Select Gameweek", available_gws)
            gw_scores = auction_data['gameweek_scores'].get(selected_gw, {})
        else:
            # Cumulative: sum all gameweeks
            gw_scores = {}
            for gw, scores in auction_data['gameweek_scores'].items():
                for player, score in scores.items():
                    gw_scores[player] = gw_scores.get(player, 0) + score
        
        # Calculate Best 11 for each participant
        def get_best_11(squad, player_scores, ir_player=None):
            """
            Selects the best 11 from a squad based on player scores.
            Rules: 1 WK (mandatory), 3-6 BAT, 1-4 AR, 3-6 BOWL
            """
            active_squad = [p for p in squad if p['name'] != ir_player]
            
            # Get scores for all squad players
            scored_players = []
            for p in active_squad:
                score = player_scores.get(p['name'], 0)
                scored_players.append({'name': p['name'], 'role': p['role'], 'score': score})
            
            # Sort by score descending
            scored_players.sort(key=lambda x: x['score'], reverse=True)
            
            # Group by role
            by_role = {'WK': [], 'Bat': [], 'AR': [], 'Bowl': []}
            for p in scored_players:
                role = p['role']
                if role in by_role:
                    by_role[role].append(p)
            
            # Selection with constraints
            best_11 = []
            
            # 1 WK mandatory
            if by_role['WK']:
                best_11.append(by_role['WK'][0])
                by_role['WK'] = by_role['WK'][1:]
            else:
                # Penalty: no WK, leave one spot empty (0 points)
                best_11.append({'name': '(No WK)', 'role': 'WK', 'score': 0})
            
            # Min constraints first
            for _ in range(3):  # Min 3 BAT
                if by_role['Bat']:
                    best_11.append(by_role['Bat'].pop(0))
            for _ in range(1):  # Min 1 AR
                if by_role['AR']:
                    best_11.append(by_role['AR'].pop(0))
            for _ in range(3):  # Min 3 BOWL
                if by_role['Bowl']:
                    best_11.append(by_role['Bowl'].pop(0))
            
            # Fill remaining slots (up to 11) with highest scorers from remaining
            remaining = by_role['WK'] + by_role['Bat'] + by_role['AR'] + by_role['Bowl']
            remaining.sort(key=lambda x: x['score'], reverse=True)
            
            while len(best_11) < 11 and remaining:
                # Check max constraints
                role_count = {}
                for p in best_11:
                    role_count[p['role']] = role_count.get(p['role'], 0) + 1
                
                for candidate in remaining:
                    r = candidate['role']
                    max_allowed = {'WK': 4, 'Bat': 6, 'AR': 4, 'Bowl': 6}
                    if role_count.get(r, 0) < max_allowed.get(r, 11):
                        best_11.append(candidate)
                        remaining.remove(candidate)
                        break
                else:
                    break  # Can't add anyone
            
            return best_11
        
        # Calculate standings
        standings = []
        for participant in auction_data['participants']:
            best_11 = get_best_11(participant['squad'], gw_scores, participant.get('ir_player'))
            total_points = sum(p['score'] for p in best_11)
            standings.append({
                "Participant": participant['name'],
                "Points": total_points,
                "Best 11": ", ".join([f"{p['name']} ({p['score']:.0f})" for p in best_11[:3]]) + "..." if best_11 else "No players"
            })
        
        standings.sort(key=lambda x: x['Points'], reverse=True)
        
        if standings:
            st.subheader("🏆 Current Standings")
            
            # Top 3 Podium
            if len(standings) >= 3:
                cols = st.columns(3)
                medals = ["🥇", "🥈", "🥉"]
                for i, col in enumerate(cols):
                    with col:
                        st.metric(
                            label=f"{medals[i]} {standings[i]['Participant']}",
                            value=f"{standings[i]['Points']:.0f} pts"
                        )
            
            # Full Table
            st.dataframe(pd.DataFrame(standings), use_container_width=True, hide_index=True)
            
            # Detailed View
            st.divider()
            st.subheader("📋 Detailed Best 11")
            detail_participant = st.selectbox("View Best 11 for", [p['name'] for p in auction_data['participants']])
            detail_p = next((p for p in auction_data['participants'] if p['name'] == detail_participant), None)
            if detail_p:
                best_11 = get_best_11(detail_p['squad'], gw_scores, detail_p.get('ir_player'))
                best_11_df = pd.DataFrame(best_11)
                st.dataframe(best_11_df, use_container_width=True, hide_index=True)
        else:
            st.info("No participants have been added yet. Go to Auction Room to add participants.")

# --- Sidebar Rules (persistent) ---
with st.sidebar:
    st.divider()
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
    
    st.divider()
    st.caption(f"📊 Database: {len(players_db)} players loaded")
