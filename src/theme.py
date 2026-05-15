"""
src/theme.py
─────────────
ATOM — Dark Glassmorphism theme.

Usage in app.py (add near the top, after st.set_page_config):

    from src.theme import apply_theme
    apply_theme()

That's it. Everything else is handled here.
"""

import streamlit as st


# ── Google Fonts ──────────────────────────────────────────────────────────────
# Syne       → display / logo / headers  (geometric, futuristic weight 700-800)
# DM Sans    → body text / chat / UI     (clean, friendly, readable at small sizes)
# JetBrains Mono → code blocks          (designed for code, very readable)

FONTS = """
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@700;800&family=DM+Sans:ital,wght@0,300;0,400;0,500;1,300&family=JetBrains+Mono:wght@400;500&display=swap');
"""

# ── CSS variables & palette ───────────────────────────────────────────────────
# All colours reference these variables so tweaking the theme means
# changing ~10 lines, not hunting through 300 lines of CSS.

VARIABLES = """
:root {
  /* Core palette */
  --atom-bg-base:      #060914;
  --atom-bg-mid:       #0d1220;
  --atom-bg-deep:      #080c18;

  /* Glass surfaces */
  --glass-surface:     rgba(255,255,255,0.04);
  --glass-border:      rgba(255,255,255,0.08);
  --glass-hover:       rgba(255,255,255,0.08);
  --glass-card:        rgba(255,255,255,0.05);
  --glass-card-border: rgba(255,255,255,0.10);

  /* Indigo accent */
  --accent:            #6366f1;
  --accent-soft:       rgba(99,102,241,0.20);
  --accent-border:     rgba(99,102,241,0.35);
  --accent-glow:       rgba(99,102,241,0.45);
  --accent-text:       #a5b4fc;
  --accent-text-dim:   rgba(165,180,252,0.55);

  /* Text hierarchy */
  --text-primary:      rgba(255,255,255,0.90);
  --text-secondary:    rgba(255,255,255,0.55);
  --text-tertiary:     rgba(255,255,255,0.30);
  --text-muted:        rgba(255,255,255,0.18);

  /* Sidebar */
  --sidebar-bg:        rgba(6,9,20,0.85);
  --sidebar-border:    rgba(255,255,255,0.07);

  /* Input */
  --input-bg:          rgba(255,255,255,0.05);
  --input-border:      rgba(255,255,255,0.10);
  --input-focus:       rgba(99,102,241,0.45);

  /* Fonts */
  --font-display:      'Syne', sans-serif;
  --font-body:         'DM Sans', sans-serif;
  --font-mono:         'JetBrains Mono', monospace;

  /* Radii */
  --r-sm:  6px;
  --r-md:  10px;
  --r-lg:  14px;
  --r-xl:  20px;
  --r-full:50px;
}
"""

# ── Animated gradient background ─────────────────────────────────────────────
BACKGROUND = """
.stApp {
  background: linear-gradient(135deg, var(--atom-bg-base) 0%, var(--atom-bg-mid) 45%, var(--atom-bg-deep) 100%) !important;
  background-size: 300% 300% !important;
  animation: atomBgShift 14s ease infinite !important;
  font-family: var(--font-body) !important;
}
@keyframes atomBgShift {
  0%   { background-position: 0%   50%; }
  50%  { background-position: 100% 50%; }
  100% { background-position: 0%   50%; }
}

/* Noise texture overlay for depth */
.stApp::before {
  content: '';
  position: fixed; inset: 0; z-index: 0; pointer-events: none;
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)' opacity='0.03'/%3E%3C/svg%3E");
  opacity: 0.4;
}

.block-container { padding-top: 1.8rem !important; position: relative; z-index: 1; }
"""

