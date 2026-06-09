"""Fantasy Auction Platform — Reflex app.

Live auction happens off-app (Zoom); the platform handles post-auction squads
(CSV upload with budgets), 24h open bidding on remaining players, trades (admin
approved), Injury Reserve, gameweek scoring/standings, top scorers, knockouts,
deadline automation, and admin tools.
"""

import reflex as rx

from . import theme
from .state import AppState
from .room_state import RoomState
from .bidding_state import BiddingState
from .trade_state import TradeState
from .season_state import SeasonState
from .admin_state import AdminState
from .scheduler import SchedulerState
from .whoscored_state import WhoScoredState
from .schedule_state import ScheduleState

T = theme


# --------------------------------------------------------------------------- #
# Shared
# --------------------------------------------------------------------------- #
def _field(label, *control):
    return rx.vstack(
        rx.text(label, style={"color": T.MUTED, "font_size": "0.8rem", "font_weight": "500"}),
        *control, spacing="1", width="100%", align="start",
    )


def _error(msg):
    return rx.cond(msg != "", rx.callout(msg, color_scheme="violet", size="1", margin_top="0.5rem"))


def _brand():
    return rx.hstack(
        rx.box("⚡", style={"font_size": "1.3rem"}),
        rx.heading("Fantasy Sports", style={"font_family": T.DISPLAY, "font_weight": "700",
                   "font_size": "1.25rem", "letter_spacing": "-0.5px", "color": T.TEXT}),
        spacing="2", align="center",
    )


def _topbar():
    return rx.hstack(
        _brand(),
        rx.spacer(),
        rx.cond(~AppState.is_hydrated,
                rx.hstack(rx.box(class_name="app-spinner",
                          style={"width": "15px", "height": "15px", "border_width": "2px"}),
                          rx.text("connecting…", style={"color": T.MUTED, "font_size": "0.78rem"}),
                          spacing="2", align="center")),
        rx.cond(AppState.logged_in,
                rx.hstack(
                    rx.box(AppState.auth_user, style={"color": T.ACCENT, "font_weight": "600",
                           "font_size": "0.9rem"}),
                    rx.button(rx.icon("refresh-cw", size=14), "Refresh", on_click=AppState.force_refresh, variant="soft", size="2", color_scheme="blue"),
                    rx.button("Logout", on_click=AppState.handle_logout, variant="soft",
                              size="2", color_scheme="gray"),
                    align="center", spacing="3")),
        width="100%", align="center", margin_bottom="1.75rem",
    )


def _theme_class():
    """Per-tournament page theme class, driven by the active room's tournament."""
    return rx.match(
        AppState.active_tournament,
        ("FIFA World Cup 2026", "app-bg theme-fifa"),
        ("IPL 2026", "app-bg theme-ipl"),
        ("T20 World Cup", "app-bg theme-t20"),
        "app-bg",
    )


def room_shell(*children, **props):
    """page_shell themed by the active tournament."""
    return T.page_shell(*children, theme_class=_theme_class(), **props)


def _navlink(label, href):
    return rx.link(label, href=href, style={"color": T.MUTED, "font_size": "0.9rem",
                   "font_weight": "500", "padding": "6px 12px", "border_radius": "10px"},
                   _hover={"color": T.TEXT, "background": T.SURFACE_2})


def _copy_code(code):
    return rx.box(
        rx.hstack(rx.text("CODE", style={"color": T.MUTED, "font_size": "0.6rem",
                          "letter_spacing": "1px"}),
                  rx.text(code, style={"color": T.ACCENT, "font_family": T.MONO,
                          "font_weight": "700", "font_size": "0.95rem", "letter_spacing": "1px"}),
                  spacing="2", align="center"),
        style={"background": T.SURFACE_2, "border": f"1px solid {T.BORDER_Hi}",
               "border_radius": "10px", "padding": "4px 12px"},
    )


def room_nav(code, is_admin):
    return T.card(
        rx.hstack(
            _copy_code(code),
            _navlink("🏠 Hub", "/room?room=" + code),
            _navlink("👥 Squads", "/squads?room=" + code),
            _navlink("🔨 Bidding", "/bidding?room=" + code),
            _navlink("🤝 Trade", "/trade?room=" + code),
            _navlink("📊 Standings", "/standings?room=" + code),
            _navlink("📅 Schedule", "/schedule?room=" + code),
            _navlink("🧮 Calculator", "/calculator?room=" + code),
            rx.cond(is_admin, _navlink("🛠️ Admin", "/admin?room=" + code)),
            rx.spacer(),
            _navlink("← Rooms", "/rooms"),
            width="100%", align="center", spacing="1", wrap="wrap",
        ),
        style={"padding": "0.6rem 0.9rem", "margin_bottom": "1.5rem"},
    )


# --------------------------------------------------------------------------- #
# Index / auth
# --------------------------------------------------------------------------- #
def auth_panel():
    login = rx.vstack(
        _field("Username", rx.input(value=AppState.username, on_change=AppState.set_field("username"),
               placeholder="Username", width="100%", size="3")),
        _field("Password", rx.input(value=AppState.password, on_change=AppState.set_field("password"),
               placeholder="Password", type="password", width="100%", size="3")),
        T.primary_button("Log in →", on_click=AppState.handle_login, width="100%", size="3",
                         margin_top="0.5rem"),
        spacing="3", width="100%",
    )
    signup = rx.vstack(
        _field("Choose a username", rx.input(value=AppState.username,
               on_change=AppState.set_field("username"), placeholder="Username", width="100%", size="3")),
        _field("Create a password", rx.input(value=AppState.password,
               on_change=AppState.set_field("password"), placeholder="Min 4 characters",
               type="password", width="100%", size="3")),
        _field("Confirm password", rx.input(value=AppState.confirm,
               on_change=AppState.set_field("confirm"), placeholder="Re-enter password",
               type="password", width="100%", size="3")),
        T.primary_button("Create account →", on_click=AppState.handle_signup, width="100%",
                         size="3", margin_top="0.5rem"),
        spacing="3", width="100%",
    )
    reset = rx.vstack(
        rx.text("Verify your identity with a room code you belong to.",
                style={"color": T.MUTED, "font_size": "0.82rem"}),
        _field("Username", rx.input(value=AppState.reset_username,
               on_change=AppState.set_field("reset_username"), placeholder="Your username",
               width="100%", size="3")),
        _field("Room code (verification)", rx.input(value=AppState.reset_room_code,
               on_change=AppState.set_field("reset_room_code"), placeholder="e.g. ZW1KJ4",
               width="100%", size="3")),
        _field("New password", rx.input(value=AppState.reset_new_pw,
               on_change=AppState.set_field("reset_new_pw"), placeholder="Min 4 characters",
               type="password", width="100%", size="3")),
        _field("Confirm new password", rx.input(value=AppState.reset_confirm,
               on_change=AppState.set_field("reset_confirm"), placeholder="Re-enter password",
               type="password", width="100%", size="3")),
        T.primary_button("Reset password", on_click=AppState.handle_reset_password, width="100%",
                         size="3", margin_top="0.5rem"),
        _error(AppState.reset_msg),
        spacing="3", width="100%",
    )
    return T.card(
        rx.tabs.root(
            rx.tabs.list(rx.tabs.trigger("Log in", value="login"),
                         rx.tabs.trigger("Sign up", value="signup"),
                         rx.tabs.trigger("Forgot?", value="reset")),
            rx.tabs.content(login, value="login", padding_top="1.5rem"),
            rx.tabs.content(signup, value="signup", padding_top="1.5rem"),
            rx.tabs.content(reset, value="reset", padding_top="1.5rem"),
            default_value="login",
        ),
        _error(AppState.auth_error),
        width="100%", max_width="440px",
    )


def index():
    return T.page_shell(
        rx.center(
            rx.vstack(
                rx.box("⚡", style={"font_size": "3rem", "margin_bottom": "0.5rem"}),
                rx.heading("Fantasy Sports", class_name="gradient-text",
                           style={"font_family": T.DISPLAY, "font_size": "3.2rem",
                                  "font_weight": "700", "letter_spacing": "-1.5px"}),
                rx.text("Run your fantasy auction league — squads, live open bidding, trades, "
                        "standings & knockouts.", style={"color": T.MUTED, "font_size": "1.05rem",
                        "max_width": "460px", "text_align": "center"}),
                rx.box(height="1rem"),
                auth_panel(),
                align="center", spacing="3",
            ),
            min_height="86vh",
        )
    )


# --------------------------------------------------------------------------- #
# Rooms dashboard
# --------------------------------------------------------------------------- #
def create_room_card():
    return T.card(
        T.section_title("➕ Create a room"),
        rx.box(height="0.9rem"),
        rx.vstack(
            _field("Room name", rx.input(value=AppState.new_room_name,
                   on_change=AppState.set_field("new_room_name"), placeholder="e.g. Friends League",
                   width="100%", size="3")),
            _field("Tournament", rx.select(AppState.tournaments, value=AppState.new_tournament,
                   on_change=AppState.set_field("new_tournament"), width="100%", size="3")),
            rx.checkbox("I'll manage a team too (not admin-only)",
                        checked=AppState.admin_participating,
                        on_change=AppState.set_field("admin_participating")),
            T.primary_button("Create room", on_click=AppState.handle_create_room, width="100%",
                             size="3", margin_top="0.4rem"),
            _error(AppState.create_error),
            spacing="3", width="100%",
        ),
        width="100%",
    )


