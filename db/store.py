"""SQLite-Speicher: Schema + Upsert für events, venues, places, recurring, source_runs.

Bewusst stdlib-only (sqlite3), damit der Prototyp ohne Installation läuft.
"""
from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "events.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id            TEXT PRIMARY KEY,     -- dedup_hash
    source_id     TEXT NOT NULL,
    source_url    TEXT,
    title         TEXT NOT NULL,
    summary       TEXT,
    start_at      TEXT,                 -- ISO 8601
    end_at        TEXT,
    venue_name    TEXT,
    address       TEXT,
    ort           TEXT,
    stadtteil     TEXT,
    lat           REAL,
    lon           REAL,
    distance_km   REAL,
    price         TEXT,
    age_min       INTEGER,
    age_max       INTEGER,
    family_score  REAL DEFAULT 0,
    categories    TEXT,                 -- kommagetrennt
    first_seen_at TEXT,
    last_seen_at  TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_start   ON events(start_at);
CREATE INDEX IF NOT EXISTS idx_events_dist    ON events(distance_km);
CREATE INDEX IF NOT EXISTS idx_events_family  ON events(family_score);

CREATE TABLE IF NOT EXISTS venues (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    kind        TEXT,                   -- indoor|zoo|bauernhof|schwimmbad|theater|museum
    url         TEXT,
    address     TEXT,
    lat         REAL,
    lon         REAL,
    distance_km REAL,
    age_hint    TEXT,
    note        TEXT
);

-- Dauer-Locations (Kindercafés, Indoor, Familienzentren …), Quelle: data/orte.json
CREATE TABLE IF NOT EXISTS places (
    id          TEXT PRIMARY KEY,       -- Kürzel, z. B. B1, CH2
    name        TEXT NOT NULL,
    kind        TEXT,                   -- spielcafe|indoor|familienzentrum|bibliothek|museum|bad|tiere|freizeit
    indoor      TEXT,                   -- ja|nein|teils
    region      TEXT,                   -- leipzig|halle|chemnitz
    ort         TEXT,
    address     TEXT,
    age_min     REAL,                   -- Jahre; NULL = unbekannt
    age_max     REAL,
    url         TEXT,
    beleg       TEXT,                   -- ok|mid|low
    note        TEXT,
    checked_at  TEXT,
    status      TEXT DEFAULT 'aktiv'
);

-- wiederkehrende Angebote; ein Eintrag je Wochentag/Zeitfenster, Quelle: data/wochenangebote.json
CREATE TABLE IF NOT EXISTS recurring (
    id          TEXT PRIMARY KEY,
    offer_id    TEXT NOT NULL,
    place_name  TEXT,
    title       TEXT NOT NULL,
    region      TEXT,
    weekday     INTEGER,                -- 0 = Montag … 6 = Sonntag
    von         TEXT,                   -- HH:MM
    bis         TEXT,
    rule        TEXT,                   -- weekly|biweekly|1st3rd|last|monthly
    anchor      TEXT,                   -- Startdatum für biweekly
    age_min     REAL,
    age_max     REAL,
    hinweis     TEXT,
    beleg       TEXT,
    checked_at  TEXT
);
CREATE INDEX IF NOT EXISTS idx_recurring_day ON recurring(weekday);

-- Messwerte je Quelle und Crawl (Gesundheitsampel)
CREATE TABLE IF NOT EXISTS source_runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_at      TEXT NOT NULL,
    source_id   TEXT NOT NULL,
    found       INTEGER, kept INTEGER, past INTEGER, radius INTEGER, nodate INTEGER,
    requests    INTEGER, errors INTEGER,
    error_codes TEXT,                   -- JSON {"403": 52}
    error_sample TEXT,
    seconds     REAL,
    unique_n    INTEGER
);
CREATE INDEX IF NOT EXISTS idx_runs_src ON source_runs(source_id, run_at);