# ── Typography — all text elements ────────────────────────────────────────────
TYPOGRAPHY = """
.stApp p, .stApp span, .stApp div, .stApp label,
.stApp li, .stApp td, .stApp th {
  font-family: var(--font-body) !important;
  color: var(--text-primary) !important;
}
.stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6 {
  font-family: var(--font-display) !important;
  color: var(--text-primary) !important;
  letter-spacing: -0.3px;
}

/* Animated gradient header — used for page titles */
.atom-page-title {
  font-family: var(--font-display) !important;
  font-size: 26px; font-weight: 800;
  background: linear-gradient(90deg, #ffffff 0%, var(--accent-text) 50%, #818cf8 100%);
  background-size: 200%;
  -webkit-background-clip: text !important;
  -webkit-text-fill-color: transparent !important;
  animation: titleSlide 5s linear infinite;
  display: inline-block;
}
@keyframes titleSlide {
  0%   { background-position: 0%;   }
  100% { background-position: 200%; }
}

/* Code blocks */
.stApp code, .stApp pre {
  font-family: var(--font-mono) !important;
  background: rgba(255,255,255,0.05) !important;
  border: 1px solid var(--glass-border) !important;
  border-radius: var(--r-sm) !important;
  color: var(--accent-text) !important;
}
"""

# ── Sidebar ───────────────────────────────────────────────────────────────────
SIDEBAR = """
section[data-testid="stSidebar"] {
  background: var(--sidebar-bg) !important;
  border-right: 1px solid var(--sidebar-border) !important;
  backdrop-filter: blur(20px) !important;
}
section[data-testid="stSidebar"] * {
  color: var(--text-primary) !important;
  font-family: var(--font-body) !important;
}

/* Logo */
section[data-testid="stSidebar"] h1 {
  font-family: var(--font-display) !important;
  font-size: 26px !important; font-weight: 800 !important;
  color: #fff !important;
  text-shadow: 0 0 22px var(--accent-glow), 0 0 44px rgba(99,102,241,0.2);
  animation: logoPulse 3.5s ease-in-out infinite;
  letter-spacing: -0.5px !important;
}
@keyframes logoPulse {
  0%,100% { text-shadow: 0 0 22px var(--accent-glow), 0 0 44px rgba(99,102,241,0.2); }
  50%      { text-shadow: 0 0 32px rgba(99,102,241,0.9), 0 0 64px rgba(99,102,241,0.4); }
}

/* Nav radio buttons → styled as nav items */
section[data-testid="stSidebar"] .stRadio > div {
  gap: 2px !important;
}
section[data-testid="stSidebar"] .stRadio label {
  padding: 8px 12px !important;
  border-radius: var(--r-md) !important;
  color: var(--text-secondary) !important;
  font-size: 13px !important;
  transition: all 0.18s ease !important;
  display: flex !important; align-items: center !important;
  cursor: pointer !important;
}
section[data-testid="stSidebar"] .stRadio label:hover {
  background: var(--glass-hover) !important;
  color: var(--text-primary) !important;
  padding-left: 16px !important;
}
section[data-testid="stSidebar"] .stRadio label[data-selected="true"] {
  background: var(--accent-soft) !important;
  border: 1px solid var(--accent-border) !important;
  color: var(--accent-text) !important;
}
/* Hide the default radio dot */
section[data-testid="stSidebar"] .stRadio input[type="radio"] { display: none !important; }

/* Sidebar buttons */
section[data-testid="stSidebar"] .stButton > button {
  background: var(--glass-surface) !important;
  color: var(--text-secondary) !important;
  border: 1px solid var(--glass-border) !important;
  border-radius: var(--r-full) !important;
  font-family: var(--font-body) !important;
  font-size: 13px !important;
  transition: all 0.18s ease !important;
}
section[data-testid="stSidebar"] .stButton > button:hover {
  background: var(--glass-hover) !important;
  color: var(--text-primary) !important;
  border-color: rgba(255,255,255,0.18) !important;
}
section[data-testid="stSidebar"] .stButton > button * { color: inherit !important; }

/* Divider */
section[data-testid="stSidebar"] hr {
  border-color: var(--glass-border) !important;
}

/* Caption / small text */
section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {
  color: var(--text-tertiary) !important;
  font-size: 11px !important;
}

/* Progress bar (token usage) */
section[data-testid="stSidebar"] .stProgress > div > div {
  background: linear-gradient(90deg, var(--accent), #818cf8) !important;
  border-radius: var(--r-full) !important;
}
section[data-testid="stSidebar"] .stProgress > div {
  background: rgba(255,255,255,0.08) !important;
  border-radius: var(--r-full) !important;
}
"""

