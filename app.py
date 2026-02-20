import os
import sys
import glob
import streamlit as st

# --------------------------------------------------
# Fix import path
# --------------------------------------------------
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT_DIR)

from src.agents.finance_agent import run_finance_agent
from src.agents.rag_agent import StockMarketRAGAgent

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
# CLEAN LIGHT THEME (DO NOT HIDE HEADER)
# --------------------------------------------------
st.markdown("""
<style>

/* App background */
.stApp {
    background-color: #f5f5f7 !important;
}

/* Main container */
.block-container {
    padding-top: 2rem !important;
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background-color: #ffffff !important;
    border-right: 1px solid #e5e5e7 !important;
}

/* Sidebar text */
section[data-testid="stSidebar"] * {
    color: #1d1d1f !important;
}

/* Sidebar buttons */
section[data-testid="stSidebar"] .stButton>button {
    background-color: #ffffff !important;
    color: #1d1d1f !important;
    border: 1px solid #d1d1d6 !important;
    border-radius: 25px !important;
}

/* Sidebar button hover */
section[data-testid="stSidebar"] .stButton>button:hover {
    background-color: #f2f2f2 !important;
}

/* Chat input */
div[data-testid="stChatInput"] textarea {
    background-color: #ffffff !important;
    color: #1d1d1f !important;
    border: 1px solid #d1d1d6 !important;
}

/* Send button */
div[data-testid="stChatInput"] button {
    background-color: #1d1d1f !important;
    color: white !important;
    border-radius: 50% !important;
}

/* Fix normal buttons (like Enter Platform) */
.stButton>button {
    background-color: #111827 !important;
    color: white !important;
    border-radius: 8px !important;
}

.stButton>button:hover {
    background-color: #000000 !important;
    color: white !important;
}

            
/* Fix chat message text color */
div[data-testid="stChatMessage"] p,
div[data-testid="stChatMessage"] span,
div[data-testid="stChatMessage"] div,
div[data-testid="stChatMessage"] li,
div[data-testid="stChatMessage"] ol,
div[data-testid="stChatMessage"] ul,
div[data-testid="stChatMessage"] strong,
div[data-testid="stChatMessage"] em {
    color: #1d1d1f !important;
}

/* Fix user message bubble */
div[data-testid="stChatMessage"][data-message-author-role="user"] {
    background-color: #e8e8ed !important;
}

/* Fix assistant message bubble */
div[data-testid="stChatMessage"][data-message-author-role="assistant"] {
    background-color: #ffffff !important;
}
                        
</style>
""", unsafe_allow_html=True)

# --------------------------------------------------
# Session State
# --------------------------------------------------
if "show_intro" not in st.session_state:
    st.session_state.show_intro = True

if "active_agent" not in st.session_state:
    st.session_state.active_agent = "Finance Planner"

if "finance_messages" not in st.session_state:
    st.session_state.finance_messages = []

if "rag_messages" not in st.session_state:
    st.session_state.rag_messages = []

if "rag_agent" not in st.session_state:
    st.session_state.rag_agent = None

if "rag_ready" not in st.session_state:
    st.session_state.rag_ready = False

if "answer_style" not in st.session_state:
    st.session_state.answer_style = "Detailed"

# --------------------------------------------------
# Sidebar
# --------------------------------------------------
with st.sidebar:
    st.title("ATOM")

    st.session_state.active_agent = st.radio(
        "Choose Agent",
        ["Finance Planner", "Stock Market RAG"]
    )

    if st.session_state.active_agent == "Stock Market RAG":
        st.subheader("Answer Style")
        st.session_state.answer_style = st.radio(
            "Select Style",
            ["Detailed", "Concise"]
        )

    st.divider()

    if st.button("🏠 Go to Home"):
        st.session_state.show_intro = True
        st.rerun()

    if st.session_state.active_agent == "Finance Planner":
        if st.button("🗑 Clear Finance Chat"):
            st.session_state.finance_messages = []
            st.rerun()

    if st.session_state.active_agent == "Stock Market RAG":
        if st.button("🗑 Clear RAG Chat"):
            st.session_state.rag_messages = []
            st.rerun()

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
        "<p style='text-align:center; font-size:22px; color:#555;'>"
        "A Multi-Agent AI Platform for Finance & Intelligence"
        "</p>",
        unsafe_allow_html=True
    )

    st.markdown("<br>", unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1,2,1])

    with col2:
        st.markdown("<h3 style='color:#111;'>Features</h3>", unsafe_allow_html=True)
        st.markdown("""
<div style='color:#1d1d1f;'>

- 💸 Smart Finance Planning  
- 📈 Market & Stock Intelligence  
- 📚 RBI & SEBI Document AI Search  
- 🧠 Modular Multi-Agent Architecture  

</div>
        """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        st.markdown(
            "<p style='text-align:center; color:#777;'>"
            "Created by Vedant • Maitreyee • Utkarsha"
            "</p>",
            unsafe_allow_html=True
        )

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
    st.markdown("<p style='color:#666; font-size:14px;'>Budget • Savings • Stocks • News • Web Search</p>", unsafe_allow_html=True)

    for idx, msg in enumerate(st.session_state.finance_messages):
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
            

    if query := st.chat_input("Ask a finance question…"):

        st.session_state.finance_messages.append(
            {"role": "user", "content": query}
        )

        with st.chat_message("user"):
            st.write(query)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                response = run_finance_agent(
                    query,
                    chat_history=st.session_state.finance_messages
                )
            st.write(response)

        st.session_state.finance_messages.append(
            {"role": "assistant", "content": response})
        
        st.rerun()

# --------------------------------------------------
# RAG AGENT
# --------------------------------------------------
if st.session_state.active_agent == "Stock Market RAG":

    st.markdown("<h2 style='color:#111;'>Stock Market RAG Agent</h2>", unsafe_allow_html=True)
    st.markdown("<p style='color:#666; font-size:14px;'>Ask questions from official RBI & SEBI documents</p>", unsafe_allow_html=True)

    if not st.session_state.rag_ready:
        with st.spinner("Indexing documents..."):
            agent = StockMarketRAGAgent()
            pdfs = glob.glob("data/pdfs/*.pdf")
            agent.ingest_pdfs(pdfs)
            st.session_state.rag_agent = agent
            st.session_state.rag_ready = True
        st.success("Documents indexed successfully!")
        st.rerun()

    for idx, msg in enumerate(st.session_state.rag_messages):
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
            

    if query := st.chat_input("Ask from RBI / SEBI PDFs…"):

        st.session_state.rag_messages.append(
            {"role": "user", "content": query}
        )

        with st.chat_message("user"):
            st.write(query)

        with st.chat_message("assistant"):
            with st.spinner("Searching documents..."):
                result = st.session_state.rag_agent.ask(
                    query,
                    answer_style=st.session_state.answer_style
                )

            st.markdown(result["answer"])

            st.markdown("**Sources:**")
            for src in result["sources"]:
                st.write(f"{src['source']} | Page {src['page']}")

        st.session_state.rag_messages.append(
            {"role": "assistant", "content": result["answer"]}
        )
        
        st.rerun()