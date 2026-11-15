"use client";
import { useEffect, useState } from "react";
import { useStore } from "@/lib/store";
import { CATEGORIES, CATEGORY_LABEL, cls } from "@/lib/format";

export default function SettingsSheet({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { settings, saveSettings } = useStore();
  const [vol, setVol] = useState(2); const [px, setPx] = useState(4); const [starred, setStarred] = useState<string[]>([]);
  useEffect(() => { if (settings) { setVol(settings.volume_multiple); setPx(settings.price_move_pct); setStarred(settings.starred_categories); } }, [settings, open]);
  if (!open) return null;
  const toggle = (c: string) => setStarred((s) => (s.includes(c) ? s.filter((x) => x !== c) : [...s, c]));
  const save = async () => { await saveSettings({ volume_multiple: vol, price_move_pct: px, starred_categories: starred }); onClose(); };
  return (
    <div className="fixed inset-0 z-50 flex items-end" style={{ background: "rgba(0,0,0,0.35)" }} onClick={onClose}>
      <div className="sheet w-full max-w-[520px] mx-auto p-4 pb-8 fade-in" onClick={(e) => e.stopPropagation()}>
        <div className="mx-auto w-10 h-1 rounded-full mb-3" style={{ background: "var(--line)" }} />
        <div className="text-[15px] font-semibold">What counts as unusual</div>
        <div className="text-[12px] muted mb-4">You decide the thresholds. FINN watches for them and re-ranks the feed.</div>

        <label className="block mb-4">
          <div className="flex justify-between text-[13px]"><span>Volume spike</span><span className="num font-semibold">{vol.toFixed(1)}× 20-day avg</span></div>
          <input type="range" min={1.2} max={5} step={0.1} value={vol} onChange={(e) => setVol(parseFloat(e.target.value))} className="w-full" />
        </label>
        <label className="block mb-5">
          <div className="flex justify-between text-[13px]"><span>Daily price move</span><span className="num font-semibold">±{px.toFixed(1)}%</span></div>
          <input type="range" min={1} max={12} step={0.5} value={px} onChange={(e) => setPx(parseFloat(e.target.value))} className="w-full" />
        </label>

        <div className="text-[13px] mb-1">Filing types you care about <span className="faint">(+20 priority, always alert)</span></div>
        <div className="flex flex-wrap gap-1.5 mb-5">
          {CATEGORIES.map((c) => (
            <button key={c} onClick={() => toggle(c)} className={cls("chip press", starred.includes(c) && "chip-accent")}>{starred.includes(c) ? "★ " : ""}{CATEGORY_LABEL[c]}</button>
          ))}
        </div>
        <div className="flex gap-2">
          <button onClick={onClose} className="flex-1 rounded-xl py-2.5 text-[14px] font-medium press" style={{ background: "var(--surface-2)" }}>Cancel</button>
          <button onClick={save} className="flex-1 rounded-xl py-2.5 text-[14px] font-semibold text-white press" style={{ background: "var(--accent)" }}>Save</button>
        </div>
      </div>
    </div>
  );
}
