"""Builds a fake agent setup for the tests: a small git repo with a filled-in
.buildinpublic/ folder, and a fake home folder holding Claude Code, Codex and
Antigravity session files in each agent's real format (from tests/fixtures/sessions).
"""
import datetime as dt, os, re, shutil, struct, subprocess, zlib
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent / "fixtures"

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
    src = FIXTURES / "sessions"
    written = []

    claude = home / ".claude" / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(repo))
    claude.mkdir(parents=True, exist_ok=True)
    f = claude / "8f3c2a10.jsonl"
    f.write_text(fill((src / "claude.jsonl").read_text(), repo, day))
    written.append(f)

    codex = home / ".codex" / "sessions" / f"{day:%Y}" / f"{day:%m}" / f"{day:%d}"
    codex.mkdir(parents=True, exist_ok=True)
    for name in ("codex.jsonl", "codex-other-project.jsonl"):
        f = codex / f"rollout-{day}T14-10-00-{name}"
        f.write_text(fill((src / name).read_text(), repo, day))
        written.append(f)

    brain = home / ".gemini" / "antigravity" / "brain" / "conv-1"
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
    env = dict(os.environ, GIT_AUTHOR_NAME="Test", GIT_AUTHOR_EMAIL="test@example.com",
               GIT_COMMITTER_NAME="Test", GIT_COMMITTER_EMAIL="test@example.com")
    git = lambda *a, **kw: subprocess.run(["git", "-C", str(repo), *a], check=True,
                                          capture_output=True, env=kw.get("env", env))
    git("init", "-q")
    (repo / "README.md").write_text("# Tinyinvoice\n\nInvoices for freelancers. (test fixture)\n")
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
    shutil.copy(FIXTURES / "narrative.md", bip / "narrative.md")
    shutil.copy(FIXTURES / "config.json", bip / "config.json")
    shutil.copy(FIXTURES / "log.md", bip / "log" / f"{day}.md")
    (bip / "commits.log").write_text("")


