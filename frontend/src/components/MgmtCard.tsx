import type { Enrich } from "@/lib/types";
import { cls } from "@/lib/format";

type M = Extract<Enrich, { kind: "management_change" }>;

export default function MgmtCard({ e }: { e: M }) {
  if (!e.ok || !e.changes?.length) return <div className="text-[12px] faint mt-2">Couldn&apos;t extract who is in or out — open the filing.</div>;
  return (
    <div className="mt-3 flex flex-col gap-2">
      {e.changes.map((c, i) => (
        <div key={i} className="rounded-xl p-2.5" style={{ background: "var(--surface-2)" }}>
          <div className="flex items-center justify-between gap-2">
            <div className="text-[13px] font-semibold">{c.person}</div>
            <span className={cls("chip", c.direction === "in" ? "chip-up" : c.direction === "out" ? "chip-down" : "")}>{c.direction === "in" ? "Incoming" : c.direction === "out" ? "Outgoing" : "Re-appointed"}</span>
          </div>
          <div className="text-[12px] muted">{c.role || "Role not stated"}{c.effective ? ` · effective ${c.effective}` : ""}{c.reason ? ` · ${c.reason}` : ""}</div>
          {c.bio && (
            <div className="mt-2 text-[12px] leading-snug">
              {c.bio.text}
              <div className="text-[10px] faint mt-1">{c.bio.label}{c.bio.sources?.[0] && <> · <a className="underline" href={c.bio.sources[0].url} target="_blank" rel="noreferrer">{c.bio.sources[0].title?.slice(0, 40)}</a></>}</div>
            </div>
          )}
          {!c.bio && c.direction !== "out" && <div className="text-[10px] faint mt-1.5">Background lookup needs a web-search key — not configured in this build.</div>}
        </div>
      ))}
      <div className="text-[10px] faint">{e.method}</div>
    </div>
  );
}
