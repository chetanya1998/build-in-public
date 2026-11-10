#!/usr/bin/env python3
"""Build Your Product in Public: send today's gist as a desktop notification, and optionally an email.

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
import argparse, base64, datetime as dt, html, json, os, platform, re, shutil, smtplib, ssl, stat, subprocess, sys, urllib.parse
from email.message import EmailMessage
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import brieflib  # noqa: E402

CONFIG_DIR = Path.home() / ".config" / "buildinpublic"
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


# A page with a Copy button for one post. The post travels in the link's #fragment, which the
# browser never sends to the server. Set "copy_page" in config.json to your own page, or "" for none.
COPY_PAGE = "https://chetanya1998.github.io/build-in-public/copy.html"
MAX_LINK = 8000  # longer links break in some mail apps; the post is still in the email to select


def copy_link(page, post):
    if not page or not post["fields"].get("Post"):
        return ""
    data = base64.urlsafe_b64encode(post["fields"]["Post"].encode()).decode().rstrip("=")
    url = f"{page}#p={urllib.parse.quote(post['platform'] or '')}&t={data}"
    return url if len(url) <= MAX_LINK else ""


def project_config(repo):
    try:
        return json.loads((repo / ".buildinpublic" / "config.json").read_text())
    except (OSError, ValueError):
        return {}


PICK = ('In your agent, say "show post 2" or "write post 2 for LinkedIn". In a terminal: '
        'python3 <skill>/scripts/posts.py --today. Nothing is posted for you.')


def gist(repo, day):
    """The day's gist as plain pieces: headline, shipped lines, suggested posts, notes."""
    out = repo / ".buildinpublic" / "daily" / str(day)
    brief = out / "brief.md"
    g = {"repo": repo.name, "day": day, "link": posts_url(repo), "shipped": [], "posts": [], "notes": []}
    if brief.exists():
        text = brief.read_text()
        today = brieflib.section(text, "Today in one line")
        g["headline"] = brieflib.to_text(today.splitlines()[0]).strip() if today else "Your brief is ready"
        g["shipped"] = brieflib.block_lines(brieflib.section(text, "What you shipped"))
        g["posts"] = brieflib.suggested_posts(text) or []
        cfg = project_config(repo)
        page = cfg.get("copy_page", COPY_PAGE)
        for p in g["posts"]:
            if p["fields"].get("Post"):
                p["stats"] = brieflib.post_stats(p["platform"], p["fields"]["Post"], cfg.get("post_limits"))
                p["copy"] = copy_link(page, p)
        if not g["posts"] and brieflib.section(text, "Post ideas"):  # very old briefs
            g["shipped"] += brieflib.block_lines(brieflib.section(text, "Post ideas"))
        g["pick"] = PICK
        g["attached"] = True
        check = out / "brief-check.json"
        if check.exists():
            try:
                result = json.loads(check.read_text())
                g["dead_links"] = result.get("dead_links", [])
                g["unchecked_links"] = result.get("unchecked_links", [])
            except ValueError:
                pass
        return g
    digest = out / "digest.md"
    if not digest.exists():
        g.update(headline="Quiet day", notes=["No activity was found for this day."])
        return g
    text = digest.read_text()
    found = re.search(r"^Sessions found: (.*)$", text, re.M)
    commits = re.findall(r"^- \d\d:\d\d [0-9a-f]{7,} (.+)$", section(text, "Git commits"), re.M)
    logged = re.findall(r"^### [\d:]+ - (.+?)\s+\(agent", text, re.M)
    g["headline"] = (logged or commits or ["Your digest is ready"])[0]
    g["shipped"] = [("li", t) for t in (logged or commits)]
    g["notes"] = ([f"Sessions: {found.group(1)}"] if found else []) + [
        'No brief was written yet (no headless agent is set up). Open your agent in this project and say '
        '"build in public brief" to get the story and the list of posts.']
    return g


def length_line(p):
    """'1,234 / 3,000 characters · 210 / 300 words', with ✓ or OVER."""
    s = p.get("stats")
    if not s:
        return ""
    lim = s["limit"]
    parts = [f"{s['chars']:,}" + (f" / {lim['chars']:,}" if lim.get("chars") else "") + " characters"
             + (" a post" if s["key"] == "x" and "thread" in p["platform"].lower() else "")]
    if lim.get("words"):
        parts.append(f"{s['words']:,} / {lim['words']:,} words")
    return " · ".join(parts) + (" · OVER THE LIMIT" if s["errors"] else (" ✓" if lim else ""))


def screenshot_line(f):
    shot = brieflib.to_text(f.get("Screenshot") or f.get("Capture") or "").strip()
    return f"Screenshot: {shot}" if shot and shot.lower().strip('".') not in ("none", "no screenshot") else "No screenshot"


