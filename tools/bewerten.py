"""Bewertung „passt für ein Kind von 2–4 Jahren?" – von Claude vorgenommen, je Titel.

Ablauf (in einer Claude-Sitzung):
  python3 -m tools.bewerten offen [TAGE]     # unbewertete Titel der nächsten TAGE (Standard 14)
                                             #   -> data/export/zu_bewerten.json
  (Claude liest die Datei und schreibt seine Urteile als JSON)
  python3 -m tools.bewerten import DATEI     # Urteile in data/bewertungen.json übernehmen + DB

data/bewertungen.json ist die Quelle der Wahrheit (im Repository, also auf allen Geräten):
  { "<rating_key>": {"titel": "...", "urteil": "passt|vielleicht|nein",
                     "ab": 2, "bis": 6, "grund": "...", "am": "YYYY-MM-DD"} }
„ab"/„bis" = geschätztes Alter; wird nur genutzt, wenn der Termin selbst keins nennt.
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
from datetime import date, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from db import store  # noqa: E402

RATINGS = os.path.join(ROOT, "data", "bewertungen.json")
OPEN_FILE = os.path.join(ROOT, "data", "export", "zu_bewerten.json")
VERDICTS = ("passt", "vielleicht", "nein")


def open_items(days: int = 14) -> list[dict]:
    """Je unbewertetem Titel ein Beispieltermin (aktiv, keine Dublette, innerhalb von `days` Tagen)."""
    rated = store.load_ratings(ROOT)
    until = (date.today() + timedelta(days=days)).isoformat()
    c = sqlite3.connect(os.path.join(ROOT, "data", "events.db"))
    c.row_factory = sqlite3.Row
    rows = c.execute(
        "SELECT title, summary, venue_name, ort, source_id, categories, age_min, age_max, start_at "
        "FROM events WHERE archived_at IS NULL AND dup_of IS NULL AND start_at<>'' "
        "AND substr(start_at,1,10) <= ? ORDER BY start_at", (until,)).fetchall()
    out, seen = [], set()
    for r in rows:
        k = store.rating_key(r["title"])
        if not k or k in rated or k in seen:
            continue
        seen.add(k)
        out.append({"key": k, "titel": r["title"], "text": (r["summary"] or "")[:300],
                    "ort": r["venue_name"] or r["ort"], "quelle": r["source_id"],
                    "rubrik": r["categories"], "alter_angabe": [r["age_min"], r["age_max"]]})
    return out


def import_ratings(path: str) -> int:
    with open(path, encoding="utf-8") as f:
        new = json.load(f)
    ratings = store.load_ratings(ROOT)
    today = date.today().isoformat()
    n = 0
    for k, r in new.items():
        if r.get("urteil") not in VERDICTS:
            print(f"übersprungen (Urteil fehlt/ungültig): {k}")
            continue
        r.setdefault("am", today)
        ratings[k] = r
        n += 1
    with open(RATINGS, "w", encoding="utf-8") as f:
        json.dump(dict(sorted(ratings.items())), f, ensure_ascii=False, indent=1)
        f.write("\n")
    store.init_db()
    with store.connect() as conn:
        store.sync_ratings(conn, ratings)
    return n


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "offen"
    if cmd == "offen":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 14
        items = open_items(days)
        os.makedirs(os.path.dirname(OPEN_FILE), exist_ok=True)
        with open(OPEN_FILE, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=1)
        print(f"{len(items)} unbewertete Titel (nächste {days} Tage) -> {OPEN_FILE}")
    elif cmd == "import":
        print(f"{import_ratings(sys.argv[2])} Bewertungen übernommen -> {RATINGS}")
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
