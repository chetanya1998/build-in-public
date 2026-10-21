#!/bin/sh
# Build In Public: end-of-day pipeline for one repo.
#   collect sessions + git -> trends -> app snapshots -> agent writes the brief -> notify
# Usage: sh nightly.sh [/path/to/repo] [YYYY-MM-DD]
#        sh nightly.sh --demo [--show]   # try it on a fictional project first (see demo.py)
if [ "$1" = "--demo" ]; then shift; exec python3 "$(dirname "$0")/demo.py" "$@"; fi
REPO="${1:-$(pwd)}"
SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO" || exit 1
DAY="${2:-$(python3 -c 'import datetime as d;print((d.datetime.now()-d.timedelta(hours=4)).date())')}"
OUT=".buildinpublic/daily/$DAY"
mkdir -p "$OUT"
LOG="$OUT/nightly.log"
echo "== Build In Public nightly $DAY $(date)" >> "$LOG"

python3 "$SKILL_DIR/scripts/collect.py"  --repo "$REPO" --date "$DAY" >> "$LOG" 2>&1
python3 "$SKILL_DIR/scripts/trends.py"   --repo "$REPO" --date "$DAY" >> "$LOG" 2>&1
python3 "$SKILL_DIR/scripts/snapshot.py" --repo "$REPO" --date "$DAY" >> "$LOG" 2>&1

cfg() { python3 -c "import json,sys;c=json.load(open('.buildinpublic/config.json'));print(c.get('$1',''))" 2>/dev/null; }
AGENT="$(cfg agent)"; CUSTOM="$(cfg agent_command)"
PROMPT="Use the build-in-public skill. Run Mode 3 (Daily brief) for $DAY using the files in $OUT. Write $OUT/brief.md and the drafts. Do not post anything."

if [ -n "$CUSTOM" ]; then
  sh -c "$CUSTOM \"$PROMPT\"" >> "$LOG" 2>&1
elif [ "$AGENT" = "claude" ] && command -v claude >/dev/null; then
  claude -p "$PROMPT" --allowedTools "Read,Write,Edit,Glob,Grep,WebSearch,WebFetch,Bash(git log:*),Bash(git show:*)" >> "$LOG" 2>&1
elif [ "$AGENT" = "codex" ] && command -v codex >/dev/null; then
  codex exec --full-auto "$PROMPT" >> "$LOG" 2>&1
else
  echo "No headless agent configured; digest and trends are ready. Ask your agent: 'build in public brief'." >> "$LOG"
fi

if [ "$(cfg notify)" != "False" ]; then
  MSG="Your build-in-public brief for $DAY is ready in $OUT"
  [ -f "$OUT/brief.md" ] || MSG="Digest for $DAY ready. Ask your agent for the brief."
  if command -v osascript >/dev/null; then
    osascript -e "display notification \"$MSG\" with title \"Build In Public\"" 2>/dev/null
  elif command -v notify-send >/dev/null; then
    notify-send "Build In Public" "$MSG" 2>/dev/null
  fi
fi
