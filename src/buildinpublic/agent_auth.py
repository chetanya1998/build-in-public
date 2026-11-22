"""`buildinpublic agent-auth`: let scheduled drafts sign in to your agent with nobody at the keyboard.

A normal `claude` sign-in expires and can't be renewed by a scheduled job. Save a long-lived token once
(`claude setup-token`, about a year) or an Anthropic API key, and every agent run the CLI makes gets it
as an environment variable. It's kept in the OS secret store: macOS Keychain (the same entry the
skill's agent_auth.py uses), Secret Service on Linux, or a DPAPI-protected file on Windows.
"""
from __future__ import annotations

import datetime as dt
import getpass
import json
import os
import re
import shutil
import subprocess
import sys

from . import notify
from .core import app_home

KINDS = {
    "claude-token": ("CLAUDE_CODE_OAUTH_TOKEN", "Claude long-lived token", "sk-ant-oat", 365),
    "anthropic-key": ("ANTHROPIC_API_KEY", "Anthropic API key", "sk-ant-api", None),
}
SAFE = re.compile(r"^[A-Za-z0-9_\-.]{20,400}$")


def _meta_file():
    return app_home() / "agent-auth.json"


def read_meta() -> dict:
    try:
        return json.loads(_meta_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def load(kind: str) -> str | None:
    try:
        return notify.get_secret(f"agent-{kind}")
    except Exception:
        return None


def active_kind() -> str | None:
    meta = read_meta()
    order = [meta.get("kind")] + [k for k in KINDS if k != meta.get("kind")]
    return next((k for k in order if k in KINDS and load(k)), None)


def agent_env(base: dict | None = None) -> dict:
    """The environment for an agent run: yours, plus the saved token if there is one."""
    env = dict(base if base is not None else os.environ)
    kind = active_kind()
    if kind:
        env[KINDS[kind][0]] = load(kind)
    return env


def expiry(meta: dict | None = None):
    meta = meta if meta is not None else read_meta()
    days = KINDS.get(meta.get("kind"), (None,) * 4)[3]
    if not days or not meta.get("saved"):
        return None, None
    until = dt.date.fromisoformat(meta["saved"]) + dt.timedelta(days=days)
    return until, (until - dt.date.today()).days


def status() -> list[str]:
    kind = active_kind()
    if not kind:
        return ["No token saved: agent runs use your normal sign-in, which can expire.",
                "Once a year instead: claude setup-token, then buildinpublic agent-auth set"]
    meta = read_meta()
    out = [f"{KINDS[kind][1]} saved in {meta.get('store', 'your secret store')}"
           + (f" on {meta['saved']}" if meta.get("saved") else "")]
    until, left = expiry(meta)
    if until:
        out.append(f"lasts until about {until:%d %b %Y} ({left} days)" if left >= 0
                   else f"probably expired on {until:%d %b %Y}: claude setup-token, then agent-auth set")
    return out


def set_token(kind: str, value: str | None = None) -> str:
    name, prefix = KINDS[kind][1], KINDS[kind][2]
    if value is None:
        if sys.stdin.isatty():
            if kind == "claude-token":
                print("Run `claude setup-token` in another terminal first, then paste the token it prints.")
            value = getpass.getpass(f"Paste your {name} (it won't be shown): ")
        else:
            value = sys.stdin.read()
    value = value.strip()
    if not value or not SAFE.match(value):
        raise SystemExit(f"That doesn't look like a {name}. Nothing saved.")
    if not value.startswith(prefix):
        raise SystemExit(f"This doesn't start with {prefix}…, so it isn't a {name}. Nothing saved."
                         + (" Use --kind anthropic-key for an API key." if value.startswith("sk-ant-api") else ""))
    where = notify.set_secret(f"agent-{kind}", value)
    _meta_file().write_text(json.dumps({"kind": kind, "store": where, "saved": str(dt.date.today())}, indent=2),
                            encoding="utf-8")
    return where


def remove() -> None:
    for kind in KINDS:
        try:
            import keyring  # type: ignore
            keyring.delete_password(notify.SERVICE, f"agent-{kind}")
        except Exception:
            pass
        if sys.platform == "darwin":
            subprocess.run(["security", "delete-generic-password", "-s", notify.SERVICE, "-a", f"agent-{kind}"],
                           capture_output=True)
        elif shutil.which("secret-tool"):
            subprocess.run(["secret-tool", "clear", "service", notify.SERVICE, "account", f"agent-{kind}"],
                           capture_output=True)
        (app_home() / f"secret-agent-{kind}").unlink(missing_ok=True)
    _meta_file().unlink(missing_ok=True)


def test() -> tuple[bool, str]:
    exe = shutil.which("claude")
    if not exe:
        return False, "`claude` isn't on your PATH."
    try:
        r = subprocess.run([exe, "-p", "Reply with just OK"], stdin=subprocess.DEVNULL, capture_output=True,
                           text=True, timeout=120, env=agent_env())
    except (OSError, subprocess.SubprocessError) as e:
        return False, str(e)
    said = (r.stdout + r.stderr).strip()
    return r.returncode == 0 and "ok" in said.lower(), said[:300]
