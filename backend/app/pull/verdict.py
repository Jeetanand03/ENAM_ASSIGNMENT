"""Promised vs delivered. Guidance (from transcripts) is matched to actual numbers (filed) and
judged in code: met | partially | missed | unclear. The LLM never computes a number.

Matching rules
  * growth guidance (revenue / profit, % YoY)   -> average YoY growth of the quarters after the call, within the horizon
  * sequential guidance (% QoQ)                 -> the first quarter after the call
  * margin level guidance (%)                   -> average operating margin of those quarters (EBIT-margin guidance is not comparable)
  * absolute full-year revenue target (Rs cr)   -> the annual P&L figure for that FY once reported
  * segment-level guidance                      -> never judged against consolidated numbers
"""
from __future__ import annotations
import re
from datetime import date

TOL = {"revenue": 3.0, "profit": 5.0, "margin": 1.0, "volume": 3.0}
ORDER = {"missed": 0, "partially": 1, "met": 2, "unclear": 3}


def _quarter_date(label: str) -> date | None:
    m = re.match(r"Q([1-4]) FY(\d\d)", label or "")
    if not m:
        return None
    q, fy = int(m.group(1)), 2000 + int(m.group(2))
    month = {1: 6, 2: 9, 3: 12, 4: 3}[q]
    return date(fy - 1 if q != 4 else fy, month, {6: 30, 9: 30, 12: 31, 3: 31}[month])


def _range(item: dict) -> tuple[float | None, float | None]:
    lo, hi = item.get("value_low"), item.get("value_high")
    if lo is None and hi is None and item.get("value_text"):
        nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", item["value_text"].replace(",", ""))]
        if nums:
            lo, hi = min(nums), max(nums)
    if hi is None and lo is not None:
        hi = None  # open-ended ("20% plus")
    if lo is None and hi is not None:
        lo = hi
    return lo, hi


def _fy_from_horizon(h: str | None) -> str | None:
    m = re.search(r"FY\s*'?(\d{2})(\d{2})?", h or "", re.I)
    if not m or re.search(r"medium|long", h or "", re.I):
        return None
    return f"FY{(m.group(2) or m.group(1))[-2:]}"


def _horizon_quarters(item: dict, given_ym: str | None, quarters: list[dict]) -> list[dict]:
    if not given_ym:
        return []
    given = date(int(given_ym[:4]), int(given_ym[5:7]), 1)
    fut = [q for q in quarters if (_quarter_date(q["label"]) or date(1900, 1, 1)) >= given]
    h = item.get("horizon") or ""
    mq = re.search(r"Q([1-4])\s*FY\s*'?(\d{2})", h, re.I)
    if mq:
        return [q for q in fut if q["label"] == f"Q{mq.group(1)} FY{mq.group(2)[-2:]}"]
    fy = _fy_from_horizon(h)
    if fy:
        return [q for q in fut if q["label"].endswith(fy)]
    return fut[:4]


def _compare(lo: float, hi: float | None, actual: float, tol: float) -> tuple[str, str | None]:
    top = hi if hi is not None else lo
    if actual > top + tol:
        return "met", "beat" if hi is not None or actual > lo + tol else None
    if lo - tol <= actual <= top + tol:
        return ("met" if actual >= lo else "partially"), None
    if actual >= lo - 2 * tol:
        return "partially", None
    return "missed", None


