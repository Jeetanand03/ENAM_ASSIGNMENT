"""Enriched cards for the two filing types the brief calls out, plus a cheap one-liner for the rest.

Results card:    results PDF -> pdfplumber text/tables -> LLM extracts raw figures as JSON (3 periods)
                 -> Python computes QoQ/YoY/margins. If the LLM is unavailable we fall back to screener's
                 standardised quarterly table (same filed numbers) so the card still renders.
Management card: LLM pulls (person, role, in/out, effective date) from the filing text -> web search
                 (Tavily, if key) for a 2–3 line background, labelled "public web, unverified".
"""
from __future__ import annotations
import json, logging, re
from ..sources import pdf, screener
from .. import db, llm, config

log = logging.getLogger("finn.enrich")

RESULTS_SYSTEM = """You extract figures from an Indian listed company's quarterly results filing.
Use ONLY the provided text. Prefer CONSOLIDATED figures if both are present. Units: Rs crore (convert from lakhs/millions if needed; state the unit you used).
Return JSON:
{"unit":"Rs crore","basis":"consolidated|standalone","periods":{"current":{"label":"Q2 FY27","revenue":..,"other_income":..,"finance_cost":..,"depreciation":..,"pbt":..,"pat":..,"ebitda":null|..},
 "previous":{...same keys...},"year_ago":{...same keys...}},"notes":"<=20 words on anything unusual (exceptional items, one-offs)"}
Use null when a figure is not in the text. Never compute growth rates yourself."""

MGMT_SYSTEM = """From this stock-exchange filing text extract management changes. Return JSON:
{"changes":[{"person":"","role":"","direction":"in|out|reappointed","effective":"YYYY-MM-DD or null","reason":"<=12 words or null"}]}
Only use the text provided."""


def _pct(a, b):
    if a is None or b in (None, 0):
        return None
    return round((a / b - 1) * 100, 1)


def _margin(x, rev):
    if x is None or not rev:
        return None
    return round(x / rev * 100, 1)


def _derive_ebitda(p: dict) -> tuple[float | None, bool]:
    if p.get("ebitda") is not None:
        return p["ebitda"], False
    if p.get("pbt") is None:
        return None, False
    e = p["pbt"] + (p.get("finance_cost") or 0) + (p.get("depreciation") or 0) - (p.get("other_income") or 0)
    return round(e, 1), True


def compute_results_table(periods: dict) -> dict:
    cur, prev, ya = periods.get("current") or {}, periods.get("previous") or {}, periods.get("year_ago") or {}
    rows = []
    e_cur, dcur = _derive_ebitda(cur); e_prev, _ = _derive_ebitda(prev); e_ya, _ = _derive_ebitda(ya)
    for key, label, vals, derived in (("revenue", "Revenue", (cur.get("revenue"), prev.get("revenue"), ya.get("revenue")), False),
                                      ("ebitda", "EBITDA", (e_cur, e_prev, e_ya), dcur),
                                      ("pbt", "PBT", (cur.get("pbt"), prev.get("pbt"), ya.get("pbt")), False),
                                      ("pat", "PAT", (cur.get("pat"), prev.get("pat"), ya.get("pat")), False)):
        c, p, y = vals
        rows.append({"key": key, "label": label, "current": c, "previous": p, "year_ago": y,
                     "qoq": _pct(c, p), "yoy": _pct(c, y), "derived": derived,
                     "margin": _margin(c, cur.get("revenue")) if key != "revenue" else None,
                     "margin_prev": _margin(p, prev.get("revenue")) if key != "revenue" else None,
                     "margin_ya": _margin(y, ya.get("revenue")) if key != "revenue" else None})
    return {"rows": rows, "labels": {"current": cur.get("label"), "previous": prev.get("label"), "year_ago": ya.get("label")}}


def _takeaway(table: dict) -> str:
    """Rule-based one-liner (no model): what moved most, in words."""
    r = {x["key"]: x for x in table["rows"]}
    rev, pat, eb = r["revenue"], r["pat"], r["ebitda"]
    bits = []
    if rev["yoy"] is not None:
        bits.append(f"Revenue {rev['yoy']:+.0f}% YoY")
    if pat["yoy"] is not None:
        bits.append(f"PAT {pat['yoy']:+.0f}% YoY")
    if eb["margin"] is not None and eb["margin_ya"] is not None:
        d = eb["margin"] - eb["margin_ya"]
        bits.append(f"margin {'expanded' if d > 0 else 'compressed'} {abs(d):.1f}pp")
    if pat["yoy"] is not None and rev["yoy"] is not None:
        if pat["yoy"] > rev["yoy"] + 5: bits.append("operating leverage showing")
        elif pat["yoy"] < rev["yoy"] - 5: bits.append("profit lagging sales")
    return "; ".join(bits) + "." if bits else "Headline numbers extracted; compare rows."


