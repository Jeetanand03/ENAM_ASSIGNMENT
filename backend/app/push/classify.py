"""Rules-first announcement classifier. Free, deterministic, explainable.

Step 1: NSE's raw category (`desc`) maps directly for most filings.
Step 2: keyword rules on the subject refine / override (e.g. "Outcome of Board Meeting" + "financial results" -> results).
Step 3 (elsewhere): an LLM is consulted only when still unclassified AND the subject is long enough to be ambiguous.
"""
from __future__ import annotations
import re

CATEGORIES = ["results", "M&A", "fund_raise", "management_change", "litigation", "insider_trading",
              "earnings_call", "investor_meetings", "credit_rating", "dividend", "bonus_split", "capex",
              "press_release", "postal_ballot", "agm_egm", "pledging", "unclassified"]

# NSE `desc` -> category (exact, case-insensitive)
RAW_MAP = {
    "financial result updates": "results", "financial results": "results",
    "acquisition": "M&A", "amalgamation / merger": "M&A", "amalgamation/merger": "M&A", "scheme of arrangement": "M&A",
    "demerger": "M&A", "joint venture": "M&A", "divestment": "M&A", "slump sale": "M&A",
    "buyback": "fund_raise", "rights issue": "fund_raise", "qualified institutional placement": "fund_raise",
    "preferential issue": "fund_raise", "fund raising": "fund_raise", "issue of securities": "fund_raise",
    "commercial paper": "fund_raise", "debenture": "fund_raise", "ncd": "fund_raise",
    "change in director(s)": "management_change", "change in directors/ key managerial personnel/ auditor/ compliance officer/ share transfer agent": "management_change",
    "change in management": "management_change", "resignation": "management_change", "appointment": "management_change",
    "litigation": "litigation", "regulatory": "litigation", "penalty": "litigation", "insolvency": "litigation",
    "action(s) taken or orders passed": "litigation", "action(s) initiated or orders passed": "litigation",
    "outcome of board meeting": "press_release",  # a bare board-meeting outcome without a results/dividend hint
    "board meeting": "press_release", "updates": "press_release", "general updates": "press_release",
    "disclosure under insider trading regulation": "insider_trading", "disclosure under sebi takeover regulations": "insider_trading",
    "analysts/institutional investor meet/con. call updates": "investor_meetings",
    "investor presentation": "investor_meetings",
    "credit rating": "credit_rating",
    "dividend": "dividend", "record date": "dividend",
    "bonus": "bonus_split", "stock split": "bonus_split", "sub-division": "bonus_split",
    "press release": "press_release", "media release": "press_release", "news verification": "press_release",
    "news clarification": "press_release", "clarification": "press_release",
    "postal ballot": "postal_ballot", "voting results": "postal_ballot",
    "shareholders meeting": "agm_egm", "annual general meeting": "agm_egm", "extraordinary general meeting": "agm_egm",
    "pledge": "pledging", "encumbrance": "pledging",
    # routine paperwork -> unclassified on purpose (score 0, collapsed)
    "loss of share certificates": "unclassified", "loss of share certificate": "unclassified",
    "allotment of esop/esps": "unclassified", "esops/esos/esps": "unclassified", "trading window": "unclassified",
    "copy of newspaper publication": "unclassified", "allotment of securities": "unclassified",
    "certificate under sebi (depositories and participants) regulations": "unclassified",
    "investor grievance": "unclassified", "related party transactions": "unclassified",
    "business responsibility and sustainability report": "unclassified", "annual report": "unclassified",
    "change in registered office": "unclassified", "closure of trading window": "unclassified",
    "monitoring agency report": "unclassified", "statement of deviation(s) or variation(s) under reg. 32": "unclassified",
    "certificate under sebi (depositories and participants) regulations, 2018": "unclassified",
}

