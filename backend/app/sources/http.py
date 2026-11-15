"""One browser-like httpx client shared by all scrapers."""
from __future__ import annotations
import httpx

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
BASE_HEADERS = {"User-Agent": UA, "Accept": "*/*", "Accept-Language": "en-US,en;q=0.9"}

_client: httpx.Client | None = None


def client() -> httpx.Client:
    global _client
    if _client is None:
        _client = httpx.Client(headers=BASE_HEADERS, timeout=httpx.Timeout(40.0, connect=15.0),
                               follow_redirects=True)
    return _client


def get(url: str, **kw) -> httpx.Response:
    r = client().get(url, **kw)
    r.raise_for_status()
    return r