def _label(col: str) -> str:
    m = re.match(r"([A-Z][a-z]{2}) (20\d\d)", col)
    if not m:
        return col
    mon, yr = m.group(1), int(m.group(2))
    q = {"Jun": "Q1", "Sep": "Q2", "Dec": "Q3", "Mar": "Q4"}.get(mon, mon)
    fy = yr + 1 if mon != "Mar" else yr
    return f"{q} FY{str(fy)[2:]}"


def results_from_screener(symbol: str) -> dict | None:
    sc, _ = screener.load_screener(symbol)
    if not sc or not sc.get("quarters"):
        return None
    cols, rows = sc["quarters"]["columns"], sc["quarters"]["rows"]
    if len(cols) < 5:
        return None

    def period(i):
        g = lambda k: (rows.get(k) or [None] * len(cols))[i]
        return {"label": _label(cols[i]), "revenue": g("Sales") or g("Revenue"), "other_income": g("Other Income"),
                "finance_cost": g("Interest"), "depreciation": g("Depreciation"), "pbt": g("Profit before tax"),
                "pat": g("Net Profit"), "ebitda": g("Operating Profit") if g("Operating Profit") is not None else None}
    n = len(cols) - 1
    return {"unit": "Rs crore", "basis": "consolidated" if sc.get("consolidated") else "standalone",
            "periods": {"current": period(n), "previous": period(n - 1), "year_ago": period(n - 4)},
            "notes": None, "source": {"kind": "screener standardised table", "url": sc.get("source_url")}}


def results_card(ann: dict) -> dict:
    symbol = ann["symbol"]
    extracted, source = None, None
    if ann.get("pdf_url") and any(llm.available().values()):  # no model -> the filed standardised table is the source; skip the download
        pages = pdf.pages(symbol, ann["pdf_url"], max_pages=8)
        if pages:
            text = "\n\n".join(f"[page {p['page']}]\n{p['text']}" for p in pages if p["text"])[:24000]
            j = llm.complete_json("results_extract", RESULTS_SYSTEM, text, tier="cheap", symbol=symbol, prompt_version="v2")
            if j and j.get("periods"):
                extracted, source = j, {"kind": "results filing", "url": ann["pdf_url"], "page": 1}
    if not extracted:
        extracted = results_from_screener(symbol)
        source = extracted.get("source") if extracted else None
    if not extracted:
        return {"kind": "results", "ok": False, "reason": "no figures available"}
    table = compute_results_table(extracted["periods"])
    return {"kind": "results", "ok": True, "unit": extracted.get("unit"), "basis": extracted.get("basis"),
            "table": table, "takeaway": _takeaway(table), "notes": extracted.get("notes"), "source": source,
            "method": "LLM extraction from filing" if source and source.get("kind") == "results filing" else "standardised table (filed numbers)"}


def _bio_search(person: str, company: str) -> dict | None:
    if not config.TAVILY_API_KEY or config.OFFLINE:
        return None
    try:
        from ..sources.http import client
        r = client().post("https://api.tavily.com/search", json={"api_key": config.TAVILY_API_KEY,
                          "query": f"{person} {company} profile career", "max_results": 4, "include_answer": True})
        r.raise_for_status(); j = r.json()
        return {"answer": j.get("answer"), "sources": [{"title": x.get("title"), "url": x.get("url")} for x in j.get("results", [])[:3]]}
    except Exception as e:
        log.warning("bio search failed: %s", e)
        return None


