"""Connect to Claude Code, Codex and Antigravity.

- installs the agent skill into each agent's skills folder
- Claude Code: SessionEnd hook (capture) + SessionStart hook (nudges)
- Codex: Stop hook (capture) + SessionStart hook (nudges), via ~/.codex/hooks.json
- Antigravity / anything else: a short block in the global GEMINI.md / AGENTS.md
  telling the agent to check ~/.buildinpublic/nudge.md at session start
Every change is marked so `buildinpublic uninstall` can remove exactly what it added.
"""
from __future__ import annotations

import json
import re
import shutil
from importlib import resources
from pathlib import Path

from . import SKILL_NAME
from .core import app_home, os_name, python_cmd, read_json, user_home, write_json

MARK = "buildinpublic"
BLOCK_START, BLOCK_END = "<!-- buildinpublic:start -->", "<!-- buildinpublic:end -->"


def skill_source() -> Path:
    """The repo's skills/build-in-public folder: packaged as buildinpublic.skills when
    installed with pip/pipx/uv, or read straight from a git checkout."""
    here = Path(__file__).resolve().parent
    # Installed: <site-packages>/buildinpublic/skills/build-in-public. Checked by path first,
    # because Python 3.9's resources.files() raises TypeError for this namespace package.
    candidates = [here / "skills" / SKILL_NAME]
    try:
        candidates.append(Path(str(resources.files("buildinpublic.skills") / SKILL_NAME)))
    except (ModuleNotFoundError, TypeError):
        pass
    candidates.append(here.parents[1] / "skills" / SKILL_NAME)  # git checkout: src/buildinpublic -> repo
    for p in candidates:
        if (p / "SKILL.md").exists():
            return p
    raise FileNotFoundError("The build-in-public skill files are missing from this install. "
                            "Reinstall with: python3 -m pip install --user --upgrade --force-reinstall build-in-public")


def skill_targets() -> dict[str, Path]:
    h = user_home()
    return {
        "Claude Code": h / ".claude" / "skills",
        "Codex": h / ".agents" / "skills",
        "Antigravity": h / ".gemini" / "config" / "skills",
    }


def detected_agents() -> dict[str, bool]:
    h = user_home()
    return {"Claude Code": (h / ".claude").exists(), "Codex": (h / ".codex").exists(),
            "Antigravity": (h / ".gemini").exists() or (h / ".antigravity").exists()}


def install_skill(only_detected: bool = True) -> list[str]:
    src, out = skill_source(), []
    det = detected_agents()
    for agent, dest in skill_targets().items():
        if only_detected and not det[agent]:
            continue
        target = dest / SKILL_NAME
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(src, target)
        out.append(f"skill → {agent}: {target}")
    return out


def _hook_entry(sub: str, timeout: int) -> dict:
    cmd = python_cmd() + ["hook", sub]
    if os_name() == "windows":
        entry = {"type": "command", "command": cmd[0], "args": cmd[1:]}
    else:
        entry = {"type": "command", "command": " ".join(f'"{c}"' if " " in c else c for c in cmd)}
    entry.update({"timeout": timeout, "statusMessage": "Build Your Product in Public"})
    return entry


def _is_ours(h: dict) -> bool:
    return "buildinpublic" in (h.get("command", "") + " " + " ".join(h.get("args", [])))


def _merge_hooks(data: dict, event: str, entry: dict, matcher: str | None = None) -> None:
    hooks = data.setdefault("hooks", {})
    groups = hooks.setdefault(event, [])
    for g in groups:
        g["hooks"] = [h for h in g.get("hooks", []) if not _is_ours(h)]
    groups[:] = [g for g in groups if g.get("hooks")]
    group = {"hooks": [entry]}
    if matcher:
        group["matcher"] = matcher
    groups.append(group)


def _strip_hooks(data: dict) -> dict:
    for event, groups in list(data.get("hooks", {}).items()):
        for g in groups:
            g["hooks"] = [h for h in g.get("hooks", []) if not _is_ours(h)]
        data["hooks"][event] = [g for g in groups if g.get("hooks")]
        if not data["hooks"][event]:
            del data["hooks"][event]
    if "hooks" in data and not data["hooks"]:
        del data["hooks"]
    return data


def _backup(p: Path) -> None:
    if p.exists():
        b = p.with_name(p.name + ".buildinpublic.bak")
        if not b.exists():
            shutil.copy2(p, b)


def install_claude_hooks(live: bool = True) -> str:
    p = user_home() / ".claude" / "settings.json"
    if not p.parent.exists():
        return "Claude Code not found, skipped hooks"
    _backup(p)
    data = _strip_hooks(read_json(p, {}))
    if live:
        _merge_hooks(data, "SessionEnd", _hook_entry("claude-end", 10))
    _merge_hooks(data, "SessionStart", _hook_entry("session-start", 10), matcher="startup")
    write_json(p, data)
    return f"Claude Code hooks → {p}"


