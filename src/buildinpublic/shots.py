"""Screenshots that look good enough to post, captured only with permission.

  code  a framed, syntax-coloured image of a code snippet
  url   your app at desktop + mobile size, framed in a browser window
  watch notices running localhost dev servers and agents testing in a browser,
        then ASKS before capturing (native dialog, or queued for your next agent
        session if there's no desktop). Nothing is captured without a yes.

Rendering uses Playwright (pip install playwright && playwright install chromium).
Without it, the framed HTML is saved so you can still open/print it.
"""
from __future__ import annotations

import base64
import datetime as dt
import html
import json
import re
import shutil
import socket
import subprocess
import urllib.request
from pathlib import Path

from . import journal, notify
from .core import app_home, load_config, os_name, read_json, save_state, slug, state, write_json

DEV_PORTS = set(range(3000, 3011)) | set(range(4000, 4011)) | set(range(5000, 5011)) | set(range(8000, 8011)) | \
    {1234, 4200, 4321, 5173, 5174, 5500, 6006, 8080, 8081, 8888, 9000, 19006, 24678}
DEV_PROCS = ("node", "bun", "deno", "python", "python3", "uvicorn", "gunicorn", "flask", "ruby", "rails",
             "php", "java", "go", "cargo", "dotnet", "vite", "next-server", "astro", "hugo", "jekyll")

# ---------------------------------------------------------------- playwright

def playwright_ok() -> bool:
    try:
        import playwright.sync_api  # noqa: F401
        return True
    except ImportError:
        return False


def _render(html_doc: str, out_png: Path, selector: str = "#frame", width: int = 1400) -> Path:
    out_png.parent.mkdir(parents=True, exist_ok=True)
    html_file = out_png.with_suffix(".html")
    html_file.write_text(html_doc, encoding="utf-8")
    if not playwright_ok():
        return html_file
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={"width": width, "height": 900}, device_scale_factor=2)
        page.set_content(html_doc, wait_until="load")
        page.locator(selector).screenshot(path=str(out_png), omit_background=False)
        b.close()
    html_file.unlink(missing_ok=True)
    return out_png

# ---------------------------------------------------------------- code images

KW = r"\b(def|class|return|if|elif|else|for|while|in|import|from|as|with|try|except|finally|raise|async|await|" \
     r"function|const|let|var|export|default|new|this|type|interface|extends|implements|public|private|static|" \
     r"fn|pub|impl|struct|enum|match|mut|use|package|func|go|defer|true|false|null|None|True|False|nil|yield|lambda)\b"


def _highlight(code: str, lang_hint: str) -> str:
    try:
        from pygments import highlight
        from pygments.formatters import HtmlFormatter
        from pygments.lexers import get_lexer_for_filename, guess_lexer
        try:
            lexer = get_lexer_for_filename(lang_hint, stripnl=False)
        except Exception:
            lexer = guess_lexer(code, stripnl=False)
        fmt = HtmlFormatter(nowrap=True, style="github-dark")
        return highlight(code, lexer, fmt), HtmlFormatter(style="github-dark").get_style_defs(".code")
    except Exception:
        pass
    tokens = re.compile(r"(?P<c>#[^\n]*|//[^\n]*|/\*[\s\S]*?\*/)|(?P<s>\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'|`[^`]*`)|"
                        r"(?P<k>" + KW + r")|(?P<n>\b\d+(?:\.\d+)?\b)|(?P<f>\b[A-Za-z_]\w*(?=\())")
    out, pos = [], 0
    for m in tokens.finditer(code):
        out.append(html.escape(code[pos:m.start()]))
        cls = m.lastgroup
        out.append(f'<span class="t{cls}">{html.escape(m.group(0))}</span>')
        pos = m.end()
    out.append(html.escape(code[pos:]))
    css = (".tc{color:#7d8590;font-style:italic}.ts{color:#a5d6ff}.tk{color:#ff7b72}"
           ".tn{color:#79c0ff}.tf{color:#d2a8ff}")
    return "".join(out), css


