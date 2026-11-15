"""screener.in: standardised financial tables + links to annual reports / concall transcripts.

Tables are the company's own filed numbers in a standard layout (Rs crore). We parse:
quarters, profit-loss, balance-sheet, cash-flow, ratios, plus the Documents section.
"""
from __future__ import annotations
import logging, re
from bs4 import BeautifulSoup
from ..cache import fetch_with_fallback
from .http import get

log = logging.getLogger("finn.screener")
MONTHS = {m: i for i, m in enumerate(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}


def _num(s: str) -> float | None:
    s = s.replace(",", "").replace("%", "").strip()
    if s in ("", "-", "—"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _table(section) -> dict | None:
    if section is None:
        return None
    t = section.find("table")
    if t is None:
        return None
    heads = [th.get_text(" ", strip=True) for th in t.find("thead").find_all("th")][1:]
    rows: dict[str, list] = {}
    for tr in t.find("tbody").find_all("tr"):
        tds = tr.find_all("td")
        if not tds:
            continue
        label = re.sub(r"\s*\+\s*$", "", tds[0].get_text(" ", strip=True)).strip()
        if not label:
            continue
        rows[label] = [_num(td.get_text(strip=True)) for td in tds[1:]]
    return {"columns": heads, "rows": rows}


def _documents(soup) -> dict:
    out = {"annual_reports": [], "transcripts": [], "presentations": []}
    sec = soup.find(id="documents")
    if sec is None:
        return out
    ar = sec.find("div", class_=re.compile("annual-reports"))
    if ar:
        for a in ar.find_all("a", href=True):
            txt = a.get_text(" ", strip=True)
            m = re.search(r"(20\d\d)", txt)
            if m and a["href"].lower().endswith((".pdf", ".zip")) or (m and "AttachHis" in a["href"]):
                out["annual_reports"].append({"label": txt, "fy": int(m.group(1)), "url": a["href"]})
    cc = sec.find("div", class_=re.compile("concalls"))
    if cc:
        for li in cc.find_all("li"):
            date_div = li.find("div")
            when = date_div.get_text(strip=True) if date_div else ""
            m = re.match(r"([A-Z][a-z]{2}) (20\d\d)", when)
            ym = f"{m.group(2)}-{MONTHS[m.group(1)]:02d}" if m else None
            for a in li.find_all("a", href=True):
                label = a.get_text(strip=True)
                item = {"when": when, "ym": ym, "url": a["href"]}
                if label.lower().startswith("transcript"):
                    out["transcripts"].append(item)
                elif label.upper() == "PPT":
                    out["presentations"].append(item)
    # de-dup by url, keep order
    for k in out:
        seen, dd = set(), []
        for x in out[k]:
            if x["url"] not in seen:
                seen.add(x["url"]); dd.append(x)
        out[k] = dd
    return out


def _about(soup) -> dict:
    about = soup.select_one(".company-profile .about p")
    ratios = {}
    for li in soup.select("#top-ratios li"):
        name = li.find(class_="name"); val = li.find(class_="value")
        if name and val:
            ratios[name.get_text(strip=True)] = val.get_text(" ", strip=True)
    name = soup.select_one("h1")
    return {"name": name.get_text(strip=True) if name else None,
            "about": about.get_text(" ", strip=True) if about else None, "top_ratios": ratios}


def _live(symbol: str) -> dict:
    url = f"https://www.screener.in/company/{symbol}/consolidated/"
    r = get(url)
    soup = BeautifulSoup(r.text, "lxml")
    consolidated = True
    # Some companies (banks, small caps) only have standalone; screener redirects or shows a notice.
    if soup.find(id="quarters") is None:
        r = get(f"https://www.screener.in/company/{symbol}/"); soup = BeautifulSoup(r.text, "lxml"); consolidated = False
    data = {"symbol": symbol, "consolidated": consolidated, "source_url": str(r.url), **_about(soup)}
    for sec in ("quarters", "profit-loss", "balance-sheet", "cash-flow", "ratios"):
        data[sec.replace("-", "_")] = _table(soup.find(id=sec))
    data["documents"] = _documents(soup)
    if not data["quarters"]:
        raise RuntimeError(f"screener page for {symbol} had no quarterly table")
    return data


def load_screener(symbol: str, ttl: int = 24 * 3600) -> tuple[dict | None, str]:
    return fetch_with_fallback(f"screener_{symbol}", lambda: _live(symbol), ttl=ttl)
