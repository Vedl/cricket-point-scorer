"""Fantasy Auction Platform — Reflex app (migration of the legacy Streamlit app).

Phase 2 pages: sign-up/login, room dashboard (create/join), admin room setup
(teams + PINs + CSV squad upload). The live auction room (/room) is a placeholder
filled in Phase 3.
"""

import reflex as rx

from . import theme
from .state import AppState
from .room_state import RoomState
from .season_state import SeasonState
from .trade_state import TradeState


# --------------------------------------------------------------------------- #
# Shared bits
# --------------------------------------------------------------------------- #
def _field(label: str, *control) -> rx.Component:
    return rx.vstack(
        rx.text(label, style={"color": theme.MUTED, "font_size": "0.85rem"}),
        *control,
        spacing="1",
        width="100%",
        align="start",
    )


def _error(msg) -> rx.Component:
    return rx.cond(
        msg != "",
        rx.callout(msg, color_scheme="red", size="1", margin_top="0.5rem"),
    )


def _topbar() -> rx.Component:
    return rx.hstack(
        rx.heading("🏏 Fantasy Auction", size="5", style={"color": theme.TEXT}),
        rx.spacer(),
        # Connection indicator — Reflex sets is_hydrated false while disconnected.
        rx.cond(
            ~AppState.is_hydrated,
            rx.hstack(rx.box(class_name="app-spinner",
                             style={"width": "16px", "height": "16px", "border_width": "2px"}),
                      rx.text("connecting…", style={"color": theme.MUTED, "font_size": "0.8rem"}),
                      spacing="2", align="center"),
        ),
        rx.cond(
            AppState.logged_in,
            rx.hstack(
                rx.text(AppState.auth_user, style={"color": theme.ACCENT}),
                rx.button("Logout", on_click=AppState.handle_logout, variant="soft", size="2"),
                align="center",
                spacing="3",
            ),
        ),
        width="100%",
        align="center",
        margin_bottom="1.5rem",
    )


# --------------------------------------------------------------------------- #
# Index / auth
# --------------------------------------------------------------------------- #
def auth_panel() -> rx.Component:
    login = rx.vstack(
        _field("Username", rx.input(value=AppState.username, on_change=AppState.set_field("username"),
                                    placeholder="Username", width="100%")),
        _field("Password", rx.input(value=AppState.password, on_change=AppState.set_field("password"),
                                    placeholder="Password", type="password", width="100%")),
        theme.primary_button("Log in", on_click=AppState.handle_login, width="100%",
                             margin_top="0.5rem"),
        spacing="3", width="100%",
    )
    signup = rx.vstack(
        _field("Choose a username", rx.input(value=AppState.username,
               on_change=AppState.set_field("username"), placeholder="Username", width="100%")),
        _field("Create a password", rx.input(value=AppState.password,
               on_change=AppState.set_field("password"), placeholder="Min 4 characters",
               type="password", width="100%")),
        _field("Confirm password", rx.input(value=AppState.confirm,
               on_change=AppState.set_field("confirm"), placeholder="Re-enter password",
               type="password", width="100%")),
        theme.primary_button("Create account", on_click=AppState.handle_signup,
                             width="100%", margin_top="0.5rem"),
        spacing="3", width="100%",
    )
    return theme.card(
        rx.tabs.root(
            rx.tabs.list(
                rx.tabs.trigger("Log in", value="login"),
                rx.tabs.trigger("Sign up", value="signup"),
            ),
            rx.tabs.content(login, value="login", padding_top="1.25rem"),
            rx.tabs.content(signup, value="signup", padding_top="1.25rem"),
            default_value="login",
        ),
        _error(AppState.auth_error),
        width="100%",
        max_width="420px",
    )


def index() -> rx.Component:
    return theme.page_shell(
        rx.center(
            rx.vstack(
                theme.hero("Fantasy Auction", "Build your dream team with live, real-time bidding."),
                auth_panel(),
                align="center",
                spacing="4",
            ),
            min_height="80vh",
        )
    )


# --------------------------------------------------------------------------- #
# Rooms dashboard
# --------------------------------------------------------------------------- #
def create_room_card() -> rx.Component:
    return theme.card(
        rx.heading("➕ Create a room", size="5", style={"color": theme.TEXT},
                   margin_bottom="1rem"),
        rx.vstack(
            _field("Room name", rx.input(value=AppState.new_room_name,
                   on_change=AppState.set_field("new_room_name"), placeholder="e.g. Friends League",
                   width="100%")),
            _field("Tournament", rx.select(AppState.tournaments, value=AppState.new_tournament,
                   on_change=AppState.set_field("new_tournament"), width="100%")),
            rx.checkbox("I'll participate as a team manager (not admin-only)",
                        checked=AppState.admin_participating,
                        on_change=AppState.set_field("admin_participating")),
            theme.primary_button("Create room", on_click=AppState.handle_create_room,
                                 width="100%", margin_top="0.5rem"),
            _error(AppState.create_error),
            spacing="3", width="100%",
        ),
        width="100%",
    )


