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
                    "participants": [],
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
                        user_data['rooms_joined'] = user_data.get('rooms_joined', []) + [join_code]
                        save_auction_data(auction_data)
                        st.success(f"Joined room: {room['name']}")
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
        
        # --- Add Participant (Admin Only) ---
        if is_admin:
            st.subheader("👤 Add New Participant")
            new_name = st.text_input("Participant Name", key="new_participant")
            if st.button("Add Participant"):
                participant_names = [p['name'] for p in room['participants']]
                if new_name and new_name not in participant_names:
                    room['participants'].append({
                        'name': new_name, 
                        'squad': [],  # [{name, role, buy_price}]
                        'ir_player': None,
                        'budget': 350  # 350M starting budget
                    })
                    save_auction_data(auction_data)
                    st.success(f"Added {new_name} with 350M budget!")
                    st.rerun()
                elif new_name:
                    st.warning("Participant already exists.")
            st.divider()
        
        # === AUCTION TABS ===
        auction_tabs = st.tabs(["🎯 Big Auction", "💰 Open Bidding", "🔄 Trading"])
        
        # ================ TAB 1: BIG AUCTION ================
        with auction_tabs[0]:
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
                        
                        # Release Player (get 50% back)
                        st.divider()
                        st.markdown("**🔄 Release Player (50% return)**")
                        remove_options = [p['name'] for p in participant['squad']]
                        player_to_remove = st.selectbox("Select Player to Release", remove_options, key="remove_player")
                        
                        # Find the player to get their buy_price
                        player_obj = next((p for p in participant['squad'] if p['name'] == player_to_remove), None)
                        refund_amount = player_obj.get('buy_price', 0) // 2 if player_obj else 0
                        
                        st.caption(f"Releasing will refund: **{refund_amount}M** (50% of buy price)")
                        
                        if st.button("🔓 Release Player"):
                            participant['squad'] = [p for p in participant['squad'] if p['name'] != player_to_remove]
                            participant['budget'] += refund_amount  # Return 50%
                            if participant.get('ir_player') == player_to_remove:
                                participant['ir_player'] = None
                            # Add to unsold pool for bidding
                            room.setdefault('unsold_players', []).append(player_to_remove)
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
        with auction_tabs[1]:
            st.subheader("💰 Open Bidding (Post-Auction)")
            
            if not room.get('big_auction_complete'):
                st.warning("⏳ Open Bidding will start after the Big Auction is complete. Admin must check 'Big Auction Complete' in sidebar.")
            else:
                st.info("📜 **Rules:** Min bid 5M. Over 50M: +5M increments. Hold for 24 hours to win.")
                
                # Process expired bids (auto-award to winners)
                now = datetime.now()
                active_bids = room.get('active_bids', [])
                awarded_bids = []
                
                for bid in active_bids:
                    expires = datetime.fromisoformat(bid['expires'])
                    if now >= expires:
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
        with auction_tabs[2]:
            st.subheader("🔄 Trading (Coming Soon)")
            
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
                                
                                if st.button("📝 Record Exchange"):
                                    p1_obj = next((p for p in from_p['squad'] if p['name'] == player1), None)
                                    p2_obj = next((p for p in to_p['squad'] if p['name'] == player2), None)
                                    if p1_obj and p2_obj:
                                        from_p['squad'].remove(p1_obj)
                                        to_p['squad'].remove(p2_obj)
                                        from_p['squad'].append(p2_obj)
                                        to_p['squad'].append(p1_obj)
                                        save_auction_data(auction_data)
                                        st.success(f"Exchange complete! {player1} ↔ {player2}")
                                        st.rerun()
                            else:
                                st.warning("Both participants need players for an exchange.")
                        
                        elif trade_type == "Loan (1 GW)":
                            st.info("🚧 Loan system is under development. Coming soon!")
                else:
                    st.warning("Need at least 2 participants for trading.")


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