# ── Main area buttons ─────────────────────────────────────────────────────────
BUTTONS = """
div[data-testid="stAppViewBlockContainer"] .stButton > button,
div[data-testid="stVerticalBlock"] .stButton > button {
  background: var(--accent-soft) !important;
  color: var(--accent-text) !important;
  border: 1px solid var(--accent-border) !important;
  border-radius: var(--r-md) !important;
  font-family: var(--font-body) !important;
  font-size: 13px !important; font-weight: 500 !important;
  transition: all 0.18s ease !important;
}
div[data-testid="stAppViewBlockContainer"] .stButton > button:hover,
div[data-testid="stVerticalBlock"] .stButton > button:hover {
  background: rgba(99,102,241,0.35) !important;
  border-color: rgba(99,102,241,0.6) !important;
  box-shadow: 0 0 18px var(--accent-glow) !important;
  transform: translateY(-1px) !important;
}
div[data-testid="stAppViewBlockContainer"] .stButton > button *,
div[data-testid="stVerticalBlock"] .stButton > button * { color: var(--accent-text) !important; }
"""

# ── Inputs ────────────────────────────────────────────────────────────────────
INPUTS = """
div[data-testid="stTextInput"] input,
div[data-testid="stNumberInput"] input,
div[data-testid="stTextArea"] textarea {
  background: var(--input-bg) !important;
  color: var(--text-primary) !important;
  border: 1px solid var(--input-border) !important;
  border-radius: var(--r-md) !important;
  font-family: var(--font-body) !important;
  transition: border-color 0.2s !important;
}
div[data-testid="stTextInput"] input:focus,
div[data-testid="stTextArea"] textarea:focus {
  border-color: var(--input-focus) !important;
  box-shadow: 0 0 0 2px rgba(99,102,241,0.15) !important;
}

div[data-testid="stSelectbox"] > div > div {
  background: var(--input-bg) !important;
  color: var(--text-primary) !important;
  border: 1px solid var(--input-border) !important;
  border-radius: var(--r-md) !important;
}
[data-testid="stSelectboxVirtualDropdown"],
[data-testid="stSelectboxVirtualDropdown"] * {
  background: #0d1220 !important;
  color: var(--text-primary) !important;
  border-color: var(--glass-border) !important;
}

div[data-testid="stFileUploader"] > section {
  background: var(--glass-surface) !important;
  border: 1px dashed var(--glass-border) !important;
  border-radius: var(--r-lg) !important;
  transition: border-color 0.2s !important;
}
div[data-testid="stFileUploader"] > section:hover {
  border-color: var(--accent-border) !important;
}
div[data-testid="stFileUploader"] button {
  background: var(--accent-soft) !important;
  color: var(--accent-text) !important;
  border: 1px solid var(--accent-border) !important;
  border-radius: var(--r-md) !important;
}
"""