def join_room_card():
    return T.card(
        T.section_title("🔗 Join a room"),
        rx.box(height="0.9rem"),
        rx.vstack(
            _field("Room code", rx.input(value=AppState.join_code,
                   on_change=AppState.set_field("join_code"), placeholder="ABC123", width="100%", size="3")),
            _field("Team PIN", rx.input(value=AppState.join_pin,
                   on_change=AppState.set_field("join_pin"), placeholder="Your team's PIN", type="password",
                   width="100%", size="3")),
            rx.text("Your PIN identifies your team — no team name needed.",
                    style={"color": T.MUTED, "font_size": "0.78rem"}),
            T.primary_button("Join room", on_click=AppState.handle_join, width="100%", size="3",
                             margin_top="0.4rem"),
            _error(AppState.join_error),
            spacing="3", width="100%",
        ),
        width="100%",
    )


def room_row(room):
    return rx.table.row(
        rx.table.row_header_cell(room["name"]),
        rx.table.cell(rx.code(room["code"])),
        rx.table.cell(room["tournament"]),
        rx.table.cell(T.pill(room["role"], T.PRIMARY)),
        rx.table.cell(room["teams"]),
        rx.table.cell(rx.hstack(
            rx.link("Enter →", href="/room?room=" + room["code"].to(str), style={"color": T.ACCENT}),
            rx.cond(room["role"] == "Admin",
                    rx.link("Setup", href="/setup?room=" + room["code"].to(str),
                            style={"color": T.MUTED})),
            spacing="3")),
    )


def rooms_page():
    return T.page_shell(
        _topbar(),
        T.hero("Your rooms", "Create a new auction room or join one with a code + team PIN."),
        rx.grid(create_room_card(), join_room_card(),
                columns=rx.breakpoints(initial="1", md="2"), spacing="4", width="100%"),
        rx.box(height="2rem"),
        T.section_title("📋 Your rooms"),
        rx.box(height="0.75rem"),
        rx.cond(AppState.my_rooms.length() > 0,
                T.card(rx.table.root(
                    rx.table.header(rx.table.row(
                        rx.table.column_header_cell("Room"), rx.table.column_header_cell("Code"),
                        rx.table.column_header_cell("Tournament"), rx.table.column_header_cell("Role"),
                        rx.table.column_header_cell("Teams"), rx.table.column_header_cell(""))),
                    rx.table.body(rx.foreach(AppState.my_rooms, room_row)), width="100%"),
                    width="100%"),
                rx.text("You haven't created or joined any rooms yet.", style={"color": T.MUTED})),
    )


# --------------------------------------------------------------------------- #
# Room setup (admin)
# --------------------------------------------------------------------------- #
def team_row(t):
    return rx.table.row(
        rx.table.row_header_cell(t["name"]), rx.table.cell(rx.code(t["pin"])),
        rx.table.cell(t["claimed"]), rx.table.cell(t["budget"] + "M"), rx.table.cell(t["squad"]),
    )


def setup_page():
    admin_view = rx.vstack(
        T.hero("Room setup", "Add teams + PINs, then upload squads from your Zoom auction."),
        rx.hstack(T.pill("Code " + AppState.room_code, T.PRIMARY),
                  T.pill(AppState.room_tournament, T.ACCENT),
                  T.pill("Pool " + AppState.pool_count.to(str), T.MUTED),
                  spacing="3"),
        rx.box(height="1rem"),
        rx.grid(
            T.card(
                T.section_title("👥 Teams"),
                rx.box(height="0.7rem"),
                rx.hstack(
                    rx.input(value=AppState.new_team_name, on_change=AppState.set_field("new_team_name"),
                             placeholder="Team name"),
                    rx.input(value=AppState.new_team_pin, on_change=AppState.set_field("new_team_pin"),
                             placeholder="PIN"),
                    T.primary_button("Add", on_click=AppState.handle_add_team),
                    spacing="2", width="100%"),
                _error(AppState.setup_msg),
                rx.box(height="0.7rem"),
                rx.cond(AppState.teams.length() > 0,
                        rx.table.root(
                            rx.table.header(rx.table.row(
                                rx.table.column_header_cell("Team"), rx.table.column_header_cell("PIN"),
                                rx.table.column_header_cell("Claimed"), rx.table.column_header_cell("Budget"),
                                rx.table.column_header_cell("Squad"))),
                            rx.table.body(rx.foreach(AppState.teams, team_row)), width="100%"),
                        rx.text("No teams yet — add one above.", style={"color": T.MUTED})),
                width="100%"),
            T.card(
                T.section_title("📥 Upload squads + budgets (CSV)"),
                rx.box(height="0.5rem"),
                rx.text("After your Zoom auction, upload one CSV with each team's squad and "
                        "remaining budget. Those players are then excluded from open bidding.",
                        style={"color": T.MUTED, "font_size": "0.82rem"}),
                rx.code("Participant,Player,Role,Team,Price", style={"margin_top": "0.4rem"}),
                rx.text("…and a budget line per team:", style={"color": T.MUTED,
                        "font_size": "0.8rem", "margin_top": "0.3rem"}),
                rx.code("Smudge49,BUDGET,,,35", style={"margin_bottom": "0.4rem"}),
                rx.upload(
                    rx.vstack(rx.icon("upload", size=26, color=T.ACCENT),
                              rx.text("Drag a .csv here or click to browse"),
                              align="center", spacing="2"),
                    id="csv_upload", accept={"text/csv": [".csv"]}, max_files=1,
                    border=f"1px dashed {T.BORDER_Hi}", padding="1.5rem", border_radius="14px",
                    width="100%"),
                rx.text(rx.selected_files("csv_upload"), style={"color": T.MUTED, "font_size": "0.8rem"}),
                rx.hstack(
                    T.primary_button("Upload",
                        on_click=AppState.handle_upload(rx.upload_files(upload_id="csv_upload"))),
                    rx.button("Clear", variant="soft", color_scheme="gray",
                              on_click=rx.clear_selected_files("csv_upload")),
                    spacing="3", margin_top="0.7rem"),
                _error(AppState.upload_msg),
                width="100%"),
            columns=rx.breakpoints(initial="1", md="2"), spacing="4", width="100%"),
        import_review_section(),
        rx.box(height="1rem"),
        rx.cond(
            AppState.team_names.length() > 0,
            T.card(
                T.section_title("🧤 Pick the team you'll manage"),
                rx.text("Your username needn't match a team name — choose which team (from the CSV) "
                        "you manage for the whole tournament.",
                        style={"color": T.MUTED, "font_size": "0.82rem"}, margin_y="0.4rem"),
                rx.hstack(
                    rx.select(AppState.team_names, value=AppState.claim_choice,
                              placeholder="Select your team", on_change=AppState.set_field("claim_choice")),
                    T.primary_button("Claim", on_click=AppState.claim_my_team),
                    spacing="3"),
                width="100%"),
        ),
        rx.box(height="1.25rem"),
        rx.hstack(rx.link("← Back to rooms", href="/rooms", style={"color": T.MUTED}), rx.spacer(),
                  T.primary_button("Go to room →", on_click=AppState.go_to_room), width="100%"),
        width="100%", spacing="2",
    )
    return T.page_shell(_topbar(),
        rx.cond(AppState.is_admin, admin_view,
                rx.callout("Only the room admin can access setup.", color_scheme="amber")))


def _status_pill(status):
    return rx.match(status,
                    ("exact", T.pill("exact", T.SUCCESS)),
                    ("confirmed", T.pill("confirmed", T.ACCENT)),
                    ("unmatched", T.pill("⚠ pick", T.DANGER)),
                    T.pill("fuzzy", T.WARNING))


def review_row(row, index):
    return rx.hstack(
        rx.text(row["participant"], style={"color": T.MUTED, "font_size": "0.82rem", "width": "120px"}),
        rx.text(row["written"], style={"color": T.TEXT, "font_size": "0.85rem", "width": "150px"}),
        rx.text("→", style={"color": T.MUTED}),
        rx.select(AppState.import_candidates[index], value=row["matched"],
                  on_change=AppState.set_match(index), width="220px"),
        rx.text(row["price"] + "M", style={"color": T.ACCENT, "font_family": T.MONO,
                "font_size": "0.82rem"}),
        rx.spacer(),
        _status_pill(row["status"]),
        width="100%", align="center", spacing="3",
        style={"background": T.SURFACE_2, "border": f"1px solid {T.BORDER}",
               "border_radius": "10px", "padding": "0.45rem 0.7rem"},
    )


