"""live -> cache -> snapshot. Every external fetch goes through `fetch_with_fallback`.

A *snapshot* is a committed JSON file in data/snapshots/ so the demo runs with no network.
A *cache* is the sqlite kv table (fresh for `ttl` seconds).
"""
from __future__ import annotations
import json, logging, time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Any
from .config import SNAPSHOT_DIR, OFFLINE, SNAPSHOT_FIRST
from . import db

log = logging.getLogger("finn.cache")


def snapshot_path(name: str) -> Path:
    return SNAPSHOT_DIR / f"{name}.json"


def read_snapshot(name: str) -> Any | None:
    p = snapshot_path(name)
    if p.exists():
        try:
            obj = json.loads(p.read_text(encoding="utf-8"))
            return obj.get("data", obj) if isinstance(obj, dict) else obj
        except Exception as e:  # a corrupt file must never kill the demo
            log.warning("bad snapshot %s: %s", name, e)
    return None


def write_snapshot(name: str, data: Any) -> None:
    try:  # read-only filesystem on serverless: the snapshot set is whatever was committed
        p = snapshot_path(name)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"_saved_at": datetime.now(timezone.utc).isoformat(), "data": data},
                                ensure_ascii=False), encoding="utf-8")
    except OSError as e:
        log.info("snapshot not written (%s): %s", name, e)


def fetch_with_fallback(name: str, live: Callable[[], Any], ttl: int = 3600,
                        save_snapshot: bool = True) -> tuple[Any, str]:
    """Returns (data, source) where source in {'cache','live','snapshot','none'}."""
    cached = db.kv_get(f"cache:{name}")
    now = time.time()
    if cached and now - cached.get("t", 0) < ttl:
        return cached["data"], "cache"
    if SNAPSHOT_FIRST and not cached:
        snap = read_snapshot(name)
        if snap is not None:
            db.kv_set(f"cache:{name}", {"t": now, "data": snap})
            return snap, "snapshot"
    if not OFFLINE:
        try:
            data = live()
            if data is not None:
                db.kv_set(f"cache:{name}", {"t": now, "data": data})
                if save_snapshot:
                    write_snapshot(name, data)
                return data, "live"
        except Exception as e:
            log.warning("live fetch failed for %s: %s", name, e)
    if cached:
        return cached["data"], "cache"
    snap = read_snapshot(name)
    if snap is not None:
        return snap, "snapshot"
    return None, "none"
