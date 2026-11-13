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


def collect(source: dict) -> list[dict]:
    """Roh-Events einer Quelle; bei `detail_age: true` zusätzlich Detailseiten nach Altersangaben."""
    evs = _collect_raw(source)
    if source.get("detail_age") and evs:
        ua = fetch.BROWSER_UA if source.get("ua") == "browser" else None
        evs = extractors.add_detail_text(source["id"], evs, ua=ua)
    return evs


def base_of(url: str) -> str:
    parts = url.split("/")
    return "/".join(parts[:3])


def _collect_raw(source: dict) -> list[dict]:
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

    if typ == "urbanite_days":
        return extractors.urbanite_days(
            sid, source.get("categories", ["kinder-familie-2"]), ua=ua,
            days=source.get("days", 21),
            nur_bekannte_orte=source.get("nur_bekannte_orte", True))

    if typ == "wp_page_list":
        return extractors.wp_page_list(sid, source["api"], source["url"],
                                       source["venue"], source["address"])

    if typ == "chemnitz_de":
        return extractors.chemnitz_de_events(sid, ua=ua, max_pages=source.get("pages", 20))

    if typ == "czr":
        return extractors.czr_events(sid, ua=ua)

    if typ == "theater_chemnitz":
        return extractors.theater_chemnitz_events(sid, ua=ua)

    if typ == "tdjw":
        return extractors.tdjw_events(sid, months=source.get("months", 6), ua=ua)

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


def _host_key(src: dict) -> str:
    """Webseite, die eine Quelle abruft – Quellen derselben Webseite laufen nacheinander."""
    u = src.get("url") or src.get("base") or src.get("api") or src["id"]
    return u.split("/")[2] if "://" in u else u


def _collect_parallel(sources: list[dict], workers: int = 10) -> dict:
    """Sammelt alle Quellen. Quellen verschiedener Webseiten laufen parallel, Quellen derselben
    Webseite nacheinander (Pause pro Host bleibt). Liefert {source_id: (roh, fehler, sekunden)}."""
    from concurrent.futures import ThreadPoolExecutor
    groups: dict[str, list[dict]] = {}
    for src in sources:
        groups.setdefault(_host_key(src), []).append(src)

    def work(group):
        import time as _t
        out = {}
        for src in group:
            fetch.set_source(src["id"])
            t0 = _t.time()
            try:
                out[src["id"]] = (collect(src), None, _t.time() - t0)
            except Exception as e:                       # eine Quelle darf nicht alles stoppen
                out[src["id"]] = ([], e, _t.time() - t0)
        fetch.set_source(None)
        return out

    results: dict = {}
    with ThreadPoolExecutor(max_workers=min(workers, max(1, len(groups)))) as pool:
        for part in pool.map(work, groups.values()):
            results.update(part)
    return results


