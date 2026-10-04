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

## Aufgabenstand (aktualisiert 2026-10-03, nach frischem Crawl)
Letzter Crawl 03.10.2026 22:20: 1541 Events in DB, Crawl dauert ~7 Min (viele Detailseiten).
Heute: Familie 132 / Alle Events 176.
**Entschieden:** Umkreis-Filter (60 km) wird NICHT weiterverfolgt – der Radius ergibt sich
indirekt aus den gewählten Quellen. (Erledigt/gestrichen.)
**Offen – nach Analyse des Crawl-Berichts vom 03.10.2026 (Reihenfolge nach Gewicht):**
1. **Quellen liefern 0:** ✅ behoben am 03.10.: `leipzig-im` (neues Karten-Layout, alter Parser als
   Rückfall), `urbanite` (neuer Typ `urbanite_days`: Tagesseiten `/leipzig/events/<datum>/`, 21 Tage,
   Rubrik per CSS-Klasse `event_category-kinder-familie-2` gefiltert; weitere Rubriken über
   `categories` in sources.json möglich: buehne-theater-show, festivals-feste-open-airs,
   fuehrungen-touren-freizeit, kunst-ausstellung-museum, maerkte-messen-kongresse, sonstiges …),
   `theater-junge-welt` (neuer Typ `tdjw`: Monatsseiten mit Seitenschaltung, 6 Monate, ~370 Termine).
   ✅ `tourismus-wurzen` (03.10.): jetzt `listing_jsonld` über die Terminsuche (`suche.html?…termine=1`,
   40 Links statt 7 auf der Übersicht) + Detailseiten-JSON-LD → 40 gefunden, 20 in DB nach Dedup.
   ✅ Gleiche Umstellung (03.10.) bei `kultur-wurzen` (7), `grimma-stadt` (165), `delitzsch-stadt` (22):
   Kommunal-CMS, Terminsuche → Detailseiten-JSON-LD; vorher nur Pressemeldungen (RSS). Alle vier
   bleiben unter „Alle Events" (scope general, bewusst NICHT in „Familie": keine Kategorie auf den Seiten). `meinestadt-torgau`: 0 (evtl. nur keine Termine).
   ✅ urbanite: nur Rubrik Kinder & Familie (Nutzerentscheidung; „Sonstiges"/„Stadtleben" bewusst
   draußen). Ortsprüfung `nur_bekannte_orte`: Ort vor dem Komma der Adresse muss exakt im
   Gazetteer (`geo.is_known_place`) stehen, sonst verworfen (Coburg, Frankfurt/Oder, Großenhain
   …). Gazetteer um Freyburg, Weißenfels, Markranstädt ergänzt. urbanite deckt Grimma/Merseburg/
   Eilenburg/Delitzsch gar nicht ab (0 Events) – die kommen von anderen Quellen.
   ⚠ Bekannte Schwäche: andere Quellen haben die Ortsprüfung nicht (1284 von 2248 Events ohne
   Entfernung, `ort` fällt dann auf die Quellenstadt).
2. **Einträge ohne Datum:** ✅ 03.10.: werden beim Einlesen verworfen (`run.py`, Spalte „verworfen (ohne
   Datum)" im Crawl-Bericht), 191 alte Einträge aus der DB gelöscht. Analyse: das waren überwiegend
   Artikel, keine Termine. Textdatum-Extraktion lohnt nicht (≈17 von 191 zukünftig; leipzig-leben:
   nur 6 von 69 aktuell, weil die Feeds nur die 10 neuesten, meist alten Artikel pro Rubrik liefern).
   ✅ Anbindung geprüft (03.10.): alle 5 Familienquellen wurden fälschlich über den Blog-Feed gelesen.
   `tiergarten-delitzsch` → neuer Typ `wp_page_list` (liest die <li>-Terminliste über die
   WP-API, 14 Termine, 2 zukünftig). **Abgeschaltet** (`active:false`): `leipziger-kinderfestival`
   (einzelne Jahresveranstaltung), `leipzig-fuer-lau` (keine Termine), `mamalismus` (Blog).
   **Offen:** `lichtblick-familien` (Eltern-Kurse, Termine als Freitext, 10 zukünftige – Parser
   nötig), 5× `leipzig-leben-*` (Feeds: nur Seite 1 gelesen, `?paged=2` liefert 10 weitere; Datum
   steht nur im Titel, nur wenige aktuell), Pressemeldungen kultur-wurzen/grimma-stadt/delitzsch-stadt.
   Crawl-Bericht: Spalte „ohne Datum"; Einträge zusätzlich in `data/export/ohne_datum.csv`.
3. **meinestadt (03.10., korrigiert):** Die 5 „Dubletten" (leipzig, grimma, wurzen, delitzsch, eilenburg)
   waren NICHT Dubletten anderer Quellen, sondern der anderen meinestadt-Städteseiten: die Seiten
   zeigen regional dieselben Termine (Summe 182 → eindeutig 67). Davon sind nur 10 auch bei unseren
   anderen Quellen, 57 sind NUR bei meinestadt (meinestadt ist also wertvoll). Die 5 laufen jetzt als
   reine **Gegenprobe** (`check:true`, nicht in der DB; kein Verlust, da alle 67 über die aktiven
   Seiten in der DB sind). Alle meinestadt-Städte tragen `gegenprobe:true` → nach jedem Crawl
   `data/export/gegenprobe.csv` (Abdeckung je Stadt gegen NICHT-meinestadt-Quellen) und
   `gegenprobe_fehlt.csv` (Termine, die nur meinestadt kennt). Ansicht „Gegenprobe" auf der Quellen-Seite.
   meinestadt liefert max. 20/Stadtseite (Seitenparameter wirkungslos); `meinestadt-torgau`: 0 korrekt.
   ⚠ Schwäche: `address` ist bei meinestadt nur die Seitenstadt – Veranstaltungsorte in anderen Orten
   (Gera, Glauchau, Limbach-Oberfrohna) werden der Seitenstadt zugeordnet. Bei doppelten Events gewinnt
   die zuletzt gecrawlte Quelle (`upsert` überschreibt source_id).
4. 41 Events ohne Ort (`ort` NULL).
5. urbanite/meinestadt/leipzig.de Kategorie-Navigation JS → Rubriken vom Nutzer nennen lassen.
6. KAOS-Kultursommer (leipzig-im „Konzert") bewusst draußen. Crawl dauert ~7 Min (optional).
**Neu geplant:** Projekt nach GitHub (Code) + Hosting/Cloud-Zugriff von anderen Geräten.

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