def management_card(ann: dict) -> dict:
    symbol = ann["symbol"]
    text = (ann.get("summary") or "") + "\n" + (ann.get("subject") or "")
    if ann.get("pdf_url"):  # management filings are 1–3 page letters: always worth reading
        pages = pdf.pages(symbol, ann["pdf_url"], max_pages=4)
        if pages:
            text += "\n" + "\n".join(p["text"] for p in pages)[:8000]
    j = llm.complete_json("mgmt_extract", MGMT_SYSTEM, text[:9000], tier="cheap", symbol=symbol, max_tokens=400)
    changes = (j or {}).get("changes") or _mgmt_rules(text)
    for ch in changes:
        if ch.get("direction") in ("in", "reappointed") and ch.get("person"):
            bio = _bio_search(ch["person"], ann.get("name") or symbol)
            if bio and bio.get("answer"):
                ch["bio"] = {"text": bio["answer"][:400], "label": "public web, unverified", "sources": bio["sources"]}
    return {"kind": "management_change", "ok": bool(changes), "changes": changes,
            "method": "LLM extraction" if j else "rule extraction"}


def _mgmt_rules(text: str) -> list[dict]:
    """No-model fallback: find 'Mr./Ms. X ... as <role>' patterns."""
    out = []
    text = re.sub(r"\s+", " ", text)
    ROLEWORD = re.compile(r"^(CEO|CFO|COO|MD|Chairman|Chairperson|Director|Officer|Company|Board|Limited|Ltd|Secretary)$", re.I)
    for m in re.finditer(r"(Mr\.?|Ms\.?|Mrs\.?|Dr\.|Shri|Smt\.?)\s+([A-Z][A-Za-z.\-]+(?:\s+[A-Z][A-Za-z.\-]+){0,3})", text):
        words = [w for w in m.group(2).split() if not ROLEWORD.match(w)]
        if not words:
            continue
        person = f"{m.group(1).rstrip('.')}. {' '.join(words)}".replace("Shri.", "Shri").replace("Smt..", "Smt.")
        window = text[max(0, m.start() - 120): m.start() + 260]
        after = text[m.end(): m.end() + 200]
        role = re.search(r"(Chief [A-Z][a-z]+ Officer|Managing Director|Whole[- ]time Director|Independent Director|Executive Director|Chairman|Chairperson|Company Secretary|Compliance Officer|CEO|CFO|Director)", after, re.I)
        direction = "out" if re.search(r"resign|cessation|retire|step(ped|s)? down|demise", window, re.I) else "reappointed" if re.search(r"re-?appoint", window, re.I) else "in" if re.search(r"appoint|elevat|designat", window, re.I) else None
        eff = re.search(r"(\d{1,2}(st|nd|rd|th)?\s+[A-Z][a-z]+,?\s+20\d\d|[A-Z][a-z]+\s+\d{1,2},?\s+20\d\d)", window)
        surname = person.split()[-1].lower()
        if direction and surname not in [o["person"].split()[-1].lower() for o in out] :
            out.append({"person": person, "role": role.group(1) if role else None, "direction": direction,
                        "effective": eff.group(1) if eff else None, "reason": None})
    names = [o["person"] for o in out]
    out = [o for o in out if not any(n != o["person"] and n.startswith(o["person"] + " ") for n in names)]
    return out[:3]


def enrich(ann: dict, force: bool = False) -> dict | None:
    row = db.one("SELECT enrich FROM announcements WHERE id=?", (ann["id"],))
    if row and row["enrich"] and not force:
        return json.loads(row["enrich"])
    cat = ann["category"]
    from ..cache import read_snapshot
    snap = (read_snapshot("enrich_cache") or {}).get(ann["id"]) if not force else None
    if snap is not None:  # computed earlier and committed: a cold serverless instance never re-downloads filings
        out = snap
    elif cat == "results":
        out = results_card(ann)
    elif cat == "management_change":
        out = management_card(ann)
    else:
        return None
    with db.tx() as c:
        c.execute("UPDATE announcements SET enrich=? WHERE id=?", (json.dumps(out, ensure_ascii=False), ann["id"]))
    return out


def enrich_top(limit: int = 60) -> int:
    """Pre-compute cards for material results / management filings so the feed shows numbers without a tap."""
    from .digest import card
    rows = db.rows("SELECT id FROM announcements WHERE category IN ('results','management_change') AND tier IN ('must','look') "
                   "AND enrich IS NULL ORDER BY ts DESC LIMIT ?", (limit,))
    n = 0
    for r in rows:
        try:
            if enrich(card(r["id"])):
                n += 1
        except Exception as ex:
            log.warning("enrich_top %s: %s", r["id"], ex)
    return n