def _crawl():
    store.init_db()
    from datetime import datetime as _dtm
    run_at = _dtm.now().strftime("%Y-%m-%dT%H:%M:%S")
    with open(os.path.join(ROOT, "sources.json"), encoding="utf-8") as f:
        cfg = json.load(f)

    # Phase 1: alle aktiven Quellen parallel einsammeln (Netzwerk), Phase 2: der Reihe nach
    # verarbeiten und speichern (gleiche Reihenfolge wie bisher: bei Dubletten gewinnt die letzte).
    import time as _time
    _t0 = _time.time()
    active = [s_ for s_ in cfg["sources"] if s_.get("active", True)]
    print(f"Sammle {len(active)} Quellen parallel …")
    collected = _collect_parallel(active)
    print(f"Sammeln fertig in {_time.time() - _t0:.0f} s.")

    total_raw = total_kept = 0
    report_rows = []
    undated_rows = []
    seen_ids = {}      # source_id -> {event_id: enriched} (für die Gegenprobe)
    with store.connect() as conn:
        orte, recurring = store.load_curated(ROOT)
        store.sync_places(conn, orte, recurring)           # data/orte.json + wochenangebote.json
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
            raw, err, secs = collected[src["id"]]
            fstat = fetch.pop_stats(src["id"])
            meas = {"requests": fstat["requests"], "errors": fstat["errors"],
                    "error_codes": fstat["codes"], "error_sample": fstat["sample"],
                    "seconds": round(secs, 1)}
            if err is not None:
                print(f"    [error] {err}")
                meas["error_sample"] = meas["error_sample"] or f"Fehler: {err}"
                report_rows.append({"source_id": src["id"], "raw": 0, "kept": 0,
                                    "past": 0, "radius": 0, "nodate": 0, **meas})
                continue
            kept = past = radius = nodate = 0
            fam_default = src.get("family_default", 0.0)
            city = src.get("city")
            bad = 0
            for ev in raw:
                try:
                    for k in ("start_at", "end_at"):     # Zeitzonen-Zusatz (+02:00) abschneiden
                        if ev.get(k) and len(ev[k]) > 19:
                            ev[k] = ev[k][:19]
                    if not ev.get("start_at"):           # ohne Datum = keine Veranstaltung
                        nodate += 1
                        undated_rows.append({"source_id": src["id"], "title": ev.get("title"),
                                             "url": ev.get("source_url")})
                        continue
                    if not pipeline.is_future(ev):       # vergangen
                        past += 1
                        continue
                    ev["source_family_default"] = fam_default
                    ev["source_city"] = city
                    ev["source_region"] = src.get("region", "leipzig")
                    ev["source_age_default"] = src.get("age_default")
                    enriched = pipeline.enrich(ev)
                    if enriched is None:                 # ausserhalb aller Regionen
                        radius += 1
                        continue
                    seen_ids.setdefault(src["id"], {})[enriched["id"]] = enriched
                    if src.get("check"):                 # nur Gegenprobe: nicht in die DB
                        continue
                    store.upsert_event(conn, enriched)
                    kept += 1
                except Exception as exc:                 # ein kaputter Eintrag stoppt nicht den Crawl
                    bad += 1
                    if bad == 1:
                        print(f"    [error] Eintrag übersprungen ({src['id']}): {exc!r}")
            if bad:
                meas["error_sample"] = meas.get("error_sample") or f"{bad} Einträge nicht verarbeitbar"
                meas["errors"] = (meas.get("errors") or 0) + bad
            total_raw += len(raw)
            total_kept += kept
            report_rows.append({"source_id": src["id"], "raw": len(raw), "kept": kept,
                                "past": past, "radius": radius,
                                "nodate": nodate, **meas})
            print(f"    roh: {len(raw):4d} | uebernommen: {kept:4d}")

        # Gegenprobe: Welche Termine einer Vergleichsquelle (z. B. meinestadt) kennen wir
        # bereits aus ANDEREN Quellen, welche nur dort?
        gp_ids = {sid for sid in seen_ids
                  if any(x["id"] == sid and x.get("gegenprobe") for x in cfg["sources"])}
        other_ids = set()
        for sid, evs_ in seen_ids.items():
            if sid not in gp_ids:
                other_ids |= set(evs_)
        gp_rows, gp_missing = [], []
        for sid in sorted(gp_ids):
            evs_ = seen_ids[sid]
            missing = [e for i, e in evs_.items() if i not in other_ids]
            gp_rows.append({"source_id": sid, "found": len(evs_),
                            "covered": len(evs_) - len(missing), "missing": len(missing)})
            for e in missing:
                gp_missing.append({"source_id": sid, "start_at": e.get("start_at"),
                                   "title": e.get("title"), "venue": e.get("venue_name"),
                                   "url": e.get("source_url")})

        # „nur hier"-Zahl je Quelle: Termine, die keine andere Quelle in diesem Lauf kennt
        for row in report_rows:
            mine = set(seen_ids.get(row["source_id"], {}))
            others = set()
            for sid, evs_ in seen_ids.items():
                if sid != row["source_id"]:
                    others |= set(evs_)
            row["unique_n"] = len(mine - others)

        # Vergangene Termine NICHT löschen, sondern archivieren (Gedächtnis für wiederkehrende
        # Veranstaltungen). Archiviert wird, wenn das ENDE vor heute liegt (mehrtägige bleiben aktiv).
        from datetime import date
        today = date.today().isoformat()
        n_arch = store.archive_past(conn, today, run_at)
        print(f"Archiviert (vergangen): {n_arch}")
        # Altbestand ohne Region (Termine, die in diesem Lauf nicht neu geliefert wurden) nachtragen
        from crawler import geo as _geo
        for r_ in conn.execute("SELECT id, lat, lon FROM events WHERE region IS NULL").fetchall():
            coord = (r_["lat"], r_["lon"]) if r_["lat"] and r_["lon"] else None
            reg, _d = _geo.region_of(coord, default="leipzig")
            conn.execute("UPDATE events SET region=? WHERE id=?", (reg or "leipzig", r_["id"]))

        # Bewertungen (data/bewertungen.json) spiegeln, Titel-Schlüssel nachtragen
        store.sync_ratings(conn, store.load_ratings(ROOT))

        # Quellenübergreifende Dubletten markieren (nichts wird gelöscht)
        from crawler import dedupe as _dd
        gen_ids = {x["id"] for x in cfg["sources"] if x.get("scope") == "general"}
        n_dup, dup_pairs = _dd.run(conn, gen_ids)
        print(f"Dubletten markiert: {n_dup}")

        ev_n, vn_n, by_src = store.stats(conn)
        store.record_runs(conn, run_at, report_rows)

    # Crawl-Bericht als CSV: finale DB-Zahl je Quelle (nach Dedup) ergänzen.
    in_db = {r["source_id"]: r["n"] for r in by_src}
    for row in report_rows:
        row["in_db"] = in_db.get(row["source_id"], 0)
    try:
        from tools import report as _report
        _report.save_crawl_report(report_rows)
        _report.save_undated(undated_rows)
        _report.save_gegenprobe(gp_rows, gp_missing)
        _report.export_events()
        _report.save_dubletten(dup_pairs)
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
