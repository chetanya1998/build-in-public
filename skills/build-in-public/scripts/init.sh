#!/bin/sh
# Build In Public: scaffold .buildinpublic/ in the current project.
# Usage: sh <skill-dir>/scripts/init.sh [--hook] [--share]
#   --hook   post-commit hook: log each commit to .buildinpublic/commits.log
#   --share  pre-commit hook: add approved posts and their images to each commit
set -e
SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p .buildinpublic/log .buildinpublic/posts .buildinpublic/assets .buildinpublic/daily
[ -f .buildinpublic/narrative.md ] || cp "$SKILL_DIR/templates/narrative.md" .buildinpublic/narrative.md
touch .buildinpublic/commits.log
[ -f .buildinpublic/config.json ] || cp "$SKILL_DIR/templates/config.json" .buildinpublic/config.json

install_hook() { # $1 = hook name, $2 = source script
  HOOK=".git/hooks/$1"
  BODY="$(sed "s#__SKILL_DIR__#$SKILL_DIR#g" "$2")"
  if [ -f "$HOOK" ]; then
    grep -q "Build In Public" "$HOOK" || printf '\n%s\n' "$(echo "$BODY" | tail -n +2)" >> "$HOOK"
  else
    echo "$BODY" > "$HOOK"
  fi
  chmod +x "$HOOK"
}

for arg in "$@"; do
  [ -d .git ] || { echo "Not a git repo; skipping $arg."; continue; }
  case "$arg" in
    --hook)  install_hook post-commit "$SKILL_DIR/scripts/post-commit.sh"; echo "Installed git post-commit hook." ;;
    --share) install_hook pre-commit "$SKILL_DIR/scripts/pre-commit.sh"
             python3 - <<'PY'
import json, pathlib
p = pathlib.Path(".buildinpublic/config.json"); c = json.loads(p.read_text()); c["share"] = "commits"
p.write_text(json.dumps(c, indent=2) + "\n")
PY
             echo "Installed git pre-commit hook: approved posts are added to your commits." ;;
  esac
done
echo "Build In Public ready in .buildinpublic/"
