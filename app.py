import os
import sys
import glob
import yaml
import streamlit as st
import pandas as pd
import streamlit.components.v1 as components
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
from src.agents.router_agent import (
    classify_query, build_routing_message,
    suggest_upload_agent, AGENT_META,
)
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
user_name    = st.session_state.get("name") or "Guest"

# --------------------------------------------------
# Session State
# --------------------------------------------------
if "show_intro"          not in st.session_state: st.session_state.show_intro          = True
if "show_auth_modal"     not in st.session_state: st.session_state.show_auth_modal     = False
if "show_reset_flow"     not in st.session_state: st.session_state.show_reset_flow     = False
if "reset_token_ss"      not in st.session_state: st.session_state.reset_token_ss      = ""
if "active_agent"        not in st.session_state: st.session_state.active_agent        = "⚛️ ATOM AI OS"
if "auto_mode"           not in st.session_state: st.session_state.auto_mode           = False
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
if "auto_messages"       not in st.session_state: st.session_state.auto_messages       = []
if "auto_pending_query"  not in st.session_state: st.session_state.auto_pending_query  = None
if "auto_pending_route"  not in st.session_state: st.session_state.auto_pending_route  = None
if "auto_awaiting_conf"  not in st.session_state: st.session_state.auto_awaiting_conf  = False
if "auto_pending_upload" not in st.session_state: st.session_state.auto_pending_upload = None

if "finance_messages" not in st.session_state:
    rows = get_finance_history(username) if is_logged_in else []
    st.session_state.finance_messages = [{"role": r["role"], "content": r["content"]} for r in rows]

if "rag_messages" not in st.session_state:
    rows = get_rag_history(username) if is_logged_in else []
    st.session_state.rag_messages = [{"role": r["role"], "content": r["content"]} for r in rows]

if "da_history" not in st.session_state:
    st.session_state.da_history = get_analysis_history(username, limit=50) if is_logged_in else []


# --------------------------------------------------
# Helper: run the correct agent given a key
# --------------------------------------------------
def _run_agent(agent_key: str, query: str) -> str:
    """Run the appropriate agent and return a text response."""
    if agent_key == "ai_os":
        result = run_workspace_agent(query=query, chat_history=st.session_state.auto_messages)
        return result["answer"]

    elif agent_key == "finance":
        try:
            return run_finance_agent(query, chat_history=st.session_state.auto_messages)
        except RuntimeError as e:
            return f"⚠️ {e}"

    elif agent_key == "stock_rag":
        if not st.session_state.rag_ready:
            return "⚠️ Stock Market RAG index isn't built yet. Switch to Stock Market RAG tab first to index documents."
        try:
            result = st.session_state.rag_agent.ask(query, answer_style="Detailed")
            answer = result["answer"]
            if result.get("sources"):
                answer += "\n\n**Sources:** " + " · ".join(
                    f"{s['source']} p.{s['page']}" for s in result["sources"]
                )
            return answer
        except RuntimeError as e:
            return f"⚠️ {e}"

    elif agent_key == "data_analyst":
        if not st.session_state.data_loaded:
            return "⚠️ No dataset loaded. Please upload a CSV or Excel file in the Data Analyst tab first."
        try:
            fig, answer, plan = st.session_state.data_agent.analyze(query)
            st.session_state.da_fig    = fig
            st.session_state.da_plan   = plan
            st.session_state.da_answer = answer
            return answer + "\n\n_📊 Chart generated — switch to Data Analyst tab to view and customise it._"
        except RuntimeError as e:
            return f"⚠️ {e}"

    elif agent_key == "my_documents":
        if not is_logged_in:
            return "⚠️ My Documents requires you to be signed in."
        user_docs = get_user_documents(username)
        if not user_docs:
            return "⚠️ You have no documents uploaded yet. Go to My Documents tab to upload some."
        result = user_rag_ask(username=username, question=query, chat_history=st.session_state.auto_messages)
        answer = result["answer"]
        if result.get("sources"):
            answer += "\n\n**Sources:** " + " · ".join(
                f"{s['filename']} p.{s['page']}" for s in result["sources"]
            )
        return answer

    return "⚠️ Unknown agent."


