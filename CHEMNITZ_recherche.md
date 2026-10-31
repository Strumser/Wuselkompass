# Chemnitz als eigene Region – Rechercheergebnis (Stand 31.10.2026)

Entscheidung des Nutzers: Chemnitz wird eigene Region (Variante 3): eigene Quellen, eigene Orte, eigener Ortsfilter.
Chemnitz liegt ca. 69 km Luftlinie von Leipzig. Ergebnisse stammen von zwei Recherche-Agenten; nicht nachgeprüft ist,
was nicht ausdrücklich als „✓" markiert ist.

## A) Veranstaltungsquellen (technisch geprüft, Agent per curl)
| Prio | Quelle | Technik | Besonderheit |
|---|---|---|---|
| 1 | **chemnitz.de Veranstaltungskalender** `/de/aktuell/veranstaltungen` | server-gerendertes HTML, Kategorie-Filter `?tx_solr[filter][0]=category:Kinder und Familie`, Paging `tx_solr[page]=N` (20/Seite), ca. 250–270 Termine | **Browser-UA nötig, „EventBot" → 403**; Detailseiten ohne JSON-LD |
| 2 | **chemnitz-zwickau-region.de** | WP-Endpunkt `/wp-json/czr-events/v1/points` (GeoJSON, 483 Events mit Koordinaten) + JSON-LD auf Detailseiten | Umland per Koordinaten filterbar (30 km); kein Kategoriefeld, Familienfilter nur per Stichwort |
| 3 | **Theater Chemnitz Spielplan** | HTML, `type=figurentheater` + Stichworte (Kinder, Familienkonzert, Märchen, Babykonzert) | Monats-URLs mit cHash → nur über Links der Seite erreichbar |
| 4 | **smac Kalender** `/kalender.php` | statisches HTML, Tags „Familien", „Familienführung" | Jahr steht nicht in der Zeile (ergänzen) |
| 5 | **Stadtbibliothek Chemnitz** `/aktuelles/veranstaltungen` | HTML, Kategorien Vorlesen/Kinderwelt/Ganz in Familie | Kategorie ggf. nur per JS; Detailseiten lesen |
| – | meinestadt.de Chemnitz `/chemnitz/kinderveranstaltungen/alle` | JSON-LD, 20 Treffer, kein Paging | **EventBot 200, Browser-UA 403** (umgekehrt zu chemnitz.de) |
| – | Freie Presse Veranstaltungskalender | JSON-LD ItemList, 15/Seite | Paging/Kinderfilter ungeprüft |
| – | Tierpark Chemnitz | feste Fütterungszeiten + Freitext | als Wochenraster abbildbar |
| – | Kunstsammlungen Chemnitz | HTML-Accordion, Klassen `date-YYYY-MM-DD` | mittel |
| ✗ | chemnitz.travel, Industriemuseum, vhs, eventfinder, rausgegangen, mamilade (403), kindaling | – | lohnt nicht / nicht abrufbar |

## B) Dauer-Locations (Kleinkinder) – CH-Kürzel für die Klickliste
**Spielcafés / Indoor**
- **CH1 Emma's Café** – Johannisplatz 10, 09111 Chemnitz · Familien- und Kindercafé, Spielbereich, Krabbelecke Babys · ✓ (emmas-cafe.com)
- **CH2 Jump'n'Play** – Reichsstraße 58 (Kaßberg) · Indoor, eigener Bereich 0–4 J. (80 m²), sonntags „Minijumpy" 9–10 Uhr · ✓ (jumpnplay.de)
- **CH3 Kuddeldaddeldu Kinderland (Chemnitz Center)** – Ringstr. 17b · Aktualität unklar, Verzeichnis zeigte „geschlossen" · ?
- **CH4 Schatzhöhle Meerane** – Dänkritzer Weg 2, 3.500 m² · ~ (ca. 40 km, außerhalb 30-km-Umland)

