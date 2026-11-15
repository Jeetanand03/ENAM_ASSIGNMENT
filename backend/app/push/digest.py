"""Ingest -> classify -> score -> store, and the windowed digest query."""
from __future__ import annotations
import json, logging, re
from datetime import datetime, timedelta
from ..config import PORTFOLIO, COMPANY_BY_SYMBOL
from ..sources import announcements, prices
from .. import db, llm
from .classify import classify, needs_llm, CATEGORIES
from .score import score as score_fn

log = logging.getLogger("finn.digest")

CLASSIFY_SYSTEM = ("You classify Indian stock-exchange filings. Categories: " + ", ".join(CATEGORIES) +
                   ". Pick exactly one. Return JSON {\"category\": ..., \"headline\": <=14 words}.")


def headline_for(a: dict, category: str) -> str:
    """Short, human headline. Free: derived from NSE's summary or the subject, no model call."""
    s = (a.get("summary") or a.get("subject") or "").strip()
    s = re.sub(r"^(please (note|find|be informed) that\s*|this is to inform (you )?that\s*|pursuant to .*?,\s*)", "", s, flags=re.I)
    s = re.sub(rf"^{re.escape(a.get('company_name') or '')}\s*(\(.*?\))?\s*(has|have)?\s*", "", s, flags=re.I) if a.get("company_name") else s
    s = re.sub(r"\s+", " ", s)
    # sentence split that ignores common abbreviations (Mr. Ms. Dr. Ltd. Rs. No. Inc. Pvt.)
    protected = re.sub(r"\b(Mr|Mrs|Ms|Dr|Ltd|Rs|No|Inc|Pvt|Co|Sr|Jr|vs|approx|w\.e\.f|Shri|Smt)\.", lambda m: m.group(0).replace(".", "․"), s)
    protected = re.sub(r"\b([A-Z])\.(?=\s?[A-Z])", lambda m: m.group(1) + "․", protected)  # initials: "Mr. V. Srinivasa"
    first = re.split(r"(?<=[.;])\s(?=[A-Z(])", protected)[0].replace("․", ".")
    first = first[0].upper() + first[1:] if first else category
    return (first[:150] + "…") if len(first) > 150 else first


def ingest(symbols: list[str] | None = None, settings: dict | None = None, use_llm: bool = True) -> dict:
    from .. import settings as settings_mod
    settings = settings or settings_mod.get()
    symbols = symbols or [c["symbol"] for c in PORTFOLIO]
    stats = {"fetched": 0, "llm_classified": 0, "sources": {}}
    for sym in symbols:
        anns, src = announcements.load_announcements(sym)
        stats["sources"][sym] = src
        for a in anns:
            cat, csrc = classify(a["subject"], a["category_raw"], a.get("summary"))
            if use_llm and needs_llm(cat, csrc, a["subject"]):
                j = llm.complete_json("classify", CLASSIFY_SYSTEM, a["subject"][:600], tier="cheap", symbol=sym, max_tokens=80)
                if j and j.get("category") in CATEGORIES:
                    cat, csrc = j["category"], "llm"; stats["llm_classified"] += 1
            move = prices.move_on(sym, a["ts"]) if a["ts"] else None
            sc = score_fn(cat, a["subject"] + " " + (a.get("summary") or ""), move, settings)
            with db.tx() as c:
                c.execute("""INSERT INTO announcements(id,symbol,ts,subject,summary,category_raw,pdf_url,category,category_source,score,score_parts,tier,headline)
                             VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
                             ON CONFLICT(id) DO UPDATE SET category=excluded.category, category_source=excluded.category_source,
                             score=excluded.score, score_parts=excluded.score_parts, tier=excluded.tier, headline=excluded.headline, summary=excluded.summary""",
                          (a["id"], sym, a["ts"], a["subject"], a.get("summary"), a["category_raw"], a.get("pdf_url"),
                           cat, csrc, sc["score"], json.dumps(sc["parts"]), sc["tier"], headline_for(a, cat)))
            stats["fetched"] += 1
    db.kv_set("last_ingest", datetime.now().isoformat())
    from .enrich import enrich_top
    stats["enriched"] = enrich_top()
    return stats


