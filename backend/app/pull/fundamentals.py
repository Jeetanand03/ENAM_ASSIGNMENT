"""Numeric research modules computed in code from screener's standardised tables (filed numbers).

Modules: financial snapshot, trajectory (5y), balance sheet, cash quality. No LLM anywhere here.
Every number carries a `source` so the UI can cite the table it came from.
"""
from __future__ import annotations
import re
from ..sources import screener


def _col_label(col: str) -> str:
    m = re.match(r"([A-Z][a-z]{2}) (20\d\d)", col)
    if not m:
        return col
    mon, yr = m.group(1), int(m.group(2))
    q = {"Jun": "Q1", "Sep": "Q2", "Dec": "Q3", "Mar": "Q4"}.get(mon, mon)
    return f"{q} FY{str(yr + 1 if mon != 'Mar' else yr)[2:]}"


def _fy(col: str) -> str:
    """'Mar 2026' -> FY26; a half-year column like 'Sep 2026' -> H1 FY27."""
    m = re.match(r"([A-Z][a-z]{2}) (20\d\d)", col)
    if not m:
        return col
    mon, yr = m.group(1), int(m.group(2))
    if mon == "Mar":
        return f"FY{str(yr)[2:]}"
    return f"{'H1' if mon == 'Sep' else mon} FY{str(yr + 1)[2:]}"


def _pct(a, b):
    if a is None or b in (None, 0):
        return None
    return round((a / b - 1) * 100, 1)


def _cagr(first, last, years):
    if not first or not last or first <= 0 or last <= 0 or years <= 0:
        return None
    return round(((last / first) ** (1 / years) - 1) * 100, 1)


def _row(t: dict | None, *names) -> list:
    if not t:
        return []
    for n in names:
        if n in t["rows"]:
            return t["rows"][n]
    return []


def quarterly_series(sc: dict) -> list[dict]:
    q = sc.get("quarters")
    if not q:
        return []
    cols = q["columns"]
    sales, op, opm, pbt, pat = _row(q, "Sales", "Revenue"), _row(q, "Operating Profit", "Financing Profit"), _row(q, "OPM %", "Financing Margin %"), _row(q, "Profit before tax"), _row(q, "Net Profit")
    out = []
    for i, c in enumerate(cols):
        out.append({"col": c, "label": _col_label(c), "revenue": sales[i] if i < len(sales) else None,
                    "ebitda": op[i] if i < len(op) else None, "opm": opm[i] if i < len(opm) else None,
                    "pbt": pbt[i] if i < len(pbt) else None, "pat": pat[i] if i < len(pat) else None})
    for i, r in enumerate(out):
        r["rev_yoy"] = _pct(r["revenue"], out[i - 4]["revenue"]) if i >= 4 else None
        r["pat_yoy"] = _pct(r["pat"], out[i - 4]["pat"]) if i >= 4 else None
        r["rev_qoq"] = _pct(r["revenue"], out[i - 1]["revenue"]) if i >= 1 else None
    return out


def financial_snapshot(sc: dict) -> dict:
    qs = quarterly_series(sc)
    last = qs[-1] if qs else {}
    pl = sc.get("profit_loss"); cols = pl["columns"] if pl else []
    ttm_i = cols.index("TTM") if "TTM" in cols else (len(cols) - 1 if cols else None)
    ttm = {}
    if ttm_i is not None:
        for k, names in {"revenue": ("Sales", "Revenue"), "ebitda": ("Operating Profit", "Financing Profit"), "pat": ("Net Profit",), "opm": ("OPM %", "Financing Margin %")}.items():
            r = _row(pl, *names); ttm[k] = r[ttm_i] if ttm_i < len(r) else None
    tr = sc.get("top_ratios") or {}
    return {"latest_quarter": last, "ttm": ttm, "ratios": {k: tr.get(k) for k in ("Market Cap", "Stock P/E", "ROCE", "ROE", "Dividend Yield", "Book Value", "Current Price", "High / Low")},
            "basis": "consolidated" if sc.get("consolidated") else "standalone",
            "source": {"doc": "screener standardised tables", "url": sc.get("source_url"), "section": "quarters / profit-loss"}}


