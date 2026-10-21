#!/bin/sh
# Build In Public: scaffold .buildinpublic/ in the current project.
# Usage: sh <skill-dir>/scripts/init.sh [--hook]
set -e
SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p .buildinpublic/log .buildinpublic/posts .buildinpublic/assets .buildinpublic/daily
[ -f .buildinpublic/narrative.md ] || cp "$SKILL_DIR/templates/narrative.md" .buildinpublic/narrative.md
touch .buildinpublic/commits.log
[ -f .buildinpublic/config.json ] || cp "$SKILL_DIR/templates/config.json" .buildinpublic/config.json

if [ "$1" = "--hook" ] && [ -d .git ]; then
  HOOK=.git/hooks/post-commit
  if [ -f "$HOOK" ]; then
    grep -q "Build In Public" "$HOOK" || tail -n +2 "$SKILL_DIR/scripts/post-commit.sh" >> "$HOOK"
  else
    cp "$SKILL_DIR/scripts/post-commit.sh" "$HOOK"
  fi
  chmod +x "$HOOK"
  echo "Installed git post-commit hook."
fi
echo "Build In Public ready in .buildinpublic/"
