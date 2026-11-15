"""Vercel serverless entry point for the FINN FastAPI backend.

Serverless instances are short-lived and have a read-only filesystem except /tmp, so:
  * sqlite + downloaded PDFs live in /tmp
  * FINN_SNAPSHOT_FIRST=1: a cold instance seeds itself from the committed snapshots in data/snapshots/
    (no network on the hot path); unseen tickers still go live to screener/BSE.
"""
import os, sys
from pathlib import Path

os.environ.setdefault("FINN_DATA_DIR", "/tmp/finn")
os.environ.setdefault("FINN_DOCS_DIR", "/tmp/finn/docs")
os.environ.setdefault("FINN_SNAPSHOT_FIRST", "1")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.main import app  # noqa: E402,F401
