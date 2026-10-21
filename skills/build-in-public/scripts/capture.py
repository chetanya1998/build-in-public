#!/usr/bin/env python3
"""Build In Public: capture a moment for today's story, only with the user's approval.

Captures go to .buildinpublic/daily/<date>/captures/ and are listed in captures.json.
The daily brief only uses approved captures.

  terminal   run a command (or read saved output) and keep its output as text plus a
             terminal-window image for posting
  browser    screenshot a page of your running app (desktop, optionally mobile)
  candidates list screenshots your agents took today (Playwright MCP, test reports,
             Antigravity) that are waiting for a yes or no
  approve    keep candidates for the story      reject   never offer them again
  list       show today's approved captures

Nothing is captured without approval: on a terminal you're asked y/N; an agent passes
--approved only after you said yes in chat. Output is redacted like the digest.
Images need Playwright: pip install playwright && playwright install chromium

Usage:
  capture.py terminal --cmd "npm test" [--title T] [--note N] [--lines 40] [--approved]
  capture.py terminal --file out.txt --title "npm test" [--approved]
  capture.py browser [--url URL] [--mobile] [--full-page] [--note N] [--approved]
  capture.py candidates | list
  capture.py approve ID... [--note N] [--approved]
  capture.py reject ID...
Common: [--repo PATH] [--date YYYY-MM-DD]
"""
import argparse, datetime as dt, hashlib, html, json, os, re, shutil, subprocess, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import collect  # noqa: E402

ANSI_SGR = re.compile(r"\x1b\[([0-9;]*)m")
ANSI_OTHER = re.compile(r"\x1b\[[0-9;?]*[A-Za-ln-z]|\x1b\][^\x07]*\x07|\r(?!\n)")
COLORS = {30: "#5c6370", 31: "#ef596f", 32: "#89ca78", 33: "#e5c07b", 34: "#61afef", 35: "#d55fde",
          36: "#2bbac5", 37: "#d7dae0", 90: "#7f848e", 91: "#ff7b86", 92: "#a5e075", 93: "#f0d58a",
          94: "#7cc1ff", 95: "#e48af0", 96: "#5fd4de", 97: "#ffffff"}


class NeedsApproval(SystemExit):
    pass


# ---------- shared ----------

def resolve(a):
    repo = Path(subprocess.run(["git", "-C", a.repo, "rev-parse", "--show-toplevel"],
                               capture_output=True, text=True).stdout.strip() or a.repo).resolve()
    day = dt.date.fromisoformat(a.date) if a.date else (dt.datetime.now() - dt.timedelta(hours=4)).date()
    return repo, day


def config(repo):
    p = repo / ".buildinpublic" / "config.json"
    try:
        return json.loads(p.read_text()) if p.exists() else {}
    except ValueError:
        return {}


def out_dir(repo, day):
    d = repo / ".buildinpublic" / "daily" / str(day) / "captures"
    d.mkdir(parents=True, exist_ok=True)
    return d


def load_manifest(repo, day):
    p = out_dir(repo, day) / "captures.json"
    if p.exists():
        try:
            return json.loads(p.read_text())
        except ValueError:
            pass
    return {"captures": [], "rejected": []}


def save_manifest(repo, day, m):
    (out_dir(repo, day) / "captures.json").write_text(json.dumps(m, indent=2) + "\n")


def short_id(*parts):
    return hashlib.sha1("|".join(map(str, parts)).encode()).hexdigest()[:6]


def approve_or_stop(question, approved, repo):
    """Every capture goes through here. No yes, no capture."""
    if config(repo).get("capture") == "off":
        raise NeedsApproval("Capturing is turned off in .buildinpublic/config.json (\"capture\": \"off\").")
    if approved:
        return
    if sys.stdin.isatty():
        if input(f"{question} [y/N] ").strip().lower() in ("y", "yes"):
            return
        raise NeedsApproval("Not captured.")
    raise NeedsApproval(f"Needs the user's approval: ask them \"{question}\", and rerun with --approved only if they say yes.")


def slug(text, n=40):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:n] or "capture"


# ---------- terminal ----------

def ansi_to_html(text):
    """Escape text and turn basic ANSI colours (SGR) into spans."""
    out, open_span, pos = [], False, 0
    fg, bold, dim = None, False, False
    for m in ANSI_SGR.finditer(text):
        out.append(html.escape(text[pos:m.start()]))
        pos = m.end()
        for code in [int(c) for c in m.group(1).split(";") if c.isdigit()] or [0]:
            if code == 0:
                fg, bold, dim = None, False, False
            elif code == 1:
                bold = True
            elif code == 2:
                dim = True
            elif code in (22,):
                bold = dim = False
            elif code == 39:
                fg = None
            elif code in COLORS:
                fg = COLORS[code]
        if open_span:
            out.append("</span>")
            open_span = False
        style = ";".join(s for s in (f"color:{fg}" if fg else "", "font-weight:700" if bold else "",
                                     "opacity:.6" if dim else "") if s)
        if style:
            out.append(f'<span style="{style}">')
            open_span = True
    out.append(html.escape(text[pos:]))
    if open_span:
        out.append("</span>")
    return "".join(out)