def import_review_section():
    return rx.cond(
        AppState.import_rows.length() > 0,
        rx.fragment(
            rx.box(height="1.25rem"),
            T.card(
                rx.hstack(T.section_title("🕵️ Review signings"), rx.spacer(),
                          T.pill(AppState.import_rows.length().to_string() + " rows", T.PRIMARY),
                          width="100%", align="center"),
                rx.text("Confirm which pool player each written name maps to (e.g. which "
                        "“Silva”). Names must match the player database so scoring works.",
                        style={"color": T.MUTED, "font_size": "0.82rem"}, margin_y="0.4rem"),
                rx.cond(AppState.import_budgets.length() > 0,
                        rx.text("Budgets from CSV: " + AppState.import_budgets.length().to_string()
                                + " teams.", style={"color": T.MUTED, "font_size": "0.8rem"})),
                rx.box(height="0.5rem"),
                rx.vstack(rx.foreach(AppState.import_rows, review_row), spacing="2", width="100%",
                          max_height="420px", overflow="auto"),
                rx.hstack(
                    T.primary_button("✅ Confirm & commit", on_click=AppState.confirm_import),
                    rx.button("Cancel", variant="soft", color_scheme="gray",
                              on_click=AppState.cancel_import),
                    spacing="3", margin_top="0.7rem"),
                width="100%"),
        ),
    )


# --------------------------------------------------------------------------- #
# Hub (your team + all teams)
# --------------------------------------------------------------------------- #
def squad_row(p):
    return rx.hstack(
        rx.cond(p["ir"] == "yes", T.pill("IR", T.WARNING), rx.box(width="34px")),
        rx.text(p["name"], style={"color": T.TEXT, "font_weight": "500"}),
        rx.text(p["role"], style={"color": T.MUTED, "font_size": "0.8rem"}),
        rx.spacer(),
        rx.text(p["price"] + "M", style={"color": T.ACCENT, "font_family": T.MONO,
                "font_size": "0.85rem"}),
        rx.cond(p["ir"] == "yes",
                rx.button("unIR", size="1", variant="ghost", color_scheme="gray",
                          on_click=RoomState.clear_ir),
                rx.button("IR", size="1", variant="ghost", color_scheme="amber",
                          on_click=RoomState.set_ir(p["name"]))),
        rx.cond(
            RoomState.confirm_release_player == p["name"],
            rx.button("Confirm release", size="1", color_scheme="red",
                      on_click=RoomState.half_release(p["name"])),
            rx.button("½ release", size="1", variant="ghost", color_scheme="red",
                      on_click=RoomState.set_confirm_release_player(p["name"]))
        ),
        width="100%", align="center", spacing="3",
        style={"padding": "0.5rem 0.7rem", "border_radius": "10px",
               "background": rx.cond(p["ir"] == "yes", "rgba(251,191,36,0.07)", "transparent")},
    )


def _brk(label, val, color):
    return rx.hstack(rx.text(label, style={"color": T.MUTED, "font_size": "0.7rem"}),
                     rx.text(val, style={"color": color, "font_size": "0.78rem",
                             "font_weight": "700"}), spacing="1", align="center")


def team_overview_card(t):
    # Whole card links to that team's full squad on the Squads page (click-through).
    return rx.link(
        rx.hstack(
            rx.vstack(
                rx.hstack(rx.text(t["name"], style={"color": T.TEXT, "font_weight": "600"}),
                          rx.cond(t["is_me"] == "yes", T.pill("YOU", T.PRIMARY)),
                          rx.cond(t["status"] == "out", T.pill("OUT", T.DANGER)),
                          spacing="2", align="center"),
                rx.hstack(
                    rx.text("🦅 " + t["squad"], style={"color": T.MUTED, "font_size": "0.8rem"}),
                    rx.text("·", style={"color": T.BORDER}),
                    _brk(t["p1_lbl"], t["p1"], T.WARNING), _brk(t["p2_lbl"], t["p2"], T.SUCCESS),
                    _brk(t["p3_lbl"], t["p3"], T.PRIMARY), _brk(t["p4_lbl"], t["p4"], T.ACCENT),
                    spacing="2", align="center", wrap="wrap"),
                spacing="1", align="start"),
            rx.spacer(),
            rx.heading(t["budget"] + "M", style={"color": T.ACCENT, "font_family": T.DISPLAY,
                       "font_size": "1.3rem"}),
            width="100%", align="center",
            style={"background": T.SURFACE_2, "border": f"1px solid {T.BORDER}",
                   "border_radius": "12px", "padding": "0.8rem 1rem"},
            _hover={"border_color": T.ACCENT}),
        href="/squads?room=" + RoomState.room_code + "&team=" + t["name"],
        width="100%", style={"text_decoration": "none"},
    )


def _stat(label, value, color, sub=""):
    return T.card(
        rx.vstack(
            rx.text(label, style={"color": T.MUTED, "font_size": "0.68rem",
                    "letter_spacing": "1px", "text_transform": "uppercase"}),
            rx.heading(value, style={"color": color, "font_family": T.DISPLAY,
                       "font_size": "1.7rem", "font_weight": "700", "line_height": "1.1"}),
            rx.cond(sub != "", rx.text(sub, style={"color": T.MUTED, "font_size": "0.72rem"})),
            spacing="1", align="start"),
        width="100%", style={"padding": "0.8rem 1rem"})


def _hub_bid_row(b):
    return rx.hstack(
        rx.text("🔨", style={"font_size": "0.9rem"}),
        rx.text(b["player"], style={"color": T.TEXT, "font_size": "0.85rem"}),
        rx.spacer(),
        rx.text(b["amount"] + "M", style={"color": T.WARNING, "font_weight": "600"}),
        width="100%", align="center", spacing="2",
        style={"background": T.SURFACE_2, "border": f"1px solid {T.BORDER}",
               "border_radius": "9px", "padding": "0.4rem 0.7rem"})


def _hub_win_row(w):
    return rx.hstack(
        rx.text("🎉", style={"font_size": "0.9rem"}),
        rx.text("You won " + w["player"], style={"color": T.TEXT, "font_size": "0.85rem"}),
        rx.spacer(),
        rx.text(w["amount"] + "M", style={"color": T.SUCCESS, "font_weight": "600"}),
        width="100%", align="center", spacing="2",
        style={"background": "rgba(34,197,94,0.08)", "border": "1px solid rgba(34,197,94,0.25)",
               "border_radius": "9px", "padding": "0.4rem 0.7rem"})


def _hub_trade_row(t):
    return rx.vstack(
        rx.text(t["text"], style={"color": T.TEXT, "font_size": "0.82rem"}),
        rx.hstack(
            rx.button("✓ Accept", on_click=RoomState.hub_accept_trade(t["id"]),
                      size="1", color_scheme="green", variant="soft"),
            rx.button("✕ Reject", on_click=RoomState.hub_reject_trade(t["id"]),
                      size="1", color_scheme="red", variant="soft"),
            rx.link("Open in Trade →", href="/trade?room=" + RoomState.room_code,
                    style={"color": T.ACCENT, "font_size": "0.76rem"}),
            spacing="2", align="center"),
        spacing="2", width="100%", align="start",
        style={"background": "rgba(124,92,255,0.07)", "border": "1px solid rgba(124,92,255,0.25)",
               "border_radius": "10px", "padding": "0.55rem 0.8rem"})


