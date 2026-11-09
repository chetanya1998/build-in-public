"""The global journal: every AI coding session, in every project.

~/.buildinpublic/
  projects.json                       discovered projects and their status
  sessions/<project>/<day>-<agent>-<id>/
      meta.json  summary.md  hooks.md  articles.md  shots/
  journal/<day>.md                    one day across all projects
  weekly/<year>-W<week>.md            weekly rollup
"""
from __future__ import annotations

import datetime as dt
import hashlib
import re
import shutil
import subprocess
from pathlib import Path

from . import readers
from .core import (app_home, clip, fmt_minutes, is_excluded, load_config, read_json, redact,
                   save_state, slug, state, today, work_day, write_json)
from .readers import Session

# ---------------------------------------------------------------- projects

def project_root(cwd: str | None) -> str | None:
    if not cwd:
        return None
    p = Path(cwd)
    for parent in [p] + list(p.parents):
        if (parent / ".git").exists():
            return str(parent)
        if parent == parent.parent:
            break
    return str(p)


def git_remote(root: str) -> str:
    try:
        r = subprocess.run(["git", "-C", root, "remote", "get-url", "origin"],
                           capture_output=True, text=True, timeout=5)
        return r.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def load_projects() -> dict:
    return read_json(app_home() / "projects.json", {})


def save_projects(p: dict) -> None:
    write_json(app_home() / "projects.json", p)


def project_key(root: str, projects: dict) -> str:
    for k, v in projects.items():
        if v.get("path") == root:
            return k
    base = slug(Path(root).name or "root")
    if base in projects:
        base = f"{base}-{hashlib.sha1(root.encode()).hexdigest()[:5]}"
    return base


def find_project(name: str) -> tuple[str, dict] | tuple[None, None]:
    projects = load_projects()
    if name in projects:
        return name, projects[name]
    for k, v in projects.items():
        if v.get("name", "").lower() == name.lower() or v.get("path") == name:
            return k, v
    matches = [k for k in projects if name.lower() in k]
    return (matches[0], projects[matches[0]]) if len(matches) == 1 else (None, None)


def set_project(name: str, **fields) -> dict | None:
    key, proj = find_project(name)
    if not key:
        return None
    projects = load_projects()
    projects[key].update(fields)
    save_projects(projects)
    return projects[key]

# ---------------------------------------------------------------- story signals

TAG_RULES = {
    "#war-story": r"\b(traceback|exception|error|failed|failing|bug|crash|broken|stuck|flaky)\b",
    "#metric": r"\d+(\.\d+)?\s?(ms|s|sec|seconds|%|x|kb|mb|gb|users|signups|requests)\b|→|->\s*\d",
    "#decision": r"\b(instead of|trade-?off|decided|chose|switch(ed)? to|migrat(e|ed|ion))\b",
    "#milestone": r"\b(deploy(ed)?|launch(ed)?|release(d)?|first (user|customer|payment|sale)|shipped|went live|v\d+\.\d+)\b",
    "#lesson": r"\b(learned|lesson|turns out|realized|til)\b",
    "#pivot": r"\b(pivot|scrap(ped)?|rewr(o|i)te|start(ed)? over)\b",
}
UI_EXT = {".tsx", ".jsx", ".vue", ".svelte", ".css", ".scss", ".html", ".astro"}


def story_tags(s: Session) -> list[str]:
    text = " ".join(t for _, t in s.messages[-40:]).lower()
    tags = [tag for tag, rx in TAG_RULES.items() if re.search(rx, text, re.I)]
    if s.media or any(Path(f).suffix in UI_EXT for f in s.files_edited):
        tags.append("#visual")
    return tags


def story_score(meta: dict) -> int:
    """0-10: how post-worthy a session looks. Tension, specificity, proof, size."""
    tags = set(meta.get("tags", []))
    score = 0
    score += 3 if "#war-story" in tags else 0
    score += 2 if "#metric" in tags else 0
    score += 2 if "#milestone" in tags else 0
    score += 1 if "#decision" in tags or "#lesson" in tags or "#pivot" in tags else 0
    score += 1 if "#visual" in tags or meta.get("shots") else 0
    score += 1 if len(meta.get("files", [])) >= 3 else 0
    score += 1 if meta.get("minutes", 0) >= 25 else 0
    maint = re.search(r"\b(bump|upgrade deps|lint|format|typo|rename|refactor|cleanup|chore)\b",
                      meta.get("title", "").lower())
    if maint and score < 4:
        score = max(0, score - 1)
    return min(score, 10)


