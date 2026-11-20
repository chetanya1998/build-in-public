#!/bin/sh
# Build Your Product in Public: end-of-day pipeline for one repo.
#   collect sessions + git + approved captures -> trends -> agent writes the brief -> notification + email
# Usage: sh nightly.sh [/path/to/repo] [YYYY-MM-DD]
REPO="${1:-$(pwd)}"
SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO" || exit 1
DAY="${2:-$(python3 -c 'import datetime as d;print((d.datetime.now()-d.timedelta(hours=4)).date())')}"
OUT=".buildinpublic/daily/$DAY"
mkdir -p "$OUT"
LOG="$OUT/nightly.log"
echo "== Build Your Product in Public nightly $DAY $(date)" >> "$LOG"

python3 "$SKILL_DIR/scripts/collect.py"  --repo "$REPO" --date "$DAY" >> "$LOG" 2>&1
python3 "$SKILL_DIR/scripts/trends.py"   --repo "$REPO" --date "$DAY" >> "$LOG" 2>&1

cfg() { python3 -c "import json,sys;c=json.load(open('.buildinpublic/config.json'));print(c.get('$1',''))" 2>/dev/null; }
AGENT="$(cfg agent)"; CUSTOM="$(cfg agent_command)"
PROMPT="Use the build-in-public skill. Run the Daily gist mode for $DAY using the files in $OUT. Write $OUT/brief.md with the list of suggested posts. Do not post anything."

# The agent writes the brief. If it fails (signed out, out of credits, not installed), save why,
# so the email says so instead of arriving with no posts and no explanation.
AOUT="$OUT/agent-output.txt"; rm -f "$OUT/agent-error.txt"; RAN=1; RC=0
if [ -n "$CUSTOM" ]; then
  sh -c "$CUSTOM \"$PROMPT\"" > "$AOUT" 2>&1; RC=$?
elif [ "$AGENT" = "claude" ] && command -v claude >/dev/null; then
  claude -p "$PROMPT" --allowedTools "Read,Write,Edit,Glob,Grep,WebSearch,WebFetch,Bash(git log:*),Bash(git show:*)" > "$AOUT" 2>&1; RC=$?
elif [ "$AGENT" = "codex" ] && command -v codex >/dev/null; then
  codex exec --full-auto "$PROMPT" > "$AOUT" 2>&1; RC=$?
elif [ -n "$AGENT" ] && [ "$AGENT" != "none" ]; then
  echo "The '$AGENT' command wasn't found on PATH when the gist ran." > "$AOUT"; RC=127
else
  RAN=0
  echo "No headless agent configured; digest and trends are ready. Ask your agent: 'build in public brief'." >> "$LOG"
fi
if [ "$RAN" = 1 ]; then
  cat "$AOUT" >> "$LOG"
  if [ ! -f "$OUT/brief.md" ]; then
    { echo "agent: ${CUSTOM:-$AGENT}"; echo "exit: $RC"; grep -v '^[[:space:]]*$' "$AOUT" | tail -3; } > "$OUT/agent-error.txt"
  fi
  rm -f "$AOUT"
fi

# check the brief (sections, fields, links) so the email can flag anything to fix before posting
[ -f "$OUT/brief.md" ] && python3 "$SKILL_DIR/scripts/brief_check.py" --repo "$REPO" --date "$DAY" >> "$LOG" 2>&1
python3 "$SKILL_DIR/scripts/notify.py" --repo "$REPO" --date "$DAY" >> "$LOG" 2>&1
