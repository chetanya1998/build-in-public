#!/usr/bin/env python3
"""Build Your Product in Public: capture a moment for today's story, only with the user's approval.

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


def render_png(page_html, target, selector="body", scale=2):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return "Playwright not installed, so no image was made (text saved): pip install playwright && playwright install chromium"
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1400, "height": 900}, device_scale_factor=scale)
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


# ---------- framing: screenshots that look good in a post ----------

BACKDROPS = {
    "ocean": "linear-gradient(135deg,#0f2027 0%,#203a43 50%,#2c5364 100%)",
    "dusk": "linear-gradient(135deg,#1f1c2c 0%,#6a3093 55%,#a044ff 100%)",
    "sunrise": "linear-gradient(135deg,#f6d365 0%,#fda085 100%)",
    "mint": "linear-gradient(135deg,#43e97b 0%,#38f9d7 100%)",
    "mono": "linear-gradient(135deg,#232526 0%,#414345 100%)",
}


def image_size(path):
    """(width, height) of a PNG or JPEG, read from its header, or None."""
    b = Path(path).read_bytes()[:64 * 1024]
    if b[:8] == b"\x89PNG\r\n\x1a\n":
        return int.from_bytes(b[16:20], "big"), int.from_bytes(b[20:24], "big")
    i = 2
    while b[:2] == b"\xff\xd8" and i + 9 < len(b):
        if b[i] != 0xFF:
            break
        marker, size = b[i + 1], int.from_bytes(b[i + 2:i + 4], "big")
        if marker in (0xC0, 0xC1, 0xC2):
            return int.from_bytes(b[i + 7:i + 9], "big"), int.from_bytes(b[i + 5:i + 7], "big")
        i += 2 + size
    return None


def frame_html(src, label="", backdrop="ocean"):
    """A browser window (or a phone, for tall images) on a gradient, around the screenshot."""
    import base64
    data = base64.b64encode(Path(src).read_bytes()).decode()
    mime = "image/png" if Path(src).suffix.lower() == ".png" else "image/jpeg"
    size = image_size(src)
    tall = bool(size) and size[1] > size[0] * 1.35
    img = f'<img src="data:{mime};base64,{data}" style="display:block;width:100%">'
    if tall:
        inner = (f'<div style="width:390px;border-radius:44px;padding:14px;background:#0b0b0c;'
                 f'box-shadow:0 30px 60px rgba(0,0,0,.45)"><div style="border-radius:32px;overflow:hidden">{img}</div></div>')
    else:
        dots = "".join(f'<span style="width:12px;height:12px;border-radius:50%;background:{c}"></span>'
                       for c in ("#ff5f57", "#febc2e", "#28c840"))
        bar = (f'<span style="margin-left:14px;flex:1;background:#fff;border-radius:8px;padding:6px 12px;'
               f'font:13px -apple-system,Segoe UI,sans-serif;color:#5f6368">{html.escape(label)}</span>' if label else "")
        width = min(1100, max(560, size[0] if size else 1100))  # never enlarge (it blurs)
        inner = (f'<div style="width:{width}px;border-radius:12px;overflow:hidden;background:#fff;'
                 f'box-shadow:0 30px 60px rgba(0,0,0,.4),0 0 0 1px rgba(0,0,0,.08)">'
                 f'<div style="display:flex;align-items:center;gap:8px;padding:12px 14px;background:#f1f3f4">{dots}{bar}</div>'
                 f'{img}</div>')
    return (f'<!doctype html><html><body style="margin:0"><div id="frame" style="display:inline-block;padding:64px;'
            f'background:{BACKDROPS.get(backdrop, BACKDROPS["ocean"])}">{inner}</div></body></html>')


def frame_png(src, dst, label="", backdrop="ocean"):
    """Write a framed copy of src to dst. Returns None, or why it couldn't (Playwright missing)."""
    return render_png(frame_html(src, label, backdrop), dst, selector="#frame", scale=1)


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
                raw = f"{cid}-browser-{slug(url.split('//')[-1])}-{name}-raw.png"
                page.screenshot(path=str(d / raw), full_page=a.full_page)
                framed = raw.replace("-raw.png", ".png")
                files[name] = raw if a.no_frame or frame_png(d / raw, d / framed, "" if name == "mobile" else url) else framed
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
        raw = f"{cid}-screenshot-raw{p.suffix.lower()}"
        shutil.copy2(p, d / raw)
        framed = f"{cid}-screenshot.png"
        problem = None if a.no_frame else frame_png(d / raw, d / framed, a.label or "")
        files = {"image": raw} if a.no_frame or problem else {"image": framed, "raw": raw}
        m["captures"].append({"id": cid, "kind": "screenshot", "title": a.note or p.stem, "note": a.note or "",
                              "source": str(p), "files": files, "time": dt.datetime.now().strftime("%H:%M")})
        print(f"Approved {cid}: {d / files['image']}" + (f"  ({problem})" if problem else ""))
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
    b.add_argument("--no-frame", action="store_true", help="keep the plain screenshot, without the window frame")
    b.add_argument("--approved", action="store_true")

    sub.add_parser("candidates")
    sub.add_parser("list")
    ok = sub.add_parser("approve")
    ok.add_argument("ids", nargs="+")
    ok.add_argument("--note")
    ok.add_argument("--label", help="text for the window's address bar, e.g. localhost:3000/billing")
    ok.add_argument("--no-frame", action="store_true", help="keep the plain screenshot, without the window frame")
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
