# DECISIONS.md — trade-offs log (feeds the covering email)

Format: **Decision** — why — what it cost.

## Data layer
- **NSE corporate-announcements API as the primary filings feed, BSE dropped.** The BSE `AnnGetData` API returned 403 from this network even with browser headers; NSE's `/api/corporate-announcements` worked with a plain cookie-less request, accepts `symbol` + `from_date/to_date`, and returns a `desc` (raw category) plus `voiceSummary` (NSE's own one-paragraph summary). Cost: one exchange instead of two; BSE-only filings are missed. Gain: zero LLM spend on summaries for most filings — NSE's summary is reused where present.
- **screener.in standardised tables for the numeric fundamentals (quarters, P&L, balance sheet, cash flow), PDFs only for narrative.** Standardised tables are already clean numbers; running an LLM over 300-page annual reports to re-extract revenue would be slower, costlier and less reliable. PDFs (transcripts) are where guidance and tone live, so that is where the LLM goes. Primary-source discipline is preserved: screener's tables are the company's own filed numbers, restated in a standard layout.
- **Snapshots in `data/snapshots/` are committed and are the fallback for every external call.** The demo must run on a phone with the API cold or offline. Every fetcher is `live → cache → snapshot`.

## Push
- **Rules-first classification, LLM last.** NSE `desc` + subject keywords classify ~95% of filings for free. The LLM sees only long, still-unclassified subjects.
- **Priority score is transparent.** `category_weight + reaction_boost + user_boost`, each component returned to the UI so the card can say "why this ranks here".
- **No LinkedIn scraping.** Management-change bios come from a web-search API (when a key is present) and are labelled "public web, unverified".

## Pull
- **Numbers computed in code, never by the LLM.** The LLM extracts raw figures/quotes into JSON; Python computes QoQ/YoY/margins/conversion.
- **Promised-vs-delivered is the showpiece.** Guidance quotes are extracted per transcript with a page citation; actuals come from the next quarters' standardised numbers; the verdict is rule-based (met/partially/missed/unclear) with the quote and the number side by side.

## Models and cost
- Cheap model (Gemini Flash / Claude Haiku) for extraction + classification; stronger model (Claude Sonnet) only for verdict narration and bull/bear.
- Cache key = sha256(document text + prompt version). Token usage is logged per ticker to `cost_log`.
- With no API key configured, the app runs entirely from cached LLM outputs in snapshots — the demo never depends on a live model.

## Deliberately left out
- Real push notifications (would need a service worker + a push provider). Alerts are evaluated server-side and surfaced in-app; the "as-of" clock makes them demoable.
- Auth / multi-user. Settings are a single-user row.
- BSE feed, voice input (stretch).
