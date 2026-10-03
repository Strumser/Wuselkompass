# Handoff: Spielraum – Entdecken-Ansicht (Desktop)

## Overview
"Spielraum" ist eine Web-App, die Kinder- und Familienveranstaltungen für Leipzig und Umgebung bündelt. Dieses Handoff enthält das Design für die Kernansicht "Entdecken": Header mit Illustration/Logo, Tab-Navigation, Filterleiste und Terminliste.

## About the Design Files
Die beigefügte Datei `Spielraum.dc.html` ist eine **Design-Referenz in HTML** — ein Prototyp, der Look & Verhalten zeigt, kein Produktionscode zum direkten Übernehmen. Aufgabe: dieses Design im Ziel-Stack (React, Vue o.ä. — je nach bestehendem Projekt-Setup) mit den dort etablierten Patterns/Bibliotheken nachbauen. Existiert noch kein Frontend-Framework, ist ein sinnvolles auszuwählen.

## Fidelity
**High-fidelity.** Farben, Typografie, Abstände und Illustration sind final abgestimmt — pixelgenau nachbauen.

## Screens / Views
### Entdecken (Terminliste)
**Zweck:** Eltern sehen auf einen Blick anstehende Familienveranstaltungen, filterbar nach Zeitraum/Ort/Stadtteil.

**Layout:**
- Card-Container: max-width 900px, Hintergrund `#FFFDFA`, `border-radius: 20px`, `box-shadow: 0 20px 50px rgba(60,40,20,0.12)`, `overflow: hidden`.
- Vertikaler Aufbau: Header-Illustration (260px hoch) → Tabs → Filterleiste → Terminliste.

**1. Header-Illustration (260px Höhe, Hintergrund `#F2A73B`)**
- Inline-SVG, `viewBox="0 0 900 260"`, skaliert responsiv mit `width:100%`.
- Elemente (von hinten nach vorne): zwei wellige Hügelformen (`#8FAE8B` vorne, `#7A9C75` dahinter, handgezeichnete/wobbelige Pfade), eine horizontale wellige "Schnur" (`#FBF3EA`, 3px) von Rand zu Rand mit Ankerpunkten (Kreise, r=4) an beiden Enden, darauf 11 Wimpel-Dreiecke abwechselnd in `#C2555C`, `#FBF3EA`, `#8FAE8B`, zwei einfache Kinderfiguren (Kopf + Körper als organische Blob-Pfade) rechts im Hügelbereich, zwei wolkenartige Blob-Akzente oben rechts (`#FBF3EA`, opacity 0.6–0.7).
- Logo (oben links auf Illustration): handgezeichnetes Sonnen-Signet als SVG (`viewBox 0 0 76 76`, ca. 52×52px dargestellt) — organischer Blob-Kreis (`#FCE2A6`, Stroke `#F2C77A`) mit 8 geraden Strahlen (`#D9663B`, 4px, round cap) — plus Wortmarke "Spielraum" in Baloo 2, 700, 44px, Farbe `#FFFDFA`.
- Untertitel darunter: "Kinder- und Familienprogramm für Leipzig und Umgebung", Nunito 700, 16px, Farbe `#FFF6E8`.

**2. Tab-Navigation** (Padding 20px 32px 0)
- "Entdecken": Baloo 2, 600, 17px, aktiv-Farbe `#D9663B`, `border-bottom: 3px solid #D9663B`.
- "Quellen": gleiche Typo, inaktive Farbe `#B0A398`, kein Unterstrich.

**3. Filterleiste** (Padding 18px 32px 6px, flex-wrap, gap 10px)
- Textsuche (flex:2, placeholder "Suche nach Veranstaltung…") + 3 Selects (Zeitraum, Ort, Stadtteil).
- Alle Felder: `border:1px solid #EADFD0`, `background:#FBF6EF`, `border-radius:14px`, `padding:11px 16px`, `font-size:14px`, Textfarbe `#3A2E28`, Nunito. Placeholder-Farbe `#A99C8E`.