-- einzelne Erreichbarkeitsprüfungen
CREATE TABLE IF NOT EXISTS source_checks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    checked_at  TEXT NOT NULL,
    source_id   TEXT NOT NULL,
    http        INTEGER,                -- NULL = keine Antwort
    ms          INTEGER,
    note        TEXT
);
CREATE INDEX IF NOT EXISTS idx_checks_src ON source_checks(source_id, checked_at);
"""

# Spalten, die nachträglich zu events kamen (Migration bestehender Datenbanken)
_EVENT_EXTRA = [("archived_at", "TEXT"), ("region", "TEXT")]


@contextmanager
def connect():
    conn = sqlite3.connect(os.path.abspath(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
    with connect() as conn:
        conn.executescript(SCHEMA)
        have = {r["name"] for r in conn.execute("PRAGMA table_info(events)")}
        for col, typ in _EVENT_EXTRA:
            if col not in have:
                conn.execute(f"ALTER TABLE events ADD COLUMN {col} {typ}")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_events_arch ON events(archived_at)")


def upsert_event(conn, ev: dict):
    """Insert oder Update anhand id (dedup_hash). first_seen bleibt erhalten.
    Ein erneut gesehener Termin wird wieder aktiv (archived_at = NULL)."""
    cols = ["id", "source_id", "source_url", "title", "summary", "start_at",
            "end_at", "venue_name", "address", "ort", "stadtteil", "lat", "lon",
            "distance_km", "price", "age_min", "age_max", "family_score",
            "categories", "first_seen_at", "last_seen_at", "region", "archived_at"]
    row = {c: ev.get(c) for c in cols}
    placeholders = ",".join("?" for _ in cols)
    updates = ",".join(f"{c}=excluded.{c}" for c in cols
                       if c not in ("id", "first_seen_at"))
    sql = (f"INSERT INTO events ({','.join(cols)}) VALUES ({placeholders}) "
           f"ON CONFLICT(id) DO UPDATE SET {updates}")
    conn.execute(sql, [row[c] for c in cols])


def archive_past(conn, today: str, now: str) -> int:
    """Vergangene Termine NICHT löschen, sondern als archiviert markieren (Gedächtnis).
    Vergangen = Ende (sonst Start) liegt vor `today` (YYYY-MM-DD)."""
    cur = conn.execute(
        "UPDATE events SET archived_at=? WHERE archived_at IS NULL AND start_at<>'' "
        "AND substr(COALESCE(NULLIF(end_at,''), start_at),1,10) < ?", (now, today))
    return cur.rowcount


def upsert_venue(conn, v: dict):
    cols = ["id", "name", "kind", "url", "address", "lat", "lon",
            "distance_km", "age_hint", "note"]
    placeholders = ",".join("?" for _ in cols)
    updates = ",".join(f"{c}=excluded.{c}" for c in cols if c != "id")
    sql = (f"INSERT INTO venues ({','.join(cols)}) VALUES ({placeholders}) "
           f"ON CONFLICT(id) DO UPDATE SET {updates}")
    conn.execute(sql, [v.get(c) for c in cols])


def sync_places(conn, orte: list[dict], recurring: list[dict]):
    """Orte und wiederkehrende Angebote aus den JSON-Dateien in die DB spiegeln
    (JSON ist die Quelle der Wahrheit: Tabelle wird komplett neu geschrieben)."""
    conn.execute("DELETE FROM places")
    for o in orte:
        conn.execute(
            "INSERT INTO places (id,name,kind,indoor,region,ort,address,age_min,age_max,"
            "url,beleg,note,checked_at,status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (o["id"], o["name"], o.get("kind"), o.get("indoor"), o.get("region"),
             o.get("ort"), o.get("address"), o.get("age_min"), o.get("age_max"),
             o.get("url"), o.get("beleg"), o.get("note"), o.get("checked_at"),
             o.get("status", "aktiv")))
    conn.execute("DELETE FROM recurring")
    for r in recurring:
        for i, slot in enumerate(r["slots"]):
            for wd in slot["days"]:
                conn.execute(
                    "INSERT INTO recurring (id,offer_id,place_name,title,region,weekday,von,bis,"
                    "rule,anchor,age_min,age_max,hinweis,beleg,checked_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (f"{r['id']}.{i}.{wd}", r["id"], r.get("place_name"), r["title"],
                     r.get("region"), wd, slot.get("von"), slot.get("bis"),
                     slot.get("rule", "weekly"), slot.get("anchor"),
                     slot.get("age_min", r.get("age_min")), slot.get("age_max", r.get("age_max")),
                     slot.get("hinweis") or r.get("hinweis"), r.get("beleg"), r.get("checked_at")))


def load_curated(root: str):
    """Liest data/orte.json und data/wochenangebote.json (fehlende Dateien = leer)."""
    def rd(name):
        p = os.path.join(root, "data", name)
        if not os.path.exists(p):
            return []
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return rd("orte.json"), rd("wochenangebote.json")


def record_runs(conn, run_at: str, rows: list[dict]):
    for r in rows:
        conn.execute(
            "INSERT INTO source_runs (run_at,source_id,found,kept,past,radius,nodate,requests,"
            "errors,error_codes,error_sample,seconds,unique_n) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (run_at, r["source_id"], r.get("raw", 0), r.get("kept", 0), r.get("past", 0),
             r.get("radius", 0), r.get("nodate", 0), r.get("requests", 0), r.get("errors", 0),
             json.dumps(r.get("error_codes") or {}), r.get("error_sample"),
             r.get("seconds"), r.get("unique_n")))


def record_checks(conn, checked_at: str, rows: list[dict]):
    for r in rows:
        conn.execute(
            "INSERT INTO source_checks (checked_at,source_id,http,ms,note) VALUES (?,?,?,?,?)",
            (checked_at, r["source_id"], r.get("http"), r.get("ms"), r.get("note")))


def stats(conn):
    ev = conn.execute("SELECT COUNT(*) n FROM events WHERE archived_at IS NULL").fetchone()["n"]
    vn = conn.execute("SELECT COUNT(*) n FROM venues").fetchone()["n"]
    by_src = conn.execute(
        "SELECT source_id, COUNT(*) n FROM events WHERE archived_at IS NULL "
        "GROUP BY source_id ORDER BY n DESC").fetchall()
    return ev, vn, by_src