def install_codex_hooks(live: bool = True) -> str:
    base = user_home() / ".codex"
    if not base.exists():
        return "Codex not found, skipped hooks"
    p = base / "hooks.json"
    _backup(p)
    data = _strip_hooks(read_json(p, {}))
    if live:
        _merge_hooks(data, "Stop", _hook_entry("codex-stop", 10))
    _merge_hooks(data, "SessionStart", _hook_entry("session-start", 10))
    write_json(p, data)
    # hooks are behind a feature flag in Codex
    cfg = base / "config.toml"
    text = cfg.read_text(encoding="utf-8") if cfg.exists() else ""
    if not re.search(r"^\s*codex_hooks\s*=", text, re.M):
        _backup(cfg)
        if re.search(r"^\[features\]\s*$", text, re.M):
            text = re.sub(r"^\[features\]\s*$", "[features]\ncodex_hooks = true  # added by buildinpublic", text, count=1, flags=re.M)
        else:
            text = text.rstrip() + ("\n\n" if text.strip() else "") + "[features]\ncodex_hooks = true  # added by buildinpublic\n"
        cfg.write_text(text, encoding="utf-8")
    return f"Codex hooks → {p} (features.codex_hooks enabled)"


INSTRUCTION = f"""{BLOCK_START}
## Build Your Product in Public
At the start of a session, if the file `{{nudge}}` exists and is not empty, read it and
ask the user its questions conversationally before starting other work (one at a time,
keep it short). When the user answers, run `buildinpublic nudge --reply "<their answer>"`,
or `buildinpublic nudge --snooze` if they say not now. When the user asks to capture a
screenshot or log work for posting, use the build-in-public skill.
{BLOCK_END}
"""


def _write_block(p: Path) -> str:
    p.parent.mkdir(parents=True, exist_ok=True)
    text = p.read_text(encoding="utf-8") if p.exists() else ""
    text = re.sub(re.escape(BLOCK_START) + r".*?" + re.escape(BLOCK_END) + r"\n?", "", text, flags=re.S)
    block = INSTRUCTION.replace("{nudge}", str(app_home() / "nudge.md"))
    p.write_text((text.rstrip() + "\n\n" if text.strip() else "") + block, encoding="utf-8")
    return f"instructions → {p}"


def install_instructions() -> list[str]:
    h, out = user_home(), []
    if (h / ".codex").exists():
        out.append(_write_block(h / ".codex" / "AGENTS.md"))
    if (h / ".gemini").exists() or (h / ".antigravity").exists():
        out.append(_write_block(h / ".gemini" / "GEMINI.md"))
    return out


def install_all(live: bool = True) -> list[str]:
    out = install_skill()
    out.append(install_claude_hooks(live))
    out.append(install_codex_hooks(live))
    out += install_instructions()
    return out


def uninstall_all() -> list[str]:
    h, out = user_home(), []
    for agent, dest in skill_targets().items():
        t = dest / SKILL_NAME
        if t.exists():
            shutil.rmtree(t)
            out.append(f"removed skill from {agent}")
    for p in (h / ".claude" / "settings.json", h / ".codex" / "hooks.json"):
        if p.exists():
            write_json(p, _strip_hooks(read_json(p, {})))
            out.append(f"removed hooks from {p}")
    cfg = h / ".codex" / "config.toml"
    if cfg.exists():
        t = cfg.read_text(encoding="utf-8")
        t2 = re.sub(r"^codex_hooks = true  # added by buildinpublic\n", "", t, flags=re.M)
        if t2 != t:
            cfg.write_text(t2, encoding="utf-8")
    for p in (h / ".codex" / "AGENTS.md", h / ".gemini" / "GEMINI.md"):
        if p.exists():
            t = p.read_text(encoding="utf-8")
            t2 = re.sub(r"\n*" + re.escape(BLOCK_START) + r".*?" + re.escape(BLOCK_END) + r"\n?", "\n", t, flags=re.S)
            if t2 != t:
                p.write_text(t2.strip() + "\n" if t2.strip() else "", encoding="utf-8")
                out.append(f"removed instructions from {p}")
    return out


def hooks_status() -> dict[str, bool]:
    h = user_home()
    c = json.dumps(read_json(h / ".claude" / "settings.json", {}))
    x = json.dumps(read_json(h / ".codex" / "hooks.json", {}))
    g = (h / ".gemini" / "GEMINI.md")
    return {"Claude Code hooks": "buildinpublic" in c, "Codex hooks": "buildinpublic" in x,
            "Antigravity instructions": g.exists() and BLOCK_START in g.read_text(encoding="utf-8")}