def room_page():
    dashboard = rx.vstack(
        # personal stat strip
        rx.grid(
            _stat("Your rank", RoomState.my_rank, T.ACCENT, RoomState.my_points + " pts"),
            _stat("Budget", RoomState.my_budget.to_string() + "M", T.SUCCESS),
            _stat("Bids held", RoomState.my_bids.length().to_string(),
                  T.WARNING, RoomState.my_bids_total + "M committed"),
            _stat("Trade offers", RoomState.hub_trades.length().to_string(), T.PRIMARY,
                  "proposed to you"),
            columns=rx.breakpoints(initial="2", md="4"), spacing="3", width="100%"),
        rx.box(height="0.4rem"),
        rx.grid(
            # left column — my squad
            T.card(
                rx.hstack(
                    T.section_title("⚽ " + RoomState.my_team), 
                    rx.dialog.root(
                        rx.dialog.trigger(rx.button(rx.icon("pencil-1", size=14), size="1", variant="ghost")),
                        rx.dialog.content(
                            rx.dialog.title("Rename Team"),
                            rx.dialog.description("Pick a new name for your team. This will update all references to your team in the database."),
                            rx.box(height="0.5rem"),
                            rx.input(value=RoomState.rename_input, on_change=RoomState.set_field("rename_input"), placeholder="New team name"),
                            _error(RoomState.rename_error),
                            rx.box(height="1rem"),
                            rx.hstack(
                                rx.dialog.close(rx.button("Cancel", variant="soft", color_scheme="gray")),
                                rx.button("Save", on_click=RoomState.handle_rename),
                            )
                        )
                    ),
                    rx.spacer(),
                    rx.select(["Price", "Position"], value=RoomState.squad_sort_by, on_change=RoomState.select_sort_by, width="110px", variant="soft"),
                    T.pill(RoomState.my_squad.length().to_string() + " players", T.PRIMARY),
                    width="100%", align="center", spacing="2"),
                rx.box(height="0.7rem"),
                rx.cond(RoomState.my_squad.length() > 0,
                        rx.vstack(rx.foreach(RoomState.my_squad, squad_row), spacing="1",
                                  width="100%"),
                        rx.text("No players yet — wait for the CSV upload or win some in bidding.",
                                style={"color": T.MUTED})),
                width="100%"),
            # right column — activity
            rx.vstack(
                T.card(
                    rx.hstack(T.section_title("🤝 Trades proposed to you"), rx.spacer(),
                              rx.cond(RoomState.hub_trades.length() > 0,
                                      T.pill(RoomState.hub_trades.length().to_string(), T.PRIMARY)),
                              width="100%", align="center"),
                    rx.box(height="0.5rem"),
                    rx.cond(RoomState.hub_trades.length() > 0,
                            rx.vstack(rx.foreach(RoomState.hub_trades, _hub_trade_row),
                                      spacing="2", width="100%"),
                            rx.text("No pending offers.", style={"color": T.MUTED,
                                    "font_size": "0.85rem"})),
                    width="100%"),
                T.card(
                    T.section_title("🎉 Won since your last visit"),
                    rx.box(height="0.5rem"),
                    rx.cond(RoomState.my_wins.length() > 0,
                            rx.vstack(rx.foreach(RoomState.my_wins, _hub_win_row), spacing="2",
                                      width="100%"),
                            rx.text("Nothing new — bids award at the deadline.",
                                    style={"color": T.MUTED, "font_size": "0.85rem"})),
                    width="100%"),
                T.card(
                    rx.hstack(T.section_title("🔨 Bids you're leading"), rx.spacer(),
                              rx.link("Bidding →", href="/bidding?room=" + RoomState.room_code,
                                      style={"color": T.ACCENT, "font_size": "0.78rem"}),
                              width="100%", align="center"),
                    rx.box(height="0.5rem"),
                    rx.cond(RoomState.my_bids.length() > 0,
                            rx.vstack(rx.foreach(RoomState.my_bids, _hub_bid_row), spacing="2",
                                      width="100%"),
                            rx.text("You're not leading any open bids.", style={"color": T.MUTED,
                                    "font_size": "0.85rem"})),
                    width="100%"),
                spacing="4", width="100%"),
            columns=rx.breakpoints(initial="1", lg="2"), spacing="4", width="100%"),
        rx.box(height="0.5rem"),
        rx.text("Browse and compare every squad on the 👥 Squads tab.",
                style={"color": T.MUTED, "font_size": "0.82rem"}),
        spacing="4", width="100%")

    return room_shell(
        _topbar(), room_nav(RoomState.room_code, RoomState.is_admin),
        rx.hstack(
            rx.heading(RoomState.room_name, class_name="gradient-text",
                       style={"font_family": T.DISPLAY, "font_size": "2rem", "font_weight": "700"}),
            rx.spacer(),
            rx.cond(RoomState.next_deadline != "",
                    T.pill("⏰ " + RoomState.next_deadline, T.WARNING)),
            T.pill("GW " + RoomState.current_gameweek, T.PRIMARY),
            width="100%", align="center", spacing="3", wrap="wrap",
        ),
        rx.box(height="1rem"),
        _error(RoomState.msg),
        rx.cond(
            RoomState.my_team != "",
            dashboard,
            T.card(
                T.section_title("👀 Spectating"),
                rx.text("You're the admin and not managing a team. Use the nav above to run the league.",
                        style={"color": T.MUTED}),
                rx.box(height="0.8rem"),
                rx.vstack(rx.foreach(RoomState.teams, team_overview_card), spacing="2", width="100%"),
                width="100%"),
        ),
    )


# --------------------------------------------------------------------------- #
# Squads (all teams, detailed)
# --------------------------------------------------------------------------- #
def _squad_view_row(p):
    return rx.hstack(
        rx.cond(p["ir"] == "yes", T.pill("IR", T.WARNING), rx.box(width="32px")),
        rx.text(p["name"], style={"color": T.TEXT, "font_weight": "500"}),
        rx.text(p["role"], style={"color": T.MUTED, "font_size": "0.8rem"}),
        rx.text(p["team"], style={"color": T.MUTED, "font_size": "0.78rem"}),
        rx.spacer(),
        rx.text(p["price"] + "M", style={"color": T.ACCENT, "font_family": T.MONO,
                "font_size": "0.85rem"}),
        # When browsing someone else's squad, offer to start a trade for this player.
        rx.cond(
            (RoomState.view_team_sel != RoomState.my_team) & (RoomState.my_team != ""),
            rx.link("🤝 Trade", href="/trade?room=" + RoomState.room_code + "&with="
                    + RoomState.view_team_sel + "&want=" + p["name"],
                    style={"color": T.PRIMARY, "font_size": "0.76rem", "font_weight": "600",
                           "white_space": "nowrap"})),
        width="100%", align="center", spacing="3",
        style={"background": T.SURFACE_2, "border": f"1px solid {T.BORDER}",
               "border_radius": "10px", "padding": "0.45rem 0.7rem"},
    )


def squads_page():
    return room_shell(
        _topbar(), room_nav(RoomState.room_code, RoomState.is_admin),
        T.hero("Squads", "Inspect any team's full squad, budget and locked gameweek snapshots."),
        T.card(
            rx.hstack(
                rx.text("🔍", style={"font_size": "1.2rem"}),
                rx.input(value=RoomState.squads_search, on_change=RoomState.set_field("squads_search"),
                         placeholder="Search for a player across all squads...", width="100%"),
                T.primary_button("Search", on_click=RoomState.do_squads_search),
                width="100%", align="center", spacing="3"
            ),
            rx.cond(
                RoomState.squads_search_results.length() > 0,
                rx.vstack(
                    rx.divider(margin_y="0.5rem"),
                    rx.foreach(RoomState.squads_search_results, _squad_view_row),
                    spacing="2", width="100%"
                )
            ),
            width="100%", style={"margin_bottom": "1.5rem"}
        ),
        rx.hstack(rx.text("View team:", style={"color": T.MUTED}),
                  rx.select(RoomState.all_team_names, value=RoomState.view_team_sel,
                            on_change=RoomState.select_view_team, width="240px"),
                  rx.spacer(),
                  rx.text("Sort by:", style={"color": T.MUTED}),
                  rx.select(["Price", "Position"], value=RoomState.squad_sort_by,
                            on_change=RoomState.select_sort_by, width="110px", variant="soft"),
                  T.pill("💰 " + RoomState.view_budget + "M", T.SUCCESS),
                  width="100%", align="center", spacing="2"),
        rx.box(height="1rem"),
        rx.grid(
            T.card(
                rx.hstack(T.section_title("🦅 Current squad"), rx.spacer(),
                          T.pill(RoomState.view_squad.length().to_string() + " players", T.PRIMARY),
                          width="100%", align="center"),
                rx.box(height="0.6rem"),
                rx.cond(RoomState.view_squad.length() > 0,
                        rx.vstack(rx.foreach(RoomState.view_squad, _squad_view_row), spacing="2",
                                  width="100%"),
                        rx.text("No players yet.", style={"color": T.MUTED})),
                width="100%"),
            T.card(
                rx.hstack(T.section_title("🔒 Locked snapshot"), rx.spacer(),
                          rx.select(RoomState.locked_gws, value=RoomState.view_locked_gw,
                                    placeholder="GW", on_change=RoomState.select_locked_gw),
                          width="100%", align="center"),
                rx.box(height="0.6rem"),
                rx.cond(RoomState.locked_rows.length() > 0,
                        rx.vstack(rx.foreach(RoomState.locked_rows, lambda p: rx.hstack(
                            rx.cond(p["ir"] == "yes", T.pill("IR", T.WARNING), rx.box(width="32px")),
                            rx.text(p["name"], style={"color": T.TEXT}),
                            rx.text(p["role"], style={"color": T.MUTED, "font_size": "0.8rem"}),
                            width="100%", align="center", spacing="3",
                            style={"background": T.SURFACE_2, "border": f"1px solid {T.BORDER}",
                                   "border_radius": "10px", "padding": "0.4rem 0.7rem"})),
                            spacing="2", width="100%"),
                        rx.text("No locked snapshot for this team/gameweek yet.",
                                style={"color": T.MUTED})),
                width="100%"),
            columns=rx.breakpoints(initial="1", md="2"), spacing="4", width="100%"),
        rx.box(height="1.5rem"),
        T.section_title("🌍 All teams at a glance"),
        rx.box(height="0.6rem"),
        rx.grid(rx.foreach(RoomState.teams, team_overview_card),
                columns=rx.breakpoints(initial="1", sm="2", md="3"), spacing="3", width="100%"),
    )


# --------------------------------------------------------------------------- #
# Open bidding (24h)
# --------------------------------------------------------------------------- #
def available_row(p):
    return rx.hstack(
        rx.text(p["name"], style={"color": T.TEXT, "font_weight": "500"}),
        rx.text(p["role"] + " · " + p["team"], style={"color": T.MUTED, "font_size": "0.78rem"}),
        rx.spacer(),
        rx.button("Bid", size="1", variant="soft", on_click=BiddingState.pick(p["name"])),
        width="100%", align="center",
        style={"background": T.SURFACE_2, "border": f"1px solid {T.BORDER}",
               "border_radius": "10px", "padding": "0.45rem 0.7rem"},
    )


# active_bid_row has been removed in favor of a data table.


