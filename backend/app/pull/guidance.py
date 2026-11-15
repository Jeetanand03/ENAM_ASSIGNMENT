"""Guidance extraction from concall transcripts — primary source only, every item cites (doc, page).

Two tiers:
  rules  — free. Sentences by management containing a forward-looking verb + a number/percent + a metric word.
  llm    — cheap model turns the candidate sentences into structured guidance JSON (metric, value, horizon).
If no model is configured we ship the rules tier's output, which is already quoted + cited.
"""
from __future__ import annotations
import collections, re
from ..sources import pdf
from ..cache import read_snapshot
from .. import llm

FORWARD = re.compile(r"\b(guid(e|ance|ing|ed)|expect(s|ed|ing)?|target(s|ed|ing)?|aim(s|ing)?|outlook|aspir(e|ation)|"
                     r"we (should|will|would|plan|intend|anticipate|see|hope|look to|are looking at|are confident)|"
                     r"should (be|close|touch|do|deliver|reach|cross|grow)|going forward|next (year|quarter|fiscal|financial year)|"
                     r"by (fy|financial year|end of|the end)|for (fy|the full year|the year|h2|second half|q[1-4])|over the next|in fy ?\d|exit (rate|run-rate))\b", re.I)
NUMBER = re.compile(r"(\d+(\.\d+)?\s*(%|percent|per cent|bps|basis points|x\b|times)|\b(double|triple|treble)\b|"
                    r"(rs\.?|inr|₹)\s*\d[\d,]*(\.\d+)?\s*(crore|cr|mn|million|bn|billion|lakh)?|\d[\d,]*(\.\d+)?\s*(crore|cr|million|mn|billion|bn)\b|"
                    r"(low|mid|high)[- ](single|double|teens|twenties)|(single|double)[- ]digit|\bteens\b|\d+\s*(to|-|–)\s*\d+\s*(%|percent))", re.I)
RANGE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:%|percent)?\s*(?:to|-|–|,)\s*(\d+(?:\.\d+)?)\s*(%|percent|bps|x\b|times|million|crore|cr\b)", re.I)
SINGLE = re.compile(r"(\d+(?:\.\d+)?)\s*(%|percent|bps|basis points|x\b|times|million|crore|cr\b)", re.I)
WORDS = {"low single": (1, 3), "mid single": (4, 6), "high single": (7, 9), "single-digit": (3, 9), "single digit": (3, 9),
         "low double": (10, 13), "low teens": (10, 13), "mid teens": (14, 16), "high teens": (17, 19), "teens": (13, 19),
         "double-digit": (10, 20), "double digit": (10, 20), "high double": (15, 25), "low twenties": (20, 23), "mid twenties": (24, 26),
         "double": (100, 100), "triple": (200, 200), "treble": (200, 200)}
METRIC_WORDS = {
    "revenue": r"revenue|top ?line|sales|turnover|growth",
    "margin": r"margin|ebitda|profitab|opm|operating profit",
    "capex": r"capex|capital expenditure|investment of|invest\b|expansion",
    "volume": r"volume|units|capacity|utili[sz]ation",
    "profit": r"\bpat\b|net profit|bottom ?line|earnings|eps",
    "order_book": r"order book|order inflow|pipeline|backlog",
    "debt": r"debt|leverage|net cash|borrowing",
    "roce": r"roce|roe|return on",
}
SEGMENT = re.compile(r"(our|the|this|that) [A-Za-z&\-]+ (business|segment|division|vertical)\b|segment|vertical|businesses|\bJV\b|joint venture|division|subsidiar|this business|that business|the business of|for (the )?(lighting|mobile|display|camera|refrigerator|washing|telecom|IT hardware|wearable|hearable|EMS|BFSI|healthcare|hi-?tech)\b", re.I)
PAST = re.compile(r"\b(as on|as of|last (year|quarter|fiscal)|previous (year|quarter)|(in|for|during) the quarter|year ago|contributed|stands? at|stood at|delivered|reported|came in at|closed at|was|were|has been|have been|grew|declined|increased|decreased|achieved|achieving|resulted|resulting|registered|recorded|posted|remained|came up to|ended (the|at))\b", re.I)
STRONG = re.compile(r"\b(expect(s|ed|ing)?|guid(e|ance|ing|ed)|target(s|ed|ing)?|should (be|close|touch|do|deliver|reach|cross|grow|see)|will (be|grow|reach|cross|deliver|see|do)|aim(s|ing)?|aspir|looking at|going forward|next (year|quarter|fiscal)|by (fy|the end|end of)|outlook)\b", re.I)
NOISE = re.compile(r"innovators|peers|competitors|industry (is|has|grew|growth)|market (is|has|grew)|global (players|majors)|market cap|marginal\b|realization|realisation|shareholding|promoter holding|contains|composition|contributed|of our (order book|revenue|sales) (is|are|comes|came|contains)|dividend of|interim dividend|employees|headcount|attrition", re.I)
SPEAKER_SPLIT = re.compile(r"\n(?=[A-Z][A-Za-z.\- ]{2,40}:\s)")
MGMT_HINT = re.compile(r"managing director|\bMD\b|\bCEO\b|\bCFO\b|chairman|chief|president|founder|promoter|group head|whole[- ]time director|executive director|head of", re.I)
ANALYST_HINT = re.compile(r"analyst|question|from (the line of|[A-Z][a-z]+ (securities|capital|asset|mutual|investments?|research|amc|pms|advisors?|broking))", re.I)