def join_room_card() -> rx.Component:
    return theme.card(
        rx.heading("🔗 Join a room", size="5", style={"color": theme.TEXT},
                   margin_bottom="1rem"),
        rx.vstack(
            _field("Room code", rx.input(value=AppState.join_code,
                   on_change=AppState.set_field("join_code"), placeholder="e.g. ABC123", width="100%")),
            _field("Team name", rx.input(value=AppState.join_team,
                   on_change=AppState.set_field("join_team"), placeholder="Your team's name", width="100%")),
            _field("Team PIN", rx.input(value=AppState.join_pin,
                   on_change=AppState.set_field("join_pin"), placeholder="PIN for your team",
                   type="password", width="100%")),
            theme.primary_button("Join room", on_click=AppState.handle_join,
                                 width="100%", margin_top="0.5rem"),
            _error(AppState.join_error),
            spacing="3", width="100%",
        ),
        width="100%",
    )


def room_row(room: rx.Var) -> rx.Component:
    return rx.table.row(
        rx.table.cell(room["name"]),
        rx.table.cell(rx.code(room["code"])),
        rx.table.cell(room["tournament"]),
        rx.table.cell(rx.badge(room["role"])),
        rx.table.cell(room["teams"]),
        rx.table.cell(
            rx.hstack(
                rx.link("Enter", href="/room?room=" + room["code"].to(str)),
                rx.cond(
                    room["role"] == "Admin",
                    rx.link("Setup", href="/setup?room=" + room["code"].to(str)),
                ),
                spacing="3",
            )
        ),
    )


def rooms_page() -> rx.Component:
    return theme.page_shell(
        _topbar(),
        theme.hero("Your rooms", "Create a new auction room or join one with a code + team PIN."),
        rx.grid(create_room_card(), join_room_card(),
                columns=rx.breakpoints(initial="1", md="2"), spacing="4", width="100%"),
        rx.box(height="2rem"),
        rx.heading("📋 Your rooms", size="5", style={"color": theme.TEXT}, margin_bottom="0.75rem"),
        rx.cond(
            AppState.my_rooms.length() > 0,
            theme.card(
                rx.table.root(
                    rx.table.header(
                        rx.table.row(
                            rx.table.column_header_cell("Room"),
                            rx.table.column_header_cell("Code"),
                            rx.table.column_header_cell("Tournament"),
                            rx.table.column_header_cell("Role"),
                            rx.table.column_header_cell("Teams"),
                            rx.table.column_header_cell(""),
                        )
                    ),
                    rx.table.body(rx.foreach(AppState.my_rooms, room_row)),
                    width="100%",
                ),
                width="100%",
            ),
            rx.text("You haven't created or joined any rooms yet.",
                    style={"color": theme.MUTED}),
        ),
    )


# --------------------------------------------------------------------------- #
# Room setup (admin)
# --------------------------------------------------------------------------- #
def team_row(team: rx.Var) -> rx.Component:
    return rx.table.row(
        rx.table.cell(team["name"]),
        rx.table.cell(rx.code(team["pin"])),
        rx.table.cell(team["claimed"]),
        rx.table.cell(team["budget"] + "M"),
        rx.table.cell(team["squad"]),
    )


