# Wuselkompass (früher „Spielraum") – Projekt-Übergabe / Stand

Web-App, die Kinder-/Familienveranstaltungen für Leipzig + 60 km aus vielen Quellen
aggregiert. Stdlib-only Python (kein pip nötig). Datenbank: `data/events.db` (SQLite).

## Starten / Bedienen (macOS, ohne Terminal)
Doppelklick im Projektordner: **Start.command** (Server + Browser), **Aktualisieren.command**
(Crawl), **Ende.command** (stoppt + sichert auf GitHub), **Sichern.command** (nur sichern,
App läuft weiter), **Export.command** (CSVs erzeugen + Ordner öffnen). Start.command holt
vorher den neuesten Stand von GitHub (Repo: Strumser/Wuselkompass, privat).
Manuell: `python3 -m webapp.serve` / `python3 -m crawler.run` / `python3 -m tools.report`.
App: http://localhost:8000

## Arbeitsweise (Entscheidung 2026-07-11): erst die Datenbank, dann das Frontend
Crawler und Webapp sind bereits über die SQLite-Datei entkoppelt (Crawler schreibt, Webapp
liest nur). Frontend gilt als „gut genug" und wird eingefroren; Fokus liegt jetzt auf
**Datenqualität**, betrachtet UNABHÄNGIG vom Frontend über zwei CSVs in `data/export/`
(`tools/report.py`, Doppelklick **Export.command**, öffnen in Numbers):
- **events.csv** – eine Zeile je Event in der DB = die Inhalte (Titel/Datum/Ort prüfen,
  Dubletten/Müll finden).
- **crawl_report.csv** – eine Zeile je Quelle: gefunden/übernommen/verworfen (vergangen,
  außerhalb 60 km) + finale DB-Zahl. Zeigt, wo eine Quelle klemmt (verworfene Events stehen
  NICHT in der DB, also nur hier sichtbar). Wird bei jedem Crawl (`crawler/run.py`) geschrieben.
- Bekannter DB-Qualitätsfund: `delitzsch-stadt` (u. a.) liefert datumslose Meldungen (keine
  Events); im Frontend unsichtbar (Filter `start_at<>''`), liegen aber in der DB. → aufräumen.
- „Fertig"-Maßstab pro Event: Titel, gültiges Startdatum, Ort/Stadtteil aufgelöst, im Radius,
  nicht vergangen, keine Dublette; Abdeckung: alle gewollten Quellen aktiv und > 0.

## Aufgabenstand (aktualisiert 2026-10-10)
Stand: 47 Quellen waren am 03.10. aktiv; seit 10.10. zusätzlich abgeschaltet: 5× `leipzig-leben-*`,
`lichtblick-familien` (Nutzerentscheidungen). Letzter Crawl 03.10. (2257 Events); frischer Crawl steht aus.
**Entschieden (nicht weiterverfolgen):** 60-km-Umkreisfilter allgemein; Ortszuordnung bei meinestadt
(Veranstaltungsorte in Gera/Glauchau/… werden der Seitenstadt zugeordnet – bekannte Schwäche, akzeptiert);
leipzig-leben; lichtblick-familien; „Konzert" bei leipzig-im; weitere urbanite-Rubriken (nur Kinder & Familie).
**Erledigt (03.10.):** leipzig-im, urbanite, theater-junge-welt, tourismus-wurzen, kultur-wurzen,
grimma-stadt, delitzsch-stadt, tiergarten-delitzsch neu angebunden; Einträge ohne Datum aussortiert
(`ohne_datum.csv`); meinestadt-Gegenprobe (`gegenprobe.csv`, `gegenprobe_fehlt.csv`).
**Crawl-Dauer (10.10.):** vorher 651 s sequentiell (526 Abrufe, 1 s Pause/Host). Umgesetzt:
(A) Termin-Detailseiten 7 Tage im Cache (`extractors.DETAIL_MAX_AGE`), (B) Quellen verschiedener Hosts
parallel sammeln (`run._collect_parallel`, je Host nacheinander, Verarbeitung/Speichern weiter in
Quellenreihenfolge; `fetch._throttle` threadsicher, Cache-Schreiben atomar). Messung: kalt 160 s,
warm 52 s (davon ~52 s = 52 fehlgeschlagene rausgegangen-Abrufe à 1 s Pause). DB-Ergebnis identisch
zum sequentiellen Lauf (bis auf +1 Event bei eventfinder-grimma).
⚠ **rausgegangen.de antwortet 403** (Bot- UND Browser-UA): zuerst 52 feste Adressen (u. a. Kategorien
Ausstellung/Markt) in jedem Lauf, beim Test am Ende alle. Vermutlich Rate-Limit/WAF nach vielen
Abrufen am 10.10. (4 Voll-Läufe + Tests in <1 h). Alte Events (122) bleiben in der DB und laufen aus.
Offen: Verhalten beobachten, nicht erneut hämmern; Vorschlag: 403 nicht erneut versuchen
(Fehler-Cache) und Quelle nach n× 403 in Folge abbrechen. Hinweis: der Zähler „[error]" zählt
fetch-Fehler NICHT – auf `[fetch] Fehler` achten.
**Offen sonst:** keine konkrete Datenbank-Aufgabe mehr. Ideen: Frontend-Durchgang (Frontend war
eingefroren), urbanite-Rubriken, Gegenprobe-Auswertung.