def _sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text)
    return [s.strip() for s in re.split(r"(?<=[.?!])\s+(?=[A-Z])", text) if len(s.strip()) > 30]


def _speaker_blocks(pages: list[dict]) -> list[tuple[int, str, str]]:
    """(page, speaker, text) blocks. Speaker detection is heuristic; unknown speakers are kept."""
    out = []
    for p in pages:
        for blk in SPEAKER_SPLIT.split("\n" + (p["text"] or "")):
            m = re.match(r"\s*([A-Z][A-Za-z.\- ]{2,40}):\s(.*)", blk, re.S)
            if m:
                out.append((p["page"], m.group(1).strip(), m.group(2)))
            elif blk.strip():
                out.append((p["page"], "", blk))
    return out


def _mgmt_set(pages: list[dict], blocks: list[tuple[int, str, str]]) -> set[str]:
    """Management = speakers introduced with a title anywhere in the first pages (participants list / intro),
    plus the two most frequent non-moderator speakers (management always talks the most)."""
    head = "\n".join(p["text"] for p in pages[:6])
    names = set()
    for _, spk, _ in blocks:
        if spk and not re.search(r"moderator|operator", spk, re.I):
            sur = spk.split()[-1]
            if re.search(re.escape(sur) + r"[^\n]{0,90}", head, re.I) and any(MGMT_HINT.search(m.group(0)) for m in re.finditer(re.escape(sur) + r"[^\n]{0,90}", head, re.I)):
                names.add(sur.lower())
    freq = collections.Counter(s for _, s, _ in blocks if s and not re.search(r"moderator|operator", s, re.I))
    for s, _ in freq.most_common(2):
        names.add(s.split()[-1].lower())
    return names


def _basis(s: str) -> str:
    if re.search(r"quarter\W{0,3}on\W{0,3}quarter|q-?o-?q|sequential|quarter ?\d (against|over|vs\.?|versus) quarter ?\d|q[1-4] (against|over|vs\.?|versus) q[1-4]", s, re.I):
        return "qoq_growth"
    if re.search(r"margin|bps|basis points", s, re.I):
        return "margin_level"
    if re.search(r"crore|cr\b|million|billion|units", s, re.I) and not re.search(r"%|percent|growth|double|triple|\dx\b", s, re.I):
        return "absolute"
    return "yoy_growth"


def _values(s: str) -> tuple[float | None, float | None, str | None, str | None]:
    """(low, high, unit, text). Multipliers become growth %: 2x -> +100%, double -> +100%."""
    m = RANGE.search(s)
    if m:
        lo, hi, unit = float(m.group(1).replace(",", "")), float(m.group(2).replace(",", "")), m.group(3).lower()
        if unit in ("x", "times"):
            return (lo - 1) * 100, (hi - 1) * 100, "%", m.group(0)
        return lo, hi, unit, m.group(0)
    for w, (lo, hi) in WORDS.items():
        if re.search(r"\b" + re.escape(w), s, re.I):
            return float(lo), float(hi), "%", w
    m = SINGLE.search(s)
    if m:
        v, unit = float(m.group(1).replace(",", "")), m.group(2).lower()
        if unit in ("x", "times"):
            return (v - 1) * 100, (v - 1) * 100, "%", m.group(0)
        return v, v, unit, m.group(0)
    return None, None, None, None


def _horizon(s: str) -> str | None:
    m = re.search(r"\b(Q[1-4]\s*FY\s*'?\d{2,4}|H[12]\s*FY\s*'?\d{2,4}|FY\s*'?\d{2,4}(-\d{2})?|financial year 20\d\d(-\d\d)?|next (year|quarter|fiscal|financial year)|this (year|quarter|fiscal)|current (year|fiscal|quarter)|full year|medium term|long term|[23]-?\s?(to|-)?\s?[345] years|next \d+ (to \d+ )?(months|years))\b", s, re.I)
    return m.group(0) if m else None


