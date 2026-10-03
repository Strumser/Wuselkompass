"""Orchestrator: liest sources.json, waehlt je Quelle den Extraktor und fuellt die DB.

Aufruf:  python3 -m crawler.run
"""
from __future__ import annotations

import json
import os
import sys

# Projektwurzel importierbar machen (erlaubt "python3 crawler/run.py" und "-m")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crawler import adapters_html, extractors, fetch, pipeline   # noqa: E402
from db import store                                      # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def base_of(url: str) -> str:
    parts = url.split("/")
    return "/".join(parts[:3])


def collect(source: dict) -> list[dict]:
    """Liefert Roh-Events je nach Quellen-Typ. 'auto' nutzt den Fingerprint."""
    typ = source["type"]
    sid = source["id"]
    # UA pro Quelle: Browser-UA nur wo nötig (Bot-blockende Seiten), sonst Default.
    ua = fetch.BROWSER_UA if source.get("ua") == "browser" else None

    if typ == "wp_api":
        return extractors.wp_events_api(source["base"], sid)

    if typ == "rausgegangen":
        return extractors.rausgegangen_api(sid, pages=source.get("pages", 15))

    if typ == "kreuzer":
        return extractors.kreuzer_api(
            sid, ressort=source.get("ressort", "kinder-familie"), ua=ua)

    if typ == "leipziginfo":
        return extractors.leipziginfo_events(sid, ua=ua)

    if typ == "listing_jsonld":
        return extractors.listing_detail_jsonld(
            sid, source["url"], source["link_re"], source["base"],
            limit=source.get("limit", 40), ua=ua)

    if typ == "html":
        parser = adapters_html.PARSERS.get(source["parser"])
        if not parser:
            print(f"    [warn] unbekannter Parser: {source.get('parser')}")
            return []
        pages = source.get("pages", 1)
        base = source["url"]
        evs = []
        for p in range(1, pages + 1):
            url = base if p == 1 else base.rstrip("/") + f"/page/{p}/"
            html_text = fetch.get(url, ua=ua)
            if html_text:
                evs += parser(html_text, sid)
        return evs

    if typ == "jsonld":
        html_text = fetch.get(source["url"])
        return extractors.extract_jsonld(html_text, sid) if html_text else []

    if typ == "ical":
        text = fetch.get(source["url"])
        return extractors.extract_ical(text, sid) if text else []

    if typ == "rss":
        return _collect_rss(source["url"], sid)

    if typ == "auto":
        return _collect_auto(source["url"], sid)

    print(f"    [warn] unbekannter Typ: {typ}")
    return []


def _collect_rss(url: str, sid: str) -> list[dict]:
    """Direkt-Feed oder RSS-Autodiscovery auf einer HTML-Seite."""
    text = fetch.get(url)
    if not text:
        return []
    if "<rss" in text[:500].lower() or "<feed" in text[:500].lower():
        return extractors.extract_rss(text, sid)
    fp = extractors.fingerprint(text)
    for feed in fp["rss_links"]:
        feed_url = feed if feed.startswith("http") else base_of(url) + feed
        feed_text = fetch.get(feed_url)
        if feed_text:
            items = extractors.extract_rss(feed_text, sid)
            if items:
                return items
    return []


def _collect_auto(url: str, sid: str) -> list[dict]:
    """Fingerprint-Autorouting: waehlt den besten Extraktor fuer die Seite."""
    text = fetch.get(url)
    if not text:
        return []
    fp = extractors.fingerprint(text)
    if fp["tribe_events"] and fp["wordpress"]:
        ev = extractors.wp_events_api(base_of(url), sid)
        if ev:
            print(f"    [auto] -> WordPress-Events-API ({len(ev)})")
            return ev
    if fp["has_jsonld"]:
        ev = extractors.extract_jsonld(text, sid)
        if ev:
            print(f"    [auto] -> JSON-LD ({len(ev)})")
            return ev
    if fp["ical_links"]:
        ics = fp["ical_links"][0]
        ics = ics if ics.startswith("http") else base_of(url) + ics
        t = fetch.get(ics)
        if t:
            ev = extractors.extract_ical(t, sid)
            print(f"    [auto] -> iCal ({len(ev)})")
            return ev
    if fp["rss_links"]:
        ev = _collect_rss(url, sid)
        print(f"    [auto] -> RSS ({len(ev)})")
        return ev
    print("    [auto] -> keine Struktur gefunden (LLM-Fallback waere hier noetig)")
    return []


