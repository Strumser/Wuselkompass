#!/bin/bash
# Holt frische Veranstaltungen aus allen Quellen.
cd "$(dirname "$0")" || exit 1
echo "🔄 Aktualisiere Veranstaltungen aus allen Quellen …"
echo "   (kann 1–3 Minuten dauern)"
echo
python3 -m crawler.run
echo
echo "✅ Fertig. Falls die Webapp läuft, zeigt sie die neuen Termine sofort."
echo "   Dieses Fenster kann geschlossen werden."
