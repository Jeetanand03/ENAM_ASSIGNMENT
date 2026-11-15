"""Triggered alerts, evaluated against the user's thresholds and an optional simulated clock (`as_of`).

Two kinds:
  * market  — |1-day move| > X%  or  volume > N x 20-day average (from EOD data)
  * filing  — an announcement in one of the user's starred (material) categories
Alerts are computed, not stored, so changing a slider re-evaluates history instantly.
"""
from __future__ import annotations
from datetime import datetime, timedelta
from ..config import PORTFOLIO, COMPANY_BY_SYMBOL
from ..sources import prices
from .. import db


def market_alerts(settings: dict, as_of: str, days: int = 10) -> list[dict]:
    thr_p = float(settings.get("price_move_pct", 4)); thr_v = float(settings.get("volume_multiple", 2))
    start = (datetime.fromisoformat(as_of[:10]) - timedelta(days=days)).strftime("%Y-%m-%d")
    out = []
    for c in PORTFOLIO:
        for r in prices.enrich_moves(prices.series(c["symbol"])):
            if r["date"] < start or r["date"] > as_of[:10]:
                continue
            hits = []
            if r["pct_move"] is not None and abs(r["pct_move"]) >= thr_p:
                hits.append({"kind": "price", "value": r["pct_move"], "threshold": thr_p,
                             "text": f"{r['pct_move']:+.1f}% in a day (threshold ±{thr_p:g}%)"})
            if r["vol_ratio"] is not None and r["vol_ratio"] >= thr_v:
                hits.append({"kind": "volume", "value": r["vol_ratio"], "threshold": thr_v,
                             "text": f"volume {r['vol_ratio']:.1f}× its 20-day average (threshold {thr_v:g}×)"})
            if hits:
                out.append({"id": f"mkt:{c['symbol']}:{r['date']}", "type": "market", "symbol": c["symbol"],
                            "name": c["name"], "ts": f"{r['date']}T15:30:00", "close": r["close"],
                            "pct_move": r["pct_move"], "vol_ratio": r["vol_ratio"], "hits": hits,
                            "headline": " · ".join(h["text"] for h in hits)})
    return out


def filing_alerts(settings: dict, as_of: str, days: int = 10) -> list[dict]:
    starred = settings.get("starred_categories") or []
    if not starred:
        return []
    start = (datetime.fromisoformat(as_of[:10]) - timedelta(days=days)).isoformat()
    q = ",".join("?" * len(starred))
    rows = db.rows(f"SELECT id,symbol,ts,subject,headline,category,score,tier,pdf_url FROM announcements "
                   f"WHERE category IN ({q}) AND ts>=? AND ts<=? ORDER BY ts DESC", (*starred, start, as_of))
    return [{"id": f"ann:{r['id']}", "type": "filing", "ann_id": r["id"], "symbol": r["symbol"],
             "name": COMPANY_BY_SYMBOL.get(r["symbol"], {}).get("name", r["symbol"]), "ts": r["ts"],
             "category": r["category"], "score": r["score"], "tier": r["tier"], "pdf_url": r["pdf_url"],
             "headline": r["headline"] or r["subject"][:140]} for r in rows]


def evaluate(settings: dict, as_of: str, days: int = 10) -> list[dict]:
    items = market_alerts(settings, as_of, days) + filing_alerts(settings, as_of, days)
    # Join: a filing alert that coincides with a market move is the most interesting kind — mark it.
    moves = {(a["symbol"], a["ts"][:10]) for a in items if a["type"] == "market"}
    for a in items:
        if a["type"] == "filing":
            d = a["ts"][:10]
            nxt = (datetime.fromisoformat(d) + timedelta(days=1)).strftime("%Y-%m-%d")
            a["with_market_move"] = (a["symbol"], d) in moves or (a["symbol"], nxt) in moves
    items.sort(key=lambda a: a["ts"], reverse=True)
    return items
