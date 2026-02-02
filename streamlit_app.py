import streamlit as st
import pandas as pd
import json
import os
import string
import random
import hashlib
from datetime import datetime, timedelta
from cricbuzz_scraper import CricbuzzScraper
from player_score_calculator import CricketScoreCalculator

# --- Page Config ---
st.set_page_config(page_title="Fantasy Cricket Auction Platform", page_icon="🏏", layout="wide")

# --- Data File Paths ---
DATA_DIR = os.path.dirname(os.path.abspath(__file__))
AUCTION_DATA_FILE = os.path.join(DATA_DIR, "auction_data.json")
PLAYERS_DB_FILE = os.path.join(DATA_DIR, "players_database.json")
SCHEDULE_FILE = os.path.join(DATA_DIR, "t20_wc_schedule.json")

# --- Load/Save Functions for Persistence ---
def load_auction_data():
    """Load auction data from JSON file."""
    if os.path.exists(AUCTION_DATA_FILE):
        try:
            with open(AUCTION_DATA_FILE, 'r') as f:
                data = json.load(f)
                # Migrate old format to new format if needed
                if 'users' not in data:
                    data = {"users": {}, "rooms": {}}
                return data
        except:
            pass
    return {"users": {}, "rooms": {}}

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

def generate_room_code():
    """Generate a unique 6-character room code."""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

def hash_password(password):
    """Hash password using SHA256."""
    return hashlib.sha256(password.encode()).hexdigest()

