#!/usr/bin/env python3
"""Build In Public: check that everything the skill needs is in place for this repo.

Checks tools (Python, git, zstd, Playwright, agent CLI), the .buildinpublic/ setup,
agent logging rules, the git hook, gist delivery (notification, email settings and
password present, never read), the schedule, which agent sessions can be found for the
last 7 days, and the last nightly run. Read-only, no network calls.
Paste the output into a GitHub issue when something doesn't work.

Usage: python3 doctor.py [--repo PATH]
Exit code 1 if something is broken (✗); warnings (!) don't fail.
"""
import argparse, datetime as dt, json, os, platform, re, shutil, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import collect, notify, share  # noqa: E402

SKILL_DIR = Path(__file__).resolve().parent.parent
RESULTS = []


def ok(label, detail=""):
    RESULTS.append(("✓", label, detail))


def warn(label, detail=""):
    RESULTS.append(("!", label, detail))


def fail(label, detail=""):
    RESULTS.append(("✗", label, detail))


def section(title):
    RESULTS.append(("", title, ""))


def run(*cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=10).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def check_tools(cfg):
    section("Tools")
    v = sys.version_info
    (ok if v >= (3, 9) else fail)("Python", f"{v.major}.{v.minor}.{v.micro}" + ("" if v >= (3, 9) else " (needs 3.9+)"))
    (ok if shutil.which("git") else fail)("git", run("git", "--version") or "not found")

    codex_zst = list((collect.HOME / ".codex" / "sessions").rglob("*.jsonl.zst")) if (collect.HOME / ".codex" / "sessions").is_dir() else []
    if shutil.which("zstd"):
        ok("zstd", "can read compressed Codex sessions")
    elif codex_zst:
        warn("zstd", f"{len(codex_zst)} compressed Codex sessions can't be read: brew install zstd (or apt install zstd)")
    else:
        ok("zstd", "not installed, not needed yet")

    if cfg.get("capture", "ask") != "off":
        try:
            import playwright  # noqa: F401
            ok("Playwright", "terminal and browser captures can make images")
        except ImportError:
            warn("Playwright", "missing, so captures save text only and browser captures can't run: "
                               "pip install playwright && playwright install chromium")

    agent, custom = cfg.get("agent", ""), cfg.get("agent_command", "")
    if custom:
        exe = custom.split()[0]
        (ok if shutil.which(exe) else fail)("Nightly agent", f"agent_command '{exe}'" + ("" if shutil.which(exe) else " not found on PATH"))
    elif agent in ("claude", "codex"):
        (ok if shutil.which(agent) else fail)("Nightly agent", f"{agent}" + ("" if shutil.which(agent) else " CLI not found on PATH, so the nightly brief can't be written"))
    elif cfg:
        warn("Nightly agent", "none configured: nightly runs stop at the digest; ask your agent for the brief")


def check_install():
    section("Skill install")
    found = [p for p in (Path.home() / ".claude/skills", Path.home() / ".agents/skills",
                         Path.home() / ".gemini/config/skills", Path(".claude/skills"), Path(".agents/skills"))
             if (p / "build-in-public" / "SKILL.md").exists()]
    if found:
        ok("Installed", ", ".join(str(p).replace(str(Path.home()), "~") for p in found))
    else:
        warn("Installed", f"running from {SKILL_DIR}, not found in any agent's skills folder: run sh install.sh")


