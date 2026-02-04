import streamlit as st
import math
import pandas as pd
import json
import os
import string
import random
import hashlib
import uuid as uuid_lib
from datetime import datetime, timedelta
import sys

# --- Robust Import Helper ---
def safe_import_module(module_name):
    if module_name in sys.modules:
        del sys.modules[module_name]
    return __import__(module_name)

# Force reload local modules to prevent Streamlit KeyErrors
try:
    import cricbuzz_scraper
except (KeyError, ImportError):
    cricbuzz_scraper = safe_import_module('cricbuzz_scraper')

try:
    import player_score_calculator
    CricketScoreCalculator = player_score_calculator.CricketScoreCalculator
except (KeyError, ImportError):
    player_score_calculator = safe_import_module('player_score_calculator')
    CricketScoreCalculator = player_score_calculator.CricketScoreCalculator

try:
    import backend.storage
    StorageManager = backend.storage.StorageManager
except (KeyError, ImportError):
    if 'backend.storage' in sys.modules: del sys.modules['backend.storage']
    import backend.storage
    StorageManager = backend.storage.StorageManager

import textwrap

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


# Initialize Storage Manager
storage_mgr = StorageManager(AUCTION_DATA_FILE)

# --- Load/Save Functions for Persistence ---
# Removed st.cache_data to ensure we always get fresh data from disk
# The local file read is fast enough (ms) and this prevents stale state bugs.
def get_cached_auction_data(_mgr_dummy_arg):
    return storage_mgr.load_data()

def load_auction_data():
    """Load auction data directly."""
    return get_cached_auction_data("global_key")

def save_auction_data(data):
    """Save auction data to Storage Manager (Remote + Local)."""
    storage_mgr.save_data(data)
    storage_mgr.save_data(data)
    # Cache clearing no longer needed as we don't cache
    # get_cached_auction_data.clear()

@st.cache_data
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

# @st.cache_data removed to ensure updates are reflected immediately
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
player_info_map = {p['name']: p for p in players_db}
player_names = [p['name'] for p in players_db]

def format_player_name(name):
    if not name: return "Select a player..."
    info = player_info_map.get(name, {})
    return f"{name} ({info.get('role', 'N/A')} - {info.get('country', 'N/A')})"

# --- CUSTOM CSS FOR PREMIUM BROADCASTER LOOK ---
# --- CUSTOM CSS FOR ELECTRIC BLUE TERMINAL LOOK ---
# --- CUSTOM CSS FOR ELECTRIC BLUE TERMINAL LOOK ---
def inject_custom_css():
    pass # Reverted to standard Streamlit theme per user request

# --- Session State Initialization ---
if 'logged_in_user' not in st.session_state:
    st.session_state.logged_in_user = None
if 'current_room' not in st.session_state:
    st.session_state.current_room = None

# =====================================
# LOGIN / REGISTER PAGE
# =====================================
def show_login_page():
    # Centered Layout
    _, col, _ = st.columns([1, 1.5, 1])
    
    with col:
        st.markdown("<div class='login-header'><h1>🏏 Fantasy Cricket Auction</h1><p style='color:#8b949e'>Build your dream team with real-time bidding strategies.</p></div>", unsafe_allow_html=True)
        
        tab_login, tab_register = st.tabs(["🔐 Login", "📝 Register"])
        
        with tab_login:
            st.markdown("<br>", unsafe_allow_html=True)
            login_username = st.text_input("Username", key="login_username", placeholder="Enter your username")
            login_password = st.text_input("Password", key="login_password", type="password", placeholder="Enter your password")
            
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("🚀 Login", type="primary", key="login_btn", use_container_width=True):
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
        
        with tab_register:
            st.markdown("<br>", unsafe_allow_html=True)
            register_username = st.text_input("Choose Username", key="register_username", placeholder="Choose a unique username")
            register_password = st.text_input("Create Password", key="register_password", type="password", placeholder="Min 4 characters")
            register_password_confirm = st.text_input("Confirm Password", key="register_password_confirm", type="password", placeholder="Re-enter password")
            
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("✨ Create Account", type="primary", key="register_btn", use_container_width=True):
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
                    st.warning("Please enter all fields.")

# =====================================
# ROOM SELECTION / CREATION PAGE
# =====================================
def show_room_selection():
    user = st.session_state.logged_in_user
    user_data = auction_data['users'].get(user, {})
    
    st.title(f"🏏 Welcome, {user}!")
    
    # Sidebar logout
    # Sidebar logout
    if st.sidebar.button("🚪 Logout"):
        st.session_state.logged_in_user = None
        st.session_state.current_room = None
        st.query_params.clear()
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
                    "members": [user],
                    "participants": [], # Init empty, Admin must import/create/claim
                    "gameweek_scores": {},
                    "gameweek_scores": {},
                    "created_at": get_ist_time().isoformat(),
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
                st.query_params['user'] = user
                st.query_params['room'] = room_code
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
                        user_data['rooms_joined'] = user_data.get('rooms_joined', []) + [join_code]
                        save_auction_data(auction_data)
                        st.success(f"Joined room: {room['name']}")
                    st.session_state.current_room = join_code
                    st.query_params['user'] = user
                    st.query_params['room'] = join_code
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
                st.query_params['user'] = user
                st.query_params['room'] = selected_room
                st.rerun()
    else:
        st.info("You haven't created or joined any rooms yet.")

