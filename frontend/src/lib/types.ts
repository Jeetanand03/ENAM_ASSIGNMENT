export type Settings = { volume_multiple: number; price_move_pct: number; starred_categories: string[]; digest_window: string };

export type Why = { category: number; category_why: string; reaction: number; reaction_why: string | null; user: number; user_why: string | null };

export type Card = {
  id: string; symbol: string; name: string; sector?: string; ts: string; category: string; category_source: string;
  headline: string; subject: string; summary: string | null; pdf_url: string | null; score: number; tier: "must" | "look" | "routine";
  why: Why; enrich: Enrich | null; related?: { id: string; ts: string; headline: string; pdf_url: string | null }[];
};

export type Digest = {
  window: string; from: string; to: string; as_of: string; total: number; raw_total?: number;
  counts: { must: number; look: number; routine: number }; by_category: Record<string, number>;
  tiers: { must: Card[]; look: Card[]; routine: Card[] }; last_ingest: string | null;
};

export type ResultsRow = { key: string; label: string; current: number | null; previous: number | null; year_ago: number | null; qoq: number | null; yoy: number | null; derived: boolean; margin: number | null; margin_prev: number | null; margin_ya: number | null };
export type Enrich =
  | { kind: "results"; ok: true; unit: string; basis: string; table: { rows: ResultsRow[]; labels: { current: string; previous: string; year_ago: string } }; takeaway: string; notes: string | null; source: { kind: string; url?: string; page?: number } | null; method: string }
  | { kind: "management_change"; ok: boolean; changes: { person: string; role: string | null; direction: "in" | "out" | "reappointed"; effective: string | null; reason: string | null; bio?: { text: string; label: string; sources: { title: string; url: string }[] } }[]; method: string }
  | { kind: string; ok: false; reason: string };

export type PriceSnap = { symbol: string; date: string; close: number; pct_move: number | null; volume: number; vol_ratio: number | null; avg_volume: number | null; spark: number[] };
export type Company = { symbol: string; name: string; sector: string; size: string; price: PriceSnap | null; filings_7d: number; top_score_7d: number | null };

export type Alert = {
  id: string; type: "market" | "filing"; symbol: string; name: string; ts: string; headline: string;
  close?: number; pct_move?: number | null; vol_ratio?: number | null; hits?: { kind: string; value: number; threshold: number; text: string }[];
  ann_id?: string; category?: string; score?: number; tier?: string; pdf_url?: string | null; with_market_move?: boolean;
};

export type Quarter = { col: string; label: string; revenue: number | null; ebitda: number | null; opm: number | null; pbt: number | null; pat: number | null; rev_yoy: number | null; pat_yoy: number | null; rev_qoq: number | null };
export type GuidanceItem = { metric: string; statement: string | null; value_low: number | null; value_high: number | null; unit: string | null; value_text?: string | null; basis?: string; scope?: string; quote: string; page: number; speaker?: string | null; horizon: string | null };
export type Transcript = { when: string; ym: string | null; url: string; doc: string; items: GuidanceItem[]; method: string; candidates: number };
export type Verdict = { metric: string; promised: string; range: [number | null, number | null]; unit: string | null; horizon: string | null; quote: string; page: number; judged_on: { label: string; value: number }[]; verdict: "met" | "partially" | "missed" | "unclear"; delivered: number | null; measure?: string; why?: string; gap?: number; partial?: boolean; given_in: string; doc: string; url: string };
export type Cited = { text: string; cite: string };

export type Research = {
  symbol: string; ok: boolean; partial?: boolean; error?: string; name?: string; data_source?: string;
  modules?: {
    business: { name: string; about: string | null; basis: string; source: { doc: string; url: string } };
    snapshot: { latest_quarter: Quarter; ttm: { revenue: number | null; ebitda: number | null; pat: number | null; opm: number | null }; ratios: Record<string, string | null>; basis: string; source: { doc: string; url: string; section: string } };
    quarters: Quarter[];
    trajectory: { years: { fy: string; revenue: number | null; ebitda: number | null; opm: number | null; pat: number | null; eps: number | null; rev_growth: number | null; pat_growth: number | null }[]; cagr: { revenue: number | null; pat: number | null }; signals: string[]; source: { doc: string; url: string; section: string } };
    balance_sheet: { years: { fy: string; net_worth: number | null; debt: number | null; de: number | null; fixed_assets: number | null; cwip: number | null; investments: number | null; total_assets: number | null; debtor_days: number | null; inventory_days: number | null; payable_days: number | null; ccc: number | null; wc_days: number | null; roce: number | null }[]; signals: string[]; source: { doc: string; url: string; section: string } };
    cash: { years: { fy: string; cfo: number | null; pat: number | null; ebitda: number | null; fcf: number | null; cfi: number | null; cfo_to_pat: number | null; cfo_to_ebitda: number | null }[]; conversion: number | null; signals: string[]; source: { doc: string; url: string; section: string } };
    guidance?: Transcript[];
    promised_vs_delivered?: { rows: Verdict[]; counts: Record<string, number>; credibility: number | null; summary: string };
    bull_bear?: { bull: Cited[]; bear: Cited[]; method: string };
    narrative?: { agree: Cited[]; diverge: Cited[]; method: string };
  };
  documents?: { transcripts: { when: string; ym: string | null; url: string }[]; annual_reports: { label: string; fy: number; url: string }[] };
  cost?: { calls: number; usd: number; in_tokens: number; out_tokens: number };
};

export type Ask = { answer: string; citations: { doc: string; page: number; url: string; snippet: string }[]; method?: string };