# --------------------------------------------------
# Sidebar
# --------------------------------------------------
with st.sidebar:
    st.markdown(
        "<div style='font-family:var(--font-display);font-size:26px;font-weight:800;"
        "color:#fff;letter-spacing:-0.5px;padding:4px 0 12px 0;"
        "text-shadow:0 0 22px rgba(99,102,241,0.6);'>ATOM</div>",
        unsafe_allow_html=True,
    )

    # ── Auto / Manual toggle ──────────────────────────────────────────────
    st.markdown(
        "<p style='font-size:11px;color:var(--text-tertiary);letter-spacing:0.5px;"
        "text-transform:uppercase;margin-bottom:4px;font-family:var(--font-body);'>"
        "Mode</p>",
        unsafe_allow_html=True,
    )
    mc1, mc2 = st.columns(2)
    with mc1:
        if st.button(
            "🤖 Auto",
            use_container_width=True,
            type="primary" if st.session_state.auto_mode else "secondary",
        ):
            st.session_state.auto_mode = True
            st.rerun()
    with mc2:
        if st.button(
            "🎛 Manual",
            use_container_width=True,
            type="primary" if not st.session_state.auto_mode else "secondary",
        ):
            st.session_state.auto_mode = False
            st.rerun()

    st.divider()

    # ── User status badge ─────────────────────────────────────────────────
    sidebar_user_badge(is_logged_in, user_name, username)

    if not is_logged_in:
        if st.button("🔑 Sign In / Sign Up", use_container_width=True):
            st.session_state.show_auth_modal = True
            st.rerun()

    st.divider()

    # ── Agent selector (Manual mode only) ────────────────────────────────
    if not st.session_state.auto_mode:
        st.session_state.active_agent = st.radio(
            "Choose Agent",
            ["ATOM AI OS", "Finance Planner", "Stock Market RAG", "Data Analyst", "My Documents"],
        )

        if st.session_state.active_agent == "Stock Market RAG":
         st.markdown(
        "<p style='font-size:12px;color:var(--text-tertiary);letter-spacing:0.5px;"
        "text-transform:uppercase;margin-bottom:4px;font-family:var(--font-body);'>"
        "Answer Style</p>",
        unsafe_allow_html=True,
    )
        st.session_state.answer_style = st.radio("Select Style", ["Detailed", "Concise"])
    else:
        st.markdown(
            "<p style='font-size:12px;color:var(--text-tertiary);font-family:var(--font-body);"
            "padding:4px 0;'>Agent selection is automatic in Auto mode.</p>",
            unsafe_allow_html=True,
        )

    st.divider()

    if st.button("🏠 Go to Home"):
        st.session_state.show_intro = True
        st.rerun()

    # ── Clear buttons (context-sensitive) ────────────────────────────────
    if st.session_state.auto_mode:
        if st.button("🗑 Clear Auto Chat"):
            st.session_state.auto_messages      = []
            st.session_state.auto_pending_query = None
            st.session_state.auto_pending_route = None
            st.session_state.auto_awaiting_conf = False
            st.rerun()
    else:
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
                st.session_state.da_history        = []
                st.session_state.da_fig            = None
                st.session_state.da_answer         = None
                st.session_state.da_plan           = None
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
                st.rerun()

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

    # Typewriter subtitle — uses components.html so script executes
    components.html("""
    <div style='text-align:center;'>
      <span id='tw'
        style='font-size:18px;color:#a5b4fc;font-family:"DM Sans",sans-serif;
               font-weight:400;letter-spacing:0.3px;'></span>
      <span style='color:#6366f1;'>|</span>
    </div>
    <script>
    const phrases = [
      "Your AI OS is live.",
      "Search. Reason. Create.",
      "Intelligence, on demand.",
      "Built for what's next."
    ];
    let pi = 0, ci = 0, deleting = false;
    const el = document.getElementById('tw');
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
    """, height=35)

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


