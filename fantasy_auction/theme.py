"""Visual identity, ported from the legacy app's premium dark theme.

Palette taken from ``.streamlit/config.toml`` + ``ui_theme.py``:
  background  #00172B (deep navy)   surface  #002b4d
  primary     #007BFF (blue)        accent   #00CCFF (cyan)
  text        #E6F1FF               muted    #8b949e
"""

import reflex as rx

BG = "#00172B"
SURFACE = "#012a4a"
SURFACE_2 = "#013a63"
BORDER = "#1b4965"
PRIMARY = "#007BFF"
ACCENT = "#00CCFF"
TEXT = "#E6F1FF"
MUTED = "#8b949e"
DANGER = "#ff5470"
SUCCESS = "#2ec4b6"

FONT = "Inter, ui-sans-serif, system-ui, sans-serif"
MONO = "'Roboto Mono', ui-monospace, monospace"

# App-wide theme: dark, blue accent.
theme = rx.theme(appearance="dark", accent_color="blue", radius="large")


def card(*children, **props) -> rx.Component:
    """A surface panel with the house style."""
    style = {
        "background": SURFACE,
        "border": f"1px solid {BORDER}",
        "border_radius": "14px",
        "padding": "1.5rem",
        "box_shadow": "0 8px 30px rgba(0,0,0,0.35)",
    }
    style.update(props.pop("style", {}))
    return rx.box(*children, style=style, **props)


def page_shell(*children, **props) -> rx.Component:
    """Full-height page background wrapper."""
    return rx.box(
        rx.box(
            *children,
            width="100%",
            max_width="1100px",
            margin="0 auto",
            padding="2rem 1.25rem",
        ),
        style={"min_height": "100vh", "background": BG, "color": TEXT},
        width="100%",
        **props,
    )


def hero(title: str, subtitle: str = "") -> rx.Component:
    return rx.vstack(
        rx.heading(title, size="8", style={"color": TEXT, "letter_spacing": "-0.5px"}),
        rx.cond(
            subtitle != "",
            rx.text(subtitle, style={"color": MUTED, "font_size": "1.05rem"}),
        ),
        spacing="1",
        align="start",
        margin_bottom="1.5rem",
    )


def primary_button(text: str, **props) -> rx.Component:
    return rx.button(
        text,
        style={
            "background": f"linear-gradient(90deg, {PRIMARY}, {ACCENT})",
            "color": "white",
            "font_weight": "600",
            "cursor": "pointer",
        },
        **props,
    )