THEMES = {
    "dusk": "linear-gradient(135deg,#1f1c2c 0%,#6a3093 50%,#a044ff 100%)",
    "ocean": "linear-gradient(135deg,#0f2027 0%,#203a43 50%,#2c5364 100%)",
    "sunrise": "linear-gradient(135deg,#f6d365 0%,#fda085 100%)",
    "mint": "linear-gradient(135deg,#43e97b 0%,#38f9d7 100%)",
    "mono": "linear-gradient(135deg,#232526 0%,#414345 100%)",
}


def code_image(source: Path | str, out: Path, lines: str | None = None, title: str | None = None,
               theme: str = "dusk", caption: str = "") -> Path:
    src = Path(source)
    text = src.read_text(encoding="utf-8", errors="ignore") if src.exists() else str(source)
    all_lines = text.splitlines()
    start = 1
    if lines:
        a, _, b = lines.partition("-")
        start = max(1, int(a))
        end = int(b) if b else start + 30
        all_lines = all_lines[start - 1:end]
    else:
        all_lines = all_lines[:40]
    while all_lines and not all_lines[-1].strip():
        all_lines.pop()
    while all_lines and not all_lines[0].strip():
        all_lines.pop(0)
        start += 1
    snippet = "\n".join(l.replace("\t", "    ") for l in all_lines)
    body, css = _highlight(snippet, src.name if src.exists() else "x.py")
    nums = "\n".join(str(i) for i in range(start, start + len(all_lines)))
    doc = f"""<!doctype html><html><head><meta charset="utf-8"><style>
body{{margin:0;background:transparent;font-family:'JetBrains Mono','SF Mono',Menlo,Consolas,monospace}}
#frame{{display:inline-block;padding:56px;background:{THEMES.get(theme, THEMES['dusk'])}}}
.win{{background:#0d1117;border-radius:14px;overflow:hidden;box-shadow:0 30px 60px rgba(0,0,0,.45),0 0 0 1px rgba(255,255,255,.08);min-width:560px;max-width:1100px}}
.bar{{display:flex;align-items:center;gap:8px;padding:14px 16px;border-bottom:1px solid rgba(255,255,255,.06)}}
.dot{{width:12px;height:12px;border-radius:50%}}
.name{{margin-left:12px;color:#8b949e;font-size:13px;font-family:-apple-system,'Segoe UI',sans-serif}}
.code{{display:flex;padding:18px 22px 22px;font-size:15px;line-height:1.6;color:#e6edf3}}
.ln,pre{{font:inherit;line-height:inherit;margin:0}}
.ln{{color:#3d444d;text-align:right;padding-right:18px;user-select:none;white-space:pre}}
pre{{white-space:pre;overflow:hidden}}
.cap{{color:rgba(255,255,255,.85);font:500 14px -apple-system,'Segoe UI',sans-serif;margin-top:18px;text-align:center}}
{css}
.code pre,.code .ln{{line-height:1.6!important;background:none!important}}</style></head><body><div id="frame"><div class="win">
<div class="bar"><span class="dot" style="background:#ff5f57"></span><span class="dot" style="background:#febc2e"></span>
<span class="dot" style="background:#28c840"></span><span class="name">{html.escape(title or src.name)}</span></div>
<div class="code"><div class="ln">{nums}</div><pre>{body}</pre></div></div>
{f'<div class="cap">{html.escape(caption)}</div>' if caption else ''}</div></body></html>"""
    return _render(doc, out)

# ---------------------------------------------------------------- app screenshots

def _framed(png: Path, url: str, mobile: bool, theme: str) -> str:
    data = base64.b64encode(png.read_bytes()).decode()
    if mobile:
        inner = (f'<div style="width:390px;border-radius:44px;padding:14px;background:#0b0b0c;'
                 f'box-shadow:0 30px 60px rgba(0,0,0,.45)"><img src="data:image/png;base64,{data}" '
                 f'style="width:100%;border-radius:32px;display:block"></div>')
    else:
        inner = (f'<div style="width:1200px;border-radius:12px;overflow:hidden;background:#fff;'
                 f'box-shadow:0 30px 60px rgba(0,0,0,.4),0 0 0 1px rgba(0,0,0,.08)">'
                 f'<div style="display:flex;align-items:center;gap:8px;padding:12px 14px;background:#f1f3f4">'
                 f'<span style="width:12px;height:12px;border-radius:50%;background:#ff5f57"></span>'
                 f'<span style="width:12px;height:12px;border-radius:50%;background:#febc2e"></span>'
                 f'<span style="width:12px;height:12px;border-radius:50%;background:#28c840"></span>'
                 f'<span style="margin-left:14px;flex:1;background:#fff;border-radius:8px;padding:6px 12px;'
                 f'font:13px -apple-system,Segoe UI,sans-serif;color:#5f6368">{html.escape(url)}</span></div>'
                 f'<img src="data:image/png;base64,{data}" style="width:100%;display:block"></div>')
    return (f'<!doctype html><html><body style="margin:0"><div id="frame" style="display:inline-block;'
            f'padding:64px;background:{THEMES.get(theme, THEMES["ocean"])}">{inner}</div></body></html>')


