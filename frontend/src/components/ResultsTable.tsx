import type { Enrich } from "@/lib/types";
import { cls, fmtNum, fmtPct } from "@/lib/format";

type R = Extract<Enrich, { kind: "results"; ok: true }>;

function Delta({ v }: { v: number | null }) {
  if (v === null || v === undefined) return <span className="faint">—</span>;
  return <span className={cls("num font-medium", v > 0 ? "up" : v < 0 ? "down" : "muted")}>{fmtPct(v, 0)}</span>;
}

export default function ResultsTable({ e }: { e: R }) {
  const { rows, labels } = e.table;
  return (
    <div className="mt-3">
      <div className="flex items-baseline justify-between mb-1">
        <div className="text-[12px] font-semibold">First cut · {labels.current}</div>
        <div className="text-[10px] faint">{e.basis} · {e.unit}</div>
      </div>
      <div className="rounded-xl overflow-hidden" style={{ border: "1px solid var(--line)" }}>
        <table className="w-full text-[12px] num">
          <thead>
            <tr style={{ background: "var(--surface-2)" }} className="text-[10px] faint">
              <th className="text-left font-medium px-2.5 py-1.5"></th>
              <th className="text-right font-medium px-2 py-1.5">{labels.current}</th>
              <th className="text-right font-medium px-2 py-1.5">QoQ</th>
              <th className="text-right font-medium px-2.5 py-1.5">YoY</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.key} style={{ borderTop: "1px solid var(--line)" }}>
                <td className="px-2.5 py-1.5 font-medium">
                  {r.label}{r.derived && <span className="faint font-normal"> (derived)</span>}
                  {r.margin !== null && r.key !== "revenue" && <div className="text-[10px] faint font-normal">{r.margin.toFixed(1)}% margin{r.margin_ya !== null && <span> · {(r.margin - r.margin_ya) > 0 ? "+" : ""}{(r.margin - r.margin_ya).toFixed(1)}pp YoY</span>}</div>}
                </td>
                <td className="text-right px-2 py-1.5">{fmtNum(r.current)}</td>
                <td className="text-right px-2 py-1.5"><Delta v={r.qoq} /></td>
                <td className="text-right px-2.5 py-1.5"><Delta v={r.yoy} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="text-[13px] mt-2 leading-snug">{e.takeaway}</div>
      {e.notes && <div className="text-[11px] muted mt-1">{e.notes}</div>}
      <div className="text-[10px] faint mt-1.5">
        {e.method}{e.source?.url ? <> · <a className="underline" href={e.source.url} target="_blank" rel="noreferrer">{e.source.kind}</a></> : null} · QoQ/YoY computed in code
      </div>
    </div>
  );
}