def bidding_page():
    return room_shell(
        _topbar(), room_nav(BiddingState.room_code, BiddingState.is_admin),
        rx.hstack(T.hero("Open bidding", "Bid on any unowned player. Min 5M; +5M steps once a bid "
                         "hits 50M. All bids award at the admin's deadline."),
                  rx.spacer(),
                  T.pill("💰 " + BiddingState.my_budget.to_string() + "M", T.SUCCESS),
                  width="100%", align="start"),
        T.card(
            rx.hstack(
                rx.box(BiddingState.window_label, style={"color": T.TEXT, "font_weight": "500"}),
                rx.spacer(),
                rx.cond(BiddingState.deadline_str != "",
                        T.pill("⏰ " + BiddingState.deadline_str, T.WARNING)),
                width="100%", align="center"),
            rx.cond(
                BiddingState.milestones.length() > 0,
                rx.vstack(
                    rx.divider(margin_y="0.5rem"),
                    rx.foreach(BiddingState.milestones, lambda m: rx.hstack(
                        rx.text(m["label"], style={"color": T.MUTED, "font_size": "0.85rem"}),
                        rx.spacer(),
                        rx.cond(
                            m["left"] == "passed",
                            rx.text("passed", style={"color": T.MUTED, "font_family": T.MONO, "font_size": "0.85rem"}),
                            rx.text(T.countdown(date=m["left"]), style={"color": T.ACCENT, "font_family": T.MONO, "font_size": "0.85rem"})
                        ),
                        width="100%", align="center")),
                    spacing="1", width="100%"),
            ),
            width="100%", style={"margin_bottom": "0.6rem"}),
        _error(BiddingState.msg),
        rx.box(height="0.5rem"),
        T.card(
            rx.hstack(
                rx.box(
                    rx.input(value=BiddingState.bid_player, on_change=BiddingState.set_field("bid_player"),
                             placeholder="Player to bid on", width="100%", id="bid_player_input", list="available-players"),
                    rx.el.datalist(
                        rx.foreach(BiddingState.all_available_players, lambda p: rx.el.option(p["role"] + " · " + p["team"], value=p["name"])),
                        id="available-players"
                    ),
                    width="40%"
                ),
                rx.input(value=BiddingState.bid_amount, on_change=BiddingState.set_field("bid_amount"),
                         placeholder="Amount (M)", type="number", width="120px"),
                T.primary_button("Place bid", on_click=BiddingState.place_bid),
                spacing="3", width="100%", wrap="wrap"),
            width="100%"),
        rx.box(height="1rem"),
        rx.grid(
            T.card(
                rx.hstack(T.section_title("🟢 Available"), rx.spacer(),
                          rx.input(value=BiddingState.search, on_change=BiddingState.set_field("search"),
                                   placeholder="search…", width="150px"),
                          rx.button("Go", variant="soft", on_click=BiddingState.do_search),
                          width="100%", align="center"),
                rx.box(height="0.7rem"),
                rx.cond(BiddingState.available.length() > 0,
                        rx.vstack(rx.foreach(BiddingState.available, available_row), spacing="2",
                                  width="100%", max_height="460px", overflow="auto"),
                        rx.text("No players match.", style={"color": T.MUTED})),
                width="100%"),
            T.card(
                T.section_title("⏳ Active bids"),
                rx.box(height="0.7rem"),
                rx.cond(BiddingState.active.length() > 0,
                        rx.table.root(
                            rx.table.header(
                                rx.table.row(
                                    rx.table.column_header_cell("Player"),
                                    rx.table.column_header_cell("Highest Bid"),
                                    rx.table.column_header_cell("Time Left"),
                                )
                            ),
                            rx.table.body(
                                rx.foreach(BiddingState.active, lambda b: rx.table.row(
                                    rx.table.row_header_cell(
                                        rx.vstack(rx.text(b["player"], style={"color": T.TEXT, "font_weight": "500"}),
                                                  rx.text(b["role"] + " · " + b["team"], style={"color": T.MUTED, "font_size": "0.78rem"}),
                                                  spacing="0", align="start")
                                    ),
                                    rx.table.cell(
                                        rx.vstack(rx.text(b["high_bid"] + "M", style={"color": T.ACCENT, "font_family": T.MONO, "font_weight": "bold"}),
                                                  rx.hstack(rx.text(b["high_bidder"], style={"color": T.MUTED, "font_size": "0.78rem"}),
                                                            rx.cond(b["mine"] == "yes", T.pill("you lead", T.SUCCESS)),
                                                            spacing="1"),
                                                  spacing="0", align="start")
                                    ),
                                    rx.table.cell(
                                        rx.cond(
                                            b["time_left"] == "passed",
                                            rx.text("passed", style={"color": T.DANGER, "font_size": "0.85rem"}),
                                            rx.hstack(rx.text("⏳", size="1"), rx.text(T.countdown(date=b["time_left"]), style={"color": T.WARNING, "font_family": T.MONO, "font_size": "0.85rem"}))
                                        )
                                    )
                                ))
                            ),
                            width="100%", variant="surface", size="1"
                        ),
                        rx.text("No active bids yet.", style={"color": T.MUTED})),
                width="100%"),
            columns=rx.breakpoints(initial="1", md="2"), spacing="4", width="100%"),
    )


# --------------------------------------------------------------------------- #
# Trade
# --------------------------------------------------------------------------- #
def _proposal_row(t, kind):
    if kind == "incoming":
        actions = rx.hstack(
            rx.button("Accept", size="1", color_scheme="green", on_click=TradeState.accept(t["id"])),
            rx.button("Reject", size="1", variant="soft", color_scheme="red",
                      on_click=TradeState.reject(t["id"])), spacing="2")
    elif kind == "awaiting":
        actions = rx.hstack(
            rx.button("Approve", size="1", color_scheme="green",
                      on_click=TradeState.admin_approve(t["id"])),
            rx.button("Reject", size="1", variant="soft", color_scheme="red",
                      on_click=TradeState.admin_reject(t["id"])), spacing="2")
    else:
        actions = T.pill("pending", T.WARNING)
    return rx.hstack(
        rx.text(t["text"], style={"color": T.TEXT, "font_size": "0.83rem"}), rx.spacer(), actions,
        width="100%", align="center",
        style={"background": T.SURFACE_2, "border": f"1px solid {T.BORDER}",
               "border_radius": "10px", "padding": "0.6rem 0.8rem"})


def trade_page():
    propose = T.card(
        T.section_title("🤝 Propose a trade"),
        rx.box(height="0.7rem"),
        rx.grid(
            _field("With", rx.select(TradeState.other_teams, value=TradeState.counterparty,
                   placeholder="Team", on_change=TradeState.pick_counterparty, width="100%")),
            _field("You give", rx.select(TradeState.my_players, value=TradeState.give_player,
                   placeholder="(player)", on_change=TradeState.set_field("give_player"), width="100%")),
            _field("You get", rx.select(TradeState.their_players, value=TradeState.get_player,
                   placeholder="(player)", on_change=TradeState.set_field("get_player"), width="100%")),
            _field("Cash you add", rx.input(value=TradeState.give_cash, type="number",
                   on_change=TradeState.set_field("give_cash"), width="100%")),
            _field("Cash you want", rx.input(value=TradeState.get_cash, type="number",
                   on_change=TradeState.set_field("get_cash"), width="100%")),
            _field("Is this a loan?", rx.checkbox("1-Gameweek Loan", checked=TradeState.is_loan,
                   on_change=TradeState.set_field("is_loan"), width="100%")),
            columns=rx.breakpoints(initial="1", md="3"), spacing="3", width="100%"),
        T.primary_button("Send proposal", on_click=TradeState.propose, margin_top="0.6rem"),
        rx.text("All accepted trades require admin approval before they apply.",
                style={"color": T.MUTED, "font_size": "0.78rem", "margin_top": "0.4rem"}),
        _error(TradeState.msg), width="100%")
    return room_shell(
        _topbar(), room_nav(TradeState.room_code, TradeState.is_admin),
        T.hero(TradeState.room_name + " · Trades", ""),
        propose,
        rx.box(height="1rem"),
        rx.grid(
            T.card(T.section_title("📥 Incoming"), rx.box(height="0.6rem"),
                   rx.cond(TradeState.incoming.length() > 0,
                           rx.vstack(rx.foreach(TradeState.incoming,
                                     lambda t: _proposal_row(t, "incoming")), spacing="2", width="100%"),
                           rx.text("No incoming proposals.", style={"color": T.MUTED})), width="100%"),
            T.card(T.section_title("📤 Outgoing"), rx.box(height="0.6rem"),
                   rx.cond(TradeState.outgoing.length() > 0,
                           rx.vstack(rx.foreach(TradeState.outgoing,
                                     lambda t: _proposal_row(t, "outgoing")), spacing="2", width="100%"),
                           rx.text("No outgoing proposals.", style={"color": T.MUTED})), width="100%"),
            columns=rx.breakpoints(initial="1", md="2"), spacing="4", width="100%"),
        rx.cond(TradeState.is_admin,
                rx.fragment(rx.box(height="1rem"),
                    T.card(T.section_title("👑 Awaiting your approval"), rx.box(height="0.6rem"),
                        rx.cond(TradeState.awaiting.length() > 0,
                                rx.vstack(rx.foreach(TradeState.awaiting,
                                          lambda t: _proposal_row(t, "awaiting")), spacing="2",
                                          width="100%"),
                                rx.text("Nothing awaiting approval.", style={"color": T.MUTED})),
                        width="100%"))),
        rx.box(height="1rem"),
        T.card(T.section_title("📜 Transactions"), rx.box(height="0.6rem"),
               rx.cond(TradeState.txns.length() > 0,
                       rx.vstack(rx.foreach(TradeState.txns,
                                 lambda e: rx.hstack(
                                     rx.cond(e["ts"] != "", rx.text(rx.moment(date=e["ts"], format="DD MMM HH:mm"), style={"color": T.PRIMARY, "font_size": "0.75rem", "font_family": T.MONO, "width": "90px"})),
                                     rx.text(e["text"], style={"color": T.MUTED, "font_size": "0.83rem"})
                                 )), spacing="1", width="100%",
                                 align="start"),
                       rx.text("No transactions yet.", style={"color": T.MUTED})), width="100%"),
    )


