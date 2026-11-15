"use client";
import { useState } from "react";
import { useStore } from "@/lib/store";
import { fmtDate } from "@/lib/format";
import SettingsSheet from "./SettingsSheet";

export default function TopBar() {
  const { asOf, setAsOf, apiOnline } = useStore();
  const [open, setOpen] = useState(false);
  const [clock, setClock] = useState(false);
  return (
    <header className="sticky top-0 z-30 px-4 pt-3 pb-2" style={{ background: "color-mix(in srgb, var(--bg) 88%, transparent)", backdropFilter: "blur(10px)" }}>
      <div className="flex items-center justify-between">
        <div className="flex items-baseline gap-2">
          <span className="text-[22px] font-bold tracking-tight">FINN</span>
          <span className="text-[11px] faint">{apiOnline === false ? "snapshot mode" : apiOnline ? "live" : ""}</span>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => setClock((v) => !v)} className={`chip press ${asOf ? "chip-warn" : ""}`} aria-label="Simulated clock">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" strokeLinecap="round" /></svg>
            {asOf ? `as of ${fmtDate(asOf, true)}` : "now"}
          </button>
          <button onClick={() => setOpen(true)} className="chip press" aria-label="Settings">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M4 7h16M4 12h16M4 17h16" strokeLinecap="round" /><circle cx="9" cy="7" r="2" fill="var(--surface)" /><circle cx="15" cy="12" r="2" fill="var(--surface)" /><circle cx="8" cy="17" r="2" fill="var(--surface)" /></svg>
            Tune
          </button>
        </div>
      </div>
      {clock && (
        <div className="card mt-2 p-3 fade-in">
          <div className="text-[12px] font-medium">Simulated clock</div>
          <div className="text-[11px] muted mb-2">Rewind the app to any moment to see what it would have pushed then. Digest, alerts and prices all follow it.</div>
          <div className="flex items-center gap-2">
            <input type="datetime-local" className="flex-1 text-[13px] rounded-lg px-2 py-1.5" style={{ background: "var(--surface-2)", border: "1px solid var(--line)" }}
              value={asOf ? asOf.slice(0, 16) : ""} onChange={(e) => setAsOf(e.target.value ? `${e.target.value}:00` : null)} />
            <button className="chip press" onClick={() => { setAsOf(null); setClock(false); }}>Live</button>
          </div>
          <div className="flex gap-1.5 mt-2 overflow-x-auto no-scrollbar">
            {[["Results week", "2026-10-23T20:00:00"], ["Eternal M&A day", "2026-10-22T09:00:00"], ["Bajaj QIP", "2026-11-12T09:00:00"], ["HDFC mgmt", "2026-11-07T09:00:00"]].map(([l, v]) => (
              <button key={v} className="chip press whitespace-nowrap" onClick={() => { setAsOf(v); setClock(false); }}>{l}</button>
            ))}
          </div>
        </div>
      )}
      <SettingsSheet open={open} onClose={() => setOpen(false)} />
    </header>
  );
}
