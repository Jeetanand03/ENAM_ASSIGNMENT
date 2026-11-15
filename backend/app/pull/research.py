"""Research view assembly for any NSE ticker + a grounded ask-bar.

build(symbol) returns module-by-module so the UI can render skeletons and fill progressively.
Everything numeric comes from `fundamentals` (code), narrative modules from transcripts via `guidance`/`verdict`.
Bull/bear is assembled from the computed signals (rules) and optionally sharpened by the strong model.
"""
from __future__ import annotations
import json, logging, re
from ..sources import screener, pdf
from ..cache import read_snapshot, write_snapshot
from .. import db, llm
from . import fundamentals, guidance, verdict

log = logging.getLogger("finn.research")
N_TRANSCRIPTS = 5

BULLBEAR_SYSTEM = """You are a sceptical buy-side analyst. Using ONLY the facts provided (computed signals, guidance record and quotes with pages),
write a bull case and a bear case, max 4 bullets each, <=22 words per bullet. Every bullet must end with a citation in the form
[source: <doc>, p.<page>] or [source: standardised tables]. Do not use outside knowledge of the company. If evidence is thin, say so.
Return JSON {"bull":[{"text":"","cite":""}],"bear":[{"text":"","cite":""}]}"""

NARRATIVE_SYSTEM = """You compare management's narrative with the filed numbers. Using ONLY the quotes (with pages) and the computed
numbers provided, list up to 4 points where story and numbers AGREE and up to 4 where they DIVERGE. <=25 words each, each with
[source: <doc>, p.<page>]. No outside knowledge. Return JSON {"agree":[{"text":"","cite":""}],"diverge":[{"text":"","cite":""}]}"""

ASK_SYSTEM = """Answer the investor's question about this company using ONLY the passages provided (each tagged with doc and page).
Cite every claim as [doc, p.N]. If the passages do not contain the answer, say "Not disclosed in the documents I have." Max 120 words."""


def _cache_key(symbol: str) -> str:
    return f"research:{symbol}"


def guidance_for(symbol: str, docs: dict, n: int = N_TRANSCRIPTS) -> list[dict]:
    out = []
    for t in (docs.get("transcripts") or [])[:n]:
        try:
            out.append(guidance.extract(symbol, t))
        except Exception as e:
            log.warning("guidance failed %s %s: %s", symbol, t.get("when"), e)
    return out


def rules_bull_bear(num: dict, pvd: dict) -> dict:
    tr, bs, cash, snap = num["trajectory"], num["balance_sheet"], num["cash"], num["snapshot"]
    bull, bear = [], []
    cg = tr.get("cagr") or {}
    if cg.get("revenue") is not None and cg["revenue"] >= 15:
        bull.append({"text": f"Revenue compounding at {cg['revenue']:.0f}% a year over the period shown.", "cite": "standardised tables, profit-loss"})
    elif cg.get("revenue") is not None:
        bear.append({"text": f"Revenue growth is only {cg['revenue']:.0f}% a year — a maturing top line.", "cite": "standardised tables, profit-loss"})
    if cash.get("conversion") is not None:
        (bull if cash["conversion"] >= 0.8 else bear).append({"text": f"CFO/PAT of {cash['conversion']:.2f}× — " + ("profits are real cash." if cash["conversion"] >= 0.8 else "profits are not turning into cash."), "cite": "standardised tables, cash-flow"})
    yrs = bs.get("years") or []
    if yrs and yrs[-1].get("de") is not None:
        (bull if yrs[-1]["de"] < 0.5 else bear).append({"text": f"Debt/equity {yrs[-1]['de']:.2f} — " + ("balance sheet has room." if yrs[-1]["de"] < 0.5 else "leverage is meaningful."), "cite": "standardised tables, balance-sheet"})
    lq = snap.get("latest_quarter") or {}
    if lq.get("rev_yoy") is not None:
        py = lq.get("pat_yoy")
        txt = f"Latest quarter revenue {lq['rev_yoy']:+.0f}% YoY, PAT {py:+.0f}% YoY." if py is not None else f"Latest quarter revenue {lq['rev_yoy']:+.0f}% YoY."
        good = lq["rev_yoy"] > 10 and (py is None or py > 0)
        if py is not None and py < 0 and lq["rev_yoy"] > 10:
            txt += " Sales up, profit down — check the base quarter for one-offs."
        (bull if good else bear).append({"text": txt, "cite": f"standardised tables, quarters ({lq.get('label')})"})
    for s in tr.get("signals", []):
        if "compressed" in s:
            bear.append({"text": s + ".", "cite": "standardised tables, profit-loss"})
        elif "expanded" in s:
            bull.append({"text": s + ".", "cite": "standardised tables, profit-loss"})
    if pvd.get("credibility") is not None:
        (bull if pvd["credibility"] >= 60 else bear).append({"text": pvd["summary"], "cite": "concall transcripts (see promised vs delivered)"})
    return {"bull": bull[:4], "bear": bear[:4], "method": "rules"}


