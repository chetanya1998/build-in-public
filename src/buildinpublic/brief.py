"""The daily summary: every project's sessions, the best story, hooks, related
reading, screenshots, ready drafts, and an honest 'no strong story' when that's
the truth. Delivered by notification and/or Gmail at summary_time.
"""
from __future__ import annotations

import datetime as dt
import re
import shutil
import subprocess
from pathlib import Path

from . import journal, notify, nudge, research
from .core import app_home, fmt_minutes, load_config, state, today
from .shots import pending as pending_shots

STRONG = 4  # story score needed before we write drafts


def no_story_reasons(metas: list[dict], content_keys: set[str]) -> list[str]:
    if not metas:
        return ["No AI coding sessions were recorded today."]
    r = []
    if not any(m["project"] in content_keys for m in metas):
        r.append("Today's work was only in journal-only projects (content is off for them).")
    maint = [m for m in metas if re.search(r"\b(bump|deps|lint|format|typo|rename|refactor|cleanup|chore|fix tests?)\b",
                                            m["title"].lower())]
    if len(maint) >= max(1, len(metas) // 2):
        r.append(f"{len(maint)} of {len(metas)} sessions look like maintenance (refactors, deps, cleanup).")
    if not any("#metric" in m["tags"] for m in metas):
        r.append("No measurable result (a number, a before/after).")
    if not any(m.get("shots") or "#visual" in m["tags"] for m in metas):
        r.append("Nothing visual captured (no screenshot or UI change).")
    if sum(m["minutes"] for m in metas) < 30:
        r.append("Short day: under 30 minutes with agents.")
    return r or ["Sessions were small and didn't produce a clear story."]


def _agent_cmd(cfg: dict) -> list[str] | None:
    choice = cfg.get("draft_agent", "auto")
    if choice in ("auto", "claude") and shutil.which("claude"):
        return ["claude", "-p", "{prompt}", "--allowedTools", "Read,Write,Edit,Glob,Grep,WebSearch,WebFetch"]
    if choice in ("auto", "codex") and shutil.which("codex"):
        return ["codex", "exec", "--full-auto", "{prompt}"]
    return None


def write_drafts(day: dt.date, picks: list[dict], cfg: dict) -> tuple[list[dict], str]:
    posts = app_home() / "posts"
    posts.mkdir(exist_ok=True)
    before = {p["path"] for p in nudge.load_posts()}
    cmd = _agent_cmd(cfg)
    how = "template"
    if cmd:
        dirs = "\n".join(f"- {m['dir']} (project: {m['project_name']})" for m in picks)
        prompt = (f"Use the build-in-public skill (Mode 6, global journal). Write drafts for {day} following its Mode 5 draft rules. "
                  f"Session folders (summary.md, hooks.md, articles.md, shots/):\n{dirs}\n"
                  f"Platforms: {', '.join(cfg.get('platforms', ['x', 'linkedin']))}. "
                  f"Write 1-2 drafts per platform into {posts} named {day}-<project>-<platform>-<slug>.md. "
                  "Never post anything.")
        try:
            subprocess.run([prompt if c == "{prompt}" else c for c in cmd], cwd=str(app_home()),
                           capture_output=True, text=True, timeout=900)
            how = cmd[0]
        except (OSError, subprocess.SubprocessError):
            cmd = None
    nudge.scan_drafts()
    new = [p for p in nudge.load_posts() if p["path"] not in before]
    if not new:  # no agent, or agent wrote nothing: leave a starter the user can finish in any agent
        m = picks[0]
        hooks = (Path(m["dir"]) / "hooks.md").read_text(encoding="utf-8") if (Path(m["dir"]) / "hooks.md").exists() else ""
        first_hook = next((l[2:].split("  _")[0] for l in hooks.splitlines() if l.startswith("- ")), m["title"])
        f = posts / f"{day}-{m['project']}-starter-{journal.slug(m['title'], 30)}.md"
        f.write_text(f"# {first_hook}\n\n"
                     f"<!-- Starter draft. Ask your agent: \"finish this post with build-in-public\" -->\n\n"
                     f"**The problem:** {m['prompts'][0] if m['prompts'] else m['title']}\n\n"
                     f"**What I did:** {m['outcome'][-1][:400] if m['outcome'] else ''}\n\n"
                     f"**What's next:** …\n\nSource: {m['dir']}/summary.md\n", encoding="utf-8")
        new = [nudge.register_draft(f, m["project"], first_hook, session=m["id"])]
        how = "starter"
    return new, how


def build(day: dt.date | None = None, send: bool = False, research_on: bool | None = None) -> Path:
    day = day or today()
    cfg = load_config()
    journal.sweep(days=2, quiet=True)
    metas = journal.metas_for(day)
    projects = journal.load_projects()
    content = {k for k, v in projects.items() if v.get("status") == "content"}
    research_on = cfg.get("research", True) if research_on is None else research_on

    ranked = sorted(metas, key=lambda m: (m["project"] in content, m["score"], m["minutes"]), reverse=True)
    picks = [m for m in ranked if m["project"] in content][:3]
    if research_on:
        for m in (picks or ranked)[:3]:
            research.research_session(Path(m["dir"]))

    best = picks[0] if picks else None
    strong = bool(best and best["score"] >= STRONG)
    L = [f"# Your day in public · {day:%a %d %b %Y}", ""]
    total = sum(m["minutes"] for m in metas)
    by_proj: dict[str, list] = {}
    for m in metas:
        by_proj.setdefault(m["project"], []).append(m)
    L.append(f"**{len(metas)} sessions · {len(by_proj)} projects · {fmt_minutes(total)} with AI agents**")
    L.append("")
    L.append("## Where your time went")
    for k, ms in sorted(by_proj.items(), key=lambda kv: -sum(m["minutes"] for m in kv[1])):
        p = projects.get(k, {})
        flag = {"content": "", "journal": " · journal only", "new": " · new project"}.get(p.get("status"), "")
        L.append(f"- **{p.get('name', k)}**: {fmt_minutes(sum(m['minutes'] for m in ms))}, {len(ms)} session(s){flag}")
        for m in ms[:4]:
            L.append(f"  - {m['title']} [{m['agent']}] {' '.join(m['tags'])}")
    L.append("")

    drafts = []
    if strong:
        L += [f"## Today's story: {best['title']}",
              f"{best.get('project_name')} · score {best['score']}/10 · {' '.join(best['tags'])}", ""]
        d = Path(best["dir"])
        if (d / "hooks.md").exists():
            hooks = [l for l in (d / "hooks.md").read_text(encoding="utf-8").splitlines() if l.startswith("- ")]
            L += ["**Hooks to open with**"] + hooks[:4] + [""]
        if (d / "articles.md").exists():
            arts = [l for l in (d / "articles.md").read_text(encoding="utf-8").splitlines() if l.startswith("- [")]
            if arts:
                L += ["**What people are reading about this**"] + arts[:4] + [""]
        shots = sorted((d / "shots").glob("*.png")) if (d / "shots").exists() else []
        if shots:
            L += ["**Screenshots ready**"] + [f"- {s}" for s in shots[:4]] + [""]
        drafts, how = write_drafts(day, picks, cfg)
        L += ["## Drafts waiting for you"] + [f"- {p['title']} → {p['path']}" for p in drafts] + \
             [f"_Mark when done: `buildinpublic posted <id>` · drafted by {how}_", ""]
        if len(picks) > 1:
            L += ["## Also worth a post"] + [f"- {m['title']} ({m['project_name']}, {m['score']}/10)" for m in picks[1:]] + [""]
    else:
        L += ["## No strong story today", "That's normal. Here's why, and what to post instead:", ""]
        L += [f"- {r}" for r in no_story_reasons(metas, content)] + [""]
        hidden = next((m for m in ranked if m["project"] not in content and m["score"] >= STRONG), None)
        if hidden:
            L += [f"**There's a story in a journal-only project:** {hidden['title']} ({hidden['project_name']}, "
                  f"{hidden['score']}/10). Turn content on to get drafts: "
                  f"`buildinpublic project {hidden['project']} content`", ""]
        L += ["**Low-effort posts that still work**"] + [f"- {f}" for f in nudge.FALLBACKS] + [""]
        L += ["**Capture tomorrow**",
              "- One number: time, size, speed, users. Anything with a before and after.",
              "- One screenshot of whatever you're building: say \"capture this\" to your agent.", ""]

    st = state()
    pend = [k for k in st.get("pending_projects", []) if projects.get(k, {}).get("status") == "new"]
    if pend:
        L += ["## New projects found"] + [f"- {projects[k]['name']} ({projects[k]['path']}): "
                                          f"`buildinpublic project {k} content|journal|ignore`" for k in pend] + [""]
    if pending_shots():
        L += ["## Screenshots waiting for your OK"] + [f"- {s['url']} ({s.get('via')}): `buildinpublic shot url {s['url']}`"
                                                       for s in pending_shots()] + [""]
    waiting = nudge.waiting_drafts()
    if waiting and not drafts:
        L += ["## Drafts still waiting"] + [f"- {p['title']} ({p['id']})" for p in waiting[-3:]] + [""]
    L.append(f"_Full journal: {app_home() / 'journal' / f'{day}.md'}_")
    text = "\n".join(L) + "\n"
    out = app_home() / "summaries" / f"{day}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")

    if send:
        short = (f"{best['title'][:70]} · {len(drafts)} draft(s) ready" if strong else
                 f"{len(metas)} sessions, no strong story today. Fallback ideas inside.")
        atts = [str(s) for s in (sorted((Path(best['dir']) / 'shots').glob('*.png'))[:2] if strong and (Path(best['dir']) / 'shots').exists() else [])]
        notify.deliver(f"Your day in public · {day:%d %b}", short, text, atts)
        nudge.check()
    return out
