#!/bin/sh
# Build Your Product in Public: end-of-day pipeline for one repo.
#   collect sessions + git + approved captures -> trends -> agent writes the brief -> notification + email
# Usage: sh nightly.sh [/path/to/repo] [YYYY-MM-DD]
#
# On a Mac the job often starts during a short background wake (the Mac is asleep at gist time),
# and the Mac sleeps again seconds later, freezing the run for hours. caffeinate keeps it awake
# until the run ends (-i idle sleep; -s system sleep, on power). It can't wake a Mac that's off or
# has its lid closed on battery: for that, schedule a wake (doctor.py shows the command).
if [ -z "$BIP_AWAKE" ] && command -v caffeinate >/dev/null 2>&1; then
  BIP_AWAKE=1 exec caffeinate -i -s /bin/sh "$0" "$@"
fi
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
MINUTES="$(cfg agent_timeout_minutes)"; MINUTES="${MINUTES:-30}"
PROMPT="Use the build-in-public skill. Run the Daily gist mode for $DAY using the files in $OUT. Write $OUT/brief.md with the list of suggested posts. Do not post anything."

# The agent writes the brief. If it fails (signed out, out of credits, not installed), save why,
# so the email says so instead of arriving with no posts and no explanation.
AOUT="$OUT/agent-output.txt"; rm -f "$OUT/agent-error.txt"; RAN=1; RC=0
# a brief written without the agent on an earlier run gets replaced if the agent works this time
grep -q "written without an agent" "$OUT/brief.md" 2>/dev/null && rm -f "$OUT/brief.md"
# Run the agent with a time limit, so one stuck run can't hold the gist back for hours.
limited() {
  "$@" < /dev/null > "$AOUT" 2>&1 &
  pid=$!
  ( sleep "${BIP_AGENT_TIMEOUT_SECONDS:-$((MINUTES * 60))}" & s=$!; trap 'kill $s 2>/dev/null; exit 0' TERM; wait $s
    kill "$pid" 2>/dev/null && echo "Stopped after $MINUTES minutes (agent_timeout_minutes)." >> "$AOUT" ) &
  watch=$!
  wait "$pid"; RC=$?
  kill "$watch" 2>/dev/null
}
# A long-lived token saved with agent_auth.py, so the agent can sign in with nobody at the keyboard.
# It goes straight into the environment: never into the log.
AUTH_ENV="$(python3 "$SKILL_DIR/scripts/agent_auth.py" env 2>/dev/null)"
[ -n "$AUTH_ENV" ] && eval "$AUTH_ENV" && echo "Using the token saved with agent_auth.py" >> "$LOG"
if [ -n "$CUSTOM" ]; then
  limited sh -c "$CUSTOM \"$PROMPT\""
elif [ "$AGENT" = "claude" ] && command -v claude >/dev/null; then
  limited claude -p "$PROMPT" --allowedTools "Read,Write,Edit,Glob,Grep,WebSearch,WebFetch,Bash(git log:*),Bash(git show:*)"
elif [ "$AGENT" = "codex" ] && command -v codex >/dev/null; then
  limited codex exec --full-auto "$PROMPT"
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

# No brief from the agent (it failed, or none is set up): write one without it, from today's
# sessions, commits and articles, so the gist still has posts. The email says how it was made.
if [ ! -f "$OUT/brief.md" ]; then
  WHY="$(sed -n '3p' "$OUT/agent-error.txt" 2>/dev/null | cut -c1-120)"
  python3 "$SKILL_DIR/scripts/fallback_brief.py" --repo "$REPO" --date "$DAY" --reason "${WHY:-no agent set up}" >> "$LOG" 2>&1
fi

# check the brief (sections, fields, links) so the email can flag anything to fix before posting
[ -f "$OUT/brief.md" ] && python3 "$SKILL_DIR/scripts/brief_check.py" --repo "$REPO" --date "$DAY" >> "$LOG" 2>&1
python3 "$SKILL_DIR/scripts/notify.py" --repo "$REPO" --date "$DAY" >> "$LOG" 2>&1
