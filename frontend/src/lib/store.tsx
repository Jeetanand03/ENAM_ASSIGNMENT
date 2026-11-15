"use client";
/** App-wide state: the simulated "as of" clock, settings, and the API reachability flag. */
import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { apiGet, apiPut, warm } from "./api";
import type { Settings } from "./types";

type Store = {
  asOf: string | null;             // ISO; null = live now
  setAsOf: (v: string | null) => void;
  asOfParam: string;               // query param value to send
  settings: Settings | null;
  saveSettings: (p: Partial<Settings>) => Promise<void>;
  apiOnline: boolean | null;
  nowISO: () => string;
};

const Ctx = createContext<Store | null>(null);
const DEFAULTS: Settings = { volume_multiple: 2, price_move_pct: 4, starred_categories: ["results", "M&A", "management_change"], digest_window: "24h" };

function localISO(d: Date) {
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}:00`;
}

export function StoreProvider({ children }: { children: React.ReactNode }) {
  const [asOf, setAsOfState] = useState<string | null>(null);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [apiOnline, setApiOnline] = useState<boolean | null>(null);

  useEffect(() => {
    warm();
    try {
      const saved = localStorage.getItem("finn.asOf");
      if (saved) setAsOfState(saved);
    } catch {}
    apiGet<Settings>("/api/settings").then(({ data, source }) => { setSettings({ ...DEFAULTS, ...data }); setApiOnline(source === "api"); })
      .catch(() => { setSettings(DEFAULTS); setApiOnline(false); });
  }, []);

  const setAsOf = useCallback((v: string | null) => {
    setAsOfState(v);
    try { v ? localStorage.setItem("finn.asOf", v) : localStorage.removeItem("finn.asOf"); } catch {}
  }, []);

  const saveSettings = useCallback(async (p: Partial<Settings>) => {
    setSettings((s) => ({ ...(s || DEFAULTS), ...p }));
    try { const s = await apiPut<Settings>("/api/settings", p); setSettings({ ...DEFAULTS, ...s }); } catch {}
  }, []);

  const nowISO = useCallback(() => asOf || localISO(new Date()), [asOf]);
  const value = useMemo<Store>(() => ({ asOf, setAsOf, asOfParam: asOf || localISO(new Date()), settings, saveSettings, apiOnline, nowISO }),
    [asOf, setAsOf, settings, saveSettings, apiOnline, nowISO]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useStore() {
  const s = useContext(Ctx);
  if (!s) throw new Error("StoreProvider missing");
  return s;
}
