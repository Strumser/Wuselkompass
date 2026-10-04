#!/bin/bash
# Beendet die Wuselkompass-Webapp und sichert Änderungen auf GitHub.
cd "$(dirname "$0")" || exit 1

if pkill -f "webapp.serve" 2>/dev/null; then
  echo "🛑 Wuselkompass wurde beendet."
else
  echo "ℹ️  Es lief kein Server."
fi

if [ -d .git ]; then
  git add -A
  if ! git diff --cached --quiet; then
    git commit -q -m "Stand $(date '+%Y-%m-%d %H:%M')"
    echo "💾 Änderungen gesichert."
  fi
  echo "⬆️  Lade auf GitHub hoch …"
  if git push -q 2>/dev/null; then
    echo "   Hochgeladen."
  else
    echo "   ⚠️ Hochladen nicht möglich (offline oder anderer Stand auf GitHub). Beim nächsten Ende.command erneut versuchen."
  fi
fi
sleep 1