# ── Chat messages ─────────────────────────────────────────────────────────────
CHAT = """
/* Chat input */
div[data-testid="stChatInput"] textarea {
  background: var(--input-bg) !important;
  color: var(--text-primary) !important;
  border: 1px solid var(--input-border) !important;
  border-radius: var(--r-lg) !important;
  font-family: var(--font-body) !important;
  transition: border-color 0.2s !important;
}
div[data-testid="stChatInput"] textarea:focus {
  border-color: var(--input-focus) !important;
}
div[data-testid="stChatInput"] button {
  background: var(--accent) !important;
  border-radius: 50% !important;
  transition: all 0.18s !important;
}
div[data-testid="stChatInput"] button:hover {
  background: #818cf8 !important;
  box-shadow: 0 0 14px var(--accent-glow) !important;
}

/* Message containers */
div[data-testid="stChatMessage"] {
  border-radius: var(--r-lg) !important;
  border: 1px solid var(--glass-card-border) !important;
  backdrop-filter: blur(8px) !important;
  transition: border-color 0.2s !important;
}
div[data-testid="stChatMessage"]:hover {
  border-color: rgba(255,255,255,0.15) !important;
}
div[data-testid="stChatMessage"] * { color: var(--text-primary) !important; }

/* User bubble — indigo tint */
div[data-testid="stChatMessage"][data-message-author-role="user"] {
  background: rgba(99,102,241,0.12) !important;
  border-color: var(--accent-border) !important;
}

/* Assistant bubble — dark glass */
div[data-testid="stChatMessage"][data-message-author-role="assistant"] {
  background: var(--glass-card) !important;
  border-color: var(--glass-card-border) !important;
}

/* Caption inside chat (mode badge) */
div[data-testid="stChatMessage"] [data-testid="stCaptionContainer"] p {
  color: var(--accent-text-dim) !important;
  font-size: 11px !important;
}
"""

# ── Metrics, alerts, expanders ─────────────────────────────────────────────────
MISC = """
div[data-testid="stMetric"] {
  background: var(--glass-card) !important;
  border: 1px solid var(--glass-card-border) !important;
  border-radius: var(--r-lg) !important;
  padding: 14px !important;
  transition: border-color 0.2s, background 0.2s !important;
}
div[data-testid="stMetric"]:hover {
  border-color: var(--accent-border) !important;
  background: rgba(255,255,255,0.07) !important;
}
div[data-testid="stMetric"] * { color: var(--text-primary) !important; }
div[data-testid="stMetric"] [data-testid="stMetricValue"] {
  color: var(--accent-text) !important;
}

div[data-testid="stAlert"] {
  background: var(--glass-card) !important;
  border: 1px solid var(--glass-card-border) !important;
  border-radius: var(--r-md) !important;
}
div[data-testid="stAlert"] * { color: var(--text-primary) !important; }

div[data-testid="stExpander"] {
  background: var(--glass-card) !important;
  border: 1px solid var(--glass-card-border) !important;
  border-radius: var(--r-md) !important;
  transition: border-color 0.2s !important;
}
div[data-testid="stExpander"]:hover { border-color: rgba(255,255,255,0.15) !important; }
div[data-testid="stExpander"] * { color: var(--text-primary) !important; }

div[data-testid="stDataFrame"] * { color: var(--text-primary) !important; }

div[data-testid="stTabs"] button[role="tab"] {
  color: var(--text-secondary) !important;
  font-family: var(--font-body) !important;
  background: transparent !important;
  border-radius: var(--r-sm) var(--r-sm) 0 0 !important;
  transition: color 0.15s !important;
}
div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
  color: var(--accent-text) !important;
  border-bottom: 2px solid var(--accent) !important;
}

hr { border-color: var(--glass-border) !important; }

div[data-testid="stCaptionContainer"] p { color: var(--text-tertiary) !important; }

/* Auth forms */
div[data-testid="stForm"] input {
  background: var(--input-bg) !important;
  color: var(--text-primary) !important;
  border: 1px solid var(--input-border) !important;
  border-radius: var(--r-md) !important;
}
div[data-testid="stForm"] label,
div[data-testid="stForm"] p,
div[data-testid="stForm"] span { color: var(--text-primary) !important; }

/* Streamlit top toolbar */
header[data-testid="stHeader"] {
  background: rgba(6,9,20,0.85) !important;
  backdrop-filter: blur(16px) !important;
  border-bottom: 1px solid var(--sidebar-border) !important;
}
header[data-testid="stHeader"] button,
header[data-testid="stHeader"] button span,
header[data-testid="stHeader"] button svg,
header[data-testid="stHeader"] a,
header[data-testid="stHeader"] span,
header[data-testid="stHeader"] p {
  color: var(--text-secondary) !important;
  fill: var(--text-secondary) !important;
}

/* Spinner */
div[data-testid="stSpinner"] * { color: var(--accent-text) !important; }
div[data-testid="stSpinner"] svg { stroke: var(--accent) !important; }

/* Radio buttons (main area) */
div[data-testid="stRadio"] label,
div[data-testid="stRadio"] p,
div[data-testid="stRadio"] span { color: var(--text-primary) !important; }

/* Color picker, file uploader labels */
div[data-testid="stColorPicker"] label,
div[data-testid="stFileUploader"] label,
div[data-testid="stFileUploader"] p,
div[data-testid="stFileUploader"] span { color: var(--text-primary) !important; }

/* Badge / code chip in sidebar */
section[data-testid="stSidebar"] .stBadge,
section[data-testid="stSidebar"] code {
  background: var(--accent-soft) !important;
  color: var(--accent-text) !important;
  border: 1px solid var(--accent-border) !important;
}

/* Slider */
div[data-testid="stSlider"] div[role="slider"] {
  background: var(--accent) !important;
  box-shadow: 0 0 8px var(--accent-glow) !important;
}
div[data-testid="stSlider"] div[data-testid="stSliderTrackFill"] {
  background: var(--accent) !important;
}
"""