## Architektur (Dateien)
- `crawler/fetch.py` – HTTP + Cache (6 h) + Rate-Limit (1 s/Host). Default-UA = `EventBot`;
  Browser-UA nur bei `"ua":"browser"` in der Quelle (WICHTIG: meinestadt/lipzkidz **blocken**
  den Browser-UA mit 403 → Default lassen!).
- `crawler/extractors.py` – JSON-LD (`_walk_jsonld` steigt in ALLE Werte ab, auch
  `mainEntity`), WordPress-API, RSS, iCal, `rausgegangen_api`, `kreuzer_api` (JSON, iteriert
  21 Tage), `listing_detail_jsonld`, `leipziginfo_events` (Microdata).
- `crawler/adapters_html.py` – HTML-Parser: `parse_leipzig_de`, `parse_leipzig_im`,
  `parse_urbanite`. Registry `PARSERS`.
- `crawler/pipeline.py` – Dedup, Geo/60 km (`geo.py`), **family_score** (`classify_family`),
  Ort/Stadtteil, `is_future` (nutzt `end_at` → mehrtägige bleiben).
- `crawler/run.py` – Orchestrator; Dispatch je `type`; Purge vergangener Termine
  (per `end_at`); schreibt `data/status.json` (Sync-Status).
- `db/store.py` – Schema (events + venues).
- `webapp/serve.py` – Webapp (Design „Spielraum", Datumsfilter=heute/nur dieser Tag,
  min=heute; Ort/Stadtteil; Quellen-Seite; Status im Header). Start-Crawl nur wenn
  letzter Sync > 6 h. Reihenfolge: Templates via `.format`, CSS als `{style}`-Arg.
- `sources.json` – 39 aktive Quellen. `KATEGORIEN_freigabe.md`, `QUELLEN_recherche.md`,
  `BAUPLAN_event-crawler-leipzig.md`.

## Diese Session erledigt
- Design aus Handoff `design_handoff_spielraum/` 1:1 umgesetzt.
- Neue Leipzig-Quellen: **kreuzer** (~82 fam), **urbanite** (~69 fam), ahoi-leipzig (0 fam),
  leipziginfo (~0). l-iz zurückgestellt (redaktionell, kein Event-Datum).
- Bugfixes: UA pro Quelle (Regression meinestadt/lipzkidz 403 behoben), JSON-LD
  `mainEntity`-Verschachtelung, Mehrtages-Events (end_at) in is_future/Purge/Anzeige.
- Datumsfilter „nur dieser Tag", min=heute; Vergangenes wird gelöscht.
- 3 .command-Skripte.

## ERLEDIGT (Session 2026-07-11b) – Aufgabe 1: freigegebene Kategorien angebunden
Umsetzung: pro freigegebener Kategorie **eigener Quelleneintrag** in `sources.json` mit
`family_default: 0.4` (lockert den Familienfilter → Events ohne Kinder-Stichwort erreichen
trotzdem ≥ 0.3 und werden angezeigt). Alle Einträge einzeln getestet, liefern Events durch.
- **leipzig-leben** (4 rss-Feeds): `leipzig-leben-tanz-theater`, `-festivals`,
  `-kunst-ausstellungen`, `-gaming-adventure`  ✓ (je ~10 Items)
- **rausgegangen** (6 listing_jsonld): `rausgegangen-aktiv-kreativ`, `-theater`,
  `-feste-festival`, `-ausstellung`, `-markt`, `-shows-performances`  ✓ (je ~24–32)
