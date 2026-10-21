#!/bin/sh
# Build In Public: run nightly.sh every day at brief_time (default 00:00) for this repo.
# macOS: launchd (runs on wake if the Mac was asleep). Linux: crontab.
# Usage: sh schedule.sh [--time HH:MM] [--remove]
set -e
SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
REPO="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
TIME=""; REMOVE=0
while [ $# -gt 0 ]; do
  case "$1" in --time) shift; TIME="$1" ;; --remove) REMOVE=1 ;; esac; shift
done
[ -n "$TIME" ] || TIME="$(python3 -c "import json;print(json.load(open('$REPO/.buildinpublic/config.json')).get('brief_time','00:00'))" 2>/dev/null || echo 00:00)"
H="$(echo "$TIME" | cut -d: -f1 | sed 's/^0*//')"; H="${H:-0}"
M="$(echo "$TIME" | cut -d: -f2 | sed 's/^0*//')"; M="${M:-0}"
ID="ai.buildinpublic.$(basename "$REPO" | tr -cd 'A-Za-z0-9-')"

if [ "$(uname)" = "Darwin" ]; then
  PLIST="$HOME/Library/LaunchAgents/$ID.plist"
  launchctl unload "$PLIST" 2>/dev/null || true
  if [ "$REMOVE" = 1 ]; then rm -f "$PLIST"; echo "Removed $ID"; exit 0; fi
  mkdir -p "$HOME/Library/LaunchAgents"
  cat > "$PLIST" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$ID</string>
  <key>ProgramArguments</key><array>
    <string>/bin/sh</string><string>$SKILL_DIR/scripts/nightly.sh</string><string>$REPO</string>
  </array>
  <key>EnvironmentVariables</key><dict><key>PATH</key><string>$PATH</string></dict>
  <key>StartCalendarInterval</key><dict>
    <key>Hour</key><integer>$H</integer><key>Minute</key><integer>$M</integer>
  </dict>
  <key>StandardOutPath</key><string>/tmp/$ID.log</string>
  <key>StandardErrorPath</key><string>/tmp/$ID.log</string>
</dict></plist>
PL
  launchctl load "$PLIST"
  echo "Scheduled $ID daily at $TIME (launchd)."
else
  LINE="$M $H * * * PATH=$PATH /bin/sh $SKILL_DIR/scripts/nightly.sh $REPO # $ID"
  ( crontab -l 2>/dev/null | grep -v "# $ID\$" ; [ "$REMOVE" = 1 ] || echo "$LINE" ) | crontab -
  [ "$REMOVE" = 1 ] && echo "Removed $ID" || echo "Scheduled $ID daily at $TIME (cron)."
fi