def setup_page() -> rx.Component:
    admin_view = rx.vstack(
        theme.hero(
            "Room setup",
            "Add teams with PINs, then share the room code + each team's PIN. "
            "Upload a CSV to populate the player pool (FIFA) or pre-assign squads.",
        ),
        rx.hstack(
            rx.badge("Code: " + AppState.room_code, size="2"),
            rx.badge(AppState.room_tournament, size="2", color_scheme="cyan"),
            rx.badge("Pool: " + AppState.pool_count.to(str) + " players", size="2"),
            spacing="3",
        ),
        rx.box(height="1rem"),
        rx.grid(
            theme.card(
                rx.heading("👥 Teams", size="5", style={"color": theme.TEXT},
                           margin_bottom="0.75rem"),
                rx.hstack(
                    rx.input(value=AppState.new_team_name, on_change=AppState.set_field("new_team_name"),
                             placeholder="Team name"),
                    rx.input(value=AppState.new_team_pin, on_change=AppState.set_field("new_team_pin"),
                             placeholder="PIN"),
                    theme.primary_button("Add", on_click=AppState.handle_add_team),
                    spacing="2", width="100%",
                ),
                _error(AppState.setup_msg),
                rx.box(height="0.75rem"),
                rx.cond(
                    AppState.teams.length() > 0,
                    rx.table.root(
                        rx.table.header(
                            rx.table.row(
                                rx.table.column_header_cell("Team"),
                                rx.table.column_header_cell("PIN"),
                                rx.table.column_header_cell("Claimed by"),
                                rx.table.column_header_cell("Budget"),
                                rx.table.column_header_cell("Squad"),
                            )
                        ),
                        rx.table.body(rx.foreach(AppState.teams, team_row)),
                        width="100%",
                    ),
                    rx.text("No teams yet — add one above.", style={"color": theme.MUTED}),
                ),
                width="100%",
            ),
            theme.card(
                rx.heading("📥 Upload squads (CSV)", size="5", style={"color": theme.TEXT},
                           margin_bottom="0.75rem"),
                rx.text(
                    "Pool format: Player,Role,Team,BasePrice  •  "
                    "Roster format: Participant,Player,Role,Team,Price",
                    style={"color": theme.MUTED, "font_size": "0.8rem"},
                ),
                rx.box(height="0.5rem"),
                rx.upload(
                    rx.vstack(
                        rx.icon("upload", size=28, color=theme.ACCENT),
                        rx.text("Drag a .csv here or click to browse"),
                        align="center", spacing="2",
                    ),
                    id="csv_upload",
                    accept={"text/csv": [".csv"]},
                    max_files=1,
                    border=f"1px dashed {theme.BORDER}",
                    padding="1.5rem",
                    border_radius="12px",
                    width="100%",
                ),
                rx.text(rx.selected_files("csv_upload"), style={"color": theme.MUTED,
                        "font_size": "0.8rem"}),
                rx.hstack(
                    theme.primary_button(
                        "Upload",
                        on_click=AppState.handle_upload(rx.upload_files(upload_id="csv_upload")),
                    ),
                    rx.button("Clear", variant="soft",
                              on_click=rx.clear_selected_files("csv_upload")),
                    spacing="3", margin_top="0.75rem",
                ),
                _error(AppState.upload_msg),
                width="100%",
            ),
            columns=rx.breakpoints(initial="1", md="2"), spacing="4", width="100%",
        ),
        rx.box(height="1.5rem"),
        rx.hstack(
            rx.link("← Back to rooms", href="/rooms", style={"color": theme.MUTED}),
            rx.spacer(),
            theme.primary_button("Go to auction room →", on_click=AppState.go_to_room),
            width="100%",
        ),
        width="100%",
        spacing="2",
    )
    return theme.page_shell(
        _topbar(),
        rx.cond(
            AppState.is_admin,
            admin_view,
            rx.callout("Only the room admin can access setup.", color_scheme="amber"),
        ),
    )


# --------------------------------------------------------------------------- #
# Auction room (Phase 3)
# --------------------------------------------------------------------------- #
def _status_pill(text, color) -> rx.Component:
    return rx.box(text, style={"background": color, "color": "white", "padding": "2px 10px",
                               "border_radius": "999px", "font_size": "0.7rem", "font_weight": "700"})


def featured_card() -> rx.Component:
    return theme.card(
        rx.vstack(
            rx.hstack(
                rx.text(RoomState.current_team, style={"color": theme.ACCENT, "font_weight": "700"}),
                rx.spacer(),
                rx.badge(RoomState.current_role, color_scheme="cyan"),
                width="100%",
            ),
            rx.heading(RoomState.current_player, size="8", style={"color": theme.TEXT}),
            rx.hstack(
                rx.vstack(
                    rx.text("CURRENT BID", style={"color": theme.MUTED, "font_size": "0.7rem"}),
                    rx.heading(RoomState.current_bid.to_string() + "M", size="7",
                               style={"color": theme.SUCCESS}),
                    spacing="0", align="start",
                ),
                rx.spacer(),
                rx.vstack(
                    rx.text("TOP BIDDER", style={"color": theme.MUTED, "font_size": "0.7rem"}),
                    rx.heading(
                        rx.cond(RoomState.current_bidder != "", RoomState.current_bidder, "—"),
                        size="6", style={"color": theme.TEXT}),
                    spacing="0", align="end",
                ),
                width="100%", align="end",
            ),
            # timer bar (pulses when under 10s)
            rx.box(
                rx.box(style={"width": RoomState.timer_pct, "height": "100%",
                              "background": f"linear-gradient(90deg,{theme.PRIMARY},{theme.ACCENT})",
                              "transition": "width 0.35s linear"}),
                class_name=rx.cond(RoomState.time_left <= 10, "timer-urgent", ""),
                style={"width": "100%", "height": "8px", "background": "rgba(255,255,255,0.08)",
                       "border_radius": "999px", "overflow": "hidden", "margin_top": "0.5rem"},
            ),
            rx.text("⏱️ " + RoomState.time_left.to_string() + "s", style={"color": theme.MUTED}),
            spacing="3", width="100%", align="start",
        ),
        width="100%",
    )