def url_images(url: str, out_dir: Path, theme: str = "ocean") -> list[Path]:
    if not playwright_ok():
        raise RuntimeError("Playwright is needed: pip install playwright && playwright install chromium")
    from playwright.sync_api import sync_playwright
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%H%M%S")
    name = slug(url.split("//")[-1], 30)
    results = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        for label, vp, mobile in (("desktop", {"width": 1440, "height": 900}, False),
                                  ("mobile", {"width": 390, "height": 844}, True)):
            page = b.new_page(viewport=vp, device_scale_factor=2, is_mobile=mobile)
            try:
                page.goto(url, wait_until="networkidle", timeout=25000)
            except Exception:
                page.wait_for_timeout(1500)
            try:  # short pages: don't frame a sea of white
                h = int(page.evaluate("Math.ceil(Math.max(...[...document.body.children].map(e => e.getBoundingClientRect().bottom), 0))"))
                page.set_viewport_size({"width": vp["width"], "height": max(560 if not mobile else 700, min(vp["height"], h + 40))})
            except Exception:
                pass
            raw = out_dir / f".raw-{name}-{label}.png"
            page.screenshot(path=str(raw))
            page.close()
            final = out_dir / f"app-{name}-{label}-{stamp}.png"
            pg = b.new_page(viewport={"width": 1500 if not mobile else 700, "height": 900}, device_scale_factor=1)
            pg.set_content(_framed(raw, url, mobile, theme))
            pg.locator("#frame").screenshot(path=str(final))
            pg.close()
            raw.unlink(missing_ok=True)
            results.append(final)
        b.close()
    return results

# ---------------------------------------------------------------- detection

def _listening_psutil() -> list[tuple[int, int, str]]:
    import psutil  # type: ignore
    out = []
    for c in psutil.net_connections(kind="tcp"):
        if c.status == psutil.CONN_LISTEN and c.laddr and c.laddr.port in DEV_PORTS and c.pid:
            out.append((c.laddr.port, c.pid, ""))
    return out


def _listening_fallback() -> list[tuple[int, int, str]]:
    o, out = os_name(), []
    try:
        if o in ("mac", "linux") and shutil.which("lsof"):
            r = subprocess.run(["lsof", "-nP", "-iTCP", "-sTCP:LISTEN", "-F", "pcn"], capture_output=True, text=True, timeout=10)
            pid, cmd = 0, ""
            for line in r.stdout.splitlines():
                if line.startswith("p"):
                    pid = int(line[1:])
                elif line.startswith("c"):
                    cmd = line[1:]
                elif line.startswith("n"):
                    m = re.search(r":(\d+)$", line)
                    if m and int(m.group(1)) in DEV_PORTS:
                        out.append((int(m.group(1)), pid, cmd))
        elif o == "linux":
            r = subprocess.run(["ss", "-ltnpH"], capture_output=True, text=True, timeout=10)
            for line in r.stdout.splitlines():
                m = re.search(r":(\d+)\s.*pid=(\d+)", line)
                c = re.search(r'\("([^"]+)"', line)
                if m and int(m.group(1)) in DEV_PORTS:
                    out.append((int(m.group(1)), int(m.group(2)), c.group(1) if c else ""))
        elif o == "windows":
            r = subprocess.run(["netstat", "-ano", "-p", "TCP"], capture_output=True, text=True, timeout=10)
            for line in r.stdout.splitlines():
                m = re.search(r"\s(?:127\.0\.0\.1|0\.0\.0\.0|\[::\]|\[::1\]):(\d+)\s+\S+\s+LISTENING\s+(\d+)", line)
                if m and int(m.group(1)) in DEV_PORTS:
                    out.append((int(m.group(1)), int(m.group(2)), ""))
    except (OSError, subprocess.SubprocessError, ValueError):
        pass
    return out


