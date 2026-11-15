"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { apiGet } from "@/lib/api";
import { useStore } from "@/lib/store";
import type { Company } from "@/lib/types";
import { cls, fmtNum, fmtPct, fmtX } from "@/lib/format";
import Sparkline from "@/components/Sparkline";

const DEMO = [["DIXON", "Dixon"], ["PERSISTENT", "Persistent"], ["VBL", "Varun Bev."], ["KAYNES", "Kaynes"]];

export default function ResearchIndex() {
  const { asOfParam } = useStore();
  const router = useRouter();
  const [q, setQ] = useState("");
  const [cos, setCos] = useState<Company[] | null>(null);
  const [sort, setSort] = useState<"move" | "name" | "filings">("move");

  useEffect(() => {
    let alive = true;
    apiGet<{ companies: Company[] }>(`/api/portfolio?as_of=${encodeURIComponent(asOfParam)}`).then(({ data }) => alive && setCos(data.companies)).catch(() => alive && setCos([]));
    return () => { alive = false; };
  }, [asOfParam]);

  const go = (s: string) => { const t = s.trim().toUpperCase().replace(/\.NS$/, ""); if (t) router.push(`/research/${t}`); };
  const sorted = [...(cos || [])].sort((a, b) => sort === "name" ? a.name.localeCompare(b.name) : sort === "filings" ? (b.top_score_7d || 0) - (a.top_score_7d || 0) : Math.abs(b.price?.pct_move || 0) - Math.abs(a.price?.pct_move || 0));

  return (
    <div className="pt-1">
      <form onSubmit={(e) => { e.preventDefault(); go(q); }} className="flex gap-2 mb-2">
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Any NSE ticker — e.g. PIIND, TATAELXSI" autoCapitalize="characters" autoCorrect="off"
          className="flex-1 rounded-xl px-3 py-2.5 text-[14px] outline-none" style={{ background: "var(--surface)", border: "1px solid var(--line)" }} />
        <button type="submit" className="rounded-xl px-4 text-[14px] font-semibold text-white press" style={{ background: "var(--accent)" }}>Dig in</button>
      </form>
      <div className="flex items-center gap-1.5 mb-4 overflow-x-auto no-scrollbar">
        <span className="text-[11px] faint shrink-0">Pre-researched:</span>
        {DEMO.map(([s, l]) => <Link key={s} href={`/research/${s}`} className="chip chip-accent press whitespace-nowrap">{l}</Link>)}
      </div>

      <div className="flex items-center justify-between mb-1.5">
        <div className="text-[13px] muted">Portfolio · {cos?.length ?? 20}</div>
        <div className="flex gap-1">
          {(["move", "filings", "name"] as const).map((k) => <button key={k} onClick={() => setSort(k)} className={cls("chip press", sort === k && "chip-accent")}>{k === "move" ? "by move" : k === "filings" ? "by news" : "A–Z"}</button>)}
        </div>
      </div>
      {!cos && <div className="flex flex-col gap-1.5">{[0, 1, 2, 3, 4, 5].map((i) => <div key={i} className="card p-3"><div className="skeleton h-4 w-full" /></div>)}</div>}
      <div className="card divide-y" style={{ borderColor: "var(--line)" }}>
        {sorted.map((c) => {
          const m = c.price?.pct_move ?? null; const tone = m === null ? "neutral" : m > 0 ? "up" : m < 0 ? "down" : "neutral";
          return (
            <Link key={c.symbol} href={`/research/${c.symbol}`} className="flex items-center gap-3 px-3 py-2.5 press hairline">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-1.5"><span className="text-[13px] font-semibold truncate">{c.name}</span>{(c.top_score_7d || 0) >= 75 && <span className="w-1.5 h-1.5 rounded-full" style={{ background: "var(--accent)" }} />}</div>
                <div className="text-[11px] faint truncate">{c.symbol} · {c.sector} · {c.size}</div>
              </div>
              <Sparkline data={c.price?.spark || []} tone={tone as "up" | "down" | "neutral"} />
              <div className="text-right num w-[76px]">
                <div className="text-[13px] font-medium">₹{fmtNum(c.price?.close, c.price && c.price.close > 1000 ? 0 : 1)}</div>
                <div className={cls("text-[11px] font-medium", tone === "up" ? "up" : tone === "down" ? "down" : "faint")}>{fmtPct(m)}{(c.price?.vol_ratio || 0) >= 2 ? <span className="faint"> · {fmtX(c.price?.vol_ratio)}</span> : null}</div>
              </div>
            </Link>
          );
        })}
      </div>
      <div className="text-[10px] faint mt-2">EOD prices via Yahoo Finance · sparkline = last 30 closes · dot = must-see filing this week</div>
    </div>
  );
}
