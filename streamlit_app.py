import streamlit as st
import pandas as pd
import json
import os
import string
import random
import hashlib
import uuid as uuid_lib
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

def get_ist_time():
    """Returns the current time in Indian Standard Time (IST)"""
    return datetime.utcnow() + timedelta(hours=5, minutes=30)

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
player_team_lookup = {p['name']: p.get('country', 'Unknown') for p in players_db}
player_names = [p['name'] for p in players_db]

# --- Custom CSS for Aesthetics ---
def inject_custom_css():
    st.markdown("""
    <style>
    /* Global Aesthetics */
    .stApp {
        background-color: #0e1117;
    }
    
    /* Cards / Containers */
    div[data-testid="stExpander"], div[data-testid="stContainer"] {
        border-radius: 12px;
        border: 1px solid #30363d;
        background-color: #161b22;
        box-shadow: 0 4px 12px rgba(0,0,0,0.2);
    }
    
    /* Buttons */
    .stButton button {
        border-radius: 8px;
        font-weight: 600;
        transition: all 0.2s;
    }
    .stButton button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.2);
    }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: #161b22;
        border-radius: 8px;
        padding: 4px 16px;
        border: 1px solid #30363d;
    }
    .stTabs [aria-selected="true"] {
        background-color: #238636 !important;
        border-color: #238636 !important;
        color: white !important;
    }
    
    /* Metrics */
    div[data-testid="metric-container"] {
        background-color: #161b22;
        padding: 1rem;
        border-radius: 10px;
        border: 1px solid #30363d;
    }
    
    /* Trade Card Styling */
    .trade-card {
        background-color: #1e2530;
        border-radius: 10px;
        padding: 15px;
        border-left: 5px solid #58a6ff;
        margin-bottom: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .trade-header {
        color: #58a6ff;
        font-weight: bold;
        font-size: 1.1em;
        margin-bottom: 5px;
    }
    .trade-details {
        color: #c9d1d9;
        font-size: 1em;
    }
    .trade-sub {
        color: #8b949e;
        font-size: 0.85em;
        margin-top: 5px;
    }
    </style>
    """, unsafe_allow_html=True)

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
    inject_custom_css() # Apply Aesthetics
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
        auction_tabs = st.tabs(["🔴 Live Auction", "🎯 Big Auction (Manual)", "💰 Open Bidding", "🔄 Trading", "👤 Squads (Dashboard)"])
        
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
                                    'timer_start': get_ist_time().isoformat(),
                                    'timer_duration': 90,  # Updated to 90 seconds
                                    'opted_out': [], # List of participants who opted out
                                    'auction_started_at': get_ist_time().isoformat()
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
                             
                             st.markdown("---")
                             st.caption("📋 **Detailed Squad View**")
                             p_options = ["None"] + [p['name'] for p in room['participants']]
                             selected_p_view = st.selectbox("Select Participant to view Squad", p_options, key="waiting_dash_select")
                             
                             if selected_p_view != "None":
                                 p_data = next((p for p in room['participants'] if p['name'] == selected_p_view), None)
                                 if p_data and p_data['squad']:
                                     squad_df = []
                                     for pl in p_data['squad']:
                                         squad_df.append({
                                             "Player": pl['name'],
                                             "Role": pl.get('role', 'Unknown'),
                                             "Team": pl.get('team', 'Unknown'),
                                             "Price": f"{pl['buy_price']}M"
                                         })
                                     st.dataframe(pd.DataFrame(squad_df), hide_index=True)
                                 elif p_data:
                                     st.info("No players in squad yet.")

                        st.json({"status": "waiting", "admin": room['admin'], "time": get_ist_time().strftime("%H:%M:%S")})
                        
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
                         
                         st.markdown("---")
                         st.caption("📋 **Detailed Squad View**")
                         p_options = ["None"] + [p['name'] for p in room['participants']]
                         selected_p_view = st.selectbox("Select Participant to view Squad", p_options, key="active_dash_select")
                         
                         if selected_p_view != "None":
                             p_data = next((p for p in room['participants'] if p['name'] == selected_p_view), None)
                             if p_data and p_data['squad']:
                                 squad_df = []
                                 for pl in p_data['squad']:
                                     squad_df.append({
                                         "Player": pl['name'],
                                         "Role": pl.get('role', 'Unknown'),
                                         "Team": pl.get('team', 'Unknown'),
                                         "Price": f"{pl['buy_price']}M"
                                     })
                                 st.dataframe(pd.DataFrame(squad_df), hide_index=True)
                             elif p_data:
                                 st.info("No players in squad yet.")

                    current_role = live_auction.get('current_player_role', 'Unknown')
                    current_team = live_auction.get('current_team')
                    current_bid = live_auction.get('current_bid', 0)

                    current_bidder = live_auction.get('current_bidder')
                    timer_start = datetime.fromisoformat(live_auction.get('timer_start', get_ist_time().isoformat()))
                    timer_duration = live_auction.get('timer_duration', 90)
                    opted_out = live_auction.get('opted_out', [])
                    
                    # Calculate time remaining
                    elapsed = (get_ist_time() - timer_start).total_seconds()
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
                                live_auction['timer_start'] = get_ist_time().isoformat()  # Reset timer
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
                                'team': current_team,
                                'buy_price': current_bid
                            })
                            winner['budget'] -= current_bid
                            
                            room.setdefault('auction_log', []).append({
                                'player': current_player,
                                'buyer': current_bidder,
                                'price': current_bid,
                                'time': get_ist_time().isoformat()
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
                                live_auction['timer_start'] = get_ist_time().isoformat()
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
                            live_auction['timer_start'] = get_ist_time().isoformat()
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
                st.info("📜 **Rules:** Min bid 5M. Over 50M: +5M increments. Hold for 5 minutes to win (or until deadline).")
                
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
                now = get_ist_time()
                deadline_str = room.get('bidding_deadline')
                global_deadline = datetime.fromisoformat(deadline_str) if deadline_str else None
                
                if global_deadline:
                    if now < global_deadline:
                        time_left = global_deadline - now
                        hours_left = time_left.total_seconds() / 3600
                        st.warning(f"⏰ **Bidding closes in {hours_left:.1f} hours** ({global_deadline.strftime('%b %d, %H:%M')})")
                    else:
                        st.error("⏰ **Bidding deadline has passed!** All active bids will be awarded.")
                
                # Process expired bids (auto-award to winners)
                active_bids = room.get('active_bids', [])
                awarded_bids = []
                
                # Create team lookup
                player_team_lookup = {p['name']: p.get('country', 'Unknown') for p in players_db}
                
                for bid in active_bids:
                    expires = datetime.fromisoformat(bid['expires'])
                    # Award if: bid expired OR deadline passed
                    should_award = now >= expires
                    if global_deadline and now >= global_deadline:
                        should_award = True  # Deadline passed, award all bids
                    
                    if should_award:
                        # Award the player to the bidder
                        bidder_participant = next((p for p in room['participants'] if p['name'] == bid['bidder']), None)
                        if bidder_participant and bid['amount'] <= bidder_participant.get('budget', 0):
                            bidder_participant['squad'].append({
                                'name': bid['player'],
                                'role': player_role_lookup.get(bid['player'], 'Unknown'),
                                'team': player_team_lookup.get(bid['player'], 'Unknown'),
                                'buy_price': bid['amount']
                            })
                            bidder_participant['budget'] -= bid['amount']
                            awarded_bids.append(bid)
                            # Remove from unsold
                            with st.spinner(f"Awarding {bid['player']}..."):
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
                        bid_expires = datetime.fromisoformat(bid['expires'])
                        # Effective expiry is min(bid expiry, global deadline)
                        effective_expires = bid_expires
                        if global_deadline and global_deadline < bid_expires:
                             effective_expires = global_deadline
                        
                        time_left = effective_expires - now
                        minutes_left = max(0, time_left.total_seconds() / 60)
                        
                        bids_data.append({
                            "Player": bid['player'],
                            "Current Bid": f"{bid['amount']}M",
                            "Bidder": bid['bidder'],
                            "Time Left": f"{minutes_left:.1f} mins",
                            "Expires": effective_expires.strftime("%b %d, %H:%M")
                        })
                    st.dataframe(pd.DataFrame(bids_data), use_container_width=True, hide_index=True)
                else:
                    st.info("No active bids. Place a bid on an unsold player below!")
                
                # Get unsold players logic
                all_drafted = []
                for p in room['participants']:
                    all_drafted.extend([pl['name'] for pl in p['squad']])
                
                unsold_players = room.get('unsold_players', [])
                # Add players that went unsold (not in any squad)
                for name in player_names:
                    if name not in all_drafted and name not in unsold_players:
                        unsold_players.append(name)
                
                # Ensure uniqueness
                unsold_players = list(set(unsold_players))
                room['unsold_players'] = unsold_players
                
                # Allow bidding on ANY unsold player, even if there is an active bid (outbid logic)
                biddable_players = unsold_players
                
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
                

                
                # --- Release Player Section (Added to Open Bidding) ---
                st.divider()
                st.subheader("🔄 Manage Squad / Release Player")
                
                # Get current participant for release
                my_p_name = user if user else None
                # If admin, maybe allow selecting? But user wants "releasing player feature". 
                # Let's trust "current_participant" logic above or re-select.
                
                # We reuse current_participant from bidding logic if available
                if current_participant:
                    st.caption(f"Managing Squad for: **{current_participant['name']}**")
                    
                    if current_participant['squad']:
                        # --- RELEASE LOGIC START (Copied/Adapted) ---
                        # Calculate current gameweek (based on locked gameweeks)
                        locked_gws = list(room.get('gameweek_squads', {}).keys())
                        current_gw = max([int(gw) for gw in locked_gws]) if locked_gws else 0
                        
                        # Check if participant has used their paid release this GW
                        paid_releases = current_participant.get('paid_releases', {})
                        used_paid_this_gw = paid_releases.get(str(current_gw), False) if current_gw > 0 else False
                        
                        knocked_out_teams = set(room.get('knocked_out_teams', []))
                        player_country_lookup = {p['name']: p.get('country', 'Unknown') for p in players_db}
                        
                        remove_options = [p['name'] for p in current_participant['squad']]
                        player_to_remove = st.selectbox("Select Player to Release", remove_options, key="open_release_player")
                        
                        if player_to_remove:
                             player_obj = next((p for p in current_participant['squad'] if p['name'] == player_to_remove), None)
                             player_country = player_country_lookup.get(player_to_remove, 'Unknown')
                             is_knocked_out_team = player_country in knocked_out_teams
                             
                             if current_gw == 0:
                                 release_type = "unlimited"
                                 st.markdown("**🔄 Release Player (Before GW1 - 50% Refund)**")
                             elif is_knocked_out_team and current_gw >= 5:
                                 release_type = "knockout_free"
                                 st.markdown("**🔄 Release Player (Knocked-Out Team - FREE 50%)**")
                             elif not used_paid_this_gw:
                                 release_type = "paid"
                                 st.markdown(f"**🔄 Release Player (GW{current_gw} - Paid 50%)**")
                             else:
                                 release_type = "free"
                                 st.markdown(f"**🔄 Release Player (GW{current_gw} - Free 0%)**")
                             
                             if release_type in ["unlimited", "paid", "knockout_free"]:
                                 refund_amount = player_obj.get('buy_price', 0) // 2 if player_obj else 0
                             else:
                                 refund_amount = 0
                                 
                             st.caption(f"Refund: **{refund_amount}M**")
                             
                             if st.button("🔓 Release Player", key="open_release_btn"):
                                 current_participant['squad'] = [p for p in current_participant['squad'] if p['name'] != player_to_remove]
                                 current_participant['budget'] += refund_amount
                                 if current_participant.get('ir_player') == player_to_remove:
                                     current_participant['ir_player'] = None
                                 
                                 room.setdefault('unsold_players', []).append(player_to_remove)
                                 
                                 if release_type == "paid":
                                     current_participant.setdefault('paid_releases', {})[str(current_gw)] = True
                                 
                                 save_auction_data(auction_data)
                                 st.success(f"Released {player_to_remove}! Refunded {refund_amount}M.")
                                 st.rerun()
                    else:
                        st.info("Your squad is empty.")
                else:
                    st.warning("Please select your participant name above to manage squad.")
                    
                if current_participant:
                    st.metric("Your Budget", f"{current_participant.get('budget', 0)}M")
                    
                    if biddable_players:
                        bid_player = st.selectbox(
                            "Select Player to Bid On",
                            [""] + sorted(biddable_players),
                            format_func=lambda x: f"{x} ({player_role_lookup.get(x, 'Unknown')})" if x else "Select a player...",
                            key="open_bid_player"
                        )
                        
                        if bid_player:
                            # Check if there's an existing bid
                            existing_bid = next((b for b in active_bids if b['player'] == bid_player), None)
                            min_bid = 5
                            if existing_bid:
                                st.warning(f"Current highest bid: **{existing_bid['amount']}M** by {existing_bid['bidder']}")
                                if existing_bid['bidder'] == current_participant['name']:
                                    st.error("You explicitly hold the highest bid already.")
                                    min_bid = existing_bid['amount'] # Prevent self-outbid unless we want to allow increasing? Usually no.
                                else:
                                    if existing_bid['amount'] >= 50:
                                        min_bid = existing_bid['amount'] + 5
                                    else:
                                        min_bid = existing_bid['amount'] + 1
                            
                            bid_amount = st.number_input(
                                f"Bid Amount (Min: {min_bid}M)",
                                min_value=min_bid,
                                max_value=int(current_participant.get('budget', 0)),
                                value=min_bid,
                                step=5 if min_bid >= 50 else 1,
                                key="open_bid_amount"
                            )
                            
                            if st.button("🎯 Place Bid", type="primary"):
                                if bid_amount > current_participant.get('budget', 0):
                                    st.error("Insufficient budget!")
                                elif existing_bid and existing_bid['bidder'] == current_participant['name'] and bid_amount <= existing_bid['amount']:
                                     st.error("You already hold the highest bid.")
                                else:
                                    # Remove old bid if exists
                                    new_active_bids = [b for b in room['active_bids'] if b['player'] != bid_player]
                                    
                                    # Add new bid with 5-minute expiry (TESTING MODE)
                                    # Logic: Expires in 5 mins OR Deadline, whichever is sooner?
                                    # Usually bid expiry adds time. So just set 5 mins. Display logic handles truncation.
                                    expiry_time = now + timedelta(minutes=5)
                                    
                                    new_active_bids.append({
                                        'player': bid_player,
                                        'amount': bid_amount,
                                        'bidder': current_participant['name'],
                                        'bid_time': now.isoformat(),
                                        'expires': expiry_time.isoformat()
                                    })
                                    room['active_bids'] = new_active_bids
                                    save_auction_data(auction_data)
                                    st.success(f"Bid placed! {bid_player} at {bid_amount}M. Expires in 5 minutes.")
                                    st.rerun()
                    else:
                        st.info("No players available for bidding.")
        
        # ================ TAB 3: TRADING ================
        with auction_tabs[3]:
            st.subheader("🔄 Trade Center")
            
            if not room.get('big_auction_complete'):
                st.info("⏳ Trading opens after the Big Auction is complete.")
            else:
                # Helper: Get current participant info
                my_p_name = user
                
                # Ensure pending_trades list exists
                if 'pending_trades' not in room:
                    room['pending_trades'] = []
                
                # Handling Counter-Offer Prefill
                prefill = st.session_state.pop('trade_prefill', None)
                
                # ---------------- INBOX ----------------
                st.markdown("### 📬 Incoming Proposals")
                my_incoming = [t for t in room['pending_trades'] if t['to'] == my_p_name]
                
                if my_incoming:
                    for trade in my_incoming:
                        with st.container():
                            # Aesthetic Card
                            details_html = ""
                            if trade['type'] == "Transfer (Sell)":
                                details_html = f"Selling <b>{trade['player']}</b> for <b>{trade['price']}M</b>"
                            elif trade['type'] == "Transfer (Buy)":
                                details_html = f"Wants to Buy <b>{trade['player']}</b> for <b>{trade['price']}M</b>"
                            elif trade['type'] == "Exchange":
                                cash_txt = ""
                                if trade['cash_amount'] > 0:
                                    payer = trade['cash_payer']
                                    cash_txt = f" <span style='color:#7ee787'>(+ {trade['cash_amount']}M from {payer})</span>"
                                details_html = f"Swap: <b>{trade['get_player']}</b> (You Get) ↔ <b>{trade['give_player']}</b> (You Give){cash_txt}"
                            elif trade['type'] == "Loan (1 GW)":
                                details_html = f"Loan: <b>{trade['player']}</b> for GW{trade['gw']} @ <b>{trade['fee']}M</b>"

                            st.markdown(f"""
                            <div class="trade-card">
                                <div class="trade-header">From {trade['from']} <span style='font-size:0.8em; color:#8b949e; float:right'>{trade['type']}</span></div>
                                <div class="trade-details">{details_html}</div>
                                <div class="trade-sub">ID: {trade['id'][:8]}...</div>
                            </div>
                            """, unsafe_allow_html=True)
                            
                            c1, c2, c3 = st.columns([1, 1, 1])
                            
                            # ACTION: ACCEPT
                            if c1.button("✅ Accept", key=f"acc_{trade['id']}"):
                                sender = next((p for p in room['participants'] if p['name'] == trade['from']), None)
                                receiver = next((p for p in room['participants'] if p['name'] == trade['to']), None)
                                success = False
                                
                                if sender and receiver:
                                    if trade['type'] == "Transfer (Sell)":
                                        p_obj = next((p for p in sender['squad'] if p['name'] == trade['player']), None)
                                        if p_obj and receiver['budget'] >= trade['price']:
                                            sender['squad'].remove(p_obj)
                                            # FIX: Restore Team Name
                                            p_obj['team'] = player_team_lookup.get(p_obj['name'], 'Unknown')
                                            p_obj['buy_price'] = trade['price']
                                            receiver['squad'].append(p_obj)
                                            sender['budget'] += trade['price']
                                            receiver['budget'] -= trade['price']
                                            success = True
                                    
                                    elif trade['type'] == "Transfer (Buy)":
                                        # Sender (Buyer) wants to buy from Receiver (Seller)
                                        p_obj = next((p for p in receiver['squad'] if p['name'] == trade['player']), None)
                                        if p_obj and sender['budget'] >= trade['price']:
                                            receiver['squad'].remove(p_obj)
                                            # Restore Team
                                            p_obj['team'] = player_team_lookup.get(p_obj['name'], 'Unknown')
                                            p_obj['buy_price'] = trade['price']
                                            sender['squad'].append(p_obj)
                                            receiver['budget'] += trade['price']
                                            sender['budget'] -= trade['price']
                                            success = True
                                    
                                    elif trade['type'] == "Exchange":
                                        p_give = next((p for p in receiver['squad'] if p['name'] == trade['give_player']), None)
                                        p_get = next((p for p in sender['squad'] if p['name'] == trade['get_player']), None)
                                        
                                        # Budget Check
                                        budget_ok = True
                                        if trade['cash_amount'] > 0:
                                            payer_name = trade['cash_payer']
                                            payer_budget = sender['budget'] if payer_name == sender['name'] else receiver['budget']
                                            if payer_budget < trade['cash_amount']:
                                                budget_ok = False
                                        
                                        if p_give and p_get and budget_ok:
                                            receiver['squad'].remove(p_give)
                                            sender['squad'].remove(p_get)
                                            # Restore Teams
                                            p_give['team'] = player_team_lookup.get(p_give['name'], 'Unknown')
                                            p_get['team'] = player_team_lookup.get(p_get['name'], 'Unknown')
                                            
                                            receiver['squad'].append(p_get)
                                            sender['squad'].append(p_give)
                                            
                                            if trade['cash_amount'] > 0:
                                                if trade['cash_payer'] == receiver['name']:
                                                    receiver['budget'] -= trade['cash_amount']
                                                    sender['budget'] += trade['cash_amount']
                                                else:
                                                    sender['budget'] -= trade['cash_amount']
                                                    receiver['budget'] += trade['cash_amount']
                                            success = True
                                    
                                    elif trade['type'] == "Loan (1 GW)":
                                        p_obj = next((p for p in sender['squad'] if p['name'] == trade['player']), None)
                                        if p_obj and receiver['budget'] >= trade['fee']:
                                            room.setdefault('active_loans', []).append({
                                                'player': trade['player'], 'from': sender['name'], 'to': receiver['name'],
                                                'fee': trade['fee'], 'gameweek': trade['gw'], 
                                                'original_buy_price': p_obj.get('buy_price', 0),
                                                'created_at': get_ist_time().isoformat()
                                            })
                                            sender['squad'].remove(p_obj)
                                            receiver['squad'].append({
                                                'name': trade['player'], 'role': p_obj['role'],
                                                'buy_price': p_obj.get('buy_price', 0), 'on_loan': True, 'loan_from': sender['name'],
                                                'team': player_team_lookup.get(trade['player'], 'Unknown')
                                            })
                                            sender['budget'] += trade['fee']
                                            receiver['budget'] -= trade['fee']
                                            success = True

                                if success:
                                    room['pending_trades'] = [t for t in room['pending_trades'] if t['id'] != trade['id']]
                                    save_auction_data(auction_data)
                                    st.success("Trade Executed Successfully!")
                                    st.rerun()
                                else:
                                    st.error("Execution failed (Budget/Player missing).")

                            # ACTION: REJECT
                            if c2.button("❌ Reject", key=f"rej_{trade['id']}"):
                                room['pending_trades'] = [t for t in room['pending_trades'] if t['id'] != trade['id']]
                                save_auction_data(auction_data)
                                st.toast("Trade Rejected")
                                st.rerun()

                            # ACTION: COUNTER
                            if c3.button("🔄 Counter", key=f"cnt_{trade['id']}"):
                                # Smart Counter Mapping
                                new_type = trade['type']
                                new_player = trade.get('player')
                                new_price = trade.get('price')
                                
                                if trade['type'] == "Transfer (Sell)":
                                    new_type = "Transfer (Buy)" # They sell, I counter by offering to Buy (diff price)
                                elif trade['type'] == "Transfer (Buy)":
                                    new_type = "Transfer (Sell)" # They buy, I counter by offering to Sell
                                
                                st.session_state['trade_prefill'] = {
                                    'to': trade['from'],
                                    'type': new_type,
                                    'player': new_player,
                                    'price': new_price,
                                    'is_counter': True,
                                    'original_id': trade['id']
                                }
                                # Force UI Reset
                                if 'tp_type_radio' in st.session_state:
                                    del st.session_state['tp_type_radio']
                                
                                st.toast("Drafting Counter Offer... Scroll down.")
                                st.rerun()
                            st.markdown("---") # Spacer
                else:
                    st.info("No incoming proposals.")

                # ---------------- OUTBOX ----------------
                with st.expander("📤 Sent Proposals"):
                    sent = [t for t in room['pending_trades'] if t['from'] == my_p_name]
                    if sent:
                        for s in sent:
                             st.write(f"To **{s['to']}**: {s['type']}")
                             if st.button("Cancel", key=f"can_{s['id']}"):
                                room['pending_trades'].remove(s)
                                save_auction_data(auction_data)
                                st.rerun()
                    else:
                        st.caption("No sent proposals.")

                # ---------------- PROPOSE FORM ----------------
                st.markdown("### 📝 Propose Trade")
                
                parts = [p['name'] for p in room['participants']]
                
                # Determine Defaults
                def_to_idx = 0
                def_type_idx = 0
                is_countering = False
                
                if prefill:
                    is_countering = prefill.get('is_counter', False)
                    if prefill['to'] in parts:
                        def_to_idx = parts.index(prefill['to'])
                        # If I am default_to, shift
                        if prefill['to'] == my_p_name:
                             def_to_idx = (def_to_idx + 1) % len(parts)
                    
                    types = ["Transfer (Sell)", "Transfer (Buy)", "Exchange", "Loan (1 GW)"]
                    if prefill['type'] in types:
                        def_type_idx = types.index(prefill['type'])
                
                if is_countering:
                    st.info(f"🔄 **Drafting Counter-Offer to {prefill['to']}**")
                
                # SECURITY FIX: Always lock FROM to Current User
                from_p_name = my_p_name
                if from_p_name not in parts:
                    st.error("You are not a participant in this auction room.")
                    st.stop()
                
                # Filter 'to' options
                to_opts = [x for x in parts if x != from_p_name]
                real_def_idx = 0
                if prefill and prefill['to'] in to_opts:
                    real_def_idx = to_opts.index(prefill['to'])
                    
                to_p_name = st.selectbox("Offer To", to_opts, index=real_def_idx, key="tp_to")

                from_p = next((p for p in room['participants'] if p['name'] == from_p_name), None)
                to_p = next((p for p in room['participants'] if p['name'] == to_p_name), None)

                if from_p and to_p:
                    # FIX: Use key and handle default
                    # If prefill exists, we want to force format.
                    # But index works reliably only if we didn't touch it.
                    # Best way: Check if match.
                    
                    t_type = st.radio("Type", ["Transfer (Sell)", "Transfer (Buy)", "Exchange", "Loan (1 GW)"], index=def_type_idx, horizontal=True, key="tp_type_radio")
                    
                    # Force Update if Prefill (Session State Hack)
                    # If prefill type != current state, update state and rerun? No, infinite loop.
                    # We rely on 'index' being respected on first load.
                    # But user said it didn't switch.
                    # The 'Counter' button logic should have cleared this key if we want to reset?
                    # Let's add that to Counter button logic instead.
                    # See chunk 1.
                    
                    payload = {}
                    ready = False
                    
                    if t_type == "Transfer (Sell)":
                        if from_p['squad']:
                            pl = st.selectbox("Player to Sell", [str(p['name']) for p in from_p['squad']])
                            pr = st.number_input("Asking Price (M)", 1, 500, 10, help="Amount you want to receive")
                            payload = {'type': t_type, 'player': pl, 'price': pr}
                            ready = True
                        else:
                            st.warning("You have no players to sell.")

                    elif t_type == "Transfer (Buy)":
                        if to_p['squad']:
                            # Default player selection from prefill
                            pl_opts = [str(p['name']) for p in to_p['squad']]
                            pl_idx = 0
                            if prefill and prefill.get('player') in pl_opts:
                                pl_idx = pl_opts.index(prefill['player'])
                            
                            pl = st.selectbox("Player to Buy", pl_opts, index=pl_idx)
                            
                            # Default price from prefill
                            def_price = 10
                            if prefill and prefill.get('price'):
                                def_price = int(prefill['price'])
                            
                            pr = st.number_input("Offer Price (M)", 1, 500, def_price, help="Amount you want to pay")
                            payload = {'type': t_type, 'player': pl, 'price': pr}
                            ready = True
                        else:
                            st.warning(f"{to_p['name']} has no players to buy.")
                    
                    elif t_type == "Exchange":
                        if from_p['squad'] and to_p['squad']:
                            c1, c2 = st.columns(2)
                            p1 = c1.selectbox(f"Your Player (Give)", [p['name'] for p in from_p['squad']])
                            p2 = c2.selectbox(f"Their Player (Get)", [p['name'] for p in to_p['squad']])
                            
                            c_dir = st.radio("Cash Adjustment", ["None", f"I pay {to_p_name}", f"{to_p_name} pays Me"], horizontal=True)
                            c_amt = 0
                            if c_dir != "None":
                                c_amt = st.number_input("Cash Amount (M)", 1, 100, 5)
                            
                            payer = None
                            if c_dir == f"I pay {to_p_name}":
                                payer = from_p_name
                            elif c_dir == f"{to_p_name} pays Me":
                                payer = to_p_name
                            
                            payload = {'type': t_type, 'give_player': p1, 'get_player': p2, 'cash_amount': c_amt, 'cash_payer': payer}
                            ready = True
                        else:
                            st.warning("Both participants need players.")

                    elif t_type == "Loan (1 GW)":
                        with st.popover("About Loans"):
                             st.write("Loans are for 1 Gameweek only. Player returns automatically.")
                        
                        if from_p['squad']:
                            pl = st.selectbox("Player to Loan Out", [p['name'] for p in from_p['squad']])
                            fee = st.number_input("Loan Fee (M)", 0, 50, 5)
                            # GW Logic
                            locked = list(room.get('gameweek_squads', {}).keys())
                            ngw = str((max([int(x) for x in locked]) if locked else 0) + 1)
                            st.caption(f"Loan Duration: Gameweek {ngw}")
                            payload = {'type': t_type, 'player': pl, 'fee': fee, 'gw': ngw}
                            ready = True
                    
                    if ready:
                        if st.button("📤 Send Proposal", type="primary"):
                            new_t = {
                                'id': str(uuid_lib.uuid4()),
                                'from': from_p_name, 'to': to_p_name,
                                'created_at': get_ist_time().strftime("%Y-%m-%d %H:%M:%S"),
                                **payload
                            }
                            room['pending_trades'].append(new_t)
                            
                            # Auto-Delete Original if Countering
                            if is_countering and prefill and 'original_id' in prefill:
                                orig_id = prefill['original_id']
                                room['pending_trades'] = [t for t in room['pending_trades'] if t['id'] != orig_id]
                                st.caption("Original trade rejected/replaced.")

                            save_auction_data(auction_data)
                            st.success("Proposal Sent!")
                            if is_countering:
                                st.session_state.pop('trade_prefill', None) # Clear prefill
                            st.rerun()

        # ================ TAB 4: SQUADS DASHBOARD ================
        with auction_tabs[4]:
            st.subheader("👤 Squad Dashboard")
            
            # Auto-Refresh Logic (using st.fragment if supported, otherwise just render)
            # Since we can't easily check imports, we'll try a conditional block if possible.
            # But simpler: Just render. User can click 'Refresh' button.
            
            # Auto-Refresh Toggle & Manual Refresh
            cR1, cR2 = st.columns([1, 4])
            if cR1.button("🔄 Refresh Now"):
                st.rerun()
            
            enable_ar = cR2.checkbox("Enable Auto-Refresh (5s)", value=False, help="Automatically refreshes the dashboard every 5 seconds.")
            if enable_ar:
                import time
                time.sleep(5)
                st.rerun()

            # Global Squad Table
            all_squads_data = []
            for p in room['participants']:
                for pl in p['squad']:
                    all_squads_data.append({
                        'Participant': p['name'],
                        'Player': pl['name'],
                        'Role': pl['role'],
                        'Team': pl.get('team', player_team_lookup.get(pl['name'], 'Unknown')),
                        'Price': pl.get('buy_price', 0)
                    })
            
            if all_squads_data:
                df = pd.DataFrame(all_squads_data)
                
                # Filters
                c1, c2 = st.columns(2)
                with c1:
                    sel_p = st.multiselect("Filter by Participant", [p['name'] for p in room['participants']])
                with c2:
                    search = st.text_input("Search Player")
                
                if sel_p:
                    df = df[df['Participant'].isin(sel_p)]
                if search:
                    df = df[df['Player'].str.contains(search, case=False)]
                
                st.dataframe(
                    df, 
                    use_container_width=True, 
                    hide_index=True,
                    column_config={
                        "Price": st.column_config.NumberColumn(format="%dM")
                    }
                )
            else:
                st.info("No squads yet.")

    # ================ PAGE 3: GAMEWEEK ADMIN ================


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
