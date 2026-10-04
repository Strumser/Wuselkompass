#!/bin/bash
# Holt den neuesten Stand von GitHub, startet die Wuselkompass-Webapp und öffnet den Browser.
cd "$(dirname "$0")" || exit 1

if [ -d .git ]; then
  # Warnung, falls beim letzten Mal nicht gesichert wurde
  if [ -n "$(git status --porcelain)" ] || [ -n "$(git log @{u}..HEAD --oneline 2>/dev/null)" ]; then
    echo "⚠️  Es gibt noch NICHT hochgeladene Änderungen (beim letzten Mal wurde Ende.command nicht benutzt)."
  fi
  echo "⬇️  Hole neuesten Stand von GitHub …"
  if git pull --ff-only -q 2>/dev/null; then
    echo "   Stand ist aktuell."
  else
    echo "   Konnte nicht abgleichen (offline oder Änderungen kollidieren) – es wird mit dem lokalen Stand weitergearbeitet."
  fi
fi

pkill -f "webapp.serve" 2>/dev/null
sleep 1
nohup python3 -m webapp.serve >/tmp/wuselkompass.log 2>&1 &
sleep 2
open "http://localhost:8000"
echo "✅ Wuselkompass läuft: http://localhost:8000"
echo "   Beim Start werden die Daten aktualisiert, falls der letzte Abruf > 6 h her ist."
echo "   Zum Beenden (und Sichern auf GitHub): 'Ende.command' doppelklicken."
echo "   Dieses Fenster kann jetzt geschlossen werden."
