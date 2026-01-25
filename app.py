import os
import sys

# ✅ Make sure project root is in import path (Streamlit-safe)
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT_DIR)

import streamlit as st
from src.agents.finance_agent import run_finance_agent

st.set_page_config(page_title="AI Finance Planner", page_icon="💸")

st.title("💸 AI Finance Planner Agent")
st.write("Budget • Savings • Live Stock Price • News • Web Search")

# ✅ Initialize conversation history in session state
if "messages" not in st.session_state:
    st.session_state.messages = []

# ✅ Display all previous messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])

# ✅ Chat input
if query := st.chat_input("Ask something (e.g., Make a budget for salary 50k)"):
    # Add user message to history and display it
    st.session_state.messages.append({"role": "user", "content": query})
    with st.chat_message("user"):
        st.write(query)
    
    # Get agent response WITH conversation history
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            # ✅ Pass the full chat history to the agent
            output = run_finance_agent(query, chat_history=st.session_state.messages)
        st.write(output)
    
    # Add assistant response to history
    st.session_state.messages.append({"role": "assistant", "content": output})

# ✅ Optional: Add a "Clear Chat" button in the sidebar
with st.sidebar:
    if st.button("🗑️ Clear Chat History"):
        st.session_state.messages = []
        st.rerun()