def bid_panel() -> rx.Component:
    return theme.card(
        rx.heading("🎯 Place a bid", size="5", style={"color": theme.TEXT}, margin_bottom="0.5rem"),
        rx.cond(
            RoomState.is_admin,
            _field("Bid as", rx.select(RoomState.team_names, value=RoomState.bid_as,
                   on_change=RoomState.set_field("bid_as"), width="100%")),
            rx.text("Bidding as: " + RoomState.bid_as, style={"color": theme.ACCENT}),
        ),
        rx.text("Min next bid: " + RoomState.min_bid.to_string() + "M",
                style={"color": theme.MUTED, "font_size": "0.8rem"}),
        rx.hstack(
            rx.input(value=RoomState.bid_amount, on_change=RoomState.set_field("bid_amount"),
                     placeholder=RoomState.min_bid.to_string(), type="number", width="50%"),
            theme.primary_button("🔨 BID", on_click=RoomState.place_bid),
            width="100%", spacing="2",
        ),
        rx.hstack(
            rx.button("+ Min bid", on_click=RoomState.quick_bid, variant="soft"),
            rx.button("Opt out", on_click=RoomState.opt_out, variant="soft", color_scheme="gray"),
            spacing="2", margin_top="0.5rem",
        ),
        width="100%",
    )


def admin_controls() -> rx.Component:
    return theme.card(
        rx.heading("🔧 Admin", size="5", style={"color": theme.TEXT}, margin_bottom="0.5rem"),
        rx.hstack(
            rx.cond(
                RoomState.is_paused,
                rx.button("▶️ Resume", on_click=RoomState.admin_resume, variant="soft"),
                rx.button("⏸️ Pause", on_click=RoomState.admin_pause, variant="soft"),
            ),
            rx.button("🔨 Force sell", on_click=RoomState.admin_force_sell, variant="soft",
                      color_scheme="green"),
            rx.button("⏭️ Force unsold", on_click=RoomState.admin_force_unsold, variant="soft",
                      color_scheme="amber"),
            rx.button("↩️ Undo", on_click=RoomState.admin_undo, variant="soft",
                      color_scheme="red", disabled=~RoomState.can_undo),
            spacing="2", wrap="wrap",
        ),
        rx.cond(
            RoomState.opted_out_names.length() > 0,
            rx.hstack(
                rx.text("Revive:", style={"color": theme.MUTED}),
                rx.foreach(
                    RoomState.opted_out_names,
                    lambda n: rx.button(n, size="1", variant="surface",
                                        on_click=RoomState.revive(n)),
                ),
                spacing="2", margin_top="0.5rem", wrap="wrap",
            ),
        ),
        width="100%",
    )


def participant_card(p: rx.Var) -> rx.Component:
    return rx.box(
        rx.hstack(
            rx.text(p["name"], style={"color": theme.TEXT, "font_weight": "600"}),
            rx.spacer(),
            rx.match(
                p["status"],
                ("holding", _status_pill("LEADING", theme.SUCCESS)),
                ("out", _status_pill("OUT", theme.DANGER)),
                _status_pill("ACTIVE", theme.PRIMARY),
            ),
            width="100%",
        ),
        rx.hstack(
            rx.text("💰 " + p["budget"] + "M", style={"color": theme.ACCENT, "font_family": theme.MONO}),
            rx.spacer(),
            rx.text("🦅 " + p["squad"], style={"color": theme.MUTED}),
            width="100%",
        ),
        style={"background": theme.SURFACE_2, "border": f"1px solid {theme.BORDER}",
               "border_radius": "10px", "padding": "0.75rem"},
    )


