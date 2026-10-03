# Familien-Events Leipzig & Umgebung — Prototyp

Metacrawler + Webapp für Veranstaltungen (Fokus: Familien mit Kleinkindern, 0–6 J.)
im Umkreis von 60 km um Leipzig.

**Bewusst stdlib-only** (Python 3.11) — läuft ohne `pip install`.

## Schnellstart

```bash
cd event-crawler-leipzig
python3 -m crawler.run      # Quellen crawlen -> data/events.db füllen
python3 -m webapp.serve     # Webapp: http://localhost:8000
```

## Architektur (Zwei-Spuren-Strategie)

```
sources.json → crawler/run.py → extractors (Fingerprint-Stapel) → pipeline → SQLite → webapp
```

- **crawler/extractors.py** — geschichteter Extraktor-Stapel:
  1. JSON-LD / schema.org Event (universell)
  2. WordPress „The Events Calendar"-REST-API
  3. iCal (.ics)
  4. RSS/Atom (mit Autodiscovery)
  - `fingerprint()` erkennt pro Seite das CMS/Muster; `type:"auto"` in `sources.json`
    wählt automatisch den passenden Weg (siehe Quelle `grimma-stadt`).
- **crawler/pipeline.py** — Dedup (Titel+Tag+Ort), Geo/60-km-Radius,
  **Familien-/Alters-Klassifikation** (`family_score`, `age_min/max`).
- **crawler/geo.py** — Gazetteer der Region + Haversine (kein Nominatim-Zwang).
- **db/store.py** — SQLite mit zwei Tabellen: `events` (Termine) + `venues`
  (Dauer-Locations wie Zoos, Indoorspielplätze, Bauernhöfe).
- **webapp/serve.py** — Liste + Leaflet-Karte + Filter (Suche, Zeitraum, Umkreis,
  Familien-Relevanz, Kindalter, gratis). Auch JSON: `/api/events.json`.

## Quellen pflegen

`sources.json` → Eintrag mit `type`: `jsonld` | `wp_api` | `ical` | `rss` | `auto`.
`active:false` schaltet eine Quelle ab. `venues_seed` = Dauer-Locations.

## Erste Ergebnisse (Beispiel-Lauf)

~180 Events aus 9 aktiven Quellen; FiZ/Mütterzentrum liefert die echten
0–6-Krabbelgruppen, meinestadt/eventfinder die Breite, Theater der Jungen Welt +
Blogs die Kultur. Dedup führt dieselben Events aus mehreren Portalen zusammen.

## Nächste Ausbaustufen (Phase 2–4)

- **LLM-Extraktor** als Fallback für strukturloses HTML (VILLA, Stadtbibliothek …).
- **TYPO3 sf_event_mgt-Adapter** (Bibliothek 16 Standorte, Zoo, Schlösser).
- **Kommunal-CMS-Sachsen-Adapter** (ein Adapter für viele Städte).
- **Playwright** für JS-Seiten (rosakrokodil, kindaling, kribbelbunt).
- **Discovery-Schicht** automatisieren (Themen-Suchen × Orte → neue Quellen).
- Nominatim-Geocoding mit Cache für exakte Adressen.
- Produktions-Stack: FastAPI + Postgres + Cronjob.

Details & Quellenregister: siehe `../BAUPLAN_event-crawler-leipzig.md` und
`../QUELLEN_recherche.md`.