**Familienzentren (städtische KiFaZ, offene Spielrunden/Elterntreffs; Zeiten telefonisch erfragen)**
- **CH5 KiFaZ „Bunte Gärten"** – Tschaikowskistr. 9 · ✓
- **CH6 KiFaZ „Pfiffikus"** – Hilbersdorfer Str. 21 · ✓
- **CH7 KiFaZ „Kappelino" / Mehrgenerationenhaus (solaris)** – Irkutsker Str. 15 · ✓/~
- **CH8 KiFaZ „Sonnenwelt" (AWO)** – Paul-Arnold-Str. 1 · ✓
- **CH9 KiFaZ „Glückskäfer"** – Usti nad Labem 119 · ✓
- **CH10 KiFaZ „Zeisigwaldfüchse"** – Yorckstr. 48 · ✓
- **CH11 KiFaZ „PampelMuse" (AWO)** – Bernhardstr. 4 · ✓
- **CH12 KiFaZ „Tausendfüßler"** – Robert-Siewert-Str. 68/70 · ✓ (Name nur als englische Übersetzung belegt)
- **CH13 Familiencafé der Heilsarmee** – Adresse nicht belegt · ~ (nicht verifiziert)

**Indoor bei Regen**
- **CH14 Museum für Naturkunde (Versteinerter Wald, TIETZ)** – Moritzstr. 20 · Atrium gratis · ~
- **CH15 smac** – Familientage, Mitmach-Basteln (für Kleinkinder eingeschränkt) · ✓ Familientage
- **CH16 Schauplatz Eisenbahn Hilbersdorf** – Frankenberger Str. 172 · Saison bis 2.11.2026, dann Winterpause · ~
- **CH17 Stadtbibliothek Chemnitz (TIETZ) + Stadtteilbibliotheken** – Vorlesen für Kinder · ✓ (Kleinkinderbereich unbelegt)
- **CH18 HOT Badeland** – Hohenstein-Ernstthal · Babybecken, Eltern-Kind-Bereich · ~
- **CH19 Schwimmhalle Gablenz / Stadtbad** – Adresse widersprüchlich, Kleinkindbereich unbelegt · ?

**Tiere**
- **CH20 Tierpark Chemnitz** – Nevoigtstr. 18 · Streichelzoo, Erlebnisbauernhof · ✓ (tierpark-chemnitz.de)
- **CH21 Wildgatter Oberrabenstein** – Thomas-Müntzer-Höhe 13 · Streichelzoo laut Verzeichnis · ✓/~
- **CH22 Amerika-Tierpark Limbach-Oberfrohna** – Tierparkstr. 1 · veraltete Angaben · ~
- **CH23 Tiergarten Thum** – Rathausplatz 4a · ~
- **CH24 Botanischer Garten (Schmetterlingspark, Haustierpark)** – ~

**Nicht aufgenommen:** Familiencafé Krümel (nur 2017), Vita Center (Einkaufszentrum), Fundora Schneeberg (zu weit).
**Nicht erreichbar:** chemnitz.de (403 für Abruf), Facebook/Instagram. Im Umland (Hohenstein-Ernstthal, Limbach-Oberfrohna,
Mittweida, Flöha, Zschopau, Glauchau …) keine weiteren Treffer – das heißt nicht, dass es dort nichts gibt.

## C) Technische Folgen für den Crawler
- Pro Quelle muss der User-Agent einstellbar bleiben (`"ua":"browser"` bei chemnitz.de; **kein** Browser-UA bei meinestadt).
- Neue Region braucht Ortsfilter: Gazetteer um Chemnitz und Umland (Flöha, Limbach-Oberfrohna, Hohenstein-Ernstthal …) erweitern;
  „Region" als Feld an Quellen/Orten, damit die App nach Leipzig / Halle / Chemnitz filtern kann.
- Radius: Chemnitz ist ca. 69 km von Leipzig – der bisherige 60-km-Filter würde Chemnitz-Termine verwerfen
  (`pipeline.RADIUS_KM`); stattdessen Distanz zum jeweiligen Regionszentrum (Leipzig / Chemnitz).
