"""Read sessions saved by Claude Code, Codex and Antigravity.

Agent file formats change between releases, so every reader is tolerant: any
JSON record carrying a role and text counts as a message, any tool_use /
function_call counts as a tool call, and timestamps/cwd are found wherever they
appear. Readers never modify agent files.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

from .core import agent_dirs, parse_ts

MEDIA = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".webm", ".mp4"}
EDIT_TOOLS = {"edit", "write", "multiedit", "apply_patch", "str_replace", "create_file",
              "str_replace_editor", "write_file", "replace", "edit_file", "notebookedit"}
SHELL_TOOLS = {"bash", "shell", "exec_command", "local_shell", "run_shell_command",
               "run_command", "terminal", "powershell"}


@dataclass
class Session:
    agent: str
    id: str
    path: str
    cwd: str | None = None
    started: dt.datetime | None = None
    ended: dt.datetime | None = None
    messages: list = field(default_factory=list)   # [(role, text)]
    tools: list = field(default_factory=list)      # [(name, target)]
    media: list = field(default_factory=list)      # [path]
    signature: str = ""                            # size:mtime for incremental capture

    @property
    def files_edited(self) -> list[str]:
        return sorted({t for n, t in self.tools if t and n.lower() in EDIT_TOOLS})

    @property
    def commands(self) -> list[str]:
        return [t for n, t in self.tools if t and n.lower() in SHELL_TOOLS]

    @property
    def browser_urls(self) -> list[str]:
        urls = []
        for n, t in self.tools:
            for u in re.findall(r"https?://(?:localhost|127\.0\.0\.1|0\.0\.0\.0|\[::1\])(?::\d+)?[^\s'\"]*", t or ""):
                urls.append(u)
        return urls


def _sig(p: Path) -> str:
    try:
        st = p.stat()
        return f"{st.st_size}:{int(st.st_mtime)}"
    except OSError:
        return ""

# ---------------------------------------------------------------- jsonl helpers

def iter_jsonl(path: Path) -> Iterator[dict]:
    try:
        if path.name.endswith(".zst"):
            if not shutil.which("zstd"):
                return
            raw = subprocess.run(["zstd", "-dc", str(path)], capture_output=True, text=True,
                                 encoding="utf-8", errors="ignore").stdout
        else:
            raw = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                yield json.loads(line)
            except ValueError:
                continue


def _text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for c in content:
            if isinstance(c, dict):
                if c.get("type") in ("tool_result", "image", "input_image", "tool_use", "function_call"):
                    continue
                t = c.get("text") or c.get("input_text") or c.get("output_text")
                if isinstance(t, str):
                    parts.append(t)
            elif isinstance(c, str):
                parts.append(c)
        return "\n".join(parts)
    if isinstance(content, dict):
        return _text(content.get("content") or content.get("text"))
    return ""


def _walk(obj, depth=0):
    if depth > 7:
        return
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            if isinstance(v, (dict, list)):
                yield from _walk(v, depth + 1)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk(v, depth + 1)


def _tool_target(args) -> str:
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except ValueError:
            return args[:200]
    if not isinstance(args, dict):
        return ""
    for key in ("file_path", "path", "filePath", "notebook_path", "url", "command", "cmd", "script"):
        v = args.get(key)
        if v:
            return (" ".join(map(str, v)) if isinstance(v, list) else str(v))[:240]
    return ""


def parse_records(records, sess: Session) -> Session:
    seen_text = set()
    for rec in records:
        for ts_key in ("timestamp", "ts", "created_at", "time"):
            ts = parse_ts(rec.get(ts_key)) if isinstance(rec, dict) else None
            if ts:
                sess.started = min(sess.started, ts) if sess.started else ts
                sess.ended = max(sess.ended, ts) if sess.ended else ts
                break
        for node in _walk(rec):
            if not sess.cwd and isinstance(node.get("cwd"), str):
                sess.cwd = node["cwd"]
            role = node.get("role")
            if role in ("user", "assistant") and ("content" in node or "text" in node):
                t = _text(node.get("content", node.get("text"))).strip()
                if t and not t.startswith("<") and t not in seen_text:
                    seen_text.add(t)
                    sess.messages.append((role, t))
            if node.get("type") in ("tool_use", "function_call", "custom_tool_call", "local_shell_call"):
                name = node.get("name") or node.get("tool_name") or ("shell" if "shell" in node.get("type", "") else "tool")
                args = node.get("input") or node.get("arguments") or node.get("action") or {}
                sess.tools.append((str(name), _tool_target(args)))
    return sess

# ---------------------------------------------------------------- Claude Code

def claude_sessions(since: float = 0) -> list[Session]:
    out = []
    for base in agent_dirs()["claude"]:
        proj = base / "projects"
        if not proj.is_dir():
            continue
        for f in proj.glob("*/*.jsonl"):
            try:
                if f.stat().st_mtime < since:
                    continue
            except OSError:
                continue
            out.append(read_claude(f))
    return [s for s in out if s and (s.messages or s.tools)]


def read_claude(f: Path) -> Session:
    s = Session(agent="claude-code", id=f.stem, path=str(f), signature=_sig(f))
    parse_records(iter_jsonl(f), s)
    if not s.cwd:  # fall back to decoding the folder name (lossy: '-' replaced '/')
        s.cwd = "/" + f.parent.name.strip("-").replace("-", "/")
    return s

# ---------------------------------------------------------------- Codex

def codex_sessions(since: float = 0) -> list[Session]:
    out = []
    for base in agent_dirs()["codex"]:
        root = base / "sessions"
        if not root.is_dir():
            continue
        for f in root.rglob("*"):
            if not f.name.endswith((".jsonl", ".jsonl.zst")):
                continue
            try:
                if f.stat().st_mtime < since:
                    continue
            except OSError:
                continue
            out.append(read_codex(f))
    return [s for s in out if s and (s.messages or s.tools)]


def read_codex(f: Path) -> Session:
    sid = re.sub(r"\.jsonl(\.zst)?$", "", f.name).replace("rollout-", "")
    s = Session(agent="codex", id=sid, path=str(f), signature=_sig(f))
    parse_records(iter_jsonl(f), s)
    # Codex prepends environment/instructions as user messages; drop obvious ones
    s.messages = [(r, t) for r, t in s.messages if not t.lstrip().startswith(("# AGENTS.md", "<environment_context>"))]
    return s

# ---------------------------------------------------------------- Antigravity

_PATH_RE = re.compile(r"file://(/[^\s)\]'\"#]+)|(?<![\w/])(/(?:Users|home)/[^\s)\]'\"#:]+)|([A-Za-z]:\\[^\s)\]'\"#]+)")


def _project_from_paths(text: str) -> str | None:
    """Antigravity artifacts link workspace files; find the git root they live in."""
    counts: dict[str, int] = {}
    for m in _PATH_RE.finditer(text):
        raw = next(g for g in m.groups() if g)
        p = Path(raw.replace("%20", " "))
        for parent in [p] + list(p.parents)[:8]:
            if (parent / ".git").exists():
                counts[str(parent)] = counts.get(str(parent), 0) + 1
                break
        else:
            if len(p.parts) > 3:
                key = str(Path(*p.parts[:4]))
                counts[key] = counts.get(key, 0) + 0.1
    return max(counts, key=counts.get) if counts else None


def antigravity_sessions(since: float = 0) -> list[Session]:
    out = []
    for base in agent_dirs()["gemini"]:
        if not base.is_dir():
            continue
        for brain in list(base.glob("antigravity*/brain")):
            for conv in brain.iterdir():
                if not conv.is_dir():
                    continue
                files = [f for f in conv.rglob("*") if f.is_file()]
                if not files:
                    continue
                newest = max(f.stat().st_mtime for f in files)
                if newest < since:
                    continue
                out.append(read_antigravity(conv, files))
    return [s for s in out if s and (s.messages or s.media)]


def read_antigravity(conv: Path, files: list[Path] | None = None) -> Session:
    files = files or [f for f in conv.rglob("*") if f.is_file()]
    sig = f"{len(files)}:{int(max((f.stat().st_mtime for f in files), default=0))}"
    s = Session(agent="antigravity", id=conv.name, path=str(conv), signature=sig)
    docs = sorted([f for f in files if f.suffix == ".md"], key=lambda f: f.stat().st_mtime)
    blob = ""
    for f in docs:
        t = f.read_text(encoding="utf-8", errors="ignore")
        blob += "\n" + t
        role = "user" if f.stem.lower() in ("task", "request", "prompt") else "assistant"
        s.messages.append((role, f"[{f.stem}] {t}"))
    for f in files:
        if f.suffix in (".json", ".jsonl"):
            parse_records(iter_jsonl(f) if f.suffix == ".jsonl" else [_safe_json(f)], s)
    s.media = [str(f) for f in files if f.suffix.lower() in MEDIA]
    s.cwd = s.cwd or _project_from_paths(blob)
    times = [dt.datetime.fromtimestamp(f.stat().st_mtime).astimezone() for f in files]
    s.started = s.started or min(times)
    s.ended = s.ended or max(times)
    return s


def _safe_json(f: Path) -> dict:
    try:
        return json.loads(f.read_text(encoding="utf-8", errors="ignore"))
    except ValueError:
        return {}

# ---------------------------------------------------------------- all

READERS = {"claude-code": claude_sessions, "codex": codex_sessions, "antigravity": antigravity_sessions}


def all_sessions(since: float = 0, agents: list[str] | None = None) -> list[Session]:
    out = []
    for name, fn in READERS.items():
        if agents and name not in agents:
            continue
        try:
            out += fn(since)
        except Exception as e:  # a broken reader must never stop the others
            import sys
            print(f"[buildinpublic] {name} reader failed: {e}", file=sys.stderr)
    for s in out:
        if not s.started:
            try:
                m = Path(s.path).stat().st_mtime
                s.started = s.ended = dt.datetime.fromtimestamp(m).astimezone()
            except OSError:
                s.started = s.ended = dt.datetime.now().astimezone()
    return out


def read_one(path: str, agent: str | None = None) -> Session | None:
    p = Path(path)
    if not p.exists():
        return None
    if agent == "antigravity" or p.is_dir():
        return read_antigravity(p)
    if agent == "codex" or "/.codex/" in str(p).replace("\\", "/"):
        return read_codex(p)
    return read_claude(p)