def rescore(settings: dict) -> None:
    """Cheap re-score of everything when thresholds/starred categories change (no refetch)."""
    for r in db.rows("SELECT id,symbol,ts,subject,summary,category FROM announcements"):
        move = prices.move_on(r["symbol"], r["ts"]) if r["ts"] else None
        sc = score_fn(r["category"], r["subject"] + " " + (r["summary"] or ""), move, settings)
        with db.tx() as c:
            c.execute("UPDATE announcements SET score=?,score_parts=?,tier=? WHERE id=?",
                      (sc["score"], json.dumps(sc["parts"]), sc["tier"], r["id"]))


def _row_to_card(r: dict) -> dict:
    parts = json.loads(r["score_parts"]) if r.get("score_parts") else {}
    enrich = json.loads(r["enrich"]) if r.get("enrich") else None
    co = COMPANY_BY_SYMBOL.get(r["symbol"], {})
    return {"id": r["id"], "symbol": r["symbol"], "name": co.get("name", r["symbol"]), "sector": co.get("sector"),
            "ts": r["ts"], "category": r["category"], "category_source": r["category_source"],
            "headline": r["headline"], "subject": r["subject"], "summary": r["summary"], "pdf_url": r["pdf_url"],
            "score": r["score"], "tier": r["tier"], "why": parts, "enrich": enrich}


def window_bounds(window: str, as_of: str, frm: str | None = None, to: str | None = None) -> tuple[str, str]:
    end = datetime.fromisoformat(as_of)
    if window == "custom" and frm:
        return datetime.fromisoformat(frm).isoformat(), (datetime.fromisoformat(to) if to else end).isoformat()
    hours = {"24h": 24, "3d": 72, "7d": 168, "30d": 720}.get(window, 24)
    return (end - timedelta(hours=hours)).isoformat(), end.isoformat()


def digest(window: str, as_of: str, frm: str | None = None, to: str | None = None, symbol: str | None = None) -> dict:
    start, end = window_bounds(window, as_of, frm, to)
    sql = "SELECT * FROM announcements WHERE ts>=? AND ts<=?"; params: list = [start, end]
    if symbol:
        sql += " AND symbol=?"; params.append(symbol)
    rows = db.rows(sql + " ORDER BY score DESC, ts DESC", params)
    cards = [_row_to_card(r) for r in rows]
    # Fold same-company, same-category filings into the strongest card ("+N related") so one event = one card.
    lead: dict[tuple, dict] = {}
    folded = []
    for c in cards:  # cards are score-desc, so the first seen is the lead
        k = (c["symbol"], c["category"])
        if c["tier"] != "routine" and k in lead:
            lead[k].setdefault("related", []).append({"id": c["id"], "ts": c["ts"], "headline": c["headline"], "pdf_url": c["pdf_url"]})
            continue
        lead[k] = c; folded.append(c)
    tiers = {"must": [], "look": [], "routine": []}
    for c in folded:
        tiers[c["tier"]].append(c)
    # within a tier, group consecutive cards of the same company so the feed reads company-by-company
    by_cat: dict[str, int] = {}
    for c in folded:
        by_cat[c["category"]] = by_cat.get(c["category"], 0) + 1
    return {"window": window, "from": start, "to": end, "as_of": as_of, "total": len(folded), "raw_total": len(cards),
            "counts": {k: len(v) for k, v in tiers.items()}, "by_category": by_cat, "tiers": tiers,
            "last_ingest": db.kv_get("last_ingest")}


def card(ann_id: str) -> dict | None:
    r = db.one("SELECT * FROM announcements WHERE id=?", (ann_id,))
    return _row_to_card(r) if r else None


def company_feed(symbol: str, limit: int = 30) -> list[dict]:
    return [_row_to_card(r) for r in db.rows("SELECT * FROM announcements WHERE symbol=? ORDER BY ts DESC LIMIT ?", (symbol, limit))]