def lobby_team_card(t: rx.Var) -> rx.Component:
    return rx.box(
        rx.hstack(
            rx.text(t["name"], style={"color": theme.TEXT, "font_weight": "600"}),
            rx.spacer(),
            rx.cond(
                t["claimed"] == "yes",
                _status_pill("✓ " + t["claimed_by"], theme.SUCCESS),
                _status_pill("OPEN", theme.MUTED),
            ),
            width="100%",
        ),
        rx.hstack(
            rx.text("💰 " + t["budget"] + "M", style={"color": theme.ACCENT, "font_family": theme.MONO,
                    "font_size": "0.85rem"}),
            rx.spacer(),
            rx.text("🦅 " + t["squad"], style={"color": theme.MUTED, "font_size": "0.85rem"}),
            width="100%",
        ),
        style={"background": theme.SURFACE_2, "border": f"1px solid {theme.BORDER}",
               "border_radius": "10px", "padding": "0.75rem"},
    )


def lobby_view() -> rx.Component:
    return theme.card(
        rx.hstack(
            rx.heading("👥 Lobby", size="5", style={"color": theme.TEXT}),
            rx.spacer(),
            rx.badge(RoomState.members_count.to_string() + " joined", size="2"),
            rx.badge(RoomState.pool_count.to_string() + " players in pool", size="2",
                     color_scheme="cyan"),
            width="100%", align="center",
        ),
        rx.text("Teams — share the room code + each team's PIN so managers can claim theirs.",
                style={"color": theme.MUTED, "font_size": "0.85rem"}, margin_y="0.5rem"),
        rx.cond(
            RoomState.lobby.length() > 0,
            rx.grid(rx.foreach(RoomState.lobby, lobby_team_card),
                    columns=rx.breakpoints(initial="1", sm="2", md="3"), spacing="3",
                    width="100%"),
            rx.text("No teams set up yet.", style={"color": theme.MUTED}),
        ),
        width="100%",
    )


def start_panel() -> rx.Component:
    admin_start = theme.card(
        rx.heading("🎬 Start the auction", size="5", style={"color": theme.TEXT},
                   margin_bottom="0.5rem"),
        rx.text("Pick a team to put their players up for bidding, one by one.",
                style={"color": theme.MUTED}),
        rx.hstack(
            rx.select(
                RoomState.available_team_names,
                value=RoomState.selected_team,
                placeholder="Select a team",
                on_change=RoomState.set_field("selected_team"),
                width="60%",
            ),
            theme.primary_button("🚀 Start", on_click=RoomState.start_team),
            spacing="2", width="100%", margin_top="0.5rem",
        ),
        width="100%",
    )
    waiting = theme.card(
        rx.vstack(
            rx.heading("📡 Waiting for the admin…", size="5", style={"color": theme.TEXT}),
            rx.text("The auction will begin shortly. Hang tight — the lobby updates live.",
                    style={"color": theme.MUTED}),
            spacing="2", align="start",
        ),
        width="100%",
    )
    return rx.vstack(
        rx.cond(RoomState.is_admin, admin_start, waiting),
        lobby_view(),
        spacing="4", width="100%",
    )


def room_page() -> rx.Component:
    return theme.page_shell(
        _topbar(),
        rx.hstack(
            rx.heading(RoomState.room_name, size="6", style={"color": theme.TEXT}),
            rx.badge("Code: " + RoomState.room_code, size="2"),
            rx.badge(RoomState.tournament, size="2", color_scheme="cyan"),
            rx.badge(RoomState.queue_count.to_string() + " in queue", size="2"),
            rx.spacer(),
            rx.link("📊 Standings", href="/standings?room=" + RoomState.room_code,
                    on_click=RoomState.stop_watching, style={"color": theme.ACCENT}),
            rx.link("🤝 Trade", href="/trade?room=" + RoomState.room_code,
                    on_click=RoomState.stop_watching, style={"color": theme.ACCENT}),
            rx.link("← Rooms", href="/rooms", on_click=RoomState.stop_watching,
                    style={"color": theme.MUTED}),
            width="100%", align="center", spacing="3", wrap="wrap",
        ),
        rx.cond(RoomState.message != "",
                rx.callout(RoomState.message, color_scheme="amber", size="1", margin_y="0.5rem")),
        # Animated SOLD banner (Phase 5)
        rx.cond(
            RoomState.flash_msg != "",
            rx.box(
                rx.text("🔨 " + RoomState.flash_msg,
                        style={"color": "white", "font_weight": "800", "font_size": "1.1rem"}),
                class_name="sold-banner",
                style={"background": f"linear-gradient(90deg,{theme.SUCCESS},{theme.ACCENT})",
                       "padding": "0.75rem 1.25rem", "border_radius": "12px",
                       "text_align": "center", "margin": "0.5rem 0"},
            ),
        ),
        rx.box(height="1rem"),
        rx.cond(
            RoomState.is_idle,
            start_panel(),
            rx.grid(
                rx.vstack(
                    featured_card(),
                    bid_panel(),
                    rx.cond(RoomState.is_admin, admin_controls()),
                    spacing="4", width="100%",
                ),
                rx.vstack(
                    theme.card(
                        rx.heading("👥 Teams", size="5", style={"color": theme.TEXT},
                                   margin_bottom="0.5rem"),
                        rx.vstack(rx.foreach(RoomState.participants, participant_card),
                                  spacing="2", width="100%"),
                        width="100%",
                    ),
                    theme.card(
                        rx.heading("📜 Bid log", size="5", style={"color": theme.TEXT},
                                   margin_bottom="0.5rem"),
                        rx.vstack(
                            rx.foreach(RoomState.log,
                                       lambda e: rx.text(e["text"], style={"color": theme.MUTED,
                                                         "font_size": "0.85rem"})),
                            spacing="1", width="100%", align="start",
                        ),
                        width="100%",
                    ),
                    spacing="4", width="100%",
                ),
                columns=rx.breakpoints(initial="1", md="2"), spacing="4", width="100%",
            ),
        ),
    )


