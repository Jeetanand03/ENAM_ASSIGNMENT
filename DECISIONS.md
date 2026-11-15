# DECISIONS.md — trade-offs log (feeds the covering email)

Format: **Decision** — why — what it cost.

## Product
- **The feed is the product; chat is contextual.** The investor never faces a blank chatbot. Every card has "Dig in", which opens research scoped to that card's topic, and the ask bar lives inside a company. Cost: no free-form "ask about anything" screen.
- **One event = one card.** Reliance filed 5 results-related letters in a day; they fold into one card with "+4 related". Must-see dropped from 44 to 30 cards over 30 days with nothing lost.
- **Numbers in the feed, not behind a tap.** A results card shows the four YoY deltas inline; a management card shows who is in or out. The tap is for QoQ, margins and the source.
- **Every rank is explainable.** "Why here" shows category weight + price/volume reaction + starred boost. Re-appointments score as continuity (40), not change (80). Results ads and meeting notices score 30, not 90.
- **Simulated clock** instead of real push notifications. It lets a reviewer replay a results week and watch alerts fire. Real web-push needs a service worker and a push provider: left out.
- **Quiet windows don't greet you with an empty screen.** An empty 24h (weekend) falls back to 3 days and says so.

## Data layer
- **NSE corporate-announcements API as the filings feed; BSE dropped.** BSE's API returned 403 from this network even with browser headers. NSE worked without a cookie handshake, takes symbol + date range, and returns `voiceSummary`, NSE's own plain-English summary, which is reused instead of paying a model. Cost: BSE-only filings are missed.
- **screener.in standardised tables for numbers, PDFs for narrative.** The tables are the company's filed numbers in a standard layout; re-extracting revenue from 300-page annual reports with an LLM would be slower, costlier and less reliable. Transcripts are where guidance lives, so that is where extraction effort goes.
- **live → cache → committed snapshot for every call.** The demo runs with the network off. The serverless backend runs snapshot-first: a cold instance seeds sqlite from `data/snapshots/` in about 1s and only goes live for tickers it hasn't seen.
- **Extracted page text of demo documents is committed (`data/docs_seed`, 5.7 MB); raw PDFs are not.** Citations and the ask bar work on a fresh host without re-downloading 150 MB of PDFs.
- **Exchange time everywhere.** Filings are IST-stamped. The server (UTC) and the client (any timezone) both compute "now" in IST, so a reviewer abroad sees the same digest.

## Push
- **Rules-first classification.** NSE's category + subject + summary classify almost everything for free. The LLM only sees long subjects still unclassified.
- **Results first cut without a model.** With a key, the cheap model extracts the P&L from the filing PDF. Without one, the card uses the filed standardised quarterly table (same numbers) and says so. EBITDA is derived from PBT + interest + depreciation − other income when not reported, and labelled "derived".
- **No LinkedIn scraping.** Management bios come from a web-search API when a key is present and are labelled "public web, unverified".

## Pull
- **Numbers computed in code, never by the LLM.** The model only turns sentences into JSON (metric, range, unit, horizon, scope, quote, page). Python does the matching and the verdict.
- **Promised vs delivered is judged conservatively.**
  - Full-year growth guidance is judged on the full year once reported; before that the verdict says "so far".
  - Absolute revenue targets (Rs cr) are judged against the annual P&L.
  - Segment-level, gross-margin, EBIT-margin and unit-volume guidance is shown with its quote but not judged: consolidated tables can't settle it.
  - A wrong "missed" is worse than an honest "unclear". The first rules-only pass on an unseen ticker (PIIND) produced 6 confident "misses", all wrong. It compared gross margin with operating margin, counted past results as promises, and took a competitor statistic as guidance. The rules tier now judges only unambiguous sentences and says so.
- **Model-tier guidance for the demo set was produced offline.** No paid key was available. The guidance-structuring pass for the 4 demo companies was done once by Claude (the coding agent) with the same prompt and cached in `guidance_curated.json`, in the format the live provider returns. Any other ticker uses the rules tier until a key is set. Stated in the UI summary.
- **Two-phase research.** Numbers (fast, no PDFs) render first; transcripts are read in parallel. A never-seen ticker is fully researched in about 11s.

## Models and cost
- Cheap tier: Gemini 2.5 Flash, then Groq Llama 3.3 70B (both free tiers), then Claude Haiku. Strong tier: Claude Sonnet, falling back to Groq or Gemini. Only bull/bear and narrative use the strong tier.
- Cache key = sha256(prompt version + tier + system + prompt). Token usage and USD are logged per ticker to `cost_log`.
- Current deployment spend: $0. Every feature degrades to rules + snapshots without a key.

## Deliberately left out
- Real push notifications (service worker + push provider).
- Auth / multi-user. Settings are a single row; on serverless they last for the life of an instance.
- BSE feed; segment-level actuals (would need parsing segment notes from results PDFs to judge segment guidance).
- Annual-report deep reads (contingent liabilities, RPTs, auditor qualifications). The documents are fetched and searchable through the ask bar, but there is no dedicated module.

## Next
1. Segment-level actuals from results PDFs, so segment guidance (most of what management says) can be judged.
2. A "since you last looked" digest window, plus web-push for starred categories.
3. A cron refresh (Vercel cron → `/api/admin/ingest`) writing to a persistent store instead of per-instance sqlite.
4. Peer view: the same promised-vs-delivered score across a sector.