def render_text(g):
    """Plain text with no Markdown symbols, for every mail app (Apple Mail sends only this)."""
    L = []
    if g.get("dead_links"):
        L += [f"CHECK BEFORE POSTING: {len(g['dead_links'])} link(s) in this brief don't load:"]
        L += [f"  {u}" for u in g["dead_links"]] + [""]
    if g.get("unchecked_links"):
        L += [f"OPEN BEFORE POSTING: {len(g['unchecked_links'])} link(s) couldn't be checked:"]
        L += [f"  {u}" for u in g["unchecked_links"]] + [""]
    L += ["TODAY", g["headline"], ""]
    if g["shipped"]:
        L.append("WHAT YOU SHIPPED")
        L += [("- " if kind == "li" and not re.match(r"^\d+[.)]", t) else "") + brieflib.to_text(t) for kind, t in g["shipped"]]
        L.append("")
    if g["posts"]:
        L += ["SUGGESTED POSTS", ""]
        for p in g["posts"]:
            f = p["fields"]
            L.append(" · ".join(x for x in (str(p["n"]), p["platform"], length_line(p)) if x))
            L.append(p["title"])
            if f.get("Post"):
                L += ["", "----- copy from here -----", f["Post"], "----- to here -----"]
                L += [f"  ! {e}" for e in p["stats"]["errors"]]
                if p.get("copy"):
                    L.append(f"Copy it in one click: {p['copy']}")
            elif f.get("Hook"):  # older briefs
                L.append(f"Hook: {brieflib.to_text(f['Hook'])}")
            L.append(screenshot_line(f))
            details = [n for n in brieflib.DETAIL_FIELDS if f.get(n) and not (n == "Hook" and not f.get("Post"))]
            if details:
                L += ["", "How this post was made"]
                L += [f"   {n}: {brieflib.to_text(f[n])}" for n in details]
            L += ["", ""]
    L += g["notes"] + ([""] if g["notes"] else [])
    if g.get("pick"):
        L += ["PICK ONE", g["pick"]]
    if g["link"]:
        L.append(f"Your approved posts and images: {g['link']}")
    if g.get("attached"):
        L += ["", "The full brief is attached."]
    return "\n".join(L).strip() + "\n"


