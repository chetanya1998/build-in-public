#!/bin/sh
# Build Your Product in Public · installer for macOS and Linux
#   curl -fsSL https://raw.githubusercontent.com/chetanya1998/build-in-public/main/install.sh | sh
set -e
REPO="git+https://github.com/chetanya1998/build-in-public.git"
PKG="${BIP_PACKAGE:-$REPO}"

say() { printf '\033[1m%s\033[0m\n' "$1"; }
PY="$(command -v python3 || command -v python || true)"
[ -n "$PY" ] || { echo "Python 3.9+ is required: https://www.python.org/downloads/"; exit 1; }
"$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' || { echo "Python 3.9+ is required."; exit 1; }

say "Installing Build Your Product in Public…"
if command -v uv >/dev/null 2>&1; then
  uv tool install --force "build-in-public[full] @ $PKG"
elif command -v pipx >/dev/null 2>&1; then
  pipx install --force "$PKG" && pipx inject build-in-public playwright psutil keyring pygments
else
  "$PY" -m pip install --user --upgrade "$PKG" playwright psutil keyring pygments
fi

if command -v buildinpublic >/dev/null 2>&1; then BIP=buildinpublic; else BIP="$PY -m buildinpublic"; fi

say "Installing the browser used for screenshots (Chromium)…"
$BIP install-browser || echo "  (skipped: run 'buildinpublic install-browser' later for screenshots)"

say "Starting setup…"
# re-attach stdin to the terminal so setup can ask questions when piped from curl
if [ -t 1 ] && [ -r /dev/tty ]; then $BIP setup < /dev/tty; else $BIP setup --yes; fi
