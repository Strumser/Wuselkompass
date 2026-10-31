"""Einmaliges Erzeugen von data/orte.json und data/wochenangebote.json aus den Recherche-Dateien.

Danach sind die JSON-Dateien die Quelle der Wahrheit und werden von Hand gepflegt; dieses Skript ist
nur zur Nachvollziehbarkeit (Herkunft: DAUERLOCATIONS_recherche.md, CHEMNITZ_recherche.md, Nutzerauswahl).

Aufruf:  python3 -m tools.seed_orte
"""
from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from crawler import geo      # noqa: E402

# Auswahl des Nutzers (31.10.2026): 91 Orte aus Leipzig/Halle/Umland + alle Chemnitz-Orte
SEL = (["A1", "A2", "A3", "A4"] + [f"B{i}" for i in range(1, 7)] + [f"C{i}" for i in range(1, 15)]
       + ["D1", "D2", "D3"] + [f"D{i}" for i in range(5, 16)] + [f"E{i}" for i in range(1, 19)]
       + [f"F{i}" for i in range(1, 11)] + [f"H{i}" for i in range(1, 13)]
       + [f"I{i}" for i in range(1, 12)] + ["J1", "J2"] + [f"CH{i}" for i in range(1, 25)])

# Art und Drinnen/Draußen je Eintrag
KIND = {
    "A1": ("tiere", "nein"), "A2": ("freizeit", "teils"), "A3": ("spielcafe", "ja"),
    "A4": ("familienzentrum", "ja"),
    "B1": ("spielcafe", "ja"), "B2": ("spielcafe", "ja"), "B3": ("indoor", "ja"),
    "B4": ("indoor", "ja"), "B5": ("indoor", "ja"), "B6": ("indoor", "ja"),
    **{f"C{i}": ("familienzentrum", "ja") for i in range(1, 13)},
    "C13": ("bibliothek", "ja"), "C14": ("bibliothek", "ja"),
    **{f"D{i}": ("tiere", "nein") for i in range(1, 16)},
    "E1": ("museum", "ja"), "E2": ("museum", "ja"), "E3": ("museum", "teils"),
    "E4": ("museum", "teils"), "E5": ("museum", "teils"), "E6": ("freizeit", "nein"),
    "E7": ("museum", "ja"), "E8": ("museum", "ja"), "E9": ("museum", "teils"),
    "E10": ("museum", "ja"), "E11": ("museum", "ja"), "E12": ("freizeit", "nein"),
    "E13": ("museum", "ja"), "E14": ("museum", "ja"), "E15": ("freizeit", "nein"),
    "E16": ("museum", "ja"), "E17": ("museum", "ja"), "E18": ("freizeit", "nein"),
    **{f"F{i}": ("bad", "ja") for i in range(1, 11)},
    "H1": ("indoor", "ja"), "H2": ("indoor", "ja"), "H3": ("spielcafe", "ja"),
    "H4": ("familienzentrum", "ja"), "H5": ("familienzentrum", "ja"),
    "H6": ("familienzentrum", "ja"), "H7": ("familienzentrum", "ja"),
    "H8": ("freizeit", "nein"), "H9": ("familienzentrum", "ja"), "H10": ("indoor", "ja"),
    "H11": ("indoor", "ja"), "H12": ("museum", "teils"),
    "I1": ("indoor", "ja"), "I2": ("freizeit", "nein"), "I3": ("indoor", "ja"),
    **{f"I{i}": ("familienzentrum", "ja") for i in range(4, 10)},
    "I10": ("freizeit", "teils"), "I11": ("freizeit", "nein"),
    "J1": ("familienzentrum", "ja"), "J2": ("familienzentrum", "ja"),
    "CH1": ("spielcafe", "ja"), "CH2": ("indoor", "ja"), "CH3": ("indoor", "ja"),
    "CH4": ("indoor", "ja"),
    **{f"CH{i}": ("familienzentrum", "ja") for i in range(5, 14)},
    "CH14": ("museum", "ja"), "CH15": ("museum", "ja"), "CH16": ("freizeit", "teils"),
    "CH17": ("bibliothek", "ja"), "CH18": ("bad", "ja"), "CH19": ("bad", "ja"),
    **{f"CH{i}": ("tiere", "nein") for i in range(20, 24)}, "CH24": ("freizeit", "teils"),
}