def build(symbol: str, refresh: bool = False, use_llm: bool = True, quick: bool = False) -> dict:
    """quick=True returns the numeric modules only (fast, no PDFs) so the UI can render while transcripts are read."""
    symbol = symbol.upper().strip()
    if not refresh:
        cached = db.kv_get(_cache_key(symbol)) or read_snapshot(f"research_{symbol}")
        if cached:
            return cached
    if quick:
        num = fundamentals.all_numeric(symbol)
        if not num:
            return {"symbol": symbol, "ok": False, "error": "No fundamentals found for this ticker (screener page missing or unparseable)."}
        docs = num.pop("documents") or {}
        return {"symbol": symbol, "ok": True, "partial": True, "name": num["name"], "data_source": num["data_source"],
                "modules": {k: num[k] for k in ("business", "snapshot", "quarters", "trajectory", "balance_sheet", "cash")},
                "documents": {"transcripts": (docs.get("transcripts") or [])[:N_TRANSCRIPTS], "annual_reports": (docs.get("annual_reports") or [])[:3]}}
    num = fundamentals.all_numeric(symbol)
    if not num:
        snap = read_snapshot(f"research_{symbol}")
        if snap:
            return snap
        return {"symbol": symbol, "ok": False, "error": "No fundamentals found for this ticker (screener page missing or unparseable)."}
    docs = num.pop("documents") or {}
    full_q = fundamentals.quarterly_series(screener.load_screener(symbol)[0])
    g = guidance_for(symbol, docs)
    if not any(x.get("items") for x in g):
        # PDFs unavailable on this host (fresh deploy / offline): reuse the committed snapshot's transcript work
        snap = read_snapshot(f"research_{symbol}")
        if snap and snap.get("modules", {}).get("guidance"):
            g = snap["modules"]["guidance"]
    pvd = verdict.promised_vs_delivered(g, full_q, num["trajectory"].get("years"))
    out = {"symbol": symbol, "ok": True, "name": num["name"], "data_source": num["data_source"],
           "modules": {"business": num["business"], "snapshot": num["snapshot"], "quarters": num["quarters"], "trajectory": num["trajectory"],
                       "balance_sheet": num["balance_sheet"], "cash": num["cash"], "guidance": g, "promised_vs_delivered": pvd},
           "documents": {"transcripts": (docs.get("transcripts") or [])[:N_TRANSCRIPTS], "annual_reports": (docs.get("annual_reports") or [])[:3]}}
    facts = _facts_blob(out)
    bb = llm.complete_json("bull_bear", BULLBEAR_SYSTEM, facts, tier="strong", symbol=symbol, prompt_version="v2", max_tokens=900) if use_llm else None
    out["modules"]["bull_bear"] = {**bb, "method": "llm"} if bb and bb.get("bull") else rules_bull_bear(num, pvd)
    nv = llm.complete_json("narrative_vs_numbers", NARRATIVE_SYSTEM, facts, tier="strong", symbol=symbol, prompt_version="v2", max_tokens=900) if use_llm else None
    out["modules"]["narrative"] = {**nv, "method": "llm"} if nv and (nv.get("agree") or nv.get("diverge")) else _rules_narrative(out)
    out["cost"] = _cost(symbol)
    db.kv_set(_cache_key(symbol), out)
    write_snapshot(f"research_{symbol}", out)
    return out


def _rules_narrative(r: dict) -> dict:
    """Without a model: pair each judged promise with its number — that *is* narrative vs numbers."""
    agree, diverge = [], []
    for row in r["modules"]["promised_vs_delivered"]["rows"]:
        if row["verdict"] == "unclear":
            continue
        txt = f"{row['given_in']}: promised {row['promised'][:90]} → delivered {row['delivered']} ({row.get('measure')})."
        (agree if row["verdict"] == "met" else diverge).append({"text": txt, "cite": f"{row['doc']}, p.{row['page']}"})
    return {"agree": agree[:4], "diverge": diverge[:4], "method": "rules"}