# --------------------------------------------------------------------------- #
# Standings + gameweek management (Phase 8)
# --------------------------------------------------------------------------- #
def _rank_table(rows, *, show_warn=False) -> rx.Component:
    def row(item):
        cells = [
            rx.table.row_header_cell(item["participant"]),
            rx.table.cell(item["points"] + " pts"),
        ]
        if show_warn:
            cells.append(rx.table.cell(item["warn"]))
        return rx.table.row(*cells)

    headers = [rx.table.column_header_cell("Team"), rx.table.column_header_cell("Points")]
    if show_warn:
        headers.append(rx.table.column_header_cell(""))
    return rx.table.root(
        rx.table.header(rx.table.row(*headers)),
        rx.table.body(rx.foreach(rows, row)),
        width="100%",
    )


def gameweek_admin_panel() -> rx.Component:
    return theme.card(
        rx.heading("⚙️ Gameweek admin", size="5", style={"color": theme.TEXT},
                   margin_bottom="0.5rem"),
        rx.hstack(
            rx.text("Current gameweek:", style={"color": theme.MUTED}),
            rx.badge("GW " + SeasonState.current_gameweek, size="2"),
            rx.button("⏭️ Advance", on_click=SeasonState.advance_gw, variant="soft", size="2"),
            spacing="3", align="center",
        ),
        rx.divider(margin_y="0.75rem"),
        _field("Gameweek to edit", rx.input(value=SeasonState.gw_input,
               on_change=SeasonState.set_field("gw_input"), width="120px")),
        rx.text("Paste scores, one per line:  Player Name, points",
                style={"color": theme.MUTED, "font_size": "0.8rem"}, margin_top="0.5rem"),
        rx.text_area(value=SeasonState.scores_text, on_change=SeasonState.set_field("scores_text"),
                     placeholder="Virat Kohli, 72\nJasprit Bumrah, 45", rows="6", width="100%"),
        rx.hstack(
            theme.primary_button("💾 Save scores", on_click=SeasonState.save_scores),
            rx.button("🔒 Lock squads for GW", on_click=SeasonState.lock_squads, variant="soft"),
            spacing="3", margin_top="0.5rem",
        ),
        rx.divider(margin_y="0.75rem"),
        rx.heading("🏆 Knockout", size="4", style={"color": theme.TEXT}),
        rx.text("Eliminate the lowest scorers for the selected gameweek (above).",
                style={"color": theme.MUTED, "font_size": "0.8rem"}),
        rx.hstack(
            rx.text("Bottom", style={"color": theme.MUTED}),
            rx.input(value=SeasonState.knockout_count,
                     on_change=SeasonState.set_field("knockout_count"), width="70px"),
            rx.button("❌ Eliminate", on_click=SeasonState.do_eliminate, variant="soft",
                      color_scheme="red"),
            rx.button("↩️ Reverse last", on_click=SeasonState.reverse_elimination,
                      variant="soft"),
            spacing="3", align="center", margin_top="0.5rem",
        ),
        rx.cond(
            SeasonState.eliminated.length() > 0,
            rx.text("Eliminated: " + SeasonState.eliminated.join(", "),
                    style={"color": theme.DANGER, "font_size": "0.85rem"}, margin_top="0.4rem"),
        ),
        _error(SeasonState.msg),
        width="100%",
    )