# ── Loading animation — inject once, reuse anywhere ───────────────────────────
# Use in app.py:  st.markdown('<div class="atom-dots"></div>', unsafe_allow_html=True)
LOADING = """
/* Bouncing dots */
.atom-dots { display: flex; gap: 5px; align-items: center; padding: 4px 0; }
.atom-dots span {
  width: 7px; height: 7px; border-radius: 50%; background: var(--accent);
  animation: atomDot 1.2s ease-in-out infinite;
  display: inline-block;
}
.atom-dots span:nth-child(2) { animation-delay: 0.18s; }
.atom-dots span:nth-child(3) { animation-delay: 0.36s; }
@keyframes atomDot {
  0%,80%,100% { transform: scale(0.55); opacity: 0.3; }
  40%          { transform: scale(1);    opacity: 1;   }
}

/* Skeleton shimmer — wrap any loading placeholder */
.atom-skeleton {
  display: flex; flex-direction: column; gap: 7px; width: 100%;
}
.atom-skeleton-line {
  height: 9px; border-radius: 5px;
  background: linear-gradient(
    90deg,
    rgba(255,255,255,0.04) 25%,
    rgba(255,255,255,0.10) 50%,
    rgba(255,255,255,0.04) 75%
  );
  background-size: 200% 100%;
  animation: atomShimmer 1.5s infinite;
}
@keyframes atomShimmer {
  0%   { background-position:  200% 0; }
  100% { background-position: -200% 0; }
}

/* Streaming cursor */
.atom-cursor {
  display: inline-block; width: 2px; height: 14px;
  background: var(--accent); vertical-align: middle; margin-left: 2px;
  animation: atomCursor 0.75s step-end infinite;
}
@keyframes atomCursor { 0%,100%{opacity:1} 50%{opacity:0} }

/* Live pulse dot (for "searching…" indicator) */
.atom-pulse {
  width: 9px; height: 9px; border-radius: 50%;
  background: var(--accent); display: inline-block;
  animation: atomPulse 1.6s ease-in-out infinite;
}
@keyframes atomPulse {
  0%,100% { box-shadow: 0 0 0 0 rgba(99,102,241,0.6); }
  50%      { box-shadow: 0 0 0 9px rgba(99,102,241,0);  }
}
"""

