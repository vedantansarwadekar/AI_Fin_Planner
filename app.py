import os
import sys
import glob
import yaml
import streamlit as st
import pandas as pd
import streamlit_authenticator as stauth
from yaml.loader import SafeLoader

# --------------------------------------------------
# Fix import path
# --------------------------------------------------
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT_DIR)

from src.theme import apply_theme, page_title, capability_chips, sidebar_user_badge
from src.agents.workspace_agent import run_workspace_agent
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
from src.password_reset import generate_reset_token, validate_reset_token, apply_new_password
from src.config import AUTH_COOKIE_SECRET
from src.user_docs import (
    upload_document,
    get_user_documents,
    delete_document,
    user_rag_ask,
)

# --------------------------------------------------
# Bootstrap DB on every start (creates tables if missing)
# --------------------------------------------------
init_db()

# --------------------------------------------------
# CHECK FOR PASSWORD RESET TOKEN IN URL
# --------------------------------------------------
_url_params      = st.query_params
_reset_token_url = _url_params.get("reset_token", "")

# --------------------------------------------------
# Page Config
# --------------------------------------------------
st.set_page_config(
    page_title="ATOM – Multi-Agent AI Platform",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --------------------------------------------------
# THEME — Dark Glassmorphism
# --------------------------------------------------
apply_theme()

# --------------------------------------------------
# AUTHENTICATION
# --------------------------------------------------
auth_config_path = os.path.join(ROOT_DIR, "auth_config.yaml")


def _load_auth_cfg():
    def deep_convert(obj):
        if hasattr(obj, "to_dict"):
            return deep_convert(obj.to_dict())
        elif hasattr(obj, "_asdict"):
            return deep_convert(obj._asdict())
        elif isinstance(obj, dict):
            return {k: deep_convert(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [deep_convert(i) for i in obj]
        else:
            return str(obj) if not isinstance(obj, (int, float, bool, type(None))) else obj

    if "auth_config" in st.secrets:
        return deep_convert(st.secrets["auth_config"])

    if os.path.exists(auth_config_path):
        with open(auth_config_path, encoding="utf-8") as f:
            return yaml.load(f, Loader=SafeLoader)

    raise ValueError("auth_config not found in secrets or yaml")


auth_cfg = _load_auth_cfg()

authenticator = stauth.Authenticate(
    auth_cfg["credentials"],
    auth_cfg["cookie"]["name"],
    AUTH_COOKIE_SECRET,
    auth_cfg["cookie"]["expiry_days"],
)

is_logged_in = st.session_state.get("authentication_status") is True
username     = st.session_state.get("username", "guest")
user_name    = st.session_state.get("name",     "Guest")

# --------------------------------------------------
# Session State
# --------------------------------------------------
if "show_intro"          not in st.session_state: st.session_state.show_intro          = True
if "show_auth_modal"     not in st.session_state: st.session_state.show_auth_modal     = False
if "show_reset_flow"     not in st.session_state: st.session_state.show_reset_flow     = False
if "reset_token_ss"      not in st.session_state: st.session_state.reset_token_ss      = ""
if "active_agent"        not in st.session_state: st.session_state.active_agent        = "⚛️ ATOM AI OS"
if "answer_style"        not in st.session_state: st.session_state.answer_style        = "Detailed"
if "rag_agent"           not in st.session_state: st.session_state.rag_agent           = None
if "rag_ready"           not in st.session_state: st.session_state.rag_ready           = False
if "data_agent"          not in st.session_state: st.session_state.data_agent          = None
if "data_loaded"         not in st.session_state: st.session_state.data_loaded         = False
if "da_fig"              not in st.session_state: st.session_state.da_fig              = None
if "da_answer"           not in st.session_state: st.session_state.da_answer           = None
if "da_plan"             not in st.session_state: st.session_state.da_plan             = None
if "da_chart_override"   not in st.session_state: st.session_state.da_chart_override   = None
if "da_palette"          not in st.session_state: st.session_state.da_palette          = "Default"
if "da_single_color"     not in st.session_state: st.session_state.da_single_color     = "#4f8ef7"
if "da_use_palette"      not in st.session_state: st.session_state.da_use_palette      = True
if "da_source_names"     not in st.session_state: st.session_state.da_source_names     = []
if "workspace_messages"  not in st.session_state: st.session_state.workspace_messages  = []
if "user_rag_messages"   not in st.session_state: st.session_state.user_rag_messages   = []

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

    # ── User status badge ─────────────────────────────────────────────────
    sidebar_user_badge(is_logged_in, user_name, username)

    if not is_logged_in:
        if st.button("🔑 Sign In / Sign Up", use_container_width=True):
            st.session_state.show_auth_modal = True
            st.rerun()

    st.divider()

    # ── Agent selector ────────────────────────────────────────────────────
    st.session_state.active_agent = st.radio(
        "Choose Agent",
        ["⚛️ ATOM AI OS", "Finance Planner", "Stock Market RAG", "Data Analyst", "My Documents"],
    )

    if st.session_state.active_agent == "Stock Market RAG":
        st.subheader("Answer Style")
        st.session_state.answer_style = st.radio("Select Style", ["Detailed", "Concise"])

    st.divider()

    if st.button("🏠 Go to Home"):
        st.session_state.show_intro = True
        st.rerun()

    if st.session_state.active_agent == "⚛️ ATOM AI OS":
        if st.button("🗑 Clear AI OS Chat"):
            st.session_state.workspace_messages = []
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
            st.session_state.da_history      = []
            st.session_state.da_fig          = None
            st.session_state.da_answer       = None
            st.session_state.da_plan         = None
            st.session_state.da_chart_override = None
            st.rerun()

    st.divider()

    # ── Token usage gauge ─────────────────────────────────────────────────
    usage = get_usage_stats()
    pct   = min(int(usage["tokens_last_minute"] / usage["warn_threshold"] * 100), 100)
    st.caption("🔢 API token usage (last 60s)")
    st.progress(pct)
    st.caption(f"{usage['tokens_last_minute']:,} / {usage['warn_threshold']:,} tokens")

    st.divider()
    if is_logged_in:
        authenticator.logout("🚪 Logout", location="sidebar")

# --------------------------------------------------
# PASSWORD RESET (URL token)
# --------------------------------------------------
if _reset_token_url:
    st.session_state.reset_token_ss  = _reset_token_url
    st.session_state.show_reset_flow = True
    st.query_params.clear()

if st.session_state.get("show_reset_flow") and st.session_state.get("reset_token_ss"):

    token = st.session_state.reset_token_ss
    valid, reset_username, err = validate_reset_token(token)

    st.markdown("---")
    st.markdown("### 🔑 Set New Password")

    if not valid:
        st.error(err)
        if st.button("Back to Sign In"):
            st.session_state.show_reset_flow = False
            st.session_state.reset_token_ss  = ""
            st.session_state.show_auth_modal = True
            st.rerun()
    else:
        st.success(f"Link verified for **{reset_username}**. Choose a new password.")
        np1 = st.text_input("New password",     type="password", key="np1")
        np2 = st.text_input("Confirm password", type="password", key="np2")

        if st.button("Save New Password", use_container_width=True):
            if not np1 or not np2:
                st.error("Please fill in both fields.")
            elif np1 != np2:
                st.error("Passwords do not match.")
            else:
                ok, err2 = apply_new_password(token, np1, auth_cfg, auth_config_path)
                if ok:
                    st.success("✅ Password updated! You can now sign in.")
                    st.session_state.show_reset_flow = False
                    st.session_state.reset_token_ss  = ""
                    st.session_state.show_auth_modal = True
                else:
                    st.error(err2)

    st.markdown("---")
    st.stop()

# --------------------------------------------------
# AUTH MODAL
# --------------------------------------------------
if st.session_state.get("show_auth_modal") and not is_logged_in:

    st.markdown("---")
    st.markdown("### 🔐 Account")

    login_tab, signup_tab, forgot_tab = st.tabs(["Sign In", "Sign Up", "Forgot Password"])

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
        new_username = st.text_input("Choose a username", key="reg_username")
        new_name     = st.text_input("Your display name", key="reg_name")
        new_email    = st.text_input("Email address",     key="reg_email")
        new_password = st.text_input("Choose a password", type="password", key="reg_pass1")
        confirm_pass = st.text_input("Confirm password",  type="password", key="reg_pass2")

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
                with open(auth_config_path, "w", encoding="utf-8") as yf:
                    yaml.dump(auth_cfg, yf, default_flow_style=False, allow_unicode=True)
                st.success(f"Account created! You can now sign in as **{new_username}**.")

    with forgot_tab:
        st.markdown("Enter the email address linked to your account:")
        reset_email = st.text_input("Email address", key="reset_email_input")
        app_url     = st.text_input(
            "App URL (for the reset link)",
            value="http://localhost:8501",
            key="reset_app_url",
            help="Change this to your deployed URL if using Streamlit Cloud",
        )

        if st.button("Send Reset Link", use_container_width=True):
            if not reset_email.strip():
                st.error("Please enter your email address.")
            else:
                with st.spinner("Sending reset email..."):
                    ok, err = generate_reset_token(
                        email        = reset_email.strip(),
                        auth_cfg     = auth_cfg,
                        app_base_url = app_url.strip().rstrip("/"),
                    )
                if ok:
                    st.success(
                        "✅ If that email is registered, a reset link has been sent. "
                        "Check your inbox — the link expires in 15 minutes."
                    )
                else:
                    st.error(f"Could not send email: {err}")

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
        "<h1 style='text-align:center;font-size:72px;font-family:var(--font-display);"
        "background:linear-gradient(90deg,#fff 0%,#a5b4fc 50%,#818cf8 100%);"
        "background-size:200%;-webkit-background-clip:text;-webkit-text-fill-color:transparent;"
        "animation:titleSlide 5s linear infinite;display:inline-block;width:100%;'>"
        "ATOM</h1>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"<p style='text-align:center;font-size:20px;color:var(--text-secondary);"
        f"font-family:var(--font-body);'>"
        f"Welcome back, <strong style='color:var(--accent-text);'>{user_name}</strong></p>",
        unsafe_allow_html=True,
    )
    
    st.markdown("""
<div style='text-align:center;margin-bottom:8px;'>
  <span id='typewriter'
    style='font-size:18px;color:var(--accent-text);font-family:var(--font-body);
           font-weight:400;letter-spacing:0.3px;'></span>
  <span style='color:var(--accent);animation:atomCursor 0.75s step-end infinite;
               font-weight:300;'>|</span>
</div>

<script>
const phrases = [
  "Your AI OS is live.",
  "Search. Reason. Create.",
  "Intelligence, on demand.",
  "Built for what's next."
];
let pi = 0, ci = 0, deleting = false;
const el = document.getElementById('typewriter');

function type() {
  const phrase = phrases[pi];
  if (!deleting) {
    el.textContent = phrase.slice(0, ++ci);
    if (ci === phrase.length) { deleting = true; setTimeout(type, 1800); return; }
  } else {
    el.textContent = phrase.slice(0, --ci);
    if (ci === 0) { deleting = false; pi = (pi + 1) % phrases.length; }
  }
  setTimeout(type, deleting ? 45 : 80);
}
type();
</script>
""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown(
            "<h3 style='color:var(--text-primary);font-family:var(--font-display);'>"
            "Features</h3>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<ul style='color:var(--text-secondary);font-family:var(--font-body);"
            "line-height:2;font-size:15px;'>"
            "<li>⚛️ Universal AI Workspace</li>"
            "<li>🔍 Live Web Search &amp; Accurate Answers</li>"
            "<li>💻 Coding, Writing &amp; Research Help</li>"
            "<li>📊 Autonomous Data Analytics</li>"
            "<li>📂 Private Document Intelligence</li>"
            "<li>🏦 Finance Specialist Tools</li>"
            "</ul>",
            unsafe_allow_html=True,
        )
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Enter Platform", use_container_width=True):
            st.session_state.show_intro = False
            st.rerun()

    st.stop()

# --------------------------------------------------
# ⚛️ ATOM AI OS — General Intelligence Workspace
# --------------------------------------------------
if st.session_state.active_agent == "⚛️ ATOM AI OS":

    page_title("⚛️ ATOM AI OS", "Ask anything · Web search · Code · Writing · Research")
    capability_chips(["🔍 Live Search", "💻 Code Help", "✍️ Writing", "📚 Research", "🧠 Reasoning"])

    # ── Chat history ──────────────────────────────────────────────────────
    for msg in st.session_state.workspace_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

            if msg["role"] == "assistant" and msg.get("sources"):
                with st.expander(f"🔍 {len(msg['sources'])} web source(s) used", expanded=False):
                    for src in msg["sources"]:
                        title = src.get("title", "Source")
                        url   = src.get("url",   "")
                        date  = src.get("published_date", "")
                        if url:
                            st.markdown(f"**[{title}]({url})**" + (f" · {date}" if date else ""))
                        elif title:
                            st.markdown(f"**{title}**" + (f" · {date}" if date else ""))

            if msg["role"] == "assistant" and msg.get("mode"):
                mode_icon  = "🔍" if msg["mode"] == "search" else "🧠"
                mode_label = "Web Search + AI" if msg["mode"] == "search" else "Direct AI Reasoning"
                st.caption(f"{mode_icon} {mode_label}")

    # ── Suggested prompts (empty state) ──────────────────────────────────
    if not st.session_state.workspace_messages:
        st.markdown("---")
        st.markdown(
            "<p style='color:var(--text-tertiary);font-size:13px;"
            "font-family:var(--font-body);'>Try asking:</p>",
            unsafe_allow_html=True,
        )
        suggestion_cols = st.columns(2)
        suggestions = [
            ("🏏", "IPL 2025 points table"),
            ("🤖", "Latest AI tools in 2026"),
            ("💻", "Fix this Python error: list index out of range"),
            ("📝", "Write a LinkedIn post about joining a new job"),
            ("📊", "Best laptops under ₹60,000 in 2026"),
            ("🔬", "Explain how transformers work in simple terms"),
        ]
        for i, (icon, suggestion) in enumerate(suggestions):
            with suggestion_cols[i % 2]:
                if st.button(f"{icon} {suggestion}", key=f"ws_suggestion_{i}", use_container_width=True):
                    st.session_state._workspace_inject = suggestion
                    st.rerun()
        st.markdown("---")

    injected = st.session_state.pop("_workspace_inject", None)
    query    = st.chat_input("Ask anything…") or injected

    if query:
        st.session_state.workspace_messages.append({"role": "user", "content": query})
        with st.chat_message("user"):
            st.markdown(query)

        with st.chat_message("assistant"):
            with st.spinner("Thinking…"):
                result = run_workspace_agent(
                    query        = query,
                    chat_history = st.session_state.workspace_messages,
                )
            answer  = result["answer"]
            mode    = result["mode"]
            sources = result["sources"]

            st.markdown(answer)

            if sources:
                with st.expander(f"🔍 {len(sources)} web source(s) used", expanded=False):
                    for src in sources:
                        title = src.get("title", "Source")
                        url   = src.get("url",   "")
                        date  = src.get("published_date", "")
                        if url:
                            st.markdown(f"**[{title}]({url})**" + (f" · {date}" if date else ""))
                        elif title:
                            st.markdown(f"**{title}**")

            mode_icon  = "🔍" if mode == "search" else "🧠"
            mode_label = "Web Search + AI" if mode == "search" else "Direct AI Reasoning"
            st.caption(f"{mode_icon} {mode_label}")

        st.session_state.workspace_messages.append({
            "role":    "assistant",
            "content": answer,
            "mode":    mode,
            "sources": sources,
        })
        st.rerun()

# --------------------------------------------------
# FINANCE AGENT
# --------------------------------------------------
elif st.session_state.active_agent == "Finance Planner":

    page_title("AI Finance Planner", "Smart money, smarter decisions")

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

    page_title("Stock Market RAG", "RBI & SEBI document intelligence")

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

    page_title("AI Data Analyst", "Upload CSV or Excel · Explore · Ask · Visualize")

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

    tab_summary, tab_analyse, tab_history = st.tabs(
        ["📋 Data Summary", "🤖 Ask AI", "📜 History"]
    )

    # ── TAB 1: SUMMARY ────────────────────────────────────────────────────
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

    # ── TAB 2: ASK AI ─────────────────────────────────────────────────────
    with tab_analyse:
        question = st.text_input(
            "Ask about your dataset",
            placeholder="e.g. show the trend of revenue by month",
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

            active_src = st.session_state.da_source_names[-1] if st.session_state.da_source_names else None
            if is_logged_in:
                save_analysis(username=username, question=question, answer=answer, plan=plan, dataset=active_src)
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
                    help="Switch without re-running AI",
                )
                selected_chart = chart_options[chart_labels.index(selected_label)]

                st.markdown("---")
                st.markdown("**🎨 Colour**")
                color_mode  = st.radio(
                    "mode", ["Palette", "Single colour"],
                    index=0 if st.session_state.da_use_palette else 1,
                    label_visibility="collapsed",
                )
                use_palette = color_mode == "Palette"

                if use_palette:
                    palette = st.selectbox(
                        "Palette",
                        options=list(DataAnalystAgent.COLOR_PALETTES.keys()),
                        index=list(DataAnalystAgent.COLOR_PALETTES.keys()).index(st.session_state.da_palette),
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
                    },
                )
                plan = st.session_state.da_plan
                st.caption(
                    f"🤖 AI: **{plan.get('chart','?')}** · "
                    f"Mode: **{plan.get('mode','?')}** · "
                    f"Group: **{plan.get('groupby') or '—'}** · "
                    f"Agg: **{plan.get('agg_func') or '—'}**"
                )

    # ── TAB 3: HISTORY ────────────────────────────────────────────────────
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
                    expanded=False,
                ):
                    c1, c2 = st.columns([3, 1])
                    with c1:
                        st.markdown(f"**Question:** {item['question']}")
                        st.write(item["answer"])
                    with c2:
                        st.caption(f"📊 Chart: **{item.get('chart_type') or '—'}**")
                        if item.get("dataset"):
                            st.caption(f"📁 {item['dataset']}")

# --------------------------------------------------
# MY DOCUMENTS AGENT
# --------------------------------------------------
elif st.session_state.active_agent == "My Documents":

    page_title("My Documents", "Private document AI · Upload · Ask · Get cited answers")

    if not is_logged_in:
        st.warning(
            "📂 Please sign in to use My Documents. "
            "Your documents are stored privately per account."
        )
        if st.button("🔑 Sign In / Sign Up"):
            st.session_state.show_auth_modal = True
            st.rerun()
        st.stop()

    doc_col, chat_col = st.columns([1, 2])

    # ── LEFT: Document Manager ────────────────────────────────────────────
    with doc_col:
        st.markdown("#### 📁 Your Documents")

        uploaded = st.file_uploader(
            "Upload a file",
            type=["pdf", "docx", "txt", "csv"],
            help="PDF, Word, plain text, or CSV. Stored privately.",
            key="user_rag_uploader",
        )

        if uploaded:
            file_bytes = uploaded.read()
            with st.spinner(f"Indexing {uploaded.name}…"):
                result = upload_document(username, file_bytes, uploaded.name)

            if result["success"]:
                st.success(
                    "✅ **" + result["filename"] + "** indexed — "
                    + str(result["pages"]) + " pages · "
                    + str(result["chunks"]) + " chunks"
                )
            else:
                st.error(f"❌ {result['message']}")

        st.markdown("---")

        user_docs = get_user_documents(username)

        if not user_docs:
            st.info("No documents yet. Upload a file above.")
        else:
            st.markdown(f"**{len(user_docs)} document(s)**")
            for fname, fmeta in user_docs.items():
                with st.expander(f"📄 {fname}", expanded=False):
                    st.caption(
                        f"Type: {fmeta.get('file_type','?').upper()}  ·  "
                        f"{fmeta.get('pages','?')} pages  ·  "
                        f"{fmeta.get('size_kb','?')} KB"
                    )
                    st.caption(f"Uploaded: {fmeta.get('uploaded_at','?')[:10]}")

                    if st.button("🗑 Delete", key=f"del_{fname}"):
                        result = delete_document(username, fname)
                        if result["success"]:
                            st.success(result["message"])
                            st.rerun()
                        else:
                            st.error(result["message"])

    # ── RIGHT: Chat ───────────────────────────────────────────────────────
    with chat_col:
        st.markdown("#### 💬 Ask About Your Documents")

        for msg in st.session_state.user_rag_messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

                if msg.get("sources"):
                    with st.expander("📎 Sources", expanded=False):
                        for src in msg["sources"]:
                            st.caption(f"**{src['filename']}** · Page {src['page']}")
                            if src.get("excerpt"):
                                st.caption(f"*…{src['excerpt']}…*")

        if query := st.chat_input("Ask about your uploaded documents…"):
            st.session_state.user_rag_messages.append({"role": "user", "content": query})
            with st.chat_message("user"):
                st.markdown(query)

            with st.chat_message("assistant"):
                with st.spinner("Searching your documents…"):
                    result = user_rag_ask(
                        username     = username,
                        question     = query,
                        chat_history = st.session_state.user_rag_messages,
                    )

                answer  = result["answer"]
                sources = result["sources"]

                st.markdown(answer)

                if sources:
                    with st.expander(f"📎 {len(sources)} source(s) used", expanded=True):
                        for src in sources:
                            st.markdown(f"**{src['filename']}** · Page {src['page']}")
                            if src.get("excerpt"):
                                st.caption(f"*{src['excerpt']}*")
                            st.markdown("---")

            st.session_state.user_rag_messages.append({
                "role":    "assistant",
                "content": answer,
                "sources": sources,
            })
            st.rerun()

        if st.session_state.user_rag_messages:
            if st.button("🗑 Clear Chat", key="clear_user_rag_chat"):
                st.session_state.user_rag_messages = []
                st.rerun()
               