def terminal_html(title, body_ansi):
    return f"""<!doctype html><meta charset="utf-8"><style>
body{{margin:0;padding:32px;background:#1f2430;display:inline-block}}
.win{{background:#282c34;border-radius:12px;box-shadow:0 20px 50px rgba(0,0,0,.45);min-width:640px;max-width:1100px;overflow:hidden}}
.bar{{display:flex;align-items:center;gap:8px;padding:12px 16px;background:#21252b}}
.dot{{width:12px;height:12px;border-radius:50%}}
.t{{flex:1;text-align:center;color:#9da5b4;font:13px -apple-system,Segoe UI,sans-serif;margin-right:52px}}
pre{{margin:0;padding:18px 22px 22px;color:#d7dae0;font:14px/1.5 "SF Mono",Menlo,Consolas,"DejaVu Sans Mono",monospace;white-space:pre-wrap;word-break:break-word}}
.p{{color:#89ca78}}
</style><div class="win"><div class="bar"><span class="dot" style="background:#ff5f57"></span><span class="dot" style="background:#febc2e"></span><span class="dot" style="background:#28c840"></span><span class="t">{html.escape(title)}</span></div><pre><span class="p">$</span> {html.escape(title)}
{ansi_to_html(body_ansi)}</pre></div>"""


def render_png(page_html, target, selector="body"):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return "Playwright not installed, so no image was made (text saved): pip install playwright && playwright install chromium"
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(device_scale_factor=2)
            page.set_content(page_html)
            page.locator(selector).screenshot(path=str(target))
            browser.close()
    except Exception as e:  # browser missing, sandbox, etc.
        return f"Couldn't render the image ({e}); text saved."
    return None


def cmd_terminal(a, repo, day):
    if not a.cmd and not a.file:
        sys.exit("terminal needs --cmd \"...\" or --file PATH")
    title = a.title or a.cmd or Path(a.file).name
    approve_or_stop(f"Capture the terminal output of `{title}` for today's story?", a.approved, repo)

    exit_code = None
    if a.cmd:
        try:
            r = subprocess.run(a.cmd, shell=True, cwd=repo, capture_output=True, text=True, timeout=a.timeout,
                               env=dict(os.environ, FORCE_COLOR="1", CLICOLOR_FORCE="1"))
            raw, exit_code = r.stdout + r.stderr, r.returncode
        except subprocess.TimeoutExpired as e:
            raw = (e.stdout or b"").decode(errors="ignore") if isinstance(e.stdout, bytes) else (e.stdout or "")
            raw += f"\n[stopped after {a.timeout}s]"
    else:
        raw = Path(a.file).read_text(errors="ignore")

    extra = collect.read_offlimits(repo)
    raw = ANSI_OTHER.sub("", raw)
    shown = "\n".join(collect.redact(raw, extra).rstrip("\n").splitlines()[-a.lines:])
    plain = ANSI_SGR.sub("", collect.redact(raw, extra))

    cid = short_id(title, time.time())
    d = out_dir(repo, day)
    base = f"{cid}-terminal-{slug(title)}"
    (d / f"{base}.txt").write_text(f"$ {title}\n{plain}")
    files = {"text": f"{base}.txt"}
    problem = render_png(terminal_html(title, shown), d / f"{base}.png")
    if not problem:
        files["image"] = f"{base}.png"

    m = load_manifest(repo, day)
    m["captures"].append({"id": cid, "kind": "terminal", "title": title, "note": a.note or "",
                          "source": a.cmd or a.file, "exit_code": exit_code, "files": files,
                          "time": dt.datetime.now().strftime("%H:%M")})
    save_manifest(repo, day, m)
    print(f"Captured {cid}: " + ", ".join(str(d / f) for f in files.values()))
    if problem:
        print(problem)


# ---------- browser ----------

