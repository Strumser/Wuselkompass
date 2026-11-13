"""Unscharfe Dublettenerkennung über Quellen hinweg.

Zwei aktive Termine gelten als Dublette, wenn sie am selben Tag in derselben Region liegen,
die Titel (normalisiert) sehr ähnlich sind und Ort/Veranstaltungsort nicht widersprechen.
Nichts wird gelöscht: die schwächere Zeile bekommt `dup_of` (id des Haupteintrags), der
Haupteintrag sammelt die anderen Quellen in `also_in`.
"""
from __future__ import annotations

import re
from collections import defaultdict
from difflib import SequenceMatcher

TITLE_MIN = 0.88
VENUE_MIN = 0.6
_STOP = re.compile(r"\b(f[üu]r|mit|und|der|die|das|im|in|am|zum|zur|kinder|familien?)\b")


def _norm(s: str) -> str:
    s = re.sub(r"[^\w\s]", " ", (s or "").lower())
    s = _STOP.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip()


def _ratio(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    if min(len(a), len(b)) >= 8 and (a in b or b in a):
        return 0.9
    return SequenceMatcher(None, a, b).ratio()


def _hhmm(s: str | None):
    s = s or ""
    if len(s) >= 16 and s[11:16] != "00:00":
        return int(s[11:13]) * 60 + int(s[14:16])
    return None


def _same(a: dict, b: dict) -> bool:
    if a["_t"] == "" or b["_t"] == "":
        return False
    if _ratio(a["_t"], b["_t"]) < TITLE_MIN:
        return False
    ta, tb = _hhmm(a["start_at"]), _hhmm(b["start_at"])
    if ta is not None and tb is not None and abs(ta - tb) > 90:
        return False
    va, vb = a["_v"], b["_v"]
    if va and vb and _ratio(va, vb) < VENUE_MIN and (a["ort"] or "") != (b["ort"] or ""):
        return False
    return True


def _rank(e: dict, general: set) -> tuple:
    """Höher = besserer Haupteintrag: Altersangabe, Familien-Quelle, Beschreibung, Detail."""
    return (e["age_min"] is not None or e["age_max"] is not None,
            e["source_id"] not in general,
            len(e["summary"] or ""), e["source_id"] == "leipzig-im", e["id"])


def run(conn, general: set | frozenset = frozenset()) -> tuple[int, list[dict]]:
    """Setzt dup_of/also_in für alle aktiven Termine neu. Gibt (Anzahl Dubletten, Paare) zurück."""
    conn.execute("UPDATE events SET dup_of=NULL, also_in=NULL")
    rows = [dict(r) for r in conn.execute(
        "SELECT id, source_id, title, summary, start_at, venue_name, address, ort, region, "
        "age_min, age_max FROM events WHERE archived_at IS NULL AND start_at<>''")]
    groups = defaultdict(list)
    for r in rows:
        r["_t"] = _norm(r["title"])
        r["_v"] = _norm(r["venue_name"] or r["address"] or "")
        groups[(r["start_at"][:10], r["region"] or "")].append(r)

    pairs, n = [], 0
    for items in groups.values():
        if len(items) < 2:
            continue
        parent = {e["id"]: e["id"] for e in items}

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x
        for i, a in enumerate(items):
            for b in items[i + 1:]:
                if a["id"] != b["id"] and _same(a, b):
                    parent[find(a["id"])] = find(b["id"])
        clusters = defaultdict(list)
        for e in items:
            clusters[find(e["id"])].append(e)
        for cl in clusters.values():
            if len(cl) < 2:
                continue
            cl.sort(key=lambda e: _rank(e, general), reverse=True)
            main, rest = cl[0], cl[1:]
            # Alter vom Duplikat übernehmen, falls der Haupteintrag keines hat
            if main["age_min"] is None and main["age_max"] is None:
                for e in rest:
                    if e["age_min"] is not None or e["age_max"] is not None:
                        conn.execute("UPDATE events SET age_min=?, age_max=? WHERE id=?",
                                     (e["age_min"], e["age_max"], main["id"]))
                        break
            srcs = sorted({e["source_id"] for e in rest} - {main["source_id"]})
            conn.execute("UPDATE events SET also_in=? WHERE id=?",
                         (", ".join(srcs) or None, main["id"]))
            for e in rest:
                conn.execute("UPDATE events SET dup_of=? WHERE id=?", (main["id"], e["id"]))
                n += 1
                pairs.append({"day": main["start_at"][:10], "region": main["region"],
                              "main_src": main["source_id"], "main_title": main["title"],
                              "dup_src": e["source_id"], "dup_title": e["title"],
                              "ratio": round(_ratio(main["_t"], e["_t"]), 2)})
    return n, pairs