- **kreuzer** (3 Ressorts): `kreuzer-theater`, `-literatur`, `-umland`  ✓. Dafür Code
  angepasst: `ressort` jetzt pro Quelle konfigurierbar (run.py Dispatch + extractors.py
  `kreuzer_api` source_url). Bestehender `kreuzer`-Eintrag hat jetzt `ressort:"kinder-familie"`.
- **leipzig-im** (3 Rubriken): `leipzig-im-fuehrung`, `-fest-festival`, `-umland`  ✓
  (67/22/31 Events, Parser funktioniert unverändert).

### ⚠️ Abweichungen von KATEGORIEN_freigabe.md (Doku-Annahmen waren falsch)
- **leipzig-im „Verschiedenes"** existiert NICHT als Rubrik auf der Seite → nicht angebunden.
- **leipzig-im „Ausstellungen"** hat eine andere URL-/HTML-Struktur (`section=Ausstellungen`,
  nicht `sort=rubrik`); der `leipzig_im`-Parser liefert dort 0 → nicht angebunden.
- **Kontroll-Testfall KAOS-Kultursommer**: liegt bei leipzig-im tatsächlich unter **Konzert**
  (nicht „Verschiedenes"). „Konzert" hat der Nutzer bewusst NICHT freigegeben → KAOS taucht
  weiterhin nicht auf. **Rückfrage an Nutzer:** Konzert doch freigeben? (bringt viele
  Nicht-Familien-Konzerte mit).
- Noch offen wie gehabt: urbanite/meinestadt/leipzig.de Kategorie-Nav ist JS.

## ERLEDIGT (Session 2026-07-11b) – Aufgabe 2: Rating abgeschafft, Ansicht-Umschalter
Nutzer-Entscheidung: Der Stichwort-Score ist sinnlos, wo eine Seite keine Kategorie hat
(er entschied über nur 8 von 1298 angezeigten Events, teils Fehltreffer wie „Kinder der
Wende"). **Umsetzung:**
- **`family_score` als Anzeige-Filter entfernt** (`webapp/serve.py`, `query_events`): kein
  `family_score>=0.3` mehr, kein Schlagwortfilter im UI. (`classify_family` in pipeline.py
  bleibt vorerst – füllt weiterhin `categories`/`age_min/max`; nur nicht mehr zum Filtern.)
- **Relevanz jetzt an der Quelle statt am Event:** Gruppe-C-Aggregatoren in `sources.json`
  mit `"scope": "general"` markiert (13 Quellen: eventfinder×6, tourismus-/kultur-wurzen,
  grimma-/delitzsch-/markkleeberg-stadt, ahoi-leipzig, leipziginfo). Alle anderen = kuratiert.
- **Ansicht-Umschalter** im Filter-Formular (`name="ansicht"`), zwei Werte:
  - **„Familie"** (Standard): nur kuratierte Quellen, ALLES davon (kein Rating).
  - **„Alle Events"** (`?ansicht=alle`): ungefiltert, inkl. general-Quellen.
  Helfer `general_source_ids()` liest scope aus sources.json; Familie-Ansicht schließt sie
  per `source_id NOT IN (...)` aus.
- Quellen-Seite: Spalte „fam" → „Ansicht" (Familie / Alle Events), Lead-Text angepasst.
- Verifiziert (18.07.2026): Familie 65, Alle Events 81, kein general-Leck in Familie-Ansicht.
  **App muss neu gestartet werden** (Ende.command → Start.command), damit der laufende
  Server den neuen Code lädt.

### Mehrtägige Events in der Tagesansicht (Folge-Fix)
Problem: laufende mehrtägige Events (z. B. „Jahr der jüdischen Kultur" 14.12.–12.12.) standen
mit ihrem alten START-Datum ganz oben. Fix in `webapp/serve.py` `render()`:
- Sortierung: heute STARTENDE zuerst, schon LAUFENDE danach.
- Laufende (`start_at`-Tag < gewählter Tag): Chip zeigt „bis + Enddatum" statt Startdatum,
  Meta-Zeile beginnt mit „läuft noch".

## Quellen-Gruppen (Kurz)
- A kategorie-gefiltert: leipzig-im, leipzig-leben, rausgegangen, kreuzer, urbanite,
  meinestadt×12, leipzig-de.
- C allgemein (alles + Score): eventfinder×6, tourismus-wurzen, grimma/delitzsch/
  markkleeberg-stadt, kultur-wurzen, ahoi-leipzig, leipziginfo.
- D inhärent familiär: theater-junge-welt, muetterzentrum-fiz, lipzkidz,
  leipziger-kinderfestival, lichtblick-familien, mamalismus, leipzig-fuer-lau, tiergarten-delitzsch.

## Entscheidungen 2026-10-31
- **Dauer-Locations:** Auswahl vom Nutzer liegt vor (91 von 103; Draußen-Spielplätze, B7–B10, D4 abgewählt):
  A1–A4, B1–B6, C1–C14, D1–D3, D5–D15, E1–E18, F1–F10, H1–H12, I1–I11, J1–J2. Kürzel siehe DAUERLOCATIONS_recherche.md.
- **Geplant (Phasen):** 1 Quellen-Gesundheit nur als Erreichbarkeits-Ampel (bei Rot Nutzer informiert, Claude sucht Ursache),
  2 Datenmodell Orte + wöchentliche Angebote, 3 Altersfilter (nur „ab 2 / ab 3 / ab 4"), 4 Reiter „Orte" + Wochenraster,
  5 Reparatur nur nach manueller Freigabe. Arbeit auf Branch `v2-orte-alter`.
- **Chemnitz wird eigene Region** (Variante 3, ca. 69 km von Leipzig): eigene Quellen + Orte + Ortsfilter; Recherche-Agenten laufen.

## v2 (Branch `v2-orte-alter`, 31.10.2026) – was gebaut wurde
Dieser Abschnitt ersetzt ältere Aussagen weiter oben, wo sie widersprechen (z. B. „60-km-Radius", „Löschen").
- **Archiv statt Löschen:** vergangene Termine bekommen `events.archived_at` (store.archive_past); alle Abfragen
  filtern `archived_at IS NULL`. Ein erneut gesehener Termin wird wieder aktiv. Zweck: Gedächtnis für jährlich
  wiederkehrende Veranstaltungen (spätere Prognose/Erinnerung).
- **Regionen** (`geo.REGIONS`): Halle (25 km), Chemnitz (30 km), Leipzig (60 km); `events.region`, Region-Filter in
  der App. `pipeline.enrich` prüft gegen die Regionen (statt fest 60 km um Leipzig); unbekannter Ort → Quellenregion,
  behalten. Quellen, die Koordinaten liefern (`lat`/`lon`), werden direkt genutzt (`geo.nearest_name`).
- **Orte** (`data/orte.json`, 115 Einträge: 91 aus Leipzig/Halle/Umland + 24 Chemnitz) und **wiederkehrende
  Angebote** (`data/wochenangebote.json`, 33 Angebote, 71 Wochentags-Einträge): handgepflegte JSON-Dateien, beim
  Crawl und beim Webapp-Start in die Tabellen `places`/`recurring` gespiegelt (`store.sync_places`). Herkunft/Erzeugung:
  `tools/seed_orte.py` (einmalig; danach JSON von Hand pflegen). Regeln: weekly, biweekly (anchor), 1st3rd, last, monthly.
  Ferien werden NICHT berechnet, nur als Hinweis („nicht in den Schulferien") angezeigt.
- **Altersfilter:** „Mein Kind: 2/3/4 Jahre" + „nur mit Altersangabe". Unbekanntes Alter bleibt sichtbar („Alter offen").
  Alterserkennung erweitert (`Alter: 5+`, `4+ Jahre`, `Alter: 3–6`) und kuratiertes Standardalter je Quelle
  (`age_default`, z. B. FiZ 0–6). Events mit Altersangabe: nur ca. 9 % → Filter greift v. a. bei Orten/Wochenraster.
- **Quellen-Gesundheit:** `source_runs` (Messwerte je Crawl: Treffer, Abrufe, Fehlercodes, Dauer, „nur hier"),
  `source_checks` (Erreichbarkeitsprüfung), `crawler/health.py` (Ampel-Regeln: Rot < 40 % des üblichen Werts bzw.
  0 Treffer/nicht erreichbar/>50 % Abruffehler; Gelb < 70 %, ≥30 % ohne Datum, ≥10 % Fehler, >3 Tage alt;
  `allow_empty` für erwartet leere Quellen). Quellen-Reiter mit Ampel, Verlauf, Befund, Knöpfen „Erreichbarkeit jetzt
  prüfen" und „abschalten/einschalten" (schreibt `sources.json`). Webapp bindet NUR an 127.0.0.1 (Host/Origin-Prüfung).
- **Chemnitz** (eigene Region): `chemnitz-de` (Rubrik Kinder & Familie, Browser-UA!), `theater-chemnitz`
  (Figurentheater + Stichwörter des Hauses, Monatslinks mit cHash), `czr-chemnitz` (GeoJSON, nur „Alle Events"),
  `meinestadt-chemnitz` (Gegenprobe). Nicht gebaut: smac (steckt in chemnitz.de), Stadtbibliothek (keine Kinder-
  Rubrik), Freie Presse (keine Kinder-Rubrik; JSON-LD, ?page=N, 15/Seite – nur falls „Alle Events" erweitert wird).
- **Crawl:** parallel je Host (160 s kalt), Detailseiten 7 Tage im Cache.
- **Bewusst NICHT umgesetzt (Nutzerentscheidung):** Reparatur-Workflow (Schritt 9), Concierge/Eingangskorb (Schritt 10).
  Bei roter Ampel: Nutzer bittet Claude um Ursachensuche.

## Alterserkennung + Dubletten (Branch `v2-orte-alter`, 01.11.2026)
- `pipeline.extract_age`: Zahlenmuster (ab N Jahren, N–M Jahre, Monate, Zahlwörter, „Alter: 3–6"), Preis-Kontext
  („Kinder bis 3 frei") wird ignoriert; Gruppenwörter: Baby = 0–1, Krabbel = 0–2, Kleinkind = ab 1, Vorschul/Kita = 3–6.
- Extraktoren liefern `_fulltext` (Langtext, wird nicht gespeichert). `detail_age: true` in sources.json
  (leipzig-de, leipzig-im*, urbanite) lädt Detailseiten nur für künftige Termine ohne Alter (7 Tage Cache).
- `crawler/dedupe.py`: Tag + Region + Titelähnlichkeit ≥ 0,88 + Ort/Venue nicht widersprüchlich → `dup_of`/`also_in`
  (nichts gelöscht, Alter wird übernommen). Kontrolle: `data/export/dubletten.csv`.
- Messung: Altersabdeckung 12 % → 20 % (500 von 2489 sichtbaren Terminen); 251 Dubletten markiert.
- Offen: czr-chemnitz, chemnitz-de, kreuzer-theater, leipzig-im-fuehrung haben 0 % Alter (Detail-Parser/`detail_age` prüfen);
  dubletten.csv stichprobenartig auf Falschtreffer prüfen; Merge in main erledigt (13.11.2026), Branch gelöscht.

## Bewertung durch Claude (13.11.2026) – steuert die Ansicht „Familie"
- `data/bewertungen.json` (im Repo, Quelle der Wahrheit): je normalisiertem Titel `urteil` (passt | vielleicht | nein),
  geschätztes Alter `ab`/`bis`, `grund`. Spiegelung in Tabelle `ratings`; `events.rkey` = Titel-Schlüssel (`store.rating_key`).
- Familie = Urteil passt/vielleicht (aus JEDER Quelle, auch „Alle Events"-Quellen) + noch unbewertete Termine der
  Familienquellen. „nein" nur unter „Alle Events". Altersfilter nutzt das geschätzte Alter, wenn der Termin keins nennt
  (Karte: „≈ ab 3", Tooltip „von Claude geschätzt").
- Ablauf in einer Sitzung: `python3 -m tools.bewerten offen 14` → Claude liest `data/export/zu_bewerten.json`, schreibt
  Urteile als JSON → `python3 -m tools.bewerten import DATEI`. Weg 2 (automatisch per Claude-API) bewusst NICHT gebaut (Entscheidung 13.11.: API wäre extra zu bezahlen, Abo deckt sie nicht).
- Entdecken-Seite zeigt Vermerk „KI-Bewertung nötig: N Termine …“, solange Titel der nächsten 14 Tage unbewertet sind
  (`serve.rating_note`). Nutzer sagt dann in einer Sitzung „Bewerte die neuen Termine“.
- Erster Durchgang: 904 Titel der nächsten 14 Tage (55 passt, 118 vielleicht, 731 nein). Familie pro Tag ~25–50 statt ~200–300.
- Kriterium: passt = für 2–4-Jährige gemacht (Puppentheater 3+, Bilderbuchkino, Krabbel-/Spielgruppen, Laternenumzug);
  vielleicht = Kleinkind kann gut mit (Märkte, Weihnachtsmärkte, Panorama) oder Grenzfall (ab 4/5, Babyangebote 0–2);
  nein = Erwachsenenprogramm, ab 6, Kurse für Eltern.
- Sortierung je Tag: „passt" zuerst, dann vielleicht/unbewertet, „nein" zuletzt (jeweils nach Uhrzeit).
- Neu im Altersparser: „(3+)", „3plus".
