"""Single-user settings row (alert thresholds, starred categories, digest window)."""
from __future__ import annotations
import json
from .config import DEFAULT_SETTINGS
from . import db


def get() -> dict:
    r = db.one("SELECT json FROM settings WHERE id=1")
    s = dict(DEFAULT_SETTINGS)
    if r:
        s.update(json.loads(r["json"]))
    return s


def update(patch: dict) -> dict:
    s = get()
    for k, v in patch.items():
        if k in DEFAULT_SETTINGS:
            s[k] = v
    with db.tx() as c:
        c.execute("INSERT OR REPLACE INTO settings(id,json) VALUES(1,?)", (json.dumps(s),))
    return s
