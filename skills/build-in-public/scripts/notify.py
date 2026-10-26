#!/usr/bin/env python3
"""Build In Public: send today's gist as a desktop notification, and optionally an email.

The gist is the top of brief.md: the day in one line, what you shipped, and the list of
suggested posts to choose from, plus a link to your approved posts on GitHub when they're
shared with commits. If no brief was written (no headless agent), it falls back to what
the digest found. The full brief.md is attached to the email.

Email is optional and only needs your address, in ~/.config/buildinpublic/email.json:
  {"to": "you@example.com"}
It's sent through a mail app you're already signed in to, so no password is involved:
  - macOS: Apple Mail, from your default account (Mail needs at least one account; run
    notify.py --test once so macOS can ask you to allow it)
  - Linux: the system sendmail (msmtp, ssmtp, postfix...) if one is set up
Optional extras: "method": "mail-app" | "sendmail" | "smtp", "from": "...", and for SMTP only:
"smtp_host", "smtp_port", "smtp_user", "security" ("starttls" or "ssl"). SMTP is the one
method that needs a password, read from BIP_SMTP_PASSWORD, the macOS Keychain
(service buildinpublic-smtp) or ~/.config/buildinpublic/smtp-password (chmod 600).

Usage: python3 notify.py [--repo PATH] [--date YYYY-MM-DD] [--dry-run] [--test] [--no-desktop]
"""
import argparse, datetime as dt, json, os, platform, re, shutil, smtplib, ssl, stat, subprocess, sys
from email.message import EmailMessage
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "buildinpublic"
GIST_SECTIONS = ("Today in one line", "What you shipped", "Post ideas", "Suggested posts")
SENDMAIL_PATHS = ("/usr/sbin/sendmail", "/usr/lib/sendmail")

MAIL_APP_SCRIPT = '''on run argv
  set {theTo, theSubject, theBody, theFile} to argv
  tell application "Mail"
    set m to make new outgoing message with properties {subject:theSubject, content:theBody & return & return, visible:false}
    tell m
      make new to recipient at end of to recipients with properties {address:theTo}
      if theFile is not "" then
        tell content to make new attachment with properties {file name:(POSIX file theFile)} at after last paragraph
      end if
    end tell
    send m
  end tell
end run'''


def section(text, name):
    m = re.search(rf"^##\s+{re.escape(name)}\s*\n(.*?)(?=^##\s|\Z)", text, re.S | re.M)
    return m.group(1).strip() if m else ""


def posts_url(repo):
    """GitHub link to the shared posts page, if this repo shares posts and has a GitHub remote."""
    if not (repo / ".buildinpublic" / "posts" / "README.md").exists():
        return ""
    remote = subprocess.run(["git", "-C", str(repo), "remote", "get-url", "origin"],
                            capture_output=True, text=True).stdout.strip()
    m = re.search(r"github\.com[:/]([^/]+/[^/]+?)(?:\.git)?$", remote)
    if not m:
        return ""
    branch = subprocess.run(["git", "-C", str(repo), "rev-parse", "--abbrev-ref", "HEAD"],
                            capture_output=True, text=True).stdout.strip() or "main"
    return f"https://github.com/{m.group(1)}/blob/{branch}/.buildinpublic/posts/README.md"


def build_gist(repo, day):
    """Return (headline, body) for today's gist."""
    out = repo / ".buildinpublic" / "daily" / str(day)
    brief = out / "brief.md"
    link = posts_url(repo)
    footer = f"\n\nYour approved posts and images: {link}" if link else ""
    if brief.exists():
        text = brief.read_text()
        parts = [(n, section(text, n)) for n in GIST_SECTIONS]
        parts = [(n, b) for n, b in parts if b]
        headline = next((b.splitlines()[0] for n, b in parts if n == "Today in one line"), "") or "Your brief is ready"
        body = "\n\n".join(f"{n.upper()}\n{b}" for n, b in parts) or text[:3000]
        body += ("\n\nPick a post: open your agent in this project and say \"review my posts\""
                 " (or \"write post 2\"). Nothing is posted for you.") + footer
        return headline, body

    digest = out / "digest.md"
    if not digest.exists():
        return "Quiet day", "No activity was found for this day." + footer
    text = digest.read_text()
    found = re.search(r"^Sessions found: (.*)$", text, re.M)
    commits = re.findall(r"^- \d\d:\d\d [0-9a-f]{7,} (.+)$", section(text, "Git commits"), re.M)
    logged = re.findall(r"^### [\d:]+ - (.+?)\s+\(agent", text, re.M)
    lines = [f"Sessions: {found.group(1)}" if found else ""]
    lines += [f"- {t}" for t in logged] or [f"- {c}" for c in commits]
    body = "\n".join(l for l in lines if l)
    body += ("\n\nNo brief was written yet (no headless agent is set up). Open your agent in this project "
             "and say \"build in public brief\" to get the story and the list of posts.") + footer
    return (logged or commits or ["Your digest is ready"])[0], body


