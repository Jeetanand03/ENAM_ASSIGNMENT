"use client";
import { useEffect, useRef, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import Link from "next/link";
import { apiGet } from "@/lib/api";
import { useStore } from "@/lib/store";
import type { Research, Ask, Card, PriceSnap, Verdict, Cited } from "@/lib/types";
import { CATEGORY_LABEL, cls, fmtCr, fmtNum, fmtPct, fmtX } from "@/lib/format";
import Sparkline, { Bars } from "@/components/Sparkline";
import FeedCard from "@/components/FeedCard";

const MODULES = [["pvd", "Promised vs delivered"], ["snapshot", "Snapshot"], ["trajectory", "Trajectory"], ["cash", "Cash"], ["balance", "Balance sheet"], ["narrative", "Narrative vs numbers"], ["bullbear", "Bull / bear"], ["filings", "Filings"]];
const TOPIC_TO_MODULE: Record<string, string> = { results: "snapshot", "M&A": "balance", fund_raise: "balance", management_change: "narrative", credit_rating: "balance", "price move": "snapshot", earnings_call: "pvd", capex: "cash", dividend: "cash" };

export default function ResearchPage() {
  const { symbol } = useParams<{ symbol: string }>();
  const sym = String(symbol).toUpperCase();
  const topic = useSearchParams().get("topic");
  const { asOfParam } = useStore();
  const [r, setR] = useState<Research | null>(null);
  const [co, setCo] = useState<{ price: PriceSnap | null; feed: Card[]; meta: { name: string; sector: string } | null } | null>(null);
  const [active, setActive] = useState<string>(topic && TOPIC_TO_MODULE[topic] ? TOPIC_TO_MODULE[topic] : "pvd");
  const [source, setSource] = useState<string>("");
  const refs = useRef<Record<string, HTMLElement | null>>({});

  useEffect(() => {
    let alive = true; setR(null);
    // Two requests in parallel: numbers first (fast, no PDFs), then the full report once transcripts are read.
    let full = false;
    apiGet<Research>(`/api/research/${sym}?quick=1`, { timeoutMs: 45000 }).then(({ data, source }) => { if (alive && !full && data.ok) { setR(data); setSource(source); } }).catch(() => {});
    apiGet<Research>(`/api/research/${sym}`, { timeoutMs: 120000 }).then(({ data, source }) => { if (alive) { full = true; setR((prev) => (data.ok || !prev?.ok ? data : prev)); setSource(source); } })
      .catch((e) => alive && setR((prev) => prev?.ok ? prev : { symbol: sym, ok: false, error: `Could not reach the research engine (${String(e)}).` }));
    apiGet<{ price: PriceSnap | null; feed: Card[]; meta: { name: string; sector: string } | null }>(`/api/company/${sym}?as_of=${encodeURIComponent(asOfParam)}`).then(({ data }) => alive && setCo(data)).catch(() => {});
    return () => { alive = false; };
  }, [sym, asOfParam]);

  useEffect(() => {
    if (r?.ok && active) { const el = refs.current[active]; if (el && topic) setTimeout(() => el.scrollIntoView({ behavior: "smooth", block: "start" }), 150); }
  }, [r?.ok]); // eslint-disable-line react-hooks/exhaustive-deps

  const m = r?.modules;
  const name = r?.name || co?.meta?.name || sym;

  return (
    <div className="pt-1 pb-28">
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="min-w-0">
          <div className="text-[18px] font-bold leading-tight truncate">{name}</div>
          <div className="text-[11px] faint">{sym}{co?.meta?.sector ? ` · ${co.meta.sector}` : ""}{m?.business?.basis ? ` · ${m.business.basis}` : ""}{source === "fallback" ? " · snapshot" : ""}</div>
        </div>
        {co?.price && (
          <div className="flex items-center gap-2 shrink-0">
            <Sparkline data={co.price.spark} tone={(co.price.pct_move || 0) > 0 ? "up" : (co.price.pct_move || 0) < 0 ? "down" : "neutral"} />
            <div className="text-right num">
              <div className="text-[14px] font-semibold">₹{fmtNum(co.price.close, co.price.close > 1000 ? 0 : 1)}</div>
              <div className={cls("text-[11px] font-medium", (co.price.pct_move || 0) > 0 ? "up" : (co.price.pct_move || 0) < 0 ? "down" : "faint")}>{fmtPct(co.price.pct_move)} · vol {fmtX(co.price.vol_ratio)}</div>
            </div>
          </div>
        )}
      </div>
      {topic && <div className="text-[11px] mb-2 chip chip-warn">Opened from a {CATEGORY_LABEL[topic] || topic} card</div>}

      <div className="sticky top-[52px] z-20 -mx-4 px-4 py-1.5 flex gap-1.5 overflow-x-auto no-scrollbar" style={{ background: "color-mix(in srgb, var(--bg) 92%, transparent)", backdropFilter: "blur(8px)" }}>
        {MODULES.map(([k, l]) => <button key={k} onClick={() => { setActive(k); refs.current[k]?.scrollIntoView({ behavior: "smooth", block: "start" }); }} className={cls("chip press whitespace-nowrap", active === k && "chip-accent")}>{l}</button>)}
      </div>

      {!r && <SkeletonModules />}
      {r && !r.ok && <div className="card p-4 mt-2"><div className="text-[14px] font-semibold">Nothing to research yet</div><div className="text-[13px] muted mt-1">{r.error}</div><div className="text-[11px] faint mt-2">The engine works on any NSE ticker with a screener.in page and filed transcripts. Try one of the pre-researched names.</div></div>}

      {m && (
        <div className="flex flex-col gap-3 mt-2">
          <Section id="pvd" refs={refs} title="Promised vs delivered" sub="management's own numbers vs what was filed next">{m.promised_vs_delivered ? <PVD d={m.promised_vs_delivered} /> : <Reading n={r.documents?.transcripts.length || 0} />}</Section>
          <Section id="snapshot" refs={refs} title="Financial snapshot" sub={`latest quarter · ${m.snapshot.basis}`}><Snapshot r={r} /></Section>
          <Section id="trajectory" refs={refs} title="Trajectory" sub="annual, Rs crore"><Trajectory r={r} /></Section>
          <Section id="cash" refs={refs} title="Cash quality" sub="do profits turn into cash?"><Cash r={r} /></Section>
          <Section id="balance" refs={refs} title="Balance sheet" sub="leverage and working capital"><Balance r={r} /></Section>
          <Section id="narrative" refs={refs} title="Narrative vs numbers" sub={!m.narrative ? "" : m.narrative.method === "rules" ? "paired from the guidance record" : "model-written, every line cited"}>{m.narrative ? <Pairs a={m.narrative.agree} b={m.narrative.diverge} la="Agree" lb="Diverge" /> : <Reading n={r.documents?.transcripts.length || 0} />}</Section>
          <Section id="bullbear" refs={refs} title="Bull vs bear" sub={!m.bull_bear ? "" : m.bull_bear.method === "rules" ? "assembled from computed signals" : "model-written, every line cited"}>{m.bull_bear ? <Pairs a={m.bull_bear.bull} b={m.bull_bear.bear} la="Bull" lb="Bear" /> : <Reading n={r.documents?.transcripts.length || 0} />}</Section>
          <Section id="filings" refs={refs} title="Recent filings" sub="from the push feed">
            <div className="flex flex-col gap-2">{(co?.feed || []).slice(0, 6).map((c) => <FeedCard key={c.id} card={c} compact />)}{!co?.feed?.length && <div className="text-[12px] faint">Not in the portfolio — no filings tracked.</div>}</div>
          </Section>
          <div className="text-[10px] faint px-1">
            Sources: {r.documents?.transcripts.length || 0} concall transcripts ({r.documents?.transcripts.map((t) => t.when).join(", ")}), standardised financial tables from filings. No news, no broker notes.
            {r.cost ? ` · Model spend for this company: $${r.cost.usd.toFixed(4)} (${r.cost.calls} calls)` : ""}
          </div>
        </div>
      )}
      {r?.ok && <AskBar sym={sym} topic={topic} />}
    </div>
  );
}

function Section({ id, refs, title, sub, children }: { id: string; refs: React.MutableRefObject<Record<string, HTMLElement | null>>; title: string; sub: string; children: React.ReactNode }) {
  return (
    <section ref={(el) => { refs.current[id] = el; }} className="card p-3.5 scroll-mt-28 fade-in">
      <div className="flex items-baseline justify-between mb-2"><div className="text-[14px] font-semibold">{title}</div><div className="text-[10px] faint">{sub}</div></div>
      {children}
    </section>
  );
}

function Cite({ doc, page, url }: { doc: string; page?: number | null; url?: string }) {
  const label = `${doc.replace("Concall transcript ", "Call ").replace("standardised tables", "tables")}${page ? ` · p.${page}` : ""}`;
  return url ? <a href={url} target="_blank" rel="noreferrer" className="chip press" style={{ fontSize: 10 }}>{label}</a> : <span className="chip" style={{ fontSize: 10 }}>{label}</span>;
}

function PVD({ d }: { d: NonNullable<NonNullable<Research["modules"]>["promised_vs_delivered"]> }) {
  const [showUnclear, setShowUnclear] = useState(false);
  const judged = d.rows.filter((x) => x.verdict !== "unclear"); const unclear = d.rows.filter((x) => x.verdict === "unclear");
  const tone = (v: Verdict["verdict"]) => v === "met" ? "chip-up" : v === "missed" ? "chip-down" : v === "partially" ? "chip-warn" : "";
  return (
    <div>
      <div className="flex items-center gap-3 mb-3">
        <div className="num"><div className="text-[26px] font-bold leading-none" style={{ color: d.credibility === null ? "var(--ink-3)" : d.credibility >= 75 ? "var(--up)" : d.credibility >= 45 ? "var(--warn)" : "var(--down)" }}>{d.credibility === null ? "—" : d.credibility}</div><div className="text-[10px] faint">credibility</div></div>
        <div className="text-[12px] leading-snug muted flex-1">{d.summary}</div>
      </div>
      <div className="flex flex-col gap-2">
        {judged.map((row, i) => (
          <div key={i} className="rounded-xl p-2.5" style={{ background: "var(--surface-2)" }}>
            <div className="flex items-center justify-between gap-2 mb-1">
              <div className="flex items-center gap-1.5"><span className={cls("chip", tone(row.verdict))}>{row.verdict}{row.why === "beat" ? " · beat" : ""}{row.partial ? " so far" : ""}</span><span className="text-[11px] faint">{row.metric} · given {row.given_in}</span></div>
              <Cite doc={row.doc} page={row.page} url={row.url} />
            </div>
            <div className="grid grid-cols-2 gap-2 num">
              <div><div className="text-[10px] faint">Promised{row.horizon ? ` · ${row.horizon}` : ""}</div><div className="text-[15px] font-semibold">{fmtRange(row)}</div></div>
              <div><div className="text-[10px] faint">Delivered · {row.judged_on.map((j) => j.label).join(", ")}</div><div className="text-[15px] font-semibold">{row.delivered !== null ? `${row.delivered}%` : "—"}<span className="text-[10px] faint font-normal"> {row.measure}</span></div></div>
            </div>
            <blockquote className="text-[12px] mt-1.5 leading-snug muted" style={{ borderLeft: "2px solid var(--line)", paddingLeft: 8 }}>“{row.quote}”</blockquote>
          </div>
        ))}
        {!judged.length && <div className="text-[12px] faint">No guidance with a checkable figure in the transcripts read. Management talks, but not in numbers you can hold them to.</div>}
      </div>
      {unclear.length > 0 && (
        <button onClick={() => setShowUnclear((v) => !v)} className="text-[11px] faint mt-2 press">{showUnclear ? "Hide" : "Show"} {unclear.length} statements FINN couldn&apos;t check (segment-level, units, or quarters not reported yet)</button>
      )}
      {showUnclear && <div className="flex flex-col gap-1.5 mt-2">{unclear.map((row, i) => (
        <div key={i} className="text-[11px] muted rounded-lg p-2" style={{ background: "var(--surface-2)" }}>
          <div className="flex justify-between gap-2"><span className="faint">{row.metric} · {row.given_in} · {row.why}</span><Cite doc={row.doc} page={row.page} url={row.url} /></div>
          <div className="mt-0.5">“{row.quote}”</div>
        </div>
      ))}</div>}
    </div>
  );
}

function fmtRange(row: Verdict) {
  const [lo, hi] = row.range; if (lo === null) return "—";
  const u = row.unit && row.unit !== "percent" ? row.unit : "%";
  return lo === hi || hi === null ? `${lo}${u}` : `${lo}–${hi}${u}`;
}

function Snapshot({ r }: { r: Research }) {
  const s = r.modules!.snapshot; const q = s.latest_quarter; const qs = r.modules!.quarters;
  const kp = (label: string, v: string, sub?: string) => <div><div className="text-[10px] faint">{label}</div><div className="text-[15px] font-semibold num">{v}</div>{sub && <div className="text-[10px] muted num">{sub}</div>}</div>;
  return (
    <div>
      <div className="grid grid-cols-3 gap-2 mb-3">
        {kp(`Revenue · ${q.label}`, fmtCr(q.revenue), `${fmtPct(q.rev_yoy, 0)} YoY · ${fmtPct(q.rev_qoq, 0)} QoQ`)}
        {kp("Op. margin", q.opm !== null ? `${q.opm}%` : "—", `TTM ${s.ttm.opm ?? "—"}%`)}
        {kp("PAT", fmtCr(q.pat), `${fmtPct(q.pat_yoy, 0)} YoY`)}
      </div>
      <div className="flex items-end gap-3 mb-3">
        <div><div className="text-[10px] faint mb-1">Revenue, last 8 quarters</div><Bars data={qs.map((x) => x.revenue)} w={150} h={34} labels={qs.map((x) => x.label)} /></div>
        <div><div className="text-[10px] faint mb-1">PAT</div><Bars data={qs.map((x) => x.pat)} w={110} h={34} /></div>
      </div>
      <div className="grid grid-cols-4 gap-1.5 text-[11px] num">
        {["Market Cap", "Stock P/E", "ROCE", "ROE"].map((k) => <div key={k} className="rounded-lg p-1.5" style={{ background: "var(--surface-2)" }}><div className="text-[9px] faint">{k}</div><div className="font-medium">{(s.ratios[k] || "—").replace("₹ ", "₹").replace(" Cr.", " cr")}</div></div>)}
      </div>
      <div className="mt-2"><Cite doc="standardised tables" url={s.source.url} /></div>
    </div>
  );
}

function Trajectory({ r }: { r: Research }) {
  const t = r.modules!.trajectory;
  return (
    <div>
      <div className="rounded-xl overflow-hidden mb-2" style={{ border: "1px solid var(--line)" }}>
        <table className="w-full text-[11px] num">
          <thead><tr className="text-[10px] faint" style={{ background: "var(--surface-2)" }}><th className="text-left px-2 py-1 font-medium">FY</th><th className="text-right px-2 py-1 font-medium">Revenue</th><th className="text-right px-2 py-1 font-medium">Growth</th><th className="text-right px-2 py-1 font-medium">OPM</th><th className="text-right px-2 py-1 font-medium">PAT</th><th className="text-right px-2 py-1 font-medium">Growth</th></tr></thead>
          <tbody>{t.years.map((y) => <tr key={y.fy} style={{ borderTop: "1px solid var(--line)" }}><td className="px-2 py-1 font-medium">{y.fy}</td><td className="text-right px-2 py-1">{fmtNum(y.revenue)}</td><td className={cls("text-right px-2 py-1", (y.rev_growth || 0) < 0 ? "down" : "muted")}>{fmtPct(y.rev_growth, 0)}</td><td className="text-right px-2 py-1">{y.opm ?? "—"}%</td><td className="text-right px-2 py-1">{fmtNum(y.pat)}</td><td className={cls("text-right px-2 py-1", (y.pat_growth || 0) < 0 ? "down" : "muted")}>{fmtPct(y.pat_growth, 0)}</td></tr>)}</tbody>
        </table>
      </div>
      <Signals s={t.signals} /><div className="mt-2"><Cite doc="standardised tables · profit-loss" url={t.source.url} /></div>
    </div>
  );
}

function Cash({ r }: { r: Research }) {
  const c = r.modules!.cash;
  return (
    <div>
      <div className="flex items-end gap-4 mb-2">
        <div className="num"><div className="text-[26px] font-bold leading-none" style={{ color: c.conversion === null ? "var(--ink-3)" : c.conversion >= 0.8 ? "var(--up)" : "var(--down)" }}>{c.conversion === null ? "—" : `${c.conversion.toFixed(2)}×`}</div><div className="text-[10px] faint">CFO / PAT, {c.years.length}y</div></div>
        <div><div className="text-[10px] faint mb-1">Free cash flow by year</div><Bars data={c.years.map((y) => y.fcf)} w={150} h={34} labels={c.years.map((y) => y.fy)} /></div>
      </div>
      <div className="rounded-xl overflow-hidden mb-2" style={{ border: "1px solid var(--line)" }}>
        <table className="w-full text-[11px] num"><thead><tr className="text-[10px] faint" style={{ background: "var(--surface-2)" }}><th className="text-left px-2 py-1 font-medium">FY</th><th className="text-right px-2 py-1 font-medium">PAT</th><th className="text-right px-2 py-1 font-medium">CFO</th><th className="text-right px-2 py-1 font-medium">CFO/PAT</th><th className="text-right px-2 py-1 font-medium">FCF</th></tr></thead>
          <tbody>{c.years.map((y) => <tr key={y.fy} style={{ borderTop: "1px solid var(--line)" }}><td className="px-2 py-1 font-medium">{y.fy}</td><td className="text-right px-2 py-1">{fmtNum(y.pat)}</td><td className="text-right px-2 py-1">{fmtNum(y.cfo)}</td><td className={cls("text-right px-2 py-1", (y.cfo_to_pat ?? 1) < 0.6 ? "down" : "")}>{y.cfo_to_pat !== null ? `${y.cfo_to_pat.toFixed(2)}×` : "—"}</td><td className={cls("text-right px-2 py-1", (y.fcf ?? 0) < 0 ? "down" : "")}>{fmtNum(y.fcf)}</td></tr>)}</tbody></table>
      </div>
      <Signals s={c.signals} /><div className="mt-2"><Cite doc="standardised tables · cash-flow" url={c.source.url} /></div>
    </div>
  );
}

function Balance({ r }: { r: Research }) {
  const b = r.modules!.balance_sheet; const last = b.years[b.years.length - 1];
  return (
    <div>
      {last && <div className="grid grid-cols-4 gap-1.5 text-[11px] num mb-2">
        {[["Debt/Equity", last.de !== null ? last.de.toFixed(2) : "—"], ["Borrowings", fmtCr(last.debt)], ["CCC days", last.ccc ?? "—"], ["ROCE", last.roce !== null ? `${last.roce}%` : "—"]].map(([k, v]) => <div key={String(k)} className="rounded-lg p-1.5" style={{ background: "var(--surface-2)" }}><div className="text-[9px] faint">{k}</div><div className="font-medium">{v}</div></div>)}
      </div>}
      <div className="rounded-xl overflow-hidden mb-2" style={{ border: "1px solid var(--line)" }}>
        <table className="w-full text-[11px] num"><thead><tr className="text-[10px] faint" style={{ background: "var(--surface-2)" }}><th className="text-left px-2 py-1 font-medium">FY</th><th className="text-right px-2 py-1 font-medium">Net worth</th><th className="text-right px-2 py-1 font-medium">Debt</th><th className="text-right px-2 py-1 font-medium">D/E</th><th className="text-right px-2 py-1 font-medium">Debtor d</th><th className="text-right px-2 py-1 font-medium">Inv. d</th><th className="text-right px-2 py-1 font-medium">CWIP</th></tr></thead>
          <tbody>{b.years.map((y) => <tr key={y.fy} style={{ borderTop: "1px solid var(--line)" }}><td className="px-2 py-1 font-medium">{y.fy}</td><td className="text-right px-2 py-1">{fmtNum(y.net_worth)}</td><td className="text-right px-2 py-1">{fmtNum(y.debt)}</td><td className="text-right px-2 py-1">{y.de?.toFixed(2) ?? "—"}</td><td className="text-right px-2 py-1">{y.debtor_days ?? "—"}</td><td className="text-right px-2 py-1">{y.inventory_days ?? "—"}</td><td className="text-right px-2 py-1">{fmtNum(y.cwip)}</td></tr>)}</tbody></table>
      </div>
      <Signals s={b.signals} /><div className="mt-2"><Cite doc="standardised tables · balance-sheet" url={b.source.url} /></div>
    </div>
  );
}

function Signals({ s }: { s: string[] }) {
  if (!s.length) return null;
  return <ul className="flex flex-col gap-1">{s.map((x, i) => <li key={i} className="text-[12px] leading-snug flex gap-1.5"><span className="faint">·</span><span>{x}</span></li>)}</ul>;
}

function Pairs({ a, b, la, lb }: { a: Cited[]; b: Cited[]; la: string; lb: string }) {
  const col = (items: Cited[], label: string, tone: string) => (
    <div>
      <div className="text-[11px] font-semibold mb-1" style={{ color: tone }}>{label}</div>
      {items.length === 0 && <div className="text-[11px] faint">Nothing strong enough to say.</div>}
      <ul className="flex flex-col gap-1.5">{items.map((x, i) => <li key={i} className="text-[12px] leading-snug"><span>{x.text}</span> <span className="chip" style={{ fontSize: 9 }}>{x.cite.replace("Concall transcript ", "Call ")}</span></li>)}</ul>
    </div>
  );
  return <div className="grid grid-cols-1 gap-3">{col(a, la, "var(--up)")}{col(b, lb, "var(--down)")}</div>;
}

function AskBar({ sym, topic }: { sym: string; topic: string | null }) {
  const [q, setQ] = useState(""); const [a, setA] = useState<Ask | null>(null); const [busy, setBusy] = useState(false);
  const [listening, setListening] = useState(false);
  const ask = async (text: string) => {
    if (!text.trim()) return; setBusy(true); setA(null);
    try { const { data } = await apiGet<Ask>(`/api/research/${sym}/ask?q=${encodeURIComponent(text)}${topic ? `&topic=${encodeURIComponent(topic)}` : ""}`, { timeoutMs: 60000 }); setA(data); }
    catch { setA({ answer: "The research engine is unreachable right now.", citations: [] }); } finally { setBusy(false); }
  };
  const voice = () => {
    const W = window as unknown as { webkitSpeechRecognition?: new () => SpeechRecognitionLike; SpeechRecognition?: new () => SpeechRecognitionLike };
    const SR = W.SpeechRecognition || W.webkitSpeechRecognition; if (!SR) return;
    const rec = new SR(); rec.lang = "en-IN"; rec.onresult = (e) => { const t = e.results[0][0].transcript; setQ(t); setListening(false); ask(t); }; rec.onend = () => setListening(false); setListening(true); rec.start();
  };
  const chips = ["What did management guide for margins?", "Any capex plans?", "What are analysts worried about?", "How is the order book?"];
  return (
    <div className="fixed bottom-14 inset-x-0 z-30">
      <div className="mx-auto max-w-[520px] px-3 pb-2">
        {(a || busy) && (
          <div className="card p-3 mb-2 fade-in max-h-[45vh] overflow-y-auto">
            {busy && <div><div className="skeleton h-3 w-32 mb-2" /><div className="skeleton h-3 w-full mb-1" /><div className="skeleton h-3 w-3/4" /></div>}
            {a && <div className="text-[13px] leading-relaxed whitespace-pre-wrap">{a.answer}</div>}
            {a?.citations?.length ? <div className="flex flex-col gap-1.5 mt-2">{a.citations.map((c, i) => <a key={i} href={c.url} target="_blank" rel="noreferrer" className="rounded-lg p-2 text-[11px] press" style={{ background: "var(--surface-2)" }}><div className="font-semibold">{c.doc} · p.{c.page}</div><div className="muted line-clamp-3">{c.snippet}</div></a>)}</div> : null}
            {a && <button onClick={() => setA(null)} className="text-[11px] faint mt-2 press">dismiss</button>}
          </div>
        )}
        {!a && !busy && <div className="flex gap-1.5 overflow-x-auto no-scrollbar mb-1.5">{chips.map((c) => <button key={c} onClick={() => { setQ(c); ask(c); }} className="chip press whitespace-nowrap" style={{ background: "var(--surface)" }}>{c}</button>)}</div>}
        <form onSubmit={(e) => { e.preventDefault(); ask(q); }} className="flex items-center gap-1.5 rounded-2xl px-2 py-1.5" style={{ background: "var(--surface)", border: "1px solid var(--line)", boxShadow: "0 6px 24px rgba(0,0,0,.08)" }}>
          <button type="button" onClick={voice} className={cls("w-8 h-8 rounded-full flex items-center justify-center press", listening && "chip-down")} aria-label="Voice"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="9" y="3" width="6" height="11" rx="3" /><path d="M5 11a7 7 0 0014 0M12 18v3" strokeLinecap="round" /></svg></button>
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder={`Ask about ${sym} — answers only from its filings`} className="flex-1 bg-transparent outline-none text-[14px] py-1" />
          <button type="submit" className="w-8 h-8 rounded-full flex items-center justify-center text-white press" style={{ background: "var(--accent)" }} aria-label="Ask"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4"><path d="M5 12h14M13 6l6 6-6 6" strokeLinecap="round" strokeLinejoin="round" /></svg></button>
        </form>
      </div>
    </div>
  );
}
type SpeechRecognitionLike = { lang: string; onresult: ((e: { results: { [i: number]: { [j: number]: { transcript: string } } } }) => void) | null; onend: (() => void) | null; start: () => void };

function SkeletonModules() {
  return <div className="flex flex-col gap-3 mt-2">{[0, 1, 2].map((i) => <div key={i} className="card p-3.5"><div className="skeleton h-4 w-40 mb-3" /><div className="skeleton h-3 w-full mb-1.5" /><div className="skeleton h-3 w-5/6 mb-1.5" /><div className="skeleton h-20 w-full" /></div>)}</div>;
}

function Reading({ n }: { n: number }) {
  return (
    <div>
      <div className="text-[12px] muted mb-2">Reading {n} concall transcripts and matching every number management promised to what was filed next…</div>
      <div className="skeleton h-3 w-full mb-1.5" /><div className="skeleton h-3 w-4/5 mb-1.5" /><div className="skeleton h-14 w-full" />
    </div>
  );
}