HALLE = {"D1", "D2", "D6", "D7", "D8", "D9", "D14", "E14", "E15", "F4", "F8", "F9", "F10"} | \
        {f"H{i}" for i in range(1, 13)}


def region_of_id(eid: str) -> str:
    if eid.startswith("CH"):
        return "chemnitz"
    return "halle" if eid in HALLE else "leipzig"


def parse_md(path: str, prefix_re: str) -> dict:
    """Liest Einträge der Form '- [ ] **B1 Name** – Text' oder '- **CH1 Name** – Text'."""
    out = {}
    lines = open(path, encoding="utf-8").read().splitlines()
    i = 0
    while i < len(lines):
        m = re.match(r"^- (?:\[[ x]\] )?\*\*(" + prefix_re + r"\d+) (.*?)\*\*(.*)", lines[i])
        if m:
            eid, name, rest = m.groups()
            j = i + 1
            while j < len(lines) and lines[j].startswith("  ") and not lines[j].startswith("- "):
                rest += " " + lines[j].strip()
                j += 1
            out[eid] = (name.strip(), rest)
            i = j
            continue
        i += 1
    return out


def level(rest: str) -> str:
    t = re.findall(r"(?:\*\*)?(✓/~|✓|~|\?)(?:\*\*)?(?:\s|\(|$|·)", rest)
    last = t[-1] if t else "?"
    return {"✓": "ok", "✓/~": "ok", "~": "mid", "?": "low"}.get(last, "low")


def clean(rest: str) -> str:
    t = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", rest)
    t = re.sub(r"\*\*(✓/~|✓|~|\?)\*\*", "", t)
    t = re.sub(r"\s*·\s*(?:✓/~|✓|~|\?)(?=\s|\(|$).*$", "", t)
    t = re.sub(r"\*\*|\*", "", t)
    t = re.sub(r"^\s*[–-]\s*", "", t)
    return re.sub(r"\s+", " ", t).strip(" ·")


def url_of(rest: str):
    m = re.search(r"\]\((https?://[^)\s]+)\)", rest)
    return m.group(1) if m else None


def parse_age(text: str):
    t = text.lower()
    num = lambda x: float(x.replace(",", "."))
    m = re.search(r"(\d+(?:,\d+)?)\s*[–-]\s*(\d+(?:,\d+)?)\s*(?:jahre|j\.|j\b)", t)
    if m:
        return num(m.group(1)), num(m.group(2))
    m = re.search(r"ab\s*(\d+)\s*monat", t)
    if m:
        return round(int(m.group(1)) / 12, 2), None
    m = re.search(r"ab\s*(\d+(?:,\d+)?)\s*(?:jahr|j\b|j\.)", t) or re.search(r"(\d+)\s*\+\s*j", t)
    mx = re.search(r"bis\s*(?:ca\.\s*)?(\d+)\s*(?:jahr|j\b|j\.)", t)
    if m or mx:
        return (num(m.group(1)) if m else None), (num(mx.group(1)) if mx else None)
    if "bis zum schuleintritt" in t:
        return None, 6.0
    return None, None


# F1–F4 stehen in der Recherche-Datei nur als Fließtext
EXTRA = {
    "F1": ("Sachsen-Therme", "Schongauer Straße 19, 04329 Leipzig-Paunsdorf · Rutschen, Wellenbad, Kinderbereich, Schwimmschule, Kinder-/Babyschwimmkurse · täglich 10–22 Uhr · ~"),
    "F2": ("Freizeitbad RIFF", "Am Riff 3, 04651 Bad Lausick · eigener Kleinkindbereich (33 °C), Babyschwimmen · ca. 35 km · ~"),
    "F3": ("Schwimmhalle Wurzen", "Wurzen · Schwimmhalle, ab 0 Jahren · ~"),
    "F4": ("Maya mare", "Halle (Saale) · Spaßbad, 0–4 Jahre laut Portal · ~"),
}
# belegte Altersangaben, die im Fließtext nicht maschinenlesbar stehen
AGE_OVERRIDE = {"B1": (0, 12), "C13": (2, None), "H2": (0, 12), "A3": (0, 5)}