def render_html(g):
    """The same gist as a simple HTML email (inline styles, as mail apps need)."""
    e = html.escape
    H2 = 'style="font:600 12px/1 ui-monospace,Menlo,monospace;letter-spacing:.08em;text-transform:uppercase;color:#5a616d;margin:26px 0 10px"'
    out = ['<div style="font:15px/1.55 -apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif;color:#14161a;max-width:640px;margin:0 auto">',
           f'<p {H2.replace("26px", "0")}>Your daily gist · {e(g["repo"])} · {g["day"]:%d %b %Y}</p>',
           f'<h1 style="font-size:22px;line-height:1.3;margin:0 0 6px">{e(g["headline"])}</h1>']
    if g.get("unchecked_links"):
        out.insert(1, '<div style="margin:0 0 16px;padding:10px 14px;border-radius:10px;background:#f4f6fb;border:1px solid #e2e5ea">'
                      f'<strong>Open before posting:</strong> {len(g["unchecked_links"])} link(s) couldn\'t be checked:'
                      + "".join(f'<br><span style="font-size:13px;word-break:break-all">{e(u)}</span>' for u in g["unchecked_links"]) + "</div>")
    if g.get("dead_links"):
        out.insert(1, '<div style="margin:0 0 16px;padding:10px 14px;border-radius:10px;background:#fff4e5;border:1px solid #f2c97d">'
                      f'<strong>Check before posting:</strong> {len(g["dead_links"])} link(s) in this brief don\'t load:'
                      + "".join(f'<br><span style="font-size:13px;word-break:break-all">{e(u)}</span>' for u in g["dead_links"]) + "</div>")
    if g["shipped"]:
        out.append(f"<h2 {H2}>What you shipped</h2>")
        items = [t for k, t in g["shipped"] if k == "li"]
        if items:
            out.append('<ul style="margin:0;padding-left:20px">' + "".join(f'<li style="margin:3px 0">{brieflib.to_html(t)}</li>' for t in items) + "</ul>")
        out += [f'<p style="margin:6px 0">{brieflib.to_html(t)}</p>' for k, t in g["shipped"] if k != "li"]
    if g["posts"]:
        out.append(f"<h2 {H2}>Suggested posts</h2>")
        for p in g["posts"]:
            f = p["fields"]
            out.append('<div style="border:1px solid #e2e5ea;border-radius:12px;padding:14px 16px;margin:0 0 12px">')
            over = bool(p.get("stats") and p["stats"]["errors"])
            out.append(f'<div style="font:600 12px/1.4 ui-monospace,Menlo,monospace;color:#2c4bd4;letter-spacing:.04em">{p["n"]}'
                       + (f' · {e(p["platform"])}' if p["platform"] else "")
                       + (f' <span style="color:{"#b42318" if over else "#5a616d"};font-weight:500">· {e(length_line(p))}</span>' if p.get("stats") else "")
                       + "</div>")
            out.append(f'<div style="font-weight:600;font-size:16px;margin:6px 0 10px">{e(p["title"])}</div>')
            if f.get("Post"):
                out.append('<div style="margin:0 0 10px;padding:14px 16px;background:#f4f6fb;border:1px solid #e2e5ea;border-radius:10px;'
                           f'white-space:pre-wrap;word-wrap:break-word;font-size:15px;line-height:1.55">{e(f["Post"])}</div>')
                out += [f'<p style="margin:4px 0;color:#b42318;font-size:14px">⚠ {e(x)}</p>' for x in p["stats"]["errors"]]
                if p.get("copy"):
                    out.append(f'<p style="margin:0 0 10px"><a href="{e(p["copy"], quote=True)}" style="display:inline-block;padding:8px 14px;'
                               'border-radius:999px;background:#14161a;color:#ffffff;text-decoration:none;font-weight:600;font-size:14px">Copy post</a>'
                               '<span style="color:#5a616d;font-size:13px">&nbsp; or select the text above</span></p>')
            elif f.get("Hook"):  # older briefs
                out.append('<div style="margin:0 0 10px;padding:9px 12px;border-left:3px solid #2c4bd4;background:#f4f6fb;'
                           f'border-radius:0 8px 8px 0">{brieflib.to_html(f["Hook"])}</div>')
            out.append(f'<p style="margin:0 0 10px;font-size:14px">{"📎 " if screenshot_line(f) != "No screenshot" else ""}{brieflib.to_html(screenshot_line(f))}</p>')
            details = [n for n in brieflib.DETAIL_FIELDS if f.get(n) and n != "Screenshot" and not (n == "Hook" and not f.get("Post"))]
            if details:
                out.append('<div style="border-top:1px dashed #e2e5ea;padding-top:8px;color:#5a616d;font-size:13.5px">'
                           '<div style="font:600 11px/1.6 ui-monospace,Menlo,monospace;letter-spacing:.06em;text-transform:uppercase">How this post was made</div>'
                           + "".join(f'<p style="margin:4px 0"><strong style="color:#14161a">{n}:</strong> {brieflib.to_html(f[n])}</p>' for n in details)
                           + "</div>")
            out.append("</div>")
    out += [f'<p style="margin:12px 0">{e(n)}</p>' for n in g["notes"]]
    if g.get("pick"):
        out.append(f'<p style="margin:18px 0 6px;padding:12px 14px;background:#f4f6fb;border-radius:10px">{e(g["pick"])}</p>')
    if g["link"]:
        out.append(f'<p style="margin:8px 0">Your approved posts and images: <a href="{e(g["link"], quote=True)}" style="color:#2c4bd4">open on GitHub</a></p>')
    if g.get("attached"):
        out.append('<p style="margin:16px 0 0;color:#5a616d;font-size:13px">The full brief is attached.</p>')
    out.append("</div>")
    return "\n".join(out)


def subject(repo, day, headline):
    """Short enough to read in an inbox: brand · project · date: first words of the headline."""
    h = headline.strip().rstrip(".")
    if len(h) > 64:
        h = h[:64].rsplit(" ", 1)[0].rstrip(",;:—-") + "…"
    return f"Build Your Product in Public · {repo.name} · {day:%d %b}: {h}"


def build_gist(repo, day):
    """Return (headline, plain-text body) for the day's gist."""
    g = gist(repo, day)
    return g["headline"], render_text(g)


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


def compose(cfg, repo, day, headline, body, html_body=None):
    msg = EmailMessage()
    msg["Subject"] = subject(repo, day, headline)
    msg["From"] = cfg.get("from") or cfg.get("smtp_user") or cfg["to"]
    msg["To"] = cfg["to"]
    msg.set_content(body)
    if html_body:
        msg.add_alternative(html_body, subtype="html")
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
                      "This is a test from Build Your Product in Public. Your daily gist will arrive like this.")
        if a.dry_run:
            print(f"(would send via {method(cfg)})\n{msg}")
            return
        how = send(cfg, msg)
        print(f"Test email sent to {cfg['to']} via {how}.")
        return

    g = gist(repo, day)
    headline, body = g["headline"], render_text(g)
    notify = project.get("notify", True)
    if notify not in (False, "off") and not a.no_desktop and not a.dry_run:
        desktop("Build Your Product in Public", f"{day}: {headline}")

    cfg = email_settings() if project.get("email", True) not in (False, "off") else None
    if not cfg:
        print(f"Gist ready ({headline}). Email is optional and not set up.")
        return
    msg = compose(cfg, repo, day, headline, body, render_html(g))
    if a.dry_run:
        print(f"(would send via {method(cfg)})\n{msg}")
        return
    how = send(cfg, msg, attachment_path(repo, day))
    print(f"Gist emailed to {cfg['to']} via {how}.")


if __name__ == "__main__":
    main()
