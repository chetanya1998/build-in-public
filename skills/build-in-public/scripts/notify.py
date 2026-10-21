#!/usr/bin/env python3
"""Build In Public: send today's gist as a desktop notification and an email.

The gist is the top of brief.md: the day in one line, what you shipped, and the list of
suggested posts to choose from. If no brief was written (no headless agent), it falls back
to what the digest found. The full brief.md is attached to the email.

Email settings are per user, not per repo, in ~/.config/buildinpublic/email.json:
  {"to": "you@example.com", "from": "you@example.com",
   "smtp_host": "smtp.gmail.com", "smtp_port": 587, "smtp_user": "you@example.com",
   "security": "starttls"}            # or "ssl" (port 465)
The password is never stored in that file. It's read from, in order:
  1. the BIP_SMTP_PASSWORD environment variable
  2. macOS Keychain:  security add-generic-password -s buildinpublic-smtp -a <smtp_user> -w
  3. ~/.config/buildinpublic/smtp-password  (must be chmod 600)
For Gmail, use an app password (Google Account > Security > App passwords).

Usage: python3 notify.py [--repo PATH] [--date YYYY-MM-DD] [--dry-run] [--test] [--no-desktop]
"""
import argparse, datetime as dt, json, os, platform, re, shutil, smtplib, ssl, stat, subprocess, sys
from email.message import EmailMessage
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "buildinpublic"
GIST_SECTIONS = ("Today in one line", "What you shipped", "Post ideas", "Suggested posts")


def section(text, name):
    m = re.search(rf"^##\s+{re.escape(name)}\s*\n(.*?)(?=^##\s|\Z)", text, re.S | re.M)
    return m.group(1).strip() if m else ""


def build_gist(repo, day):
    """Return (headline, body) for today's gist."""
    out = repo / ".buildinpublic" / "daily" / str(day)
    brief = out / "brief.md"
    if brief.exists():
        text = brief.read_text()
        parts = [(n, section(text, n)) for n in GIST_SECTIONS]
        parts = [(n, b) for n, b in parts if b]
        headline = next((b.splitlines()[0] for n, b in parts if n == "Today in one line"), "") or "Your brief is ready"
        body = "\n\n".join(f"{n.upper()}\n{b}" for n, b in parts) or text[:3000]
        body += ("\n\nPick a post: open your agent in this project and say \"review my posts\""
                 " (or \"write post 2\"). Nothing is posted for you.")
        return headline, body

    digest = out / "digest.md"
    if not digest.exists():
        return "Quiet day", "No activity was found for this day."
    text = digest.read_text()
    found = re.search(r"^Sessions found: (.*)$", text, re.M)
    commits = re.findall(r"^- \d\d:\d\d [0-9a-f]{7,} (.+)$", section(text, "Git commits"), re.M)
    logged = re.findall(r"^### [\d:]+ - (.+?)\s+\(agent", text, re.M)
    lines = [f"Sessions: {found.group(1)}" if found else ""]
    lines += [f"- {t}" for t in logged] or [f"- {c}" for c in commits]
    body = "\n".join(l for l in lines if l)
    body += ("\n\nNo brief was written yet (no headless agent is set up). Open your agent in this project "
             "and say \"build in public brief\" to get the story and the list of posts.")
    return (logged or commits or ["Your digest is ready"])[0], body


def desktop(title, message):
    message = message.replace('"', "'")
    if platform.system() == "Darwin" and shutil.which("osascript"):
        subprocess.run(["osascript", "-e", f'display notification "{message}" with title "{title}"'],
                       capture_output=True)
    elif shutil.which("notify-send"):
        subprocess.run(["notify-send", title, message], capture_output=True)


def email_settings():
    p = CONFIG_DIR / "email.json"
    if not p.exists():
        return None
    cfg = json.loads(p.read_text())
    missing = [k for k in ("to", "smtp_host", "smtp_user") if not cfg.get(k)]
    if missing:
        sys.exit(f"{p} is missing: {', '.join(missing)}")
    return cfg