# =====================================
# MAIN APP (Inside a Room)
# =====================================
@st.fragment(run_every=5)
def render_live_auction_fragment(room_code, user):
    auction_data = load_auction_data()
    room = auction_data['rooms'].get(room_code)
    if not room: return
    # players_db is global
    is_admin = room['admin'] == user
    
    # Get all teams from players
    teams_with_players = {}
    for player in players_db:
        team = player.get('country', 'Unknown')
        if team not in teams_with_players:
            teams_with_players[team] = []
        teams_with_players[team].append(player)
        
    # Get Draft Status
    all_drafted_players = set()
    for p in room.get('participants', []):
        for pl in p['squad']:
            all_drafted_players.add(pl['name'])

    st.subheader("🔴 Live Auction")
    
    # Feature: View Real World Squads
    with st.expander("🌏 View World Cup Squads (Reference)"):
        all_teams_list = sorted(list(teams_with_players.keys()))
        view_team = st.selectbox("Select Team", all_teams_list, key="view_real_squad_select")
        if view_team:
            t_players = teams_with_players[view_team]
            # Create DF
            t_data = []
            for tp in t_players:
                status = "✅ Taken" if tp['name'] in all_drafted_players else "Popcorn" # Wait, "Available"?
                # Status: Taken or Available
                status = "🔴 Taken" if tp['name'] in all_drafted_players else "🟢 Available"
                t_data.append({
                    "Player": tp['name'],
                    "Role": tp.get('role', '-'),
                    "Status": status
                })
            st.dataframe(pd.DataFrame(t_data), hide_index=True, use_container_width=True)
    
    if room.get('big_auction_complete'):
        st.success("✅ Big Auction is complete! Use 'Open Bidding' tab to bid on unsold players.")
    elif not room['participants']:
        st.warning("Add participants before starting the live auction.")
    else:
        # Live auction state
        live_auction = room.get('live_auction', {})
        
        
        # Get all teams from players (Already loaded at top)
        # Filter out already drafted players (Already loaded at top)
        
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
                            # Let's update timer_start to `get_ist_time()` to give fresh 60s (fair for network issues).
                            existing_auction['timer_start'] = get_ist_time().isoformat()
                            
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
                                'timer_start': get_ist_time().isoformat(),
                                'timer_duration': 60,
                                'opted_out': [],
                                'auction_started_at': get_ist_time().isoformat()
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
                            'timer_duration': 60,  # Updated to 60 seconds
                            'opted_out': [], # List of participants who opted out
                            'auction_started_at': get_ist_time().isoformat()
                        }
                        save_auction_data(auction_data)
                        st.rerun()
                else:
                    st.success("All players have been drafted!")
            else:
                # === MEMBER: WAITING SCREEN ===
                st.markdown("### 📡 MISSION CONTROL: PRE-AUCTION LOBBY")
                st.info("The Admin is initializing the auction protocols. Stand by...")
                
                # Show Live Dashboard (Grid View)
                st.markdown("#### 👥 PARTICIPANT STATUS")
                
                # 4 Columns Grid
                cols = st.columns(4)
                for i, p in enumerate(room['participants']):
                     with cols[i % 4]:
                         # Calculate Budget %
                         budget_pct = min(100, max(0, (p['budget'] / 500) * 100))
                         
                         st.markdown(f"""
                         <div class="terminal-card" style="padding: 15px; margin-bottom: 0px; height: 100%;">
                             <div style="font-size: 0.9rem; color: #00CCFF; font-weight: bold; margin-bottom: 5px;">{p['name']}</div>
                             <div style="font-size: 1.8rem; color: white; font-weight: 700; font-family: 'Roboto Mono'; line-height: 1;">{p['budget']}M</div>
                             <div style="font-size: 0.7rem; color: #8b949e; letter-spacing: 1px;">BUDGET AVAIL</div>
                             
                             <div style="margin-top: 10px; margin-bottom: 10px; height: 4px; background: rgba(255,255,255,0.1); border-radius: 2px; overflow: hidden;">
                                 <div style="width: {budget_pct}%; height: 100%; background: linear-gradient(90deg, #007BFF, #00CCFF);"></div>
                             </div>
                             
                             <div style="display: flex; justify-content: space-between; align-items: center; font-size: 0.75rem;">
                                 <span style="color: #8b949e;">SQUAD</span>
                                <span class="status-badge" style="background: rgba(0, 204, 255, 0.1); color: #00CCFF;">{len(p['squad'])} / 30</span>
                             </div>
                         </div>
                         """, unsafe_allow_html=True)
                
                st.write("") # Spacer
                with st.expander("📋 Detailed Squad Manifest", expanded=False):
                     
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
                time.sleep(5)
                st.rerun()
        
        else:
            # === ACTIVE AUCTION MODE ===
            current_player = live_auction.get('current_player')
            
            # === 1. TEAM STATUS (Progress Bars) ===
            with st.expander("📊 Team Budgets & Rosters", expanded=False):
                 st.markdown("### 🏦 Live Budgets")
                 cols = st.columns(3)
                 for i, p in enumerate(room['participants']):
                     with cols[i % 3]:
                         st.markdown(f"**{p['name']}**")
                         # Assume 100M is max for visualization base
                         budget_val = p.get('budget', 0)
                         # Progress bar (Green to Blue gradient via CSS)
                         st.progress(min(1.0, max(0.0, budget_val / 100.0)))
                         st.caption(f"💰 **{budget_val}M** Left | 🦅 {len(p['squad'])} / 30 Players")

                 st.markdown("---")
                 st.caption("📋 **Detailed Squad View**")
                 p_options = ["Select Team..."] + [p['name'] for p in room['participants']]
                 selected_p_view = st.selectbox("View Squad", p_options, label_visibility="collapsed", key="active_dash_select")
                 
                 if selected_p_view != "Select Team...":
                     p_data = next((p for p in room['participants'] if p['name'] == selected_p_view), None)
                     if p_data and p_data['squad']:
                         squad_df = []
                         for pl in p_data['squad']:
                             squad_df.append({
                                 "Player": pl['name'],
                                 "Role": pl.get('role', 'Unknown'),
                                 "Price": f"{pl['buy_price']}M"
                             })
                         st.dataframe(pd.DataFrame(squad_df), hide_index=True, use_container_width=True)
                     elif p_data:
                         st.info("No players acquired yet.")

            current_role = live_auction.get('current_player_role', 'Unknown')
            current_team = live_auction.get('current_team')
            current_bid = live_auction.get('current_bid', 0)

            current_bidder = live_auction.get('current_bidder')
            timer_start = datetime.fromisoformat(live_auction.get('timer_start', get_ist_time().isoformat()))
            timer_duration = live_auction.get('timer_duration', 60)
            opted_out = live_auction.get('opted_out', [])
            
            # Calculate time remaining
            elapsed = (get_ist_time() - timer_start).total_seconds()
            time_remaining = max(0, timer_duration - elapsed)
            
            # === 2. FEATURED PLAYER CARD (Main Floor) ===
            # Using custom HTML for the "Broadcaster" look
            
            # Map role to icon
            role_icon = "🏏"
            if "Bowler" in current_role: role_icon = "🥎"
            elif "Allrounder" in current_role: role_icon = "🦄"
            elif "WK" in current_role: role_icon = "🧤"
            
            # Explicitly left-aligned string to avoid Markdown code-block interpretation
            # === 2. FEATURED PLAYER (SIMPLE RELIABLE VIEW) ===
            st.divider()
            
            # Simple, fail-safe display using standard Streamlit components
            col_info, col_timer = st.columns([2, 1])
            
            with col_info:
                st.subheader("🏏 Auctioning Now")
                st.title(f"{current_player}")
                st.markdown(f"#### **Role:** {current_role}")
                st.markdown(f"**Team:** {current_team}")
                
            with col_timer:
                if time_remaining > 0:
                    st.error("🔴 LIVE")
                else:
                    st.success("✅ SOLD")
            
            st.divider()
            
            # === 3. METRICS & TIMER ===
            c1, c2, c3 = st.columns([1, 1, 1])
            with c1:
                st.metric("💰 Current Bid", f"{current_bid}M", delta="Leading" if current_bid > 0 else None)
            with c2:
                # Active Bidder Name
                bidder_display = current_bidder if current_bidder else "Waiting..."
                st.metric("👑 Top Bidder", bidder_display)
            with c3:
                # Timer with Color Logic
                if time_remaining > 10:
                    st.metric("⏱️ Time Left", f"{int(time_remaining)}s")
                elif time_remaining > 0:
                    st.metric("⏱️ Time Left", f"{int(time_remaining)}s", delta="HURRY UP!", delta_color="inverse")
                else:
                    st.metric("⏱️ Time Left", "0s", delta="- SOLD -", delta_color="off")
            
            # Thin elegant progress bar
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
                
                # Use a container to isolate layout
                with st.container():
                    col1, col2, col3 = st.columns([1, 1, 1])
                    
                    # Column 1: Bidder Selection
                    with col1:
                        if is_admin:
                            bidder_options = [p['name'] for p in room['participants'] if p['name'] not in opted_out]
                            default_idx = 0
                            if my_participant and my_participant['name'] in bidder_options:
                                default_idx = bidder_options.index(my_participant['name'])
                            bidder_name = st.selectbox("Bidder", bidder_options, index=default_idx, key=f"bid_select_{current_player}_uniq")
                        else:
                            if my_participant and my_participant['name'] not in opted_out:
                                bidder_name = my_participant['name']
                                st.text_input("Bidder", value=bidder_name, disabled=True, key=f"bid_select_{current_player}_uniq")
                            else:
                                bidder_name = None
                                st.warning("You are not an active participant for this player")
                        
                        bidder = next((p for p in room['participants'] if p['name'] == bidder_name), None)

                    # Column 2: Bid Amount
                    with col2:
                        if bidder:
                            # Dynamic Bidding Rules
                            if current_bid >= 100:
                                increment = 10
                            elif current_bid >= 50:
                                increment = 5
                            else:
                                increment = 1
                            
                            min_bid = max(5, current_bid + increment)
                            max_bid_allowed = bidder.get('budget', 0)
                            
                            step_val = 10 if min_bid >= 100 else (5 if min_bid >= 50 else 1)
                            
                            if max_bid_allowed >= min_bid:
                                bid_amount = st.number_input(
                                    f"Bid (Min: {int(min_bid)}M)", 
                                    min_value=int(min_bid), 
                                    max_value=int(max_bid_allowed),
                                    value=int(min_bid),
                                    step=step_val,
                                    format="%d",
                                    key=f"bid_input_{current_player}_uniq"
                                )
                            else:
                                st.error(f"Low Budget")
                                bid_amount = 0
                        else:
                            bid_amount = 0

                    # Column 3: Actions
                    with col3:
                        # Bid Button
                        if st.button("🔨 BID!", type="primary", disabled=(bid_amount==0), key=f"bid_btn_{current_player}_uniq"):
                            live_auction['current_bid'] = bid_amount
                            live_auction['current_bidder'] = bidder_name
                            live_auction['timer_start'] = get_ist_time().isoformat()
                            room['live_auction'] = live_auction
                            save_auction_data(auction_data)
                            st.rerun()
                        
                        st.write("") # Spacer
                        
                        # Actions: Success or Opt Out
                        # Helper: Check if I am the active bidder holding the bid
                        am_i_holding = my_participant and my_participant['name'] == current_bidder
                        
                        if am_i_holding:
                            st.success("👑 You hold the bid")
                        elif is_my_turn:
                            if st.button("❌ Opt Out", key=f"optout_btn_{current_player}_uniq"):
                                live_auction.setdefault('opted_out', []).append(my_participant['name'])
                                room['live_auction'] = live_auction
                                save_auction_data(auction_data)
                                st.rerun()


            # Admin Override Flags
            force_sell = False
            force_unsold = False
            
            # Admin controls (Pause / Force Sell)
            if is_admin:
                st.divider()
                with st.expander("🔧 Admin Controls"):
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        if st.button("⏸️ Pause"):
                            live_auction['active'] = False
                            room['live_auction'] = live_auction
                            save_auction_data(auction_data)
                            st.rerun()
                    with c2:
                        if st.button("🔨 Force SELL", disabled=(current_bid == 0)):
                            force_sell = True
                    with c3:
                        if st.button("⏩ Force UNSOLD"):
                            force_unsold = True
                    
                    # Revive Bidder Logic
                    current_opted_out = live_auction.get('opted_out', [])
                    if current_opted_out:
                        st.write("---")
                        st.markdown("##### ♻️ Revive Bidder")
                        rc1, rc2 = st.columns([3, 1])
                        revive_target = rc1.selectbox("Select Bidder", current_opted_out, key="revive_select")
                        if rc2.button("Revive"):
                            if revive_target in live_auction['opted_out']:
                                live_auction['opted_out'].remove(revive_target)
                                room['live_auction'] = live_auction
                                save_auction_data(auction_data)
                                st.success(f"Revived {revive_target}!")
                                import time
                                time.sleep(1)
                                st.rerun()
                    
                    st.write("---")
                    if st.button("💸 Boost All Budgets (+150M)"):
                        # One-time migration for existing rooms
                        for p in room['participants']:
                            p['budget'] = p.get('budget', 0) + 150
                        save_auction_data(auction_data)
                        st.success("✅ Added 150M to everyone's budget!")
                        import time
                        time.sleep(1)
                        st.rerun()

            # Handle Sale / Unsold
            if should_autosell or force_sell:
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

            elif should_autopass or force_unsold:
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
            

            
            # Auto-refresh loop for everyone
            if not should_autosell and not should_autopass:
                import time
                time.sleep(1)
                st.rerun()




