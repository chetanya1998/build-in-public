#!/usr/bin/env python3
"""Build Your Product in Public: let the nightly gist's agent sign in with nobody at the keyboard.

The nightly job runs your agent on a schedule. A normal `claude` sign-in expires and can't be
renewed there, so the brief fails ("OAuth session expired"). Save a long-lived token once instead:

  claude setup-token                              # Claude subscription: gives a token for about a year
  python3 agent_auth.py set                       # paste it when asked (it isn't shown or logged)

  python3 agent_auth.py set --kind anthropic-key  # or an Anthropic API key (billed per use, no expiry)
  python3 agent_auth.py status                    # what's saved, where, and when it expires
  python3 agent_auth.py test                      # run `claude` once with it
  python3 agent_auth.py remove

Where it's kept: the macOS Keychain, the Linux Secret Service (secret-tool), or else a file only you
can read (~/.config/buildinpublic/agent-<kind>, mode 600). Never in the repo, the schedule or logs.
nightly.sh loads it just before it runs the agent. Each person saves their own: never share a token.
"""
import argparse
import datetime as dt
import getpass
import json
import os
import platform
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

SERVICE = os.environ.get("BIP_KEYCHAIN_SERVICE", "build-in-public")  # the same one the buildinpublic CLI uses
KINDS = {
    # kind: (environment variable, name, prefix it should start with, days it lasts)
    "claude-token": ("CLAUDE_CODE_OAUTH_TOKEN", "Claude long-lived token", "sk-ant-oat", 365),
    "anthropic-key": ("ANTHROPIC_API_KEY", "Anthropic API key", "sk-ant-api", None),
}
SAFE = re.compile(r"^[A-Za-z0-9_\-.]{20,400}$")


def conf_dir():
    return Path(os.environ.get("BIP_CONFIG_DIR") or Path.home() / ".config" / "buildinpublic")


def meta_path():
    return conf_dir() / "agent-auth.json"


def account(kind):
    return f"agent-{kind}"


def read_meta():
    try:
        return json.loads(meta_path().read_text())
    except (OSError, ValueError):
        return {}


def _run(cmd, **kw):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=20, **kw)
    except (OSError, subprocess.SubprocessError):
        return None


def _file(kind):
    return conf_dir() / f"agent-{kind}"


def backends():
    """Secret stores to use, best first. BIP_SECRET_STORE=file forces the file (tests, servers)."""
    forced = os.environ.get("BIP_SECRET_STORE")
    if forced:
        return [forced]
    out = []
    if platform.system() == "Darwin" and shutil.which("security"):
        out.append("keychain")
    if platform.system() == "Linux" and shutil.which("secret-tool"):
        out.append("secret-service")
    return out + ["file"]


