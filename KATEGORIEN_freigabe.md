# Kategorie-Freigabe – welche zusätzlichen Kategorien sollen wir crawlen?

## Problem
Bisher ziehen wir pro Quelle nur die Rubrik **„Kinder & Familie"**. Familienrelevante
Events, die woanders einsortiert sind (z. B. **„17. KAOS-Kultursommer"** unter
*Verschiedenes* auf leipzig-im), werden nie erfasst.

## So gibst du frei
- Setze bei gewünschten Kategorien ein **[x]** (Datei speichern) – oder sag mir welche.
- Freigegebene Kategorien werden **zusätzlich gecrawlt UND angezeigt** (der Stichwort-
  Familienfilter wird für sie gelockert, sonst käme KAOS & Co. trotzdem nicht durch).
- **Preis:** gemischte Kategorien (z. B. *Konzert*) bringen auch Nicht-Familiäres mit.
  Jederzeit wieder abwählbar.
- **💡** = wahrscheinlich familienrelevant.  **(aktiv)** = wird bereits gecrawlt.

================================================================
## A) Quellen mit sauberer Kategorie-Struktur (Freigabe wirkt direkt)
================================================================

### leipzig-im.de  (Rubriken)
- [x] Kinder & Familie  *(aktiv)*
- [x] Verschiedenes   💡  ← hier liegt der KAOS-Kultursommer
- [x] Führung   💡
- [x] Fest & Festival   💡
- [x] Ausstellungen   💡
- [ ] Konzert
- [ ] Kirchen
- [ ] Literatur & Lesung
- [ ] Kabarett
- [ ] Sport
- [ ] Dinner-Show
- [ ] Gastro-Events
- [ ] Messen & Kongresse
- [x] Umland

### leipzig-leben.de  (Kategorie-Feeds)
- [x] freizeit-ideen / kinder-familien  *(aktiv)*
- [x] kultur / tanz-theater-performance   💡
- [x] kultur / festivals   💡
- [x] kultur / kunst-ausstellungen   💡
- [x] freizeit-ideen / gaming-adventure   💡
- [ ] nachhaltigkeit-leipzig / tauschen-und-verschenken   💡
- [ ] nachhaltigkeit-leipzig / urban-gardening
- [ ] kultur / musik
- [ ] kultur / literatur-buecher
- [ ] kultur / fotografie-film
- [ ] freizeit-ideen / koerper-entspannung
- [ ] freizeit-ideen / inspiration
- [ ] nachhaltigkeit-leipzig / ernaehrung-zero-waste
- [ ] (nachtleben/*: bars, clubs, partys – eher nicht)

### rausgegangen.de
- [x] kinder-und-familien  *(aktiv)*
- [x] aktiv-und-kreativ   💡
- [x] theater   💡
- [x] feste-und-festival   💡
- [x] ausstellung   💡
- [x] markt   💡
- [x] shows-und-performances
- [ ] konzerte-und-musik
- [ ] film
- [ ] sport
- [ ] gesprochenes
- [ ] food-und-drinks
- [ ] party

### kreuzer-leipzig.de  (Ressorts)
- [x] kinder-familie  *(aktiv)*
- [x] theater   💡
- [x] literatur   💡
- [ ] musik
- [ ] film
- [ ] vortraege-diskussionen
- [x] umland
- [ ] clubbing
- [ ] gastro-events

================================================================
## B) Kategorie-gefiltert, aber Liste (noch) nicht sauber auslesbar
================================================================

### urbanite.net
Zieht aktuell `kinder-familie`. Die weiteren Event-Kategorien stecken in einer
JS-Navigation, die ich nicht auslesen konnte. → Wenn du auf der Seite eine Rubrik
siehst, die rein soll, nenn mir den Namen; dann teste ich die URL und binde sie an.

### meinestadt.de  (×12 Städte)
Zieht aktuell `/kinderveranstaltungen/`. Weitere Kategorien (die Nav ist JS) müsste ich
gezielt testen. Wahrscheinliche Slugs: `veranstaltungen` (= alles), `konzerte`,
`theater-buehne`, `ausstellungen`, `feste-feiern`, `maerkte`, `fuehrungen`.
→ Sag welche, ich verifiziere die URLs vor dem Anbinden.

### leipzig.de
Sonderfall: unsere Quelle ist die **offizielle „Kinder- und Jugendliche"-Seite**, kein
Kategorie-Filter. Es gibt keinen sauberen Kategorie-Umschalter. Alternative wäre der
**komplette Stadt-Kalender** (`/kultur-und-freizeit/veranstaltungen`, = alle Events) –
das wäre dann „alles + Familien-Filter", keine Kategorie-Auswahl.

================================================================
## C) Ohne Kategorie-Auswahl (ziehen ohnehin ALLES; nur der Familien-Score filtert)
================================================================
eventfinder ×6, tourismus-wurzen, grimma-stadt, delitzsch-stadt, markkleeberg-stadt,
kultur-wurzen, ahoi-leipzig, leipziginfo.
→ Hier gibt es keine Kategorie freizugeben. Wenn dort „versteckte" Familien-Events
fehlen, liegt es am Familien-Score (andere Baustelle: Stichwörter/LLM).

================================================================
## D) Inhärent familiär (alle Events schon relevant)
================================================================
theater-junge-welt, muetterzentrum-fiz, lipzkidz, leipziger-kinderfestival,
lichtblick-familien, mamalismus, leipzig-fuer-lau, tiergarten-delitzsch.
