import os
from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT_DIR / ".env"

load_dotenv(dotenv_path=ENV_PATH, override=True)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")

if not GROQ_API_KEY:
    raise ValueError(f"❌ GROQ_API_KEY missing. Check {ENV_PATH}")
if not TAVILY_API_KEY:
    raise ValueError(f"❌ TAVILY_API_KEY missing. Check {ENV_PATH}")
if not FINNHUB_API_KEY:
    raise ValueError(f"❌ FINNHUB_API_KEY missing. Check {ENV_PATH}")
