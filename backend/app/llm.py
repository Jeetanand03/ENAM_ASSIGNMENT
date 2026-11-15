"""Model router with cache + cost log.

Tiers:  "cheap"  -> Gemini Flash (free tier) or Claude Haiku   — extraction, classification, one-liners
        "strong" -> Claude Sonnet                              — verdicts, bull/bear narration
Cache key = sha256(prompt_version + model tier + prompt). A hit costs nothing and is logged as cached.
With no API key configured, `complete()` returns None and callers fall back to rules / cached snapshots —
the demo never depends on a live model.
"""
from __future__ import annotations
import hashlib, json, logging, re
from datetime import datetime, timezone
from . import config, db

log = logging.getLogger("finn.llm")

# USD per 1M tokens (input, output) — used only for the cost table in the README.
PRICES = {
    "groq/llama-3.3-70b-versatile": (0.0, 0.0),  # free tier (list price 0.59/0.79 on the paid tier)
    "gemini-2.5-flash": (0.30, 2.50), "claude-haiku-4-5": (1.00, 5.00), "claude-sonnet-4-5": (3.00, 15.00),
}
MODELS = {"cheap": ["gemini-2.5-flash", "groq/llama-3.3-70b-versatile", "claude-haiku-4-5"],
          "strong": ["claude-sonnet-4-5", "groq/llama-3.3-70b-versatile", "gemini-2.5-flash"]}


def available() -> dict:
    return {"gemini": bool(config.GEMINI_API_KEY), "groq": bool(config.GROQ_API_KEY), "anthropic": bool(config.ANTHROPIC_API_KEY)}


def _pick(tier: str) -> str | None:
    for m in MODELS[tier]:
        if m.startswith("gemini") and config.GEMINI_API_KEY:
            return m
        if m.startswith("groq/") and config.GROQ_API_KEY:
            return m
        if m.startswith("claude") and config.ANTHROPIC_API_KEY:
            return m
    return None


def _call(model: str, system: str, prompt: str, max_tokens: int) -> tuple[str, int, int]:
    if model.startswith("groq/"):  # OpenAI-compatible endpoint, free tier
        from .sources.http import client
        r = client().post("https://api.groq.com/openai/v1/chat/completions",
                          headers={"Authorization": f"Bearer {config.GROQ_API_KEY}"},
                          json={"model": model.split("/", 1)[1], "temperature": 0, "max_tokens": max_tokens,
                                "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}]})
        r.raise_for_status(); j = r.json(); u = j.get("usage", {})
        return j["choices"][0]["message"]["content"] or "", int(u.get("prompt_tokens", 0)), int(u.get("completion_tokens", 0))
    if model.startswith("gemini"):
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=config.GEMINI_API_KEY)
        r = client.models.generate_content(model=model, contents=prompt,
                                           config=types.GenerateContentConfig(system_instruction=system, max_output_tokens=max_tokens, temperature=0))
        u = r.usage_metadata
        return r.text or "", int(u.prompt_token_count or 0), int(u.candidates_token_count or 0)
    import anthropic
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    r = client.messages.create(model=model, max_tokens=max_tokens, temperature=0, system=system,
                               messages=[{"role": "user", "content": prompt}])
    return "".join(b.text for b in r.content if getattr(b, "type", "") == "text"), r.usage.input_tokens, r.usage.output_tokens


def _log(symbol: str | None, task: str, model: str, i: int, o: int, cached: bool) -> None:
    p = PRICES.get(model, (0, 0))
    usd = 0.0 if cached else (i * p[0] + o * p[1]) / 1e6
    with db.tx() as c:
        c.execute("INSERT INTO cost_log(ts,symbol,task,model,in_tokens,out_tokens,usd,cached) VALUES(?,?,?,?,?,?,?,?)",
                  (datetime.now(timezone.utc).isoformat(), symbol, task, model, i, o, usd, int(cached)))


def complete(task: str, system: str, prompt: str, tier: str = "cheap", symbol: str | None = None,
             prompt_version: str = "v1", max_tokens: int = 1500) -> str | None:
    key = hashlib.sha256(f"{prompt_version}|{tier}|{system}|{prompt}".encode()).hexdigest()
    hit = db.one("SELECT output, model, in_tokens, out_tokens FROM llm_cache WHERE key=?", (key,))
    if hit:
        _log(symbol, task, hit["model"], hit["in_tokens"] or 0, hit["out_tokens"] or 0, cached=True)
        return hit["output"]
    model = _pick(tier)
    if not model or config.OFFLINE:
        return None
    try:
        out, i, o = _call(model, system, prompt, max_tokens)
    except Exception as e:
        log.warning("llm call failed (%s/%s): %s", task, model, e)
        return None
    with db.tx() as c:
        c.execute("INSERT OR REPLACE INTO llm_cache VALUES(?,?,?,?,?,?,?)",
                  (key, model, prompt_version, out, i, o, datetime.now(timezone.utc).isoformat()))
    _log(symbol, task, model, i, o, cached=False)
    return out


def complete_json(task: str, system: str, prompt: str, **kw):
    out = complete(task, system + "\nRespond with a single JSON object and nothing else.", prompt, **kw)
    if not out:
        return None
    m = re.search(r"\{.*\}", out, re.S)
    try:
        return json.loads(m.group(0) if m else out)
    except Exception:
        return None


def cost_summary() -> dict:
    tot = db.one("SELECT COUNT(*) n, COALESCE(SUM(usd),0) usd, COALESCE(SUM(in_tokens),0) i, COALESCE(SUM(out_tokens),0) o, "
                 "COALESCE(SUM(cached),0) cached FROM cost_log") or {}
    by_sym = db.rows("SELECT symbol, COUNT(*) calls, ROUND(SUM(usd),4) usd, SUM(in_tokens) in_tokens, SUM(out_tokens) out_tokens "
                     "FROM cost_log WHERE cached=0 GROUP BY symbol ORDER BY usd DESC")
    return {"total": tot, "by_symbol": by_sym, "providers": available()}