def check_setup(repo):
    section(f"Project setup ({repo.name})")
    if not (repo / ".git").exists():
        warn("git repo", "not a git repo, so commits won't be included")
    bip = repo / ".buildinpublic"
    if not bip.is_dir():
        fail(".buildinpublic/", "missing: ask your agent \"set up build in public\"")
        return {}

    cfg = {}
    cfg_path = bip / "config.json"
    if not cfg_path.exists():
        fail("config.json", "missing: copy it from templates/config.json or rerun setup")
    else:
        try:
            cfg = json.loads(cfg_path.read_text())
        except ValueError as e:
            fail("config.json", f"invalid JSON: {e}")
        else:
            topics = cfg.get("topics") or []
            placeholders = [t for t in topics if "<" in t]
            if not topics:
                warn("Trend topics", "none set, so trends.py will skip")
            elif placeholders:
                warn("Trend topics", f"still template placeholders: {placeholders[0]}")
            else:
                ok("Trend topics", ", ".join(topics))

    narrative = bip / "narrative.md"
    if not narrative.exists():
        fail("narrative.md", "missing: rerun setup")
    else:
        text = narrative.read_text()
        empty = []
        for name in ("Product", "Audience", "Problem", "Voice"):
            m = re.search(rf"## {name}\s*\n(.*?)(\n## |\Z)", text, re.S)
            if not m or not re.sub(r"<!--.*?-->", "", m.group(1), flags=re.S).strip():
                empty.append(name)
        if empty:
            warn("narrative.md", "empty sections: " + ", ".join(empty) + " (drafts will be generic)")
        else:
            ok("narrative.md", "filled in")

    rules = [f for f in ("AGENTS.md", "CLAUDE.md", "GEMINI.md")
             if (repo / f).exists() and ".buildinpublic/log" in (repo / f).read_text(errors="ignore")]
    if rules:
        ok("Agent logging rule", ", ".join(rules))
    else:
        warn("Agent logging rule", "not in AGENTS.md / CLAUDE.md / GEMINI.md, so agents won't write log entries")

    hook = repo / ".git" / "hooks" / "post-commit"
    if hook.exists() and "Build In Public" in hook.read_text(errors="ignore"):
        ok("git hook", "post-commit logs commits")
    else:
        warn("git hook", "not installed (optional): sh <skill>/scripts/init.sh --hook")
    return cfg


def check_email(cfg):
    section("Daily gist delivery")
    if cfg.get("notify", True) in (False, "off"):
        warn("Desktop notification", "turned off in config.json")
    else:
        ok("Desktop notification", "on")
    if cfg.get("email", True) in (False, "off"):
        ok("Email", "turned off in config.json")
        return
    path = Path.home() / ".config" / "buildinpublic" / "email.json"
    if not path.exists():
        ok("Email", "optional, not set up (to add it, just your address: {\"to\": \"you@example.com\"} in "
                    + str(path).replace(str(Path.home()), "~") + ")")
        return
    try:
        email = json.loads(path.read_text())
    except ValueError as e:
        fail("Email", f"email.json is invalid JSON: {e}")
        return
    if not email.get("to"):
        fail("Email", "email.json needs your address: {\"to\": \"you@example.com\"}")
        return
    how = notify.method(email)
    if how == "mail-app":
        ok("Email", f"to {email['to']} via Apple Mail (needs an account in Mail; run notify.py --test once to allow access)")
    elif how == "sendmail":
        (ok if notify.sendmail_path() else fail)("Email", f"to {email['to']} via sendmail"
                                                 + ("" if notify.sendmail_path() else ", but no sendmail is installed"))
    elif how == "smtp":
        user = email.get("smtp_user", "")
        pw_file = Path.home() / ".config" / "buildinpublic" / "smtp-password"
        has_pw = bool(os.environ.get("BIP_SMTP_PASSWORD")) or pw_file.exists() or (
            platform.system() == "Darwin" and subprocess.run(
                ["security", "find-generic-password", "-s", "buildinpublic-smtp", "-a", user],
                capture_output=True).returncode == 0)
        (ok if has_pw else fail)("Email", f"to {email['to']} via SMTP {email.get('smtp_host')}" + (
            "" if has_pw else f": no password found (security add-generic-password -s buildinpublic-smtp -a {user} -w)"))
    else:
        fail("Email", "no Apple Mail or sendmail on this machine to send it with; remove email.json or set up msmtp")


def check_share(repo, cfg):
    section("Posts on GitHub")
    hook = repo / ".git" / "hooks" / "pre-commit"
    hooked = hook.exists() and "share.py" in hook.read_text(errors="ignore")
    if cfg.get("share") != "commits":
        ok("Share with commits", "off (to turn on: sh <skill>/scripts/init.sh --share)")
        return
    if not hooked:
        fail("Share with commits", "on in config.json, but the pre-commit hook is missing: sh <skill>/scripts/init.sh --share")
        return
    target = re.search(r'python3 "([^"]+/share\.py)"', hook.read_text(errors="ignore"))
    if target and not Path(target.group(1)).exists():
        fail("Share with commits", f"the hook points to {target.group(1)}, which no longer exists: rerun init.sh --share")
        return
    shared = len(share.shared_posts(repo))
    remote = run("git", "-C", str(repo), "remote", "get-url", "origin")
    ok("Share with commits", f"{shared} approved post(s) go out with your next commit"
       + (f"; on GitHub after you push" if "github.com" in remote else "; no GitHub remote yet"))
    warn("Visibility", "if this repo is public, everyone can read shared posts and see their images")


