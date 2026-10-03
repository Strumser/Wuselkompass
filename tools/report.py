"""CSV-Werkzeuge, um die Datenbank unabhängig vom Frontend zu betrachten.

Zwei Ausgaben (beide in data/export/, in Numbers/Excel öffnen):
  * events.csv        – eine Zeile pro Veranstaltung in der DB (die Inhalte).
  * crawl_report.csv  – eine Zeile pro Quelle: gefunden/übernommen/verworfen und warum.
                        Wird beim Crawl (crawler/run.py) geschrieben, nicht hier.

Aufruf:  python3 -m tools.report        # erzeugt/aktualisiert events.csv
"""
from __future__ import annotations

import csv
import json
import os
import sqlite3

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "data", "events.db")
SOURCES = os.path.join(ROOT, "sources.json")
EXPORT_DIR = os.path.join(ROOT, "data", "export")
EVENTS_CSV = os.path.join(EXPORT_DIR, "events.csv")
REPORT_CSV = os.path.join(EXPORT_DIR, "crawl_report.csv")


def scope_map() -> dict:
    """source_id -> Ansicht ('Familie' kuratiert | 'Alle Events' allgemein)."""
    try:
        with open(SOURCES, encoding="utf-8") as f:
            cfg = json.load(f)
    except (OSError, ValueError):
        return {}
    return {s["id"]: ("Alle Events" if s.get("scope") == "general" else "Familie")
            for s in cfg.get("sources", [])}


# Spalten der Event-CSV: (DB-Feld, Überschrift) – bewusst menschenlesbar sortiert.
_EVENT_COLS = [
    ("start_at", "Beginn"), ("end_at", "Ende"), ("title", "Titel"),
    ("ort", "Ort"), ("stadtteil", "Stadtteil"), ("venue_name", "Veranstaltungsort"),
    ("address", "Adresse"), ("price", "Preis"), ("distance_km", "km bis Leipzig"),
    ("age_min", "Alter ab"), ("age_max", "Alter bis"),
    ("source_id", "Quelle"), ("source_url", "Link"),
]


def export_events(path: str = EVENTS_CSV) -> int:
    """Schreibt alle Events als CSV (nach Beginn sortiert). Gibt die Zeilenzahl zurück."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    smap = scope_map()
    with sqlite3.connect(DB, timeout=5) as c:
        c.row_factory = sqlite3.Row
        rows = c.execute(
            "SELECT * FROM events ORDER BY start_at, source_id").fetchall()
    # utf-8-sig: Umlaute erscheinen in Numbers/Excel korrekt.
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow([h for _, h in _EVENT_COLS] + ["Ansicht"])
        for r in rows:
            w.writerow([r[db] for db, _ in _EVENT_COLS]
                       + [smap.get(r["source_id"], "Familie")])
    return len(rows)


# Spalten der Crawl-Report-CSV (eine Zeile je Quelle).
_REPORT_HEADERS = ["Quelle", "Ansicht", "gefunden", "übernommen",
                   "verworfen (vergangen)", "verworfen (außerhalb 60 km)",
                   "in DB (nach Dedup)"]


def save_crawl_report(rows: list[dict], path: str = REPORT_CSV) -> int:
    """Schreibt den Crawl-Bericht. `rows`: dicts mit den Schlüsseln aus run.py."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    smap = scope_map()
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(_REPORT_HEADERS)
        for r in rows:
            w.writerow([
                r["source_id"], smap.get(r["source_id"], "Familie"),
                r.get("raw", 0), r.get("kept", 0), r.get("past", 0),
                r.get("radius", 0), r.get("in_db", 0),
            ])
    return len(rows)


def main():
    n = export_events()
    print(f"events.csv geschrieben: {n} Veranstaltungen -> {EVENTS_CSV}")
    if os.path.exists(REPORT_CSV):
        print(f"crawl_report.csv (vom letzten Crawl) -> {REPORT_CSV}")
    else:
        print("crawl_report.csv gibt es noch nicht – wird beim nächsten "
              "Aktualisieren (Crawl) erzeugt.")


if __name__ == "__main__":
    main()
