"""SQLite-Speicher: Schema + Upsert für events und venues.

Bewusst stdlib-only (sqlite3), damit der Prototyp ohne Installation läuft.
"""
from __future__ import annotations

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
"""


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
    with connect() as conn:
        conn.executescript(SCHEMA)


def upsert_event(conn, ev: dict):
    """Insert oder Update anhand id (dedup_hash). first_seen bleibt erhalten."""
    cols = ["id", "source_id", "source_url", "title", "summary", "start_at",
            "end_at", "venue_name", "address", "ort", "stadtteil", "lat", "lon",
            "distance_km", "price", "age_min", "age_max", "family_score",
            "categories", "first_seen_at", "last_seen_at"]
    row = {c: ev.get(c) for c in cols}
    placeholders = ",".join("?" for _ in cols)
    updates = ",".join(f"{c}=excluded.{c}" for c in cols
                       if c not in ("id", "first_seen_at"))
    sql = (f"INSERT INTO events ({','.join(cols)}) VALUES ({placeholders}) "
           f"ON CONFLICT(id) DO UPDATE SET {updates}")
    conn.execute(sql, [row[c] for c in cols])


def upsert_venue(conn, v: dict):
    cols = ["id", "name", "kind", "url", "address", "lat", "lon",
            "distance_km", "age_hint", "note"]
    placeholders = ",".join("?" for _ in cols)
    updates = ",".join(f"{c}=excluded.{c}" for c in cols if c != "id")
    sql = (f"INSERT INTO venues ({','.join(cols)}) VALUES ({placeholders}) "
           f"ON CONFLICT(id) DO UPDATE SET {updates}")
    conn.execute(sql, [v.get(c) for c in cols])


def stats(conn):
    ev = conn.execute("SELECT COUNT(*) n FROM events").fetchone()["n"]
    vn = conn.execute("SELECT COUNT(*) n FROM venues").fetchone()["n"]
    by_src = conn.execute(
        "SELECT source_id, COUNT(*) n FROM events GROUP BY source_id "
        "ORDER BY n DESC").fetchall()
    return ev, vn, by_src
