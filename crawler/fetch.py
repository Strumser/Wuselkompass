"""Höflicher HTTP-Fetch (stdlib): eigener User-Agent, gzip, On-Disk-Cache, Rate-Limit."""
from __future__ import annotations

import gzip
import hashlib
import os
import threading
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
_lock = threading.Lock()    # Rate-Limit ist threadsicher (parallele Quellen)

# --- Messwerte je Quelle (für die Gesundheitsampel) -----------------------------
_ctx = threading.local()    # welche Quelle ruft gerade ab (pro Thread)
_stats: dict = {}
_stats_lock = threading.Lock()


def set_source(sid: str | None):
    """Merkt sich die aktuelle Quelle dieses Threads; Abrufe/Fehler werden ihr zugerechnet."""
    _ctx.sid = sid


def _count(kind: str, code=None, url: str | None = None):
    sid = getattr(_ctx, "sid", None) or "?"
    with _stats_lock:
        st = _stats.setdefault(sid, {"requests": 0, "errors": 0, "codes": {}, "sample": None})
        if kind == "req":
            st["requests"] += 1
        else:
            st["errors"] += 1
            st["codes"][str(code)] = st["codes"].get(str(code), 0) + 1
            if st["sample"] is None:
                st["sample"] = f"{code}: {url}"


def pop_stats(sid: str) -> dict:
    with _stats_lock:
        return _stats.pop(sid, {"requests": 0, "errors": 0, "codes": {}, "sample": None})

MIN_INTERVAL = 1.0          # Sekunden pro Host


def _host(url: str) -> str:
    return url.split("/")[2] if "://" in url else url


def _throttle(url: str):
    h = _host(url)
    with _lock:      # Zeitslot reservieren; gewartet wird außerhalb des Locks
        now = time.time()
        wait = max(0.0, _last_request.get(h, 0) + MIN_INTERVAL - now)
        _last_request[h] = now + wait
    if wait:
        time.sleep(wait)


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
    _count("req")
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
        _count("err", getattr(e, "code", None) or type(e).__name__, url)
        return None

    if use_cache:
        tmp = f"{path}.{threading.get_ident()}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)        # atomar: kein halb geschriebener Cache
    return text


def probe(url: str, ua: str | None = None, timeout: int = 15) -> dict:
    """Erreichbarkeitsprüfung: ein einzelner GET (nur die ersten 2 KB gelesen), kein Cache.
    Liefert {"http": Statuscode oder None, "ms": Dauer, "note": Hinweis}."""
    _throttle(url)
    t0 = time.time()
    req = urllib.request.Request(url, headers={
        "User-Agent": ua or UA, "Accept": "text/html,application/json,*/*",
        "Accept-Language": "de,en;q=0.7"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            resp.read(2048)
            return {"http": resp.status, "ms": int((time.time() - t0) * 1000), "note": None}
    except urllib.error.HTTPError as e:
        return {"http": e.code, "ms": int((time.time() - t0) * 1000), "note": str(e.reason)}
    except Exception as e:                                   # keine Antwort (DNS, TLS, Timeout …)
        return {"http": None, "ms": int((time.time() - t0) * 1000),
                "note": f"{type(e).__name__}: {e}"[:160]}
