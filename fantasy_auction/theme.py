"""Visual identity — a premium dark design system.

Glassmorphism surfaces, a violet→cyan gradient accent, Space Grotesk display +
Inter body type, soft shadows and motion. Function names (card/page_shell/hero/
primary_button) are stable so all pages pick up the new look automatically.
"""

import reflex as rx

# --- palette -------------------------------------------------------------- #
BG = "#08080c"            # near-black base
BG2 = "#0d0d14"
SURFACE = "rgba(255,255,255,0.045)"   # glass
SURFACE_2 = "rgba(255,255,255,0.07)"
BORDER = "rgba(255,255,255,0.09)"
BORDER_Hi = "rgba(255,255,255,0.16)"
PRIMARY = "#7c5cff"       # violet
ACCENT = "#22d3ee"        # cyan
TEXT = "#f4f5fb"
MUTED = "#9aa0b8"
DANGER = "#fb7185"
SUCCESS = "#34d399"
WARNING = "#fbbf24"

GRADIENT = f"linear-gradient(135deg, {PRIMARY} 0%, {ACCENT} 100%)"

FONT = "Inter, ui-sans-serif, system-ui, sans-serif"
DISPLAY = "'Space Grotesk', Inter, sans-serif"
MONO = "'Space Mono', ui-monospace, monospace"


def card(*children, **props) -> rx.Component:
    """A glass surface panel."""
    style = {
        "background": SURFACE,
        "backdrop_filter": "blur(14px)",
        "-webkit-backdrop-filter": "blur(14px)",
        "border": f"1px solid {BORDER}",
        "border_radius": "18px",
        "padding": "1.5rem",
        "box_shadow": "0 10px 40px rgba(0,0,0,0.35)",
    }
    style.update(props.pop("style", {}))
    cls = ("glass-card " + props.pop("class_name", "")).strip()
    return rx.box(*children, style=style, class_name=cls, **props)


def page_shell(*children, theme_class="app-bg", **props) -> rx.Component:
    """Full-height page with the ambient gradient-glow background.

    ``theme_class`` may be a per-tournament class (e.g. "app-bg theme-fifa") so the
    room takes on the tournament's colours.
    """
    return rx.box(
        rx.box(
            *children,
            width="100%",
            max_width="1140px",
            margin="0 auto",
            padding="2rem 1.25rem 4rem",
            position="relative",
            z_index="1",
        ),
        class_name=theme_class,
        style={"min_height": "100vh", "background": BG, "color": TEXT,
               "font_family": FONT, "position": "relative", "overflow_x": "hidden"},
        width="100%",
        **props,
    )



def hero(title: str, subtitle: str = "") -> rx.Component:
    return rx.vstack(
        rx.heading(title, class_name="gradient-text",
                   style={"font_family": DISPLAY, "font_size": "2.4rem", "font_weight": "700",
                          "letter_spacing": "-1px", "line_height": "1.1"}),
        rx.cond(subtitle != "",
                rx.text(subtitle, style={"color": MUTED, "font_size": "1.02rem"})),
        spacing="2", align="start", margin_bottom="1.75rem",
    )


def section_title(text: str, **props) -> rx.Component:
    return rx.heading(text, size="5",
                      style={"color": TEXT, "font_family": DISPLAY, "font_weight": "600",
                             "letter_spacing": "-0.3px"}, **props)


def primary_button(text, **props) -> rx.Component:
    return rx.button(
        text,
        class_name="btn-primary",
        style={"background": GRADIENT, "color": "#0a0a0f", "font_weight": "700",
               "border": "none", "cursor": "pointer", "border_radius": "12px"},
        **props,
    )


def pill(text, color=PRIMARY) -> rx.Component:
    return rx.box(text, style={
        "background": f"color-mix(in srgb, {color} 16%, transparent)",
        "color": color, "border": f"1px solid color-mix(in srgb, {color} 35%, transparent)",
        "padding": "3px 11px", "border_radius": "999px", "font_size": "0.72rem",
        "font_weight": "700", "letter_spacing": "0.3px", "white_space": "nowrap"})


def stat(label: str, value, accent=ACCENT) -> rx.Component:
    """A compact stat tile."""
    return card(
        rx.text(label, style={"color": MUTED, "font_size": "0.72rem", "letter_spacing": "0.5px",
                              "text_transform": "uppercase"}),
        rx.heading(value, style={"color": TEXT, "font_family": DISPLAY, "font_size": "1.7rem",
                                 "font_weight": "700"}),
        style={"padding": "1rem 1.25rem"},
    )
