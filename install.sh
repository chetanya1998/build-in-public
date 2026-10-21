#!/bin/sh
# Build In Public installer
# Usage:
#   sh install.sh            # install for your user (Claude Code, Codex, Antigravity)
#   sh install.sh --project  # install into the current project only
#   sh install.sh --only claude|codex|antigravity
set -e
SRC="$(cd "$(dirname "$0")" && pwd)/skills/build-in-public"
MODE=user; ONLY=""
while [ $# -gt 0 ]; do
  case "$1" in
    --project) MODE=project ;;
    --only) shift; ONLY="$1" ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
  shift
done

if [ "$MODE" = project ]; then
  CLAUDE_DIR=".claude/skills"
  CODEX_DIR=".agents/skills"      # Codex and Antigravity both read .agents/skills
  AG_DIR=".agents/skills"
else
  CLAUDE_DIR="$HOME/.claude/skills"
  CODEX_DIR="$HOME/.agents/skills"
  AG_DIR="$HOME/.gemini/config/skills"
fi

copy() { # $1 = label, $2 = target dir
  mkdir -p "$2"
  rm -rf "$2/build-in-public"
  cp -R "$SRC" "$2/build-in-public"
  echo "  ✓ $1 → $2/build-in-public"
}

echo "Installing Build In Public ($MODE)…"
[ -z "$ONLY" ] || [ "$ONLY" = claude ]      && copy "Claude Code" "$CLAUDE_DIR"
[ -z "$ONLY" ] || [ "$ONLY" = codex ]       && copy "Codex"       "$CODEX_DIR"
if [ -z "$ONLY" ] || [ "$ONLY" = antigravity ]; then
  [ "$AG_DIR" = "$CODEX_DIR" ] || copy "Antigravity" "$AG_DIR"
fi
echo "Done. In any project, ask your agent: \"set up build in public\"."