def candidates(symbol: str, url: str, limit: int = 40) -> list[dict]:
    pages = pdf.pages(symbol, url)
    if not pages:
        return []
    blocks = _speaker_blocks(pages)
    mgmt = _mgmt_set(pages, blocks)
    out, seen = [], set()
    for page, speaker, text in blocks:
        if speaker and (re.search(r"moderator|operator", speaker, re.I) or speaker.split()[-1].lower() not in mgmt):
            continue
        for s in _sentences(text):
            if len(s) > 420 or not FORWARD.search(s) or not NUMBER.search(s):
                continue
            if PAST.search(s) and not STRONG.search(s):
                continue  # a past-tense fact with a number, not guidance
            if NOISE.search(s):
                continue  # market cap, shareholding mix, order-book composition: numbers, but not promises
            metrics = [k for k, pat in METRIC_WORDS.items() if re.search(pat, s, re.I)]
            if "revenue" in metrics and len(metrics) > 1 and not re.search(r"revenue|top ?line|sales|turnover", s, re.I):
                metrics.remove("revenue")  # matched only via the word "growth"
            if "volume" in metrics and "revenue" in metrics and not re.search(r"revenue|top ?line|sales", s, re.I):
                metrics.remove("revenue")
            if not metrics:
                continue
            key = s[:80].lower()
            if key in seen:
                continue
            seen.add(key)
            out.append({"quote": s, "page": page, "speaker": speaker or None, "metrics": metrics})
    out.sort(key=lambda c: (-bool(re.search(r"guid|target|expect|aim|aspir", c["quote"], re.I)), -len(c["metrics"])))
    return out[:limit]


GUIDANCE_SYSTEM = """You are given sentences spoken by a company's management on an earnings call (each with a page number).
Extract explicit, forward-looking guidance ONLY — numbers or ranges management commits to or expects for a future period.
Ignore past results, analyst questions, and vague optimism without a figure.
Return JSON: {"items":[{"metric":"revenue|margin|capex|volume|profit|order_book|debt|other","statement":"<=18 words paraphrase",
"value_low":number|null,"value_high":number|null,"unit":"%|pp|Rs cr|x|units|other","basis":"yoy_growth|qoq_growth|absolute|margin_level|other",
"scope":"company|segment","horizon":"FY26|Q3 FY26|H2 FY26|medium_term|null","quote":"verbatim sentence","page":int}]}
Keep at most 8 items; prefer the most specific. Multipliers are growth: '2x' => value_low 100, unit '%'."""


def extract(symbol: str, transcript: dict) -> dict:
    """One transcript -> {when, ym, url, items[], method}."""
    cands = candidates(symbol, transcript["url"])
    base = {"when": transcript.get("when"), "ym": transcript.get("ym"), "url": transcript["url"], "doc": f"Concall transcript {transcript.get('when')}"}
    curated = (read_snapshot("guidance_curated") or {}).get("by_url", {})
    if not cands and transcript["url"] in curated:
        return {**base, "items": curated[transcript["url"]][:8], "method": "llm-curated", "candidates": 0}
    if not cands:
        return {**base, "items": [], "method": "none", "candidates": 0}
    prompt = "\n".join(f"[p{c['page']}] {c['quote']}" for c in cands[:30])
    j = llm.complete_json("guidance_extract", GUIDANCE_SYSTEM, prompt, tier="cheap", symbol=symbol, prompt_version="v3", max_tokens=1200)
    if j and isinstance(j.get("items"), list):
        items = [i for i in j["items"] if i.get("quote")]
        return {**base, "items": items[:8], "method": "llm", "candidates": len(cands)}
    if transcript["url"] in curated:  # LLM-tier output produced offline for the demo set (see DECISIONS.md)
        return {**base, "items": curated[transcript["url"]][:8], "method": "llm-curated", "candidates": len(cands)}
    items, seen_vals = [], set()
    for c in cands[:12]:
        lo, hi, unit, txt = _values(c["quote"])
        if unit in ("percent",): unit = "%"
        if unit in ("crores", "cr"): unit = "crore"
        sig = (c["metrics"][0], lo, hi)
        if sig in seen_vals:
            continue
        seen_vals.add(sig)
        if len(items) >= 8:
            break
        items.append({"metric": c["metrics"][0], "statement": None, "value_low": lo, "value_high": hi, "unit": unit, "value_text": txt,
                      "basis": _basis(c["quote"]), "scope": "segment" if SEGMENT.search(c["quote"]) else "company",
                      "quote": c["quote"], "page": c["page"], "speaker": c["speaker"], "horizon": _horizon(c["quote"])})
    return {**base, "items": items, "method": "rules", "candidates": len(cands)}