def cmd_browser(a, repo, day):
    cfg = config(repo)
    url = a.url or cfg.get("app_url") or (cfg.get("snapshot_urls") or [None])[0]
    if not url:
        sys.exit("No URL: pass --url, or set \"app_url\" in .buildinpublic/config.json")
    approve_or_stop(f"Capture a screenshot of {url} for today's story?", a.approved, repo)
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.exit("Playwright not installed: pip install playwright && playwright install chromium")

    cid = short_id(url, time.time())
    d = out_dir(repo, day)
    views = {"desktop": {"width": 1440, "height": 900}}
    if a.mobile:
        views["mobile"] = {"width": 390, "height": 844}
    files = {}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for name, vp in views.items():
            page = browser.new_page(viewport=vp, device_scale_factor=2)
            try:
                page.goto(url, wait_until="networkidle", timeout=20000)
                f = f"{cid}-browser-{slug(url.split('//')[-1])}-{name}.png"
                page.screenshot(path=str(d / f), full_page=a.full_page)
                files[name] = f
            except Exception as e:
                print(f"skip {name}: {e}", file=sys.stderr)
            finally:
                page.close()
        browser.close()
    if not files:
        sys.exit(f"Couldn't load {url}. Is the app running?")
    m = load_manifest(repo, day)
    m["captures"].append({"id": cid, "kind": "browser", "title": a.title or url, "note": a.note or "",
                          "source": url, "files": files, "time": dt.datetime.now().strftime("%H:%M")})
    save_manifest(repo, day, m)
    print(f"Captured {cid}: " + ", ".join(str(d / f) for f in files.values()))


# ---------- agent screenshots awaiting approval ----------

def pending(repo, day):
    sessions = collect.antigravity_sessions(repo, day)
    found = collect.find_candidates(repo, day, sessions)
    return [(short_id(p), p) for p in collect.undecided(found, load_manifest(repo, day))]


def cmd_candidates(a, repo, day):
    rows = pending(repo, day)
    if not rows:
        print("No new screenshots from your agents today.")
        return
    print("Screenshots your agents took today, waiting for a yes or no:")
    for cid, p in rows:
        print(f"  {cid}  {p.relative_to(repo) if p.is_relative_to(repo) else p}")
    print("Keep:  capture.py approve ID...     Skip:  capture.py reject ID...")


def pick(repo, day, ids):
    rows = dict(pending(repo, day))
    unknown = [i for i in ids if i not in rows]
    if unknown:
        sys.exit(f"Unknown id(s): {', '.join(unknown)}. Run capture.py candidates.")
    return [(i, rows[i]) for i in ids]


def cmd_approve(a, repo, day):
    chosen = pick(repo, day, a.ids)
    names = ", ".join(p.name for _, p in chosen)
    approve_or_stop(f"Use {names} in today's story?", a.approved, repo)
    d, m = out_dir(repo, day), load_manifest(repo, day)
    for cid, p in chosen:
        f = f"{cid}-screenshot-{p.name}"
        shutil.copy2(p, d / f)
        m["captures"].append({"id": cid, "kind": "screenshot", "title": p.stem, "note": a.note or "",
                              "source": str(p), "files": {"image": f}, "time": dt.datetime.now().strftime("%H:%M")})
        print(f"Approved {cid}: {d / f}")
    save_manifest(repo, day, m)


def cmd_reject(a, repo, day):
    chosen = pick(repo, day, a.ids)
    m = load_manifest(repo, day)
    m["rejected"] += [str(p) for _, p in chosen]
    save_manifest(repo, day, m)
    print(f"Won't offer {len(chosen)} screenshot(s) again.")


def cmd_list(a, repo, day):
    caps = load_manifest(repo, day)["captures"]
    if not caps:
        print("No approved captures today.")
    for c in caps:
        print(f"  {c['id']}  {c['time']}  {c['kind']:<10} {c['title']}" + (f"  · {c['note']}" if c["note"] else ""))


def main():
    ap = argparse.ArgumentParser(description="Capture a moment for today's story, with approval.")
    ap.add_argument("--repo", default=".")
    ap.add_argument("--date")
    sub = ap.add_subparsers(dest="cmd_name", required=True)

    t = sub.add_parser("terminal")
    t.add_argument("--cmd")
    t.add_argument("--file")
    t.add_argument("--title")
    t.add_argument("--note")
    t.add_argument("--lines", type=int, default=40, help="last N lines in the image (text keeps all)")
    t.add_argument("--timeout", type=int, default=300)
    t.add_argument("--approved", action="store_true")

    b = sub.add_parser("browser")
    b.add_argument("--url")
    b.add_argument("--title")
    b.add_argument("--note")
    b.add_argument("--mobile", action="store_true")
    b.add_argument("--full-page", action="store_true")
    b.add_argument("--approved", action="store_true")

    sub.add_parser("candidates")
    sub.add_parser("list")
    ok = sub.add_parser("approve")
    ok.add_argument("ids", nargs="+")
    ok.add_argument("--note")
    ok.add_argument("--approved", action="store_true")
    no = sub.add_parser("reject")
    no.add_argument("ids", nargs="+")

    a = ap.parse_args()
    repo, day = resolve(a)
    {"terminal": cmd_terminal, "browser": cmd_browser, "candidates": cmd_candidates, "list": cmd_list,
     "approve": cmd_approve, "reject": cmd_reject}[a.cmd_name](a, repo, day)


if __name__ == "__main__":
    try:
        main()
    except NeedsApproval as e:
        print(e.code, file=sys.stderr)
        sys.exit(2)
