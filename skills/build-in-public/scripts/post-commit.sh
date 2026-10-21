#!/bin/sh
# Build In Public: append each commit to .buildinpublic/commits.log
ROOT="$(git rev-parse --show-toplevel)" || exit 0
mkdir -p "$ROOT/.buildinpublic"
{
  git log -1 --date=format:'%Y-%m-%d %H:%M' --pretty=format:'%ad | %h | %s'
  echo
  git log -1 --shortstat --pretty=format: | sed '/^$/d'
  echo
} >> "$ROOT/.buildinpublic/commits.log"
