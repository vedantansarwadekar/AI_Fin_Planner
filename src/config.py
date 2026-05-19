"""
Configuration file for all agents
Loads API keys from Streamlit secrets (cloud) or .env file (local)
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Find .env file (works from any location)
ROOT_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT_DIR / ".env"

load_dotenv(dotenv_path=ENV_PATH, override=True)

# Try to import streamlit, but don't fail if not available yet
try:
    import streamlit as st
    HAS_STREAMLIT = True
except (ImportError, RuntimeError):
    HAS_STREAMLIT = False

# API Keys - Try Streamlit secrets first, then .env
def get_secret(key, default=None):
    """Get secret from Streamlit secrets (cloud) or environment (local)"""
    # Try environment variable first (works everywhere)
    env_val = os.getenv(key)
    if env_val:
        return env_val
    
    # Try Streamlit secrets (cloud deployment)
    if HAS_STREAMLIT:
        try:
            return st.secrets.get(key)
        except Exception:
            pass
    
    return default

GROQ_API_KEY    = get_secret("GROQ_API_KEY")
TAVILY_API_KEY  = get_secret("TAVILY_API_KEY")
FINNHUB_API_KEY = get_secret("FINNHUB_API_KEY")
AUTH_COOKIE_SECRET = get_secret("AUTH_COOKIE_SECRET", "atom_default_secret_change_me")

# Validate REQUIRED key (all agents need this)
if not GROQ_API_KEY:
    raise ValueError(f"❌ GROQ_API_KEY missing. Check Streamlit Secrets or {ENV_PATH}")

# Validate OPTIONAL keys (only Finance Agent needs these)
if not TAVILY_API_KEY:
    print(f"⚠️  TAVILY_API_KEY missing - Web search disabled")
if not FINNHUB_API_KEY:
    print(f"⚠️  FINNHUB_API_KEY missing - Stock data disabled")