"""PDF download + per-page text extraction, cached as JSON next to the PDF.

Pages are kept separate so every downstream claim can cite (doc, page).
"""
from __future__ import annotations
import hashlib, json, logging, re
from pathlib import Path
from ..config import DOCS_DIR, SEED_DOCS_DIR, OFFLINE
from .http import client

log = logging.getLogger("finn.pdf")
MAX_PAGES = 400


def doc_id(url: str) -> str:
    return hashlib.sha1(url.encode()).hexdigest()[:12]


def _paths(symbol: str, url: str) -> tuple[Path, Path]:
    d = DOCS_DIR / symbol
    d.mkdir(parents=True, exist_ok=True)
    i = doc_id(url)
    return d / f"{i}.pdf", d / f"{i}.pages.json"


def download(symbol: str, url: str) -> Path | None:
    pdf, _ = _paths(symbol, url)
    if pdf.exists() and pdf.stat().st_size > 1000:
        return pdf
    if OFFLINE:
        return None
    ref = "https://www.bseindia.com/" if "bseindia" in url else "https://www.nseindia.com/"
    try:
        with client().stream("GET", url, headers={"Referer": ref}) as r:
            r.raise_for_status()
            with open(pdf, "wb") as f:
                for chunk in r.iter_bytes(1 << 16):
                    f.write(chunk)
        if pdf.stat().st_size < 1000 or pdf.read_bytes()[:5] != b"%PDF-":
            pdf.unlink(missing_ok=True)
            return None
        return pdf
    except Exception as e:
        log.warning("download failed %s: %s", url, e)
        pdf.unlink(missing_ok=True)
        return None


def _clean(t: str) -> str:
    t = t.replace(" ", " ")
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def pages(symbol: str, url: str, max_pages: int = MAX_PAGES) -> list[dict] | None:
    """[{page, text}] for the doc; extracted once and cached. Returns None if unavailable."""
    pdf, cache = _paths(symbol, url)
    seed = SEED_DOCS_DIR / symbol / cache.name
    if not cache.exists() and seed.exists():
        cache = seed
    if cache.exists():
        try:
            return json.loads(cache.read_text(encoding="utf-8"))
        except Exception:
            pass
    if download(symbol, url) is None:
        return None
    import pdfplumber
    out = []
    try:
        with pdfplumber.open(pdf) as doc:
            for i, p in enumerate(doc.pages[:max_pages], 1):
                try:
                    txt = p.extract_text() or ""
                except Exception:
                    txt = ""
                out.append({"page": i, "text": _clean(txt)})
    except Exception as e:
        log.warning("pdf parse failed %s: %s", pdf, e)
        return None
    cache.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    return out


def tables(symbol: str, url: str, first_n_pages: int = 12) -> list[dict]:
    """Tables from the first pages (results filings put the P&L up front)."""
    pdf, _ = _paths(symbol, url)
    if download(symbol, url) is None:
        return []
    import pdfplumber
    out = []
    with pdfplumber.open(pdf) as doc:
        for i, p in enumerate(doc.pages[:first_n_pages], 1):
            try:
                for t in p.extract_tables() or []:
                    out.append({"page": i, "rows": [[(c or "").strip() for c in row] for row in t]})
            except Exception:
                continue
    return out
