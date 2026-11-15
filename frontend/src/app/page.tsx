"use client";
import { useEffect, useMemo, useState } from "react";
import { apiGet } from "@/lib/api";
import { useStore } from "@/lib/store";
import type { Digest, Card } from "@/lib/types";
import { CATEGORY_LABEL, cls, fmtDate } from "@/lib/format";
import FeedCard from "@/components/FeedCard";

const WINDOWS = [["24h", "24h"], ["3d", "3 days"], ["7d", "7 days"], ["30d", "30 days"]];

export default function FeedPage() {
  const { asOfParam, asOf, settings } = useStore();
  const [win, setWin] = useState("24h");
  const [digest, setDigest] = useState<Digest | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [routineOpen, setRoutineOpen] = useState(false);
  const [filter, setFilter] = useState<string | null>(null);
  const [widened, setWidened] = useState(false);

  useEffect(() => {
    let alive = true;
    setDigest(null); setErr(null);
    setWidened(false);
    apiGet<Digest>(`/api/digest?window=${win}&as_of=${encodeURIComponent(asOfParam)}`)
      .then(async ({ data }) => {
        // A quiet 24h (weekend, holiday) shouldn't greet the investor with an empty screen: show the last 3 days, and say so.
        if (data.total === 0 && win === "24h") {
          try { const r = await apiGet<Digest>(`/api/digest?window=3d&as_of=${encodeURIComponent(asOfParam)}`); if (r.data.total > 0) { if (alive) { setDigest(r.data); setWidened(true); } return; } } catch {}
        }
        if (alive) setDigest(data);
      }).catch((e) => alive && setErr(String(e)));
    return () => { alive = false; };
  }, [win, asOfParam, settings?.starred_categories?.join(","), settings?.price_move_pct, settings?.volume_multiple]);

  const cats = useMemo(() => Object.entries(digest?.by_category || {}).sort((a, b) => b[1] - a[1]), [digest]);
  const pick = (cards: Card[]) => (filter ? cards.filter((c) => c.category === filter) : cards);

  return (
    <div className="pt-1">
      <div className="flex items-center justify-between mb-2">
        <div>
          <div className="text-[13px] muted">What changed</div>
          <div className="text-[11px] faint">{digest ? `${fmtDate(digest.from, true)} → ${fmtDate(digest.to, true)}` : "…"}{asOf ? " · simulated" : ""}</div>
        </div>
        <div className="flex rounded-lg p-0.5" style={{ background: "var(--surface-2)" }}>
          {WINDOWS.map(([k, l]) => (
            <button key={k} onClick={() => setWin(k)} className={cls("px-2.5 py-1 text-[12px] rounded-md press", win === k ? "font-semibold" : "muted")} style={win === k ? { background: "var(--surface)", boxShadow: "0 1px 2px rgba(0,0,0,.08)" } : undefined}>{l}</button>
          ))}
        </div>
      </div>

      {digest && digest.total > 0 && (
        <div className="flex gap-1.5 overflow-x-auto no-scrollbar -mx-4 px-4 pb-2">
          <button onClick={() => setFilter(null)} className={cls("chip press whitespace-nowrap", !filter && "chip-accent")}>All {digest.total}</button>
          {cats.map(([c, n]) => (
            <button key={c} onClick={() => setFilter(filter === c ? null : c)} className={cls("chip press whitespace-nowrap", filter === c && "chip-accent")}>{CATEGORY_LABEL[c] || c} {n}</button>
          ))}
        </div>
      )}

      {widened && <div className="text-[12px] muted mb-2 rounded-lg px-3 py-2" style={{ background: "var(--surface-2)" }}>Nothing filed in the last 24 hours. Showing the last 3 days instead.</div>}
      {!digest && !err && <Skeleton />}
      {err && <div className="card p-4 text-[13px] muted">Couldn&apos;t load the digest. {err}</div>}

      {digest && digest.total === 0 && (
        <div className="card p-5 text-center mt-2">
          <div className="text-[15px] font-semibold">Quiet window</div>
          <div className="text-[13px] muted mt-1">No filings across your 20 companies in this period. Widen the window or rewind the clock to a results week.</div>
        </div>
      )}

      {digest && <Tier title="Must see" sub="material filings — read these" cards={pick(digest.tiers.must)} tone="must" />}
      {digest && <Tier title="Worth a look" sub="one line is usually enough" cards={pick(digest.tiers.look)} tone="look" />}
      {digest && pick(digest.tiers.routine).length > 0 && (
        <section className="mt-5">
          <button onClick={() => setRoutineOpen((v) => !v)} className="w-full flex items-center justify-between py-2 press">
            <div className="text-left">
              <div className="text-[13px] font-semibold faint">Routine · {pick(digest.tiers.routine).length}</div>
              <div className="text-[11px] faint">ESOPs, certificates, newspaper copies, investor meets — hidden by default</div>
            </div>
            <span className="faint text-[12px]">{routineOpen ? "Hide" : "Show"}</span>
          </button>
          {routineOpen && <div className="flex flex-col gap-2 fade-in">{pick(digest.tiers.routine).map((c) => <FeedCard key={c.id} card={c} compact />)}</div>}
        </section>
      )}
    </div>
  );
}

function Tier({ title, sub, cards, tone }: { title: string; sub: string; cards: Card[]; tone: "must" | "look" }) {
  if (!cards.length) return null;
  return (
    <section className="mt-3">
      <div className="flex items-baseline justify-between mb-1.5">
        <div className="flex items-baseline gap-2">
          <span className="text-[15px] font-semibold" style={tone === "must" ? { color: "var(--accent)" } : undefined}>{title}</span>
          <span className="text-[11px] faint">{sub}</span>
        </div>
        <span className="text-[11px] num faint">{cards.length}</span>
      </div>
      <div className="flex flex-col gap-2">{cards.map((c) => <FeedCard key={c.id} card={c} compact={tone === "look"} />)}</div>
    </section>
  );
}

function Skeleton() {
  return (
    <div className="flex flex-col gap-2 mt-2">
      {[0, 1, 2, 3].map((i) => (
        <div key={i} className="card p-3">
          <div className="skeleton h-3 w-24 mb-2" /><div className="skeleton h-4 w-full mb-1.5" /><div className="skeleton h-3 w-2/3" />
        </div>
      ))}
    </div>
  );
}