def standings_page() -> rx.Component:
    return theme.page_shell(
        _topbar(),
        rx.hstack(
            rx.heading(SeasonState.room_name + " · Standings", size="6",
                       style={"color": theme.TEXT}),
            rx.spacer(),
            rx.link("← Room", href="/room?room=" + SeasonState.room_code,
                    style={"color": theme.MUTED}),
            width="100%", align="center",
        ),
        rx.box(height="1rem"),
        rx.grid(
            theme.card(
                rx.heading("🏆 Overall", size="5", style={"color": theme.TEXT},
                           margin_bottom="0.5rem"),
                rx.cond(SeasonState.cumulative.length() > 0,
                        _rank_table(SeasonState.cumulative),
                        rx.text("No scores entered yet.", style={"color": theme.MUTED})),
                width="100%",
            ),
            theme.card(
                rx.hstack(
                    rx.heading("📅 Gameweek", size="5", style={"color": theme.TEXT}),
                    rx.spacer(),
                    rx.select(SeasonState.gameweeks, value=SeasonState.selected_gw,
                              placeholder="GW", on_change=SeasonState.select_gw),
                    width="100%", align="center",
                ),
                rx.box(height="0.5rem"),
                rx.cond(SeasonState.gw_standings.length() > 0,
                        _rank_table(SeasonState.gw_standings, show_warn=True),
                        rx.text("Pick a gameweek with scores.", style={"color": theme.MUTED})),
                width="100%",
            ),
            columns=rx.breakpoints(initial="1", md="2"), spacing="4", width="100%",
        ),
        rx.box(height="1.5rem"),
        rx.cond(SeasonState.is_admin, gameweek_admin_panel()),
    )


# --------------------------------------------------------------------------- #
# Trading + open market (Phase 9)
# --------------------------------------------------------------------------- #
def _proposal_row(t: rx.Var, *, incoming: bool) -> rx.Component:
    actions = rx.cond(
        incoming,
        rx.hstack(
            rx.button("Accept", size="1", color_scheme="green",
                      on_click=TradeState.accept(t["id"])),
            rx.button("Reject", size="1", variant="soft", color_scheme="red",
                      on_click=TradeState.reject(t["id"])),
            spacing="2",
        ),
        rx.badge("pending", color_scheme="amber"),
    )
    return rx.hstack(
        rx.text(t["text"], style={"color": theme.TEXT, "font_size": "0.85rem"}),
        rx.spacer(), actions,
        width="100%", align="center",
        style={"background": theme.SURFACE_2, "border": f"1px solid {theme.BORDER}",
               "border_radius": "10px", "padding": "0.6rem 0.8rem"},
    )


def _market_row(p: rx.Var) -> rx.Component:
    return rx.hstack(
        rx.text(p["name"], style={"color": theme.TEXT}),
        rx.text(p["team"], style={"color": theme.MUTED, "font_size": "0.8rem"}),
        rx.spacer(),
        rx.cond(TradeState.is_admin,
                rx.button("Resolve", size="1", variant="soft",
                          on_click=TradeState.resolve(p["name"]))),
        width="100%", align="center",
        style={"background": theme.SURFACE_2, "border": f"1px solid {theme.BORDER}",
               "border_radius": "10px", "padding": "0.5rem 0.8rem"},
    )


