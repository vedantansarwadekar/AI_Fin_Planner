"""
Configuration file for all agents
Loads API keys from .env file
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Find .env file (works from any location)
ROOT_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT_DIR / ".env"

load_dotenv(dotenv_path=ENV_PATH, override=True)

# API Keys
GROQ_API_KEY    = os.getenv("GROQ_API_KEY")
TAVILY_API_KEY  = os.getenv("TAVILY_API_KEY")      # Finance Agent only
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")     # Finance Agent only

# Auth cookie secret — set this in your .env as:
#   AUTH_COOKIE_SECRET=some_long_random_string
# If not set, falls back to a default (CHANGE IN PRODUCTION)
AUTH_COOKIE_SECRET = os.getenv("AUTH_COOKIE_SECRET", "atom_default_secret_change_me")

# Validate REQUIRED key (all agents need this)
if not GROQ_API_KEY:
    raise ValueError(f"❌ GROQ_API_KEY missing. Check {ENV_PATH}")

# Validate OPTIONAL keys (only Finance Agent needs these)
if not TAVILY_API_KEY:
    print(f"⚠️  TAVILY_API_KEY missing - Web search disabled")
if not FINNHUB_API_KEY:
    print(f"⚠️  FINNHUB_API_KEY missing - Stock data disabled")