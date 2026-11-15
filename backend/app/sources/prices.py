"""End-of-day prices via yfinance (SYMBOL.NS). Stored in sqlite; snapshot per symbol."""
from __future__ import annotations
import logging, math
from datetime import datetime, timedelta, timezone
from ..config import PRICE_HISTORY_DAYS, AVG_VOLUME_WINDOW
from ..cache import fetch_with_fallback
from .. import db

log = logging.getLogger("finn.prices")


def _live(symbol: str) -> list[dict]:
    import yfinance as yf
    t = yf.Ticker(f"{symbol}.NS")
    hist = t.history(period=f"{PRICE_HISTORY_DAYS + 40}d", interval="1d", auto_adjust=False)
    if hist is None or hist.empty:
        raise RuntimeError(f"no price data for {symbol}")
    out = []
    for idx, r in hist.iterrows():
        if any(math.isnan(float(r[k])) for k in ("Open", "High", "Low", "Close")):
            continue
        out.append({"date": idx.strftime("%Y-%m-%d"), "open": round(float(r["Open"]), 2),
                    "high": round(float(r["High"]), 2), "low": round(float(r["Low"]), 2),
                    "close": round(float(r["Close"]), 2), "volume": int(r["Volume"] or 0)})
    return out[-PRICE_HISTORY_DAYS:]


def load_prices(symbol: str, ttl: int = 6 * 3600) -> tuple[list[dict], str]:
    data, src = fetch_with_fallback(f"prices_{symbol}", lambda: _live(symbol), ttl=ttl)
    if data:
        with db.tx() as c:
            c.executemany("INSERT OR REPLACE INTO prices VALUES (?,?,?,?,?,?,?)",
                          [(symbol, d["date"], d["open"], d["high"], d["low"], d["close"], d["volume"]) for d in data])
    return data or [], src


def series(symbol: str) -> list[dict]:
    return db.rows("SELECT date,open,high,low,close,volume FROM prices WHERE symbol=? ORDER BY date", (symbol,))


def enrich_moves(rows: list[dict]) -> list[dict]:
    """Adds pct_move (vs previous close) and vol_ratio (vs trailing 20d avg, excluding the day itself)."""
    out = []
    for i, r in enumerate(rows):
        prev = rows[i - 1]["close"] if i > 0 else None
        win = [x["volume"] for x in rows[max(0, i - AVG_VOLUME_WINDOW):i] if x["volume"]]
        avg = sum(win) / len(win) if win else None
        out.append({**r,
                    "pct_move": round((r["close"] / prev - 1) * 100, 2) if prev else None,
                    "vol_ratio": round(r["volume"] / avg, 2) if avg else None,
                    "avg_volume": int(avg) if avg else None})
    return out


def snapshot(symbol: str, as_of: str | None = None) -> dict | None:
    """Latest bar at/before as_of (YYYY-MM-DD) with move + volume ratio + 30d sparkline."""
    rows = enrich_moves(series(symbol))
    if as_of:
        rows = [r for r in rows if r["date"] <= as_of[:10]]
    if not rows:
        return None
    last = rows[-1]
    spark = [r["close"] for r in rows[-30:]]
    return {"symbol": symbol, "date": last["date"], "close": last["close"], "pct_move": last["pct_move"],
            "volume": last["volume"], "vol_ratio": last["vol_ratio"], "avg_volume": last["avg_volume"],
            "spark": spark}


def move_on(symbol: str, ts: str) -> dict | None:
    """The first trading bar that could react to a filing at `ts` (ISO datetime).
    Filings after the 15:30 close react the next session."""
    try:
        t = datetime.fromisoformat(ts)
    except ValueError:
        return None
    day = t.date()
    if len(ts) > 10 and (t.hour, t.minute) >= (15, 30):
        day = day + timedelta(days=1)
    d = day.isoformat()
    for r in enrich_moves(series(symbol)):
        if r["date"] >= d:
            return r if (datetime.fromisoformat(r["date"]).date() - day).days <= 3 else None
    return None