def title_for(s: Session) -> str:
    for role, t in s.messages:
        if role == "user":
            t = re.sub(r"^\[\w+\]\s*", "", t)
            first = t.strip().splitlines()[0] if t.strip() else ""
            if len(first) > 8:
                return clip(first, 90)
    return f"{s.agent} session"

# ---------------------------------------------------------------- capture

def session_dir(key: str, s: Session) -> Path:
    day = work_day(s.started) if s.started else today()
    return app_home() / "sessions" / key / f"{day}-{s.agent}-{s.id[:8]}"


def offlimits_for(proj: dict) -> list[str]:
    items = list(proj.get("offlimits", []))
    n = narrative_path(proj)
    if n and n.exists():
        m = re.search(r"## Off-limits\s*\n(.*?)(\n## |\Z)", n.read_text(encoding="utf-8"), re.S)
        if m:
            items += [i.strip() for i in re.findall(r"[-*]\s*(.+)", re.sub(r"<!--.*?-->", "", m.group(1), flags=re.S))]
    return [i for i in items if 2 < len(i) < 60]


def narrative_path(proj: dict) -> Path | None:
    if not proj:
        return None
    repo_n = Path(proj.get("path", "")) / ".buildinpublic" / "narrative.md"
    if repo_n.exists():
        return repo_n
    return app_home() / "projects" / proj.get("key", "x") / "narrative.md"


def write_session(key: str, proj: dict, s: Session) -> dict:
    d = session_dir(key, s)
    d.mkdir(parents=True, exist_ok=True)
    extra = offlimits_for(proj)
    R = lambda t: redact(t, extra)
    root = proj.get("path", "")
    rel = lambda f: R(f.replace(root.rstrip("/\\") + "/", "").replace(root.rstrip("/\\") + "\\", ""))
    minutes = 0.0
    if s.started and s.ended:
        minutes = min((s.ended - s.started).total_seconds() / 60, 8 * 60)

    # copy screenshots/recordings the agent made
    shots = []
    if s.media:
        sd = d / "shots"
        sd.mkdir(exist_ok=True)
        for m in s.media[:30]:
            src = Path(m)
            dst = sd / f"agent-{src.name}"
            try:
                if not dst.exists():
                    shutil.copy2(src, dst)
                shots.append(dst.name)
            except OSError:
                pass

    meta = {
        "id": s.id, "agent": s.agent, "project": key, "project_name": proj.get("name"),
        "path": root, "source": s.path, "signature": s.signature,
        "day": str(work_day(s.started)) if s.started else str(today()),
        "started": s.started.isoformat() if s.started else None,
        "ended": s.ended.isoformat() if s.ended else None,
        "minutes": round(minutes, 1),
        "title": R(title_for(s)),
        "prompts": [clip(R(t), 300) for r, t in s.messages if r == "user"][:25],
        "outcome": [clip(R(t), 700) for r, t in s.messages if r == "assistant"][-5:],
        "files": [rel(f) for f in s.files_edited][:40],
        "commands": [clip(R(c), 120) for c in s.commands][-15:],
        "browser_urls": sorted(set(s.browser_urls))[:10],
        "tool_calls": len(s.tools),
        "tags": story_tags(s),
        "shots": sorted(set(shots + [p.name for p in (d / "shots").glob("*")] if (d / "shots").exists() else shots)),
    }
    meta["score"] = story_score(meta)
    write_json(d / "meta.json", meta)
    (d / "summary.md").write_text(render_summary(meta), encoding="utf-8")
    return meta