def _crawl():
    store.init_db()
    with open(os.path.join(ROOT, "sources.json"), encoding="utf-8") as f:
        cfg = json.load(f)

    total_raw = total_kept = 0
    report_rows = []
    with store.connect() as conn:
        # Dauer-Locations (venues) laden
        for v in cfg.get("venues_seed", []):
            coord = None
            from crawler import geo
            coord = geo.locate(v.get("address"))
            v = dict(v)
            v["lat"] = coord[0] if coord else None
            v["lon"] = coord[1] if coord else None
            v["distance_km"] = geo.distance_from_leipzig(coord)
            store.upsert_venue(conn, v)

        # Termine (events) crawlen
        for src in cfg["sources"]:
            if not src.get("active", True):
                continue
            print(f"[{src['id']}] ({src['type']}) …")
            try:
                raw = collect(src)
            except Exception as e:                       # eine Quelle darf nicht alles stoppen
                print(f"    [error] {e}")
                report_rows.append({"source_id": src["id"], "raw": 0, "kept": 0,
                                    "past": 0, "radius": 0})
                continue
            kept = past = radius = 0
            fam_default = src.get("family_default", 0.0)
            city = src.get("city")
            for ev in raw:
                if not pipeline.is_future(ev):           # vergangen
                    past += 1
                    continue
                ev["source_family_default"] = fam_default
                ev["source_city"] = city
                enriched = pipeline.enrich(ev)
                if enriched is None:                     # ausserhalb 60 km
                    radius += 1
                    continue
                store.upsert_event(conn, enriched)
                kept += 1
            total_raw += len(raw)
            total_kept += kept
            report_rows.append({"source_id": src["id"], "raw": len(raw), "kept": kept,
                                "past": past, "radius": radius})
            print(f"    roh: {len(raw):4d} | uebernommen: {kept:4d}")

        # Vergangene Termine entfernen – erst löschen, wenn das ENDE vor heute liegt
        # (mehrtägige Veranstaltungen bleiben, solange sie noch laufen).
        from datetime import date
        today = date.today().isoformat()
        conn.execute("DELETE FROM events WHERE start_at<>'' "
                     "AND substr(COALESCE(NULLIF(end_at,''), start_at),1,10) < ?", (today,))

        ev_n, vn_n, by_src = store.stats(conn)

    # Crawl-Bericht als CSV: finale DB-Zahl je Quelle (nach Dedup) ergänzen.
    in_db = {r["source_id"]: r["n"] for r in by_src}
    for row in report_rows:
        row["in_db"] = in_db.get(row["source_id"], 0)
    try:
        from tools import report as _report
        _report.save_crawl_report(report_rows)
        _report.export_events()
    except Exception as e:
        print(f"    [warn] CSV-Export fehlgeschlagen: {e}")

    print("\n" + "=" * 52)
    print(f"Fertig. Roh gesamt: {total_raw} | DB events: {ev_n} | venues: {vn_n}")
    print("Events je Quelle:")
    for r in by_src:
        print(f"  {r['source_id']:24s} {r['n']:4d}")
    return ev_n


def _write_status(state, events=None):
    """Schreibt data/status.json (state: 'running' | 'idle')."""
    from datetime import datetime as _dt
    data = {"state": state, "at": _dt.now().strftime("%Y-%m-%dT%H:%M:%S")}
    if events is not None:
        data["events"] = events
    try:
        with open(os.path.join(ROOT, "data", "status.json"), "w", encoding="utf-8") as f:
            json.dump(data, f)
    except OSError:
        pass


def main():
    _write_status("running")
    events = 0
    try:
        events = _crawl()
    finally:
        _write_status("idle", events)


if __name__ == "__main__":
    main()
