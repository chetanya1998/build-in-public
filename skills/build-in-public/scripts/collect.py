#!/usr/bin/env python3
"""Build In Public: collect one day of work for the current repo.

Reads, read-only and locally:
  - Claude Code sessions   ~/.claude/projects/<encoded-cwd>/*.jsonl
  - Codex sessions         ~/.codex/sessions/YYYY/MM/DD/*.jsonl[.zst]
  - Antigravity            ~/.gemini/antigravity*/brain/**  (markdown artifacts + media)
  - git                    commits, diffstat
  - .buildinpublic/log/     entries written by agents via AGENTS.md
and writes a compact, redacted digest to .buildinpublic/daily/<date>/digest.md

Session formats change between releases, so parsing is deliberately tolerant:
any JSON line with a role + text is treated as a message. Use --inspect to see
what was found for each source.

Usage: python3 collect.py [--date YYYY-MM-DD] [--repo PATH] [--inspect]
"""
import argparse, datetime as dt, json, os, re, shutil, subprocess, sys
from pathlib import Path

HOME = Path.home()
MAX_MSG = 600          # chars kept per message
MAX_MSGS = 60          # messages kept per session
MEDIA = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".webm", ".mp4"}

SECRET_PATTERNS = [
    r"sk-[A-Za-z0-9_\-]{16,}", r"sk-ant-[A-Za-z0-9_\-]{16,}", r"gh[pousr]_[A-Za-z0-9]{20,}",
    r"AKIA[0-9A-Z]{16}", r"AIza[0-9A-Za-z_\-]{30,}", r"xox[baprs]-[A-Za-z0-9\-]{10,}",
    r"eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}",
    r"(?:[Aa][Pp][Ii][_-]?[Kk][Ee][Yy]|[Ss]ecret|SECRET|[Tt]oken|TOKEN|[Pp]assword|PASSWORD|passwd)\s*[:=]\s*['\"]?[^\s'\"]{6,}",
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----",
]
SECRET_RE = re.compile("|".join(SECRET_PATTERNS))
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")


def redact(text, extra=()):
    text = SECRET_RE.sub("[REDACTED]", text)
    text = EMAIL_RE.sub("[email]", text)
    for word in extra:
        if word:
            text = re.sub(re.escape(word), "[off-limits]", text, flags=re.I)
    return text


def clip(text, n=MAX_MSG):
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= n else text[: n - 1] + "…"


def day_bounds(day):
    start = dt.datetime.combine(day, dt.time.min).astimezone()
    return start.timestamp(), (start + dt.timedelta(days=1)).timestamp()


def modified_on(path, day):
    lo, hi = day_bounds(day)
    try:
        m = path.stat().st_mtime
    except OSError:
        return False
    return lo <= m < hi + 6 * 3600  # sessions touched that day (allow a late-night spill)


# ---------- generic JSONL message extraction ----------

def iter_jsonl(path):
    try:
        if path.suffix == ".zst":
            if not shutil.which("zstd"):
                return
            raw = subprocess.run(["zstd", "-dc", str(path)], capture_output=True, text=True).stdout
            lines = raw.splitlines()
        else:
            lines = path.read_text(errors="ignore").splitlines()
    except OSError:
        return
    for line in lines:
        line = line.strip()
        if line.startswith("{"):
            try:
                yield json.loads(line)
            except ValueError:
                continue


