/** API client. Every GET falls back to a static JSON baked into /public/fallback at build time,
 *  so the demo renders on a phone even if the API host is asleep or offline. */
export const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");

export type Source = "api" | "fallback";

function fallbackKey(path: string): string | null {
  const [p, qs] = path.split("?");
  const q = new URLSearchParams(qs || "");
  if (p === "/api/digest") return `digest_${q.get("window") || "24h"}`;
  if (p === "/api/portfolio") return "portfolio";
  if (p === "/api/alerts") return "alerts";
  if (p === "/api/settings") return "settings";
  if (p === "/api/health") return "health";
  if (p === "/api/cost") return "cost";
  const m = p.match(/^\/api\/(research|company|prices)\/([A-Z0-9&-]+)$/i);
  if (m) return `${m[1]}_${m[2].toUpperCase()}`;
  const e = p.match(/^\/api\/announcements\/([a-z0-9]+)\/enrich$/i);
  if (e) return `enrich_${e[1]}`;
  return null;
}

export async function apiGet<T>(path: string, init?: RequestInit & { timeoutMs?: number }): Promise<{ data: T; source: Source }> {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), init?.timeoutMs ?? 12000);
  try {
    const r = await fetch(`${API_URL}${path}`, { ...init, signal: ctrl.signal, cache: "no-store" });
    if (!r.ok) throw new Error(`${r.status}`);
    return { data: (await r.json()) as T, source: "api" };
  } catch (err) {
    const key = fallbackKey(path);
    if (key) {
      const r = await fetch(`/fallback/${key}.json`, { cache: "force-cache" });
      if (r.ok) return { data: (await r.json()) as T, source: "fallback" };
    }
    throw err;
  } finally {
    clearTimeout(t);
  }
}

export async function apiPut<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(`${API_URL}${path}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  if (!r.ok) throw new Error(`${r.status}`);
  return (await r.json()) as T;
}

/** Wake a sleeping free-tier API host early. */
export function warm() {
  if (typeof window !== "undefined") fetch(`${API_URL}/api/health`, { cache: "no-store" }).catch(() => {});
}
