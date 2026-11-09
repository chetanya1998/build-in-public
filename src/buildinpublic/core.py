"""Paths, config, state, redaction and small helpers shared by every module.

Everything is standard-library only and works on macOS, Windows and Linux.
Two environment variables make testing (and unusual setups) possible:
  BUILDINPUBLIC_HOME   where the journal lives      (default ~/.buildinpublic)
  BIP_USER_HOME        where agent folders are read (default the user's home)
"""
from __future__ import annotations

import datetime as dt
import fnmatch
import json
import os
import platform
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------- platform

def os_name() -> str:
    s = platform.system().lower()
    if s == "darwin":
        return "mac"
    if s == "windows":
        return "windows"
    return "linux"


def user_home() -> Path:
    return Path(os.environ.get("BIP_USER_HOME") or Path.home())


def app_home() -> Path:
    p = Path(os.environ.get("BUILDINPUBLIC_HOME") or (user_home() / ".buildinpublic"))
    p.mkdir(parents=True, exist_ok=True)
    return p


def python_cmd() -> list[str]:
    """How to invoke this package from hooks and schedulers."""
    exe = sys.executable
    if os_name() == "windows":
        w = Path(exe).with_name("pythonw.exe")
        if w.exists():
            exe = str(w)
    return [exe, "-m", "buildinpublic"]


def wsl_homes() -> list[Path]:
    """On Windows, agents may run inside WSL. Return Linux home dirs we can see."""
    if os_name() != "windows" or os.environ.get("BIP_USER_HOME"):
        return []
    out = []
    for root in (Path(r"\\wsl.localhost"), Path(r"\\wsl$")):
        try:
            for distro in root.iterdir():
                h = distro / "home"
                if h.is_dir():
                    out += [d for d in h.iterdir() if d.is_dir()]
        except OSError:
            continue
        if out:
            break
    return out


def agent_dirs() -> dict[str, list[Path]]:
    """Where each agent keeps its data, including WSL copies on Windows."""
    homes = [user_home()] + wsl_homes()
    claude = [Path(os.environ["CLAUDE_CONFIG_DIR"])] if os.environ.get("CLAUDE_CONFIG_DIR") else []
    codex = [Path(os.environ["CODEX_HOME"])] if os.environ.get("CODEX_HOME") else []
    claude += [h / ".claude" for h in homes]
    codex += [h / ".codex" for h in homes]
    gemini = [h / ".gemini" for h in homes]
    return {"claude": claude, "codex": codex, "gemini": gemini}

# ---------------------------------------------------------------- json io

def read_json(path: Path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def write_json(path: Path, data) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    os.replace(tmp, path)

# ---------------------------------------------------------------- config

DEFAULT_CONFIG = {
    "capture": "live+hourly",          # live+hourly | hourly | nightly
    "summary_time": "00:00",           # local time the daily summary is delivered
    "channels": ["notification"],      # notification, email
    "email": {"to": "", "from": "", "method": "", "smtp_host": "smtp.gmail.com", "smtp_port": 465},
    "screenshots": "ask",              # ask | never
    "localhost_check_minutes": 5,
    "shot_prompt_cooldown_minutes": 90,
    "nudge_after_days": 2,
    "new_project_default": "ask",      # ask | journal | content
    "exclude": [],                     # glob patterns of folders never recorded
    "retention_days": 0,               # 0 = keep forever
    "research": True,                  # fetch related articles and hook examples
    "trend_sources": ["hn", "devto", "reddit", "github"],
    "draft_agent": "auto",             # auto | claude | codex | none
    "platforms": ["x", "linkedin"],
}


def load_config() -> dict:
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    user = read_json(app_home() / "config.json", {})
    for k, v in user.items():
        if isinstance(v, dict) and isinstance(cfg.get(k), dict):
            cfg[k].update(v)
        else:
            cfg[k] = v
    return cfg


def save_config(cfg: dict) -> None:
    write_json(app_home() / "config.json", cfg)


def set_config_value(key: str, raw: str) -> dict:
    cfg = load_config()
    try:
        val = json.loads(raw)
    except ValueError:
        val = raw
    node = cfg
    parts = key.split(".")
    for p in parts[:-1]:
        node = node.setdefault(p, {})
    node[parts[-1]] = val
    save_config(cfg)
    return cfg


def state() -> dict:
    return read_json(app_home() / "state.json", {})


def save_state(s: dict) -> None:
    write_json(app_home() / "state.json", s)

# ---------------------------------------------------------------- redaction

_SECRET = re.compile("|".join([
    r"sk-ant-[A-Za-z0-9_\-]{16,}", r"sk-[A-Za-z0-9_\-]{16,}", r"gh[pousr]_[A-Za-z0-9]{20,}",
    r"github_pat_[A-Za-z0-9_]{20,}", r"AKIA[0-9A-Z]{16}", r"AIza[0-9A-Za-z_\-]{30,}",
    r"xox[baprs]-[A-Za-z0-9\-]{10,}", r"(?:sk|pk|rk)_(?:live|test)_[A-Za-z0-9]{10,}",
    r"eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}",
    r"(?:[Aa][Pp][Ii][_-]?[Kk][Ee][Yy]|[Ss]ecret|SECRET|[Tt]oken|TOKEN|[Pp]assword|PASSWORD|passwd)"
    r"\s*[:=]\s*['\"]?[^\s'\"]{6,}",
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----",
    r"(?:postgres|postgresql|mysql|mongodb(?:\+srv)?|redis)://[^\s'\"]+",
]))
_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")


def redact(text: str, extra: list[str] | None = None) -> str:
    if not text:
        return ""
    text = _SECRET.sub("[REDACTED]", text)
    text = _EMAIL.sub("[email]", text)
    for word in extra or []:
        if word and len(word) > 2:
            text = re.sub(re.escape(word), "[off-limits]", text, flags=re.I)
    home = str(user_home())
    if len(home) > 3:
        text = text.replace(home, "~")
    return text


def clip(text: str, n: int = 400) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text if len(text) <= n else text[: n - 1] + "…"

# ---------------------------------------------------------------- misc

def slug(text: str, n: int = 48) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return (s[:n].strip("-")) or "untitled"


def today() -> dt.date:
    """'Today' for journaling: work done before 4am counts as the previous day."""
    return (dt.datetime.now() - dt.timedelta(hours=4)).date()


def parse_ts(value) -> dt.datetime | None:
    if value is None:
        return None
    try:
        if isinstance(value, (int, float)):
            v = value / 1000 if value > 1e12 else value
            return dt.datetime.fromtimestamp(v).astimezone()
        s = str(value).replace("Z", "+00:00")
        d = dt.datetime.fromisoformat(s)
        return (d if d.tzinfo else d.astimezone()).astimezone()
    except (ValueError, OSError, OverflowError):
        return None


def work_day(ts: dt.datetime) -> dt.date:
    return (ts - dt.timedelta(hours=4)).date()


def is_excluded(path: str | None, cfg: dict | None = None) -> bool:
    if not path:
        return False
    cfg = cfg or load_config()
    norm = str(Path(path).expanduser()).replace("\\", "/")
    for pat in cfg.get("exclude", []):
        p = str(Path(pat).expanduser()).replace("\\", "/")
        if fnmatch.fnmatch(norm, p) or fnmatch.fnmatch(norm, p.rstrip("/") + "/*") or norm == p:
            return True
    return False


def fmt_minutes(m: float) -> str:
    m = int(round(m))
    return f"{m // 60}h {m % 60:02d}m" if m >= 60 else f"{m}m"
