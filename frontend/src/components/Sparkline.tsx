export default function Sparkline({ data, w = 72, h = 22, tone }: { data: (number | null)[]; w?: number; h?: number; tone?: "up" | "down" | "neutral" }) {
  const pts = data.filter((x): x is number => x !== null && x !== undefined);
  if (pts.length < 2) return <svg width={w} height={h} />;
  const min = Math.min(...pts), max = Math.max(...pts), span = max - min || 1;
  const step = w / (pts.length - 1);
  const d = pts.map((v, i) => `${i === 0 ? "M" : "L"}${(i * step).toFixed(1)},${(h - 2 - ((v - min) / span) * (h - 4)).toFixed(1)}`).join(" ");
  const color = tone === "up" ? "var(--up)" : tone === "down" ? "var(--down)" : "var(--ink-3)";
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} aria-hidden>
      <path d={d} fill="none" stroke={color} strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

export function Bars({ data, w = 120, h = 28, labels }: { data: (number | null)[]; w?: number; h?: number; labels?: string[] }) {
  const vals = data.map((x) => x ?? 0);
  const max = Math.max(...vals.map(Math.abs), 1);
  const bw = w / vals.length;
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} aria-label={labels?.join(", ")}>
      {vals.map((v, i) => {
        const bh = (Math.abs(v) / max) * (h - 2);
        const y = v >= 0 ? h - bh : 0;
        return <rect key={i} x={i * bw + 1.5} y={v >= 0 ? y : h / 2} width={Math.max(2, bw - 3)} height={Math.max(1, v >= 0 ? bh : bh / 2)} rx="1.5" fill={v >= 0 ? "var(--accent)" : "var(--down)"} opacity={i === vals.length - 1 ? 1 : 0.55} />;
      })}
    </svg>
  );
}
