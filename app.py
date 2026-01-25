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

query = st.text_input("Ask something:", placeholder="e.g. Make a budget for salary 50k")

if st.button("Run"):
    if not query.strip():
        st.warning("Enter a query first.")
    else:
        with st.spinner("Thinking..."):
            output = run_finance_agent(query)
        st.write(output)
