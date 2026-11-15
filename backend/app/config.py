"""Central config. Demo sets live here ONLY — the engine itself is ticker-agnostic."""
from __future__ import annotations
import os
from pathlib import Path
from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = BACKEND_DIR.parent
load_dotenv(BACKEND_DIR / ".env")

DATA_DIR = Path(os.getenv("FINN_DATA_DIR", BACKEND_DIR / "data"))
SNAPSHOT_DIR = Path(os.getenv("FINN_SNAPSHOT_DIR", REPO_DIR / "data" / "snapshots"))
DOCS_DIR = Path(os.getenv("FINN_DOCS_DIR", REPO_DIR / "data" / "docs"))
SEED_DOCS_DIR = REPO_DIR / "data" / "docs_seed"   # committed, read-only: extracted pages for the demo set
DB_PATH = DATA_DIR / "finn.db"
for p in (DATA_DIR, DOCS_DIR):
    p.mkdir(parents=True, exist_ok=True)

OFFLINE = os.getenv("FINN_OFFLINE", "0") == "1"            # never touch the network
SNAPSHOT_FIRST = os.getenv("FINN_SNAPSHOT_FIRST", "0") == "1"  # serverless: serve committed snapshots, go live only on a miss

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")

# Mock portfolio: 20 NSE names across sectors and sizes.
PORTFOLIO: list[dict] = [
    {"symbol": "RELIANCE",   "name": "Reliance Industries",       "sector": "Conglomerate / Energy", "size": "Mega"},
    {"symbol": "HDFCBANK",   "name": "HDFC Bank",                 "sector": "Banking",               "size": "Mega"},
    {"symbol": "TCS",        "name": "Tata Consultancy Services", "sector": "IT Services",           "size": "Mega"},
    {"symbol": "INFY",       "name": "Infosys",                   "sector": "IT Services",           "size": "Large"},
    {"symbol": "ITC",        "name": "ITC",                       "sector": "FMCG",                  "size": "Large"},
    {"symbol": "BAJFINANCE", "name": "Bajaj Finance",             "sector": "NBFC",                  "size": "Large"},
    {"symbol": "SUNPHARMA",  "name": "Sun Pharmaceutical",        "sector": "Pharma",                "size": "Large"},
    {"symbol": "MARUTI",     "name": "Maruti Suzuki",             "sector": "Auto",                  "size": "Large"},
    {"symbol": "HAL",        "name": "Hindustan Aeronautics",     "sector": "Defence",               "size": "Large"},
    {"symbol": "TRENT",      "name": "Trent",                     "sector": "Retail",                "size": "Large"},
    {"symbol": "ETERNAL",    "name": "Eternal (Zomato)",          "sector": "Internet",              "size": "Large"},
    {"symbol": "APOLLOHOSP", "name": "Apollo Hospitals",          "sector": "Healthcare",            "size": "Large"},
    {"symbol": "DIXON",      "name": "Dixon Technologies",        "sector": "Electronics Mfg",       "size": "Mid"},
    {"symbol": "PERSISTENT", "name": "Persistent Systems",        "sector": "IT Services",           "size": "Mid"},
    {"symbol": "POLYCAB",    "name": "Polycab India",             "sector": "Cables / Electricals",  "size": "Mid"},
    {"symbol": "VBL",        "name": "Varun Beverages",           "sector": "Beverages",             "size": "Large"},
    {"symbol": "IRCTC",      "name": "IRCTC",                     "sector": "Travel / PSU",          "size": "Mid"},
    {"symbol": "KAYNES",     "name": "Kaynes Technology",         "sector": "Electronics Mfg",       "size": "Small"},
    {"symbol": "TANLA",      "name": "Tanla Platforms",           "sector": "CPaaS / Software",      "size": "Small"},
    {"symbol": "RATEGAIN",   "name": "RateGain Travel Tech",      "sector": "SaaS",                  "size": "Small"},
]
PORTFOLIO_SYMBOLS = [c["symbol"] for c in PORTFOLIO]
COMPANY_BY_SYMBOL = {c["symbol"]: c for c in PORTFOLIO}

# Ad-hoc research demo set (pre-cached so the pull side is instant on a phone).
RESEARCH_DEMO: list[str] = ["DIXON", "PERSISTENT", "VBL", "KAYNES"]

DEFAULT_SETTINGS = {
    "volume_multiple": 2.0,        # alert if volume > N x 20d avg
    "price_move_pct": 4.0,         # alert if |1d move| > X %
    "starred_categories": ["results", "M&A", "management_change"],
    "digest_window": "24h",
}

PRICE_HISTORY_DAYS = 120
AVG_VOLUME_WINDOW = 20
ANNOUNCEMENT_LOOKBACK_DAYS = 45
