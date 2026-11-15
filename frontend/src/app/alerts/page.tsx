"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { apiGet } from "@/lib/api";
import { useStore } from "@/lib/store";
import type { Alert, Settings } from "@/lib/types";
import { CATEGORY_LABEL, cls, fmtDate, fmtNum, fmtPct, fmtX } from "@/lib/format";

export default function AlertsPage() {
  const { asOfParam, asOf, settings } = useStore();
  const [data, setData] = useState<{ alerts: Alert[]; settings: Settings } | null>(null);
  const [days, setDays] = useState(10);
  const [kind, setKind] = useState<"all" | "market" | "filing">("all");

  useEffect(() => {
    let alive = true; setData(null);
    apiGet<{ alerts: Alert[]; settings: Settings }>(`/api/alerts?as_of=${encodeURIComponent(asOfParam)}&days=${days}`)
      .then(({ data }) => alive && setData(data)).catch(() => alive && setData({ alerts: [], settings: settings! }));
    return () => { alive = false; };
  }, [asOfParam, days, settings?.price_move_pct, settings?.volume_multiple, settings?.starred_categories?.join(",")]);

  const list = (data?.alerts || []).filter((a) => kind === "all" || a.type === kind);
  const groups = groupByDay(list);
  const s = data?.settings || settings;

  return (
    <div className="pt-1">
      <div className="flex items-center justify-between mb-2">
        <div>
          <div className="text-[13px] muted">Threshold crossings</div>
          <div className="text-[11px] faint">{s ? `|move| ≥ ${s.price_move_pct}% · volume ≥ ${s.volume_multiple}× · ★ ${s.starred_categories.map((c) => CATEGORY_LABEL[c]).join(", ")}` : ""}</div>
        </div>
        <div className="flex rounded-lg p-0.5" style={{ background: "var(--surface-2)" }}>
          {[5, 10, 30].map((d) => (
            <button key={d} onClick={() => setDays(d)} className={cls("px-2.5 py-1 text-[12px] rounded-md press", days === d ? "font-semibold" : "muted")} style={days === d ? { background: "var(--surface)", boxShadow: "0 1px 2px rgba(0,0,0,.08)" } : undefined}>{d}d</button>
          ))}
        </div>
      </div>
      <div className="flex gap-1.5 mb-3">
        {(["all", "market", "filing"] as const).map((k) => (
          <button key={k} onClick={() => setKind(k)} className={cls("chip press", kind === k && "chip-accent")}>{k === "all" ? `All ${data?.alerts.length ?? ""}` : k === "market" ? "Price / volume" : "Filings"}</button>
        ))}
        <span className="ml-auto text-[11px] faint self-center">{asOf ? "as of simulated clock" : "up to today"}</span>
      </div>

      {!data && <div className="flex flex-col gap-2">{[0, 1, 2].map((i) => <div key={i} className="card p-3"><div className="skeleton h-3 w-24 mb-2" /><div className="skeleton h-4 w-3/4" /></div>)}</div>}
      {data && list.length === 0 && <div className="card p-5 text-center text-[13px] muted">Nothing crossed your thresholds in the last {days} days. Lower them in Tune, or rewind the clock.</div>}

      {groups.map(([day, items]) => (
        <section key={day} className="mb-4">
          <div className="text-[11px] font-semibold faint uppercase tracking-wide mb-1.5">{fmtDate(day)}</div>
          <div className="flex flex-col gap-2">
            {items.map((a) => <AlertRow key={a.id} a={a} />)}
          </div>
        </section>
      ))}
    </div>
  );
}

function AlertRow({ a }: { a: Alert }) {
  const neg = (a.pct_move ?? 0) < 0;
  return (
    <Link href={`/research/${a.symbol}?topic=${encodeURIComponent(a.type === "filing" ? a.category || "" : "price move")}`} className="card p-3 block press fade-in">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5 min-w-0">
          <span className={cls("w-1.5 h-1.5 rounded-full shrink-0")} style={{ background: a.type === "market" ? (neg ? "var(--down)" : "var(--up)") : "var(--accent)" }} />
          <span className="text-[13px] font-semibold truncate">{a.name}</span>
          <span className="text-[11px] faint">{a.symbol}</span>
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          {a.type === "filing" && <span className="chip chip-accent">{CATEGORY_LABEL[a.category || ""] || a.category}</span>}
          {a.type === "filing" && a.with_market_move && <span className="chip chip-warn">+ stock moved</span>}
          <span className="text-[11px] num faint">{fmtDate(a.ts, a.type === "filing")}</span>
        </div>
      </div>
      {a.type === "market" ? (
        <div className="mt-1.5 flex items-baseline gap-3 num">
          <span className="text-[15px] font-semibold">₹{fmtNum(a.close, 1)}</span>
          <span className={cls("text-[14px] font-semibold", neg ? "down" : "up")}>{fmtPct(a.pct_move)}</span>
          <span className="text-[12px] muted">vol {fmtX(a.vol_ratio)}</span>
          <span className="ml-auto text-[11px] faint">{a.hits?.map((h) => h.kind).join(" + ")}</span>
        </div>
      ) : (
        <div className="mt-1.5 text-[13px] leading-snug">{a.headline}</div>
      )}
    </Link>
  );
}

function groupByDay(list: Alert[]): [string, Alert[]][] {
  const m = new Map<string, Alert[]>();
  for (const a of list) { const d = a.ts.slice(0, 10); m.set(d, [...(m.get(d) || []), a]); }
  return Array.from(m.entries()).sort((x, y) => (x[0] < y[0] ? 1 : -1));
}