**4. Terminliste** (Padding 8px 16px 24px)
- Eine Zeile pro Termin, `display:flex; gap:18px; align-items:center; padding:16px; border-radius:14px;`. Hover: `background:#FBF6EF`.
- Spalten:
  - Datum (56px breit, zentriert): Wochentag (12px, 800, uppercase, `#B0A398`), Tag (Baloo 2, 24px, 700, `#3A2E28`), Monat (11px, 700, uppercase, `#B0A398`).
  - Kategorie-Tag: pill (`border-radius:999px`, padding 3px 10px), Nunito 800, 13px — je Kategorie eigenes ruhiges Farbpaar (Hintergrund hell/Text dunkel derselben Farbfamilie). Aktuell definiert: Krabbelgruppe (`bg #E7EFE3` / `text #5B7A54`), Theater (`#F7E3E1` / `#A85253`), Museum (`#F5E3D6` / `#A9633A`), Vorlesen (`#FDEFCB` / `#9A7A1E`), Zoo (`#DEEAE0` / `#3E7856`), Basteln (`#F3E1E5` / `#A14A63`).
  - Titel: Baloo 2, 600, 19px, `#2E241D`.
  - Meta-Zeile: Ort · Uhrzeit · Stadtteil · ggf. "kostenlos", 13.5px, `#8A7A6B`.
  - Quelle (rechtsbündig, flex-shrink:0): "Quelle: {domain} ↗" als Link, 12.5px, Link-Farbe `#B15A34` (Hover `#8F4526`), Rest `#B0A398`.

## Interactions & Behavior
- Tab-Wechsel "Entdecken" ↔ "Quellen" (Quellen-Seite ist noch nicht ausgearbeitet — Layout analog: Tabelle/Liste der Datenquellen).
- Terminzeile: Hover-Highlight (siehe oben). Kein Klick-Ziel definiert — vermutlich Link zur Quelle oder Detailansicht, mit Produktteam klären.
- Filter (Suche/Zeitraum/Ort/Stadtteil): rein visuell im Prototyp, keine Filterlogik implementiert.
- Responsive/Mobile: noch nicht ausgearbeitet, nur Desktop-Breite (900px Card) vorhanden.

## State Management
- Terminliste kommt aus einem Array von Objekten: `{ weekday, day, month, category, tagBg, tagText, title, meta, source }`.
- Reale Implementierung braucht: Datenquelle (API/Feed) für Termine, Filterzustand (Suchtext, Zeitraum, Ort, Stadtteil), leerer Zustand bei 0 Treffern (im Prototyp noch nicht gebaut).

## Design Tokens

**Farben**
- Terracotta (Primär): `#D9663B`
- Sonnengelb/Orange (Header-Hintergrund): `#F2A73B`
- Sonnengelb hell (Signet-Füllung): `#FCE2A6` / Stroke `#F2C77A`
- Salbeigrün: `#8FAE8B` / dunkler `#7A9C75` / `#6F9468`
- Beere/Coral: `#C2555C`
- Creme (Wimpel/Wolken/Text auf dunklem Grund): `#FBF3EA` / `#FFF6E8`
- Seitenhintergrund: `#EFE7DC`
- Card-Hintergrund: `#FFFDFA`
- Formularfeld-Hintergrund: `#FBF6EF`, Rand `#EADFD0`
- Text dunkel (Titel): `#3A2E28` / `#2E241D`
- Text gedämpft (Meta/Labels): `#8A7A6B` / `#B0A398`
- Placeholder: `#A99C8E`
- Link: `#B15A34`, Hover `#8F4526`

**Typografie**
- Headlines/Wortmarke: "Baloo 2", Gewichte 600/700.
- Fließtext/UI: "Nunito", Gewichte 400/700/800.
- Skala: Wordmark 44px, Titel-Zeile 19px, Tag-Text 13px, Meta-Text 13.5px, Datum-Tag 24px (Baloo 2), Wochentag/Monat 11–12px.

**Radien**
- Card: 20px. Terminzeile: 14px. Formularfelder: 14px. Tag-Pills: 999px (voll rund).

**Shadows**
- Card: `0 20px 50px rgba(60,40,20,0.12)`.

**Abstände**
- Card-Innenabstand horizontal: 32px (Tabs/Filter), 16px (Terminliste).
- Gap zwischen Terminzeilen-Spalten: 18px. Gap Filterleiste: 10px.

## Assets
- Google Fonts: Baloo 2 (600, 700), Nunito (400, 600, 700, 800) — via `<link>` von fonts.googleapis.com.
- Header-Illustration & Logo: reines Inline-SVG, keine externen Bilddateien nötig (siehe HTML für exakte Pfade).
- Keine Icons/Emojis im Listenbereich — nur Text-Tags und der "↗"-Pfeil als Zeichen.

## Files
- `Spielraum.dc.html` — vollständiges Referenz-Markup (Header-SVG, Tabs, Filter, Terminliste) mit Beispiel-Terminen.
