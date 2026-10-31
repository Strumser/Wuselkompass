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
    "freyburg": (51.2220, 11.7780),
    "weißenfels": (51.2000, 11.9680),
    "markranstädt": (51.2960, 12.2230),
    # --- Region Chemnitz (Näherungswerte, nur für Region/Radius) ---
    "chemnitz": (50.8278, 12.9214),
    "hohenstein-ernstthal": (50.7956, 12.7139),
    "limbach-oberfrohna": (50.8644, 12.7683),
    "burgstädt": (50.9150, 12.8150),
    "mittweida": (50.9853, 12.9810),
    "flöha": (50.8586, 13.0750),
    "oederan": (50.8610, 13.2370),
    "zschopau": (50.7500, 13.0700),
    "augustusburg": (50.7961, 13.1117),
    "glauchau": (50.8167, 12.5333),
    "meerane": (50.8500, 12.4667),
    "penig": (50.9347, 12.7003),
    "frankenberg": (50.9167, 13.0333),
    "lichtenau": (50.9300, 13.0600),
    "thum": (50.6200, 12.9500),
    "niederwiesa": (50.8700, 13.0000),
    # --- weitere Orte aus den Dauer-Locations (Näherungswerte) ---
    "döbeln": (51.1200, 13.1200),
    "leisnig": (51.1597, 12.9242),
    "mügeln": (51.2380, 13.0620),
    "oschatz": (51.3000, 13.1167),
    "schmölln": (50.9025, 12.3547),
    "posterstein": (50.9570, 12.3740),
    "ronneburg": (50.8500, 12.1833),
    "meuselwitz": (51.0500, 12.3000),
    "memleben": (51.2847, 11.4483),
    "eckartsberga": (51.1333, 11.5500),
    "landsberg": (51.4167, 12.1500),
    "bad dürrenberg": (51.2970, 12.0680),
    "querfurt": (51.3800, 11.6000),
    "mücheln": (51.2833, 11.8000),
    "wettin": (51.5833, 11.8167),
    "bad düben": (51.5900, 12.5890),
    "machern": (51.3600, 12.6000),
    "naunhof": (51.2700, 12.5800),
    "albrechtshain": (51.2750, 12.5900),
    "günthersdorf": (51.3170, 12.1000),
    "leuna": (51.3167, 12.0100),
    "geithain": (51.0520, 12.6960),
    "kohren-sahlis": (51.0100, 12.6700),
    "frohburg": (51.0700, 12.5600),
    "pegau": (51.1700, 12.2700),
    "zwenkau": (51.2210, 12.3260),
    "neukieritzsch": (51.1700, 12.4400),
    "regis-breitingen": (51.1100, 12.4300),
    "rötha": (51.1900, 12.4800),
    "groitzsch": (51.1500, 12.2900),
    "gaschwitz": (51.2300, 12.4000),
    "trebsen": (51.2800, 12.7400),
    "dahlen": (51.3000, 13.0200),
    "wehlitz": (51.4000, 12.2300),
}


# Regionen: Zentrum + Radius in km. Ein Termin gehört zur Region, deren Zentrum ihm am nächsten ist
# und deren Radius er einhält (Halle/Chemnitz vor Leipzig, damit „Halle" ein eigener Filter wird).
REGIONS = {
    "halle":   {"name": "Halle (Saale)", "center": (51.4820, 11.9700), "radius": 25.0},
    "chemnitz": {"name": "Chemnitz",     "center": (50.8278, 12.9214), "radius": 30.0},
    "leipzig": {"name": "Leipzig",       "center": (51.3397, 12.3731), "radius": 60.0},
}
REGION_ORDER = ["halle", "chemnitz", "leipzig"]      # Prüfreihenfolge


def region_of(coord, default: str = "leipzig"):
    """(Region, Distanz zum Zentrum dieser Region) für Koordinaten; None = außerhalb aller Regionen.
    Ohne Koordinaten: `default` (Ort unbekannt -> behalten wie bisher)."""
    if not coord:
        return default, None
    for key in REGION_ORDER:
        r = REGIONS[key]
        d = haversine(r["center"], coord)
        if d <= r["radius"]:
            return key, round(d, 1)
    return None, None



# Anzeigenamen für Orte (kanonisch, konsistent mit source "city")
DISPLAY = {
    "halle": "Halle (Saale)", "halle (saale)": "Halle (Saale)",
    "naumburg": "Naumburg", "bad kösen": "Bad Kösen",
    "bad lausick": "Bad Lausick", "bitterfeld": "Bitterfeld-Wolfen",
    "bitterfeld-wolfen": "Bitterfeld-Wolfen", "großpösna": "Großpösna",
    "grossösna": "Großpösna", "lützen": "Lützen",
    "freyburg": "Freyburg (Unstrut)", "weißenfels": "Weißenfels",
    "markranstädt": "Markranstädt",
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


def is_known_place(name: str | None) -> bool:
    """True, wenn der reine Ortsname (z. B. "Naumburg (Saale)", "Halle") im Gazetteer steht.
    Exakter Namensvergleich – kein Teilstring (sonst trifft "Reithalle" auf "Halle")."""
    if not name:
        return False
    n = name.lower().split("(")[0].strip()
    return n in GAZETTEER or name.lower().strip() in GAZETTEER


def nearest_name(coord, max_km: float = 8.0) -> str | None:
    """Anzeigename des nächstgelegenen Orts aus dem Gazetteer (für Quellen, die nur Koordinaten liefern)."""
    if not coord:
        return None
    best, bd = None, max_km
    for name, c in GAZETTEER.items():
        d = haversine(c, coord)
        if d < bd:
            best, bd = name, d
    return DISPLAY.get(best, best.title()) if best else None
