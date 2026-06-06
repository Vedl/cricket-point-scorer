import re

with open("fantasy_auction/fantasy_auction.py", "r") as f:
    content = f.read()

# I want to rewrite the body of admin_page up to the Data & Danger zone
start = content.find("def admin_page():")
end_danger = content.find("_admin_band(\"⚠️\", \"Data & Danger zone\"", start)

original = content[start:end_danger]

new_code = """def admin_page():
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
            T.card(T.section_title("🗑️ Force release"), rx.box(height="0.5rem"),
                rx.select(AdminState.teams, value=AdminState.fr_team, placeholder="Team",
                          on_change=AdminState.pick_fr_team, width="100%"),
                rx.select(AdminState.fr_team_players, value=AdminState.fr_player,
                          placeholder="Player from that team",
                          on_change=AdminState.set_field("fr_player"), width="100%"),
                rx.checkbox("Refund buy price", checked=AdminState.fr_refund,
                            on_change=AdminState.set_field("fr_refund")),
                rx.button("Release", on_click=AdminState.force_release, color_scheme="red",
                          variant="soft", margin_top="0.4rem"), spacing="2", width="100%"),
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
                          rx.text("Auto-generate a unique 4-digit PIN for every unclaimed team.",
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
                        rx.spacer(),
                        rx.button("Return", size="1", variant="ghost", color_scheme="red",
                                  on_click=AdminState.return_loan(l["id"])),
                        width="100%", align="center")),
                        spacing="1", width="100%", margin_top="0.6rem"),
                    rx.text("No active loans.", style={"color": T.MUTED, "font_size": "0.82rem", "margin_top": "0.4rem"})),
            width="100%"),

        """

content = content.replace(original, new_code)
with open("fantasy_auction/fantasy_auction.py", "w") as f:
    f.write(content)
print("Replaced!")
