"""Fantasy Auction Platform — Reflex app (migration of the legacy Streamlit app).

Phase 2 pages: sign-up/login, room dashboard (create/join), admin room setup
(teams + PINs + CSV squad upload). The live auction room (/room) is a placeholder
filled in Phase 3.
"""

import reflex as rx

from . import theme
from .state import AppState


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
        rx.grid(create_room_card(), join_room_card(), columns="2", spacing="4", width="100%"),
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
            columns="2", spacing="4", width="100%",
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
# Auction room (Phase 3 placeholder)
# --------------------------------------------------------------------------- #
def room_page() -> rx.Component:
    return theme.page_shell(
        _topbar(),
        theme.card(
            rx.vstack(
                rx.heading("🔴 Live auction", size="6", style={"color": theme.TEXT}),
                rx.text("The real-time auction room is built in Phase 3.",
                        style={"color": theme.MUTED}),
                rx.link("← Back to rooms", href="/rooms", style={"color": theme.ACCENT}),
                spacing="3", align="start",
            )
        ),
    )


# --------------------------------------------------------------------------- #
# App
# --------------------------------------------------------------------------- #
app = rx.App(theme=theme.theme, style={"font_family": theme.FONT})
app.add_page(index, route="/", title="Fantasy Auction",
             on_load=AppState.redirect_if_logged_in)
app.add_page(rooms_page, route="/rooms", title="Your Rooms",
             on_load=AppState.load_rooms)
app.add_page(setup_page, route="/setup", title="Room Setup",
             on_load=AppState.load_setup)
app.add_page(room_page, route="/room", title="Auction Room",
             on_load=AppState.require_login)