def trajectory(sc: dict, years: int = 6) -> dict:
    pl = sc.get("profit_loss")
    if not pl:
        return {"years": []}
    cols = [c for c in pl["columns"] if c != "TTM"][-years:]
    idx = [pl["columns"].index(c) for c in cols]
    g = lambda *n: [(_row(pl, *n) or [None] * len(pl["columns"]))[i] for i in idx]
    rev, ebitda, opm, pat, eps = g("Sales", "Revenue"), g("Operating Profit", "Financing Profit"), g("OPM %", "Financing Margin %"), g("Net Profit"), g("EPS in Rs")
    yrs = [{"fy": _fy(c), "revenue": rev[i], "ebitda": ebitda[i], "opm": opm[i], "pat": pat[i], "eps": eps[i],
            "rev_growth": _pct(rev[i], rev[i - 1]) if i else None, "pat_growth": _pct(pat[i], pat[i - 1]) if i else None} for i, c in enumerate(cols)]
    n = len(cols) - 1
    signals = []
    if n >= 2:
        rc, pc = _cagr(rev[0], rev[-1], n), _cagr(pat[0], pat[-1], n)
        if rc is not None: signals.append(f"Revenue CAGR {rc:+.0f}% over {n}y")
        if pc is not None: signals.append(f"PAT CAGR {pc:+.0f}% over {n}y")
        if opm[0] is not None and opm[-1] is not None:
            d = opm[-1] - opm[0]
            signals.append(f"Operating margin {'expanded' if d > 0.3 else 'compressed' if d < -0.3 else 'flat'} ({opm[0]:.1f}% → {opm[-1]:.1f}%)")
        if rc is not None and pc is not None:
            signals.append("Profit growing faster than sales — leverage in the model" if pc > rc + 3 else "Profit lagging sales — margin pressure" if pc < rc - 3 else "Profit tracking sales")
    return {"years": yrs, "cagr": {"revenue": _cagr(rev[0], rev[-1], n) if n else None, "pat": _cagr(pat[0], pat[-1], n) if n else None},
            "signals": signals, "source": {"doc": "screener standardised tables", "url": sc.get("source_url"), "section": "profit-loss"}}


def balance_sheet(sc: dict, years: int = 5) -> dict:
    bs, ra = sc.get("balance_sheet"), sc.get("ratios")
    if not bs:
        return {"years": []}
    cols = bs["columns"][-years:]; idx = [bs["columns"].index(c) for c in cols]
    g = lambda t, *n: [(_row(t, *n) or [None] * len(t["columns"]))[i] if t else None for i in idx]
    eq, res, debt, fa, cwip, inv, tot = g(bs, "Equity Capital"), g(bs, "Reserves"), g(bs, "Borrowings"), g(bs, "Fixed Assets"), g(bs, "CWIP"), g(bs, "Investments"), g(bs, "Total Assets")
    ridx = [ra["columns"].index(c) if ra and c in ra["columns"] else None for c in cols]
    rg = lambda *n: [((_row(ra, *n) or [])[i] if i is not None and i < len(_row(ra, *n) or []) else None) for i in ridx]
    dd, ind, dp, ccc, wcd, roce = rg("Debtor Days"), rg("Inventory Days"), rg("Days Payable"), rg("Cash Conversion Cycle"), rg("Working Capital Days"), rg("ROCE %")
    yrs = []
    for i, c in enumerate(cols):
        networth = (eq[i] or 0) + (res[i] or 0) if eq[i] is not None else None
        yrs.append({"fy": _fy(c), "net_worth": networth, "debt": debt[i], "de": round(debt[i] / networth, 2) if debt[i] is not None and networth else None,
                    "fixed_assets": fa[i], "cwip": cwip[i], "investments": inv[i], "total_assets": tot[i],
                    "debtor_days": dd[i], "inventory_days": ind[i], "payable_days": dp[i], "ccc": ccc[i], "wc_days": wcd[i], "roce": roce[i]})
    signals = []
    if len(yrs) >= 2:
        a, b = yrs[0], yrs[-1]
        if a["de"] is not None and b["de"] is not None:
            signals.append(f"Debt/equity {a['de']:.2f} → {b['de']:.2f}")
        if a["ccc"] is not None and b["ccc"] is not None:
            d = b["ccc"] - a["ccc"]
            signals.append(f"Cash conversion cycle {'lengthened' if d > 0 else 'shortened'} by {abs(d):.0f} days ({a['ccc']:.0f} → {b['ccc']:.0f})")
        if b["cwip"] and b["fixed_assets"]:
            signals.append(f"CWIP is {b['cwip'] / b['fixed_assets'] * 100:.0f}% of fixed assets — capex in flight" if b["cwip"] / b["fixed_assets"] > 0.15 else "Little capex in flight (low CWIP)")
    return {"years": yrs, "signals": signals, "source": {"doc": "screener standardised tables", "url": sc.get("source_url"), "section": "balance-sheet / ratios"}}