# --------------------------------------------------------------------------- #
# Standings + gameweek admin
# --------------------------------------------------------------------------- #
def _rank_table(rows, warn=False):
    def row(item):
        team_cell = rx.table.row_header_cell(
            rx.cond(
                warn,
                rx.link(item["participant"], on_click=lambda: SeasonState.open_best11(item["participant"]), cursor="pointer", color=T.ACCENT),
                rx.text(item["participant"])
            )
        )
        cells = [team_cell, rx.table.cell(item["points"] + " pts")]
        if warn:
            cells.append(rx.table.cell(item["warn"]))
        return rx.table.row(*cells)
    headers = [rx.table.column_header_cell("Team"), rx.table.column_header_cell("Points")]
    if warn:
        headers.append(rx.table.column_header_cell(""))
    return rx.table.root(rx.table.header(rx.table.row(*headers)),
                         rx.table.body(rx.foreach(rows, row)), width="100%")


def scorer_row(s):
    return rx.table.row(rx.table.row_header_cell(s["player"]),
                        rx.table.cell(s["points"] + " pts"), rx.table.cell(s["owner"]))


def gameweek_admin_panel():
    return T.card(
        T.section_title("⚙️ Gameweek admin"),
        rx.box(height="0.5rem"),
        rx.hstack(rx.text("Current:", style={"color": T.MUTED}),
                  T.pill("GW " + SeasonState.current_gameweek, T.PRIMARY),
                  rx.button("⏭️ Advance", on_click=SeasonState.advance_gw, variant="soft", size="2"),
                  spacing="3", align="center"),
        rx.divider(margin_y="0.7rem"),
        T.section_title("📊 Score a gameweek from WhoScored links"),
        rx.hstack(
            rx.text("Gameweek:", style={"color": T.MUTED}),
            rx.select(SeasonState.gw_options, value=SeasonState.gw_input,
                      on_change=SeasonState.set_field("gw_input"), width="110px"),
            rx.button("🔒 Lock squads now", on_click=SeasonState.lock_squads, variant="soft", size="2"),
            spacing="3", align="center", wrap="wrap"),
        rx.text("Paste the WhoScored match links for the selected gameweek — one per line. Points "
                "(players + nation keepers, dual-position) are scraped and the standings for that "
                "gameweek are computed on each team's locked squad (IR excluded).",
                style={"color": T.MUTED, "font_size": "0.8rem", "margin_top": "0.5rem"}),
        rx.text_area(value=SeasonState.score_links, on_change=SeasonState.set_field("score_links"),
                     placeholder="https://www.whoscored.com/matches/…/live/…\nhttps://www.whoscored.com/matches/…/live/…",
                     rows="5", width="100%"),
        rx.cond(SeasonState.scoring_running,
                rx.button(rx.spinner(), "Scraping…", disabled=True),
                T.primary_button("📊 Compute standings for GW " + SeasonState.gw_input,
                                 on_click=SeasonState.run_whoscored_scoring)),
        rx.divider(margin_y="0.7rem"),
        T.section_title("⏰ Bidding deadline (drives the gameweek)"),
        rx.text("Set ONE deadline: new bids until −1h, raise-only (+5M) in the last 30m, bids "
                "award at the deadline, trading until +30m, then squads auto-lock & the next "
                "gameweek starts. Frozen until you set the next one.",
                style={"color": T.MUTED, "font_size": "0.8rem"}),
        rx.hstack(
            rx.input(value=SeasonState.bidding_deadline_value,
                     on_change=SeasonState.set_field("bidding_deadline_value"),
                     type="datetime-local", width="220px"),
            T.primary_button("Set bidding deadline", on_click=SeasonState.save_bidding_deadline),
            spacing="3", align="center", margin_top="0.4rem", wrap="wrap"),
        rx.divider(margin_y="0.7rem"),
        T.section_title("🏆 Knockout"),
        rx.text("Keep the top N for the selected gameweek; the rest are eliminated and their "
                "players freed to open bidding.", style={"color": T.MUTED, "font_size": "0.8rem"}),
        rx.hstack(
            rx.button("R16 → 8", on_click=SeasonState.run_knockout_round(8), variant="soft", size="1"),
            rx.button("QF → 4", on_click=SeasonState.run_knockout_round(4), variant="soft", size="1"),
            rx.button("SF → 2", on_click=SeasonState.run_knockout_round(2), variant="soft", size="1"),
            rx.button("Final → 1", on_click=SeasonState.run_knockout_round(1), variant="soft", size="1"),
            rx.button("↩️ Reverse", on_click=SeasonState.reverse_elimination, variant="soft",
                      color_scheme="gray", size="1"),
            spacing="2", margin_top="0.4rem", wrap="wrap"),
        rx.cond(SeasonState.eliminated.length() > 0,
                rx.text("Eliminated: " + SeasonState.eliminated.join(", "),
                        style={"color": T.DANGER, "font_size": "0.82rem", "margin_top": "0.3rem"})),
        _error(SeasonState.msg), width="100%")


def best11_modal():
    def _player_row(p):
        return rx.table.row(
            rx.table.cell(p["name"]),
            rx.table.cell(p["role"]),
            rx.table.cell(p["score"] + " pts")
        )

    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title(SeasonState.best11_team_name + " · Best 11"),
            rx.dialog.description("Gameweek " + SeasonState.selected_gw + " — Total: " + SeasonState.best11_total + " pts"),
            rx.box(height="1rem"),
            rx.table.root(
                rx.table.header(
                    rx.table.row(
                        rx.table.column_header_cell("Player"),
                        rx.table.column_header_cell("Pos"),
                        rx.table.column_header_cell("Score"),
                    )
                ),
                rx.table.body(rx.foreach(SeasonState.best11_players, _player_row)),
                variant="surface", size="1"
            ),
            rx.box(height="1rem"),
            rx.flex(
                rx.dialog.close(
                    rx.button("Close", variant="soft", color_scheme="gray", on_click=SeasonState.close_best11)
                ),
                justify="end",
            ),
            max_width="450px",
        ),
        open=SeasonState.show_best11_modal,
        on_open_change=SeasonState.set_field("show_best11_modal")
    )


def standings_page():
    return room_shell(
        _topbar(), room_nav(SeasonState.room_code, SeasonState.is_admin),
        T.hero(SeasonState.room_name + " · Standings", ""),
        rx.grid(
            T.card(T.section_title("🏆 Overall"), rx.box(height="0.5rem"),
                   rx.cond(SeasonState.cumulative.length() > 0, _rank_table(SeasonState.cumulative),
                           rx.text("No scores entered yet.", style={"color": T.MUTED})), width="100%"),
            T.card(rx.hstack(T.section_title("📅 Gameweek"), rx.spacer(),
                   rx.select(SeasonState.gameweeks, value=SeasonState.selected_gw, placeholder="GW",
                             on_change=SeasonState.select_gw), width="100%", align="center"),
                   rx.box(height="0.5rem"),
                   rx.cond(SeasonState.gw_standings.length() > 0,
                           _rank_table(SeasonState.gw_standings, warn=True),
                           rx.text("Pick a gameweek with scores.", style={"color": T.MUTED})),
                   width="100%"),
            columns=rx.breakpoints(initial="1", md="2"), spacing="4", width="100%"),
        rx.box(height="1rem"),
        T.card(T.section_title("⭐ Top player scorers"), rx.box(height="0.5rem"),
               rx.cond(SeasonState.top_scorers.length() > 0,
                       rx.table.root(rx.table.header(rx.table.row(
                           rx.table.column_header_cell("Player"), rx.table.column_header_cell("Points"),
                           rx.table.column_header_cell("Owner"))),
                           rx.table.body(rx.foreach(SeasonState.top_scorers, scorer_row)), width="100%"),
                       rx.text("No scores yet.", style={"color": T.MUTED})), width="100%"),
        rx.cond(SeasonState.is_admin,
                rx.text("Gameweek admin (scores, deadlines, knockout) has moved to the 🛠️ Admin tab.",
                        style={"color": T.MUTED, "font_size": "0.82rem", "margin_top": "1rem"})),
        best11_modal()
    )


# --------------------------------------------------------------------------- #
# Admin micro-features
# --------------------------------------------------------------------------- #
def _admin_band(emoji, label, desc=""):
    return rx.hstack(
        rx.box(emoji, style={"font_size": "1.1rem"}),
        rx.vstack(
            rx.heading(label, style={"font_family": T.DISPLAY, "font_weight": "600",
                       "font_size": "1.05rem", "color": T.TEXT, "letter_spacing": "-0.2px"}),
            rx.cond(desc != "", rx.text(desc, style={"color": T.MUTED, "font_size": "0.8rem"})),
            spacing="0", align="start"),
        rx.spacer(),
        width="100%", align="center", spacing="3",
        style={"border_left": f"3px solid {T.ACCENT}", "padding": "0.4rem 0 0.4rem 0.8rem",
               "margin": "0.6rem 0 0.2rem"},
    )


