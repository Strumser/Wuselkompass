"""Gesundheit der Quellen: Ampel aus den Crawl-Messwerten (source_runs) und der
Erreichbarkeitsprüfung (source_checks). Reine Regeln, keine KI.

Ampel:
  rot    – liefert nichts / Seite nicht erreichbar / Termine stark eingebrochen / viele Abruffehler
  gelb   – auffällig (Rückgang, viele Termine ohne Datum, viele Fehler, lange nicht gelaufen)
  gruen  – unauffällig
  grau   – abgeschaltet
  offen  – noch keine Messung vorhanden
"""
from __future__ import annotations

import json
import statistics
from datetime import datetime, timedelta

from . import fetch

# Schwellen (mit dem Nutzer abgestimmt: Rot < 40 % des üblichen Werts, Gelb < 70 %)
DROP_RED = 0.40
DROP_YELLOW = 0.70
ERR_RED = 0.50
ERR_YELLOW = 0.10
NODATE_YELLOW = 0.30
STALE_DAYS = 3


def _rows(conn, sql, args=()):
    return [dict(r) for r in conn.execute(sql, args).fetchall()]


def evaluate(conn, cfg: dict, now: datetime | None = None) -> list[dict]:
    """Liefert je Quelle (in sources.json-Reihenfolge) Status + Begründungen + Verlauf."""
    now = now or datetime.now()
    out = []
    for src in cfg["sources"]:
        sid = src["id"]
        runs = _rows(conn, "SELECT * FROM source_runs WHERE source_id=? ORDER BY run_at DESC LIMIT 10", (sid,))
        chk = _rows(conn, "SELECT * FROM source_checks WHERE source_id=? ORDER BY checked_at DESC LIMIT 1", (sid,))
        chk = chk[0] if chk else None
        last = runs[0] if runs else None
        history = [r["found"] or 0 for r in reversed(runs)]
        reasons: list[str] = []
        level = 0                       # 0 grün, 1 gelb, 2 rot

        def flag(lv: int, text: str):
            nonlocal level
            level = max(level, lv)
            reasons.append(text)

        active = src.get("active", True)
        if not active:
            out.append(_pack(src, "grau", ["abgeschaltet"], last, chk, history))
            continue

        newest_check_is_after_run = bool(chk and (not last or chk["checked_at"] > last["run_at"]))
        if chk and newest_check_is_after_run and (chk["http"] is None or chk["http"] >= 400):
            flag(2, f"Seite nicht erreichbar ({'HTTP ' + str(chk['http']) if chk['http'] else chk['note'] or 'keine Antwort'})")

        if last is None:
            if not reasons:
                out.append(_pack(src, "offen", ["noch keine Messung"], last, chk, history))
                continue
        else:
            found = last["found"] or 0
            prev = [r["found"] or 0 for r in runs[1:6]]
            base = statistics.median(prev) if prev else None
            if found == 0:
                if src.get("allow_empty"):
                    flag(1, "keine Termine (laut Konfiguration erwartet)")
                else:
                    flag(2, "liefert 0 Termine" + (f" (sonst ca. {int(base)})" if base else ""))
            elif base and base > 0:
                if found < DROP_RED * base:
                    flag(2, f"Termine eingebrochen: {found} statt ca. {int(base)}")
                elif found < DROP_YELLOW * base:
                    flag(1, f"weniger Termine als üblich: {found} statt ca. {int(base)}")
            reqs, errs = last.get("requests") or 0, last.get("errors") or 0
            if reqs and errs:
                share = errs / reqs
                try:
                    codes = json.loads(last.get("error_codes") or "{}")
                except ValueError:
                    codes = {}
                code_txt = ", ".join(f"{c}×{n}" for c, n in sorted(codes.items(), key=lambda x: -x[1]))
                txt = f"{errs} von {reqs} Abrufen fehlgeschlagen ({code_txt})"
                if share > ERR_RED:
                    flag(2, txt)
                elif share >= ERR_YELLOW:
                    flag(1, txt)
            if found and (last.get("nodate") or 0) / max(found, 1) >= NODATE_YELLOW:
                flag(1, f"{last['nodate']} Einträge ohne Datum")
            try:
                age = now - datetime.fromisoformat(last["run_at"])
                if age > timedelta(days=STALE_DAYS):
                    flag(1, f"letzter Lauf vor {age.days} Tagen")
            except ValueError:
                pass
        out.append(_pack(src, ["gruen", "gelb", "rot"][level], reasons or ["in Ordnung"], last, chk, history))
    return out


def _pack(src, status, reasons, last, chk, history):
    return {"id": src["id"], "type": src.get("type"), "active": src.get("active", True),
            "check": bool(src.get("check")), "scope": src.get("scope"), "region": src.get("region", "leipzig"),
            "url": src.get("url") or src.get("base") or src.get("api") or "", "note": src.get("note", ""),
            "status": status, "reasons": reasons, "last": last, "check_row": chk, "history": history}


# ------------------------------------------------------------------ Erreichbarkeitsprüfung
def _probe_url(src: dict) -> str | None:
    return src.get("probe_url") or src.get("url") or src.get("base") or src.get("api")


def check_all(cfg: dict, only: list[str] | None = None, workers: int = 10) -> list[dict]:
    """Ruft je aktiver Quelle EINMAL die Einstiegsadresse ab (ohne Cache) und meldet HTTP-Status.
    Quellen derselben Webseite laufen nacheinander (Pause pro Host), verschiedene parallel."""
    from concurrent.futures import ThreadPoolExecutor
    groups: dict[str, list[dict]] = {}
    for src in cfg["sources"]:
        if not src.get("active", True) or (only and src["id"] not in only):
            continue
        url = _probe_url(src)
        if not url:
            continue
        host = url.split("/")[2] if "://" in url else url
        groups.setdefault(host, []).append(src)

    def work(group):
        res = []
        for src in group:
            ua = fetch.BROWSER_UA if src.get("ua") == "browser" else None
            r = fetch.probe(_probe_url(src), ua=ua)
            res.append({"source_id": src["id"], **r})
        return res

    rows: list[dict] = []
    if not groups:
        return rows
    with ThreadPoolExecutor(max_workers=min(workers, len(groups))) as pool:
        for part in pool.map(work, groups.values()):
            rows.extend(part)
    return rows