def check_schedule(repo):
    section("Nightly schedule")
    job = "ai.buildinpublic." + re.sub(r"[^A-Za-z0-9-]", "", repo.name)
    if platform.system() == "Darwin":
        plist = Path.home() / "Library" / "LaunchAgents" / f"{job}.plist"
        if not plist.exists():
            warn("Scheduled", "no nightly brief scheduled (optional): sh <skill>/scripts/schedule.sh")
            return
        text = plist.read_text()
        h = re.search(r"<key>Hour</key><integer>(\d+)", text)
        m = re.search(r"<key>Minute</key><integer>(\d+)", text)
        when = f"{int(h.group(1)):02d}:{int(m.group(1)):02d}" if h and m else "?"
        loaded = job in run("launchctl", "list")
        (ok if loaded else warn)("Scheduled", f"daily at {when} (launchd)" + ("" if loaded else ", but not loaded: rerun schedule.sh"))
        target = re.search(r"<string>([^<]*nightly\.sh)</string>", text)
        if target and not Path(target.group(1)).exists():
            fail("Scheduled script", f"{target.group(1)} no longer exists: rerun schedule.sh")
    else:
        line = next((l for l in run("crontab", "-l").splitlines() if l.endswith(f"# {job}")), "")
        if line:
            m, h = line.split()[:2]
            ok("Scheduled", f"daily at {int(h):02d}:{int(m):02d} (cron)")
        else:
            warn("Scheduled", "no nightly brief scheduled (optional): sh <skill>/scripts/schedule.sh")


def check_sessions(repo, today):
    section("Agent sessions for this repo (last 7 days)")
    days = [today - dt.timedelta(days=i) for i in range(7)]
    sources = {"Claude Code": collect.claude_sessions, "Codex": collect.codex_sessions,
               "Antigravity": collect.antigravity_sessions}
    total = 0
    for name, fn in sources.items():
        paths = set()
        for d in days:
            paths |= {s["path"] for s in fn(repo, d)}
        total += len(paths)
        (ok if paths else warn)(name, f"{len(paths)} session(s)" + ("" if paths else
                                 ", fine if you don't use it; if you do, run collect.py --inspect and open an issue"))
    if not total:
        warn("Sessions", "none found: check the agent was run inside this folder")


def check_last_run(repo):
    section("Last nightly run")
    daily = repo / ".buildinpublic" / "daily"
    runs = sorted(d for d in daily.iterdir() if d.is_dir()) if daily.is_dir() else []
    if not runs:
        warn("Runs", "none yet: sh <skill>/scripts/nightly.sh, or ask your agent \"build in public brief\"")
        return
    last = runs[-1]
    files = [f for f in ("digest.md", "trends.md", "brief.md") if (last / f).exists()]
    (ok if "brief.md" in files else warn)(last.name, "has " + (", ".join(files) or "no output files"))
    log = last / "nightly.log"
    if log.exists():
        errors = [l for l in log.read_text(errors="ignore").splitlines()
                  if re.search(r"Traceback|Error|error:|command not found", l)]
        if errors:
            warn("nightly.log", f"{len(errors)} error line(s), last: {errors[-1].strip()[:120]}")
        else:
            ok("nightly.log", "no errors")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    a = ap.parse_args()
    repo = Path(run("git", "-C", a.repo, "rev-parse", "--show-toplevel") or a.repo).resolve()
    today = (dt.datetime.now() - dt.timedelta(hours=4)).date()

    print(f"Build In Public doctor · {repo} · {platform.system()} · {today}")
    check_install()
    cfg = check_setup(repo)
    check_tools(cfg)
    check_email(cfg)
    check_share(repo, cfg)
    check_schedule(repo)
    check_sessions(repo, today)
    check_last_run(repo)

    for mark, label, detail in RESULTS:
        print(f"\n{label}" if not mark else f"  {mark} {label}" + (f": {detail}" if detail else ""))
    fails = sum(1 for r in RESULTS if r[0] == "✗")
    warns = sum(1 for r in RESULTS if r[0] == "!")
    print(f"\n{fails} problem(s), {warns} warning(s).")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