def admin_page():
    body = rx.vstack(
        _admin_band("⚙️", "Gameweek control",
                    "Scores, the bidding deadline that drives the whole gameweek, and knockouts."),
        rx.cond(AdminState.is_admin, gameweek_admin_panel()),
        _admin_band("👥", "Roster Control", "Force moves, editing budgets, and reversing releases."),
        rx.grid(
            T.card(T.section_title("➕ Force add"), rx.box(height="0.5rem"),
                rx.select(AdminState.teams, value=AdminState.fa_team, placeholder="Team",
                          on_change=AdminState.set_field("fa_team"), width="100%"),
                rx.input(value=AdminState.fa_player, placeholder="Type a player name…",
                         on_change=AdminState.fa_type),
                rx.cond(AdminState.fa_suggestions.length() > 0,
                        rx.vstack(rx.foreach(AdminState.fa_suggestions, lambda s: rx.box(
                            rx.text(s["name"] + "  ·  " + s["role"] + "  ·  " + s["team"],
                                    style={"color": T.TEXT, "font_size": "0.82rem"}),
                            on_click=AdminState.pick_fa(s["name"], s["role"], s["team"]),
                            style={"cursor": "pointer", "background": T.SURFACE_2,
                                   "border": f"1px solid {T.BORDER}", "border_radius": "8px",
                                   "padding": "0.35rem 0.6rem"}, _hover={"border_color": T.ACCENT})),
                            spacing="1", width="100%", max_height="160px", overflow="auto")),
                rx.hstack(rx.input(value=AdminState.fa_role, placeholder="Role",
                          on_change=AdminState.set_field("fa_role")),
                          rx.input(value=AdminState.fa_team_name, placeholder="Real team",
                          on_change=AdminState.set_field("fa_team_name")),
                          rx.input(value=AdminState.fa_price, placeholder="Price", type="number",
                          on_change=AdminState.set_field("fa_price"), width="90px"), spacing="2"),
                T.primary_button("Add", on_click=AdminState.force_add, margin_top="0.4rem"),
                spacing="2", width="100%"),
            # Edit Budget & Reverse Release
            T.card(T.section_title("💰 Edit Budget"), rx.box(height="0.5rem"),
                rx.vstack(
                    rx.select(AdminState.teams, placeholder="Select team", on_change=AdminState.set_field("edit_participant")),
                    rx.input(placeholder="Amount (+ or - M)", on_change=AdminState.set_field("edit_delta")),
                    rx.button("Adjust Budget", on_click=AdminState.do_edit_budget, color_scheme="blue", width="100%"),
                    spacing="2", width="100%"
                )
            ),
            
            T.card(T.section_title("⏪ Reverse Release"), rx.box(height="0.5rem"),
                rx.text("Undo an accidental release. Returns player to squad and deducts refund.", style={"color": T.MUTED, "font_size": "0.85rem", "margin_bottom": "0.5rem"}),
                rx.vstack(
                    rx.select(AdminState.teams, placeholder="Target team", on_change=AdminState.set_field("rev_participant")),
                    rx.select(AdminState.rev_player_options, placeholder="Select released player", 
                              value=AdminState.rev_player, on_change=AdminState.pick_rev_player),
                    rx.input(placeholder="Original buy price (M)", value=AdminState.rev_buy, on_change=AdminState.set_field("rev_buy")),
                    rx.input(placeholder="Refund given to deduct back (M)", value=AdminState.rev_refund, on_change=AdminState.set_field("rev_refund")),
                    rx.button("Reverse Release", on_click=AdminState.do_reverse_release, color_scheme="orange", width="100%"),
                    spacing="2", width="100%"
                )
            ),

            T.card(T.section_title("🗑️ Force release"), rx.box(height="0.5rem"),
                rx.select(AdminState.teams, value=AdminState.fr_team, placeholder="Team",
                          on_change=AdminState.pick_fr_team, width="100%"),
                rx.select(AdminState.fr_team_players, value=AdminState.fr_player,
                          placeholder="Player from that team",
                          on_change=AdminState.set_field("fr_player"), width="100%"),
                rx.checkbox("Refund buy price", checked=AdminState.fr_refund,
                            on_change=AdminState.set_field("fr_refund")),
                rx.hstack(
                    rx.button("Release", on_click=AdminState.force_release, color_scheme="red",
                              variant="soft"),
                    rx.button("Release for full price", on_click=AdminState.release_full_price,
                              color_scheme="green", variant="soft"),
                    spacing="2", margin_top="0.4rem", width="100%"),
                rx.text("“Release for full price” returns the player to the pool and refunds "
                        "the team the full amount they paid.",
                        style={"color": T.MUTED, "font_size": "0.78rem"}),
                spacing="2", width="100%"),
            columns=rx.breakpoints(initial="1", md="2"), spacing="4", width="100%"),

        _admin_band("🔑", "Access & Economy", "Team PINs and the overall budget boosts."),
        rx.grid(
            T.card(T.section_title("🔑 Reset PIN"), rx.box(height="0.5rem"),
                rx.select(AdminState.teams, value=AdminState.pin_team, placeholder="Team",
                          on_change=AdminState.set_field("pin_team"), width="100%"),
                rx.input(value=AdminState.pin_value, placeholder="New PIN",
                         on_change=AdminState.set_field("pin_value")),
                rx.button("Set PIN", on_click=AdminState.reset_pin, variant="soft",
                          margin_top="0.4rem"), spacing="2", width="100%"),
            T.card(
                rx.vstack(T.section_title("🔑 Distribute PINs"),
                          rx.text("Auto-generate a unique 4-digit PIN for every unclaimed team "
                                  "(e.g. after CSV import).",
                                  style={"color": T.MUTED, "font_size": "0.82rem"}),
                          T.primary_button("Generate PINs", on_click=AdminState.distribute_pins),
                          spacing="2", align="start"),
                rx.cond(
                    AdminState.show_pins,
                    rx.vstack(
                        rx.divider(margin_y="0.7rem"),
                        rx.table.root(
                            rx.table.header(rx.table.row(
                                rx.table.column_header_cell("Team"),
                                rx.table.column_header_cell("PIN"))),
                            rx.table.body(rx.foreach(AdminState.pin_summary, lambda p: rx.table.row(
                                rx.table.row_header_cell(p["name"]),
                                rx.table.cell(rx.code(p["pin"]))))),
                            width="100%"),
                        rx.hstack(
                            rx.button("Copy all", variant="soft", size="2",
                                      on_click=rx.set_clipboard(
                                          AdminState.pin_clipboard_text)),
                            rx.button("Hide", variant="ghost", size="2", color_scheme="gray",
                                      on_click=AdminState.hide_pins),
                            spacing="3", margin_top="0.4rem"),
                        spacing="2", width="100%"),
                ),
                width="100%"),
            T.card(
                rx.vstack(T.section_title("💰 Budget boost"),
                          rx.text("Give every team +100M (e.g. after Gameweek 1 squads lock).",
                                  style={"color": T.MUTED, "font_size": "0.82rem"}),
                          rx.cond(
                              AdminState.manual_boost_applied,
                              rx.text("✅ +100M Applied", size="2", color="green", weight="bold"),
                              T.primary_button("+100M to everyone", on_click=AdminState.boost_all),
                          ),
                          spacing="2", align="start"),
                width="100%"),
            columns=rx.breakpoints(initial="1", md="3"), spacing="4", width="100%"),
        _admin_band("🔁", "Loans", "Temporarily move a player between teams, with a return gameweek."),
        T.card(T.section_title("🔁 Loans"), rx.box(height="0.5rem"),
            rx.hstack(rx.select(AdminState.teams, value=AdminState.loan_from, placeholder="From",
                      on_change=AdminState.set_field("loan_from")),
                      rx.select(AdminState.teams, value=AdminState.loan_to, placeholder="To",
                      on_change=AdminState.set_field("loan_to")),
                      rx.input(value=AdminState.loan_player, placeholder="Player",
                      on_change=AdminState.set_field("loan_player")),
                      rx.input(value=AdminState.loan_gw, placeholder="Return GW", width="100px",
                      on_change=AdminState.set_field("loan_gw")),
                      rx.button("Loan", on_click=AdminState.make_loan, variant="soft"),
                      spacing="2", wrap="wrap"),
            rx.cond(AdminState.loans.length() > 0,
                    rx.vstack(rx.foreach(AdminState.loans, lambda l: rx.hstack(
                        rx.text(l["text"], style={"color": T.MUTED, "font_size": "0.82rem"}),
                        rx.spacer(), rx.button("Reverse", size="1", variant="soft",
                        on_click=AdminState.undo_loan(l["id"])), width="100%", align="center")),
                        spacing="2", width="100%", margin_top="0.5rem"),
                    rx.text("No active loans.", style={"color": T.MUTED}, margin_top="0.4rem")),
            width="100%"),
        _admin_band("📦", "Data & danger zone", "Export/import the room, reset or delete it."),
        T.card(T.section_title("📦 Backup / restore"), rx.box(height="0.5rem"),
            rx.hstack(rx.button("Export JSON", on_click=AdminState.export_room, variant="soft"),
                      rx.button("Import (from box)", on_click=AdminState.import_room, variant="soft"),
                      spacing="3"),
            rx.text_area(value=AdminState.export_text, on_change=AdminState.set_field("export_text"),
                         placeholder="Exported JSON appears here; paste JSON to import.", rows="5",
                         width="100%", margin_top="0.5rem"),
            rx.text_area(value=AdminState.import_text, on_change=AdminState.set_field("import_text"),
                         placeholder="Paste a room JSON, then Import.", rows="3", width="100%",
                         margin_top="0.4rem"), width="100%"),
        T.card(rx.heading("⚠️ Danger zone", style={"color": T.DANGER, "font_family": T.DISPLAY,
               "font_weight": "600"}), rx.box(height="0.5rem"),
            rx.hstack(rx.button("♻️ Reset room", on_click=AdminState.reset_room, color_scheme="amber",
                      variant="soft"),
                      rx.button("🧨 Delete room", on_click=AdminState.delete_room, color_scheme="red"),
                      spacing="3"),
            rx.text("Reset keeps teams + PINs; clears squads, scores, auction state. Delete is permanent.",
                    style={"color": T.MUTED, "font_size": "0.8rem", "margin_top": "0.4rem"}),
            width="100%"),
        _error(AdminState.msg), spacing="4", width="100%")
    return room_shell(_topbar(), room_nav(AdminState.room_code, AdminState.is_admin),
        T.hero(AdminState.room_name + " · Admin", ""),
        rx.cond(AdminState.is_admin, body,
                rx.callout("Only the room admin can access this page.", color_scheme="amber")))


