#!/bin/bash
# Sichert den aktuellen Stand auf GitHub, ohne die App zu beenden.
cd "$(dirname "$0")" || exit 1

if [ ! -d .git ]; then
  echo "⚠️  Kein Git-Repository gefunden."
  exit 1
fi

git add -A
if ! git diff --cached --quiet; then
  git commit -q -m "Stand $(date '+%Y-%m-%d %H:%M')"
  echo "💾 Änderungen gesichert."
else
  echo "ℹ️  Keine neuen Änderungen."
fi

echo "⬆️  Lade auf GitHub hoch …"
if git push -q 2>/dev/null; then
  echo "✅ Hochgeladen. Die App läuft weiter."
else
  echo "⚠️  Hochladen nicht möglich (offline oder anderer Stand auf GitHub). Später erneut versuchen."
fi
echo "   Dieses Fenster kann geschlossen werden."
