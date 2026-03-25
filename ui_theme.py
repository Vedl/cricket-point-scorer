"""
╔══════════════════════════════════════════════════════════════╗
║  FANTASY CRICKET AUCTION — PREMIUM UI THEME ENGINE          ║
║  Futuristic glassmorphism + 3D depth design system          ║
║  Zero business logic — pure visual layer                    ║
╚══════════════════════════════════════════════════════════════╝
"""
import streamlit as st

# ═══════════════════════════════════════════════════════════
# COLOR TOKENS
# ═══════════════════════════════════════════════════════════
COLORS = {
    "bg_primary": "#0a0e1a",
    "bg_secondary": "#0f1629",
    "bg_card": "rgba(15, 22, 41, 0.65)",
    "bg_card_hover": "rgba(20, 30, 55, 0.8)",
    "bg_sidebar": "#080c18",
    "accent_blue": "#00d4ff",
    "accent_cyan": "#00ffd5",
    "accent_red": "#ff3366",
    "accent_gold": "#ffd700",
    "accent_purple": "#a855f7",
    "text_primary": "#e6edf3",
    "text_secondary": "#8b949e",
    "text_muted": "#484f58",
    "border": "rgba(0, 212, 255, 0.12)",
    "border_glow": "rgba(0, 212, 255, 0.3)",
    "glass": "rgba(255, 255, 255, 0.03)",
    "success": "#00ffa3",
    "warning": "#ffaa00",
    "error": "#ff4466",
}