def trade_page() -> rx.Component:
    propose_card = theme.card(
        rx.heading("🤝 Propose a trade", size="5", style={"color": theme.TEXT},
                   margin_bottom="0.5rem"),
        rx.grid(
            _field("With", rx.select(TradeState.other_teams, value=TradeState.counterparty,
                   placeholder="Team", on_change=TradeState.pick_counterparty, width="100%")),
            _field("You give", rx.select(TradeState.my_players, value=TradeState.give_player,
                   placeholder="(player)", on_change=TradeState.set_field("give_player"),
                   width="100%")),
            _field("You get", rx.select(TradeState.their_players, value=TradeState.get_player,
                   placeholder="(player)", on_change=TradeState.set_field("get_player"),
                   width="100%")),
            _field("Cash you add", rx.input(value=TradeState.give_cash, type="number",
                   on_change=TradeState.set_field("give_cash"), width="100%")),
            _field("Cash you want", rx.input(value=TradeState.get_cash, type="number",
                   on_change=TradeState.set_field("get_cash"), width="100%")),
            columns=rx.breakpoints(initial="1", md="3"), spacing="3", width="100%",
        ),
        theme.primary_button("Send proposal", on_click=TradeState.propose, margin_top="0.5rem"),
        _error(TradeState.msg),
        width="100%",
    )
    return theme.page_shell(
        _topbar(),
        rx.hstack(
            rx.heading(TradeState.room_name + " · Trade Center", size="6",
                       style={"color": theme.TEXT}),
            rx.spacer(),
            rx.link("← Room", href="/room?room=" + TradeState.room_code,
                    style={"color": theme.MUTED}),
            width="100%", align="center",
        ),
        rx.box(height="1rem"),
        propose_card,
        rx.box(height="1rem"),
        rx.grid(
            theme.card(
                rx.heading("📥 Incoming", size="5", style={"color": theme.TEXT},
                           margin_bottom="0.5rem"),
                rx.cond(TradeState.incoming.length() > 0,
                        rx.vstack(rx.foreach(TradeState.incoming,
                                  lambda t: _proposal_row(t, incoming=True)),
                                  spacing="2", width="100%"),
                        rx.text("No incoming proposals.", style={"color": theme.MUTED})),
                width="100%",
            ),
            theme.card(
                rx.heading("📤 Outgoing", size="5", style={"color": theme.TEXT},
                           margin_bottom="0.5rem"),
                rx.cond(TradeState.outgoing.length() > 0,
                        rx.vstack(rx.foreach(TradeState.outgoing,
                                  lambda t: _proposal_row(t, incoming=False)),
                                  spacing="2", width="100%"),
                        rx.text("No outgoing proposals.", style={"color": theme.MUTED})),
                width="100%",
            ),
            columns=rx.breakpoints(initial="1", md="2"), spacing="4", width="100%",
        ),
        rx.box(height="1rem"),
        rx.grid(
            theme.card(
                rx.heading("🗑️ Release a player", size="5", style={"color": theme.TEXT},
                           margin_bottom="0.5rem"),
                rx.hstack(
                    rx.select(TradeState.my_players, value=TradeState.release_sel,
                              placeholder="Your player", on_change=TradeState.set_field("release_sel")),
                    rx.button("Release", variant="soft", color_scheme="red",
                              on_click=TradeState.do_release),
                    spacing="2",
                ),
                width="100%",
            ),
            theme.card(
                rx.heading("🛒 Open market", size="5", style={"color": theme.TEXT},
                           margin_bottom="0.5rem"),
                rx.hstack(
                    rx.select(TradeState.available.foreach(lambda p: p["name"]),
                              value=TradeState.bid_player, placeholder="Free agent",
                              on_change=TradeState.set_field("bid_player")),
                    rx.input(value=TradeState.bid_amount, type="number", placeholder="bid",
                             on_change=TradeState.set_field("bid_amount"), width="90px"),
                    rx.button("Bid", on_click=TradeState.place_bid, variant="soft"),
                    spacing="2",
                ),
                rx.box(height="0.5rem"),
                rx.cond(TradeState.available.length() > 0,
                        rx.vstack(rx.foreach(TradeState.available, _market_row),
                                  spacing="2", width="100%"),
                        rx.text("No free agents.", style={"color": theme.MUTED})),
                width="100%",
            ),
            columns=rx.breakpoints(initial="1", md="2"), spacing="4", width="100%",
        ),
        rx.box(height="1rem"),
        theme.card(
            rx.heading("📜 Transactions", size="5", style={"color": theme.TEXT},
                       margin_bottom="0.5rem"),
            rx.cond(TradeState.txns.length() > 0,
                    rx.vstack(rx.foreach(TradeState.txns,
                              lambda t: rx.text(t["text"], style={"color": theme.MUTED,
                                                "font_size": "0.85rem"})),
                              spacing="1", width="100%", align="start"),
                    rx.text("No transactions yet.", style={"color": theme.MUTED})),
            width="100%",
        ),
    )


# --------------------------------------------------------------------------- #
# App
# --------------------------------------------------------------------------- #
app = rx.App(style={"font_family": theme.FONT}, stylesheets=["/custom.css"])
app.add_page(index, route="/", title="Fantasy Auction",
             on_load=AppState.redirect_if_logged_in)
app.add_page(rooms_page, route="/rooms", title="Your Rooms",
             on_load=AppState.load_rooms)
app.add_page(setup_page, route="/setup", title="Room Setup",
             on_load=AppState.load_setup)
app.add_page(room_page, route="/room", title="Auction Room",
             on_load=RoomState.on_load_room)
app.add_page(standings_page, route="/standings", title="Standings",
             on_load=SeasonState.on_load_standings)
app.add_page(trade_page, route="/trade", title="Trade Center",
             on_load=TradeState.on_load_trade)