# --------------------------------------------------------------------------- #
# Schedule (fixtures by gameweek)
# --------------------------------------------------------------------------- #
def schedule_page():
    return room_shell(
        _topbar(), room_nav(ScheduleState.room_code, ScheduleState.is_admin),
        T.hero(ScheduleState.room_name + " · Schedule", ""),
        rx.cond(
            ScheduleState.has_schedule,
            rx.vstack(
                rx.hstack(rx.text("Gameweek:", style={"color": T.MUTED}),
                          rx.select(ScheduleState.gw_options, value=ScheduleState.selected_gw,
                                    on_change=ScheduleState.select_gw, width="120px"),
                          T.pill(ScheduleState.gw_name, T.ACCENT),
                          spacing="3", align="center", width="100%"),
                rx.cond(
                    ScheduleState.is_admin,
                    rx.text("To score a gameweek, paste its WhoScored match links in the 🛠️ Admin "
                            "tab → Gameweek control.", style={"color": T.MUTED, "font_size": "0.82rem"})),
                rx.box(height="0.8rem"),
                T.card(
                    rx.cond(
                        ScheduleState.matches.length() > 0,
                        rx.vstack(rx.foreach(ScheduleState.matches, lambda mt: rx.hstack(
                            rx.text(mt["teams"], style={"color": T.TEXT, "font_weight": "500"}),
                            rx.spacer(),
                            rx.text(mt["date"] + " · " + mt["time"],
                                    style={"color": T.MUTED, "font_size": "0.82rem"}),
                            rx.text(mt["venue"], style={"color": T.MUTED, "font_size": "0.78rem",
                                    "min_width": "200px", "text_align": "right"}),
                            width="100%", align="center", spacing="3",
                            style={"background": T.SURFACE_2, "border": f"1px solid {T.BORDER}",
                                   "border_radius": "10px", "padding": "0.55rem 0.9rem"})),
                            spacing="2", width="100%"),
                        rx.text("No matches listed.", style={"color": T.MUTED})),
                    width="100%"),
                width="100%", align="start"),
            rx.callout("No schedule available for this tournament.", color_scheme="gray"),
        ),
    )


# --------------------------------------------------------------------------- #
# WhoScored points calculator (all participants)
# --------------------------------------------------------------------------- #
def ws_row(r):
    return rx.table.row(
        rx.table.row_header_cell(r["player"]),
        rx.table.cell(r["team"]),
        rx.table.cell(T.pill(r["pos"], T.PRIMARY)),
        rx.table.cell(r["minutes"] + "'"),
        rx.table.cell(rx.text(r["score"] + " pts", style={"color": T.ACCENT, "font_weight": "600"})),
    )


def calculator_page():
    return T.page_shell(
        _topbar(),
        rx.hstack(
            rx.cond(WhoScoredState.room_code != "",
                    rx.link("← Back to room", href="/room?room=" + WhoScoredState.room_code,
                            style={"color": T.ACCENT}),
                    rx.link("← Rooms", href="/rooms", style={"color": T.MUTED})),
            spacing="4", width="100%"),
        rx.box(height="0.5rem"),
        T.hero("Match calculator", "Paste any WhoScored match link to compute fantasy points for "
               "every player in that match. Available to everyone."),
        T.card(
            rx.hstack(
                rx.input(value=WhoScoredState.url, on_change=WhoScoredState.set_field("url"),
                         placeholder="https://www.whoscored.com/matches/…/live/…", width="100%",
                         size="3"),
                rx.cond(WhoScoredState.running,
                        rx.button(rx.spinner(), "Running…", disabled=True, size="3"),
                        T.primary_button("Run", on_click=WhoScoredState.run, size="3")),
                spacing="3", width="100%"),
            rx.text("WhoScored has strong bot protection — if a run fails, try again in a moment.",
                    style={"color": T.MUTED, "font_size": "0.78rem", "margin_top": "0.4rem"}),
            _error(WhoScoredState.error),
            width="100%"),
        rx.box(height="1rem"),
        rx.cond(
            WhoScoredState.results.length() > 0,
            T.card(
                rx.hstack(T.section_title("Player points"), rx.spacer(),
                          T.pill(WhoScoredState.count.to_string() + " players", T.ACCENT),
                          width="100%", align="center"),
                rx.box(height="0.5rem"),
                rx.table.root(
                    rx.table.header(rx.table.row(
                        rx.table.column_header_cell("Player"), rx.table.column_header_cell("Team"),
                        rx.table.column_header_cell("Pos"), rx.table.column_header_cell("Min"),
                        rx.table.column_header_cell("Points"))),
                    rx.table.body(rx.foreach(WhoScoredState.results, ws_row)), width="100%"),
                width="100%"),
        ),
    )


# --------------------------------------------------------------------------- #
# App
# --------------------------------------------------------------------------- #
app = rx.App(style={"font_family": T.FONT}, stylesheets=["/custom.css"])


def _serve_prebuilt_frontend(reflex_asgi):
    """Make Reflex's OWN backend serve the pre-built static frontend.

    On the cloud (Render 512MB) the runtime ``reflex run --env prod`` frontend compile
    spikes ~700MB and OOM-kills the instance; Caddy/nginx to serve a pre-built frontend
    is blocked by Render's sandbox. So we pre-build the frontend at image-build time and
    run ``reflex run --backend-only`` (no compile, ~190MB) — and this wrapper serves
    those static files directly from the backend ASGI app. Backend HTTP paths and ALL
    websockets go to Reflex; everything else is served as static files."""
    import os
    static_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".web", "build", "client")
    if not os.path.isdir(static_dir):
        return reflex_asgi  # dev / not pre-built → use Reflex as-is
    from starlette.staticfiles import StaticFiles
    static = StaticFiles(directory=static_dir, html=True)
    backend_prefixes = ("/_event", "/ping", "/_upload", "/_health", "/backend",
                        "/sitemap", "/.well-known")

    async def asgi(scope, receive, send):
        if scope.get("type") == "http" and not scope.get("path", "/").startswith(backend_prefixes):
            try:
                await static(scope, receive, send)
                return
            except Exception:
                pass  # fall back to Reflex (e.g. SPA route not found as a file)
        await reflex_asgi(scope, receive, send)

    return asgi


app.api_transformer = _serve_prebuilt_frontend


app.add_page(index, route="/", title="Fantasy Sports", on_load=AppState.redirect_if_logged_in)
app.add_page(rooms_page, route="/rooms", title="Your Rooms",
             on_load=[AppState.load_rooms, SchedulerState.ensure_running])
app.add_page(setup_page, route="/setup", title="Room Setup", on_load=AppState.load_setup)
app.add_page(room_page, route="/room", title="Room", on_load=RoomState.on_load_hub)
app.add_page(squads_page, route="/squads", title="Squads", on_load=RoomState.on_load_hub)
app.add_page(bidding_page, route="/bidding", title="Open Bidding",
             on_load=BiddingState.on_load_bidding)
app.add_page(trade_page, route="/trade", title="Trades", on_load=TradeState.on_load_trade)
app.add_page(standings_page, route="/standings", title="Standings",
             on_load=[SeasonState.on_load_standings, RoomState.on_load_hub])
app.add_page(admin_page, route="/admin", title="Admin",
             on_load=[AdminState.on_load_admin, SeasonState.on_load_standings, RoomState.on_load_hub])
app.add_page(calculator_page, route="/calculator", title="Match Calculator",
             on_load=WhoScoredState.guard)
app.add_page(schedule_page, route="/schedule", title="Schedule",
             on_load=ScheduleState.on_load_schedule)
