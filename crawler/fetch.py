"""Höflicher HTTP-Fetch (stdlib): eigener User-Agent, gzip, On-Disk-Cache, Rate-Limit."""
from __future__ import annotations

import gzip
import hashlib
import os
import time
import urllib.request
import urllib.error

CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "cache")
# Default: schlanker Bot-UA (meinestadt/lipzkidz akzeptieren nur diesen, blocken Chrome).
UA = "EventBot/0.1 (+Familien-Events Leipzig; Kontakt: admin@example.org)"
# Browser-UA nur für Quellen, die Bot-UAs abweisen (urbanite, l-iz …) – per source "ua":"browser".
BROWSER_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
_last_request = {}          # host -> timestamp (einfaches Rate-Limit)
MIN_INTERVAL = 1.0          # Sekunden pro Host


def _host(url: str) -> str:
    return url.split("/")[2] if "://" in url else url


def _throttle(url: str):
    h = _host(url)
    dt = time.time() - _last_request.get(h, 0)
    if dt < MIN_INTERVAL:
        time.sleep(MIN_INTERVAL - dt)
    _last_request[h] = time.time()


def get(url: str, timeout: int = 20, use_cache: bool = True,
        max_age: int = 6 * 3600, extra_headers: dict | None = None,
        ua: str | None = None) -> str | None:
    """Lädt eine URL als Text. Nutzt einen Datei-Cache (Default 6h).

    extra_headers: zusätzliche Request-Header (z. B. X-Requested-With für JSON-APIs).
    ua: User-Agent-Override (z. B. BROWSER_UA für Bot-blockende Quellen). Fließt in
        den Cache-Key ein, damit UA-Varianten getrennt gecacht werden.
    """
    os.makedirs(CACHE_DIR, exist_ok=True)
    key = hashlib.sha1((url + "|" + (ua or "")).encode()).hexdigest()
    path = os.path.join(CACHE_DIR, key)
    if use_cache and os.path.exists(path):
        if time.time() - os.path.getmtime(path) < max_age:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                return f.read()

    _throttle(url)
    headers = {
        "User-Agent": ua or UA,
        "Accept": "text/html,application/xhtml+xml,application/json,*/*",
        "Accept-Encoding": "gzip",
        "Accept-Language": "de,en;q=0.7",
    }
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            if resp.headers.get("Content-Encoding") == "gzip":
                raw = gzip.decompress(raw)
            text = raw.decode("utf-8", errors="replace")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError,
            ConnectionError, OSError) as e:
        print(f"    [fetch] Fehler {url}: {e}")
        return None

    if use_cache:
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
    return text