def store(kind, value):
    """Save the secret; returns where it went. The value never goes on a command line."""
    for b in backends():
        if b == "keychain":
            # `security -i` reads the command from stdin, so the token isn't visible in the process list
            r = _run(["security", "-i"], input=f"add-generic-password -U -s {SERVICE} -a {account(kind)} -w {value}\n")
            if r and r.returncode == 0 and load_from("keychain", kind) == value:
                return "macOS Keychain"
        elif b == "secret-service":
            r = _run(["secret-tool", "store", "--label", f"{SERVICE} {kind}", "service", SERVICE, "account", account(kind)],
                     input=value)
            if r and r.returncode == 0:
                return "Secret Service"
        elif b == "file":
            f = _file(kind)
            f.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(str(f), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w") as fh:
                fh.write(value + "\n")
            os.chmod(f, 0o600)
            return f"file {str(f).replace(str(Path.home()), '~')} (only you can read it)"
    raise SystemExit("Couldn't save it anywhere.")


def load_from(b, kind):
    if b == "keychain":
        r = _run(["security", "find-generic-password", "-s", SERVICE, "-a", account(kind), "-w"])
        return r.stdout.strip() if r and r.returncode == 0 and r.stdout.strip() else None
    if b == "secret-service":
        for attr in ("account", "username"):  # the CLI's keyring library uses "username"
            r = _run(["secret-tool", "lookup", "service", SERVICE, attr, account(kind)])
            if r and r.returncode == 0 and r.stdout.strip():
                return r.stdout.strip()
        return None
    if b == "file":
        f = _file(kind)
        try:
            return f.read_text().strip() or None
        except OSError:
            return None
    return None


def load(kind):
    for b in backends():
        v = load_from(b, kind)
        if v:
            return v
    return None


def delete(kind):
    for b in backends():
        if b == "keychain":
            _run(["security", "delete-generic-password", "-s", SERVICE, "-a", account(kind)])
        elif b == "secret-service":
            _run(["secret-tool", "clear", "service", SERVICE, "account", account(kind)])
        elif b == "file":
            _file(kind).unlink(missing_ok=True)


def active_kind():
    """The kind the nightly job should use: the last one saved that's still there."""
    meta = read_meta()
    kinds = [meta.get("kind")] + [k for k in KINDS if k != meta.get("kind")]
    return next((k for k in kinds if k in KINDS and load(k)), None)


def expiry(meta=None):
    """(expires date, days left) for a Claude token, or (None, None)."""
    meta = meta if meta is not None else read_meta()
    days = KINDS.get(meta.get("kind"), (None,) * 4)[3]
    if not days or not meta.get("saved"):
        return None, None
    try:
        until = dt.date.fromisoformat(meta["saved"]) + dt.timedelta(days=days)
    except ValueError:
        return None, None
    return until, (until - dt.date.today()).days


def env_lines():
    """Shell lines for nightly.sh to eval. Empty when nothing is saved."""
    kind = active_kind()
    if not kind:
        return ""
    return f"export {KINDS[kind][0]}={shlex.quote(load(kind))}"


def agent_env(base=None):
    """os.environ plus the saved secret, for running the agent from Python."""
    env = dict(base if base is not None else os.environ)
    kind = active_kind()
    if kind:
        env[KINDS[kind][0]] = load(kind)
    return env


def status_lines():
    kind = active_kind()
    if not kind:
        return ["No token saved. The nightly agent uses your normal sign-in, which can expire.",
                "To fix that for good: claude setup-token, then python3 agent_auth.py set"]
    meta = read_meta()
    lines = [f"{KINDS[kind][1]} saved in {meta.get('store', 'your secret store')}"
             + (f" on {meta['saved']}" if meta.get("saved") else "") + "."]
    until, left = expiry(meta)
    if until:
        lines.append(f"It should last until about {until:%d %b %Y} ({left} days)." if left >= 0
                     else f"It probably expired on {until:%d %b %Y}: run claude setup-token, then agent_auth.py set again.")
    lines.append(f"The nightly job passes it to the agent as {KINDS[kind][0]}.")
    return lines


def cmd_set(a):
    name, prefix = KINDS[a.kind][1], KINDS[a.kind][2]
    if sys.stdin.isatty():
        if a.kind == "claude-token":
            print("Run `claude setup-token` in another terminal first, then paste the token it prints.")
        value = getpass.getpass(f"Paste your {name} (it won't be shown): ")
    else:
        value = sys.stdin.read()
    value = value.strip()
    if not value:
        raise SystemExit("Nothing pasted, nothing saved.")
    if not SAFE.match(value):
        raise SystemExit(f"That doesn't look like a {name} (unexpected characters). Nothing saved.")
    if not value.startswith(prefix):
        other = next((k for k, v in KINDS.items() if value.startswith(v[2])), None)
        art = lambda n: ("an " if n[0] in "AEIOU" else "a ") + n
        hint = f" It looks like {art(KINDS[other][1])}: use --kind {other}." if other else ""
        raise SystemExit(f"{art(name).capitalize()} starts with {prefix}…, and this doesn't.{hint} Nothing saved.")
    where = store(a.kind, value)
    meta_path().parent.mkdir(parents=True, exist_ok=True)
    meta_path().write_text(json.dumps({"kind": a.kind, "store": where, "saved": str(dt.date.today())}, indent=2) + "\n")
    print(f"Saved your {name} in {where}.")
    print("\n".join(status_lines()[1:]))
    print("Check it works: python3 agent_auth.py test")


def cmd_status(a):
    print("\n".join(status_lines()))


def cmd_remove(a):
    for k in KINDS:
        delete(k)
    meta_path().unlink(missing_ok=True)
    print("Removed. The nightly agent goes back to your normal sign-in.")


def cmd_test(a):
    if not shutil.which("claude"):
        raise SystemExit("`claude` isn't on your PATH.")
    kind = active_kind()
    print(f"Running claude with your {KINDS[kind][1]}…" if kind else "No token saved; testing your normal sign-in…")
    try:
        r = subprocess.run(["claude", "-p", "Reply with just OK"], stdin=subprocess.DEVNULL, capture_output=True,
                           text=True, timeout=120, env=agent_env())
    except subprocess.TimeoutExpired:
        raise SystemExit("claude didn't answer within 2 minutes.")
    said = (r.stdout + r.stderr).strip()
    if r.returncode == 0 and "ok" in said.lower():
        print("✓ Works: the nightly brief can be written.")
    else:
        raise SystemExit(f"✗ claude said: {said[:300]}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Sign in the nightly agent with a long-lived token.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("set", help="save a token (pasted, or piped on stdin)")
    s.add_argument("--kind", choices=list(KINDS), default="claude-token")
    s.set_defaults(fn=cmd_set)
    sub.add_parser("status").set_defaults(fn=cmd_status)
    sub.add_parser("test").set_defaults(fn=cmd_test)
    sub.add_parser("remove").set_defaults(fn=cmd_remove)
    sub.add_parser("env", help="for nightly.sh: shell exports (prints a secret!)").set_defaults(
        fn=lambda a: print(env_lines()) if env_lines() else None)
    a = ap.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
