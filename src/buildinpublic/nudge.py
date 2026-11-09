"""Post tracking and the interactive nudge.

posts.json tracks every draft: drafted → posted | skipped.
When nothing has been posted for `nudge_after_days`, a nudge is written to
~/.buildinpublic/nudge.md and delivered (notification / email). The next time
you open Claude Code, Codex or Antigravity, the agent reads it and asks you,
conversationally: post the waiting draft? what are you working on? low-effort idea?
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

from . import journal, notify
from .core import app_home, load_config, read_json, save_state, slug, state, today, write_json

POSTS = lambda: app_home() / "posts.json"


def load_posts() -> list[dict]:
    return read_json(POSTS(), [])


def save_posts(p: list[dict]) -> None:
    write_json(POSTS(), p)


def register_draft(path: Path, project: str | None, title: str, session: str | None = None,
                   platform: str = "") -> dict:
    posts = load_posts()
    rel = str(Path(path).resolve())
    for p in posts:
        if p["path"] == rel:
            return p
    pid = f"{dt.date.today():%m%d}-{slug(title, 24)}"
    item = {"id": pid, "path": rel, "project": project, "title": title, "session": session,
            "platform": platform, "status": "drafted",
            "created": dt.datetime.now().isoformat(timespec="seconds")}
    posts.append(item)
    save_posts(posts)
    return item


def scan_drafts() -> int:
    """Register any draft files the agent wrote into ~/.buildinpublic/posts/."""
    n = 0
    known = {p["path"] for p in load_posts()}
    for f in sorted((app_home() / "posts").glob("*.md")):
        if str(f.resolve()) not in known:
            first = next((l.lstrip("# ").strip() for l in f.read_text(encoding="utf-8").splitlines() if l.strip()), f.stem)
            parts = f.stem.split("-")
            register_draft(f, None, first[:80], platform=parts[3] if len(parts) > 3 else "")
            n += 1
    return n


def mark(ident: str, status: str) -> dict | None:
    posts = load_posts()
    target = None
    if ident in ("latest", "last"):
        waiting = [p for p in posts if p["status"] == "drafted"]
        target = waiting[-1] if waiting else None
    else:
        target = next((p for p in posts if p["id"] == ident or ident.lower() in p["title"].lower()), None)
    if not target:
        return None
    target["status"] = status
    target[f"{status}_at"] = dt.datetime.now().isoformat(timespec="seconds")
    save_posts(posts)
    if status == "posted":
        st = state()
        st["last_posted"] = target[f"{status}_at"]
        st.pop("nudge_active", None)
        save_state(st)
        (app_home() / "nudge.md").unlink(missing_ok=True)
    return target


def days_since_post() -> int:
    st = state()
    last = st.get("last_posted") or st.get("installed_at")
    if not last:
        st["installed_at"] = dt.datetime.now().isoformat(timespec="seconds")
        save_state(st)
        return 0
    return (dt.datetime.now() - dt.datetime.fromisoformat(last)).days


def waiting_drafts() -> list[dict]:
    return [p for p in load_posts() if p["status"] == "drafted"]


FALLBACKS = [
    "A 'what I'm building and why' post: one paragraph on the problem, one screenshot.",
    "A lesson from this week, even a small one: 'I thought X, turns out Y.'",
    "A question for your audience about a decision you're facing right now.",
    "A behind-the-scenes look at your setup: how you work with your AI agents.",
]


def check(force: bool = False) -> str | None:
    """Create and deliver a nudge if the threshold has passed. Returns the nudge text."""
    cfg = load_config()
    days = days_since_post()
    limit = int(cfg.get("nudge_after_days", 2))
    st = state()
    if not force:
        if days < limit:
            return None
        if st.get("nudge_snoozed_until") and st["nudge_snoozed_until"] > dt.datetime.now().isoformat():
            return None
        if st.get("nudge_sent_day") == str(today()):
            return (app_home() / "nudge.md").read_text(encoding="utf-8") if (app_home() / "nudge.md").exists() else None
    last = journal.latest_meta(content_only=True) or journal.latest_meta()
    drafts = waiting_drafts()
    L = ["# Build Your Product in Public · nudge", "",
         f"It's been **{days} day(s)** since your last post." if days else "Time for a post?", ""]
    L.append("Ask the user these, one at a time, and keep it light:")
    q = 1
    if drafts:
        d = drafts[-1]
        L.append(f"{q}. \"A draft is ready: **{d['title']}**. Want to post it, edit it, or skip it?\" "
                 f"(draft file: {d['path']}; mark with `buildinpublic posted {d['id']}` or `buildinpublic skipped {d['id']}`)")
        q += 1
    if last:
        L.append(f"{q}. \"Your last session was **{last['title']}** in {last.get('project_name')} "
                 f"({last['day']}). Want me to turn it into a post?\" "
                 f"(summary: {Path(last['dir']) / 'summary.md'}; hooks: {Path(last['dir']) / 'hooks.md'})")
        q += 1
    L.append(f"{q}. \"Nothing post-worthy lately? What are you working on right now?\" Their answer becomes a "
             "'what I'm building' post. Save it with `buildinpublic nudge --reply \"<answer>\"`.")
    q += 1
    L.append(f"{q}. If they're not coding at the moment, offer one of these low-effort posts:")
    L += [f"   - {f}" for f in FALLBACKS[:3]]
    L += ["", "If they say not now: `buildinpublic nudge --snooze`."]
    text = "\n".join(L) + "\n"
    (app_home() / "nudge.md").write_text(text, encoding="utf-8")
    st["nudge_active"] = True
    st["nudge_sent_day"] = str(today())
    save_state(st)
    short = (f"No post in {days} days. " + (f"Draft waiting: {drafts[-1]['title'][:60]}" if drafts else
             f"Last session: {last['title'][:60]}" if last else "Tell me what you're building."))
    notify.deliver("Time to build in public", short, text)
    return text


def snooze(hours: int = 24) -> None:
    st = state()
    st["nudge_snoozed_until"] = (dt.datetime.now() + dt.timedelta(hours=hours)).isoformat(timespec="seconds")
    st.pop("nudge_active", None)
    save_state(st)
    (app_home() / "nudge.md").unlink(missing_ok=True)


def reply(answer: str) -> Path:
    """Save the user's 'what I'm working on' answer as material for a post."""
    d = app_home() / "inbox"
    d.mkdir(parents=True, exist_ok=True)
    f = d / f"{dt.date.today()}.md"
    with f.open("a", encoding="utf-8") as fh:
        fh.write(f"- {dt.datetime.now():%H:%M} {answer.strip()}\n")
    snooze(12)
    return f


def session_start_context() -> str:
    """What the SessionStart hook prints: active nudge, new projects, pending screenshots."""
    st = state()
    parts = []
    nudge = app_home() / "nudge.md"
    shown = st.get("nudge_shown_at", "")
    recent = shown and dt.datetime.fromisoformat(shown) > dt.datetime.now() - dt.timedelta(hours=4)
    if st.get("nudge_active") and nudge.exists() and not recent:
        parts.append(nudge.read_text(encoding="utf-8"))
        st["nudge_shown_at"] = dt.datetime.now().isoformat(timespec="seconds")
    projects = journal.load_projects()
    pend = [k for k in st.get("pending_projects", []) if projects.get(k, {}).get("status") == "new"]
    if pend:
        names = ", ".join(f"{projects[k]['name']} ({projects[k]['path']})" for k in pend[:5])
        parts.append("## New projects found by Build Your Product in Public\n"
                     f"Ask the user once: should these be **journal only**, **content on** (used for posts), "
                     f"or **ignored**? {names}\nThen run `buildinpublic project <name> journal|content|ignore`.")
    shots = st.get("pending_shots", [])
    if shots:
        s = shots[-1]
        parts.append("## Screenshot offer\n"
                     f"Earlier, {s['url']} was running ({s.get('via')}). Ask the user if they want screenshots for "
                     f"a post. If yes: `buildinpublic shot url {s['url']}`. Then `buildinpublic shot --clear`.")
    save_state(st)
    if not parts:
        return ""
    return ("<build-in-public>\n" + "\n\n".join(parts) +
            "\nBring this up briefly at the start, then continue with what the user asked.\n"
            "</build-in-public>")