def smtp_password(user):
    if os.environ.get("BIP_SMTP_PASSWORD"):
        return os.environ["BIP_SMTP_PASSWORD"]
    if platform.system() == "Darwin":
        r = subprocess.run(["security", "find-generic-password", "-s", "buildinpublic-smtp", "-a", user, "-w"],
                           capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    f = CONFIG_DIR / "smtp-password"
    if f.exists():
        if f.stat().st_mode & (stat.S_IRWXG | stat.S_IRWXO):
            sys.exit(f"{f} is readable by other users; run: chmod 600 {f}")
        return f.read_text().strip()
    sys.exit("No SMTP password found. Add it to the Keychain with:\n"
             f"  security add-generic-password -s buildinpublic-smtp -a {user} -w\n"
             "or set BIP_SMTP_PASSWORD, or write it to ~/.config/buildinpublic/smtp-password (chmod 600).")


def compose(cfg, repo, day, headline, body):
    msg = EmailMessage()
    msg["Subject"] = f"Build In Public · {repo.name} · {day}: {headline}"[:180]
    msg["From"] = cfg.get("from") or cfg["smtp_user"]
    msg["To"] = cfg["to"]
    msg.set_content(body)
    brief = repo / ".buildinpublic" / "daily" / str(day) / "brief.md"
    if brief.exists():
        msg.add_attachment(brief.read_bytes(), maintype="text", subtype="markdown", filename=f"brief-{day}.md")
    return msg


def send(cfg, msg):
    host, port = cfg["smtp_host"], int(cfg.get("smtp_port") or 587)
    password = smtp_password(cfg["smtp_user"])
    ctx = ssl.create_default_context()
    if cfg.get("security") == "ssl" or port == 465:
        with smtplib.SMTP_SSL(host, port, context=ctx, timeout=30) as s:
            s.login(cfg["smtp_user"], password)
            s.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=30) as s:
            s.starttls(context=ctx)
            s.login(cfg["smtp_user"], password)
            s.send_message(msg)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    ap.add_argument("--date")
    ap.add_argument("--dry-run", action="store_true", help="print the email instead of sending it")
    ap.add_argument("--test", action="store_true", help="send a short test email to check the settings")
    ap.add_argument("--no-desktop", action="store_true")
    a = ap.parse_args()
    repo = Path(subprocess.run(["git", "-C", a.repo, "rev-parse", "--show-toplevel"],
                               capture_output=True, text=True).stdout.strip() or a.repo).resolve()
    day = dt.date.fromisoformat(a.date) if a.date else (dt.datetime.now() - dt.timedelta(hours=4)).date()
    cfg_path = repo / ".buildinpublic" / "config.json"
    project = json.loads(cfg_path.read_text()) if cfg_path.exists() else {}

    if a.test:
        cfg = email_settings()
        if not cfg:
            sys.exit(f"No email settings yet: create {CONFIG_DIR / 'email.json'} (see the top of notify.py).")
        msg = compose(cfg, repo, day, "test email",
                      "This is a test from Build In Public. Your daily gist will arrive like this.")
        print(msg) if a.dry_run else (send(cfg, msg), print(f"Test email sent to {cfg['to']}."))
        return

    headline, body = build_gist(repo, day)
    notify = project.get("notify", True)
    if notify not in (False, "off") and not a.no_desktop and not a.dry_run:
        desktop("Build In Public", f"{day}: {headline}")

    cfg = email_settings() if project.get("email", True) not in (False, "off") else None
    if not cfg:
        print(f"Gist ready ({headline}). Email not set up; see notify.py --help.")
        return
    msg = compose(cfg, repo, day, headline, body)
    if a.dry_run:
        print(msg)
        return
    send(cfg, msg)
    print(f"Gist emailed to {cfg['to']}.")


if __name__ == "__main__":
    main()
