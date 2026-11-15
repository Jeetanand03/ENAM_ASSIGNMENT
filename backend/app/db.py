"""Tiny sqlite layer. One file, WAL mode, dict rows."""
from __future__ import annotations
import json, sqlite3, threading
from contextlib import contextmanager
from datetime import datetime, timezone
from .config import DB_PATH

_lock = threading.RLock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS prices (
  symbol TEXT, date TEXT, open REAL, high REAL, low REAL, close REAL, volume INTEGER,
  PRIMARY KEY (symbol, date));
CREATE TABLE IF NOT EXISTS announcements (
  id TEXT PRIMARY KEY, symbol TEXT, ts TEXT, subject TEXT, summary TEXT, category_raw TEXT,
  pdf_url TEXT, category TEXT, category_source TEXT, score INTEGER, score_parts TEXT, tier TEXT,
  headline TEXT, enrich TEXT);
CREATE INDEX IF NOT EXISTS ann_sym_ts ON announcements(symbol, ts);
CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY CHECK (id=1), json TEXT);
CREATE TABLE IF NOT EXISTS kv (k TEXT PRIMARY KEY, v TEXT, ts TEXT);
CREATE TABLE IF NOT EXISTS llm_cache (key TEXT PRIMARY KEY, model TEXT, prompt_version TEXT, output TEXT,
  in_tokens INTEGER, out_tokens INTEGER, ts TEXT);
CREATE TABLE IF NOT EXISTS cost_log (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, symbol TEXT, task TEXT,
  model TEXT, in_tokens INTEGER, out_tokens INTEGER, usd REAL, cached INTEGER);
"""

_con: sqlite3.Connection | None = None


def con() -> sqlite3.Connection:
    global _con
    if _con is None:
        c = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        c.executescript(SCHEMA)
        _con = c
    return _con


@contextmanager
def tx():
    with _lock:
        c = con()
        try:
            yield c
            c.commit()
        except Exception:
            c.rollback()
            raise


def rows(sql: str, params=()) -> list[dict]:
    with _lock:
        return [dict(r) for r in con().execute(sql, params).fetchall()]


def one(sql: str, params=()) -> dict | None:
    r = rows(sql, params)
    return r[0] if r else None


def kv_get(k: str, default=None):
    r = one("SELECT v FROM kv WHERE k=?", (k,))
    return json.loads(r["v"]) if r else default


def kv_set(k: str, v) -> None:
    with tx() as c:
        c.execute("INSERT OR REPLACE INTO kv(k,v,ts) VALUES(?,?,?)",
                  (k, json.dumps(v, ensure_ascii=False), datetime.now(timezone.utc).isoformat()))