def build_orte() -> list[dict]:
    items = {}
    items.update(parse_md(os.path.join(ROOT, "DAUERLOCATIONS_recherche.md"), "[A-J]"))
    items.update({k: (v[0], " – " + v[1]) for k, v in EXTRA.items()})
    items.update(parse_md(os.path.join(ROOT, "CHEMNITZ_recherche.md"), "CH"))
    out = []
    missing = []
    for eid in SEL:
        if eid not in items:
            missing.append(eid)
            continue
        name, rest = items[eid]
        meta = clean(rest)
        kind, indoor = KIND[eid]
        seg = meta.split(" · ")[0]
        addr = seg if re.search(r"\d{5}|str(?:\.|aße)?\b|platz|weg\b|allee|ring\b|gasse|markt|promenade", seg, re.I) else None
        ort = geo.locate_name(f"{addr or ''} {name} {meta}")
        if not ort:     # Stadtteile (Gohlis, Sonnenberg …) nennen den Ort nicht: aus Region ableiten
            ort = ("Bitterfeld-Wolfen" if eid == "F10" else "Halle (Saale)" if region_of_id(eid) == "halle"
                   else "Chemnitz" if region_of_id(eid) == "chemnitz" else "Leipzig" if eid[0] in "BCF" else None)
        age_min, age_max = AGE_OVERRIDE.get(eid) or parse_age(meta)
        out.append({
            "id": eid, "name": name, "kind": kind, "indoor": indoor, "region": region_of_id(eid),
            "ort": ort, "address": addr, "age_min": age_min, "age_max": age_max,
            "url": url_of(rest), "beleg": level(rest), "note": meta[:320],
            "checked_at": "2026-10-31" if eid.startswith("CH") else "2026-10-12", "status": "aktiv",
        })
    if missing:
        print("FEHLEND:", missing)
    return out


# ---------------------------------------------------------------- Wochenangebote
D = {"Mo": 0, "Di": 1, "Mi": 2, "Do": 3, "Fr": 4, "Sa": 5, "So": 6}
ALL = list(range(7))


def S(days, von, bis=None, rule="weekly", **kw):
    return {"days": [D[d] if isinstance(d, str) else d for d in days], "von": von, "bis": bis, "rule": rule, **kw}