def show_main_app():
    inject_custom_css() # Apply Aesthetics
    
    # === GLOBAL BROADCASTER HEADER ===
    st.markdown("""
    <div style="display: flex; align-items: center; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid rgba(255,255,255,0.1); margin-bottom: 20px;">
        <div style="display: flex; align-items: center; gap: 15px;">
            <div style="font-size: 2.5rem; filter: drop-shadow(0 0 10px rgba(0,255,153,0.5));">🏆</div>
            <div>
                <h3 style="margin: 0; font-family: 'Orbitron', sans-serif; color: #fff; line-height: 1.2; font-size: 1.4rem;">T20 WORLD CUP <span style="color: #00FF99;">2026</span></h3>
                <div style="color: #8b949e; font-size: 0.75rem; letter-spacing: 3px; font-weight: 600;">OFFICIAL AUCTION TERMINAL</div>
            </div>
        </div>
        <div style="display: flex; align-items: center; gap: 15px;">
            <div class="live-badge" style="background: rgba(255,0,0,0.8); backdrop-filter: blur(5px);">LIVE SIGNAL 📡</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    user = st.session_state.logged_in_user
    room_code = st.session_state.current_room
    room = auction_data['rooms'].get(room_code)
    
    if not room:
        st.error("Room not found!")
        st.session_state.current_room = None
        st.rerun()
        return
    
    is_admin = room['admin'] == user
    
    # === TEAM ASSIGNMENT LOGIC (Auto-Match or Claim) ===
    # 1. Check if user is already managing a team
    my_p = next((p for p in room['participants'] if p.get('user') == user), None)
    
    if not my_p:
        # 2. Try Auto-Match (Username == Participant Name)
        # Look for UNCLAIMED participant with exact name match
        auto_match = next((p for p in room['participants'] if p['name'] == user and p.get('user') is None), None)
        
        if auto_match:
            auto_match['user'] = user
            save_auction_data(auction_data)
            st.toast(f"✅ Recognized you as **{auto_match['name']}**. Auto-assigned!")
            time.sleep(1)
            st.rerun()
            return

        # 3. If still no team, FORCE CLAIM (Blocking UI)
        # Check for any unclaimed teams
        unclaimed = [p['name'] for p in room['participants'] if p.get('user') is None]
        
        if unclaimed:
            st.container().warning(f"👋 Welcome, **{user}**! You are not linked to a team yet.")
            st.markdown("### 🛡️ Claim Your Squad")
            st.info("You must join one of the generated teams to continue.")
            
            selected_team = st.selectbox("Select which team belongs to you:", unclaimed, key="force_claim_sel")
            
            if st.button("🚀 Join Team & Enter Room", type="primary"):
                p_claim = next((p for p in room['participants'] if p['name'] == selected_team), None)
                if p_claim:
                    p_claim['user'] = user
                    save_auction_data(auction_data)
                    st.success(f"Successfully joined as **{selected_team}**!")
                    st.rerun()
            
            st.image("https://media.giphy.com/media/l0HlHFRbmaX9ivvWw/giphy.gif", width=300) # Optional fun element
            return # BLOCK ACCESS until claimed
        else:
            # OPTIONAL: If no unclaimed teams left, maybe let them be a generic viewer or create a new team?
            # For now, we assume they must be one of the imported teams.
            if is_admin:
                st.warning("⚠️ You are Admin but not linked to a team. You can manage the room below.")
            else:
                st.error("🔒 Room is full or all teams are claimed. Please ask Admin.")
                if st.button("Refresh"): st.rerun()
                return

    # If we get here, 'my_p' is valid (or user is Admin bypassing check, though Admin usually has a team too)
    if my_p:
        # Update session for display if needed
        pass
    
    # --- Sidebar ---
    st.sidebar.title(f"🏏 {room['name']}")
    
    # Room Info
    # Room Info
    st.sidebar.markdown(f"**Room Code:** `{room_code}`")
    if is_admin:
        st.sidebar.success("👑 You are the Admin")
    else:
        st.sidebar.info(f"👑 Admin: {room['admin']}")
    
    st.sidebar.markdown(f"**Members:** {len(room['members'])}")

    # === CLAIM TEAM LOGIC ===
    my_p = next((p for p in room['participants'] if p.get('user') == user), None)
    if not my_p:
        # Check for unclaimed teams
        unclaimed = [p['name'] for p in room['participants'] if p.get('user') is None]
        if unclaimed:
            st.sidebar.divider()
            st.sidebar.warning("⚠️ You are not managing a team!")
            claim_name = st.sidebar.selectbox("Select Your Team", [""] + unclaimed, key="claim_team_sel")
            if claim_name and st.sidebar.button("Claim Team"):
                p_claim = next((p for p in room['participants'] if p['name'] == claim_name), None)
                if p_claim:
                    p_claim['user'] = user
                    save_auction_data(auction_data)
                    st.sidebar.success(f"You are now managing {claim_name}!")
                    st.rerun()
    else:
        st.sidebar.success(f"👤 Managing: **{my_p['name']}**")
    
    # Navigation
    st.sidebar.divider()
    page = st.sidebar.radio("Navigation", ["📊 Calculator", "👤 Squads & Trading", "📅 Schedule & Admin", "🏆 Standings"])
    
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
                        scraper = cricbuzz_scraper.CricbuzzScraper()
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
    # PAGE 2: Squads & Trading (Restored Features)
    # =====================================
    elif page == "👤 Squads & Trading":
        st.title("👤 Squads & Trading")
        
        # === TABS ===
        squad_tabs = st.tabs(["💰 Open Bidding", "🔄 Trading", "👤 Squads"])
        
        # ================ TAB 1: OPEN BIDDING ================
        with squad_tabs[0]:
            st.subheader("💰 Open Bidding")
            
            # Phase Check (Soft)
            is_bidding_active = room.get('game_phase', 'Bidding') == 'Bidding'
            if not is_bidding_active:
                st.warning(f"🔒 Bidding Disabled (Phase: {room.get('game_phase')})")

            # Helper: Get current participant info
            my_p_name_check = st.session_state.get('logged_in_user')
            my_participant = next((p for p in room['participants'] if p.get('user') == my_p_name_check or p['name'] == my_p_name_check), None)

            if my_participant and not is_admin:
                with st.expander("🚑 Manage Injury Reserve (IR)"):
                    st.info("Designating an IR player costs **2M** (deducted when squads lock). IR players get **0 points**.")
                    current_ir = my_participant.get('injury_reserve')
                    squad_names = [p['name'] for p in my_participant['squad']]
                    
                    # Add None option
                    opts = ["None"] + squad_names
                    def_idx = 0
                    if current_ir in squad_names:
                        def_idx = opts.index(current_ir)
                    
                    new_ir = st.selectbox("Select Injury Reserve Player", opts, index=def_idx, key="ir_select")
                    
                    if st.button("Save IR Choice"):
                        my_participant['injury_reserve'] = new_ir if new_ir != "None" else None
                        save_auction_data(auction_data)
                        st.success("Injury Reserve Updated!")
            
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
                    effective_expires = bid_expires
                    if global_deadline and global_deadline < bid_expires:
                            effective_expires = global_deadline
                    
                    time_left = effective_expires - now
                    minutes_left = max(0, time_left.total_seconds() / 60)
                    
                    bids_data.append({
                        "Player": bid['player'],
                        "Current Bid": f"{bid['amount']}M",
                        "Bidder": bid['bidder'],
                        "Time Left": f"{minutes_left/60:.1f} hours",
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
                    st.warning("No participants.")
            
            if current_participant:
                target_player = st.selectbox(
                    "Select Player", 
                    [""] + sorted(biddable_players), 
                    key="bid_player",
                    format_func=format_player_name
                )
                
                if target_player:
                    existing_bid = next((b for b in active_bids if b['player'] == target_player), None)
                    
                    min_bid = 5
                    if existing_bid:
                        curr_amt = float(existing_bid['amount'])
                        if curr_amt >= 100: interval = 10
                        elif curr_amt >= 50: interval = 5
                        else: interval = 1
                        min_bid = int(math.ceil(curr_amt + interval))
                    
                    step_val = 10 if min_bid >= 100 else (5 if min_bid >= 50 else 1)
                    bid_amount = st.number_input(f"Your Bid (Min {min_bid}M)", min_value=int(min_bid), step=step_val, format="%d", key="bid_input_val")
                    
                    if st.button("Place Bid", key="place_bid", disabled=not is_bidding_active):
                        if bid_amount > current_participant.get('budget', 0):
                            st.error(f"Insufficient budget! You have {current_participant.get('budget')}M.")
                        else:
                            # Remove old bid if exists
                            if existing_bid:
                                active_bids.remove(existing_bid)
                                st.toast(f"Outbid previous bid of {existing_bid['amount']}M!")
                            
                            expiry_time = now + timedelta(hours=24) 
                            
                            new_bid = {
                                'player': target_player,
                                'amount': int(bid_amount),
                                'bidder': current_participant['name'],
                                'expires': expiry_time.isoformat()
                            }
                            active_bids.append(new_bid)
                            room['active_bids'] = active_bids
                            save_auction_data(auction_data)
                            st.success(f"Bid placed on {target_player} for {bid_amount}M! Win in 24h.")
                            st.rerun()
            

            # --- Release Player Section ---
            st.divider()
            st.subheader("🔄 Manage Squad / Release Player")
            
            # We reuse current_participant from bidding logic if available
            if current_participant:
                st.caption(f"Managing Squad for: **{current_participant['name']}**")
                
                if current_participant['squad']:
                    # Calculate current gameweek (based on locked gameweeks)
                    locked_gws = list(room.get('gameweek_squads', {}).keys())
                    current_gw = max([int(gw) for gw in locked_gws]) if locked_gws else 0
                    
                    # Check if participant has used their paid release this GW
                    paid_releases = current_participant.get('paid_releases', {})
                    used_paid_this_gw = paid_releases.get(str(current_gw), False) if current_gw > 0 else False
                    
                    knocked_out_teams = set(room.get('knocked_out_teams', []))
                    player_country_lookup = {p['name']: p.get('country', 'Unknown') for p in players_db}
                    
                    remove_options = [p['name'] for p in current_participant['squad']]
                    player_to_remove = st.selectbox(
                        "Select Player to Release", 
                        [""] + remove_options, 
                        key="open_release_player",
                        format_func=format_player_name
                    )
                    
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
                                refund_amount = int(math.ceil(player_obj.get('buy_price', 0) / 2))
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
        
        # ================ TAB 2: TRADING ================
        with squad_tabs[1]:
            st.subheader("🔄 Trade Center")
            
            # Check Phase for Trading
            current_phase = room.get('game_phase', 'Bidding')
            if current_phase == 'Locked':
                st.info("🔒 Trading is currently LOCKED for Gameweek processing.")
            else:
                my_p_name = user
                if 'pending_trades' not in room: room['pending_trades'] = []
                prefill = st.session_state.pop('trade_prefill', None)
                
                # INBOX
                st.markdown("### 📬 Incoming Proposals")
                my_incoming = [t for t in room['pending_trades'] if t['to'] == my_p_name]
                if my_incoming:
                    for trade in my_incoming:
                        with st.container():
                            st.write(f"From **{trade['from']}**: {trade['type']} - {trade.get('player') or trade.get('give_player')}")
                            c1, c2 = st.columns(2)
                            if c1.button("✅ Accept", key=f"acc_{trade['id']}"):
                                sender = next((p for p in room['participants'] if p['name'] == trade['from']), None)
                                receiver = next((p for p in room['participants'] if p['name'] == trade['to']), None)
                                
                                success = False
                                if sender and receiver:
                                   if trade['type'] == "Transfer (Sell)":
                                       p_obj = next((p for p in sender['squad'] if p['name'] == trade['player']), None)
                                       if p_obj and receiver['budget'] >= trade['price']:
                                           sender['squad'].remove(p_obj)
                                           p_obj['buy_price'] = trade['price']
                                           receiver['squad'].append(p_obj)
                                           sender['budget'] += trade['price']
                                           receiver['budget'] -= trade['price']
                                           success = True
                                   # Simplified execution check for other types (would need expansion in real usage)
                                   # Assuming users mainly do simple transfers for now.
                                   elif trade['type'] == "Transfer (Buy)":
                                       p_obj = next((p for p in receiver['squad'] if p['name'] == trade['player']), None)
                                       if p_obj and sender['budget'] >= trade['price']:
                                           receiver['squad'].remove(p_obj)
                                           p_obj['buy_price'] = trade['price']
                                           sender['squad'].append(p_obj)
                                           sender['budget'] -= trade['price']
                                           success = True
                                   
                                   elif trade['type'] == "Exchange":
                                       # Sender GIVES 'give_player' and RECEIVES 'get_player'.
                                       # Sender PAYS 'price' (net cash).
                                       give_pl_name = trade['give_player']
                                       get_pl_name = trade['get_player']
                                       net_cash = trade['price']
                                       
                                       p_give = next((p for p in sender['squad'] if p['name'] == give_pl_name), None)
                                       p_get = next((p for p in receiver['squad'] if p['name'] == get_pl_name), None)
                                       
                                       if p_give and p_get:
                                           # Check budget if net_cash positive (Sender pays)
                                           if net_cash > 0 and sender['budget'] < net_cash:
                                               success = False
                                           # Check budget if net_cash negative (Receiver pays)
                                           elif net_cash < 0 and receiver['budget'] < abs(net_cash):
                                               success = False
                                           else:
                                               # Execute Swap
                                               sender['squad'].remove(p_give)
                                               receiver['squad'].remove(p_get)
                                               sender['squad'].append(p_get)
                                               receiver['squad'].append(p_give)
                                               
                                               # Cash
                                               sender['budget'] -= net_cash
                                               receiver['budget'] += net_cash
                                               success = True

                                   elif trade['type'] in ["Loan Out", "Loan In"]:
                                       # Loan Logic: Move player, but maybe mark as 'loaned'?
                                       # For simplicity in this version, we just move them.
                                       # Loan Out: Sender GIVES player, Receives FEE.
                                       # Loan In: Sender TAKES player, Pays FEE.
                                       
                                            current_gw = 0
                                            locked_gws = list(room.get('gameweek_squads', {}).keys())
                                            if locked_gws:
                                                current_gw = max([int(gw) for gw in locked_gws])
                                            
                                            # Loan Return: Next Gameweek (Current + 1)
                                            return_gw = current_gw + 1
                                            
                                            if trade['type'] == "Loan Out":
                                                pl_name = trade['player']
                                                fee = trade['price'] # Sender receives this
                                                p_obj = next((p for p in sender['squad'] if p['name'] == pl_name), None)
                                                
                                                if p_obj and receiver['budget'] >= fee:
                                                    sender['squad'].remove(p_obj)
                                                    
                                                    # Tag metadata
                                                    p_obj['loan_origin'] = sender['name']
                                                    p_obj['loan_expiry_gw'] = return_gw
                                                    
                                                    receiver['squad'].append(p_obj)
                                                    sender['budget'] += fee
                                                    receiver['budget'] -= fee
                                                    success = True

                                            elif trade['type'] == "Loan In":
                                                pl_name = trade['player']
                                                fee = trade['price'] # Sender PAYS this
                                                p_obj = next((p for p in receiver['squad'] if p['name'] == pl_name), None)
                                                
                                                if p_obj and sender['budget'] >= fee:
                                                    receiver['squad'].remove(p_obj)
                                                    
                                                    # Tag metadata
                                                    p_obj['loan_origin'] = receiver['name']
                                                    p_obj['loan_expiry_gw'] = return_gw
                                                    
                                                    sender['squad'].append(p_obj)
                                                    receiver['budget'] += fee
                                                    sender['budget'] -= fee
                                                    success = True
                                   
                                   if success:
                                       room['pending_trades'] = [t for t in room['pending_trades'] if t['id'] != trade['id']]
                                       save_auction_data(auction_data)
                                       st.success("Trade Executed!")
                                       st.rerun()
                                   else:
                                       st.error("Failed (Budget/Player missing)")
                            if c2.button("❌ Reject", key=f"rej_{trade['id']}"):
                                room['pending_trades'] = [t for t in room['pending_trades'] if t['id'] != trade['id']]
                                save_auction_data(auction_data)
                                st.rerun()
                else:
                    st.info("No incoming proposals.")
                
                st.divider()
                st.subheader("Send Proposal")
                
                parts = [p['name'] for p in room['participants']]
                to_p_name = st.selectbox("Offer To", [x for x in parts if x != my_p_name], key="tp_to")
                
                t_type = st.radio("Type", ["Transfer (Buy)", "Transfer (Sell)", "Exchange", "Loan"], horizontal=True, key="tp_type_simple")
                
                my_part = next((p for p in room['participants'] if p['name'] == my_p_name), None)
                their_part = next((p for p in room['participants'] if p['name'] == to_p_name), None)
                
                if my_part and their_part:
                    if t_type == "Transfer (Sell)":
                        pl = st.selectbox("Player to Sell", [p['name'] for p in my_part['squad']], key="sell_pl")
                        pr = st.number_input("Selling Price", 1, 500, 10, key="sell_pr")
                        if st.button("Send Offer"):
                            room['pending_trades'].append({
                                'id': str(uuid_lib.uuid4()), 'from': my_p_name, 'to': to_p_name,
                                'type': t_type, 'player': pl, 'price': pr,
                                'created_at': get_ist_time().isoformat()
                            })
                            save_auction_data(auction_data)
                            st.success("Proposal Sent!")
                            st.rerun()

                    elif t_type == "Transfer (Buy)":
                        pl = st.selectbox("Player to Buy", [p['name'] for p in their_part['squad']], key="buy_pl")
                        pr = st.number_input("Offer Price", 1, 500, 10, key="buy_pr")
                        if st.button("Send Offer"):
                            room['pending_trades'].append({
                                'id': str(uuid_lib.uuid4()), 'from': my_p_name, 'to': to_p_name,
                                'type': t_type, 'player': pl, 'price': pr,
                                'created_at': get_ist_time().isoformat()
                            })
                            save_auction_data(auction_data)
                            st.success("Proposal Sent!")
                            st.rerun()
                            
                    elif t_type == "Exchange":
                        c1, c2 = st.columns(2)
                        with c1:
                            give_pl = st.selectbox("You Give", [p['name'] for p in my_part['squad']], key="exch_give")
                        with c2:
                            get_pl = st.selectbox("You Get", [p['name'] for p in their_part['squad']], key="exch_get")
                        
                        net_cash = st.number_input("Net Cash Payment (from You to Them)", -500, 500, 0, help="Positive: You pay them. Negative: They pay you.")
                        
                        if st.button("Send Exchange Offer"):
                            room['pending_trades'].append({
                                'id': str(uuid_lib.uuid4()), 'from': my_p_name, 'to': to_p_name,
                                'type': t_type, 
                                'give_player': give_pl,
                                'get_player': get_pl,
                                'price': net_cash,
                                'created_at': get_ist_time().isoformat()
                            })
                            save_auction_data(auction_data)
                            st.success("Exchange Proposal Sent!")
                            st.rerun()

                    elif t_type == "Loan":
                        loan_dir = st.radio("Direction", ["Loan Out (You Give)", "Loan In (You Get)"], horizontal=True)
                        if loan_dir == "Loan Out (You Give)":
                            pl = st.selectbox("Player to Loan Out", [p['name'] for p in my_part['squad']], key="loan_out_pl")
                            fee = st.number_input("Loan Fee (They pay you)", 0, 100, 0, key="loan_fee_out")
                            if st.button("Offer Loan"):
                                room['pending_trades'].append({
                                    'id': str(uuid_lib.uuid4()), 'from': my_p_name, 'to': to_p_name,
                                    'type': "Loan Out", 'player': pl, 'price': fee,
                                    'created_at': get_ist_time().isoformat()
                                })
                                save_auction_data(auction_data)
                                st.success("Loan Offer Sent!")
                                st.rerun()
                        else:
                            pl = st.selectbox("Player to Loan In", [p['name'] for p in their_part['squad']], key="loan_in_pl")
                            fee = st.number_input("Loan Fee (You pay them)", 0, 100, 0, key="loan_fee_in")
                            if st.button("Request Loan"):
                                room['pending_trades'].append({
                                    'id': str(uuid_lib.uuid4()), 'from': my_p_name, 'to': to_p_name,
                                    'type': "Loan In", 'player': pl, 'price': fee,
                                    'created_at': get_ist_time().isoformat()
                                })
                                save_auction_data(auction_data)
                                st.success("Loan Request Sent!")
                                st.rerun()

        # ================ TAB 3: SQUADS DASHBOARD ================
        with squad_tabs[2]:
            st.subheader("👤 Squad Dashboard")
            
            # Auto-Refresh Toggle
            if st.button("🔄 Refresh Now"): st.rerun()

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
                c1, c2 = st.columns(2)
                with c1: sel_p = st.multiselect("Filter by Participant", [p['name'] for p in room['participants']])
                with c2: search = st.text_input("Search Player")
                
                if sel_p: df = df[df['Participant'].isin(sel_p)]
                if search: df = df[df['Player'].str.contains(search, case=False)]
                
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.info("No squads yet.")


    elif page == "📅 Schedule & Admin":
        st.title("📅 Schedule & Admin")
        
        # Load schedule
        schedule = load_schedule()
        
        st.markdown("View match schedule and gameweek data.")
        if not is_admin:
            st.info(f"👑 **Admin:** {room['admin']} (Only admin can process scores)")
        
        # Knocked-out Teams Admin (for Super 8s and beyond)
        if is_admin:
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
                                
            st.divider()
            st.divider()
            st.subheader("📥 Bulk Squad Import (CSV with Staging)")
            
            # Session State for Import Persistence
            if 'import_staging_df' not in st.session_state:
                st.session_state.import_staging_df = None
            if 'import_file_id' not in st.session_state:
                st.session_state.import_file_id = None
                
            uploaded_file = st.file_uploader("Upload Squads CSV", type=['csv'], key="admin_squad_import")
            
            # CLEAR/RESET Button
            if st.session_state.import_staging_df is not None:
                if st.button("🔄 Clear Staging Area / Upload New"):
                    st.session_state.import_staging_df = None
                    st.session_state.import_file_id = None
                    st.rerun()

            if uploaded_file is not None:
                # Check if this is a new file or we already have staged data
                file_id = f"{uploaded_file.name}_{uploaded_file.size}"
                
                # If new file, PARSE IT. If same file and data exists, SKIP PARSING.
                if st.session_state.import_file_id != file_id:
                    try:
                        df_in = pd.read_csv(uploaded_file, header=None) # Read without header to handle Row 0 manually
                        
                        matches = []
                        
                        # DETECT MODE
                        first_row = df_in.iloc[0].tolist()
                        potential_participants = {} # index -> Name
                        
                        # Scan Row 0 (skip blank cells)
                        for idx, val in enumerate(first_row):
                            if pd.isna(val) or str(val).strip() == '': continue
                            
                            val_str = str(val).strip()
                            p_match = next((p for p in room['participants'] if p['name'].lower() == val_str.lower()), None)
                            if p_match:
                                potential_participants[idx] = p_match['name']
                            else:
                                 potential_participants[idx] = val_str # Mark as Raw Name
                        
                        if potential_participants:
                            # Horizontal Mode Logic
                            start_row_idx = 2 
                            for r_idx in range(start_row_idx, len(df_in)):
                                row = df_in.iloc[r_idx]
                                for col_idx, p_name in potential_participants.items():
                                    pl_raw = row[col_idx]
                                    if pd.isna(pl_raw) or str(pl_raw).strip() == '': continue
                                    pl_raw = str(pl_raw).strip()
                                    
                                    if "remaining" in pl_raw.lower() or "budget" in pl_raw.lower(): continue
                                    
                                    price = 0
                                    if col_idx + 1 < len(df_in.columns):
                                        price_raw = row[col_idx + 1]
                                        try:
                                            if pd.notna(price_raw):
                                                price = float(str(price_raw).replace(',', '').replace('$',''))
                                        except: pass
                                    
                                    # Matches
                                    pl_match = pl_raw # Default
                                    status = "⚠️ Check"
                                    
                                    matches.append({
                                        "Row": r_idx + 1,
                                        "Participant (Matched)": p_name if any(p['name'] == p_name for p in room['participants']) else "UNKNOWN",
                                        "Participant (Raw)": p_name,
                                        "Player (Raw)": pl_raw,
                                        "Player (DB)": pl_match, # To be filled by fuzzy
                                        "Price": price,
                                        "Status": status
                                    })
                            
                            if matches:
                                import difflib
                                valid_parts = [p['name'] for p in room['participants']]
                                
                                # Auto-create Shadow Participants
                                found_parts_raw = set(m['Participant (Raw)'] for m in matches)
                                new_parts_created = []
                                for p_raw in found_parts_raw:
                                    if p_raw and p_raw not in valid_parts:
                                        # Create shadow participant
                                        new_p = {
                                            'name': p_raw.strip(),
                                            'budget': 100,
                                            'squad': [],
                                            'user': None
                                        }
                                        room['participants'].append(new_p)
                                        new_parts_created.append(p_raw)
                                if new_parts_created:
                                    save_auction_data(auction_data)
                                    st.toast(f"Created Auto-Teams: {', '.join(new_parts_created)}")
                                    
                                    # REFRESH valid_parts to include new ones
                                    valid_parts = [p['name'] for p in room['participants']]
                                    
                                    # UPDATE Matches to reflect new teams (Replace UNKNOWN)
                                    for m in matches:
                                        if m['Participant (Matched)'] == "UNKNOWN" and m['Participant (Raw)'] in valid_parts:
                                            m['Participant (Matched)'] = m['Participant (Raw)']

                                # Fuzzy Match Logic (Run ONCE during parse)
                                for m in matches:
                                    pl_raw = m['Player (Raw)']
                                    best_matches = difflib.get_close_matches(str(pl_raw), player_names, n=1, cutoff=0.5)
                                    if best_matches:
                                        m['Player (DB)'] = best_matches[0]
                                        m['Status'] = "⚠️ Fuzzy Match" if best_matches[0] != pl_raw else "✅ Exact"

                                # Store in Session State
                                st.session_state.import_staging_df = pd.DataFrame(matches)
                                st.session_state.import_file_id = file_id
                                st.rerun() # Rerun to display editor with fresh data

                    except Exception as e:
                         st.error(f"Error parsing CSV: {e}")

            # === DISPLAY STAGING AREA (From Session State) ===
            if st.session_state.import_staging_df is not None:
                st.divider()
                st.subheader("🕵️ Review & Edit (Staging Area)")
                st.info("✅ Data parsed and cached. Edits here will NOT be lost on refresh unless you clear/re-upload.")
                
                valid_parts = [p['name'] for p in room['participants']]
                
                # Bind Editor to Session State? No, just initialize from it.
                # Actually, to keep edits across reruns (if they click other buttons), we need logic.
                # But 'st.data_editor' maintains its own state if key is constant.
                # The issue before was 'uploaded_file' triggering a re-parse that overwrote the editor.
                # Now, re-parse is blocked by 'import_file_id' check.
                
                edited_df = st.data_editor(
                    st.session_state.import_staging_df,
                    column_config={
                        "Participant (Matched)": st.column_config.SelectboxColumn(
                            "Participant",
                            options=valid_parts + ["UNKNOWN"],
                            required=True
                        ),
                        "Player (DB)": st.column_config.SelectboxColumn(
                            "Player Name (DB)",
                            help="Select the valid player from Database",
                            options=sorted(player_names),
                            required=True,
                            width="large"
                        )
                    },
                    hide_index=True,
                    num_rows="dynamic",
                    use_container_width=True,
                    key="staging_editor_persist"
                )
                
                if st.button("✅ Confirm & Import Squads", type="primary"):
                    success = 0
                    import time
                    
                    if 'unsold_players' not in room:
                        all_owned = [pl['name'] for p in room['participants'] for pl in p['squad']]
                        room['unsold_players'] = [p for p in player_names if p not in all_owned]
                    
                    for _, row in edited_df.iterrows():
                        p_curr = row['Participant (Matched)']
                        pl_name = row['Player (DB)']
                        
                        if p_curr == "UNKNOWN" or not pl_name or pd.isna(pl_name): continue
                        pl_name = str(pl_name).strip()
                        
                        part_obj = next((p for p in room['participants'] if p['name'] == p_curr), None)
                        if part_obj:
                            # Dedupe
                            if any(x['name'] == pl_name for x in part_obj['squad']): continue
                            
                            info = player_info_map.get(pl_name, {})
                            part_obj['squad'].append({
                                'name': pl_name,
                                'role': info.get('role', 'Unknown'),
                                'active': True,
                                'buy_price': row['Price'],
                                'team': info.get('country', 'Unknown')
                            })
                            part_obj['budget'] -= row['Price']
                            
                            if pl_name in room['unsold_players']:
                                room['unsold_players'].remove(pl_name)
                                
                            success += 1
                    
                    save_auction_data(auction_data)
                    st.success(f"Finalized Import! Added {success} players.")
                    
                    # Updates Session State w/ latest edits to be safe? 
                    # Or just clear it to finish.
                    st.session_state.import_staging_df = None # Clear staging
                    st.session_state.import_file_id = None
                    time.sleep(2)
                    st.rerun()
            
            st.divider()
            with st.expander("⚠️ Danger Zone (Reset)"):
                 st.write("This will clear all participants and their squads. Use with caution.")
                 if st.button("🔄 Reset Room Data", type="primary"):
                    room['participants'] = []
                    room['gameweek_scores'] = {}
                    room['active_bids'] = []
                    room['unsold_players'] = []
                    save_auction_data(auction_data)
                    st.success("Room data reset! All participants and squads cleared.")
                    st.rerun()
        st.divider()
        
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
                    
                    locked_squads = room.get('gameweek_squads', {}).get(selected_gw, {})
                    if locked_squads:
                        st.success(f"✅ Squads are locked for GW {selected_gw}. {len(locked_squads)} participants locked.")
                        
                        # Show locked squads overview
                        with st.expander("View Locked Squads"):
                             for participant_name, squad_data in locked_squads.items():
                                 st.markdown(f"**{participant_name}** - {len(squad_data['squad'])} players, IR: {squad_data.get('injury_reserve', 'None')}")
                    else:
                        st.info("ℹ️ Squads have not been locked for this gameweek yet. Use the **Gameweek Manager** in the Sidebar/Auction Room to lock squads.")
                    
                    # Check if already processed
                    if selected_gw in room.get('gameweek_scores', {}):
                        st.warning(f"⚠️ Gameweek {selected_gw} has already been processed. Processing again will overwrite scores.")
                    
                    # Manual URL input for this gameweek (Admin Only)
                    if is_admin:
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
                                scraper = cricbuzz_scraper.CricbuzzScraper()
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
                                room.setdefault('gameweek_scores', {})[selected_gw] = all_scores
                                save_auction_data(auction_data)
                                
                                status.text("✅ Processing Complete!")
                                st.success(f"Gameweek {selected_gw} processed! {len(all_scores)} players scored.")
                                
                                # Process Loan Returns (End of this Gameweek)
                                returned_loans = []
                                current_gw_int = int(selected_gw)
                                
                                for p in room['participants']:
                                    to_remove = []
                                    for pl in p['squad']:
                                        expiry = pl.get('loan_expiry_gw')
                                        origin = pl.get('loan_origin')
                                        
                                        # If expiry matches current processed GW, return now
                                        if expiry and expiry == current_gw_int and origin:
                                            origin_p = next((x for x in room['participants'] if x['name'] == origin), None)
                                            if origin_p:
                                                to_remove.append(pl)
                                                # Clean metadata
                                                pl_ret = pl.copy()
                                                pl_ret.pop('loan_expiry_gw', None)
                                                pl_ret.pop('loan_origin', None)
                                                origin_p['squad'].append(pl_ret)
                                                returned_loans.append(f"{pl['name']} ({p['name']} -> {origin})")
                                    
                                    # Remove from borrower
                                    for tr in to_remove:
                                        p['squad'].remove(tr)
                                        
                                if returned_loans:
                                    st.info(f"↩️ Processed Loan Returns: {', '.join(returned_loans)}")
                                    save_auction_data(auction_data)
                                
                                # Show preview
                                st.subheader("📊 Scores Preview")
                                scores_df = pd.DataFrame([{"Player": k, "Points": v} for k, v in all_scores.items()])
                                scores_df = scores_df.sort_values(by="Points", ascending=False)
                                st.dataframe(scores_df.head(20), use_container_width=True, hide_index=True)
            else:
                st.warning("T20 WC Schedule not loaded.")
        
        with tab2:
            st.subheader("Manual URL Processing")
            if not is_admin:
                st.info("Manual score processing is restricted to the room admin.")
            else:
                manual_gw = st.number_input("Gameweek Number", min_value=1, max_value=10, value=1)
                manual_urls = st.text_area("Match URLs (one per line)", height=200, placeholder="https://www.cricbuzz.com/live-cricket-scorecard/...", key="manual_urls")
                
                if st.button("🚀 Process", type="primary", key="manual_process_btn"):
                    urls = [u.strip() for u in manual_urls.split('\n') if u.strip()]
                    
                    if not urls:
                        st.error("Please enter at least one URL.")
                    else:
                        scraper = cricbuzz_scraper.CricbuzzScraper()
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
                        
                        room.setdefault('gameweek_scores', {})[str(manual_gw)] = all_scores
                        save_auction_data(auction_data)
                        
                        status.text("✅ Processing Complete!")
                        st.success(f"Gameweek {manual_gw} processed! {len(all_scores)} players scored.")
        
        # Show processed gameweeks
        st.divider()
        st.subheader("📅 Processed Gameweeks")
        if room.get('gameweek_scores'):
            for gw, scores in sorted(room['gameweek_scores'].items(), key=lambda x: int(x[0]) if x[0].isdigit() else 0):
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
            st.info("No gameweeks have been processed yet. Go to Schedule & Admin to process matches.")
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
                import itertools
                
                # Active pool
                active_squad = [p for p in squad if p['name'] != ir_player]
                scored_players = []
                for p in active_squad: 
                    score = player_scores.get(p['name'], 0)
                    # Normalize Role
                    role_str = p.get('role', '').lower()
                    if 'wk' in role_str or 'wicket' in role_str: cat = 'WK'
                    elif 'allrounder' in role_str or 'ar' in role_str: cat = 'AR'
                    elif 'bat' in role_str: cat = 'BAT'
                    elif 'bowl' in role_str: cat = 'BWL'
                    else: cat = 'BAT'
                    
                    scored_players.append({'name': p['name'], 'role': p['role'], 'category': cat, 'score': score})
                
                if len(scored_players) <= 11:
                    return scored_players, [] # List of players, empty warnings
                
                # Brute force 11 from N
                scored_players.sort(key=lambda x: x['score'], reverse=True)
                
                valid_ranges = {
                    'WK': (1, 3),
                    'BAT': (1, 4),
                    'AR': (2, 6),
                    'BWL': (3, 4)
                }
                
                best_team = []
                best_score = -1
                
                # Optimization: Try to find a valid team starting from highest scorers
                # Given max squad 19, active 18, C(18,11) = 31824.
                for team in itertools.combinations(scored_players, 11):
                    counts = {'WK': 0, 'BAT': 0, 'AR': 0, 'BWL': 0}
                    current_score = 0
                    for p in team:
                        counts[p['category']] += 1
                        current_score += p['score']
                    
                    is_valid = True
                    for role, (min_v, max_v) in valid_ranges.items():
                        if not (min_v <= counts[role] <= max_v):
                            is_valid = False
                            break
                    
                    if is_valid:
                        if current_score > best_score:
                            best_score = current_score
                            best_team = list(team)
                
                if best_team:
                    return best_team, []
                else:
                    # Fallback to top 11 if no valid team
                    return scored_players[:11], ["⚠️ Could not satisfy role constraints (WK:1-3, BAT:1-4, AR:2-6, BWL:3-4). Showed top scorers instead."]
            
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
                
                best_11, warnings = get_best_11(squad, gw_scores, ir_player)
                total_points = sum(p['score'] for p in best_11)
                standings.append({
                    "Participant": participant['name'],
                    "Points": total_points,
                    "Best 11": ", ".join([f"{p['name']} ({p['score']:.0f})" for p in best_11[:3]]) + "...",
                    "Warnings": " ".join(warnings) if warnings else "OK"
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
                    best_11, warnings = get_best_11(detail_p['squad'], gw_scores, detail_p.get('ir_player'))
                    if warnings:
                        for w in warnings: st.warning(w)
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
# Auto-Login from URL (Persistence)
if st.session_state.logged_in_user is None:
    qp = st.query_params
    url_user = qp.get("user")
    url_room = qp.get("room")
    
    if url_user and url_room:
        # Validate existence
        if url_user in auction_data['users'] and url_room in auction_data['rooms']:
            st.session_state.logged_in_user = url_user
            st.session_state.current_room = url_room
            st.rerun()

if st.session_state.logged_in_user is None:
    show_login_page()
elif st.session_state.current_room is None:
    show_room_selection()
else:
    show_main_app()
