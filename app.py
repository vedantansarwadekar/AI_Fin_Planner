import os
import sys
import glob
import toml
import pathlib
import streamlit as st
import pandas as pd
import streamlit_authenticator as stauth

# --------------------------------------------------
# Fix import path
# --------------------------------------------------
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT_DIR)

from src.agents.finance_agent import run_finance_agent
from src.agents.rag_agent import StockMarketRAGAgent
from src.agents.data_agent import DataAnalystAgent
from src.database import (
    init_db,
    save_analysis, get_analysis_history, delete_analysis_history,
    save_finance_message, get_finance_history, clear_finance_history,
    save_rag_message, get_rag_history, clear_rag_history,
)
from src.llm import get_usage_stats
from src.config import AUTH_COOKIE_SECRET

# --------------------------------------------------
# Bootstrap DB on every start (creates tables if missing)
# --------------------------------------------------
init_db()

# --------------------------------------------------
# Page Config
# --------------------------------------------------
st.set_page_config(
    page_title="ATOM – Multi-Agent AI Platform",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --------------------------------------------------
# THEME CSS
# --------------------------------------------------
st.markdown("""
<style>
.stApp { background-color: #f5f5f7 !important; }
.block-container { padding-top: 2rem !important; }

.stApp p, .stApp span, .stApp div,
.stApp label, .stApp li, .stApp h1, .stApp h2,
.stApp h3, .stApp h4, .stApp h5, .stApp h6 {
    color: #1d1d1f;
}

div[data-testid="stAppViewBlockContainer"] .stButton > button,
div[data-testid="stVerticalBlock"] .stButton > button {
    background-color: #111827 !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 8px !important;
}
div[data-testid="stAppViewBlockContainer"] .stButton > button p,
div[data-testid="stAppViewBlockContainer"] .stButton > button span,
div[data-testid="stVerticalBlock"] .stButton > button p,
div[data-testid="stVerticalBlock"] .stButton > button span {
    color: #ffffff !important;
}
div[data-testid="stAppViewBlockContainer"] .stButton > button:hover,
div[data-testid="stVerticalBlock"] .stButton > button:hover {
    background-color: #000000 !important;
}

div[data-testid="stFileUploader"] button {
    background-color: #111827 !important;
    color: #ffffff !important;
    border-radius: 8px !important;
}
div[data-testid="stFileUploader"] button span,
div[data-testid="stFileUploader"] button p { color: #ffffff !important; }

div[data-testid="stTextInput"] input,
div[data-testid="stNumberInput"] input {
    background-color: #ffffff !important;
    color: #1d1d1f !important;
    border: 1px solid #d1d1d6 !important;
    border-radius: 8px !important;
}

div[data-testid="stSelectbox"] > div > div,
div[data-testid="stSelectbox"] > div > div > div {
    background-color: #ffffff !important;
    color: #1d1d1f !important;
    border: 1px solid #d1d1d6 !important;
    border-radius: 8px !important;
}
div[data-testid="stSelectbox"] label,
div[data-testid="stSelectbox"] p,
div[data-testid="stSelectbox"] span { color: #1d1d1f !important; }
[data-testid="stSelectboxVirtualDropdown"],
[data-testid="stSelectboxVirtualDropdown"] * {
    background-color: #ffffff !important;
    color: #1d1d1f !important;
}

div[data-testid="stRadio"] label,
div[data-testid="stRadio"] p,
div[data-testid="stRadio"] span { color: #1d1d1f !important; }

div[data-testid="stColorPicker"] label,
div[data-testid="stColorPicker"] p,
div[data-testid="stColorPicker"] span { color: #1d1d1f !important; }

div[data-testid="stFileUploader"] label,
div[data-testid="stFileUploader"] p,
div[data-testid="stFileUploader"] span { color: #1d1d1f !important; }
div[data-testid="stFileUploader"] > section {
    background-color: #ffffff !important;
    border: 1px dashed #d1d1d6 !important;
    border-radius: 8px !important;
}

div[data-testid="stExpander"] {
    background-color: #ffffff !important;
    border: 1px solid #e5e5e7 !important;
    border-radius: 8px !important;
}
div[data-testid="stExpander"] summary,
div[data-testid="stExpander"] p,
div[data-testid="stExpander"] span { color: #1d1d1f !important; }

div[data-testid="stAlert"] p,
div[data-testid="stAlert"] span,
div[data-testid="stAlert"] div { color: #1d1d1f !important; }

div[data-testid="stCaptionContainer"] p { color: #555555 !important; }
div[data-testid="stDataFrame"] * { color: #1d1d1f !important; }
div[data-testid="stMetric"] * { color: #1d1d1f !important; }

div[data-testid="stTabs"] button,
div[data-testid="stTabs"] button p,
div[data-testid="stTabs"] button span { color: #1d1d1f !important; }

hr { border-color: #e5e5e7 !important; }

section[data-testid="stSidebar"] {
    background-color: #ffffff !important;
    border-right: 1px solid #e5e5e7 !important;
}
section[data-testid="stSidebar"] * { color: #1d1d1f !important; }
section[data-testid="stSidebar"] .stButton > button {
    background-color: #ffffff !important;
    color: #1d1d1f !important;
    border: 1px solid #d1d1d6 !important;
    border-radius: 25px !important;
}
section[data-testid="stSidebar"] .stButton > button *,
section[data-testid="stSidebar"] .stButton > button span,
section[data-testid="stSidebar"] .stButton > button p {
    color: #1d1d1f !important;
    background-color: transparent !important;
}
section[data-testid="stSidebar"] .stButton > button:hover { background-color: #f2f2f2 !important; }
section[data-testid="stSidebar"] .stButton > button:hover * { color: #1d1d1f !important; }

div[data-testid="stChatInput"] textarea {
    background-color: #ffffff !important;
    color: #1d1d1f !important;
    border: 1px solid #d1d1d6 !important;
}
div[data-testid="stChatInput"] button {
    background-color: #1d1d1f !important;
    color: white !important;
    border-radius: 50% !important;
}

div[data-testid="stChatMessage"] * { color: #1d1d1f !important; }
div[data-testid="stChatMessage"][data-message-author-role="user"] { background-color: #e8e8ed !important; }
div[data-testid="stChatMessage"][data-message-author-role="assistant"] { background-color: #ffffff !important; }

header[data-testid="stHeader"] {
    background-color: #1d1d1f !important;
}
header[data-testid="stHeader"] button,
header[data-testid="stHeader"] button span,
header[data-testid="stHeader"] button svg,
header[data-testid="stHeader"] a,
header[data-testid="stHeader"] span,
header[data-testid="stHeader"] p {
    color: #ffffff !important;
    fill: #ffffff !important;
}

section[data-testid="stSidebar"] .stBadge,
section[data-testid="stSidebar"] [data-testid="stBadge"],
section[data-testid="stSidebar"] code,
section[data-testid="stSidebar"] .stCode {
    background-color: #e8e8ed !important;
    color: #1d1d1f !important;
}
section[data-testid="stSidebar"] code * {
    color: #1d1d1f !important;
}

div[data-testid="stForm"] input {
    background-color: #ffffff !important;
    color: #1d1d1f !important;
    border: 1px solid #d1d1d6 !important;
    border-radius: 8px !important;
}
div[data-testid="stForm"] label,
div[data-testid="stForm"] p,
div[data-testid="stForm"] span {
    color: #1d1d1f !important;
}

div[data-testid="stTabs"] button[role="tab"] {
    background-color: #f5f5f7 !important;
    color: #1d1d1f !important;
    border-radius: 8px 8px 0 0 !important;
}
div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
    background-color: #ffffff !important;
    border-bottom: 2px solid #111827 !important;
}
</style>
""", unsafe_allow_html=True)

# --------------------------------------------------
# LOAD AUTH CONFIG — read raw TOML to get a plain dict
# that streamlit-authenticator can consume without issues
# --------------------------------------------------
# --------------------------------------------------
# LOAD AUTH CONFIG FROM STREAMLIT SECRETS
# --------------------------------------------------
import streamlit as st

try:
    auth_cfg = st.secrets["auth_config"]
except Exception:
    # fallback for local dev
    auth_cfg = {
        "credentials": {"usernames": {}},
        "cookie": {"name": "atom_auth", "expiry_days": 30},
    }
# Ensure nested keys exist with safe defaults
auth_cfg.setdefault("credentials", {"usernames": {}})
auth_cfg.setdefault("cookie", {"name": "atom_auth", "expiry_days": 30})


authenticator = stauth.Authenticate(
    auth_cfg["credentials"],
    auth_cfg["cookie"]["name"],
    AUTH_COOKIE_SECRET,
    auth_cfg["cookie"]["expiry_days"],
)

# --------------------------------------------------
# Guest mode: login is optional
# --------------------------------------------------
is_logged_in = st.session_state.get("authentication_status") is True
username     = st.session_state.get("username", "guest")
user_name    = st.session_state.get("name",     "Guest")

# --------------------------------------------------
# Session State
# --------------------------------------------------
if "show_intro"        not in st.session_state: st.session_state.show_intro        = True
if "show_auth_modal"   not in st.session_state: st.session_state.show_auth_modal   = False
if "active_agent"      not in st.session_state: st.session_state.active_agent      = "Finance Planner"
if "answer_style"      not in st.session_state: st.session_state.answer_style      = "Detailed"
if "rag_agent"         not in st.session_state: st.session_state.rag_agent         = None
if "rag_ready"         not in st.session_state: st.session_state.rag_ready         = False
if "data_agent"        not in st.session_state: st.session_state.data_agent        = None
if "data_loaded"       not in st.session_state: st.session_state.data_loaded       = False
if "da_fig"            not in st.session_state: st.session_state.da_fig            = None
if "da_answer"         not in st.session_state: st.session_state.da_answer         = None
if "da_plan"           not in st.session_state: st.session_state.da_plan           = None
if "da_chart_override" not in st.session_state: st.session_state.da_chart_override = None
if "da_palette"        not in st.session_state: st.session_state.da_palette        = "Default"
if "da_single_color"   not in st.session_state: st.session_state.da_single_color   = "#4f8ef7"
if "da_use_palette"    not in st.session_state: st.session_state.da_use_palette    = True
if "da_source_names"   not in st.session_state: st.session_state.da_source_names   = []

# Load chat histories from DB (only for logged-in users)
if "finance_messages" not in st.session_state:
    rows = get_finance_history(username) if is_logged_in else []
    st.session_state.finance_messages = [{"role": r["role"], "content": r["content"]} for r in rows]

if "rag_messages" not in st.session_state:
    rows = get_rag_history(username) if is_logged_in else []
    st.session_state.rag_messages = [{"role": r["role"], "content": r["content"]} for r in rows]

if "da_history" not in st.session_state:
    st.session_state.da_history = get_analysis_history(username, limit=50) if is_logged_in else []

# --------------------------------------------------
# Sidebar
# --------------------------------------------------
with st.sidebar:
    st.title("ATOM")

    if is_logged_in:
        st.markdown(
            f"<div style='background:#f0f0f5;border-radius:8px;padding:8px 12px;"
            f"margin-bottom:4px;'>"
            f"<span style='color:#555;font-size:12px;'>Signed in as</span><br>"
            f"<span style='color:#111;font-weight:600;font-size:14px;'>{user_name}</span>"
            f"<span style='color:#888;font-size:12px;'> · {username}</span>"
            f"</div>",
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            "<div style='background:#fff8e1;border-radius:8px;padding:8px 12px;"
            "margin-bottom:4px;border:1px solid #ffe082;'>"
            "<span style='color:#888;font-size:12px;'>Browsing as</span><br>"
            "<span style='color:#111;font-weight:600;font-size:14px;'>Guest</span>"
            "<span style='color:#888;font-size:12px;'> · History not saved</span>"
            "</div>",
            unsafe_allow_html=True
        )
        if st.button("🔑 Sign In / Sign Up", use_container_width=True):
            st.session_state.show_auth_modal = True
            st.rerun()
    st.divider()

    st.session_state.active_agent = st.radio(
        "Choose Agent",
        ["Finance Planner", "Stock Market RAG", "Data Analyst"]
    )

    if st.session_state.active_agent == "Stock Market RAG":
        st.subheader("Answer Style")
        st.session_state.answer_style = st.radio("Select Style", ["Detailed", "Concise"])

    st.divider()

    if st.button("🏠 Go to Home"):
        st.session_state.show_intro = True
        st.rerun()

    if st.session_state.active_agent == "Finance Planner":
        if st.button("🗑 Clear Finance Chat"):
            if is_logged_in: clear_finance_history(username)
            st.session_state.finance_messages = []
            st.rerun()

    if st.session_state.active_agent == "Stock Market RAG":
        if st.button("🗑 Clear RAG Chat"):
            if is_logged_in: clear_rag_history(username)
            st.session_state.rag_messages = []
            st.rerun()

    if st.session_state.active_agent == "Data Analyst":
        if st.button("🗑 Clear Analysis History"):
            if is_logged_in: delete_analysis_history(username)
            st.session_state.da_history        = []
            st.session_state.da_fig            = None
            st.session_state.da_answer         = None
            st.session_state.da_plan           = None
            st.session_state.da_chart_override = None
            st.rerun()

    st.divider()

    usage = get_usage_stats()
    pct   = min(int(usage["tokens_last_minute"] / usage["warn_threshold"] * 100), 100)
    st.caption("🔢 API token usage (last 60s)")
    st.progress(pct)
    st.caption(f"{usage['tokens_last_minute']:,} / {usage['warn_threshold']:,} tokens")

    st.divider()
    if is_logged_in:
        authenticator.logout("🚪 Logout", location="sidebar")

# --------------------------------------------------
# AUTH MODAL (login / sign-up overlay)
# --------------------------------------------------
if st.session_state.get("show_auth_modal") and not is_logged_in:

    st.markdown("---")
    st.markdown("### 🔐 Account")

    login_tab, signup_tab = st.tabs(["Sign In", "Sign Up"])

    with login_tab:
        authenticator.login(location="main")
        if st.session_state.get("authentication_status") is False:
            st.error("Incorrect username or password.")
        elif st.session_state.get("authentication_status") is True:
            st.session_state.show_auth_modal = False
            uname = st.session_state.get("username", "guest")
            st.session_state.finance_messages = [
                {"role": r["role"], "content": r["content"]}
                for r in get_finance_history(uname)
            ]
            st.session_state.rag_messages = [
                {"role": r["role"], "content": r["content"]}
                for r in get_rag_history(uname)
            ]
            st.session_state.da_history = get_analysis_history(uname, limit=50)
            st.rerun()

    with signup_tab:
        st.markdown("Create a new account:")
        new_username  = st.text_input("Choose a username",  key="reg_username")
        new_name      = st.text_input("Your display name",  key="reg_name")
        new_email     = st.text_input("Email address",      key="reg_email")
        new_password  = st.text_input("Choose a password",  type="password", key="reg_pass1")
        confirm_pass  = st.text_input("Confirm password",   type="password", key="reg_pass2")

        if st.button("Create Account", use_container_width=True):
            if not all([new_username, new_name, new_email, new_password, confirm_pass]):
                st.error("Please fill in all fields.")
            elif new_password != confirm_pass:
                st.error("Passwords do not match.")
            elif new_username in auth_cfg["credentials"]["usernames"]:
                st.error(f"Username '{new_username}' is already taken.")
            elif len(new_password) < 6:
                st.error("Password must be at least 6 characters.")
            else:
                import bcrypt
                hashed = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
                auth_cfg["credentials"]["usernames"][new_username] = {
                    "email":    new_email,
                    "name":     new_name,
                    "password": hashed,
                }
                # Write back to secrets.toml
            
                st.warning("⚠️ Signup is disabled in deployed version (read-only environment).")
                
                st.success(f"Account created! You can now sign in as **{new_username}**.")

    if st.button("✕ Cancel", key="close_auth"):
        st.session_state.show_auth_modal = False
        st.rerun()

    st.markdown("---")
    st.stop()

# --------------------------------------------------
# INTRO SCREEN
# --------------------------------------------------
if st.session_state.show_intro:

    st.markdown("<br><br>", unsafe_allow_html=True)
    st.markdown(
        "<h1 style='text-align:center; font-size:64px; color:#111;'>ATOM</h1>",
        unsafe_allow_html=True
    )
    st.markdown(
        f"<p style='text-align:center; font-size:20px; color:#555;'>"
        f"Welcome back, <strong>{user_name}</strong></p>",
        unsafe_allow_html=True
    )
    st.markdown(
        "<p style='text-align:center; font-size:18px; color:#888;'>"
        "A Multi-Agent AI Platform for Finance & Intelligence"
        "</p>",
        unsafe_allow_html=True
    )
    st.markdown("<br>", unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<h3 style='color:#111;'>Features</h3>", unsafe_allow_html=True)
        st.markdown("""
- 💸 Smart Finance Planning
- 📈 Market & Stock Intelligence
- 📚 RBI & SEBI Document AI Search
- 📊 Autonomous Data Analytics
        """)
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Enter Platform", use_container_width=True):
            st.session_state.show_intro = False
            st.rerun()

    st.stop()

# --------------------------------------------------
# FINANCE AGENT
# --------------------------------------------------
if st.session_state.active_agent == "Finance Planner":

    st.markdown("<h2 style='color:#111;'>AI Finance Planner</h2>", unsafe_allow_html=True)

    for msg in st.session_state.finance_messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    if query := st.chat_input("Ask a finance question…"):
        st.session_state.finance_messages.append({"role": "user", "content": query})
        if is_logged_in: save_finance_message(username, "user", query)

        with st.chat_message("assistant"):
            try:
                response = run_finance_agent(query, chat_history=st.session_state.finance_messages)
            except RuntimeError as e:
                response = f"⚠️ {e}"
            st.write(response)

        st.session_state.finance_messages.append({"role": "assistant", "content": response})
        if is_logged_in: save_finance_message(username, "assistant", response)
        st.rerun()

# --------------------------------------------------
# RAG AGENT
# --------------------------------------------------
elif st.session_state.active_agent == "Stock Market RAG":

    st.markdown("<h2 style='color:#111;'>Stock Market RAG Agent</h2>", unsafe_allow_html=True)

    if not st.session_state.rag_ready:
        with st.spinner("Indexing documents..."):
            agent = StockMarketRAGAgent()
            pdfs  = glob.glob("data/pdfs/*.pdf")
            agent.ingest_pdfs(pdfs)
            st.session_state.rag_agent = agent
            st.session_state.rag_ready = True
        st.success("Documents indexed!")
        st.rerun()

    for msg in st.session_state.rag_messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    if query := st.chat_input("Ask from RBI / SEBI PDFs…"):
        st.session_state.rag_messages.append({"role": "user", "content": query})
        if is_logged_in: save_rag_message(username, "user", query)

        try:
            result = st.session_state.rag_agent.ask(query, answer_style=st.session_state.answer_style)
            reply  = result["answer"]
        except RuntimeError as e:
            result = {"answer": f"⚠️ {e}", "sources": []}
            reply  = result["answer"]

        with st.chat_message("assistant"):
            st.markdown(result["answer"])
            if result.get("sources"):
                st.markdown("**Sources:**")
                for src in result["sources"]:
                    st.write(f"{src['source']} | Page {src['page']}")

        st.session_state.rag_messages.append({"role": "assistant", "content": reply})
        if is_logged_in: save_rag_message(username, "assistant", reply)
        st.rerun()

# --------------------------------------------------
# DATA ANALYST AGENT
# --------------------------------------------------
elif st.session_state.active_agent == "Data Analyst":

    st.markdown("<h2 style='color:#111;'>AI Data Analyst</h2>", unsafe_allow_html=True)
    st.markdown(
        "<p style='color:#666; font-size:14px;'>"
        "Upload CSV or Excel · Explore data · Ask questions · Customise charts"
        "</p>",
        unsafe_allow_html=True
    )

    # ── Upload ─────────────────────────────────────────────────────────────
    uploaded_files = st.file_uploader(
        "Upload CSV or Excel files (multiple supported)",
        type=["csv", "xlsx", "xls"],
        accept_multiple_files=True,
    )

    if uploaded_files:
        if st.session_state.data_agent is None:
            st.session_state.data_agent = DataAnalystAgent()

        agent        = st.session_state.data_agent
        loaded_names = []

        for uf in uploaded_files:
            try:
                sheets = DataAnalystAgent.read_file(uf)
                for sheet_name, raw_df in sheets.items():
                    label = uf.name if len(sheets) == 1 else f"{uf.name} — {sheet_name}"
                    agent.load_dataframe(raw_df, source_name=label)
                    loaded_names.append(label)
            except Exception as e:
                st.error(f"Could not read {uf.name}: {e}")

        if loaded_names:
            st.session_state.da_source_names = loaded_names
            st.session_state.data_loaded     = True

            if len(loaded_names) > 1:
                chosen = st.selectbox("Active dataset", options=loaded_names, key="da_active_source")
                agent.load_source(chosen)
            else:
                agent.load_source(loaded_names[0])

            active_df = agent.df
            st.success(
                f"✅ **{loaded_names[-1]}** — "
                f"{active_df.shape[0]:,} rows × {active_df.shape[1]} columns"
            )

    if not st.session_state.data_loaded:
        st.stop()

    # ── Tabs ───────────────────────────────────────────────────────────────
    tab_summary, tab_analyse, tab_history = st.tabs(
        ["📋 Data Summary", "🤖 Ask AI", "📜 History"]
    )

    # ══════════════════════════════
    # TAB 1 — SUMMARY
    # ══════════════════════════════
    with tab_summary:
        summary = st.session_state.data_agent.get_data_summary()

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Rows",    f"{summary['rows']:,}")
        m2.metric("Columns", summary["columns"])
        null_cols  = sum(1 for c in summary["column_details"] if c["nulls"] > 0)
        total_null = sum(c["nulls"] for c in summary["column_details"])
        m3.metric("Columns with nulls", null_cols)
        m4.metric("Total null cells",   f"{total_null:,}")

        st.markdown("---")
        st.markdown("#### Column Details")
        TYPE_ICONS = {"numeric": "🔢", "text": "🔤", "date": "📅"}
        col_data = []
        for c in summary["column_details"]:
            null_badge = f"⚠️ {c['null_pct']}%" if c["nulls"] > 0 else "✅ 0%"
            col_data.append({
                "Column":  c["column"],
                "Type":    TYPE_ICONS.get(c["type"], "") + " " + c["type"],
                "Nulls":   null_badge,
                "Unique":  c["unique"],
                "Details": c["detail"],
            })
        st.dataframe(pd.DataFrame(col_data), use_container_width=True, hide_index=True)

        st.markdown("---")
        st.markdown("#### Data Preview")
        n_rows = st.slider("Rows to show", min_value=5, max_value=100, value=10, step=5)
        st.dataframe(st.session_state.data_agent.df.head(n_rows), use_container_width=True)

    # ══════════════════════════════
    # TAB 2 — ASK AI
    # ══════════════════════════════
    with tab_analyse:
        question = st.text_input(
            "Ask about your dataset",
            placeholder="e.g. show the trend of revenue by month"
        )

        if st.button("Analyze") and question.strip():
            with st.spinner("Analysing with AI…"):
                try:
                    fig, answer, plan = st.session_state.data_agent.analyze(question)
                except RuntimeError as e:
                    st.error(f"⚠️ {e}")
                    st.stop()

            st.session_state.da_fig            = fig
            st.session_state.da_answer         = answer
            st.session_state.da_plan           = plan
            st.session_state.da_chart_override = plan.get("chart")
            st.session_state.da_use_palette    = True

            active_src = (
                st.session_state.da_source_names[-1]
                if st.session_state.da_source_names else None
            )
            if is_logged_in:
                save_analysis(username=username, question=question,
                              answer=answer, plan=plan, dataset=active_src)
                st.session_state.da_history = get_analysis_history(username, limit=50)

        if st.session_state.da_fig is not None and st.session_state.da_plan is not None:
            st.divider()
            chart_col, ctrl_col = st.columns([3, 1])

            with ctrl_col:
                st.markdown("#### 🎛 Chart Controls")
                CHART_ICONS = {
                    "bar": "📊 Bar", "line": "📈 Line", "area": "🏔 Area",
                    "pie": "🥧 Pie", "scatter": "✦ Scatter",
                    "histogram": "📉 Histogram", "box": "📦 Box",
                }
                chart_options = list(CHART_ICONS.keys())
                chart_labels  = [CHART_ICONS[c] for c in chart_options]
                current_chart = st.session_state.da_chart_override or "bar"
                current_idx   = chart_options.index(current_chart) if current_chart in chart_options else 0

                selected_label = st.selectbox(
                    "Chart Type", options=chart_labels, index=current_idx,
                    help="Switch without re-running AI"
                )
                selected_chart = chart_options[chart_labels.index(selected_label)]

                st.markdown("---")
                st.markdown("**🎨 Colour**")
                color_mode = st.radio(
                    "mode", ["Palette", "Single colour"],
                    index=0 if st.session_state.da_use_palette else 1,
                    label_visibility="collapsed"
                )
                use_palette = color_mode == "Palette"

                if use_palette:
                    palette = st.selectbox(
                        "Palette",
                        options=list(DataAnalystAgent.COLOR_PALETTES.keys()),
                        index=list(DataAnalystAgent.COLOR_PALETTES.keys()).index(
                            st.session_state.da_palette
                        ),
                    )
                    single_color = None
                else:
                    palette      = "Default"
                    single_color = st.color_picker("Pick colour", value=st.session_state.da_single_color)

                st.markdown("---")
                st.markdown("**⬇️ Download**")
                dl_fmt = st.selectbox("Format", ["PNG", "SVG", "PDF"], key="dl_fmt")

                if st.button("🔄 Apply & Download", use_container_width=True):
                    st.session_state.da_chart_override = selected_chart
                    st.session_state.da_palette        = palette
                    st.session_state.da_single_color   = single_color or "#4f8ef7"
                    st.session_state.da_use_palette    = use_palette
                    st.session_state.da_fig = st.session_state.data_agent.rerender(
                        plan=st.session_state.da_plan,
                        chart_override=selected_chart,
                        palette=palette,
                        single_color=single_color,
                    )
                    st.rerun()

            with chart_col:
                st.markdown("##### 📋 Answer")
                st.info(st.session_state.da_answer)
                fmt_map   = {"PNG": "png", "SVG": "svg", "PDF": "pdf"}
                dl_format = fmt_map.get(st.session_state.get("dl_fmt", "PNG"), "png")
                st.plotly_chart(
                    st.session_state.da_fig,
                    use_container_width=True,
                    config={
                        "displayModeBar": True,
                        "toImageButtonOptions": {
                            "format": dl_format, "filename": "ATOM_chart",
                            "height": 600, "width": 1000, "scale": 2,
                        },
                        "modeBarButtonsToAdd": ["drawline", "drawopenpath", "eraseshape"],
                    }
                )
                plan = st.session_state.da_plan
                st.caption(
                    f"🤖 AI: **{plan.get('chart','?')}** · "
                    f"Mode: **{plan.get('mode','?')}** · "
                    f"Group: **{plan.get('groupby') or '—'}** · "
                    f"Agg: **{plan.get('agg_func') or '—'}**"
                )

    # ══════════════════════════════
    # TAB 3 — HISTORY
    # ══════════════════════════════
    with tab_history:
        history = st.session_state.da_history

        if not history:
            st.info("No analysis history yet. Ask a question in the Ask AI tab.")
        else:
            st.markdown(f"**{len(history)} saved analyses** for `{username}` (newest first)")
            st.markdown("---")
            for item in history:
                with st.expander(
                    f"🕐 {item['created_at']}  ·  {item['question'][:80]}",
                    expanded=False
                ):
                    c1, c2 = st.columns([3, 1])
                    with c1:
                        st.markdown(f"**Question:** {item['question']}")
                        st.write(item["answer"])
                    with c2:
                        st.caption(f"📊 Chart: **{item.get('chart_type') or '—'}**")
                        if item.get("dataset"):
                            st.caption(f"📁 {item['dataset']}")