def _facts_blob(r: dict) -> str:
    m = r["modules"]
    lines = [f"Company: {r['name']} ({r['symbol']})", "SIGNALS:"]
    for k in ("trajectory", "balance_sheet", "cash"):
        for s in m[k].get("signals", []):
            lines.append(f"- {s} [source: standardised tables]")
    lq = m["snapshot"].get("latest_quarter") or {}
    lines.append(f"- Latest quarter {lq.get('label')}: revenue {lq.get('revenue')} cr ({lq.get('rev_yoy')}% YoY), OPM {lq.get('opm')}%, PAT {lq.get('pat')} cr ({lq.get('pat_yoy')}% YoY) [source: standardised tables]")
    lines.append("GUIDANCE RECORD: " + m["promised_vs_delivered"]["summary"])
    for row in m["promised_vs_delivered"]["rows"][:10]:
        lines.append(f"- [{row['verdict']}] given {row['given_in']}: \"{(row['quote'] or '')[:220]}\" → delivered {row['delivered']} {row.get('measure') or ''} [source: {row['doc']}, p.{row['page']}]")
    return "\n".join(lines)[:9000]


def _cost(symbol: str) -> dict:
    r = db.one("SELECT COUNT(*) calls, COALESCE(SUM(usd),0) usd, COALESCE(SUM(in_tokens),0) i, COALESCE(SUM(out_tokens),0) o FROM cost_log WHERE symbol=? AND cached=0", (symbol,)) or {}
    return {"calls": r.get("calls", 0), "usd": round(r.get("usd", 0.0), 4), "in_tokens": r.get("i", 0), "out_tokens": r.get("o", 0)}


# ---------- ask-bar: retrieval over transcript + AR pages, grounded answer ----------
STOP = set("the a an and or of to in on for is are was were be been with that this it as at by from we our you your i they their what how does did do has have had will would can could about tell me".split())


def _passages(symbol: str, docs: dict, max_docs: int = 4) -> list[dict]:
    out = []
    for t in (docs.get("transcripts") or [])[:max_docs]:
        for p in pdf.pages(symbol, t["url"]) or []:
            out.append({"doc": f"Concall {t.get('when')}", "url": t["url"], "page": p["page"], "text": p["text"]})
    for ar in (docs.get("annual_reports") or [])[:1]:
        for p in (pdf.pages(symbol, ar["url"]) or [])[:120]:
            out.append({"doc": f"Annual Report {ar.get('fy')}", "url": ar["url"], "page": p["page"], "text": p["text"]})
    return out


def ask(symbol: str, question: str, topic: str | None = None) -> dict:
    symbol = symbol.upper()
    r = build(symbol)
    if not r.get("ok"):
        return {"answer": r.get("error"), "citations": []}
    terms = [w for w in re.findall(r"[a-z0-9]+", (question + " " + (topic or "")).lower()) if w not in STOP and len(w) > 2]
    scored = []
    for p in _passages(symbol, r["documents"]):
        txt = p["text"].lower()
        s = sum(txt.count(t) for t in terms)
        if s:
            scored.append((s, p))
    scored.sort(key=lambda x: -x[0])
    top = [p for _, p in scored[:6]]
    if not top:
        return {"answer": "Not disclosed in the documents I have.", "citations": [], "method": "retrieval"}
    ctx = "\n\n".join(f"[{p['doc']}, p.{p['page']}]\n{_window(p['text'], terms)}" for p in top)
    ans = llm.complete("ask", ASK_SYSTEM, f"Question: {question}\n\nPassages:\n{ctx}", tier="cheap", symbol=symbol, max_tokens=350)
    cites = [{"doc": p["doc"], "page": p["page"], "url": p["url"], "snippet": _window(p["text"], terms, 260)} for p in top[:4]]
    if ans:
        return {"answer": ans, "citations": cites, "method": "llm"}
    return {"answer": "No model configured — here are the most relevant passages from the primary documents:", "citations": cites, "method": "retrieval"}


def _window(text: str, terms: list[str], n: int = 900) -> str:
    low = text.lower()
    pos = min((low.find(t) for t in terms if low.find(t) >= 0), default=0)
    start = max(0, pos - n // 3)
    return re.sub(r"\s+", " ", text[start:start + n]).strip()