def cash_quality(sc: dict, years: int = 5) -> dict:
    cf, pl = sc.get("cash_flow"), sc.get("profit_loss")
    if not cf or not pl:
        return {"years": []}
    cols = cf["columns"][-years:]; idx = [cf["columns"].index(c) for c in cols]
    cfo = [(_row(cf, "Cash from Operating Activity") or [None] * 99)[i] for i in idx]
    fcf_row = _row(cf, "Free Cash Flow")
    fcf = [fcf_row[i] if fcf_row and i < len(fcf_row) else None for i in idx]
    cfi = [(_row(cf, "Cash from Investing Activity") or [None] * 99)[i] for i in idx]
    pidx = [pl["columns"].index(c) if c in pl["columns"] else None for c in cols]
    pat = [(_row(pl, "Net Profit")[i] if i is not None else None) for i in pidx]
    ebitda = [(_row(pl, "Operating Profit", "Financing Profit")[i] if i is not None else None) for i in pidx]
    yrs = [{"fy": _fy(c), "cfo": cfo[i], "pat": pat[i], "ebitda": ebitda[i], "fcf": fcf[i], "cfi": cfi[i],
            "cfo_to_pat": round(cfo[i] / pat[i], 2) if cfo[i] is not None and pat[i] else None,
            "cfo_to_ebitda": round(cfo[i] / ebitda[i], 2) if cfo[i] is not None and ebitda[i] else None} for i, c in enumerate(cols)]
    tot_cfo = sum(x for x in cfo if x is not None); tot_pat = sum(x for x in pat if x is not None)
    conv = round(tot_cfo / tot_pat, 2) if tot_pat else None
    signals = []
    if conv is not None:
        signals.append(f"{len(cols)}-year CFO/PAT {conv:.2f}× — " + ("profits convert to cash" if conv >= 0.8 else "cash lags reported profit — check working capital"))
    neg = [y["fy"] for y in yrs if y["fcf"] is not None and y["fcf"] < 0]
    if neg:
        signals.append(f"Negative FCF in {', '.join(neg)}" + (" — heavy investment phase" if len(neg) >= 2 else ""))
    elif any(y["fcf"] is not None for y in yrs):
        signals.append("FCF positive every year shown")
    return {"years": yrs, "conversion": conv, "signals": signals, "source": {"doc": "screener standardised tables", "url": sc.get("source_url"), "section": "cash-flow"}}


def business_snapshot(sc: dict) -> dict:
    return {"name": sc.get("name"), "about": sc.get("about"), "basis": "consolidated" if sc.get("consolidated") else "standalone",
            "source": {"doc": "screener company profile (from company filings)", "url": sc.get("source_url")}}


def all_numeric(symbol: str) -> dict | None:
    sc, src = screener.load_screener(symbol)
    if not sc:
        return None
    return {"symbol": symbol, "name": sc.get("name"), "data_source": src, "business": business_snapshot(sc),
            "snapshot": financial_snapshot(sc), "quarters": quarterly_series(sc)[-8:], "trajectory": trajectory(sc),
            "balance_sheet": balance_sheet(sc), "cash": cash_quality(sc), "documents": sc.get("documents")}