# ═══════════════════════════════════════════════════════════
# MAIN CSS INJECTION
# ═══════════════════════════════════════════════════════════
def get_premium_css():
    return """
    <style>
    /* ══════════ GOOGLE FONTS ══════════ */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Orbitron:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500&display=swap');

    /* ══════════ ROOT VARIABLES ══════════ */
    :root {
        --bg-primary: #0a0e1a;
        --bg-secondary: #0f1629;
        --bg-card: rgba(15, 22, 41, 0.65);
        --accent-blue: #00d4ff;
        --accent-cyan: #00ffd5;
        --accent-red: #ff3366;
        --accent-gold: #ffd700;
        --accent-purple: #a855f7;
        --text-primary: #e6edf3;
        --text-secondary: #8b949e;
        --border-glass: rgba(0, 212, 255, 0.12);
        --border-glow: rgba(0, 212, 255, 0.25);
        --glass-surface: rgba(255, 255, 255, 0.03);
        --shadow-depth: 0 8px 32px rgba(0, 0, 0, 0.4);
        --shadow-glow-blue: 0 0 20px rgba(0, 212, 255, 0.15);
        --shadow-glow-red: 0 0 20px rgba(255, 51, 102, 0.15);
        --radius-lg: 16px;
        --radius-md: 12px;
        --radius-sm: 8px;
    }

    /* ══════════ GLOBAL BACKGROUND ══════════ */
    .stApp, [data-testid="stAppViewContainer"] {
        background: linear-gradient(145deg, #060911 0%, #0a0e1a 30%, #0d1225 60%, #0a1020 100%) !important;
        color: var(--text-primary) !important;
        font-family: 'Inter', -apple-system, sans-serif !important;
    }

    .stApp::before {
        content: '';
        position: fixed;
        top: 0; left: 0; right: 0; bottom: 0;
        background:
            radial-gradient(ellipse at 20% 0%, rgba(0, 212, 255, 0.04) 0%, transparent 50%),
            radial-gradient(ellipse at 80% 100%, rgba(255, 51, 102, 0.03) 0%, transparent 50%),
            radial-gradient(ellipse at 50% 50%, rgba(168, 85, 247, 0.02) 0%, transparent 60%);
        pointer-events: none;
        z-index: 0;
    }

    [data-testid="stMain"] {
        background: transparent !important;
    }

    /* ══════════ TYPOGRAPHY ══════════ */
    h1 {
        font-family: 'Orbitron', sans-serif !important;
        font-weight: 800 !important;
        color: #ffffff !important;
        text-shadow: 0 0 30px rgba(0, 212, 255, 0.3), 0 0 60px rgba(0, 212, 255, 0.1) !important;
        letter-spacing: 1px !important;
        font-size: 2.2rem !important;
        padding-bottom: 0.3rem !important;
    }

    h2 {
        font-family: 'Orbitron', sans-serif !important;
        font-weight: 700 !important;
        color: #f0f6fc !important;
        text-shadow: 0 0 20px rgba(0, 212, 255, 0.2) !important;
        letter-spacing: 0.5px !important;
        font-size: 1.5rem !important;
    }

    h3 {
        font-family: 'Inter', sans-serif !important;
        font-weight: 700 !important;
        color: #e6edf3 !important;
        font-size: 1.2rem !important;
        letter-spacing: 0.3px !important;
    }

    p, li, span, label, .stMarkdown {
        font-family: 'Inter', sans-serif !important;
        color: var(--text-primary) !important;
    }

    /* ══════════ SIDEBAR ══════════ */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #060911 0%, #0a0f1e 40%, #0c1225 100%) !important;
        border-right: 1px solid rgba(0, 212, 255, 0.08) !important;
        box-shadow: 4px 0 24px rgba(0, 0, 0, 0.5) !important;
    }

    [data-testid="stSidebar"]::before {
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 2px;
        background: linear-gradient(90deg, transparent, var(--accent-blue), var(--accent-purple), transparent);
        opacity: 0.6;
    }

    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
    [data-testid="stSidebar"] .stCaption p {
        color: var(--text-secondary) !important;
        font-size: 0.85rem !important;
    }

    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3 {
        font-size: 1rem !important;
        letter-spacing: 1.5px !important;
        text-transform: uppercase !important;
        color: var(--accent-blue) !important;
        text-shadow: 0 0 15px rgba(0, 212, 255, 0.3) !important;
        border-bottom: 1px solid rgba(0, 212, 255, 0.1);
        padding-bottom: 8px;
        margin-bottom: 12px;
    }

    /* Sidebar radio/nav */
    [data-testid="stSidebar"] [role="radiogroup"] {
        gap: 4px !important;
    }

    [data-testid="stSidebar"] [role="radiogroup"] label {
        background: rgba(255, 255, 255, 0.02) !important;
        border: 1px solid rgba(255, 255, 255, 0.04) !important;
        border-radius: var(--radius-sm) !important;
        padding: 10px 14px !important;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
        margin: 2px 0 !important;
    }

    [data-testid="stSidebar"] [role="radiogroup"] label:hover {
        background: rgba(0, 212, 255, 0.06) !important;
        border-color: rgba(0, 212, 255, 0.2) !important;
        transform: translateX(4px);
    }

    [data-testid="stSidebar"] [role="radiogroup"] label[data-checked="true"],
    [data-testid="stSidebar"] [role="radiogroup"] label[aria-checked="true"] {
        background: rgba(0, 212, 255, 0.08) !important;
        border-color: rgba(0, 212, 255, 0.35) !important;
        box-shadow: 0 0 15px rgba(0, 212, 255, 0.1), inset 0 0 15px rgba(0, 212, 255, 0.03) !important;
    }

    /* Sidebar dividers */
    [data-testid="stSidebar"] hr {
        border-color: rgba(0, 212, 255, 0.08) !important;
        margin: 16px 0 !important;
    }

    /* ══════════ BUTTONS ══════════ */
    .stButton > button {
        background: linear-gradient(135deg, rgba(0, 212, 255, 0.1) 0%, rgba(0, 212, 255, 0.05) 100%) !important;
        color: var(--accent-blue) !important;
        border: 1px solid rgba(0, 212, 255, 0.2) !important;
        border-radius: var(--radius-sm) !important;
        font-family: 'Inter', sans-serif !important;
        font-weight: 600 !important;
        padding: 8px 20px !important;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
        text-shadow: 0 0 10px rgba(0, 212, 255, 0.3) !important;
        letter-spacing: 0.3px !important;
        backdrop-filter: blur(8px) !important;
    }

    .stButton > button:hover {
        background: linear-gradient(135deg, rgba(0, 212, 255, 0.2) 0%, rgba(0, 212, 255, 0.1) 100%) !important;
        border-color: rgba(0, 212, 255, 0.4) !important;
        box-shadow: 0 0 20px rgba(0, 212, 255, 0.2), 0 4px 15px rgba(0, 0, 0, 0.3) !important;
        transform: translateY(-1px) !important;
        color: #fff !important;
    }

    .stButton > button:active {
        transform: translateY(0) !important;
    }

    /* Primary Buttons */
    .stButton > button[kind="primary"],
    .stButton > button[data-testid="stBaseButton-primary"] {
        background: linear-gradient(135deg, #00d4ff 0%, #0099cc 50%, #00d4ff 100%) !important;
        background-size: 200% 200% !important;
        color: #0a0e1a !important;
        border: none !important;
        font-weight: 700 !important;
        text-shadow: none !important;
        box-shadow: 0 0 20px rgba(0, 212, 255, 0.3), 0 4px 15px rgba(0, 0, 0, 0.3) !important;
    }

    .stButton > button[kind="primary"]:hover,
    .stButton > button[data-testid="stBaseButton-primary"]:hover {
        background-position: 100% 0 !important;
        box-shadow: 0 0 30px rgba(0, 212, 255, 0.5), 0 6px 20px rgba(0, 0, 0, 0.4) !important;
        color: #0a0e1a !important;
    }

    /* ══════════ INPUTS ══════════ */
    .stTextInput > div > div > input,
    .stNumberInput > div > div > input,
    .stSelectbox > div > div,
    .stMultiSelect > div > div,
    .stTextArea > div > div > textarea {
        background: rgba(15, 22, 41, 0.6) !important;
        border: 1px solid rgba(0, 212, 255, 0.12) !important;
        border-radius: var(--radius-sm) !important;
        color: var(--text-primary) !important;
        font-family: 'Inter', sans-serif !important;
        transition: all 0.3s ease !important;
        backdrop-filter: blur(8px) !important;
    }

    .stTextInput > div > div > input:focus,
    .stNumberInput > div > div > input:focus,
    .stTextArea > div > div > textarea:focus {
        border-color: var(--accent-blue) !important;
        box-shadow: 0 0 15px rgba(0, 212, 255, 0.15), inset 0 0 10px rgba(0, 212, 255, 0.05) !important;
    }

    /* Input labels */
    .stTextInput label, .stNumberInput label, .stSelectbox label,
    .stMultiSelect label, .stTextArea label, .stRadio label,
    .stCheckbox label {
        color: var(--text-secondary) !important;
        font-weight: 500 !important;
        font-size: 0.85rem !important;
        letter-spacing: 0.5px !important;
        text-transform: uppercase !important;
    }

    /* ══════════ TABS ══════════ */
    .stTabs [data-baseweb="tab-list"] {
        background: rgba(15, 22, 41, 0.4) !important;
        border-radius: var(--radius-md) !important;
        padding: 4px !important;
        border: 1px solid rgba(0, 212, 255, 0.08) !important;
        gap: 4px !important;
    }

    .stTabs [data-baseweb="tab"] {
        background: transparent !important;
        border-radius: var(--radius-sm) !important;
        color: var(--text-secondary) !important;
        font-family: 'Inter', sans-serif !important;
        font-weight: 600 !important;
        font-size: 0.85rem !important;
        padding: 10px 18px !important;
        transition: all 0.3s ease !important;
        border: none !important;
    }

    .stTabs [data-baseweb="tab"]:hover {
        background: rgba(0, 212, 255, 0.06) !important;
        color: var(--text-primary) !important;
    }

    .stTabs [aria-selected="true"] {
        background: rgba(0, 212, 255, 0.1) !important;
        color: var(--accent-blue) !important;
        box-shadow: 0 0 15px rgba(0, 212, 255, 0.1), inset 0 0 10px rgba(0, 212, 255, 0.05) !important;
        border: 1px solid rgba(0, 212, 255, 0.2) !important;
    }

    .stTabs [data-baseweb="tab-highlight"] {
        background: var(--accent-blue) !important;
        height: 2px !important;
        box-shadow: 0 0 10px var(--accent-blue) !important;
    }

    .stTabs [data-baseweb="tab-border"] {
        display: none !important;
    }

    /* ══════════ EXPANDERS ══════════ */
    .streamlit-expanderHeader {
        background: rgba(15, 22, 41, 0.5) !important;
        border: 1px solid rgba(0, 212, 255, 0.08) !important;
        border-radius: var(--radius-sm) !important;
        color: var(--text-primary) !important;
        font-weight: 600 !important;
        transition: all 0.3s ease !important;
    }

    .streamlit-expanderHeader:hover {
        border-color: rgba(0, 212, 255, 0.2) !important;
        background: rgba(0, 212, 255, 0.04) !important;
    }

    details[data-testid="stExpander"] {
        background: rgba(15, 22, 41, 0.3) !important;
        border: 1px solid rgba(0, 212, 255, 0.08) !important;
        border-radius: var(--radius-md) !important;
        overflow: hidden;
    }

    details[data-testid="stExpander"] summary {
        color: var(--text-primary) !important;
        font-weight: 600 !important;
        padding: 14px 18px !important;
    }

    details[data-testid="stExpander"] summary:hover {
        color: var(--accent-blue) !important;
    }

    details[data-testid="stExpander"] > div {
        border-top: 1px solid rgba(0, 212, 255, 0.06) !important;
    }

    /* ══════════ METRICS ══════════ */
    [data-testid="stMetric"] {
        background: var(--bg-card) !important;
        border: 1px solid var(--border-glass) !important;
        border-radius: var(--radius-md) !important;
        padding: 18px 20px !important;
        backdrop-filter: blur(12px) !important;
        box-shadow: var(--shadow-depth), inset 0 1px 0 rgba(255,255,255,0.03) !important;
        transition: all 0.3s ease !important;
    }

    [data-testid="stMetric"]:hover {
        border-color: var(--border-glow) !important;
        box-shadow: var(--shadow-depth), var(--shadow-glow-blue) !important;
        transform: translateY(-2px);
    }

    [data-testid="stMetric"] [data-testid="stMetricLabel"] {
        color: var(--text-secondary) !important;
        font-weight: 600 !important;
        text-transform: uppercase !important;
        font-size: 0.7rem !important;
        letter-spacing: 1.5px !important;
    }

    [data-testid="stMetric"] [data-testid="stMetricValue"] {
        color: #ffffff !important;
        font-family: 'Orbitron', sans-serif !important;
        font-weight: 700 !important;
        font-size: 1.6rem !important;
        text-shadow: 0 0 15px rgba(0, 212, 255, 0.3) !important;
    }

    [data-testid="stMetric"] [data-testid="stMetricDelta"] {
        font-weight: 600 !important;
    }

    /* ══════════ DATAFRAMES & TABLES ══════════ */
    [data-testid="stDataFrame"],
    .stDataFrame {
        border-radius: var(--radius-md) !important;
        overflow: hidden !important;
        border: 1px solid rgba(0, 212, 255, 0.1) !important;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3) !important;
    }

    [data-testid="stDataFrame"] [data-testid="glideDataEditor"] {
        border-radius: var(--radius-md) !important;
    }

    /* ══════════ ALERTS (success, warning, error, info) ══════════ */
    [data-testid="stAlert"] {
        border-radius: var(--radius-sm) !important;
        backdrop-filter: blur(8px) !important;
        font-family: 'Inter', sans-serif !important;
        border-left-width: 3px !important;
    }

    .stSuccess, div[data-testid="stAlert"][data-baseweb*="positive"] {
        background: rgba(0, 255, 163, 0.05) !important;
        border-color: rgba(0, 255, 163, 0.3) !important;
    }

    .stWarning, div[data-testid="stAlert"][data-baseweb*="warning"] {
        background: rgba(255, 170, 0, 0.05) !important;
        border-color: rgba(255, 170, 0, 0.3) !important;
    }

    .stError, div[data-testid="stAlert"][data-baseweb*="negative"] {
        background: rgba(255, 68, 102, 0.05) !important;
        border-color: rgba(255, 68, 102, 0.3) !important;
    }

    .stInfo, div[data-testid="stAlert"][data-baseweb*="info"] {
        background: rgba(0, 212, 255, 0.05) !important;
        border-color: rgba(0, 212, 255, 0.3) !important;
    }

    /* ══════════ DIVIDERS ══════════ */
    hr {
        border-color: rgba(0, 212, 255, 0.06) !important;
        margin: 24px 0 !important;
    }

    /* ══════════ CONTAINERS & GLASS CARDS ══════════ */
    [data-testid="stVerticalBlock"] > [data-testid="stVerticalBlockBorderWrapper"] {
        background: var(--bg-card) !important;
        border: 1px solid var(--border-glass) !important;
        border-radius: var(--radius-md) !important;
        backdrop-filter: blur(12px) !important;
        box-shadow: var(--shadow-depth), inset 0 1px 0 rgba(255,255,255,0.03) !important;
        padding: 4px !important;
    }

    /* ══════════ SCROLLBAR ══════════ */
    ::-webkit-scrollbar {
        width: 6px;
        height: 6px;
    }
    ::-webkit-scrollbar-track {
        background: rgba(10, 14, 26, 0.5);
    }
    ::-webkit-scrollbar-thumb {
        background: rgba(0, 212, 255, 0.2);
        border-radius: 3px;
    }
    ::-webkit-scrollbar-thumb:hover {
        background: rgba(0, 212, 255, 0.4);
    }

    /* ══════════ LIVE BADGE ANIMATION ══════════ */
    @keyframes livePulse {
        0%, 100% { opacity: 1; box-shadow: 0 0 8px rgba(255, 0, 0, 0.6); }
        50% { opacity: 0.7; box-shadow: 0 0 20px rgba(255, 0, 0, 0.9); }
    }

    @keyframes glowShift {
        0%, 100% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
    }

    @keyframes subtleBreathe {
        0%, 100% { box-shadow: 0 0 15px rgba(0, 212, 255, 0.1); }
        50% { box-shadow: 0 0 25px rgba(0, 212, 255, 0.2); }
    }

    .live-badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 5px 14px;
        border-radius: 20px;
        font-size: 0.7rem;
        font-weight: 700;
        letter-spacing: 2px;
        text-transform: uppercase;
        animation: livePulse 2s infinite;
        color: #fff;
    }

    /* ══════════ CUSTOM COMPONENT CLASSES ══════════ */

    /* Glass Panel */
    .glass-panel {
        background: rgba(15, 22, 41, 0.55);
        border: 1px solid rgba(0, 212, 255, 0.1);
        border-radius: 16px;
        padding: 24px;
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        box-shadow:
            0 8px 32px rgba(0, 0, 0, 0.4),
            inset 0 1px 0 rgba(255, 255, 255, 0.04),
            inset 0 -1px 0 rgba(0, 0, 0, 0.2);
        position: relative;
        overflow: hidden;
    }

    .glass-panel::before {
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 1px;
        background: linear-gradient(90deg, transparent, rgba(0, 212, 255, 0.3), transparent);
    }

    /* Hero Header */
    .hero-header {
        text-align: center;
        padding: 40px 20px 30px;
        position: relative;
    }

    .hero-header h1 {
        font-family: 'Orbitron', sans-serif !important;
        font-size: 2.8rem !important;
        font-weight: 900 !important;
        background: linear-gradient(135deg, #ffffff 0%, #00d4ff 50%, #00ffd5 100%);
        background-size: 200% 200%;
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        animation: glowShift 4s ease infinite;
        margin-bottom: 8px !important;
        text-shadow: none !important;
    }

    .hero-header p {
        color: #8b949e !important;
        font-size: 1rem !important;
        letter-spacing: 2px !important;
        text-transform: uppercase !important;
        font-weight: 400 !important;
    }

    /* Section Header */
    .section-header {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 16px 0 12px;
        border-bottom: 1px solid rgba(0, 212, 255, 0.08);
        margin-bottom: 16px;
    }

    .section-header .icon {
        font-size: 1.5rem;
        filter: drop-shadow(0 0 8px rgba(0, 212, 255, 0.4));
    }

    .section-header h3 {
        margin: 0 !important;
        font-family: 'Orbitron', sans-serif !important;
        font-weight: 600 !important;
        font-size: 1.1rem !important;
        color: #fff !important;
        letter-spacing: 1px !important;
    }

    .section-header .tag {
        margin-left: auto;
        padding: 3px 10px;
        border-radius: 12px;
        font-size: 0.65rem;
        font-weight: 700;
        letter-spacing: 1.5px;
        text-transform: uppercase;
        background: rgba(0, 212, 255, 0.1);
        border: 1px solid rgba(0, 212, 255, 0.2);
        color: var(--accent-blue);
    }

    /* Metric Row */
    .metric-row {
        display: flex;
        gap: 12px;
        margin: 12px 0;
    }

    .metric-tile {
        flex: 1;
        background: rgba(15, 22, 41, 0.5);
        border: 1px solid rgba(0, 212, 255, 0.08);
        border-radius: 12px;
        padding: 16px;
        text-align: center;
        transition: all 0.3s ease;
        backdrop-filter: blur(8px);
    }

    .metric-tile:hover {
        border-color: rgba(0, 212, 255, 0.2);
        box-shadow: 0 0 15px rgba(0, 212, 255, 0.1);
        transform: translateY(-2px);
    }

    .metric-tile .value {
        font-family: 'Orbitron', sans-serif;
        font-size: 1.5rem;
        font-weight: 700;
        color: #fff;
        text-shadow: 0 0 15px rgba(0, 212, 255, 0.3);
    }

    .metric-tile .label {
        font-size: 0.65rem;
        color: #8b949e;
        text-transform: uppercase;
        letter-spacing: 1.5px;
        margin-top: 6px;
        font-weight: 600;
    }

    /* Status Badge */
    .status-pill {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.7rem;
        font-weight: 700;
        letter-spacing: 1px;
        text-transform: uppercase;
    }

    .status-pill.live {
        background: rgba(255, 0, 0, 0.15);
        border: 1px solid rgba(255, 0, 0, 0.3);
        color: #ff4444;
        animation: livePulse 2s infinite;
    }

    .status-pill.success {
        background: rgba(0, 255, 163, 0.1);
        border: 1px solid rgba(0, 255, 163, 0.25);
        color: #00ffa3;
    }

    .status-pill.warning {
        background: rgba(255, 170, 0, 0.1);
        border: 1px solid rgba(255, 170, 0, 0.25);
        color: #ffaa00;
    }

    .status-pill.info {
        background: rgba(0, 212, 255, 0.1);
        border: 1px solid rgba(0, 212, 255, 0.25);
        color: #00d4ff;
    }

    /* Auction Player Card */
    .auction-player-card {
        background: linear-gradient(135deg, rgba(15, 22, 41, 0.7), rgba(0, 212, 255, 0.05));
        border: 1px solid rgba(0, 212, 255, 0.15);
        border-radius: 20px;
        padding: 32px;
        text-align: center;
        position: relative;
        overflow: hidden;
        box-shadow: 0 12px 40px rgba(0, 0, 0, 0.5), 0 0 30px rgba(0, 212, 255, 0.08);
        animation: subtleBreathe 3s ease infinite;
    }

    .auction-player-card::before {
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 3px;
        background: linear-gradient(90deg, transparent, var(--accent-blue), var(--accent-cyan), transparent);
    }

    .auction-player-card .player-name {
        font-family: 'Orbitron', sans-serif;
        font-size: 1.8rem;
        font-weight: 800;
        color: #fff;
        text-shadow: 0 0 30px rgba(0, 212, 255, 0.35);
        margin-bottom: 4px;
    }

    .auction-player-card .player-role {
        font-size: 0.8rem;
        color: var(--accent-blue);
        text-transform: uppercase;
        letter-spacing: 2px;
        font-weight: 600;
    }

    .auction-player-card .bid-display {
        margin-top: 20px;
        padding: 16px;
        background: rgba(0, 0, 0, 0.3);
        border-radius: 12px;
        border: 1px solid rgba(0, 212, 255, 0.1);
    }

    .auction-player-card .bid-amount {
        font-family: 'Orbitron', sans-serif;
        font-size: 2.5rem;
        font-weight: 900;
        color: var(--accent-gold);
        text-shadow: 0 0 20px rgba(255, 215, 0, 0.4);
    }

    .auction-player-card .bidder-name {
        font-size: 0.85rem;
        color: var(--accent-cyan);
        font-weight: 600;
        margin-top: 4px;
    }

    /* Timer Bar */
    .timer-bar-container {
        margin-top: 16px;
        background: rgba(0, 0, 0, 0.3);
        border-radius: 8px;
        overflow: hidden;
        height: 8px;
        border: 1px solid rgba(255, 255, 255, 0.05);
    }

    .timer-bar-fill {
        height: 100%;
        border-radius: 8px;
        transition: width 1s linear;
        box-shadow: 0 0 10px currentColor;
    }

    .timer-bar-fill.safe { background: linear-gradient(90deg, #00ffa3, #00d4ff); color: #00ffa3; }
    .timer-bar-fill.warning { background: linear-gradient(90deg, #ffaa00, #ff6600); color: #ffaa00; }
    .timer-bar-fill.danger { background: linear-gradient(90deg, #ff3366, #ff0000); color: #ff3366; }

    /* Room Card */
    .room-card {
        background: rgba(15, 22, 41, 0.5);
        border: 1px solid rgba(0, 212, 255, 0.08);
        border-radius: 14px;
        padding: 20px;
        transition: all 0.3s ease;
        cursor: pointer;
    }

    .room-card:hover {
        border-color: rgba(0, 212, 255, 0.25);
        box-shadow: 0 8px 30px rgba(0, 0, 0, 0.4), 0 0 20px rgba(0, 212, 255, 0.1);
        transform: translateY(-3px);
    }

    /* Login Container */
    .login-container {
        max-width: 440px;
        margin: 0 auto;
        padding: 40px 32px;
        background: rgba(15, 22, 41, 0.55);
        border: 1px solid rgba(0, 212, 255, 0.1);
        border-radius: 20px;
        backdrop-filter: blur(20px);
        box-shadow: 0 12px 40px rgba(0, 0, 0, 0.5), 0 0 30px rgba(0, 212, 255, 0.05);
        position: relative;
        overflow: hidden;
    }

    .login-container::before {
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 2px;
        background: linear-gradient(90deg, transparent, var(--accent-blue), var(--accent-cyan), transparent);
    }

    .login-header {
        text-align: center;
        margin-bottom: 20px;
    }

    .login-header h1 {
        font-family: 'Orbitron', sans-serif !important;
        font-size: 2rem !important;
        font-weight: 800 !important;
        background: linear-gradient(135deg, #ffffff, #00d4ff);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        text-shadow: none !important;
    }

    /* Broadcaster Header */
    .broadcast-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 14px 24px;
        background: rgba(15, 22, 41, 0.5);
        border: 1px solid rgba(0, 212, 255, 0.08);
        border-radius: 14px;
        margin-bottom: 24px;
        backdrop-filter: blur(12px);
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
    }

    .broadcast-header .title-group {
        display: flex;
        align-items: center;
        gap: 15px;
    }

    .broadcast-header .trophy-icon {
        font-size: 2.5rem;
        filter: drop-shadow(0 0 12px rgba(255, 215, 0, 0.5));
    }

    .broadcast-header h3 {
        margin: 0 !important;
        font-family: 'Orbitron', sans-serif !important;
        color: #fff !important;
        font-size: 1.3rem !important;
        line-height: 1.2 !important;
        text-shadow: 0 0 20px rgba(0, 212, 255, 0.2) !important;
    }

    .broadcast-header .subtitle {
        color: #8b949e;
        font-size: 0.7rem;
        letter-spacing: 3px;
        font-weight: 600;
        text-transform: uppercase;
    }

    /* Column panels for create/join */
    .action-panel {
        background: rgba(15, 22, 41, 0.45);
        border: 1px solid rgba(0, 212, 255, 0.08);
        border-radius: 16px;
        padding: 24px;
        height: 100%;
        backdrop-filter: blur(12px);
        transition: all 0.3s ease;
    }

    .action-panel:hover {
        border-color: rgba(0, 212, 255, 0.15);
    }

    .action-panel h2 {
        font-size: 1.1rem !important;
        margin-bottom: 16px !important;
    }

    /* Sidebar room info card */
    .sidebar-room-card {
        background: rgba(0, 212, 255, 0.04);
        border: 1px solid rgba(0, 212, 255, 0.1);
        border-radius: 10px;
        padding: 12px 14px;
        margin: 8px 0;
    }

    .sidebar-room-card .room-name {
        font-family: 'Orbitron', sans-serif;
        font-size: 0.85rem;
        font-weight: 700;
        color: #fff;
    }

    .sidebar-room-card .room-code {
        display: inline-block;
        margin-top: 6px;
        padding: 2px 10px;
        background: rgba(0, 212, 255, 0.1);
        border: 1px solid rgba(0, 212, 255, 0.2);
        border-radius: 6px;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.75rem;
        color: var(--accent-blue);
        letter-spacing: 2px;
    }

    /* ══════════ TOAST / POPOVER FIX ══════════ */
    [data-testid="stToast"] {
        background: rgba(15, 22, 41, 0.9) !important;
        border: 1px solid rgba(0, 212, 255, 0.2) !important;
        border-radius: var(--radius-md) !important;
        backdrop-filter: blur(16px) !important;
    }

    /* ══════════ SELECTBOX DROPDOWN ══════════ */
    [data-baseweb="popover"] {
        background: rgba(15, 22, 41, 0.95) !important;
        border: 1px solid rgba(0, 212, 255, 0.15) !important;
        border-radius: var(--radius-sm) !important;
        backdrop-filter: blur(16px) !important;
    }

    [data-baseweb="menu"] {
        background: transparent !important;
    }

    [data-baseweb="menu"] li {
        color: var(--text-primary) !important;
        transition: all 0.2s ease !important;
    }

    [data-baseweb="menu"] li:hover {
        background: rgba(0, 212, 255, 0.08) !important;
    }

    /* ══════════ MULTISELECT TAGS ══════════ */
    [data-baseweb="tag"] {
        background: rgba(0, 212, 255, 0.1) !important;
        border: 1px solid rgba(0, 212, 255, 0.2) !important;
        color: var(--accent-blue) !important;
        border-radius: 6px !important;
    }

    /* ══════════ CHECKBOX & RADIO ══════════ */
    .stCheckbox > label > span[data-testid="stCheckbox"],
    .stRadio > label > div {
        color: var(--text-primary) !important;
    }

    /* ══════════ HIDE STREAMLIT DEFAULTS ══════════ */
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    header[data-testid="stHeader"] {
        background: rgba(10, 14, 26, 0.8) !important;
        backdrop-filter: blur(12px) !important;
        border-bottom: 1px solid rgba(0, 212, 255, 0.05) !important;
    }

    /* ══════════ RESPONSIVE ══════════ */
    @media (max-width: 768px) {
        .hero-header h1 { font-size: 1.8rem !important; }
        .auction-player-card .player-name { font-size: 1.3rem; }
        .auction-player-card .bid-amount { font-size: 1.8rem; }
        .broadcast-header { flex-direction: column; gap: 10px; text-align: center; }
        .metric-row { flex-direction: column; }
    }

    </style>
    """