def render_summary(m: dict) -> str:
    L = [f"# {m['title']}", "",
         f"**Project:** {m['project_name']} · **Agent:** {m['agent']} · **Day:** {m['day']} · "
         f"**Time:** {fmt_minutes(m['minutes'])} · **Story score:** {m['score']}/10", ""]
    if m["tags"]:
        L += ["**Story signals:** " + " ".join(m["tags"]), ""]
    if m["prompts"]:
        L += ["## What you asked"] + [f"- {p}" for p in m["prompts"][:12]] + [""]
    if m["outcome"]:
        L += ["## What the agent reported"] + [f"- {o}" for o in m["outcome"]] + [""]
    if m["files"]:
        L += ["## Files changed", ", ".join(f"`{f}`" for f in m["files"][:30]), ""]
    if m["commands"]:
        L += ["## Commands (latest)"] + [f"- `{c}`" for c in m["commands"][-8:]] + [""]
    if m["shots"]:
        L += ["## Screenshots"] + [f"- shots/{s}" for s in m["shots"]] + [""]
    L += [f"_Source: {m['source']}_", ""]
    return "\n".join(L)


def register_project(root: str, s: Session, projects: dict, cfg: dict) -> tuple[str, dict, bool]:
    key = project_key(root, projects)
    new = key not in projects
    if new:
        default = cfg.get("new_project_default", "ask")
        projects[key] = {
            "key": key, "name": Path(root).name or key, "path": root,
            "first_seen": dt.datetime.now().isoformat(timespec="seconds"),
            "status": {"ask": "new", "journal": "journal", "content": "content"}.get(default, "new"),
            "shots": "ask", "agents": [], "sessions": 0, "remote": git_remote(root),
        }
    p = projects[key]
    if s.agent not in p["agents"]:
        p["agents"].append(s.agent)
    ts = (s.ended or s.started)
    if ts and ts.isoformat() > p.get("last_active", ""):
        p["last_active"] = ts.isoformat(timespec="seconds")
    return key, p, new


def capture(sessions: list[Session], quiet: bool = False) -> dict:
    """Write summaries for new or changed sessions. Safe to run any number of times."""
    cfg = load_config()
    st = state()
    seen = st.setdefault("seen", {})
    projects = load_projects()
    report = {"captured": [], "new_projects": [], "skipped_excluded": 0}
    for s in sessions:
        root = project_root(s.cwd) or "unassigned"
        if is_excluded(root, cfg):
            report["skipped_excluded"] += 1
            continue
        uid = f"{s.agent}:{s.id}"
        if seen.get(uid) == s.signature and s.signature:
            continue
        key, proj, new = register_project(root, s, projects, cfg)
        if proj.get("status") == "ignored":
            seen[uid] = s.signature
            continue
        if new:
            report["new_projects"].append(key)
        meta = write_session(key, proj, s)
        if uid not in seen:
            proj["sessions"] = proj.get("sessions", 0) + 1
        seen[uid] = s.signature
        report["captured"].append(f"{key}/{meta['day']}-{s.agent}-{s.id[:8]}")
    save_projects(projects)
    if report["new_projects"]:
        pend = st.setdefault("pending_projects", [])
        pend += [k for k in report["new_projects"] if projects[k]["status"] == "new" and k not in pend]
    save_state(st)
    for day in {c.split("/")[1][:10] for c in report["captured"]}:
        build_day(dt.date.fromisoformat(day))
    if not quiet:
        print(f"Captured {len(report['captured'])} session(s)"
              + (f", new projects: {', '.join(report['new_projects'])}" if report["new_projects"] else ""))
    return report


def sweep(days: int = 2, quiet: bool = False, agents: list[str] | None = None) -> dict:
    since = (dt.datetime.now() - dt.timedelta(days=days)).timestamp()
    rep = capture(readers.all_sessions(since, agents), quiet=quiet)
    apply_retention()
    return rep

# ---------------------------------------------------------------- reading the journal

def all_meta() -> list[dict]:
    out = []
    for f in (app_home() / "sessions").glob("*/*/meta.json"):
        m = read_json(f, None)
        if m:
            m["dir"] = str(f.parent)
            out.append(m)
    return sorted(out, key=lambda m: m.get("started") or "")


def metas_for(day_from: dt.date, day_to: dt.date | None = None, project: str | None = None) -> list[dict]:
    day_to = day_to or day_from
    return [m for m in all_meta()
            if str(day_from) <= m["day"] <= str(day_to) and (not project or m["project"] == project)]