WOCHEN = [
 dict(id="W1", place_name="Kawi Kids (Südvorstadt)", title="Offenes Spielen", region="leipzig", beleg="ok",
      hinweis="Do/So und Feiertage auch für 3–5-Jährige", slots=[
      S(ALL, "09:00", "12:00", age_min=0, age_max=2), S(ALL, "15:00", "18:00", age_min=0, age_max=2),
      S(["Do", "So"], "15:00", "18:00", age_min=3, age_max=5)]),
 dict(id="W2", place_name="Kinderwelt Gohlis (Hummelbienchen)", title="Spielzeiten (90 Min.)", region="leipzig", beleg="mid",
      age_min=0.75, age_max=4, slots=[S(["Do", "Fr"], "10:00", "11:30"), S(["Do", "Fr"], "15:30", "17:00"), S(["Sa"], "09:30", "11:30")]),
 dict(id="W3", place_name="Familienzentrum Tüpfelhausen (Leutzsch)", title="Offenes Elterncafé", region="leipzig", beleg="ok",
      age_min=0, age_max=6, slots=[S(["Mo", "Di"], "10:00", "15:30"), S(["Mi", "Do", "Fr"], "10:00", "18:00")]),
 dict(id="W4", place_name="Familienzentrum GeyserHaus (Gohlis)", title="Haus geöffnet (Krabbelstunde, Papa-Café, Familienfrühstück)", region="leipzig",
      beleg="mid", age_min=0, age_max=6, hinweis="Zeiten der einzelnen Angebote nicht belegt, Stand 01/2023", slots=[
      S(["Mo"], "09:00", "15:00"), S(["Di"], "09:00", "17:30"), S(["Mi"], "09:00", "17:00"), S(["Do"], "09:00", "14:00"), S(["Fr"], "09:00", "13:00")]),
 dict(id="W5", place_name="Familienzentrum Schönefeld (CVJM)", title="Eltern-Kind-Gruppe", region="leipzig", beleg="ok", slots=[S(["Di"], "09:00", "10:00")]),
 dict(id="W8", place_name="BWG Erlebnishaus (Halle)", title="Offener Krabbeltreff", region="halle", beleg="mid", age_min=0, age_max=2,
      hinweis="nicht in den Schulferien/an Feiertagen", slots=[S(["Mo"], "10:00", "12:00")]),
 dict(id="W9", place_name="Familiencafé Völkchen (Halle)", title="Offenes Familiencafé", region="halle", beleg="ok", age_min=0, age_max=3, slots=[
      S(["Di", "Do"], "09:30", "12:00"), S(["Mi"], "09:30", "12:00"), S(["Mi"], "14:00", "17:00"), S(["Fr"], "09:30", "12:00"),
      S(["Fr"], "14:00", "17:00", rule="1st3rd")]),
 dict(id="W10", place_name="Familiencafé Völkchen (Halle)", title="Krabbelcafé", region="halle", beleg="ok", age_min=0, age_max=1, slots=[S(["Mi"], "09:30", "11:30")]),
 dict(id="W11", place_name="Kinderschutzbund Halle", title="Krabbelgruppe", region="halle", beleg="ok", age_min=0, age_max=2, slots=[S(["Di"], "09:30", "11:30")]),
 dict(id="W12", place_name="Kinderschutzbund Halle", title="Naturzeit", region="halle", beleg="ok", slots=[S(["Mi"], "09:00", "11:00")]),
 dict(id="W13", place_name="Kinderschutzbund Halle", title="Familienfrühstück (Anmeldung)", region="halle", beleg="ok", hinweis="Anmeldung nötig", slots=[S(["Fr"], "09:30", "11:30", rule="1st3rd")]),
 dict(id="W14", place_name="Kinderschutzbund Halle", title="Familiennachmittag / Eltern-Kind-Spieletreff", region="halle", beleg="ok", slots=[S(["Do"], "15:00", "17:30")]),
 dict(id="W15", place_name="Franckesche Stiftungen Halle", title="Offene Spielgruppe", region="halle", beleg="mid", age_min=0, age_max=3,
      hinweis="Quellen widersprüchlich, Zeiten bitte prüfen", slots=[S(["Di"], "14:00", "17:00"), S(["Mi"], "12:30", "14:30"), S(["Do"], "10:00", "12:00")]),
 dict(id="W16", place_name="IRIS e. V. (Halle, Schleiermacherstr. 39)", title="Offene Krabbelgruppen", region="halle", beleg="mid", slots=[
      S(["Di", "Do"], "09:00", "12:00", age_min=0, age_max=1.5), S(["Fr"], "09:00", "11:00", age_min=1, age_max=3)]),
 dict(id="W17", place_name="Baby & Me (Halle, Schleiermacherstr. 15)", title="Krabbel-/Spielgruppen", region="halle", beleg="mid", age_min=0, age_max=2, slots=[S(["Mi", "Do"], "09:30", "11:30")]),
 dict(id="W18", place_name="Geburtshaus Lebenslicht (Halle)", title="Offene Krabbelgruppe", region="halle", beleg="mid", age_min=0, age_max=1, slots=[S(["Mi"], "09:00", "10:00")]),
 dict(id="W19", place_name="eXxtra CVJM Halle", title="Krabbelgruppe", region="halle", beleg="mid", age_min=0, age_max=2, slots=[S(["Di"], "09:00", "12:00")]),
 dict(id="W20", place_name="Die Wasserflöhe (Halle)", title="Babyschwimmen 0–2,5 J. / Eltern-Kind-Schwimmen 2,5–5 J.", region="halle", beleg="ok", age_min=0, age_max=5,
      hinweis="Kurs mit 6–8 Einheiten, Anmeldung", slots=[S(["Mi"], "14:30", "16:30")]),
 dict(id="W21", place_name="Landesmuseum für Vorgeschichte (Halle)", title="Familiennachmittag (letzter Sonntag im Monat)", region="halle", beleg="mid", slots=[S(["So"], None, None, rule="last")]),
 dict(id="W22", place_name="Bürger- und Vereinshaus Bad Dürrenberg", title="Eltern-Kind-Gruppe (Frühe Hilfen), 14-tägig", region="halle", beleg="mid", age_min=0, age_max=3,
      slots=[S(["Do"], "10:00", "12:00", rule="biweekly", anchor="2026-08-13")]),
 dict(id="W23", place_name="Norbertsaal Merseburg (St. Norbert)", title="Krabbelgruppe", region="halle", beleg="mid", age_min=0, age_max=2, hinweis="nicht in den Schulferien", slots=[S(["Di"], "09:30", "11:00")]),
 dict(id="W24", place_name="Ev. Kirche Mücheln-Langeneichstädt", title="Krabbelgruppe", region="halle", beleg="mid", age_min=0, age_max=2, slots=[S(["Di"], "09:30", "11:00")]),
 dict(id="W25", place_name="Querfurt (Kirchplan 2)", title="SingKlangBabyZeit", region="halle", beleg="mid", age_min=0, age_max=1, slots=[S(["Do"], "10:00", None)]),
 dict(id="W26a", place_name="CVJM Bad Lauchstädt", title="Krabbelgruppe", region="halle", beleg="mid", age_min=0, age_max=2, slots=[S(["Mo"], "09:30", "11:00")]),
 dict(id="W26b", place_name="CVJM Landsberg", title="Krabbelgruppe", region="halle", beleg="mid", age_min=0, age_max=2, slots=[S(["Do"], "09:30", "11:00")]),
 dict(id="W26c", place_name="CVJM Petersberg OT Teicha", title="Krabbelgruppe", region="halle", beleg="mid", age_min=0, age_max=2, slots=[S(["Mi"], "09:30", "11:00")]),
 dict(id="W26d", place_name="CVJM Salzatal (Schochwitz)", title="Krabbelgruppe", region="halle", beleg="mid", age_min=0, age_max=2, slots=[S(["Di"], "09:30", "11:00")]),
 dict(id="W27", place_name="Wettin-Löbejün", title="Eltern-Kind-Treff (monatlich, Termin erfragen)", region="halle", beleg="mid", age_min=0, age_max=3, slots=[S(["Di"], "15:00", "16:30", rule="monthly")]),
 dict(id="W28", place_name="Gemeindehaus Lieskau (DLL)", title="Krabbelgruppe", region="halle", beleg="mid", age_min=0, age_max=2, slots=[S(["Do"], "10:00", "11:00")]),
 dict(id="W29", place_name="Kita Bärchen Eilenburg", title="Offene Krabbelgruppe", region="leipzig", beleg="ok", age_min=0, age_max=1.5, hinweis="Rhythmus widersprüchlich, Zeiten klären", slots=[S(["Mo"], "09:00", "10:30")]),
 dict(id="W30", place_name="Familienzentrum Markkleeberg (Lichtblick)", title="Offener Treff (0–7 J.) und Krabbelgruppe", region="leipzig", beleg="ok", slots=[
      S(["Do"], "15:00", "17:00", age_min=0, age_max=7), S(["Mi"], "09:30", None, age_min=0, age_max=2, hinweis="Krabbelgruppe, Orangerie Gaschwitz")]),
 dict(id="W31", place_name="Residenzschloss Altenburg", title="Kartenmacherwerkstatt (Drucktag)", region="leipzig", beleg="ok", slots=[S(["Fr"], "14:00", None)]),
 dict(id="W32", place_name="Jump'n'Play Chemnitz (Kaßberg)", title="MINIJUMPY (inkl. Tageskarte, ab 8 €)", region="chemnitz", beleg="ok", age_min=0, age_max=4, slots=[S(["So"], "09:00", "10:00")]),
]


