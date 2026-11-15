"""FINN API. Every route is read-mostly and backed by cache -> snapshot so it answers even offline."""
from __future__ import annotations
import logging, threading
from datetime import datetime
from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from . import config, db, llm, settings as settings_mod
from .sources import prices
from .push import digest, alerts, enrich
from .pull import research

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("finn")

app = FastAPI(title="FINN", version="0.1")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def _now() -> str:
    """Exchange time (IST), naive — filings are timestamped in IST and the server may run in UTC."""
    from datetime import timedelta, timezone
    return datetime.now(timezone(timedelta(hours=5, minutes=30))).replace(microsecond=0, tzinfo=None).isoformat()


def _bootstrap():
    """Make sure prices + announcements exist (from snapshots if offline). Runs in a thread at startup."""
    try:
        for s in config.PORTFOLIO_SYMBOLS:
            prices.load_prices(s)
        if not db.one("SELECT 1 FROM announcements LIMIT 1") or _stale():
            digest.ingest(use_llm=True)
        log.info("bootstrap done")
    except Exception as e:
        log.exception("bootstrap failed: %s", e)


def _stale() -> bool:
    last = db.kv_get("last_ingest")
    return not last or (datetime.fromisoformat(_now()) - datetime.fromisoformat(last)).total_seconds() > 1800


_boot_lock = threading.Lock()
_booted = False


def ensure_data():
    """Serverless-safe bootstrap: on a cold instance, seed sqlite from committed snapshots (no network) before answering."""
    global _booted
    if _booted:
        return
    with _boot_lock:
        if _booted:
            return
        db.con()
        if config.SNAPSHOT_FIRST:
            for s in config.PORTFOLIO_SYMBOLS:
                prices.load_prices(s)
            if not db.one("SELECT 1 FROM announcements LIMIT 1"):
                digest.ingest(use_llm=False)
        _booted = True


@app.middleware("http")
async def _ensure(request, call_next):
    if request.url.path.startswith("/api/") and request.url.path != "/api/health":
        import anyio
        await anyio.to_thread.run_sync(ensure_data)
    return await call_next(request)


@app.on_event("startup")
def _startup():
    db.con()
    if not config.SNAPSHOT_FIRST:  # long-running host: refresh live in the background
        threading.Thread(target=_bootstrap, daemon=True).start()


@app.get("/api/health")
def health():
    return {"ok": True, "time": _now(), "offline": config.OFFLINE, "llm": llm.available(),
            "announcements": (db.one("SELECT COUNT(*) n FROM announcements") or {}).get("n", 0),
            "last_ingest": db.kv_get("last_ingest")}


@app.get("/api/portfolio")
def portfolio(as_of: str | None = None):
    out = []
    for c in config.PORTFOLIO:
        snap = prices.snapshot(c["symbol"], as_of)
        n = db.one("SELECT COUNT(*) n, MAX(score) mx FROM announcements WHERE symbol=? AND ts>=date(?, '-7 day')", (c["symbol"], (as_of or _now())[:10])) or {}
        out.append({**c, "price": snap, "filings_7d": n.get("n", 0), "top_score_7d": n.get("mx")})
    return {"as_of": as_of or _now(), "companies": out}


@app.get("/api/digest")
def get_digest(window: str = "24h", as_of: str | None = None, frm: str | None = Query(None, alias="from"), to: str | None = None, symbol: str | None = None):
    return digest.digest(window, as_of or _now(), frm, to, symbol)


@app.get("/api/announcements/{ann_id}")
def announcement(ann_id: str):
    c = digest.card(ann_id)
    if not c:
        raise HTTPException(404, "unknown announcement")
    return c


@app.get("/api/announcements/{ann_id}/enrich")
def announcement_enrich(ann_id: str, force: bool = False):
    c = digest.card(ann_id)
    if not c:
        raise HTTPException(404, "unknown announcement")
    try:
        return enrich.enrich(c, force=force) or {"kind": c["category"], "ok": False, "reason": "no enrichment for this type"}
    except Exception as e:
        log.exception("enrich failed")
        return {"kind": c["category"], "ok": False, "reason": str(e)[:200]}


@app.get("/api/alerts")
def get_alerts(as_of: str | None = None, days: int = 10):
    s = settings_mod.get()
    return {"as_of": as_of or _now(), "settings": s, "alerts": alerts.evaluate(s, as_of or _now(), days)}


class SettingsPatch(BaseModel):
    volume_multiple: float | None = None
    price_move_pct: float | None = None
    starred_categories: list[str] | None = None
    digest_window: str | None = None


@app.get("/api/settings")
def get_settings():
    return settings_mod.get()


@app.put("/api/settings")
def put_settings(patch: SettingsPatch):
    s = settings_mod.update({k: v for k, v in patch.model_dump().items() if v is not None})
    digest.rescore(s)
    return s


@app.get("/api/prices/{symbol}")
def get_prices(symbol: str, as_of: str | None = None):
    symbol = symbol.upper()
    rows = prices.enrich_moves(prices.series(symbol))
    if not rows:
        prices.load_prices(symbol); rows = prices.enrich_moves(prices.series(symbol))
    if as_of:
        rows = [r for r in rows if r["date"] <= as_of[:10]]
    return {"symbol": symbol, "bars": rows[-60:], "snapshot": prices.snapshot(symbol, as_of)}


@app.get("/api/company/{symbol}")
def company(symbol: str, as_of: str | None = None):
    symbol = symbol.upper()
    return {"symbol": symbol, "meta": config.COMPANY_BY_SYMBOL.get(symbol), "price": prices.snapshot(symbol, as_of),
            "feed": [c for c in digest.company_feed(symbol) if not as_of or c["ts"] <= as_of]}


@app.get("/api/research/{symbol}")
def get_research(symbol: str, refresh: bool = False, quick: bool = False):
    try:
        return research.build(symbol, refresh=refresh, quick=quick)
    except Exception as e:
        log.exception("research failed")
        return {"symbol": symbol.upper(), "ok": False, "error": f"Research failed: {str(e)[:160]}"}


@app.get("/api/research/{symbol}/ask")
def ask(symbol: str, q: str, topic: str | None = None):
    return research.ask(symbol, q, topic)


@app.post("/api/admin/ingest")
def admin_ingest(bg: BackgroundTasks):
    bg.add_task(digest.ingest, None, None, True)
    return {"started": True}


@app.get("/api/cost")
def cost():
    return llm.cost_summary()