def _proc_info(pid: int) -> tuple[str, str]:
    """(process name, working directory) for a pid, best effort on each OS."""
    try:
        import psutil  # type: ignore
        p = psutil.Process(pid)
        return p.name(), p.cwd()
    except Exception:
        pass
    o = os_name()
    try:
        if o == "linux":
            return Path(f"/proc/{pid}/comm").read_text().strip(), str(Path(f"/proc/{pid}/cwd").resolve())
        if o == "mac" and shutil.which("lsof"):
            r = subprocess.run(["lsof", "-a", "-p", str(pid), "-d", "cwd", "-Fcn"], capture_output=True, text=True, timeout=5)
            name = next((l[1:] for l in r.stdout.splitlines() if l.startswith("c")), "")
            cwd = next((l[1:] for l in r.stdout.splitlines() if l.startswith("n")), "")
            return name, cwd
        if o == "windows":
            r = subprocess.run(["powershell", "-NoProfile", "-Command",
                                f"(Get-CimInstance Win32_Process -Filter 'ProcessId={pid}') | "
                                "ForEach-Object {{ $_.Name + '|' + $_.CommandLine }}"],
                               capture_output=True, text=True, timeout=15)
            name, _, cmdline = r.stdout.strip().partition("|")
            m = re.search(r"([A-Za-z]:\\[^\"]+?)\\(?:node_modules|\.venv|venv)\\", cmdline)
            return name, m.group(1) if m else ""
    except (OSError, subprocess.SubprocessError):
        pass
    return "", ""


def _is_html(url: str) -> bool:
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "buildinpublic"}), timeout=3) as r:
            return "html" in (r.headers.get("Content-Type") or "")
    except Exception:
        return False


def dev_servers() -> list[dict]:
    try:
        raw = _listening_psutil()
    except Exception:
        raw = _listening_fallback()
    seen, out = set(), []
    for port, pid, cmd in raw:
        if port in seen:
            continue
        seen.add(port)
        name, cwd = _proc_info(pid) if pid else (cmd, "")
        name = name or cmd
        if name and not any(p in name.lower() for p in DEV_PROCS):
            continue
        url = f"http://localhost:{port}"
        if not _is_html(url):
            continue
        root = journal.project_root(cwd) if cwd else None
        out.append({"url": url, "port": port, "process": name, "project_path": root, "via": "dev server"})
    return out


def agent_testing(minutes: int = 30) -> list[dict]:
    """Localhost URLs agents opened in a browser during the last N minutes."""
    cutoff = (dt.datetime.now().astimezone() - dt.timedelta(minutes=minutes)).isoformat()
    out = []
    for m in journal.all_meta()[-40:]:
        if (m.get("ended") or "") >= cutoff and m.get("browser_urls"):
            for u in m["browser_urls"][:2]:
                out.append({"url": u, "project_path": m.get("path"), "process": m["agent"],
                            "via": f"{m['agent']} browser test", "session_dir": m["dir"]})
    return out

# ---------------------------------------------------------------- permission + capture

def _project_for(path: str | None) -> tuple[str | None, dict]:
    if not path:
        return None, {}
    for k, v in journal.load_projects().items():
        if v.get("path") == path:
            return k, v
    return None, {}


def shots_dir(project_key: str | None, session_dir: str | None = None) -> Path:
    if session_dir:
        return Path(session_dir) / "shots"
    m = journal.latest_meta(project_key) if project_key else None
    if m:
        return Path(m["dir"]) / "shots"
    return app_home() / "shots" / (project_key or "unsorted") / str(dt.date.today())