# ── User badge ────────────────────────────────────────────────────────────────
USER_BADGE = """
.atom-user-badge {
  background: var(--glass-surface);
  border: 1px solid var(--glass-border);
  border-radius: var(--r-md);
  padding: 9px 12px; margin-bottom: 4px;
}
.atom-user-badge .badge-label { color: var(--text-tertiary); font-size: 11px; }
.atom-user-badge .badge-name  { color: var(--text-primary);  font-size: 14px; font-weight: 500; }
.atom-user-badge .badge-user  { color: var(--text-tertiary); font-size: 12px; }

.atom-guest-badge {
  background: rgba(234,179,8,0.08);
  border: 1px solid rgba(234,179,8,0.2);
  border-radius: var(--r-md);
  padding: 9px 12px; margin-bottom: 4px;
}
.atom-guest-badge .badge-label { color: rgba(234,179,8,0.6); font-size: 11px; }
.atom-guest-badge .badge-name  { color: var(--text-primary);  font-size: 14px; font-weight: 500; }
.atom-guest-badge .badge-sub   { color: var(--text-tertiary); font-size: 12px; }
"""

# ── Full assembled CSS ─────────────────────────────────────────────────────────

FULL_CSS = (
    "<style>"
    + FONTS
    + VARIABLES
    + BACKGROUND
    + TYPOGRAPHY
    + SIDEBAR
    + BUTTONS
    + INPUTS
    + CHAT
    + MISC
    + LOADING
    + USER_BADGE
    + "</style>"
)


def apply_theme() -> None:
    """
    Inject the Dark Glassmorphism theme into the Streamlit app.
    Call once near the top of app.py, after st.set_page_config().
    """
    st.markdown(FULL_CSS, unsafe_allow_html=True)


# ── Helper: page title with gradient animation ─────────────────────────────────

def page_title(text: str, subtitle: str = "") -> None:
    """
    Render a gradient-animated page title + optional subtitle.
    Replaces st.markdown("<h2>…</h2>") calls in each agent section.

    Usage:
        from src.theme import page_title
        page_title("AI Finance Planner", "Smart money advice powered by AI")
    """
    sub_html = (
        f"<p style='color:var(--text-tertiary);font-size:13px;margin-top:2px;"
        f"font-family:var(--font-body);'>{subtitle}</p>"
        if subtitle else ""
    )
    st.markdown(
        f"<div class='atom-page-title'>{text}</div>{sub_html}",
        unsafe_allow_html=True
    )


# ── Helper: capability chips row ──────────────────────────────────────────────

def capability_chips(chips: list[str]) -> None:
    """
    Render a row of glass capability chips.

    Usage:
        capability_chips(["Live Search", "Code Help", "Writing"])
    """
    chips_html = "".join(
        f"<span style='"
        f"background:var(--glass-surface);border:1px solid var(--glass-border);"
        f"border-radius:var(--r-full);padding:4px 12px;font-size:11px;"
        f"color:var(--text-secondary);font-family:var(--font-body);'>"
        f"{c}</span>"
        for c in chips
    )
    st.markdown(
        f"<div style='display:flex;gap:7px;flex-wrap:wrap;margin-bottom:4px;'>"
        f"{chips_html}</div>",
        unsafe_allow_html=True
    )


# ── Helper: user/guest sidebar badge ─────────────────────────────────────────

def sidebar_user_badge(is_logged_in: bool, user_name: str, username: str) -> None:
    """
    Render the user identity badge in the sidebar.
    Replaces the raw st.markdown() badge blocks in app.py.
    """
    if is_logged_in:
        st.markdown(
            f"<div class='atom-user-badge'>"
            f"<span class='badge-label'>Signed in as</span><br>"
            f"<span class='badge-name'>{user_name}</span> "
            f"<span class='badge-user'>· {username}</span>"
            f"</div>",
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            "<div class='atom-guest-badge'>"
            "<span class='badge-label'>Browsing as</span><br>"
            "<span class='badge-name'>Guest</span> "
            "<span class='badge-sub'>· History not saved</span>"
            "</div>",
            unsafe_allow_html=True
        )