# (regex on subject, category) — ordered: first hit wins. Material things first.
SUBJECT_RULES: list[tuple[re.Pattern, str]] = [(re.compile(p, re.I), c) for p, c in [
    (r"transcript|earnings (conference )?call|concall|conference call.*(q[1-4]|quarter|results)|audio recording", "earnings_call"),
    (r"(un-?audited|audited) (standalone|consolidated|financial)|financial results? for the (quarter|half|year|period)|outcome of (the )?board meeting.*(result|quarter)|results? (for|of) (q[1-4]|the quarter)|approved .{0,40}financial results", "results"),
    (r"acqui(re|sition)|merger|amalgamation|demerger|joint venture|\bJV\b|stake (sale|purchase)|divest|slump sale|scheme of arrangement|subsidiar(y|ies).*(incorporat|acquir|invest)", "M&A"),
    (r"resign|appoint|cessation|retire|steps? down|demise|superannuat|re-?designat|chief (executive|financial|operating)|\bCEO\b|\bCFO\b|managing director|\bMD\b|whole[- ]time director|company secretary|independent director|key managerial", "management_change"),
    (r"show[- ]cause|penalty|fine|litigation|arbitra|tribunal|\bNCLT\b|\bSAT\b|\bSEBI order\b|writ|court|insolvency|\bIBC\b|prosecution|demand (order|notice)|tax (order|notice|demand)|GST (order|notice)", "litigation"),
    (r"credit rating|rating (action|update|reaffirm|upgrade|downgrade|assigned)|(?-i:\bCRISIL\b|\bICRA\b|\bCARE\b)|India Ratings|Brickwork", "credit_rating"),
    (r"pledg|encumbr|release of pledge", "pledging"),
    (r"buy-?back|rights issue|\bQIP\b|qualified institution|preferential (issue|allotment)|fund ?rais|commercial paper|debenture|\bNCD\b|borrowing|term loan|bond issue", "fund_raise"),
    (r"bonus (issue|share)|stock split|sub-?division", "bonus_split"),
    (r"dividend", "dividend"),
    (r"insider trading|SAST|takeover regulation|promoter.*(acquir|sold|purchase|disposal)", "insider_trading"),
    (r"capacity (expansion|addition)|new (plant|facility|manufacturing|unit)|capex|greenfield|brownfield|expansion (project|plan)", "capex"),
    (r"postal ballot|e-?voting result|voting results|scrutini[sz]er", "postal_ballot"),
    (r"annual general meeting|\bAGM\b|extra-?ordinary general meeting|\bEGM\b", "agm_egm"),
    (r"investor (meet|conference|day)|analyst (meet|day|call)|one-on-one|group meeting|roadshow|institutional investor|investor presentation", "investor_meetings"),
    (r"order (win|book|received)|bags? (an )?order|letter of (award|intent)|contract (win|award)|purchase order|\bLOA\b|\bLOI\b|press release|media release|launch|partnership|collaborat|clarification|rumou?r|news (item|article|report)", "press_release"),
    (r"loss of share certificate|duplicate share|esop|espp|\bESOS\b|allotment of (equity )?shares? (pursuant|under)|trading window|newspaper (publication|advertisement)|compliance certificate|investor grievance|reconciliation of share capital|business responsibility|sustainability report|secretarial compliance|change in registered office|registrar|related party transaction", "unclassified"),
]]

# Finer signal used by scoring
SENIORITY = re.compile(r"chief executive|\bCEO\b|chief financial|\bCFO\b|managing director|\bMD\b|chairman|chairperson|whole[- ]time director|executive director", re.I)
ORDER_WIN = re.compile(r"order (win|book|received)|bags? (an )?order|letter of (award|intent)|contract (win|award)|purchase order|\bLOA\b|\bLOI\b", re.I)
DOWNGRADE = re.compile(r"downgrad|negative|watch", re.I)
REAFFIRM = re.compile(r"reaffirm|re-affirm|reiterat|retain|unchanged", re.I)
UPGRADE = re.compile(r"upgrad", re.I)


def classify(subject: str, category_raw: str, summary: str | None = None) -> tuple[str, str]:
    """Returns (category, source). source in {'raw','rule','none'}.
    NSE's own summary (when present) is appended to the subject so bare subjects like
    "Outcome of Board Meeting" still classify from their content."""
    subj = (subject or "") + ("\n" + summary if summary else "")
    raw = (category_raw or "").strip().lower()
    # subject rules first for the really material ones (NSE's desc is often just "Updates"/"Outcome of Board Meeting")
    for pat, cat in SUBJECT_RULES[:3]:
        if pat.search(subj):
            return cat, "rule"
    if raw in RAW_MAP:
        return RAW_MAP[raw], "raw"
    for pat, cat in SUBJECT_RULES[3:]:
        if pat.search(subj):
            return cat, "rule"
    for key, cat in RAW_MAP.items():  # partial match on raw desc
        if key in raw:
            return cat, "raw"
    return "unclassified", "none"


def needs_llm(category: str, source: str, subject: str) -> bool:
    return category == "unclassified" and source == "none" and len(subject or "") > 120