def capture_url(url: str, project_key: str | None = None, session_dir: str | None = None) -> list[Path]:
    out = shots_dir(project_key, session_dir)
    files = url_images(url, out)
    st = state()
    base = re.match(r"https?://[^/]+", url).group(0)
    st["pending_shots"] = [p for p in st.get("pending_shots", []) if not p["url"].startswith(base)]
    save_state(st)
    meta_f = out.parent / "meta.json"
    if meta_f.exists():
        meta = read_json(meta_f, {})
        meta["shots"] = sorted({*meta.get("shots", []), *[f.name for f in files]})
        if "#visual" not in meta.get("tags", []):
            meta.setdefault("tags", []).append("#visual")
        meta["score"] = journal.story_score(meta)
        write_json(meta_f, meta)
        (out.parent / "summary.md").write_text(journal.render_summary(meta), encoding="utf-8")
    return files


def pending() -> list[dict]:
    return state().get("pending_shots", [])


def watch(quiet: bool = False) -> list[str]:
    cfg = load_config()
    if cfg.get("screenshots") == "never":
        return []
    st = state()
    cool = st.setdefault("shot_prompted", {})
    now = dt.datetime.now()
    cooldown = dt.timedelta(minutes=int(cfg.get("shot_prompt_cooldown_minutes", 90)))
    results = []
    candidates = agent_testing() + dev_servers()
    seen_urls = set()
    for c in candidates:
        base = re.match(r"https?://[^/]+", c["url"]).group(0)
        if base in seen_urls:
            continue
        seen_urls.add(base)
        key, proj = _project_for(c.get("project_path"))
        pref = proj.get("shots", "ask")
        if pref == "never" or proj.get("status") == "ignored":
            continue
        last = cool.get(f"{key}:{base}")
        if last and now - dt.datetime.fromisoformat(last) < cooldown:
            continue
        cool[f"{key}:{base}"] = now.isoformat(timespec="seconds")
        save_state(st)
        name = proj.get("name") or c.get("process") or "your app"
        if pref == "always":
            answer = "Capture"
        else:
            answer = notify.ask(f"{c['url']} ({name}) looks like it's running ({c['via']}).\n\n"
                                "Capture desktop + mobile screenshots for a post?",
                                ["Capture", "Not now", "Never for this project"])
        if answer == "Capture":
            try:
                files = capture_url(c["url"], key, c.get("session_dir"))
                results.append(f"captured {c['url']} → {files[0].parent}")
                notify.desktop(f"Saved {len(files)} screenshots of {name}")
            except Exception as e:
                results.append(f"capture failed for {c['url']}: {e}")
        elif answer == "Never for this project" and key:
            journal.set_project(key, shots="never")
        elif answer is None:  # no GUI: ask in the next agent session instead
            pend = st.setdefault("pending_shots", [])
            if not any(p["url"] == c["url"] for p in pend):
                pend.append({**c, "project": key, "asked": now.isoformat(timespec="seconds")})
                save_state(st)
            results.append(f"queued {c['url']} to ask in your next agent session")
    if not quiet:
        print("\n".join(results) or "No local dev servers or agent browser tests found.")
    return results


def clear_pending(url: str | None = None) -> None:
    st = state()
    st["pending_shots"] = [p for p in st.get("pending_shots", []) if url and p["url"] != url]
    save_state(st)


def latest_code_shot(project_key: str | None = None, theme: str = "dusk") -> Path | None:
    """Make a code image from the most recent session's most-changed file."""
    m = journal.latest_meta(project_key)
    if not m or not m.get("files"):
        return None
    root = Path(m.get("path", ""))
    for f in m["files"]:
        p = Path(f) if Path(f).is_absolute() else root / f
        if p.exists() and p.suffix not in (".json", ".lock", ".md", ".png", ".svg"):
            rng = _changed_range(root, p)
            return code_image(p, Path(m["dir"]) / "shots" / f"code-{slug(p.name, 30)}.png",
                              lines=rng, title=f"{m.get('project_name')} · {p.name}", theme=theme)
    return None


def _changed_range(root: Path, f: Path) -> str | None:
    try:
        r = subprocess.run(["git", "-C", str(root), "diff", "-U2", "HEAD", "--", str(f)],
                           capture_output=True, text=True, timeout=10)
        m = re.search(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", r.stdout, re.M)
        if m:
            a, n = int(m.group(1)), int(m.group(2) or 10)
            return f"{max(1, a)}-{a + min(max(n, 8), 30)}"
    except (OSError, subprocess.SubprocessError):
        pass
    return None