def judge(item: dict, given_ym: str | None, quarters: list[dict], annual: list[dict] | None = None) -> dict:
    metric = item.get("metric") or "other"
    basis = item.get("basis") or ""
    unit = (item.get("unit") or "").lower()
    lo, hi = _range(item)
    out = {"metric": metric, "promised": item.get("statement") or item.get("quote"), "range": [lo, hi], "unit": item.get("unit") or item.get("value_text"),
           "horizon": item.get("horizon"), "quote": item.get("quote"), "page": item.get("page"), "judged_on": [], "verdict": "unclear", "delivered": None}
    if lo is None:
        out["why"] = "guidance has no explicit figure"; return out
    if (item.get("scope") or "company") == "segment":
        out["why"] = "segment-level guidance — consolidated numbers can't judge it"; return out
    if metric == "capex":
        out["why"] = "capex outturn is in the cash-flow statement, not reported quarterly — check at year end"; return out
    if metric not in ("revenue", "profit", "margin"):
        out["why"] = "no comparable filed number for this metric"; return out

    # absolute full-year revenue target -> annual P&L
    if metric == "revenue" and basis == "absolute":
        fy = _fy_from_horizon(item.get("horizon"))
        if unit not in ("rs cr", "crore", "cr", "rs crore") or not fy:
            out["why"] = f"absolute target in {item.get('unit')}; not comparable to the standardised tables"; return out
        yr = next((y for y in (annual or []) if y.get("fy") == fy and y.get("revenue")), None)
        if not yr:
            out["why"] = f"{fy} not reported yet"; return out
        actual = float(yr["revenue"])
        out.update({"judged_on": [{"label": fy, "value": actual}], "measure": "annual revenue, Rs cr", "delivered": actual})
        v, note = _compare(lo, hi, actual, 0.03 * lo)
        out["verdict"] = v; out["why"] = note; out["gap"] = round(actual - lo, 0); return out

    q = item.get("quote") or ""
    if metric == "margin" and re.search(r"gross|\bGP\b|EBIT\b|PAT margin|net margin|contribution margin", q, re.I):
        out["why"] = "gross / EBIT / net margin guidance; standardised tables carry operating (EBITDA) margin only"; return out
    if item.get("method_hint") == "rules":
        from .guidance import PAST
        if PAST.search(q):
            out["why"] = "sentence mixes past results with outlook — left for a model to read"; return out
    if re.search(r"declin|drop|fall|contract", q, re.I) and item.get("method_hint") == "rules":
        out["why"] = "direction of the figure is ambiguous (decline language) — left for a model to read"; return out
    if metric == "margin" and basis not in ("margin_level", "", None):
        out["why"] = "margin guidance is a change or an EBIT figure; standardised tables carry EBITDA-margin levels only"; return out
    if metric in ("revenue", "profit") and unit not in ("%", "percent", "pp"):
        out["why"] = f"target stated in {item.get('unit')}, not as growth"; return out

    fy = _fy_from_horizon(item.get("horizon"))
    if fy and metric in ("revenue", "profit") and basis != "qoq_growth" and not re.search(r"Q[1-4]", item.get("horizon") or ""):
        yr = next((y for y in (annual or []) if y.get("fy") == fy), None)
        g = (yr or {}).get("rev_growth" if metric == "revenue" else "pat_growth")
        if g is not None:  # full year reported: judge the full-year promise on the full year
            out.update({"judged_on": [{"label": fy, "value": g}], "measure": f"{'revenue' if metric == 'revenue' else 'PAT'} growth, full year", "delivered": g})
            v, note = _compare(lo, hi, g, TOL.get(metric, 3.0))
            out["verdict"] = v; out["why"] = note; out["gap"] = round(g - lo, 1); return out
    qs = _horizon_quarters(item, given_ym, quarters)
    if fy and qs and len(qs) < 4 and not re.search(r"Q[1-4]", item.get("horizon") or ""):
        out["partial"] = True  # year still running: verdict is "so far"
    if not qs:
        out["why"] = "those quarters are not reported yet"; return out
    if metric == "revenue" and basis == "qoq_growth":
        vals = [(q["label"], q.get("rev_qoq")) for q in qs[:1] if q.get("rev_qoq") is not None]; measure = "revenue QoQ %"
    elif metric == "revenue":
        vals = [(q["label"], q.get("rev_yoy")) for q in qs if q.get("rev_yoy") is not None]; measure = "revenue YoY %"
    elif metric == "profit":
        vals = [(q["label"], q.get("pat_yoy")) for q in qs if q.get("pat_yoy") is not None]; measure = "PAT YoY %"
    else:
        if not (0 < lo < 80) or not re.search(r"\bmargins?\b", item.get("quote") or "", re.I):
            out["why"] = "margin guidance not expressed as a level"; return out
        vals = [(q["label"], q.get("opm")) for q in qs if q.get("opm") is not None]; measure = "operating margin %"
    if not vals:
        out["why"] = "those quarters are not reported yet"; return out
    actual = round(sum(v for _, v in vals) / len(vals), 1)
    out.update({"judged_on": [{"label": l, "value": v} for l, v in vals], "measure": measure, "delivered": actual})
    v, note = _compare(lo, hi, actual, TOL.get(metric, 3.0))
    out["verdict"] = v; out["why"] = note; out["gap"] = round(actual - lo, 1)
    return out


def promised_vs_delivered(guidance_by_transcript: list[dict], quarters: list[dict], annual: list[dict] | None = None) -> dict:
    rows, counts = [], {"met": 0, "partially": 0, "missed": 0, "unclear": 0}
    rules_only = bool(guidance_by_transcript) and all(t.get("method") in ("rules", "none") for t in guidance_by_transcript)
    for t in guidance_by_transcript:
        for item in t.get("items", []):
            if t.get("method") == "rules":
                item = {**item, "method_hint": "rules"}
            v = judge(item, t.get("ym"), quarters, annual)
            v.update({"given_in": t.get("when"), "doc": t.get("doc"), "url": t.get("url")})
            rows.append(v); counts[v["verdict"]] += 1
    judged = [r for r in rows if r["verdict"] != "unclear"]
    rows.sort(key=lambda r: (ORDER[r["verdict"]], r.get("given_in") or ""))
    score = round(100 * (counts["met"] + 0.5 * counts["partially"]) / len(judged)) if judged else None
    summary = _summary(counts, score, len(rows))
    if rules_only:
        judged_n = counts["met"] + counts["partially"] + counts["missed"]
        summary = (f"{len(rows)} forward-looking statements quoted below. Without a model key this deployment only judges unambiguous ones"
                   + (f": {counts['met']} met, {counts['partially']} partially, {counts['missed']} missed." if judged_n else ", and none qualified.")
                   + " The four demo companies carry model-extracted guidance.")
    return {"rows": rows, "counts": counts, "credibility": score, "summary": summary, "tier": "rules" if rules_only else "model"}


def _summary(c: dict, score, total: int) -> str:
    n = c["met"] + c["partially"] + c["missed"]
    if not n:
        return f"{total} forward-looking statements found, none with a figure FINN can check against filed numbers. Management talks direction, not targets." if total else "No guidance with a checkable figure found in the transcripts read."
    tone = "reliable" if score >= 75 else "mixed" if score >= 45 else "over-promising"
    return f"{n} checkable promises: {c['met']} met, {c['partially']} partially, {c['missed']} missed — guidance record looks {tone}. {c['unclear']} more were segment-level or not yet reportable."
