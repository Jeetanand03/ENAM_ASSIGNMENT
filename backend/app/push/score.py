"""Priority score 0–100 = category_weight + reaction_boost + user_boost. Every part is returned
so the UI can show *why* a card ranks where it does."""
from __future__ import annotations
import re
from .classify import SENIORITY, ORDER_WIN, DOWNGRADE, REAFFIRM, UPGRADE

CATEGORY_WEIGHT = {
    "results": 90, "M&A": 85, "management_change": 70, "litigation": 75, "fund_raise": 70, "pledging": 70,
    "credit_rating": 50, "capex": 55, "dividend": 50, "bonus_split": 50, "press_release": 40,
    "insider_trading": 35, "earnings_call": 30, "investor_meetings": 10, "postal_ballot": 10,
    "agm_egm": 10, "unclassified": 0,
}
TIER_MUST, TIER_LOOK = 75, 45


def category_weight(category: str, subject: str) -> tuple[int, str]:
    w = CATEGORY_WEIGHT.get(category, 0)
    why = category.replace("_", " ")
    s = subject or ""
    if category == "management_change":
        if re.search(r"re-?appoint|continuation|extension of (the )?term", s, re.I):
            w, why = 40, "re-appointment / term extension (continuity, not change)"
        elif SENIORITY.search(s):
            w, why = 80, "senior management change (CEO/CFO/MD level)"
        else:
            why = "director-level change"
    elif category == "results" and re.search(r"newspaper|publication|advertisement|intimation of (the )?board meeting|board meeting (to be held|scheduled)|prior intimation|(is|are) scheduled|will be held|to consider and approve|trading window|commence", s, re.I):
        w, why = 30, "results-related notice (ad / meeting intimation), not the numbers"
    elif category == "credit_rating":
        if DOWNGRADE.search(s): w, why = 75, "rating downgrade / negative outlook"
        elif UPGRADE.search(s): w, why = 60, "rating upgrade"
        elif REAFFIRM.search(s): w, why = 25, "rating reaffirmed"
    elif category == "press_release" and ORDER_WIN.search(s):
        w, why = 50, "order win"
    elif category == "earnings_call" and re.search(r"transcript", s, re.I):
        w, why = 35, "call transcript available"
    return w, why


def reaction_boost(move: dict | None, settings: dict) -> tuple[int, str | None]:
    """Up to +15 if the stock reacted on/after the filing day beyond the user's thresholds."""
    if not move:
        return 0, None
    pct, vr = move.get("pct_move"), move.get("vol_ratio")
    thr_p, thr_v = float(settings.get("price_move_pct", 4)), float(settings.get("volume_multiple", 2))
    b, parts = 0, []
    if pct is not None and abs(pct) >= thr_p:
        b += 10; parts.append(f"price {pct:+.1f}% on {move['date']}")
    if vr is not None and vr >= thr_v:
        b += 5; parts.append(f"volume {vr:.1f}× avg")
    return min(b, 15), ", ".join(parts) or None


def score(category: str, subject: str, move: dict | None, settings: dict) -> dict:
    cw, why = category_weight(category, subject)
    rb, rwhy = reaction_boost(move, settings)
    ub = 20 if category in (settings.get("starred_categories") or []) else 0
    total = max(0, min(100, cw + rb + ub))
    tier = "must" if total >= TIER_MUST else "look" if total >= TIER_LOOK else "routine"
    return {"score": total, "tier": tier,
            "parts": {"category": cw, "category_why": why, "reaction": rb, "reaction_why": rwhy,
                      "user": ub, "user_why": "starred category" if ub else None}}
