"""Refresh demo data and bake static fallbacks for the frontend.

1. Live-refresh prices + announcements for the portfolio, re-enrich, rebuild research for the demo set
   (this rewrites data/snapshots/*, which the serverless backend serves first).
2. Call every API view the UI needs and write it to frontend/public/fallback/<key>.json, so the deployed
   app still renders if the API host is cold or down.

Run from backend/:  PYTHONPATH=. python scripts/export_fallback.py [--no-refresh]
"""
import json, sys, logging
from pathlib import Path
logging.basicConfig(level=logging.WARNING)
from fastapi.testclient import TestClient
from app import config
from app.main import app
from app.sources import prices
from app.push import digest
from app.pull import research

OUT = config.REPO_DIR / "frontend" / "public" / "fallback"
OUT.mkdir(parents=True, exist_ok=True)
EXTRA_RESEARCH = ["PIIND"]

if "--no-refresh" not in sys.argv:
    for s in config.PORTFOLIO_SYMBOLS:
        prices.load_prices(s, ttl=0)
    print("ingest", digest.ingest(use_llm=True))
    for s in config.RESEARCH_DEMO + EXTRA_RESEARCH:
        r = research.build(s, refresh=True)
        print("research", s, r.get("ok"), r.get("modules", {}).get("promised_vs_delivered", {}).get("summary", "")[:80])

from app import db
from app.cache import write_snapshot
write_snapshot("enrich_cache", {r["id"]: json.loads(r["enrich"]) for r in db.rows("SELECT id, enrich FROM announcements WHERE enrich IS NOT NULL")})

c = TestClient(app)
def save(key, path):
    r = c.get(path); r.raise_for_status()
    (OUT / f"{key}.json").write_text(json.dumps(r.json(), ensure_ascii=False), encoding="utf-8")

save("health", "/api/health"); save("settings", "/api/settings"); save("cost", "/api/cost")
save("portfolio", "/api/portfolio"); save("alerts", "/api/alerts?days=30")
for w in ("24h", "3d", "7d", "30d"):
    save(f"digest_{w}", f"/api/digest?window={w}")
for s in sorted(set(config.PORTFOLIO_SYMBOLS + config.RESEARCH_DEMO + EXTRA_RESEARCH)):
    save(f"company_{s}", f"/api/company/{s}")
for s in config.RESEARCH_DEMO + EXTRA_RESEARCH:
    save(f"research_{s}", f"/api/research/{s}")
print("wrote", len(list(OUT.glob("*.json"))), "fallback files to", OUT)
