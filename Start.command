#!/bin/bash
# Startet die Wuselkompass-Webapp und öffnet den Browser.
cd "$(dirname "$0")" || exit 1
pkill -f "webapp.serve" 2>/dev/null
sleep 1
nohup python3 -m webapp.serve >/tmp/wuselkompass.log 2>&1 &
sleep 2
open "http://localhost:8000"
echo "✅ Wuselkompass läuft: http://localhost:8000"
echo "   Beim Start werden die Daten aktualisiert, falls der letzte Abruf > 6 h her ist."
echo "   Zum Beenden: 'Ende.command' doppelklicken."
echo "   Dieses Fenster kann jetzt geschlossen werden."
