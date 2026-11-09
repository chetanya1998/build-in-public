#!/bin/sh
# Build Your Product in Public · installer for macOS and Linux
#   curl -fsSL https://raw.githubusercontent.com/chetanya1998/build-in-public/main/install-cli.sh | sh
# Optional settings:
#   BIP_PACKAGE=...          what to install (default: this repo on GitHub)
#   BIP_PYTHON=/path/python  which Python to use with pip (default: python3)
#   BIP_INSTALLER=uv|pipx|pip  force an installer (default: uv, then pipx, then pip)
#   BIP_NO_MODIFY_PATH=1     don't add the command's folder to your shell profile
#   BIP_SKIP_EXTRAS=1        skip Playwright and the other optional packages
set -e
REPO="git+https://github.com/chetanya1998/build-in-public.git"
PKG="${BIP_PACKAGE:-$REPO}"

say() { printf '\033[1m%s\033[0m\n' "$1"; }
PY="${BIP_PYTHON:-$(command -v python3 || command -v python || true)}"
[ -n "$PY" ] || { echo "Python 3.9+ is required: https://www.python.org/downloads/"; exit 1; }
"$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' || { echo "Python 3.9+ is required."; exit 1; }

INSTALLER="${BIP_INSTALLER:-}"
if [ -z "$INSTALLER" ]; then
  if command -v uv >/dev/null 2>&1; then INSTALLER=uv
  elif command -v pipx >/dev/null 2>&1; then INSTALLER=pipx
  else INSTALLER=pip; fi
fi
EXTRAS="playwright psutil keyring pygments"
[ -n "$BIP_SKIP_EXTRAS" ] && EXTRAS=""

say "Installing Build Your Product in Public (with $INSTALLER)…"
case "$INSTALLER" in
  uv)   if [ -n "$EXTRAS" ]; then uv tool install --force "build-in-public[full] @ $PKG"; else uv tool install --force "$PKG"; fi ;;
  pipx) pipx install --force "$PKG"; [ -z "$EXTRAS" ] || pipx inject build-in-public $EXTRAS ;;
  pip)
    if "$PY" -c 'import os, sys, sysconfig; sys.exit(0 if os.path.exists(os.path.join(sysconfig.get_path("stdlib"), "EXTERNALLY-MANAGED")) else 1)'; then
      # Ubuntu 23.04+/Debian 12+: the system Python refuses `pip install --user`.
      # Install into a private virtualenv instead and link the command into ~/.local/bin.
      VENV="${XDG_DATA_HOME:-$HOME/.local/share}/buildinpublic/venv"
      "$PY" -m venv "$VENV" || {
        echo "Couldn't create a virtualenv. Install pipx (sudo apt install pipx) or uv, then run this again."
        exit 1
      }
      "$VENV/bin/python" -m pip install --quiet --upgrade pip
      "$VENV/bin/python" -m pip install --upgrade "$PKG" $EXTRAS
      mkdir -p "$HOME/.local/bin"
      ln -sf "$VENV/bin/buildinpublic" "$HOME/.local/bin/buildinpublic"
      PY="$VENV/bin/python"
    else
      # The pip that ships with macOS (21.x) builds this package as "UNKNOWN 0.0.0" with no code,
      # because it can't read pyproject.toml metadata. A current pip, in your user folder, can.
      "$PY" -m pip install --user --quiet --upgrade pip
      "$PY" -m pip install --user --upgrade "$PKG" $EXTRAS
    fi
    "$PY" -c 'import buildinpublic' 2>/dev/null || {
      echo "The install didn't work: Python can't import buildinpublic after pip finished."
      echo "Try: $PY -m pip install --user --upgrade --force-reinstall \"$PKG\""
      exit 1
    } ;;
  *) echo "Unknown BIP_INSTALLER: $INSTALLER (use uv, pipx or pip)"; exit 1 ;;
esac

# Make sure the `buildinpublic` command can be found, now and in new terminals.
if ! command -v buildinpublic >/dev/null 2>&1; then
  BIN=""
  for d in "$("$PY" -m site --user-base 2>/dev/null)/bin" "$HOME/.local/bin"; do
    [ -x "$d/buildinpublic" ] && { BIN="$d"; break; }
  done
  if [ -n "$BIN" ]; then
    PATH="$BIN:$PATH"; export PATH
    case "$(basename "${SHELL:-sh}")" in
      zsh)  PROFILE="$HOME/.zprofile" ;;
      bash) if [ "$(uname)" = Darwin ]; then PROFILE="$HOME/.bash_profile"; else PROFILE="$HOME/.bashrc"; fi ;;
      *)    PROFILE="$HOME/.profile" ;;
    esac
    LINE="export PATH=\"$BIN:\$PATH\"  # buildinpublic"
    if [ -n "$BIP_NO_MODIFY_PATH" ]; then
      echo "  buildinpublic is in $BIN, which isn't on your PATH. Add it with:"
      echo "    $LINE"
    elif ! grep -qs "# buildinpublic" "$PROFILE"; then
      printf '\n%s\n' "$LINE" >> "$PROFILE"
      echo "  Added $BIN to your PATH in $PROFILE. Open a new terminal to use \`buildinpublic\`."
    fi
  fi
fi
if command -v buildinpublic >/dev/null 2>&1; then BIP=buildinpublic; else BIP="$PY -m buildinpublic"; fi

if [ -n "$EXTRAS" ]; then
  say "Installing the browser used for screenshots (Chromium)…"
  $BIP install-browser || echo "  (skipped: run 'buildinpublic install-browser' later for screenshots)"
fi

say "Starting setup…"
# re-attach stdin to the terminal so setup can ask questions when piped from curl
if [ -t 1 ] && [ -r /dev/tty ]; then $BIP setup < /dev/tty; else $BIP setup --yes; fi
