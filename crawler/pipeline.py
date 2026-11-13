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

# ------------------------------------------------------------------ Alterserkennung
_NUMW = {"ein": 1, "eins": 1, "einem": 1, "einen": 1, "einer": 1, "zwei": 2, "drei": 3, "vier": 4,
         "fünf": 5, "fuenf": 5, "sechs": 6, "sieben": 7, "acht": 8, "neun": 9, "zehn": 10,
         "elf": 11, "zwölf": 12, "zwoelf": 12}
_NUMW_RE = re.compile(r"\b(" + "|".join(sorted(_NUMW, key=len, reverse=True)) + r")\b"
                      r"(?=\s*(?:bis\b|[-–]|jahr|j\b|monat))")
_N = r"(\d+(?:[.,]\d+)?)"
_YR = r"(?:jahre?n?|j\b\.?)"
# (Muster, Art): range = von–bis, min = ab, max = bis, mrange/mmin = in Monaten
_NUM_PATTERNS = [
    (r"alter\w*:?\s*" + _N + r"\s*(?:bis|[-–])\s*" + _N, "range"),            # "Alter: 3–6"
    (r"alter\w*:?\s*" + _N + r"\s*\+", "min"),                                # "Alter: 5+"
    (_N + r"\s*(?:bis|[-–])\s*" + _N + r"\s*monat\w*", "mrange"),             # "6 bis 18 Monate"
    (_N + r"\s*(?:bis|[-–])\s*" + _N + r"\s*" + _YR, "range"),                # "3 bis 6 Jahre", "3-6 J."
    (r"kinder\w*\s*(?:ab|von)\s*" + _N + r"\s*(?:bis|[-–])\s*" + _N, "range"),
    (r"\bab\s*" + _N + r"\s*monat\w*", "mmin"),                               # "ab 6 Monaten"
    (r"\bab\s*" + _N + r"\s*" + _YR, "min"),                                  # "ab 3 Jahren", "ab 3 J."
    (r"kinder\w*\s*ab\s*" + _N, "min"),                                       # "Kinder ab 5"
    (r"(?<![\d.])(\d{1,2})\s*\+\s*" + _YR, "min"),                              # "4+ Jahre"
    (r"\(\s*(\d{1,2})\s*\+\s*\)|(?<![\d.])(\d{1,2})\s*plus\b", "min"),            # "(3+)", "3plus"
]
# Preis-Kontext („Kinder bis 3 Jahre frei") ist KEINE Altersempfehlung
_PRICE_CTX = re.compile(r"frei|eintritt|kostenlos|ermäßig|zahlen|bezahlen|preis|€|euro|ticket|gratis", re.I)
# Zielgruppenwörter (nur Titel/Kurztext/Rubrik, nicht im Langtext). Werte vom Nutzer festgelegt:
# Baby = unter 1 Jahr, Kleinkind = ab 1 Jahr.
_GROUPS = [
    (r"\bbaby(?!lon)\w*(?!\s*!)", (0, 1)),
    (r"\bkrabbel\w*", (0, 2)),
    (r"\bkleinkind\w*", (1, None)),
    (r"\bvorschul\w*|\bkita-?kinder\b", (3, 6)),
]


def _f(x: str) -> float:
    return float(x.replace(",", "."))


def _clean_num(v):
    return int(v) if v is not None and float(v) == int(v) else (round(v, 2) if v is not None else None)


def extract_age(text: str, full: str | None = None):
    """(age_min, age_max) in Jahren aus Kurztext (+ optional Langtext). (None, None) = unbekannt.
    Reihenfolge: ausdrückliche Zahlen (Kurztext, dann Langtext), danach Zielgruppenwörter (nur Kurztext)."""
    for src_text in (text, full):
        if not src_text:
            continue
        t = _NUMW_RE.sub(lambda m: str(_NUMW[m.group(1)]), src_text.lower())
        for pat, kind in _NUM_PATTERNS:
            for m in re.finditer(pat, t):
                ctx = t[max(0, m.start() - 20): m.end() + 25]
                if _PRICE_CTX.search(ctx):
                    continue
                g = m.groups()
                if kind == "range":
                    a, b = _f(g[0]), _f(g[1])
                    if a <= b <= 18:
                        return _clean_num(a), _clean_num(b)
                elif kind == "min":
                    n = next(x for x in g if x)
                    if _f(n) <= 18:
                        return _clean_num(_f(n)), None
                elif kind == "mmin":
                    return _clean_num(round(_f(g[0]) / 12, 2)), None
                elif kind == "mrange":
                    return _clean_num(round(_f(g[0]) / 12, 2)), _clean_num(round(_f(g[1]) / 12, 2))
    lo = hi = None
    for pat, (a, b) in _GROUPS:
        if re.search(pat, text.lower()):
            lo = a if lo is None else min(lo, a)
            hi = (b if hi is None else (None if b is None else max(hi, b))) if lo is not None else b
    if lo is not None:
        return lo, hi
    return None, None


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

    short = " ".join(str(ev.get(k) or "") for k in ("title", "summary", "categories"))
    age_min, age_max = extract_age(short, ev.get("_fulltext"))
    # kuratiertes Standardalter der Quelle (z. B. FiZ 0–6), nur wenn der Text nichts hergibt
    dflt = ev.get("source_age_default")
    if age_min is None and age_max is None and dflt:
        age_min, age_max = dflt[0], dflt[1]
    # Kleinkind-Bonus, wenn Alter ins 0-6-Fenster passt
    if age_min is not None and age_min <= 6:
        score = min(1.0, score + 0.2)
    return round(score, 2), age_min, age_max, sorted(set(cats))


def enrich(ev: dict) -> dict | None:
    """Ergänzt id, Geo, Region, Familien-Score. None = außerhalb jeder Region/verwerfen."""
    coord = (ev["lat"], ev["lon"]) if ev.get("lat") and ev.get("lon") \
        else geo.locate(ev.get("address") or ev.get("venue_name"))
    # Region = Halle (25 km) / Chemnitz (30 km) / Leipzig (60 km); Ort unbekannt -> Quellenregion, behalten
    region, dist = geo.region_of(coord, default=ev.get("source_region") or "leipzig")
    if coord and region is None:
        return None

    score, age_min, age_max, cats = classify_family(ev)
    loc_text = " ".join(str(ev.get(k) or "") for k in ("address", "venue_name", "title"))
    ort = (geo.locate_name(ev.get("address") or ev.get("venue_name"))
           or (geo.nearest_name(coord) if ev.get("lat") else None) or ev.get("source_city"))
    stadtteil = geo.detect_stadtteil(loc_text) if ort == "Leipzig" else None
    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
    ev = dict(ev)
    ev["id"] = dedup_hash(ev)
    ev["ort"] = ort
    ev["stadtteil"] = stadtteil
    ev["lat"] = coord[0] if coord else None
    ev["lon"] = coord[1] if coord else None
    ev["distance_km"] = dist
    ev["region"] = region
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
        d = datetime.fromisoformat(ref)
    except ValueError:
        return True
    if d.tzinfo:                        # Datum mit Zeitzone (z. B. +02:00) -> lokale Zeit ohne Zone
        d = d.replace(tzinfo=None)
    return d >= midnight