# ══════════════════════════════════════════════════════════
# AUTO MODE
# ══════════════════════════════════════════════════════════
if st.session_state.auto_mode:

    # ── Clean hero when chat is empty ─────────────────────────────────────
    if (
        not st.session_state.auto_messages
        and not st.session_state.auto_awaiting_conf
        and st.session_state.auto_pending_upload is None
    ):
        st.markdown("<br><br>", unsafe_allow_html=True)
        components.html("""
        <div style='text-align:center;'>
          <div style='font-family:"Syne",sans-serif;font-size:52px;font-weight:800;
            background:linear-gradient(90deg,#fff 0%,#a5b4fc 55%,#818cf8 100%);
            background-size:200%;-webkit-background-clip:text;-webkit-text-fill-color:transparent;
            animation:slide 5s linear infinite;margin-bottom:12px;'>ATOM</div>
          <div>
            <span id='atw' style='font-size:20px;color:#a5b4fc;
              font-family:"DM Sans",sans-serif;font-weight:400;letter-spacing:0.2px;'></span>
            <span style='color:#6366f1;font-size:20px;'>|</span>
          </div>
          <p style='font-size:13px;color:rgba(255,255,255,0.3);
            font-family:"DM Sans",sans-serif;margin-top:10px;'>
            Type anything below — ATOM figures out the rest.
          </p>
        </div>
        <style>
          @keyframes slide{0%{background-position:0%}100%{background-position:200%}}
        </style>
        <script>
          const ph = [
            "Route me to the right agent.",
            "I'll figure out what you need.",
            "One box. Every answer.",
            "Just ask. I'll handle it."
          ];
          let pi=0, ci=0, del=false;
          const el = document.getElementById('atw');
          function t() {
            const p = ph[pi];
            if (!del) {
              el.textContent = p.slice(0, ++ci);
              if (ci === p.length) { del=true; setTimeout(t, 1900); return; }
            } else {
              el.textContent = p.slice(0, --ci);
              if (ci === 0) { del=false; pi=(pi+1)%ph.length; }
            }
            setTimeout(t, del ? 40 : 75);
          }
          t();
        </script>
        """, height=200)
        st.markdown("<br>", unsafe_allow_html=True)

    # ── File upload picker ────────────────────────────────────────────────
    if st.session_state.auto_pending_upload is None:
        auto_upload = st.file_uploader(
            "📎 Upload a file — ATOM will ask where to send it",
            type=["csv", "xlsx", "xls", "pdf", "docx", "txt"],
            key="auto_uploader",
        )
        if auto_upload:
            st.session_state.auto_pending_upload = {
                "name":      auto_upload.name,
                "bytes":     auto_upload.read(),
                "suggested": suggest_upload_agent(
                    auto_upload.name,
                    auto_upload.name.rsplit(".", 1)[-1]
                ),
            }
            st.rerun()

    # ── Upload destination picker ─────────────────────────────────────────
    if st.session_state.auto_pending_upload is not None:
        upload_info = st.session_state.auto_pending_upload
        st.markdown(
            f"<div style='background:rgba(99,102,241,0.1);border:1px solid rgba(99,102,241,0.3);"
            f"border-radius:12px;padding:16px 20px;margin-bottom:16px;'>"
            f"<p style='color:var(--accent-text);font-size:14px;font-weight:500;margin:0 0 4px 0;'>"
            f"📄 <strong>{upload_info['name']}</strong> ready to send.</p>"
            f"<p style='color:var(--text-tertiary);font-size:12px;margin:0;'>"
            f"Where should this go?</p></div>",
            unsafe_allow_html=True,
        )
        up1, up2, up3 = st.columns([1, 1, 1])

        with up1:
            if st.button("📊 Data Analyst", use_container_width=True):
                if st.session_state.data_agent is None:
                    st.session_state.data_agent = DataAnalystAgent()
                import io
                file_like      = io.BytesIO(upload_info["bytes"])
                file_like.name = upload_info["name"]
                try:
                    sheets = DataAnalystAgent.read_file(file_like)
                    for sname, raw_df in sheets.items():
                        label = (
                            upload_info["name"] if len(sheets) == 1
                            else f"{upload_info['name']} — {sname}"
                        )
                        st.session_state.data_agent.load_dataframe(raw_df, source_name=label)
                        st.session_state.da_source_names.append(label)
                    st.session_state.data_loaded = True
                    st.session_state.auto_messages.append({
                        "role":    "assistant",
                        "content": (
                            f"✅ **{upload_info['name']}** loaded into Data Analyst. "
                            "Ask me data questions about it here, or switch to the "
                            "Data Analyst tab for full chart controls."
                        ),
                        "agent": "data_analyst",
                    })
                except Exception as e:
                    st.error(f"Could not load file: {e}")
                st.session_state.auto_pending_upload = None
                st.rerun()

        with up2:
            if st.button("📂 My Documents", use_container_width=True):
                if not is_logged_in:
                    st.error("My Documents requires you to be signed in.")
                else:
                    with st.spinner(f"Indexing {upload_info['name']}…"):
                        result = upload_document(username, upload_info["bytes"], upload_info["name"])
                    if result["success"]:
                        st.session_state.auto_messages.append({
                            "role":    "assistant",
                            "content": (
                                f"✅ **{upload_info['name']}** indexed — "
                                f"{result['pages']} pages · {result['chunks']} chunks. "
                                "Ask me anything about it."
                            ),
                            "agent": "my_documents",
                        })
                    else:
                        st.error(f"❌ {result['message']}")
                    st.session_state.auto_pending_upload = None
                    st.rerun()

        with up3:
            if st.button("❌ Cancel", use_container_width=True):
                st.session_state.auto_pending_upload = None
                st.rerun()

        st.stop()

    # ── Render auto chat history ──────────────────────────────────────────
    for msg in st.session_state.auto_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg["role"] == "assistant" and msg.get("agent"):
                meta = AGENT_META.get(msg["agent"], {})
                st.caption(f"{meta.get('icon','🤖')} {meta.get('label','ATOM')}")

    # ── Routing confirmation buttons ──────────────────────────────────────
    if st.session_state.auto_awaiting_conf and st.session_state.auto_pending_route:
        route      = st.session_state.auto_pending_route
        agent      = route["agent"]
        query      = st.session_state.auto_pending_query
        meta       = AGENT_META.get(agent, AGENT_META["ai_os"])
        alternates = route["alternates"]

        cc1, cc2 = st.columns([1, 1])
        with cc1:
            if st.button("✅ Yes, go ahead", use_container_width=True):
                with st.chat_message("assistant"):
                    with st.spinner(f"Running {meta['label']}…"):
                        answer = _run_agent(agent, query)
                    st.markdown(answer)
                    st.caption(f"{meta['icon']} {meta['label']}")
                st.session_state.auto_messages.append({
                    "role": "assistant", "content": answer, "agent": agent,
                })
                st.session_state.auto_awaiting_conf = False
                st.session_state.auto_pending_route = None
                st.session_state.auto_pending_query = None
                st.rerun()

        with cc2:
            if st.button("🔄 Switch agent", use_container_width=True):
                st.session_state.auto_awaiting_conf = False
                st.session_state.auto_pending_route["show_alternates"] = True
                st.rerun()

        # Alternate agent buttons
        if route.get("show_alternates"):
            st.markdown(
                "<p style='color:var(--text-secondary);font-size:13px;margin-top:8px;'>"
                "Choose a different agent:</p>",
                unsafe_allow_html=True,
            )
            alt_cols = st.columns(len(alternates))
            for i, alt_key in enumerate(alternates):
                alt_meta = AGENT_META.get(alt_key, {})
                with alt_cols[i]:
                    if st.button(
                        f"{alt_meta.get('icon','')} {alt_meta.get('label', alt_key)}",
                        key=f"alt_{alt_key}",
                        use_container_width=True,
                    ):
                        with st.chat_message("assistant"):
                            with st.spinner(f"Running {alt_meta['label']}…"):
                                answer = _run_agent(alt_key, query)
                            st.markdown(answer)
                            st.caption(f"{alt_meta.get('icon','🤖')} {alt_meta['label']}")
                        st.session_state.auto_messages.append({
                            "role": "assistant", "content": answer, "agent": alt_key,
                        })
                        st.session_state.auto_pending_route = None
                        st.session_state.auto_pending_query = None
                        st.rerun()

    # ── Chat input ────────────────────────────────────────────────────────
    if not st.session_state.auto_awaiting_conf:
        if query := st.chat_input("Ask anything — ATOM will route it automatically…"):
            st.session_state.auto_messages.append({"role": "user", "content": query})
            with st.chat_message("user"):
                st.markdown(query)

            has_user_docs = bool(is_logged_in and get_user_documents(username))
            route = classify_query(
                query         = query,
                data_loaded   = st.session_state.data_loaded,
                has_user_docs = has_user_docs,
                rag_ready     = st.session_state.rag_ready,
            )

            conf_msg = build_routing_message(route["agent"], route["confidence"], route["reason"])
            st.session_state.auto_messages.append({
                "role": "assistant", "content": conf_msg, "agent": None,
            })
            with st.chat_message("assistant"):
                st.markdown(conf_msg)

            st.session_state.auto_pending_query = query
            st.session_state.auto_pending_route = route
            st.session_state.auto_awaiting_conf = True
            st.rerun()

    st.stop()


# ══════════════════════════════════════════════════════════
# MANUAL MODE — individual agents (your original code, unchanged)
# ══════════════════════════════════════════════════════════

# --------------------------------------------------
# ATOM AI OS — General Intelligence Workspace
# --------------------------------------------------
if st.session_state.active_agent == "ATOM AI OS":

    page_title("ATOM AI OS", "Ask anything · Web search · Code · Writing · Research")
    capability_chips(["🔍 Live Search", "💻 Code Help", "✍️ Writing", "📚 Research", "🧠 Reasoning"])

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
                color_mode = st.radio(
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