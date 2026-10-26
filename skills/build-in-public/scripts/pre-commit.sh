#!/bin/sh
# Build In Public: add your approved posts and their images to this commit (see share.py).
# Never blocks a commit. Skip once with: BIP_SKIP_SHARE=1 git commit ...
[ -n "$BIP_SKIP_SHARE" ] && exit 0
ROOT="$(git rev-parse --show-toplevel)" || exit 0
[ -d "$ROOT/.buildinpublic/posts" ] || exit 0
python3 "__SKILL_DIR__/scripts/share.py" --repo "$ROOT" --stage --quiet || true
