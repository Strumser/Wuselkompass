"""Pipeline: Dedup -> Geo/Radius -> Familien-/Alters-Klassifikation."""
from __future__ import annotations

import hashlib
import re
from datetime import datetime

from . import geo

RADIUS_KM = 60.0

# Signalwörter für Familien-/Kleinkind-Relevanz (gewichtet)
STRONG = ["krabbel", "kleinkind", "baby", "bilderbuchkino", "eltern-kind",
          "eltern kind", "familientreff", "spielgruppe", "vorlese", "puppentheater",
          "familiensonntag", "familienfest", "kindertheater", "musikspielwiese",
          "babyschwimmen", "familienfrühstück", "0-3", "0-6", "0 bis 6", "ab 2 monaten"]
MEDIUM = ["kinder", "familie", "familien", "märchen", "basteln", "mitmach",
          "zoo", "tierpark", "bauernhof", "kasperle", "figurentheater",
          "kinderkonzert", "kinderfest", "ferienprogramm"]
NEGATIVE = ["ab 12", "ab 14", "ab 16", "ab 18", "erwachsene", "18+", "party",
            "techno", "poetry slam", "lesung für erwachsene"]

AGE_PATTERNS = [
    (r"(\d+)\s*bis\s*(\d+)\s*jahr", "range"),
    (r"(\d+)\s*[-–]\s*(\d+)\s*jahr", "range"),
    (r"ab\s*(\d+)\s*jahr", "min"),
    (r"für\s*kinder\s*ab\s*(\d+)", "min"),
    (r"ab\s*(\d+)\s*monat", "min_month"),
]


def dedup_hash(ev: dict) -> str:
    title = re.sub(r"\W+", "", (ev.get("title") or "").lower())[:60]
    day = (ev.get("start_at") or "")[:10]
    place = re.sub(r"\W+", "", (ev.get("venue_name") or ev.get("address") or "").lower())[:30]
    return hashlib.sha1(f"{title}|{day}|{place}".encode()).hexdigest()


def classify_family(ev: dict) -> tuple[float, int | None, int | None, list[str]]:
    text = " ".join(str(ev.get(k) or "") for k in
                    ("title", "summary", "venue_name", "categories")).lower()
    # Basiswert aus dem Quellen-Vertrauen: kid-kuratierte Quellen (z. B. FiZ,
    # meinestadt-Kinderrubrik, Kindertheater) starten bereits erhöht.
    score = float(ev.get("source_family_default") or 0.0)
    cats = []
    if score >= 0.4:
        cats.append("familie")
    for kw in STRONG:
        if kw in text:
            score += 0.4
            cats.append("kleinkind")
            break
    for kw in MEDIUM:
        if kw in text:
            score += 0.25
            cats.append("familie")
            break
    for kw in NEGATIVE:
        if kw in text:
            score -= 0.5
    score = max(0.0, min(1.0, score))

    age_min = age_max = None
    for pat, kind in AGE_PATTERNS:
        m = re.search(pat, text)
        if not m:
            continue
        if kind == "range":
            age_min, age_max = int(m.group(1)), int(m.group(2))
        elif kind == "min":
            age_min = int(m.group(1))
        elif kind == "min_month":
            age_min = 0
        break
    # Kleinkind-Bonus, wenn Alter ins 0-6-Fenster passt
    if age_min is not None and age_min <= 6:
        score = min(1.0, score + 0.2)
    return round(score, 2), age_min, age_max, sorted(set(cats))


def enrich(ev: dict) -> dict | None:
    """Ergänzt id, Geo, Distanz, Familien-Score. None = außerhalb Radius/verwerfen."""
    coord = geo.locate(ev.get("address") or ev.get("venue_name"))
    dist = geo.distance_from_leipzig(coord)
    # Wenn Ort bekannt UND außerhalb Radius -> verwerfen.
    # Ort unbekannt (dist None) -> behalten, aber ungefiltert (Quelle ist regional).
    if dist is not None and dist > RADIUS_KM:
        return None

    score, age_min, age_max, cats = classify_family(ev)
    loc_text = " ".join(str(ev.get(k) or "") for k in ("address", "venue_name", "title"))
    ort = geo.locate_name(ev.get("address") or ev.get("venue_name")) or ev.get("source_city")
    stadtteil = geo.detect_stadtteil(loc_text) if ort == "Leipzig" else None
    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
    ev = dict(ev)
    ev["id"] = dedup_hash(ev)
    ev["ort"] = ort
    ev["stadtteil"] = stadtteil
    ev["lat"] = coord[0] if coord else None
    ev["lon"] = coord[1] if coord else None
    ev["distance_km"] = dist
    ev["family_score"] = score
    ev["age_min"] = age_min
    ev["age_max"] = age_max
    ev["categories"] = ",".join(cats)
    ev["first_seen_at"] = now
    ev["last_seen_at"] = now
    return ev


def is_future(ev: dict) -> bool:
    """Behalten, wenn kein Datum ODER noch nicht vorbei.

    Maßgeblich ist das Ende (end_at), sonst der Start – so bleiben mehrtägige
    Veranstaltungen erhalten, solange sie noch laufen.
    """
    ref = ev.get("end_at") or ev.get("start_at")
    if not ref:
        return True
    midnight = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    try:
        return datetime.fromisoformat(ref) >= midnight
    except ValueError:
        return True
