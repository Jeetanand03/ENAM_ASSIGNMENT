export const fmtNum = (v: number | null | undefined, d = 0) =>
  v === null || v === undefined || Number.isNaN(v) ? "—" : v.toLocaleString("en-IN", { maximumFractionDigits: d, minimumFractionDigits: d });

export const fmtCr = (v: number | null | undefined) => {
  if (v === null || v === undefined) return "—";
  const a = Math.abs(v);
  if (a >= 1e5) return `${(v / 1e5).toLocaleString("en-IN", { maximumFractionDigits: 2 })} L cr`;
  if (a >= 1000) return `${v.toLocaleString("en-IN", { maximumFractionDigits: 0 })} cr`;
  return `${v.toLocaleString("en-IN", { maximumFractionDigits: 1 })} cr`;
};

export const fmtPct = (v: number | null | undefined, d = 1, sign = true) =>
  v === null || v === undefined || Number.isNaN(v) ? "—" : `${sign && v > 0 ? "+" : ""}${v.toFixed(d)}%`;

export const fmtX = (v: number | null | undefined) => (v === null || v === undefined ? "—" : `${v.toFixed(1)}×`);

export const fmtVol = (v: number | null | undefined) => {
  if (v === null || v === undefined) return "—";
  if (v >= 1e7) return `${(v / 1e7).toFixed(1)} cr`;
  if (v >= 1e5) return `${(v / 1e5).toFixed(1)} L`;
  if (v >= 1e3) return `${(v / 1e3).toFixed(0)}k`;
  return `${v}`;
};

export function timeAgo(iso: string, now: Date = new Date()): string {
  const t = new Date(iso).getTime();
  const s = Math.max(0, (now.getTime() - t) / 1000);
  if (s < 3600) return `${Math.max(1, Math.round(s / 60))}m`;
  if (s < 86400) return `${Math.round(s / 3600)}h`;
  if (s < 86400 * 7) return `${Math.round(s / 86400)}d`;
  return new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short" });
}

export const fmtDate = (iso: string | null | undefined, withTime = false) => {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "short" }) + (withTime ? ` ${d.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", hour12: false })}` : "");
};

export const CATEGORY_LABEL: Record<string, string> = {
  results: "Results", "M&A": "M&A", fund_raise: "Fund raise", management_change: "Management", litigation: "Legal / regulatory",
  insider_trading: "Insider trade", earnings_call: "Earnings call", investor_meetings: "Investor meet", credit_rating: "Credit rating",
  dividend: "Dividend", bonus_split: "Bonus / split", capex: "Capex", press_release: "Press release", postal_ballot: "Postal ballot",
  agm_egm: "AGM / EGM", pledging: "Pledge", unclassified: "Routine",
};
export const CATEGORIES = Object.keys(CATEGORY_LABEL).filter((c) => c !== "unclassified");
export const cls = (...xs: (string | false | null | undefined)[]) => xs.filter(Boolean).join(" ");