def desktop(title, message):
    message = message.replace('"', "'")
    if platform.system() == "Darwin" and shutil.which("osascript"):
        subprocess.run(["osascript", "-e", f'display notification "{message}" with title "{title}"'],
                       capture_output=True)
    elif shutil.which("notify-send"):
        subprocess.run(["notify-send", title, message], capture_output=True)


# ---------- email (optional) ----------

def email_settings():
    p = CONFIG_DIR / "email.json"
    if not p.exists():
        return None
    try:
        cfg = json.loads(p.read_text())
    except ValueError as e:
        sys.exit(f"{p} is not valid JSON: {e}")
    if not cfg.get("to"):
        sys.exit(f"{p} needs your address: {{\"to\": \"you@example.com\"}}")
    if cfg.get("method") == "smtp" and not (cfg.get("smtp_host") and cfg.get("smtp_user")):
        sys.exit(f"{p}: the smtp method also needs smtp_host and smtp_user")
    return cfg


def sendmail_path():
    return shutil.which("sendmail") or next((p for p in SENDMAIL_PATHS if Path(p).exists()), None)


def method(cfg, system=None):
    """How the email will be sent. Only "smtp" needs a password."""
    if cfg.get("method"):
        return cfg["method"]
    if cfg.get("smtp_host"):
        return "smtp"
    system = system or platform.system()
    if system == "Darwin":
        return "mail-app"
    if sendmail_path():
        return "sendmail"
    return None


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
    sys.exit("The smtp method needs a password. Add it to the Keychain with:\n"
             f"  security add-generic-password -s buildinpublic-smtp -a {user} -w\n"
             "or remove smtp_host/method from email.json to send through your mail app instead.")


def compose(cfg, repo, day, headline, body):
    msg = EmailMessage()
    msg["Subject"] = f"Build In Public · {repo.name} · {day}: {headline}"[:180]
    msg["From"] = cfg.get("from") or cfg.get("smtp_user") or cfg["to"]
    msg["To"] = cfg["to"]
    msg.set_content(body)
    brief = repo / ".buildinpublic" / "daily" / str(day) / "brief.md"
    if brief.exists():
        msg.add_attachment(brief.read_bytes(), maintype="text", subtype="markdown", filename=f"brief-{day}.md")
    return msg


def attachment_path(repo, day):
    brief = repo / ".buildinpublic" / "daily" / str(day) / "brief.md"
    return str(brief) if brief.exists() else ""


def send(cfg, msg, attachment=""):
    how = method(cfg)
    if how == "mail-app":
        r = subprocess.run(["osascript", "-", cfg["to"], msg["Subject"], msg.get_body(("plain",)).get_content(),
                            attachment], input=MAIL_APP_SCRIPT, capture_output=True, text=True)
        if r.returncode:
            sys.exit("Apple Mail couldn't send it. Check that Mail has an account set up, and allow "
                     f"access when macOS asks (run notify.py --test from a terminal once).\n{r.stderr.strip()}")
    elif how == "sendmail":
        path = sendmail_path()
        if not path:
            sys.exit("No sendmail found. Install and configure one (for example msmtp), or skip email.")
        r = subprocess.run([path, "-t", "-oi"], input=msg.as_bytes(), capture_output=True)
        if r.returncode:
            sys.exit(f"sendmail failed: {r.stderr.decode(errors='ignore').strip()}")
    elif how == "smtp":
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
    else:
        sys.exit("No way to send email on this machine: no Apple Mail and no sendmail. "
                 "Set up a sendmail (for example msmtp), or skip email; the desktop notification still works.")
    return how


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    ap.add_argument("--date")
    ap.add_argument("--dry-run", action="store_true", help="print the email instead of sending it")
    ap.add_argument("--test", action="store_true", help="send a short test email to check it works")
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
            sys.exit(f"Email is optional and not set up. To add it: echo '{{\"to\": \"you@example.com\"}}' > {CONFIG_DIR / 'email.json'}")
        msg = compose(cfg, repo, day, "test email",
                      "This is a test from Build In Public. Your daily gist will arrive like this.")
        if a.dry_run:
            print(f"(would send via {method(cfg)})\n{msg}")
            return
        how = send(cfg, msg)
        print(f"Test email sent to {cfg['to']} via {how}.")
        return

    headline, body = build_gist(repo, day)
    notify = project.get("notify", True)
    if notify not in (False, "off") and not a.no_desktop and not a.dry_run:
        desktop("Build In Public", f"{day}: {headline}")

    cfg = email_settings() if project.get("email", True) not in (False, "off") else None
    if not cfg:
        print(f"Gist ready ({headline}). Email is optional and not set up.")
        return
    msg = compose(cfg, repo, day, headline, body)
    if a.dry_run:
        print(f"(would send via {method(cfg)})\n{msg}")
        return
    how = send(cfg, msg, attachment_path(repo, day))
    print(f"Gist emailed to {cfg['to']} via {how}.")


if __name__ == "__main__":
    main()
