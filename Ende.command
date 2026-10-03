#!/bin/bash
# Beendet die Wuselkompass-Webapp.
if pkill -f "webapp.serve" 2>/dev/null; then
  echo "🛑 Wuselkompass wurde beendet."
else
  echo "ℹ️  Es lief kein Server."
fi
sleep 1