def text_of(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for c in content:
            if isinstance(c, dict):
                if c.get("type") in ("tool_result", "image", "input_image"):
                    continue
                t = c.get("text") or c.get("input_text") or c.get("output_text")
                if isinstance(t, str):
                    parts.append(t)
            elif isinstance(c, str):
                parts.append(c)
        return "\n".join(parts)
    if isinstance(content, dict):
        return text_of(content.get("content") or content.get("text"))
    return ""


def find_messages(obj, out, depth=0):
    """Find {role, content/text} dicts anywhere in a record."""
    if depth > 6 or not isinstance(obj, (dict, list)):
        return
    if isinstance(obj, list):
        for v in obj:
            find_messages(v, out, depth + 1)
        return
    role = obj.get("role")
    if role in ("user", "assistant"):
        t = text_of(obj.get("content", obj.get("text")))
        if t and not t.startswith("<"):  # skip injected system/xml blocks
            out.append((role, t))
            return
    for v in obj.values():
        find_messages(v, out, depth + 1)


def find_tools(obj, out, depth=0):
    if depth > 6 or not isinstance(obj, (dict, list)):
        return
    if isinstance(obj, list):
        for v in obj:
            find_tools(v, out, depth + 1)
        return
    if obj.get("type") in ("tool_use", "function_call", "custom_tool_call"):
        name = obj.get("name") or obj.get("tool_name") or "tool"
        args = obj.get("input") or obj.get("arguments") or {}
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except ValueError:
                args = {"raw": args}
        target = ""
        if isinstance(args, dict):
            target = args.get("file_path") or args.get("path") or args.get("command") or args.get("cmd") or ""
            if isinstance(target, list):
                target = " ".join(map(str, target))
        out.append((name, str(target)[:1000]))  # trimmed for display in render(), after the repo path is stripped
    for v in obj.values():
        find_tools(v, out, depth + 1)


def find_cwd(obj, depth=0):
    if depth > 4 or not isinstance(obj, (dict, list)):
        return None
    if isinstance(obj, list):
        for v in obj:
            r = find_cwd(v, depth + 1)
            if r:
                return r
        return None
    c = obj.get("cwd")
    if isinstance(c, str):
        return c
    for v in obj.values():
        r = find_cwd(v, depth + 1)
        if r:
            return r
    return None


def summarize_session(path, repo, require_cwd):
    msgs, tools, cwd = [], [], None
    for rec in iter_jsonl(path):
        cwd = cwd or find_cwd(rec)
        find_messages(rec, msgs)
        find_tools(rec, tools)
    if require_cwd and (not cwd or not Path(cwd).resolve().is_relative_to(repo)):
        return None
    if not msgs and not tools:
        return None
    return {"path": str(path), "cwd": cwd, "messages": msgs, "tools": tools}


# ---------- sources ----------

def claude_sessions(repo, day):
    base = HOME / ".claude" / "projects"
    if not base.is_dir():
        return []
    enc = re.sub(r"[^A-Za-z0-9]", "-", str(repo))
    dirs = [d for d in base.iterdir() if d.is_dir() and (d.name == enc or d.name.startswith(enc + "-"))]
    out = []
    for d in dirs:
        for f in sorted(d.glob("*.jsonl")):
            if modified_on(f, day):
                s = summarize_session(f, repo, require_cwd=False)
                if s:
                    out.append(s)
    return out


def codex_sessions(repo, day):
    out = []
    for d in {day, day + dt.timedelta(days=1)}:
        folder = HOME / ".codex" / "sessions" / f"{d:%Y}" / f"{d:%m}" / f"{d:%d}"
        if folder.is_dir():
            for f in sorted(folder.iterdir()):
                if f.name.endswith((".jsonl", ".jsonl.zst")) and modified_on(f, day):
                    s = summarize_session(f, repo, require_cwd=True)
                    if s:
                        out.append(s)
    return out


def antigravity_sessions(repo, day):
    """Antigravity keeps per-conversation 'brain' folders with markdown artifacts
    (task, implementation plan, walkthrough) and browser screenshots/recordings."""
    out = []
    roots = [p for p in (HOME / ".gemini").glob("antigravity*/brain")] if (HOME / ".gemini").is_dir() else []
    for root in roots:
        for conv in root.iterdir():
            if not conv.is_dir():
                continue
            files = [f for f in conv.rglob("*") if f.is_file() and modified_on(f, day)]
            if not files:
                continue
            docs = [f for f in files if f.suffix == ".md"]
            blob = " ".join(f.read_text(errors="ignore") for f in docs)
            if str(repo) not in blob and repo.name.lower() not in blob.lower():
                continue  # can't tie it to this repo
            msgs = [("assistant", f"[{f.stem}] " + f.read_text(errors="ignore")) for f in docs]
            media = [str(f) for f in files if f.suffix.lower() in MEDIA]
            out.append({"path": str(conv), "cwd": None, "messages": msgs, "tools": [], "media": media})
    return out


def git_info(repo, day):
    if not (repo / ".git").exists():
        return "", ""
    since, until = f"{day} 00:00", f"{day + dt.timedelta(days=1)} 06:00"
    run = lambda *a: subprocess.run(["git", "-C", str(repo), *a], capture_output=True, text=True).stdout.strip()
    log = run("log", f"--since={since}", f"--until={until}", "--date=format:%H:%M",
              "--pretty=format:- %ad %h %s", "--shortstat")
    log = re.sub(r"\n\s*\n", "\n", log)
    diff = run("diff", "--stat", "HEAD")
    return log, diff


def harvest_media(repo, day, dest, sessions):
    """Copy screenshots produced that day by browser testing into the daily folder."""
    candidates = []
    for d in (".playwright-mcp", "test-results", "playwright-report", "screenshots", "cypress/screenshots",
              ".buildinpublic/assets"):
        p = repo / d
        if p.is_dir():
            candidates += [f for f in p.rglob("*") if f.suffix.lower() in MEDIA and modified_on(f, day)]
    for s in sessions:
        candidates += [Path(m) for m in s.get("media", [])]
    dest.mkdir(parents=True, exist_ok=True)
    copied = []
    for f in candidates[:40]:
        target = dest / f"{f.parent.name}-{f.name}"
        try:
            shutil.copy2(f, target)
            copied.append(target.name)
        except OSError:
            pass
    return copied


def read_offlimits(repo):
    n = repo / ".buildinpublic" / "narrative.md"
    if not n.exists():
        return []
    m = re.search(r"## Off-limits\s*\n(.*?)(\n## |\Z)", n.read_text(), re.S)
    if not m:
        return []
    items = re.findall(r"[-*]\s*(.+)", re.sub(r"<!--.*?-->", "", m.group(1), flags=re.S))
    return [i.strip() for i in items if 2 < len(i.strip()) < 60]


# ---------- output ----------

def render(day, repo, sources, git_log, git_diff, agent_log, media, extra):
    L = [f"# Digest {day} · {repo.name}", ""]
    total = sum(len(v) for v in sources.values())
    L.append(f"Sessions found: " + ", ".join(f"{k} {len(v)}" for k, v in sources.items()) + f" (total {total})")
    L.append("")
    for name, sess in sources.items():
        for i, s in enumerate(sess, 1):
            L.append(f"## {name} session {i}")
            users = [m for m in s["messages"] if m[0] == "user"]
            asst = [m for m in s["messages"] if m[0] == "assistant"]
            if users:
                L.append("**User asked:**")
                for _, t in users[:MAX_MSGS // 2]:
                    L.append(f"- {clip(redact(t, extra))}")
            if asst:
                L.append("**Agent said (last messages):**")
                for _, t in asst[-6:]:
                    L.append(f"- {clip(redact(t, extra), 900)}")
            if s["tools"]:
                edited = sorted({t for n, t in s["tools"] if t and n.lower() in
                                 ("edit", "write", "multiedit", "apply_patch", "str_replace", "create_file")})
                cmds = [t for n, t in s["tools"] if n.lower() in ("bash", "shell", "exec_command", "local_shell") and t]
                L.append(f"**Tool calls:** {len(s['tools'])}")
                if edited:
                    L.append("**Files edited:** " + ", ".join(redact(e.replace(str(repo) + "/", "")[:160], extra) for e in edited[:25]))
                if cmds:
                    L.append("**Commands (sample):** " + " · ".join(clip(redact(c, extra), 80) for c in cmds[-8:]))
            L.append("")
    L += ["## Git commits", git_log or "_none_", "", "## Uncommitted changes", git_diff or "_none_", ""]
    L += ["## Agent log entries (.buildinpublic/log)", agent_log or "_none_", ""]
    L += ["## Snapshots collected", ("\n".join(f"- snapshots/{m}" for m in media) or "_none_"), ""]
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=None, help="YYYY-MM-DD (default: today, or yesterday if before 4am)")
    ap.add_argument("--repo", default=".")
    ap.add_argument("--inspect", action="store_true", help="print what each source found and exit")
    a = ap.parse_args()

    now = dt.datetime.now()
    day = dt.date.fromisoformat(a.date) if a.date else (now - dt.timedelta(hours=4)).date()
    repo = Path(subprocess.run(["git", "-C", a.repo, "rev-parse", "--show-toplevel"],
                               capture_output=True, text=True).stdout.strip() or a.repo).resolve()

    sources = {
        "Claude Code": claude_sessions(repo, day),
        "Codex": codex_sessions(repo, day),
        "Antigravity": antigravity_sessions(repo, day),
    }
    if a.inspect:
        for k, v in sources.items():
            print(f"{k}: {len(v)} session(s)")
            for s in v:
                print(f"   {s['path']}  msgs={len(s['messages'])} tools={len(s['tools'])}")
        return

    out_dir = repo / ".buildinpublic" / "daily" / str(day)
    out_dir.mkdir(parents=True, exist_ok=True)
    git_log, git_diff = git_info(repo, day)
    log_file = repo / ".buildinpublic" / "log" / f"{day}.md"
    agent_log = log_file.read_text() if log_file.exists() else ""
    media = harvest_media(repo, day, out_dir / "snapshots", sources["Antigravity"])
    extra = read_offlimits(repo)

    (out_dir / "digest.md").write_text(render(day, repo, sources, git_log, git_diff, agent_log, media, extra))
    print(out_dir / "digest.md")


if __name__ == "__main__":
    main()
