"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cls } from "@/lib/format";

const tabs = [
  { href: "/", label: "Feed", icon: (a: boolean) => (<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={a ? 2.2 : 1.8}><path d="M4 6h16M4 12h16M4 18h10" strokeLinecap="round" /></svg>) },
  { href: "/research", label: "Research", icon: (a: boolean) => (<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={a ? 2.2 : 1.8}><circle cx="11" cy="11" r="6.5" /><path d="M16 16l4 4" strokeLinecap="round" /></svg>) },
  { href: "/alerts", label: "Alerts", icon: (a: boolean) => (<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={a ? 2.2 : 1.8}><path d="M6 16V11a6 6 0 1112 0v5l1.5 2h-15L6 16z" strokeLinejoin="round" /><path d="M10 20a2 2 0 004 0" /></svg>) },
];

export default function TabBar() {
  const path = usePathname();
  return (
    <nav className="fixed bottom-0 inset-x-0 z-40">
      <div className="mx-auto max-w-[520px] safe-b" style={{ background: "var(--surface)", borderTop: "1px solid var(--line)" }}>
        <div className="grid grid-cols-3 h-14">
          {tabs.map((t) => {
            const active = t.href === "/" ? path === "/" || path.startsWith("/company") : path.startsWith(t.href);
            return (
              <Link key={t.href} href={t.href} className={cls("flex flex-col items-center justify-center gap-0.5 text-[11px] press", active ? "" : "faint")} style={active ? { color: "var(--accent)" } : undefined}>
                {t.icon(active)}
                <span className={active ? "font-semibold" : "font-medium"}>{t.label}</span>
              </Link>
            );
          })}
        </div>
      </div>
    </nav>
  );
}
