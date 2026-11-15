"""Corporate announcements from NSE's public JSON endpoint.

NSE returns, per filing: subject (`attchmntText`), raw category (`desc`), PDF (`attchmntFile`),
timestamp (`sort_date`) and — usefully — `voiceSummary`, NSE's own plain-English summary.
We reuse that summary instead of paying an LLM for one.
"""
from __future__ import annotations
import hashlib, logging
from datetime import datetime, timedelta
from ..config import ANNOUNCEMENT_LOOKBACK_DAYS
from ..cache import fetch_with_fallback
from .http import client

log = logging.getLogger("finn.ann")
NSE_URL = "https://www.nseindia.com/api/corporate-announcements"
NSE_HEADERS = {"Referer": "https://www.nseindia.com/companies-listing/corporate-filings-announcements",
               "Accept": "application/json, text/plain, */*"}


def _ann_id(symbol: str, raw: dict) -> str:
    key = raw.get("seq_id") or f"{raw.get('sort_date')}|{raw.get('attchmntFile')}|{raw.get('attchmntText','')[:80]}"
    return hashlib.sha1(f"{symbol}|{key}".encode()).hexdigest()[:16]


def _normalise(symbol: str, raw: dict) -> dict:
    ts = raw.get("sort_date") or ""
    try:
        ts = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S").isoformat()
    except Exception:
        pass
    return {"id": _ann_id(symbol, raw), "symbol": symbol, "ts": ts,
            "subject": (raw.get("attchmntText") or raw.get("desc") or "").strip(),
            "summary": (raw.get("voiceSummary") or "").strip() or None,
            "category_raw": (raw.get("desc") or "").strip(),
            "pdf_url": raw.get("attchmntFile") or None,
            "company_name": raw.get("sm_name"), "industry": raw.get("smIndustry")}


def _live(symbol: str, days: int) -> list[dict]:
    to = datetime.now(); frm = to - timedelta(days=days)
    c = client()
    try:  # cookie handshake helps on some networks; harmless if it 403s
        c.get("https://www.nseindia.com/", headers=NSE_HEADERS, timeout=10)
    except Exception:
        pass
    r = c.get(NSE_URL, params={"index": "equities", "symbol": symbol,
                               "from_date": frm.strftime("%d-%m-%Y"), "to_date": to.strftime("%d-%m-%Y")},
              headers=NSE_HEADERS)
    r.raise_for_status()
    data = r.json()
    if not isinstance(data, list):
        raise RuntimeError(f"unexpected NSE payload for {symbol}")
    return [_normalise(symbol, x) for x in data if (x.get("symbol") or symbol) == symbol]


def load_announcements(symbol: str, days: int = ANNOUNCEMENT_LOOKBACK_DAYS, ttl: int = 1800) -> tuple[list[dict], str]:
    data, src = fetch_with_fallback(f"ann_{symbol}", lambda: _live(symbol, days), ttl=ttl)
    return data or [], src