def build_day(day: dt.date) -> Path:
    metas = metas_for(day)
    projects = load_projects()
    by_proj: dict[str, list] = {}
    for m in metas:
        by_proj.setdefault(m["project"], []).append(m)
    total = sum(m["minutes"] for m in metas)
    L = [f"# Journal · {day:%A, %d %B %Y}", "",
         f"{len(metas)} session(s) across {len(by_proj)} project(s) · {fmt_minutes(total)} with AI agents", ""]
    for key, ms in sorted(by_proj.items(), key=lambda kv: -sum(m["minutes"] for m in kv[1])):
        p = projects.get(key, {})
        status = {"content": "content on", "journal": "journal only", "new": "new — not decided"}.get(p.get("status"), "")
        L.append(f"## {p.get('name', key)}  ·  {fmt_minutes(sum(m['minutes'] for m in ms))}  ·  {status}")
        for m in ms:
            t = m["started"][11:16] if m.get("started") else "--:--"
            tags = " ".join(m["tags"])
            L.append(f"- **{t}** [{m['agent']}] {m['title']}  ({fmt_minutes(m['minutes'])}, score {m['score']}) {tags}")
            if m["files"]:
                L.append(f"  - files: {', '.join(m['files'][:6])}{' …' if len(m['files']) > 6 else ''}")
            L.append(f"  - details: {Path(m['dir']).relative_to(app_home()).as_posix()}/summary.md")
        L.append("")
    out = app_home() / "journal" / f"{day}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(L), encoding="utf-8")
    return out


def build_week(day: dt.date | None = None, project: str | None = None) -> Path:
    day = day or today()
    start = day - dt.timedelta(days=day.weekday())
    end = start + dt.timedelta(days=6)
    metas = metas_for(start, end, project)
    projects = load_projects()
    iso = start.isocalendar()
    L = [f"# Week {iso[1]}, {iso[0]} ({start:%d %b} – {end:%d %b})" + (f" · {project}" if project else ""), ""]
    totals: dict[str, float] = {}
    for m in metas:
        totals[m["project"]] = totals.get(m["project"], 0) + m["minutes"]
    L.append(f"{len(metas)} sessions · {fmt_minutes(sum(totals.values()))} · {len(totals)} projects")
    L.append("")
    L.append("| Project | Time | Sessions | Best story |")
    L.append("|---|---|---|---|")
    for key, mins in sorted(totals.items(), key=lambda kv: -kv[1]):
        ms = [m for m in metas if m["project"] == key]
        best = max(ms, key=lambda m: m["score"])
        L.append(f"| {projects.get(key, {}).get('name', key)} | {fmt_minutes(mins)} | {len(ms)} | {best['title']} ({best['score']}/10) |")
    L.append("")
    for d in range(7):
        dd = start + dt.timedelta(days=d)
        ms = [m for m in metas if m["day"] == str(dd)]
        if ms:
            L.append(f"## {dd:%A}")
            L += [f"- [{m['project']}] {m['title']} ({fmt_minutes(m['minutes'])})" for m in ms]
            L.append("")
    name = f"{iso[0]}-W{iso[1]:02d}" + (f"-{project}" if project else "")
    out = app_home() / "weekly" / f"{name}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(L), encoding="utf-8")
    return out


def search(query: str, limit: int = 20) -> list[tuple[dict, str]]:
    q = query.lower()
    hits = []
    for m in reversed(all_meta()):
        text = (Path(m["dir"]) / "summary.md").read_text(encoding="utf-8", errors="ignore")
        if q in text.lower():
            line = next((l for l in text.splitlines() if q in l.lower()), m["title"])
            hits.append((m, clip(line, 160)))
            if len(hits) >= limit:
                break
    return hits


def latest_meta(project: str | None = None, content_only: bool = False) -> dict | None:
    projects = load_projects()
    for m in reversed(all_meta()):
        if project and m["project"] != project:
            continue
        if content_only and projects.get(m["project"], {}).get("status") != "content":
            continue
        return m
    return None


def apply_retention() -> int:
    days = int(load_config().get("retention_days") or 0)
    if days <= 0:
        return 0
    cutoff = str(today() - dt.timedelta(days=days))
    removed = 0
    for m in all_meta():
        if m["day"] < cutoff:
            shutil.rmtree(m["dir"], ignore_errors=True)
            removed += 1
    return removed