def build_wochen() -> list[dict]:
    out = []
    for w in WOCHEN:
        w = dict(w)
        w["checked_at"] = "2026-10-12"
        if "hinweis" not in w:
            w["hinweis"] = None
        out.append(w)
    return out


def main():
    orte = build_orte()
    with open(os.path.join(ROOT, "data", "orte.json"), "w", encoding="utf-8") as f:
        json.dump(orte, f, ensure_ascii=False, indent=1)
    wochen = build_wochen()
    with open(os.path.join(ROOT, "data", "wochenangebote.json"), "w", encoding="utf-8") as f:
        json.dump(wochen, f, ensure_ascii=False, indent=1)
    print(f"orte.json: {len(orte)} Orte | wochenangebote.json: {len(wochen)} Angebote "
          f"({sum(len(s['days']) for w in wochen for s in w['slots'])} Wochentags-Einträge)")
    from collections import Counter
    print("Art:", dict(Counter(o['kind'] for o in orte)))
    print("Region:", dict(Counter(o['region'] for o in orte)))
    print("Alter bekannt:", sum(1 for o in orte if o['age_min'] is not None or o['age_max'] is not None), "von", len(orte))
    print("Adresse erkannt:", sum(1 for o in orte if o['address']), "| Ort erkannt:", sum(1 for o in orte if o['ort']))


if __name__ == "__main__":
    main()
