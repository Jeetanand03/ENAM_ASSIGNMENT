# FINN — Financial Investment Agent

A mobile-first agent that shows an investor only what matters.

**Live app (open on a phone):** https://finn-app-alpha.vercel.app
**API:** https://finn-api-sooty.vercel.app/api/health

## What it does

**Push: the feed is the product.**
- **Windowed digest** of every NSE filing across a 20-stock portfolio (24h default; 3d / 7d / 30d). Filings are ranked into *Must see*, *Worth a look* and a collapsed *Routine* tier. If 24h is quiet (weekend), it says so and shows the last 3 days.
- **One event, one card.** Related filings for the same company and category fold into the strongest card ("+4 related").
- **Results cards** show Revenue / EBITDA / PBT / PAT YoY in the feed itself, and QoQ + margins on tap. Every delta is computed in code.
- **Management cards** say who is in, who is out, role and effective date, read from the filing letter.
- **"Why here"** on every card: category weight + price/volume reaction + your starred types = score.
- **Alerts** for |1-day move| ≥ X%, volume ≥ N× 20-day average, and filings in starred categories, all set with sliders. A filing that coincided with a stock move is flagged.
- **Simulated clock.** Rewind the whole app to any moment ("Results week") to see what it would have pushed then.

**Pull: research on any NSE ticker, from primary sources only.**
- **Promised vs delivered** (the showpiece). Guidance is quoted from the last 5 concall transcripts with a page citation, then matched to what was filed afterwards and judged *met / partially / missed* in code. A credibility score summarises the record. Segment-level, gross-margin or absolute-unit guidance is shown but never judged against consolidated numbers.
- Financial snapshot, 6-year trajectory, cash quality (CFO/PAT, FCF), balance sheet (D/E, cash conversion cycle, CWIP), narrative vs numbers, bull vs bear. Each claim carries a source chip.
- **Ask bar** answers follow-ups only from the company's transcripts and annual report, with page-cited passages. Voice input uses the Web Speech API.
- Numbers render first (about 2s) while transcripts are read (about 10s for a ticker never seen before).

## Architecture

```
frontend/  Next.js 14 PWA (Vercel)   ── every GET falls back to /public/fallback/*.json
api/       Vercel Python entry        ── wraps backend/app (FastAPI)
backend/app
  sources/   NSE announcements · yfinance EOD · screener tables + doc links · PDF -> pages
  push/      classify (rules) · score · digest (fold) · alerts · enrich (results / mgmt)
  pull/      fundamentals (code) · guidance (rules → LLM) · verdict (code) · research · ask
  llm.py     tiered router (cheap / strong) + sha256 cache + cost_log
data/snapshots/   committed JSON: the fallback for every external call
data/docs_seed/   committed per-page text of the demo set's transcripts / annual reports
```

Every external call goes **live → sqlite cache → committed snapshot**. A cold serverless instance seeds itself from snapshots in about 1s.

## Models and cost

| Step | Default | How |
|---|---|---|
| Filing classification | rules (NSE category + keywords) | LLM only for long subjects still unclassified |
| One-line summaries | NSE's own `voiceSummary` | no model call |
| Results numbers | filed standardised tables | LLM table extraction from the PDF when a key is set |
| Guidance extraction | rules pick candidate sentences | cheap model (Gemini Flash / Groq Llama 3.3 70B / Haiku) structures them |
| Verdicts, QoQ/YoY, margins | Python | never the LLM |
| Bull/bear, narrative | rules from computed signals | strong model (Sonnet) when a key is set |

**Cost to analyse a company in this deployment: $0.00.** No paid key is configured. For the four demo companies, the guidance-structuring pass was done once offline by Claude, the coding agent, using the same prompt, and is cached in `data/snapshots/guidance_curated.json`. With a key, the per-ticker spend is logged to `cost_log` and shown at the bottom of each research page (`/api/cost`).

## Run locally

```bash
cd backend && python -m venv .venv && .venv/Scripts/pip install -r requirements.txt
cp ../.env.example .env            # optional keys
python -m uvicorn app.main:app --port 8000
cd ../frontend && npm i && NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

Refresh data and the static fallbacks: `cd backend && PYTHONPATH=. python scripts/export_fallback.py`

## Portfolio and demo set

Portfolio (20): RELIANCE, HDFCBANK, TCS, INFY, ITC, BAJFINANCE, SUNPHARMA, MARUTI, HAL, TRENT, ETERNAL, APOLLOHOSP, DIXON, PERSISTENT, POLYCAB, VBL, IRCTC, KAYNES, TANLA, RATEGAIN.
Research demo: DIXON, PERSISTENT, VBL, KAYNES (plus PIIND as an unseen-ticker example). Type any NSE symbol in Research.

See `DECISIONS.md` for trade-offs and what was left out.