def load_schedule():
    """Load T20 WC schedule."""
    if os.path.exists(SCHEDULE_FILE):
        try:
            with open(SCHEDULE_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return {"gameweeks": {}}

# --- Initialize Data ---
auction_data = load_auction_data()
players_db = load_players_database()

# Create lookup dict for quick role finding
player_role_lookup = {p['name']: p['role'] for p in players_db}
player_names = [p['name'] for p in players_db]

# --- Session State Initialization ---
if 'logged_in_user' not in st.session_state:
    st.session_state.logged_in_user = None
if 'current_room' not in st.session_state:
    st.session_state.current_room = None

# =====================================
# LOGIN / REGISTER PAGE
# =====================================
def show_login_page():
    st.title("🏏 Fantasy Cricket Auction Platform")
    st.markdown("### Welcome! Please login or register to continue.")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🔐 Login")
        login_username = st.text_input("Username", key="login_username", placeholder="Enter your username")
        login_password = st.text_input("Password", key="login_password", type="password", placeholder="Enter your password")
        if st.button("Login", type="primary", key="login_btn"):
            if login_username and login_password:
                if login_username in auction_data['users']:
                    user_data = auction_data['users'][login_username]
                    stored_hash = user_data.get('password_hash', '')
                    if stored_hash and hash_password(login_password) == stored_hash:
                        st.session_state.logged_in_user = login_username
                        st.success(f"Welcome back, {login_username}!")
                        st.rerun()
                    else:
                        st.error("Incorrect password.")
                else:
                    st.error("Username not found. Please register first.")
            else:
                st.warning("Please enter both username and password.")
    
    with col2:
        st.subheader("📝 Register")
        register_username = st.text_input("Choose Username", key="register_username", placeholder="Choose a username")
        register_password = st.text_input("Create Password", key="register_password", type="password", placeholder="Min 4 characters")
        register_password_confirm = st.text_input("Confirm Password", key="register_password_confirm", type="password", placeholder="Re-enter password")
        if st.button("Register", type="secondary", key="register_btn"):
            if register_username and register_password:
                if len(register_password) < 4:
                    st.error("Password must be at least 4 characters.")
                elif register_password != register_password_confirm:
                    st.error("Passwords do not match.")
                elif register_username in auction_data['users']:
                    st.error("Username already taken. Choose another.")
                else:
                    auction_data['users'][register_username] = {
                        "created_at": datetime.now().isoformat(),
                        "password_hash": hash_password(register_password),
                        "rooms_created": [],
                        "rooms_joined": []
                    }
                    save_auction_data(auction_data)
                    st.session_state.logged_in_user = register_username
                    st.success(f"Welcome, {register_username}! Account created.")
                    st.rerun()
            else:
                st.warning("Please enter both username and password.")

# =====================================
# ROOM SELECTION / CREATION PAGE
# =====================================
def show_room_selection():
    user = st.session_state.logged_in_user
    user_data = auction_data['users'].get(user, {})
    
    st.title(f"🏏 Welcome, {user}!")
    
    # Sidebar logout
    if st.sidebar.button("🚪 Logout"):
        st.session_state.logged_in_user = None
        st.session_state.current_room = None
        st.rerun()
    
    st.markdown("### Select or create an auction room to get started.")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("➕ Create New Room")
        room_name = st.text_input("Room Name", placeholder="e.g., Friends T20 League")
        if st.button("Create Room", type="primary"):
            if room_name:
                room_code = generate_room_code()
                # Ensure unique code
                while room_code in auction_data['rooms']:
                    room_code = generate_room_code()
                
                auction_data['rooms'][room_code] = {
                    "name": room_name,
                    "admin": user,
                    "members": [user],
                    "participants": [{
                        'name': user,
                        'squad': [],
                        'budget': 350,
                        'user': user
                    }],
                    "gameweek_scores": {},
                    "created_at": datetime.now().isoformat(),
                    # Auction System Fields
                    "big_auction_complete": False,
                    "bidding_open": False,
                    "trading_open": False,
                    "unsold_players": [],
                    "active_bids": [],
                    "pending_trades": [],
                    "gameweek_squads": {},
                    "auction_log": []
                }
                user_data['rooms_created'] = user_data.get('rooms_created', []) + [room_code]
                save_auction_data(auction_data)
                st.session_state.current_room = room_code
                st.success(f"Room created! Code: **{room_code}**")
                st.rerun()
            else:
                st.warning("Please enter a room name.")
    
    with col2:
        st.subheader("🔗 Join Existing Room")
        join_code = st.text_input("Enter Room Code", placeholder="e.g., ABC123").upper()
        if st.button("Join Room", type="secondary"):
            if join_code:
                if join_code in auction_data['rooms']:
                    room = auction_data['rooms'][join_code]
                    if user not in room['members']:
                        room['members'].append(user)
                        # Auto-add as participant
                        room['participants'].append({
                            'name': user,
                            'squad': [],
                            'budget': 350,
                            'user': user
                        })
                        user_data['rooms_joined'] = user_data.get('rooms_joined', []) + [join_code]
                        save_auction_data(auction_data)
                        st.success(f"Joined room: {room['name']} (You are now a participant!)")
                    st.session_state.current_room = join_code
                    st.rerun()
                else:
                    st.error("Invalid room code. Please check and try again.")
            else:
                st.warning("Please enter a room code.")
    
    # Show user's rooms
    st.divider()
    st.subheader("📋 Your Rooms")
    
    user_rooms = user_data.get('rooms_created', []) + user_data.get('rooms_joined', [])
    user_rooms = list(set(user_rooms))  # Remove duplicates
    
    if user_rooms:
        room_data = []
        for code in user_rooms:
            if code in auction_data['rooms']:
                room = auction_data['rooms'][code]
                room_data.append({
                    "Room Name": room['name'],
                    "Code": code,
                    "Role": "Admin" if room['admin'] == user else "Member",
                    "Members": len(room['members']),
                    "Participants": len(room['participants'])
                })
        
        if room_data:
            st.dataframe(pd.DataFrame(room_data), use_container_width=True, hide_index=True)
            
            # Quick select room
            room_codes = [r['Code'] for r in room_data]
            selected_room = st.selectbox("Select a room to enter", room_codes, format_func=lambda x: f"{auction_data['rooms'][x]['name']} ({x})")
            if st.button("Enter Room", type="primary"):
                st.session_state.current_room = selected_room
                st.rerun()
    else:
        st.info("You haven't created or joined any rooms yet.")

# =====================================
# MAIN APP (Inside a Room)
# =====================================
def show_main_app():
    user = st.session_state.logged_in_user
    room_code = st.session_state.current_room
    room = auction_data['rooms'].get(room_code)
    
    if not room:
        st.error("Room not found!")
        st.session_state.current_room = None
        st.rerun()
        return
    
    is_admin = room['admin'] == user
    
    # Auto-enroll existing members as participants if missing (Retroactive Fix)
    member_added = False
    participant_names = {p.get('user', p['name']) for p in room['participants']}
    
    for member in room['members']:
        if member not in participant_names:
            room['participants'].append({
                'name': member,
                'squad': [],
                'budget': 350,
                'user': member
            })
            member_added = True
    
    if member_added:
        save_auction_data(auction_data)
        st.toast("Updated participant list with existing room members.")
    
    # --- Sidebar ---
    st.sidebar.title(f"🏏 {room['name']}")
    
    # Room Info
    st.sidebar.markdown(f"**Room Code:** `{room_code}`")
    if is_admin:
        st.sidebar.success("👑 You are the Admin")
    else:
        st.sidebar.info(f"👑 Admin: {room['admin']}")
    
    st.sidebar.markdown(f"**Members:** {len(room['members'])}")
    
    # Navigation
    st.sidebar.divider()
    page = st.sidebar.radio("Navigation", ["📊 Calculator", "🎯 Auction Room", "⚙️ Gameweek Admin", "🏆 Standings"])
    
    # Leave Room / Logout
    st.sidebar.divider()
    if st.sidebar.button("🔙 Back to Rooms"):
        st.session_state.current_room = None
        st.rerun()
    if st.sidebar.button("🚪 Logout"):
        st.session_state.logged_in_user = None
        st.session_state.current_room = None
        st.rerun()
    
    # =====================================
    # PAGE 1: Calculator
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
                                    "Runs": p.get('runs', 0),
                                    "Wickets": p.get('wickets', 0),
                                    "Catches": p.get('catches', 0)
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
        st.markdown(f"Manage participants and squads for **{room['name']}**.")
        
        # Admin: Show invite code prominently
        if is_admin:
            st.info(f"📤 **Invite Code:** `{room_code}` — Share this with friends to join!")
            
            # Admin Actions
            st.sidebar.divider()
            st.sidebar.subheader("⚠️ Admin Actions")
            if st.sidebar.button("🔄 Reset Room Data", type="secondary"):
                room['participants'] = []
                room['gameweek_scores'] = {}
                room['active_bids'] = []
                room['unsold_players'] = []
                save_auction_data(auction_data)
                st.sidebar.success("Room data reset!")
                st.rerun()
            
            # Toggle Big Auction Complete
            big_auction_done = room.get('big_auction_complete', False)
            if st.sidebar.checkbox("Big Auction Complete", value=big_auction_done):
                room['big_auction_complete'] = True
                room['bidding_open'] = True  # Open bidding after big auction
                save_auction_data(auction_data)
            else:
                room['big_auction_complete'] = False
                room['bidding_open'] = False
                save_auction_data(auction_data)
        
        # --- Participants ---
        st.markdown("### 👥 Participants")
        st.caption("Members automatically become participants when they join the room.")
        
        # Show existing participants
        if room['participants']:
            for p in room['participants']:
                st.write(f"• **{p['name']}** - Budget: {p.get('budget', 350)}M | Squad: {len(p.get('squad', []))}")
        
        # Admin fallback: manually add participant (for guests/non-members)
        if is_admin:
            with st.expander("➕ Add Non-Member Participant (Admin)"):
                st.caption("Use this to add participants who aren't room members (e.g., guest accounts)")
                new_name = st.text_input("Participant Name", key="new_participant")
                if st.button("Add Participant"):
                    participant_names = [p['name'] for p in room['participants']]
                    if new_name and new_name not in participant_names:
                        room['participants'].append({
                            'name': new_name, 
                            'squad': [],
                            'ir_player': None,
                            'budget': 350
                        })
                        save_auction_data(auction_data)
                        st.success(f"Added {new_name} with 350M budget!")
                        st.rerun()
                    elif new_name:
                        st.warning("Participant already exists.")
        st.divider()
        
        # === AUCTION TABS ===
        auction_tabs = st.tabs(["🔴 Live Auction", "🎯 Big Auction (Manual)", "💰 Open Bidding", "🔄 Trading"])
        
        # ================ TAB 0: LIVE AUCTION ================
        with auction_tabs[0]:
            st.subheader("🔴 Live Auction")
            
            if room.get('big_auction_complete'):
                st.success("✅ Big Auction is complete! Use 'Open Bidding' tab to bid on unsold players.")
            elif not room['participants']:
                st.warning("Add participants before starting the live auction.")
            else:
                # Live auction state
                live_auction = room.get('live_auction', {})
                
                # Get all teams from players
                teams_with_players = {}
                for player in players_db:
                    team = player.get('country', 'Unknown')
                    if team not in teams_with_players:
                        teams_with_players[team] = []
                    teams_with_players[team].append(player)
                
                # Filter out already drafted players
                all_drafted_players = set()
                for p in room['participants']:
                    for pl in p['squad']:
                        all_drafted_players.add(pl['name'])
                
                if not live_auction.get('active'):
                    if is_admin:
                        # === ADMIN: START AUCTION SETUP ===
                        st.markdown("### 🎬 Start Live Auction")
                        st.info("Select a team to auction their players. Players will be shown one by one with a 15-second timer.")
                        
                        # Show available teams with player counts
                        available_teams = []
                        for team, players in teams_with_players.items():
                            undrafted = [p for p in players if p['name'] not in all_drafted_players]
                            if undrafted:
                                available_teams.append((team, len(undrafted)))
                        
                        if available_teams:
                            team_options = [f"{t[0]} ({t[1]} players)" for t in available_teams]
                            selected_team_idx = st.selectbox("Select Team to Auction", range(len(team_options)), format_func=lambda x: team_options[x])
                            selected_team = available_teams[selected_team_idx][0]
                            
                            # Show players from this team
                            team_players = [p for p in teams_with_players[selected_team] if p['name'] not in all_drafted_players]
                            
                            # Sort by role: batsman -> allrounder -> bowler
                            role_order = {'WK-Batsman': 0, 'Batsman': 1, 'Batting Allrounder': 2, 'Bowling Allrounder': 3, 'Bowler': 4}
                            team_players.sort(key=lambda x: role_order.get(x.get('role', 'Unknown'), 99))
                            
                            st.write("**Auction order:**")
                            for i, p in enumerate(team_players[:10], 1):  # Show first 10
                                st.caption(f"{i}. {p['name']} ({p.get('role', 'Unknown')})")
                            if len(team_players) > 10:
                                st.caption(f"...and {len(team_players) - 10} more")
                            
                            # Check if hidden/paused auction exists
                            existing_auction = room.get('live_auction')
                            if existing_auction and not existing_auction.get('active') and existing_auction.get('current_team') == selected_team:
                                st.warning(f"⚠️ A paused auction exists for {selected_team}")
                                if st.button("▶️ Resume Auction for " + selected_team, type="primary"):
                                    existing_auction['active'] = True
                                    # Adjust timer start to account for pause? Simple approach: Just reset timer for current player?
                                    # Or better: keep it paused until new bid?
                                    # User requested "nothing gets affected".
                                    # If we restart timer now, we might give extra time.
                                    # Let's just resume active state. The loop below will recalculate time remaining.
                                    # If time expired while paused... that's tricky.
                                    # Best to reset timer_start to NOW - (duration - remaining_when_paused).
                                    # But we didn't save remaining_when_paused.
                                    # Simplest reliable fix: Reset timer to full 90s only if it was expired?
                                    # Actually, if we just set active=True, the code below calculates `elapsed = now - timer_start`.
                                    # If we paused 10 mins ago, `elapsed` will be huge, and time_remaining will be 0.
                                    # So player will be sold instantly upon resume!
                                    # FIX: Update timer_start so that `remaining` is what it should be.
                                    # For now, let's just RESET timer to 90s for FAIRNESS upon resume?
                                    # Or assume admin wants to continue.
                                    # Let's simple reset timer to current time so they have full time again?
                                    # Or better: "Resume" means "Continue".
                                    # Let's update timer_start to `datetime.now()` to give fresh 90s (fair for network issues).
                                    existing_auction['timer_start'] = datetime.now().isoformat()
                                    
                                    room['live_auction'] = existing_auction
                                    save_auction_data(auction_data)
                                    st.rerun()
                                
                                st.write("OR")
                                if st.button("Start Fresh (⚠️ Discards paused state)"):
                                     room['live_auction'] = {
                                        'active': True,
                                        'current_team': selected_team,
                                        'player_queue': [p['name'] for p in team_players],
                                        'current_player': team_players[0]['name'] if team_players else None,
                                        'current_player_role': team_players[0].get('role', 'Unknown') if team_players else None,
                                        'current_bid': 0,
                                        'current_bidder': None,
                                        'timer_start': datetime.now().isoformat(),
                                        'timer_duration': 90,
                                        'opted_out': [],
                                        'auction_started_at': datetime.now().isoformat()
                                    }
                                     save_auction_data(auction_data)
                                     st.rerun()
                            
                            elif st.button("🚀 Start Auction for " + selected_team, type="primary"):
                                # Initialize live auction
                                room['live_auction'] = {
                                    'active': True,
                                    'current_team': selected_team,
                                    'player_queue': [p['name'] for p in team_players],
                                    'current_player': team_players[0]['name'] if team_players else None,
                                    'current_player_role': team_players[0].get('role', 'Unknown') if team_players else None,
                                    'current_bid': 0,
                                    'current_bidder': None,
                                    'timer_start': datetime.now().isoformat(),
                                    'timer_duration': 90,  # Updated to 90 seconds
                                    'opted_out': [], # List of participants who opted out
                                    'auction_started_at': datetime.now().isoformat()
                                }
                                save_auction_data(auction_data)
                                st.rerun()
                        else:
                            st.success("All players have been drafted!")
                    else:
                        # === MEMBER: WAITING SCREEN ===
                        st.markdown("### ⏳ Waiting for Auction...")
                        st.info("The admin has not started the live auction yet. Please wait.")
                        
                        # Show Live Dashboard even while waiting
                        with st.expander("📊 Live Auction Dashboard (Budgets & Squads)", expanded=True):
                             dash_data = []
                             for p in room['participants']:
                                 dash_data.append({
                                     "Participant": p['name'],
                                     "Budget": f"{p['budget']}M",
                                     "Est. Max Bid": f"{p['budget']}M" if p['budget'] > 0 else "0M",
                                     "Squad Size": len(p['squad']),
                                     "Squad Value": f"{sum(x['buy_price'] for x in p['squad'])}M"
                                 })
                             st.dataframe(pd.DataFrame(dash_data), hide_index=True)

                        st.json({"status": "waiting", "admin": room['admin'], "time": datetime.now().strftime("%H:%M:%S")})
                        
                        # Auto-refresh to check for start
                        import time
                        time.sleep(2)
                        st.rerun()
                
                else:
                    # === ACTIVE AUCTION MODE ===
                    current_player = live_auction.get('current_player')
                    
                    # === LIVE DASHBOARD (Top/Sidebar) ===
                    with st.expander("📊 Live Auction Dashboard (Budgets & Squads)", expanded=True):
                         # Create a dataframe for display
                         dash_data = []
                         for p in room['participants']:
                             dash_data.append({
                                 "Participant": p['name'],
                                 "Budget": f"{p['budget']}M",
                                 "Est. Max Bid": f"{p['budget']}M" if p['budget'] > 0 else "0M", # Placeholder for max calc logic
                                 "Squad Size": len(p['squad']),
                                 "Squad Value": f"{sum(x['buy_price'] for x in p['squad'])}M"
                             })
                         st.dataframe(pd.DataFrame(dash_data), hide_index=True)

                    current_role = live_auction.get('current_player_role', 'Unknown')
                    current_team = live_auction.get('current_team')
                    current_bid = live_auction.get('current_bid', 0)

                    current_bidder = live_auction.get('current_bidder')
                    timer_start = datetime.fromisoformat(live_auction.get('timer_start', datetime.now().isoformat()))
                    timer_duration = live_auction.get('timer_duration', 90)
                    opted_out = live_auction.get('opted_out', [])
                    
                    # Calculate time remaining
                    elapsed = (datetime.now() - timer_start).total_seconds()
                    time_remaining = max(0, timer_duration - elapsed)
                    
                    # Display auction header
                    st.markdown(f"### 🏏 Auctioning: **{current_team}**")
                    
                    # Current player display
                    col1, col2, col3 = st.columns([2, 1, 1])
                    with col1:
                        st.markdown(f"## 👤 {current_player}")
                        st.markdown(f"**Role:** {current_role}")
                        if opted_out:
                            total_participants = len(room['participants'])
                            st.caption(f"🚫 Opted Out: {len(opted_out)}/{total_participants}")
                    with col2:
                        if current_bidder:
                            st.metric("💰 Current Bid", f"{current_bid}M")
                            st.caption(f"By: {current_bidder}")
                        else:
                            st.metric("💰 Starting Bid", "5M")
                            st.caption("No bids yet")
                    with col3:
                        # Timer display
                        if time_remaining > 5:
                            st.metric("⏱️ Time", f"{int(time_remaining)}s")
                        elif time_remaining > 0:
                            st.metric("⏱️ Time", f"{int(time_remaining)}s", delta="Going...", delta_color="inverse")
                        else:
                            st.metric("⏱️ Time", "0s", delta="SOLD!")
                    
                    # Progress bar for timer
                    st.progress(time_remaining / timer_duration)
                    
                    # Auto-Sell / Auto-Pass Logic
                    # If timer expired OR (everyone else opted out and there is a bidder)
                    active_participants_count = len([p for p in room['participants'] if p['name'] not in opted_out])
                    # If current bidder exists, they are active but we don't count them as "others"
                    others_active = active_participants_count - (1 if current_bidder and current_bidder not in opted_out else 0)
                    
                    should_autosell = (time_remaining <= 0 and current_bidder) or (current_bidder and others_active == 0)
                    should_autopass = (time_remaining <= 0 and not current_bidder) or (not current_bidder and active_participants_count == 0)
                    
                    # Execute Auto-Sell/Pass (Only one person needs to trigger this to save state)
                    # We use a button for manual confirmation OR just run it if condition met
                    # To prevent loop, we check if we already processed this player? 
                    # No, we just act and change state.
                    
                    # Bidding section (for participants)
                    st.markdown("---")
                    
                    # Determine current user's participant status
                    my_name = st.session_state.get('logged_in_user', 'Unknown')
                    my_participant = next((p for p in room['participants'] if p.get('user') == my_name or p['name'] == my_name), None)
                    is_my_turn = my_participant and my_participant['name'] not in opted_out and my_participant['name'] != current_bidder
                    
                    if not should_autosell and not should_autopass:
                        st.markdown("### 🎯 Place Your Bid")
                        
                        col1, col2, col3 = st.columns([1, 1, 1])
                        with col1:
                            # Restrict bidder selection to self if not admin
                            if is_admin:
                                bidder_options = [p['name'] for p in room['participants'] if p['name'] not in opted_out]
                                default_idx = 0
                                if my_participant and my_participant['name'] in bidder_options:
                                    default_idx = bidder_options.index(my_participant['name'])
                                bidder_name = st.selectbox("Bidder", bidder_options, index=default_idx, key=f"bid_select_{current_player}")
                            else:
                                if my_participant and my_participant['name'] not in opted_out:
                                    bidder_name = my_participant['name']
                                    st.text_input("Bidder", value=bidder_name, disabled=True, key=f"bid_select_{current_player}")
                                else:
                                    bidder_name = None
                                    st.warning("You are not an active participant for this player")
                            
                            bidder = next((p for p in room['participants'] if p['name'] == bidder_name), None)
                        
                        with col2:
                            min_bid = max(5, current_bid + 5) if current_bid >= 50 else max(5, current_bid + 1)
                            max_bid_allowed = bidder.get('budget', 0) if bidder else 0
                            
                            if max_bid_allowed >= min_bid:
                                bid_amount = st.number_input(
                                    f"Bid (Min: {min_bid}M)", 
                                    min_value=min_bid, 
                                    max_value=max_bid_allowed,
                                    value=min_bid,
                                    step=5 if min_bid >= 50 else 1,
                                    key=f"bid_input_{current_player}"
                                )
                            else:
                                st.error(f"Low Budget")
                                bid_amount = 0
                        
                        with col3:
                            # Bid Button
                            if st.button("🔨 BID!", type="primary", disabled=bid_amount==0, key=f"bid_btn_{current_player}"):
                                live_auction['current_bid'] = bid_amount
                                live_auction['current_bidder'] = bidder_name
                                live_auction['timer_start'] = datetime.now().isoformat()  # Reset timer
                                # IMPORTANT: Reset opt-outs? Usually yes if price changes, but let's keep it sticky for speed. 
                                # If sticky: No reset. If lenient: live_auction['opted_out'] = []
                                # User asked for "opt out of bidding for a player". Usually implies permanent for that player.
                                room['live_auction'] = live_auction
                                save_auction_data(auction_data)
                                st.rerun()
                            
                            # Opt Out / Status
                            if my_participant and my_participant['name'] == current_bidder:
                                st.success("👑 You hold the highest bid")
                            elif is_my_turn:
                                if st.button("❌ Opt Out", key=f"optout_btn_{current_player}"):
                                    live_auction.setdefault('opted_out', []).append(my_participant['name'])
                                    room['live_auction'] = live_auction
                                    save_auction_data(auction_data)
                                    st.rerun()

                    # Handle Sale / Unsold
                    if should_autosell:
                        st.success(f"🎉 **SOLD!** {current_player} to **{current_bidder}** for **{current_bid}M**")
                        # Auto-execute after brief delay or showing the message
                        # We need a way to show the success message before switching.
                        # We can use a short sleep then execute.
                        
                        # EXECUTE SALE
                        winner = next((p for p in room['participants'] if p['name'] == current_bidder), None)
                        if winner:
                            winner['squad'].append({
                                'name': current_player,
                                'role': current_role,
                                'buy_price': current_bid
                            })
                            winner['budget'] -= current_bid
                            
                            room.setdefault('auction_log', []).append({
                                'player': current_player,
                                'buyer': current_bidder,
                                'price': current_bid,
                                'time': datetime.now().isoformat()
                            })
                            
                            # Move to next
                            queue = live_auction.get('player_queue', [])
                            if current_player in queue:
                                queue.remove(current_player)
                            
                            if queue:
                                next_player = queue[0]
                                live_auction['current_player'] = next_player
                                live_auction['current_player_role'] = player_role_lookup.get(next_player, 'Unknown')
                                live_auction['current_bid'] = 0
                                live_auction['current_bidder'] = None
                                live_auction['timer_start'] = datetime.now().isoformat()
                                live_auction['opted_out'] = []
                                live_auction['player_queue'] = queue
                            else:
                                live_auction['active'] = False
                                st.balloons()
                            
                            room['live_auction'] = live_auction
                            save_auction_data(auction_data)
                            import time
                            time.sleep(3) # Show result for 3s then next
                            st.rerun()

                    elif should_autopass:
                        st.warning(f"⏸️ **UNSOLD** - {current_player}")
                        
                        # EXECUTE UNSOLD
                        room.setdefault('unsold_players', []).append(current_player)
                        
                        queue = live_auction.get('player_queue', [])
                        if current_player in queue:
                            queue.remove(current_player)
                            
                        if queue:
                            next_player = queue[0]
                            live_auction['current_player'] = next_player
                            live_auction['current_player_role'] = player_role_lookup.get(next_player, 'Unknown')
                            live_auction['current_bid'] = 0
                            live_auction['current_bidder'] = None
                            live_auction['timer_start'] = datetime.now().isoformat()
                            live_auction['opted_out'] = []
                            live_auction['player_queue'] = queue
                        else:
                            live_auction['active'] = False
                        
                        room['live_auction'] = live_auction
                        save_auction_data(auction_data)
                        import time
                        time.sleep(3)
                        st.rerun()
                    
                    # Admin controls (Pause)
                    if is_admin:
                        st.divider()
                        with st.expander("🔧 Admin Controls"):
                            if st.button("⏸️ Pause Auction"):
                                live_auction['active'] = False
                                room['live_auction'] = live_auction
                                save_auction_data(auction_data)
                                st.rerun()
                    
                    # Auto-refresh loop for everyone
                    if not should_autosell and not should_autopass:
                        import time
                        time.sleep(1)
                        st.rerun()
        
        # ================ TAB 1: BIG AUCTION (Manual) ================
        with auction_tabs[1]:
            st.subheader("📋 Manage Squads (Big Auction)")
            
            if room.get('big_auction_complete'):
                st.success("✅ Big Auction is complete! Use 'Open Bidding' tab to bid on unsold players.")
            
            if not room['participants']:
                if is_admin:
                    st.info("No participants yet. Add some above!")
                else:
                    st.info("No participants yet. Ask the admin to add participants.")
            else:
                participant_names = [p['name'] for p in room['participants']]
                selected_participant = st.selectbox("Select Participant", participant_names)
                participant = next((p for p in room['participants'] if p['name'] == selected_participant), None)
                
                if participant:
                    # Ensure participant has budget field (migration for old data)
                    if 'budget' not in participant:
                        participant['budget'] = 350
                        save_auction_data(auction_data)
                    
                    col1, col2 = st.columns([2, 1])
                    
                    with col1:
                        # Budget and Squad Info
                        budget_col1, budget_col2 = st.columns(2)
                        with budget_col1:
                            st.metric("💰 Budget Remaining", f"{participant['budget']}M")
                        with budget_col2:
                            st.metric("👥 Squad Size", f"{len(participant['squad'])}/19")
                        
                        if participant.get('ir_player'):
                            st.warning(f"🚑 Injury Reserve: {participant['ir_player']}")
                        
                        # Add Player to Squad - BIG AUCTION STYLE
                        st.markdown("---")
                        st.markdown("### ➕ Add Player (Big Auction)")
                        
                        # Filter out players already in any squad
                        all_drafted_players = []
                        for p in room['participants']:
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
                                
                                # Buy Price Input
                                max_bid = participant['budget']
                                buy_price = st.number_input(
                                    "Buy Price (M)", 
                                    min_value=5, 
                                    max_value=max(5, int(max_bid)), 
                                    value=5, 
                                    step=1,
                                    help="Minimum 5M. Enter the auction winning bid."
                                )
                                
                                if st.button("💰 Buy Player", type="primary"):
                                    if len(participant['squad']) >= 19:
                                        st.error("Squad is full (19 players max)!")
                                    elif buy_price > participant['budget']:
                                        st.error(f"Insufficient budget! You have {participant['budget']}M.")
                                    else:
                                        # Add player with buy_price
                                        participant['squad'].append({
                                            'name': selected_player, 
                                            'role': role,
                                            'buy_price': buy_price
                                        })
                                        # Deduct budget
                                        participant['budget'] -= buy_price
                                        # Log the auction
                                        room.setdefault('auction_log', []).append({
                                            'player': selected_player,
                                            'buyer': participant['name'],
                                            'price': buy_price,
                                            'time': datetime.now().isoformat()
                                        })
                                        save_auction_data(auction_data)
                                        st.success(f"✅ {selected_player} bought for {buy_price}M by {selected_participant}!")
                                        st.rerun()
                        else:
                            st.warning("All players have been drafted!")
                        
                        # Reset Squad Button (Admin Only)
                        if is_admin:
                            st.divider()
                            if st.button(f"🗑️ Reset {selected_participant}'s Squad", type="secondary"):
                                participant['squad'] = []
                                participant['ir_player'] = None
                                participant['budget'] = 350  # Restore full budget
                                save_auction_data(auction_data)
                                st.success(f"Reset {selected_participant}'s squad! Budget restored to 350M.")
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
                            
                            # Release Player (dynamic rules based on gameweek)
                            st.divider()
                            
                            # Calculate current gameweek (based on locked gameweeks)
                            locked_gws = list(room.get('gameweek_squads', {}).keys())
                            current_gw = max([int(gw) for gw in locked_gws]) if locked_gws else 0
                            
                            # Check if participant has used their paid release this GW
                            paid_releases = participant.get('paid_releases', {})
                            used_paid_this_gw = paid_releases.get(str(current_gw), False) if current_gw > 0 else False
                            
                            # Get knocked out teams
                            knocked_out_teams = set(room.get('knocked_out_teams', []))
                            
                            # Create country lookup from players_db
                            player_country_lookup = {p['name']: p.get('country', 'Unknown') for p in players_db}
                            
                            remove_options = [p['name'] for p in participant['squad']]
                            player_to_remove = st.selectbox("Select Player to Release", remove_options, key="remove_player")
                            
                            # Find the player to get their buy_price and check if from knocked-out team
                            player_obj = next((p for p in participant['squad'] if p['name'] == player_to_remove), None)
                            player_country = player_country_lookup.get(player_to_remove, 'Unknown')
                            is_knocked_out_team = player_country in knocked_out_teams
                            
                            # Display release rules based on situation
                            if current_gw == 0:
                                release_type = "unlimited"  # Before GW1 starts
                                st.markdown("**🔄 Release Player (50% return - Unlimited)**")
                                st.caption("Before GW1: Release any number of players for 50% refund")
                            elif is_knocked_out_team and current_gw >= 5:
                                # Super 8s+ and player from knocked-out team
                                release_type = "knockout_free"
                                st.markdown(f"**🔄 Release Player (Knocked-Out Team - FREE 50%)**")
                                st.success(f"🚫 {player_country} is knocked out! You get 50% refund without using your paid release.")
                            elif not used_paid_this_gw:
                                release_type = "paid"
                                st.markdown(f"**🔄 Release Player (GW{current_gw} - 1 Paid Release Available)**")
                                st.caption("You have 1 paid (50%) release remaining this gameweek")
                            else:
                                release_type = "free"
                                st.markdown(f"**🔄 Release Player (GW{current_gw} - Free Only)**")
                                st.warning("⚠️ You've used your paid release. Additional releases are FREE (0M).")
                            
                            # Calculate refund based on release type
                            if release_type in ["unlimited", "paid", "knockout_free"]:
                                refund_amount = player_obj.get('buy_price', 0) // 2 if player_obj else 0
                            else:
                                refund_amount = 0  # Free release
                            
                            st.caption(f"Player: **{player_to_remove}** ({player_country})")
                            st.caption(f"Releasing will refund: **{refund_amount}M**" + 
                                      (" (50% of buy price)" if release_type != "free" else " (free release)"))
                            
                            if st.button("🔓 Release Player"):
                                participant['squad'] = [p for p in participant['squad'] if p['name'] != player_to_remove]
                                participant['budget'] += refund_amount
                                if participant.get('ir_player') == player_to_remove:
                                    participant['ir_player'] = None
                                # Add to unsold pool for bidding
                                room.setdefault('unsold_players', []).append(player_to_remove)
                                
                                # Mark paid release as used (only if NOT knockout_free)
                                if release_type == "paid":
                                    participant.setdefault('paid_releases', {})[str(current_gw)] = True
                                
                                save_auction_data(auction_data)
                                st.success(f"Released {player_to_remove}! Refunded {refund_amount}M.")
                                st.rerun()
                        else:
                            st.info("No players in squad yet.")
        
        # --- Participants Overview ---
        st.divider()
        st.subheader("📊 All Participants")
        if room['participants']:
            overview_data = []
            for p in room['participants']:
                squad_value = sum(pl.get('buy_price', 0) for pl in p['squad'])
                overview_data.append({
                    "Name": p['name'],
                    "Budget": f"{p.get('budget', 350)}M",
                    "Squad Value": f"{squad_value}M",
                    "Squad Size": f"{len(p['squad'])}/19",
                    "IR": p.get('ir_player') or "-"
                })
            st.dataframe(pd.DataFrame(overview_data), use_container_width=True, hide_index=True)
            
            # Delete Participant Button (Admin Only)
            if is_admin:
                st.divider()
                st.subheader("🗑️ Delete Participant")
                del_participant = st.selectbox("Select Participant to Delete", [p['name'] for p in room['participants']], key="del_participant")
                if st.button("Delete Participant", type="secondary"):
                    room['participants'] = [p for p in room['participants'] if p['name'] != del_participant]
                    save_auction_data(auction_data)
                    st.success(f"Deleted {del_participant}!")
                    st.rerun()
        
        # Show room members
        st.divider()
        st.subheader("👥 Room Members")
        members_df = pd.DataFrame([{"Member": m, "Role": "Admin" if m == room['admin'] else "Member"} for m in room['members']])
        st.dataframe(members_df, use_container_width=True, hide_index=True)
        
        # ================ TAB 2: OPEN BIDDING ================
        with auction_tabs[2]:
            st.subheader("💰 Open Bidding (Post-Auction)")
            
            if not room.get('big_auction_complete'):
                st.warning("⏳ Open Bidding will start after the Big Auction is complete. Admin must check 'Big Auction Complete' in sidebar.")
            else:
                st.info("📜 **Rules:** Min bid 5M. Over 50M: +5M increments. Hold for 24 hours to win (or until deadline).")
                
                # Admin: Set Bidding Deadline
                if is_admin:
                    with st.expander("⏰ Set Bidding Deadline (Admin)"):
                        deadline_str = room.get('bidding_deadline', '')
                        if deadline_str:
                            current_deadline = datetime.fromisoformat(deadline_str)
                            st.info(f"Current deadline: {current_deadline.strftime('%b %d, %Y %H:%M')}")
                        
                        new_deadline_date = st.date_input("Deadline Date")
                        new_deadline_time = st.time_input("Deadline Time")
                        
                        if st.button("Set Deadline"):
                            new_deadline = datetime.combine(new_deadline_date, new_deadline_time)
                            room['bidding_deadline'] = new_deadline.isoformat()
                            save_auction_data(auction_data)
                            st.success(f"Deadline set to {new_deadline.strftime('%b %d, %Y %H:%M')}")
                            st.rerun()
                
                # Show countdown to deadline
                now = datetime.now()
                deadline_str = room.get('bidding_deadline')
                if deadline_str:
                    deadline = datetime.fromisoformat(deadline_str)
                    if now < deadline:
                        time_left = deadline - now
                        hours_left = time_left.total_seconds() / 3600
                        st.warning(f"⏰ **Bidding closes in {hours_left:.1f} hours** ({deadline.strftime('%b %d, %H:%M')})")
                    else:
                        st.error("⏰ **Bidding deadline has passed!** All active bids will be awarded.")
                
                # Process expired bids (auto-award to winners)
                active_bids = room.get('active_bids', [])
                awarded_bids = []
                
                for bid in active_bids:
                    expires = datetime.fromisoformat(bid['expires'])
                    # Award if: bid expired OR deadline passed
                    should_award = now >= expires
                    if deadline_str and now >= datetime.fromisoformat(deadline_str):
                        should_award = True  # Deadline passed, award all bids
                    
                    if should_award:
                        # Award the player to the bidder
                        bidder_participant = next((p for p in room['participants'] if p['name'] == bid['bidder']), None)
                        if bidder_participant and bid['amount'] <= bidder_participant.get('budget', 0):
                            bidder_participant['squad'].append({
                                'name': bid['player'],
                                'role': player_role_lookup.get(bid['player'], 'Unknown'),
                                'buy_price': bid['amount']
                            })
                            bidder_participant['budget'] -= bid['amount']
                            awarded_bids.append(bid)
                            # Remove from unsold
                            if bid['player'] in room.get('unsold_players', []):
                                room['unsold_players'].remove(bid['player'])
                
                # Remove awarded bids
                for ab in awarded_bids:
                    active_bids.remove(ab)
                    st.success(f"🎉 {ab['player']} awarded to {ab['bidder']} for {ab['amount']}M!")
                
                room['active_bids'] = active_bids
                if awarded_bids:
                    save_auction_data(auction_data)
                
                # Show current active bids
                st.markdown("### 📋 Active Bids")
                if active_bids:
                    bids_data = []
                    for bid in active_bids:
                        expires = datetime.fromisoformat(bid['expires'])
                        time_left = expires - now
                        hours_left = max(0, time_left.total_seconds() / 3600)
                        bids_data.append({
                            "Player": bid['player'],
                            "Current Bid": f"{bid['amount']}M",
                            "Bidder": bid['bidder'],
                            "Time Left": f"{hours_left:.1f} hours",
                            "Expires": expires.strftime("%b %d, %H:%M")
                        })
                    st.dataframe(pd.DataFrame(bids_data), use_container_width=True, hide_index=True)
                else:
                    st.info("No active bids. Place a bid on an unsold player below!")
                
                # Get unsold players (players not in any squad and not being bid on)
                all_drafted = []
                for p in room['participants']:
                    all_drafted.extend([pl['name'] for pl in p['squad']])
                being_bid_on = [b['player'] for b in active_bids]
                
                unsold_players = room.get('unsold_players', [])
                # Add players that went unsold (not in any squad)
                for name in player_names:
                    if name not in all_drafted and name not in unsold_players:
                        unsold_players.append(name)
                room['unsold_players'] = unsold_players
                
                biddable_players = [p for p in unsold_players if p not in being_bid_on]
                
                # Place a new bid
                st.markdown("### 🆕 Place New Bid")
                
                # Get current user's participant profile
                current_participant = next((p for p in room['participants'] if p['name'] == user), None)
                if not current_participant:
                    # Check if user is in any participant's name loosely (for flexibility)
                    participant_options = [p['name'] for p in room['participants']]
                    if participant_options:
                        selected_bidder = st.selectbox("Select Your Name", participant_options, key="bidder_select")
                        current_participant = next((p for p in room['participants'] if p['name'] == selected_bidder), None)
                    else:
                        st.warning("No participants yet. Admin needs to add you first.")
                
                if current_participant:
                    st.metric("Your Budget", f"{current_participant.get('budget', 0)}M")
                    
                    if biddable_players:
                        bid_player = st.selectbox(
                            "Select Player to Bid On",
                            [""] + biddable_players,
                            format_func=lambda x: f"{x} ({player_role_lookup.get(x, 'Unknown')})" if x else "Select a player..."
                        )
                        
                        if bid_player:
                            # Check if there's an existing bid
                            existing_bid = next((b for b in active_bids if b['player'] == bid_player), None)
                            min_bid = 5
                            if existing_bid:
                                if existing_bid['amount'] >= 50:
                                    min_bid = existing_bid['amount'] + 5
                                else:
                                    min_bid = existing_bid['amount'] + 1
                            
                            bid_amount = st.number_input(
                                f"Bid Amount (Min: {min_bid}M)",
                                min_value=min_bid,
                                max_value=int(current_participant.get('budget', 0)),
                                value=min_bid,
                                step=5 if min_bid >= 50 else 1
                            )
                            
                            if st.button("🎯 Place Bid", type="primary"):
                                if bid_amount > current_participant.get('budget', 0):
                                    st.error("Insufficient budget!")
                                else:
                                    # Remove old bid if exists
                                    room['active_bids'] = [b for b in room['active_bids'] if b['player'] != bid_player]
                                    # Add new bid with 24-hour expiry
                                    room['active_bids'].append({
                                        'player': bid_player,
                                        'amount': bid_amount,
                                        'bidder': current_participant['name'],
                                        'bid_time': now.isoformat(),
                                        'expires': (now + timedelta(hours=24)).isoformat()
                                    })
                                    save_auction_data(auction_data)
                                    st.success(f"Bid placed! {bid_player} at {bid_amount}M. Expires in 24 hours.")
                                    st.rerun()
                    else:
                        st.info("No players available for bidding. All have been drafted or have active bids.")
        
        # ================ TAB 3: TRADING ================
        with auction_tabs[3]:
            st.subheader("🔄 Trading")
            
            if not room.get('big_auction_complete'):
                st.warning("⏳ Trading will open after the Big Auction is complete.")
            else:
                st.info("""
                **Trading Rules:**
                - **Transfers**: Sell a player to another participant
                - **Exchanges**: Swap players between two participants
                - **Loans**: Temporary player transfer for 1 gameweek
                - **No donations** (cash for nothing)
                
                Trading closes 30 min after bidding closes each gameweek.
                """)
                
                st.markdown("### 📤 Propose a Trade")
                
                # Get current participant
                participant_options = [p['name'] for p in room['participants']]
                if len(participant_options) >= 2:
                    col1, col2 = st.columns(2)
                    with col1:
                        from_participant = st.selectbox("From Participant", participant_options, key="trade_from")
                    with col2:
                        to_options = [p for p in participant_options if p != from_participant]
                        to_participant = st.selectbox("To Participant", to_options, key="trade_to")
                    
                    from_p = next((p for p in room['participants'] if p['name'] == from_participant), None)
                    to_p = next((p for p in room['participants'] if p['name'] == to_participant), None)
                    
                    if from_p and to_p:
                        trade_type = st.radio("Trade Type", ["Transfer (Sell)", "Exchange", "Loan (1 GW)"], horizontal=True)
                        
                        if trade_type == "Transfer (Sell)":
                            if from_p['squad']:
                                player_to_sell = st.selectbox(
                                    f"Player from {from_participant}",
                                    [p['name'] for p in from_p['squad']]
                                )
                                sell_price = st.number_input("Sell Price (M)", min_value=1, value=10)
                                
                                if st.button("📝 Record Transfer"):
                                    player_obj = next((p for p in from_p['squad'] if p['name'] == player_to_sell), None)
                                    if player_obj and sell_price <= to_p.get('budget', 0):
                                        # Move player
                                        from_p['squad'].remove(player_obj)
                                        player_obj['buy_price'] = sell_price
                                        to_p['squad'].append(player_obj)
                                        # Transfer money
                                        from_p['budget'] += sell_price
                                        to_p['budget'] -= sell_price
                                        save_auction_data(auction_data)
                                        st.success(f"Transfer complete! {player_to_sell} to {to_participant} for {sell_price}M")
                                        st.rerun()
                                    else:
                                        st.error("Transfer failed. Check budget.")
                            else:
                                st.warning(f"{from_participant} has no players to sell.")
                        
                        elif trade_type == "Exchange":
                            if from_p['squad'] and to_p['squad']:
                                excol1, excol2 = st.columns(2)
                                with excol1:
                                    player1 = st.selectbox(f"Player from {from_participant}", [p['name'] for p in from_p['squad']], key="ex1")
                                with excol2:
                                    player2 = st.selectbox(f"Player from {to_participant}", [p['name'] for p in to_p['squad']], key="ex2")
                                
                                # Cash component for exchange
                                st.markdown("**Optional: Add Cash to Balance**")
                                cash_direction = st.radio(
                                    "Who pays extra?", 
                                    ["No cash involved", f"{from_participant} pays extra", f"{to_participant} pays extra"],
                                    horizontal=True
                                )
                                cash_amount = 0
                                if cash_direction != "No cash involved":
                                    cash_amount = st.number_input("Cash Amount (M)", min_value=1, max_value=100, value=5)
                                
                                if st.button("📝 Record Exchange"):
                                    p1_obj = next((p for p in from_p['squad'] if p['name'] == player1), None)
                                    p2_obj = next((p for p in to_p['squad'] if p['name'] == player2), None)
                                    
                                    # Check budget if cash involved
                                    can_proceed = True
                                    if cash_direction == f"{from_participant} pays extra":
                                        if from_p.get('budget', 0) < cash_amount:
                                            st.error(f"{from_participant} doesn't have {cash_amount}M!")
                                            can_proceed = False
                                    elif cash_direction == f"{to_participant} pays extra":
                                        if to_p.get('budget', 0) < cash_amount:
                                            st.error(f"{to_participant} doesn't have {cash_amount}M!")
                                            can_proceed = False
                                    
                                    if p1_obj and p2_obj and can_proceed:
                                        # Swap players
                                        from_p['squad'].remove(p1_obj)
                                        to_p['squad'].remove(p2_obj)
                                        from_p['squad'].append(p2_obj)
                                        to_p['squad'].append(p1_obj)
                                        
                                        # Handle cash component
                                        if cash_direction == f"{from_participant} pays extra":
                                            from_p['budget'] -= cash_amount
                                            to_p['budget'] += cash_amount
                                        elif cash_direction == f"{to_participant} pays extra":
                                            to_p['budget'] -= cash_amount
                                            from_p['budget'] += cash_amount
                                        
                                        save_auction_data(auction_data)
                                        cash_msg = f" + {cash_amount}M" if cash_amount > 0 else ""
                                        st.success(f"Exchange complete! {player1}{cash_msg if cash_direction == f'{from_participant} pays extra' else ''} ↔ {player2}{cash_msg if cash_direction == f'{to_participant} pays extra' else ''}")
                                        st.rerun()
                            else:
                                st.warning("Both participants need players for an exchange.")
                        
                        elif trade_type == "Loan (1 GW)":
                            st.markdown("**Loan a player for 1 Gameweek**")
                            if from_p['squad']:
                                player_to_loan = st.selectbox(
                                    f"Player to loan from {from_participant}",
                                    [p['name'] for p in from_p['squad']]
                                )
                                loan_fee = st.number_input("Loan Fee (M)", min_value=0, max_value=50, value=5)
                                
                                # Calculate which GW this loan is for
                                locked_gws = list(room.get('gameweek_squads', {}).keys())
                                current_gw = max([int(gw) for gw in locked_gws]) if locked_gws else 0
                                next_gw = current_gw + 1
                                
                                st.info(f"This loan will be for GW{next_gw}. Player returns after that gameweek.")
                                
                                if st.button("📝 Record Loan"):
                                    if loan_fee > to_p.get('budget', 0):
                                        st.error(f"{to_participant} doesn't have {loan_fee}M for loan fee!")
                                    else:
                                        player_obj = next((p for p in from_p['squad'] if p['name'] == player_to_loan), None)
                                        if player_obj:
                                            # Create loan record
                                            room.setdefault('active_loans', []).append({
                                                'player': player_to_loan,
                                                'from': from_participant,
                                                'to': to_participant,
                                                'fee': loan_fee,
                                                'gameweek': str(next_gw),
                                                'original_buy_price': player_obj.get('buy_price', 0),
                                                'created_at': datetime.now().isoformat()
                                            })
                                            
                                            # Move player temporarily
                                            from_p['squad'].remove(player_obj)
                                            to_p['squad'].append({
                                                'name': player_to_loan,
                                                'role': player_obj['role'],
                                                'buy_price': player_obj.get('buy_price', 0),
                                                'on_loan': True,
                                                'loan_from': from_participant
                                            })
                                            
                                            # Transfer loan fee
                                            from_p['budget'] += loan_fee
                                            to_p['budget'] -= loan_fee
                                            
                                            save_auction_data(auction_data)
                                            st.success(f"Loan complete! {player_to_loan} loaned to {to_participant} for GW{next_gw} ({loan_fee}M fee)")
                                            st.rerun()
                            else:
                                st.warning(f"{from_participant} has no players to loan.")
                else:
                    st.warning("Need at least 2 participants for trading.")
                
                # === VIEW OTHER SQUADS ===
                st.divider()
                st.markdown("### 👀 View Participant Squads")
                
                view_participant = st.selectbox(
                    "Select participant to view squad",
                    [p['name'] for p in room['participants']],
                    key="view_squad_select"
                )
                
                view_p = next((p for p in room['participants'] if p['name'] == view_participant), None)
                if view_p and view_p['squad']:
                    squad_df = pd.DataFrame(view_p['squad'])
                    st.dataframe(squad_df, use_container_width=True, hide_index=True)
                    st.caption(f"Budget: {view_p.get('budget', 350)}M | IR: {view_p.get('ir_player', 'None')}")
                else:
                    st.info(f"{view_participant} has no players yet.")
                
                # === TRADE PROPOSALS ===
                st.divider()
                st.markdown("### 📩 Trade Proposals")
                
                # Show my proposals (incoming and outgoing)
                pending_trades = room.get('pending_trades', [])
                my_name = st.session_state.get('user', 'Unknown')
                
                # Get participant name for current user (if they're a participant)
                my_participant = next((p['name'] for p in room['participants'] 
                                      if p.get('user') == my_name or p['name'] == my_name), None)
                
                if not my_participant:
                    st.info("You need to be a participant to send or receive trade proposals.")
                else:
                    # Incoming proposals
                    my_incoming = [t for t in pending_trades if t['to'] == my_participant and t['status'] == 'pending']
                    if my_incoming:
                        st.markdown("**📥 Incoming Proposals**")
                        for i, trade in enumerate(my_incoming):
                            with st.expander(f"From {trade['from']}: {trade.get('from_players', [])} ↔ {trade.get('to_players', [])}"):
                                cash_note = ""
                                if trade.get('cash_from_to', 0) > 0:
                                    cash_note = f" + {trade['cash_from_to']}M from {trade['from']}"
                                elif trade.get('cash_from_to', 0) < 0:
                                    cash_note = f" + {abs(trade['cash_from_to'])}M from you"
                                
                                st.write(f"**Offer:** {', '.join(trade.get('from_players', []))}")
                                st.write(f"**Wants:** {', '.join(trade.get('to_players', []))}")
                                if cash_note:
                                    st.write(f"**Cash:** {cash_note}")
                                
                                col1, col2, col3 = st.columns(3)
                                with col1:
                                    if st.button("✅ Accept", key=f"accept_{trade['id']}"):
                                        # Execute the trade
                                        from_p = next((p for p in room['participants'] if p['name'] == trade['from']), None)
                                        to_p = next((p for p in room['participants'] if p['name'] == trade['to']), None)
                                        
                                        if from_p and to_p:
                                            # Move players
                                            for pname in trade.get('from_players', []):
                                                pobj = next((p for p in from_p['squad'] if p['name'] == pname), None)
                                                if pobj:
                                                    from_p['squad'].remove(pobj)
                                                    to_p['squad'].append(pobj)
                                            
                                            for pname in trade.get('to_players', []):
                                                pobj = next((p for p in to_p['squad'] if p['name'] == pname), None)
                                                if pobj:
                                                    to_p['squad'].remove(pobj)
                                                    from_p['squad'].append(pobj)
                                            
                                            # Handle cash
                                            cash = trade.get('cash_from_to', 0)
                                            if cash > 0:
                                                from_p['budget'] -= cash
                                                to_p['budget'] += cash
                                            elif cash < 0:
                                                to_p['budget'] += cash  # cash is negative
                                                from_p['budget'] -= cash
                                            
                                            trade['status'] = 'accepted'
                                            save_auction_data(auction_data)
                                            st.success("Trade accepted and executed!")
                                            st.rerun()
                                
                                with col2:
                                    if st.button("❌ Reject", key=f"reject_{trade['id']}"):
                                        trade['status'] = 'rejected'
                                        save_auction_data(auction_data)
                                        st.info("Trade rejected.")
                                        st.rerun()
                                
                                with col3:
                                    if st.button("🔄 Counter", key=f"counter_{trade['id']}"):
                                        st.session_state['counter_trade'] = trade['id']
                    
                    # Outgoing proposals
                    my_outgoing = [t for t in pending_trades if t['from'] == my_participant and t['status'] == 'pending']
                    if my_outgoing:
                        st.markdown("**📤 Your Outgoing Proposals**")
                        for trade in my_outgoing:
                            st.write(f"To {trade['to']}: {trade.get('from_players', [])} ↔ {trade.get('to_players', [])} - *Pending*")
                    
                    # Create new proposal
                    st.markdown("**➕ Create New Trade Proposal**")
                    
                    other_participants = [p['name'] for p in room['participants'] if p['name'] != my_participant]
                    if other_participants:
                        proposal_to = st.selectbox("Send proposal to", other_participants, key="proposal_to")
                        
                        my_p = next((p for p in room['participants'] if p['name'] == my_participant), None)
                        other_p = next((p for p in room['participants'] if p['name'] == proposal_to), None)
                        
                        if my_p and other_p and my_p['squad'] and other_p['squad']:
                            col1, col2 = st.columns(2)
                            with col1:
                                my_players = st.multiselect(
                                    "Your players to offer",
                                    [p['name'] for p in my_p['squad']],
                                    key="proposal_my_players"
                                )
                            with col2:
                                their_players = st.multiselect(
                                    f"Players you want from {proposal_to}",
                                    [p['name'] for p in other_p['squad']],
                                    key="proposal_their_players"
                                )
                            
                            cash_direction = st.radio(
                                "Cash component",
                                ["No cash", "You pay extra", "They pay extra"],
                                horizontal=True
                            )
                            cash_amount = 0
                            if cash_direction != "No cash":
                                cash_amount = st.number_input("Cash Amount (M)", min_value=1, max_value=100, value=5, key="proposal_cash")
                            
                            if st.button("📨 Send Proposal"):
                                if not my_players and not their_players:
                                    st.error("Select at least one player!")
                                else:
                                    import uuid
                                    new_trade = {
                                        'id': str(uuid.uuid4()),
                                        'from': my_participant,
                                        'to': proposal_to,
                                        'from_players': my_players,
                                        'to_players': their_players,
                                        'cash_from_to': cash_amount if cash_direction == "You pay extra" else (-cash_amount if cash_direction == "They pay extra" else 0),
                                        'status': 'pending',
                                        'created_at': datetime.now().isoformat()
                                    }
                                    room.setdefault('pending_trades', []).append(new_trade)
                                    save_auction_data(auction_data)
                                    st.success(f"Proposal sent to {proposal_to}!")
                                    st.rerun()
                        else:
                            st.info("Both participants need players for trade proposals.")


    # =====================================
    # PAGE 3: Gameweek Admin
    # =====================================
    elif page == "⚙️ Gameweek Admin":
        st.title("⚙️ Gameweek Admin")
        
        # Load schedule
        schedule = load_schedule()
        
        if not is_admin:
            st.warning("Only the room admin can process gameweeks.")
            st.info(f"Admin: {room['admin']}")
        else:
            st.markdown("Process match data and calculate points for each gameweek.")
            
            # Knocked-out Teams Admin (for Super 8s and beyond)
            with st.expander("🚫 Manage Knocked-Out Teams (Super 8s+)"):
                st.caption("Players from knocked-out teams can be released for 50% without counting as your paid release.")
                
                all_teams = ["India", "Australia", "England", "South Africa", "New Zealand", "Pakistan", 
                            "West Indies", "Sri Lanka", "Afghanistan", "Bangladesh", "Netherlands", 
                            "Ireland", "Scotland", "UAE", "Zimbabwe", "Namibia", "USA", "Nepal", 
                            "Oman", "Papua New Guinea"]
                
                knocked_out = set(room.get('knocked_out_teams', []))
                active_teams = [t for t in all_teams if t not in knocked_out]
                
                if knocked_out:
                    st.write(f"**Knocked out:** {', '.join(sorted(knocked_out))}")
                
                team_to_knockout = st.selectbox("Select team to knockout", active_teams)
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("🚫 Knockout Team"):
                        room.setdefault('knocked_out_teams', []).append(team_to_knockout)
                        save_auction_data(auction_data)
                        st.success(f"{team_to_knockout} marked as knocked out!")
                        st.rerun()
                
                with col2:
                    if knocked_out:
                        team_to_restore = st.selectbox("Restore team", sorted(knocked_out))
                        if st.button("✅ Restore Team"):
                            room['knocked_out_teams'].remove(team_to_restore)
                            save_auction_data(auction_data)
                            st.success(f"{team_to_restore} restored!")
                            st.rerun()
            
            # Two tabs: Schedule-based and Manual
            tab1, tab2 = st.tabs(["📅 T20 WC Schedule", "🔗 Manual URLs"])
            
            with tab1:
                st.subheader("Select Gameweek from T20 WC 2026 Schedule")
                
                gameweeks = schedule.get('gameweeks', {})
                if gameweeks:
                    gw_options = [(k, f"GW {k}: {v['name']} ({v['dates']})") for k, v in gameweeks.items()]
                    selected_gw = st.selectbox(
                        "Select Gameweek",
                        options=[g[0] for g in gw_options],
                        format_func=lambda x: next(g[1] for g in gw_options if g[0] == x)
                    )
                    
                    if selected_gw:
                        gw_data = gameweeks[selected_gw]
                        st.info(f"**{gw_data['name']}** | {gw_data['phase']} | {gw_data['dates']}")
                        
                        # Display matches
                        st.markdown("**Matches in this Gameweek:**")
                        matches_df = pd.DataFrame(gw_data['matches'])
                        matches_df['Match'] = matches_df['teams'].apply(lambda x: f"{x[0]} vs {x[1]}")
                        st.dataframe(matches_df[['match_id', 'Match', 'date', 'venue']], use_container_width=True, hide_index=True)
                        
                        # Squad Locking Section
                        st.divider()
                        st.markdown("### 🔒 Squad Locking")
                        
                        locked_squads = room.get('gameweek_squads', {}).get(selected_gw, {})
                        
                        if locked_squads:
                            st.success(f"✅ Squads are locked for GW {selected_gw}. {len(locked_squads)} participants locked.")
                            
                            # Show locked squads overview
                            with st.expander("View Locked Squads"):
                                for participant_name, squad_data in locked_squads.items():
                                    st.markdown(f"**{participant_name}** - {len(squad_data['squad'])} players, IR: {squad_data.get('ir_player', 'None')}")
                        else:
                            st.warning("⚠️ Squads are NOT locked for this gameweek. Lock squads before the first match starts!")
                            
                            if st.button("🔒 Lock All Squads for GW " + selected_gw, type="primary"):
                                # Create snapshot of each participant's current squad
                                gameweek_squads = {}
                                for participant in room['participants']:
                                    gameweek_squads[participant['name']] = {
                                        'squad': participant['squad'].copy(),
                                        'ir_player': participant.get('ir_player'),
                                        'locked_at': datetime.now().isoformat()
                                    }
                                
                                room.setdefault('gameweek_squads', {})[selected_gw] = gameweek_squads
                                save_auction_data(auction_data)
                                st.success(f"🔒 Locked {len(gameweek_squads)} participant squads for GW {selected_gw}!")
                                st.rerun()
                        
                        # Check if already processed
                        if selected_gw in room.get('gameweek_scores', {}):
                            st.warning(f"⚠️ Gameweek {selected_gw} has already been processed. Processing again will overwrite scores.")
                        
                        # Manual URL input for this gameweek
                        st.divider()
                        st.markdown("**Enter Cricbuzz Scorecard URLs for the above matches:**")
                        st.caption("After each match completes, paste the scorecard URL here.")
                        urls_input = st.text_area(
                            "Match URLs (one per line)", 
                            height=150, 
                            placeholder="https://www.cricbuzz.com/live-cricket-scorecard/...\nhttps://www.cricbuzz.com/live-cricket-scorecard/...",
                            key="gw_urls"
                        )
                        
                        if st.button(f"🚀 Process Gameweek {selected_gw}", type="primary", key="process_gw_btn"):
                            urls = [u.strip() for u in urls_input.split('\n') if u.strip()]
                            
                            if not urls:
                                st.error("Please enter at least one match URL.")
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
                                
                                # Store in room data
                                room['gameweek_scores'][selected_gw] = all_scores
                                save_auction_data(auction_data)
                                
                                status.text("✅ Processing Complete!")
                                st.success(f"Gameweek {selected_gw} processed! {len(all_scores)} players scored.")
                                
                                # Show preview
                                st.subheader("📊 Scores Preview")
                                scores_df = pd.DataFrame([{"Player": k, "Points": v} for k, v in all_scores.items()])
                                scores_df = scores_df.sort_values(by="Points", ascending=False)
                                st.dataframe(scores_df.head(20), use_container_width=True, hide_index=True)
                else:
                    st.warning("T20 WC Schedule not loaded. Using manual mode.")
            
            with tab2:
                st.subheader("Manual URL Processing")
                manual_gw = st.number_input("Gameweek Number", min_value=1, max_value=10, value=1)
                manual_urls = st.text_area("Match URLs (one per line)", height=200, placeholder="https://www.cricbuzz.com/live-cricket-scorecard/...", key="manual_urls")
                
                if st.button("🚀 Process", type="primary", key="manual_process_btn"):
                    urls = [u.strip() for u in manual_urls.split('\n') if u.strip()]
                    
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
                        
                        room['gameweek_scores'][str(manual_gw)] = all_scores
                        save_auction_data(auction_data)
                        
                        status.text("✅ Processing Complete!")
                        st.success(f"Gameweek {manual_gw} processed! {len(all_scores)} players scored.")
        
        # Show processed gameweeks
        st.divider()
        st.subheader("📅 Processed Gameweeks")
        if room.get('gameweek_scores'):
            for gw, scores in room['gameweek_scores'].items():
                gw_name = schedule.get('gameweeks', {}).get(gw, {}).get('name', f'Gameweek {gw}')
                st.write(f"**{gw_name}**: {len(scores)} players scored")
            
            # Reset gameweek scores button (Admin Only)
            if is_admin:
                if st.button("🔄 Reset All Gameweek Scores", type="secondary"):
                    room['gameweek_scores'] = {}
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
        
        available_gws = list(room.get('gameweek_scores', {}).keys())
        
        if not available_gws:
            st.info("No gameweeks have been processed yet. Go to Gameweek Admin to process matches.")
        else:
            view_mode = st.radio("View", ["Overall (Cumulative)", "By Gameweek"], horizontal=True)
            
            if view_mode == "By Gameweek":
                selected_gw = st.selectbox("Select Gameweek", available_gws)
                gw_scores = room['gameweek_scores'].get(selected_gw, {})
            else:
                gw_scores = {}
                for gw, scores in room['gameweek_scores'].items():
                    for player, score in scores.items():
                        gw_scores[player] = gw_scores.get(player, 0) + score
            
            # Calculate Best 11 for each participant
            def get_best_11(squad, player_scores, ir_player=None):
                active_squad = [p for p in squad if p['name'] != ir_player]
                scored_players = []
                for p in active_squad:
                    score = player_scores.get(p['name'], 0)
                    scored_players.append({'name': p['name'], 'role': p['role'], 'score': score})
                scored_players.sort(key=lambda x: x['score'], reverse=True)
                
                by_role = {'WK-Batsman': [], 'Batsman': [], 'Batting Allrounder': [], 'Bowling Allrounder': [], 'Bowler': []}
                for p in scored_players:
                    role = p['role']
                    if role in by_role:
                        by_role[role].append(p)
                    else:
                        # Handle unknown roles
                        by_role.setdefault(role, []).append(p)
                
                best_11 = []
                
                # 1 WK mandatory
                if by_role.get('WK-Batsman'):
                    best_11.append(by_role['WK-Batsman'].pop(0))
                
                # Fill remaining with top scorers
                all_remaining = []
                for role_list in by_role.values():
                    all_remaining.extend(role_list)
                all_remaining.sort(key=lambda x: x['score'], reverse=True)
                
                while len(best_11) < 11 and all_remaining:
                    best_11.append(all_remaining.pop(0))
                
                return best_11
            
            # Calculate standings
            standings = []
            
            # Get locked squads if viewing by gameweek
            locked_squads = {}
            if view_mode == "By Gameweek" and selected_gw:
                locked_squads = room.get('gameweek_squads', {}).get(selected_gw, {})
            
            for participant in room['participants']:
                # Use locked squad if available, otherwise current squad
                if locked_squads and participant['name'] in locked_squads:
                    squad_data = locked_squads[participant['name']]
                    squad = squad_data['squad']
                    ir_player = squad_data.get('ir_player')
                else:
                    squad = participant['squad']
                    ir_player = participant.get('ir_player')
                
                best_11 = get_best_11(squad, gw_scores, ir_player)
                total_points = sum(p['score'] for p in best_11)
                standings.append({
                    "Participant": participant['name'],
                    "Points": total_points,
                    "Best 11": ", ".join([f"{p['name']} ({p['score']:.0f})" for p in best_11[:3]]) + "..." if best_11 else "No players"
                })
            
            standings.sort(key=lambda x: x['Points'], reverse=True)
            
            if standings:
                st.subheader("🏆 Current Standings")
                
                if len(standings) >= 3:
                    cols = st.columns(3)
                    medals = ["🥇", "🥈", "🥉"]
                    for i, col in enumerate(cols):
                        with col:
                            st.metric(
                                label=f"{medals[i]} {standings[i]['Participant']}",
                                value=f"{standings[i]['Points']:.0f} pts"
                            )
                
                st.dataframe(pd.DataFrame(standings), use_container_width=True, hide_index=True)
                
                st.divider()
                st.subheader("📋 Detailed Best 11")
                detail_participant = st.selectbox("View Best 11 for", [p['name'] for p in room['participants']])
                detail_p = next((p for p in room['participants'] if p['name'] == detail_participant), None)
                if detail_p:
                    best_11 = get_best_11(detail_p['squad'], gw_scores, detail_p.get('ir_player'))
                    best_11_df = pd.DataFrame(best_11)
                    st.dataframe(best_11_df, use_container_width=True, hide_index=True)
            else:
                st.info("No participants have been added yet. Go to Auction Room to add participants.")
    
    # --- Sidebar Scoring Rules ---
    with st.sidebar:
        st.divider()
        st.header("ℹ️ Scoring Rules")
        st.markdown("""
        **Batting**
        - Run: +0.5
        - Boundary: +0.5
        - Six: +1
        - 50 Bonus: +4
        - 100 Bonus: +8
        
        **Bowling**
        - Wicket: +12
        - LBW/Bowled: +4
        - Maiden: +4
        - 3 Wkts: +4
        - 5 Wkts: +12
        
        **Role-Based**
        - Bowlers exempt from Duck & SR penalties
        """)
        
        st.divider()
        st.caption(f"📊 Database: {len(players_db)} players")

# =====================================
# MAIN ROUTING
# =====================================
if st.session_state.logged_in_user is None:
    show_login_page()
elif st.session_state.current_room is None:
    show_room_selection()
else:
    show_main_app()