# ═══════════════════════════════════════════════════════════
# THEME INJECTION FUNCTION
# ═══════════════════════════════════════════════════════════
def inject_premium_theme():
    """Injects the full premium CSS theme into the Streamlit app."""
    st.markdown(get_premium_css(), unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════
# REUSABLE HTML COMPONENT HELPERS
# ═══════════════════════════════════════════════════════════

def hero_header(title: str, subtitle: str = ""):
    """Renders a large gradient hero header."""
    sub_html = f'<p>{subtitle}</p>' if subtitle else ''
    st.markdown(f"""
    <div class="hero-header">
        <h1>{title}</h1>
        {sub_html}
    </div>
    """, unsafe_allow_html=True)


def section_header(icon: str, title: str, tag: str = ""):
    """Renders a styled section header with icon and optional tag."""
    tag_html = f'<span class="tag">{tag}</span>' if tag else ''
    st.markdown(f"""
    <div class="section-header">
        <span class="icon">{icon}</span>
        <h3>{title}</h3>
        {tag_html}
    </div>
    """, unsafe_allow_html=True)


def status_badge(text: str, badge_type: str = "info"):
    """Renders an inline status pill badge. Types: live, success, warning, info."""
    return f'<span class="status-pill {badge_type}">{text}</span>'


def metric_row(metrics: list):
    """
    Renders a row of metric tiles.
    metrics: list of dicts with 'value', 'label', and optional 'icon' keys.
    """
    tiles = ""
    for m in metrics:
        icon = m.get('icon', '')
        tiles += f"""
        <div class="metric-tile">
            <div class="value">{icon} {m['value']}</div>
            <div class="label">{m['label']}</div>
        </div>
        """
    st.markdown(f'<div class="metric-row">{tiles}</div>', unsafe_allow_html=True)


def glass_card_start():
    """Opens a glass panel div (use with glass_card_end)."""
    st.markdown('<div class="glass-panel">', unsafe_allow_html=True)


def glass_card_end():
    """Closes a glass panel div."""
    st.markdown('</div>', unsafe_allow_html=True)


def broadcast_header(tournament_type: str):
    """Renders the broadcaster-style header bar."""
    st.markdown(f"""
    <div class="broadcast-header">
        <div class="title-group">
            <span class="trophy-icon">🏆</span>
            <div>
                <h3>{tournament_type}</h3>
                <div class="subtitle">Official Auction Terminal</div>
            </div>
        </div>
        <div>
            <span class="status-pill live">📡 LIVE SIGNAL</span>
        </div>
    </div>
    """, unsafe_allow_html=True)


def sidebar_room_info(room_name: str, room_code: str):
    """Renders a compact room info card in the sidebar."""
    st.sidebar.markdown(f"""
    <div class="sidebar-room-card">
        <div class="room-name">{room_name}</div>
        <div class="room-code">{room_code}</div>
    </div>
    """, unsafe_allow_html=True)


def auction_player_card(player_name: str, role: str, team: str, bid: int, bidder: str):
    """Renders the dominant auction player card."""
    bidder_html = f'<div class="bidder-name">👤 {bidder}</div>' if bidder else '<div class="bidder-name">No bids yet</div>'
    bid_display = f'{bid}M' if bid > 0 else 'BASE'
    
    st.markdown(f"""
    <div class="auction-player-card">
        <div class="player-role">{team} • {role}</div>
        <div class="player-name">{player_name}</div>
        <div class="bid-display">
            <div class="bid-amount">{bid_display}</div>
            {bidder_html}
        </div>
    </div>
    """, unsafe_allow_html=True)


def timer_bar(seconds_left: float, total_seconds: float = 15.0):
    """Renders a visual timer progress bar."""
    pct = max(0, min(100, (seconds_left / total_seconds) * 100))
    if pct > 50:
        bar_class = "safe"
    elif pct > 25:
        bar_class = "warning"
    else:
        bar_class = "danger"
    
    st.markdown(f"""
    <div class="timer-bar-container">
        <div class="timer-bar-fill {bar_class}" style="width: {pct}%"></div>
    </div>
    """, unsafe_allow_html=True)


def login_glass_start():
    """Opens the login glass container."""
    st.markdown('<div class="login-container">', unsafe_allow_html=True)


def login_glass_end():
    """Closes the login glass container."""
    st.markdown('</div>', unsafe_allow_html=True)
