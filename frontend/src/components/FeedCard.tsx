"use client";
import { useState } from "react";
import Link from "next/link";
import type { Card, Enrich } from "@/lib/types";
import { CATEGORY_LABEL, cls, timeAgo } from "@/lib/format";
import { apiGet } from "@/lib/api";
import { useStore } from "@/lib/store";
import ResultsTable from "./ResultsTable";
import MgmtCard from "./MgmtCard";

const ENRICHABLE = new Set(["results", "management_change"]);

export default function FeedCard({ card, compact = false }: { card: Card; compact?: boolean }) {
  const { nowISO } = useStore();
  const [open, setOpen] = useState(false);
  const [enrich, setEnrich] = useState<Enrich | null>(card.enrich);
  const [loading, setLoading] = useState(false);
  const [why, setWhy] = useState(false);

  const toggle = async () => {
    const next = !open; setOpen(next);
    if (next && !enrich && ENRICHABLE.has(card.category)) {
      setLoading(true);
      try { const { data } = await apiGet<Enrich>(`/api/announcements/${card.id}/enrich`, { timeoutMs: 40000 }); setEnrich(data); } catch {} finally { setLoading(false); }
    }
  };
  const tierChip = card.tier === "must" ? "chip-accent" : card.tier === "look" ? "" : "";
  const catTone = card.category === "results" || card.category === "M&A" ? "chip-accent" : card.category === "litigation" || card.category === "pledging" ? "chip-down" : "";
  const reaction = card.why?.reaction_why;

  return (
    <article className={cls("card fade-in", compact ? "p-3" : "p-3.5")}>
      <button onClick={toggle} className="w-full text-left press">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-1.5 min-w-0">
            <span className="text-[13px] font-semibold truncate">{card.name}</span>
            <span className="text-[11px] faint">{card.symbol}</span>
          </div>
          <div className="flex items-center gap-1.5 shrink-0">
            <span className={cls("chip", catTone)}>{CATEGORY_LABEL[card.category] || card.category}</span>
            <span className="text-[11px] num faint">{timeAgo(card.ts, new Date(nowISO()))}</span>
          </div>
        </div>
        <div className={cls("mt-1.5 leading-snug", compact ? "text-[13px]" : "text-[14px] font-medium")}>{card.headline}</div>
        {!open && enrich && enrich.kind === "results" && enrich.ok && <ResultsStrip e={enrich} />}
        {!open && enrich && enrich.kind === "management_change" && enrich.ok && <MgmtStrip e={enrich as Extract<Enrich, { kind: "management_change" }>} />}
        {!compact && card.summary && !open && !(enrich && enrich.ok) && <div className="text-[12px] muted mt-1 line-clamp-2">{card.summary}</div>}
        {(reaction || card.why?.user || card.related?.length) && (
          <div className="flex gap-1.5 mt-2 flex-wrap">
            {reaction && <span className={cls("chip", reaction.includes("-") && reaction.includes("price") ? "chip-down" : "chip-up")}>{reaction}</span>}
            {card.why?.user ? <span className="chip">★ starred</span> : null}
            {card.related?.length ? <span className="chip">+{card.related.length} related</span> : null}
          </div>
        )}
      </button>

      {open && (
        <div className="mt-3 pt-3 fade-in" style={{ borderTop: "1px solid var(--line)" }}>
          {card.summary && <p className="text-[13px] leading-relaxed">{card.summary}</p>}
          {!card.summary && <p className="text-[13px] muted">{card.subject}</p>}
          {loading && <div className="mt-3"><div className="skeleton h-3 w-28 mb-2" /><div className="skeleton h-16 w-full" /></div>}
          {enrich && enrich.kind === "results" && enrich.ok && <ResultsTable e={enrich} />}
          {enrich && enrich.kind === "management_change" && <MgmtCard e={enrich as Extract<Enrich, { kind: "management_change" }>} />}
          {enrich && !enrich.ok && ENRICHABLE.has(card.category) && <div className="text-[12px] faint mt-2">No first-cut available: {(enrich as { reason?: string }).reason}</div>}

          {card.related?.length ? (
            <div className="mt-3 flex flex-col gap-1">
              <div className="text-[10px] faint uppercase tracking-wide">Same event, also filed</div>
              {card.related.map((r) => (
                <a key={r.id} href={r.pdf_url || "#"} target="_blank" rel="noreferrer" className="text-[12px] muted flex gap-2 press"><span className="num faint shrink-0">{timeAgo(r.ts, new Date(nowISO()))}</span><span className="line-clamp-1">{r.headline}</span></a>
              ))}
            </div>
          ) : null}
          <div className="flex items-center justify-between mt-3">
            <div className="flex items-center gap-1.5">
              <Link href={`/research/${card.symbol}?topic=${encodeURIComponent(card.category)}`} className="chip chip-accent press">Dig in →</Link>
              {card.pdf_url && <a href={card.pdf_url} target="_blank" rel="noreferrer" className="chip press">Filing PDF</a>}
            </div>
            <button onClick={() => setWhy((v) => !v)} className="text-[11px] faint press">why here · {card.score}</button>
          </div>
          {why && (
            <div className="mt-2 text-[11px] muted rounded-lg p-2 num" style={{ background: "var(--surface-2)" }}>
              <div className="flex justify-between"><span>{card.why.category_why}</span><span>{card.why.category}</span></div>
              <div className="flex justify-between"><span>{card.why.reaction_why || "no unusual price/volume reaction"}</span><span>+{card.why.reaction}</span></div>
              <div className="flex justify-between"><span>{card.why.user_why || "not a starred type"}</span><span>+{card.why.user}</span></div>
              <div className="flex justify-between font-semibold pt-1 mt-1" style={{ borderTop: "1px solid var(--line)" }}><span>score → {card.tier === "must" ? "Must see (≥75)" : card.tier === "look" ? "Worth a look (45–74)" : "Routine (<45)"}</span><span>{card.score}</span></div>
              <div className="faint mt-1">classified by {card.category_source === "raw" ? "exchange category" : card.category_source === "rule" ? "keyword rule" : card.category_source === "llm" ? "model" : "fallback"}</div>
            </div>
          )}
        </div>
      )}
    </article>
  );
}

function ResultsStrip({ e }: { e: Extract<Enrich, { kind: "results"; ok: true }> }) {
  const rows = e.table.rows.filter((r) => r.yoy !== null);
  return (
    <div className="mt-2 grid grid-cols-4 gap-1 num">
      {rows.map((r) => (
        <div key={r.key} className="rounded-lg px-1.5 py-1" style={{ background: "var(--surface-2)" }}>
          <div className="text-[9px] faint">{r.label}{r.derived ? "*" : ""} YoY</div>
          <div className={cls("text-[13px] font-semibold", (r.yoy ?? 0) > 0 ? "up" : (r.yoy ?? 0) < 0 ? "down" : "")}>{r.yoy! > 0 ? "+" : ""}{r.yoy!.toFixed(0)}%</div>
        </div>
      ))}
    </div>
  );
}

function MgmtStrip({ e }: { e: Extract<Enrich, { kind: "management_change" }> }) {
  return (
    <div className="mt-2 flex flex-wrap gap-1.5">
      {e.changes.slice(0, 3).map((c, i) => (
        <span key={i} className={cls("chip", c.direction === "in" ? "chip-up" : c.direction === "out" ? "chip-down" : "")}>
          {c.direction === "in" ? "In" : c.direction === "out" ? "Out" : "Re-appointed"}: {c.person}{c.role ? `, ${c.role}` : ""}
        </span>
      ))}
    </div>
  );
}
