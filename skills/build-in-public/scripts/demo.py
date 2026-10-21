#!/usr/bin/env python3
"""Build In Public: see what the skill produces before you set anything up.

Builds a throwaway project ("Tinyinvoice", fictional) in a temp folder, with a git
history, an agent log, and fake Claude Code, Codex and Antigravity session files in a
fake home folder. Then it runs the real collect.py on it, so digest.md is exactly what
the skill would extract, and adds a sample brief written for that same day.

Nothing outside the temp folder is read or changed, and there are no network calls.
The same sample data is used by the tests in tests/.

Usage: python3 demo.py [--out DIR] [--date YYYY-MM-DD] [--show]
"""
import argparse, datetime as dt, os, re, shutil, struct, subprocess, sys, tempfile, zlib
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
DEMO = SKILL_DIR / "demo"

COMMITS = [  # (time, message, files)
    ("10:24", "fix: due dates shift a day in US timezones",
     ["src/lib/dates.ts", "src/pdf/render.ts", "src/lib/dates.test.ts", "migrations/0007_due_date_as_date.sql"]),
    ("14:25", "feat: retry Stripe webhooks that arrive before the invoice",
     ["src/webhooks/stripe.ts", "src/webhooks/queue.ts", "migrations/0008_webhook_events.sql"]),
    ("17:38", "feat: two-step onboarding",
     ["src/onboarding/steps.tsx", "src/onboarding/defaults.ts"]),
]


def fill(text, repo, day):
    return text.replace("{{REPO}}", str(repo)).replace("{{DAY}}", str(day))


def touch_on(path, day):
    t = dt.datetime.combine(day, dt.time(12, 0)).timestamp()
    os.utime(path, (t, t))


def png(width=320, height=200, rgb=(46, 125, 230)):
    """A plain one-colour PNG, standing in for an agent's browser screenshot."""
    row = b"\x00" + bytes(rgb) * width
    chunk = lambda kind, data: (struct.pack(">I", len(data)) + kind + data
                                + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(row * height)) + chunk(b"IEND", b""))


def build_fake_home(home, repo, day):
    """Lay out the sample sessions where each agent keeps them, as if run in `repo` on `day`."""
    src = DEMO / "sessions"
    written = []

    claude = home / ".claude" / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(repo))
    claude.mkdir(parents=True, exist_ok=True)
    f = claude / "8f3c2a10-demo.jsonl"
    f.write_text(fill((src / "claude.jsonl").read_text(), repo, day))
    written.append(f)

    codex = home / ".codex" / "sessions" / f"{day:%Y}" / f"{day:%m}" / f"{day:%d}"
    codex.mkdir(parents=True, exist_ok=True)
    for name in ("codex.jsonl", "codex-other-project.jsonl"):
        f = codex / f"rollout-{day}T14-10-00-{name}"
        f.write_text(fill((src / name).read_text(), repo, day))
        written.append(f)

    brain = home / ".gemini" / "antigravity" / "brain" / "demo-conv"
    brain.mkdir(parents=True, exist_ok=True)
    for md in (src / "antigravity").glob("*.md"):
        f = brain / md.name
        f.write_text(fill(md.read_text(), repo, day))
        written.append(f)
    f = brain / "onboarding-after.png"
    f.write_bytes(png())
    written.append(f)

    for f in written:
        touch_on(f, day)
    return written


def build_repo(repo, day):
    """A small git repo with the day's commits and a filled-in .buildinpublic/ folder."""
    repo.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, GIT_AUTHOR_NAME="Demo", GIT_AUTHOR_EMAIL="demo@example.com",
               GIT_COMMITTER_NAME="Demo", GIT_COMMITTER_EMAIL="demo@example.com")
    git = lambda *a, **kw: subprocess.run(["git", "-C", str(repo), *a], check=True,
                                          capture_output=True, env=kw.get("env", env))
    git("init", "-q")
    (repo / "README.md").write_text("# Tinyinvoice\n\nInvoices for freelancers. (Build In Public demo project.)\n")
    (repo / ".gitignore").write_text(".buildinpublic/daily/\n")
    git("add", "-A")
    stamp = f"{day - dt.timedelta(days=1)}T18:00:00"
    git("commit", "-q", "-m", "initial commit", env=dict(env, GIT_AUTHOR_DATE=stamp, GIT_COMMITTER_DATE=stamp))
    for hhmm, msg, files in COMMITS:
        for rel in files:
            p = repo / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(f"// {msg}\n")
        git("add", "-A")
        stamp = f"{day}T{hhmm}:00"
        git("commit", "-q", "-m", msg, env=dict(env, GIT_AUTHOR_DATE=stamp, GIT_COMMITTER_DATE=stamp))

    bip = repo / ".buildinpublic"
    for d in ("log", "posts", "assets", "daily"):
        (bip / d).mkdir(parents=True, exist_ok=True)
    shutil.copy(DEMO / "narrative.md", bip / "narrative.md")
    shutil.copy(DEMO / "config.json", bip / "config.json")
    shutil.copy(DEMO / "log.md", bip / "log" / f"{day}.md")
    (bip / "commits.log").write_text("")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", help="folder to build the demo in (default: a new temp folder)")
    ap.add_argument("--date", help="YYYY-MM-DD (default: today)")
    ap.add_argument("--show", action="store_true", help="print the sample brief")
    a = ap.parse_args()

    day = dt.date.fromisoformat(a.date) if a.date else (dt.datetime.now() - dt.timedelta(hours=4)).date()
    root = Path(a.out or tempfile.mkdtemp(prefix="buildinpublic-demo-")).resolve()
    repo, home = root / "tinyinvoice", root / "home"
    if repo.exists():
        sys.exit(f"{repo} already exists; pass a different --out")

    build_repo(repo, day)
    build_fake_home(home, repo, day)
    r = subprocess.run([sys.executable, str(SKILL_DIR / "scripts" / "collect.py"), "--repo", str(repo),
                        "--date", str(day)], env=dict(os.environ, HOME=str(home)), capture_output=True, text=True)
    if r.returncode:
        sys.exit("collect.py failed:\n" + r.stderr)

    out = repo / ".buildinpublic" / "daily" / str(day)
    brief = out / "brief.md"
    brief.write_text(fill((DEMO / "sample-brief.md").read_text(), repo, day))

    print(f"""Build In Public demo ready (fictional project, nothing outside {root} was touched).

  Digest  {out / 'digest.md'}
          what collect.py actually pulled from 3 sample agent sessions, git and the log,
          with the email, token and off-limits client name redacted
  Brief   {brief}
          a sample brief written for this same day; yours is written by your agent

See your own agent write one:  cd {repo} && claude "build in public brief"
""")
    if a.show:
        print(brief.read_text())


if __name__ == "__main__":
    main()
