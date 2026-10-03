#!/bin/bash
# Erzeugt die CSV-Dateien zum Betrachten der Datenbank und öffnet den Ordner.
cd "$(dirname "$0")" || exit 1
echo "📊 Erzeuge CSV-Dateien aus der Datenbank …"
echo
python3 -m tools.report
echo
open "data/export"
echo "✅ Fertig. Ordner 'data/export' wurde geöffnet."
echo "   events.csv       = alle Veranstaltungen in der Datenbank (die Inhalte)."
echo "   crawl_report.csv = pro Quelle: gefunden / übernommen / verworfen (vom letzten Aktualisieren)."
echo "   Doppelklick öffnet die Dateien in Numbers."
echo "   Dieses Fenster kann geschlossen werden."
