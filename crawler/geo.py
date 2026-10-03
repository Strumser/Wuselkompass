"""Geo: Ortszentren-Gazetteer + Haversine + Radius-Filter.

Für den Prototyp reicht ein Gazetteer der Region (kein Nominatim-Zwang).
Ein Event-Ortstext wird gegen bekannte Städte gematcht -> Koordinaten.
Optional kann später Nominatim mit Cache ergänzt werden.
"""
from __future__ import annotations

import math

# Zentrum für die Radius-Messung: Leipzig, Markt
LEIPZIG = (51.3397, 12.3731)

# Städte/Orte im ~70-km-Umkreis (Name -> (lat, lon))
GAZETTEER = {
    "leipzig": (51.3397, 12.3731),
    "markkleeberg": (51.2760, 12.3690),
    "taucha": (51.3820, 12.4940),
    "borsdorf": (51.3500, 12.5300),
    "panitzsch": (51.3660, 12.5250),
    "schkeuditz": (51.3960, 12.2200),
    "grossösna": (51.2360, 12.5170),
    "großpösna": (51.2360, 12.5170),
    "zwenkau": (51.2210, 12.3260),
    "böhlen": (51.2000, 12.3860),
    "borna": (51.1230, 12.4970),
    "grimma": (51.2360, 12.7230),
    "wurzen": (51.3690, 12.7370),
    "eilenburg": (51.4610, 12.6340),
    "delitzsch": (51.5260, 12.3400),
    "torgau": (51.5610, 12.9940),
    "lossatal": (51.4200, 12.8400),
    "colditz": (51.1300, 12.8080),
    "bad lausick": (51.1490, 12.6320),
    "geithain": (51.0520, 12.6960),
    "lützen": (51.2540, 12.1400),
    "halle": (51.4820, 11.9700),
    "halle (saale)": (51.4820, 11.9700),
    "merseburg": (51.3550, 11.9910),
    "naumburg": (51.1510, 11.8090),
    "bad kösen": (51.1330, 11.7220),
    "altenburg": (50.9850, 12.4340),
    "bitterfeld": (51.6240, 12.3170),
    "bitterfeld-wolfen": (51.6240, 12.3170),
    "zeitz": (51.0490, 12.1360),
    "riesa": (51.3080, 13.2920),
    "petersberg": (51.5850, 11.9500),
    "otterwisch": (51.1780, 12.6180),
    "kitzen": (51.2350, 12.2100),
    "kreuma": (51.5000, 12.4000),
    "dornreichenbach": (51.4100, 12.8600),
}


# Anzeigenamen für Orte (kanonisch, konsistent mit source "city")
DISPLAY = {
    "halle": "Halle (Saale)", "halle (saale)": "Halle (Saale)",
    "naumburg": "Naumburg", "bad kösen": "Bad Kösen",
    "bad lausick": "Bad Lausick", "bitterfeld": "Bitterfeld-Wolfen",
    "bitterfeld-wolfen": "Bitterfeld-Wolfen", "großpösna": "Großpösna",
    "grossösna": "Großpösna", "lützen": "Lützen",
}

# Wichtige Leipziger Stadtteile (für den Sub-Filter)
LEIPZIG_STADTTEILE = [
    # "Zentrum" (bare) bewusst weggelassen: kollidiert mit "...zentrum" in Venue-Namen
    "Zentrum-Süd", "Zentrum-Nord", "Zentrum-Ost", "Zentrum-West",
    "Südvorstadt", "Connewitz", "Lößnig", "Dölitz", "Probstheida",
    "Stötteritz", "Reudnitz", "Anger-Crottendorf", "Volkmarsdorf",
    "Neustadt-Neuschönefeld", "Sellerhausen", "Paunsdorf", "Heiterblick",
    "Schönefeld", "Mockau", "Thekla", "Portitz", "Gohlis", "Eutritzsch",
    "Möckern", "Wahren", "Lützschena-Stahmeln", "Wiederitzsch", "Lindenthal",
    "Plagwitz", "Kleinzschocher", "Großzschocher", "Grünau", "Grünau-Mitte",
    "Grünau-Nord", "Grünau-Ost", "Grünau-Süd", "Schönau", "Lausen",
    "Miltitz", "Böhlitz-Ehrenberg", "Burghausen", "Lindenau", "Leutzsch",
    "Schleußig", "Schleusig", "Altlindenau", "Neulindenau", "Gohlis-Süd",
    "Gohlis-Nord", "Gohlis-Mitte", "Marienbrunn", "Meusdorf", "Liebertwolkwitz",
    "Holzhausen", "Mölkau", "Engelsdorf", "Baalsdorf", "Knautkleeberg",
]


def locate_name(text: str | None) -> str | None:
    """Kanonischer Ortsname aus einem Orts-/Adresstext (via Gazetteer)."""
    if not text:
        return None
    t = text.lower()
    for name in sorted(GAZETTEER, key=len, reverse=True):
        if name in t:
            return DISPLAY.get(name, name.title())
    return None


def detect_stadtteil(text: str | None) -> str | None:
    """Findet einen Leipziger Stadtteil im Text (längste Treffer zuerst)."""
    if not text:
        return None
    t = text.lower()
    for st in sorted(LEIPZIG_STADTTEILE, key=len, reverse=True):
        if st.lower() in t:
            return st
    return None


def haversine(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Distanz in km zwischen zwei (lat, lon)-Punkten."""
    r = 6371.0
    lat1, lon1, lat2, lon2 = map(math.radians, [a[0], a[1], b[0], b[1]])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def locate(text: str | None) -> tuple[float, float] | None:
    """Findet Koordinaten anhand eines Orts-/Adresstextes via Gazetteer."""
    if not text:
        return None
    t = text.lower()
    # längste Namen zuerst matchen (z. B. "halle (saale)" vor "halle")
    for name in sorted(GAZETTEER, key=len, reverse=True):
        if name in t:
            return GAZETTEER[name]
    return None


def distance_from_leipzig(coord: tuple[float, float] | None) -> float | None:
    if not coord:
        return None
    return round(haversine(LEIPZIG, coord), 1)
