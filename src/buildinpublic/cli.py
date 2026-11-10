"""buildinpublic: command line for Build Your Product in Public."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

from . import __version__, brief, integrations, journal, notify, nudge, readers, research, scheduler, shots
from .core import (agent_dirs, app_home, fmt_minutes, load_config, os_name, python_cmd, save_config,
                   set_config_value, state, today)


def _day(s: str | None) -> dt.date:
    if not s or s == "today":
        return today()
    if s == "yesterday":
        return today() - dt.timedelta(days=1)
    return dt.date.fromisoformat(s)


def _spawn(args: list[str]) -> None:
    """Run a command detached so hooks return instantly (SessionEnd has a ~1.5s budget)."""
    kw: dict = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL, "stdin": subprocess.DEVNULL}
    if os_name() == "windows":
        kw["creationflags"] = 0x00000008 | 0x00000200  # DETACHED_PROCESS | NEW_PROCESS_GROUP
    else:
        kw["start_new_session"] = True
    subprocess.Popen(python_cmd() + args, **kw)

# ---------------------------------------------------------------- commands

def cmd_hook(a):
    raw = ""
    if a.event != "session-start" and sys.stdin and not sys.stdin.isatty():
        raw = sys.stdin.read()
    try:
        data = json.loads(raw) if raw.strip() else {}
    except ValueError:
        data = {}
    if a.event == "claude-end":
        tp = data.get("transcript_path")
        _spawn(["capture", "--path", tp, "--agent", "claude-code"] if tp else ["sweep", "--quiet", "--days", "1"])
    elif a.event == "codex-stop":
        tp = data.get("transcript_path")
        _spawn(["capture", "--path", tp, "--agent", "codex"] if tp else ["sweep", "--quiet", "--days", "1", "--agent", "codex"])
    elif a.event == "session-start":
        try:
            ctx = nudge.session_start_context()
        except Exception:
            ctx = ""
        if ctx:
            print(ctx)


def cmd_capture(a):
    s = readers.read_one(a.path, a.agent)
    if s:
        journal.capture([s], quiet=a.quiet)
    nudge.scan_drafts()


def cmd_sweep(a):
    journal.sweep(days=a.days, quiet=a.quiet, agents=[a.agent] if a.agent else None)
    nudge.scan_drafts()
    if load_config().get("capture") != "nightly":
        nudge.check()


def cmd_today(a):
    day = _day(a.date)
    journal.sweep(days=2, quiet=True)
    f = journal.build_day(day)
    print(f.read_text(encoding="utf-8"))


def cmd_week(a):
    key = None
    if a.project:
        key, _ = journal.find_project(a.project)
        if not key:
            sys.exit(f"Unknown project: {a.project}")
    f = journal.build_week(_day(a.date), key)
    print(f.read_text(encoding="utf-8"))


def cmd_search(a):
    hits = journal.search(" ".join(a.query), a.limit)
    if not hits:
        print("No matches.")
    for m, line in hits:
        print(f"{m['day']}  {m['project']:<22} [{m['agent']}] {m['title']}\n    {line}\n    {m['dir']}/summary.md")


def cmd_projects(a):
    ps = journal.load_projects()
    if not ps:
        print("No projects yet. Run `buildinpublic sweep` after a coding session.")
    for k, p in sorted(ps.items(), key=lambda kv: kv[1].get("last_active", ""), reverse=True):
        print(f"{k:<26} {p.get('status', ''):<8} shots:{p.get('shots', 'ask'):<6} "
              f"{p.get('sessions', 0):>4} sessions  last {p.get('last_active', '')[:10]}  "
              f"{', '.join(p.get('agents', []))}\n    {p.get('path')}")


def cmd_project(a):
    mapping = {"content": {"status": "content"}, "journal": {"status": "journal"}, "ignore": {"status": "ignored"},
               "shots-always": {"shots": "always"}, "shots-ask": {"shots": "ask"}, "shots-never": {"shots": "never"}}
    p = journal.set_project(a.name, **mapping[a.action])
    if not p:
        sys.exit(f"Unknown project: {a.name}. See `buildinpublic projects`.")
    st = state()
    st["pending_projects"] = [k for k in st.get("pending_projects", []) if k != p["key"]]
    from .core import save_state
    save_state(st)
    if a.action == "content":
        n = journal.narrative_path(p)
        if n and not n.exists():
            n.parent.mkdir(parents=True, exist_ok=True)
            tpl = Path(__file__).with_name("templates") / "narrative.md"
            n.write_text(tpl.read_text(encoding="utf-8") if tpl.exists() else "# Narrative\n", encoding="utf-8")
        print(f"{p['name']}: content on. Ask your agent to \"fill the narrative for {p['name']}\" ({n}).")
    else:
        print(f"{p['name']}: {mapping[a.action]}")


def cmd_shot(a):
    if a.clear:
        shots.clear_pending()
        print("Cleared pending screenshot offers.")
        return
    key = journal.find_project(a.project)[0] if a.project else None
    if a.kind == "url":
        files = shots.capture_url(a.target, key)
        print("\n".join(str(f) for f in files))
    elif a.kind == "code":
        if a.target:
            m = journal.latest_meta(key)
            out_dir = Path(m["dir"]) / "shots" if m else app_home() / "shots"
            f = shots.code_image(a.target, out_dir / f"code-{Path(a.target).stem}.png", a.lines, theme=a.theme,
                                 caption=a.caption or "")
        else:
            f = shots.latest_code_shot(key, a.theme)
        print(f or "No recent edited file found. Pass a file: buildinpublic shot code path/to/file.py")
    else:  # auto: whatever is running right now
        found = shots.dev_servers()
        if not found:
            print("No local dev server found. Start your app, or use: buildinpublic shot url <url>")
        for s in found:
            k, _ = shots._project_for(s.get("project_path"))
            print("\n".join(str(f) for f in shots.capture_url(s["url"], k)))


def cmd_watch(a):
    shots.watch(quiet=a.quiet)


def cmd_research(a):
    m = journal.latest_meta(journal.find_project(a.project)[0] if a.project else None)
    if not m:
        sys.exit("No sessions yet.")
    art, hk = research.research_session(Path(m["dir"]), force=True)
    print(art.read_text(encoding="utf-8"))
    print(hk.read_text(encoding="utf-8"))


def cmd_summary(a):
    f = brief.build(_day(a.date), send=a.send, research_on=not a.no_research)
    print(f.read_text(encoding="utf-8"))


def cmd_nudge(a):
    if a.reply:
        print(f"Saved to {nudge.reply(a.reply)}. Ask your agent to turn it into a post.")
    elif a.snooze:
        nudge.snooze(a.hours)
        print(f"Snoozed for {a.hours}h.")
    else:
        t = nudge.check(force=a.force)
        print(t or f"No nudge needed ({nudge.days_since_post()} day(s) since last post).")


def cmd_mark(status):
    def run(a):
        p = nudge.mark(a.id, status)
        print(f"{status}: {p['title']}" if p else f"No draft matching '{a.id}'. See `buildinpublic posts`.")
    return run


def cmd_posts(a):
    nudge.scan_drafts()
    ps = nudge.load_posts()
    if a.id:  # show one draft as clean text, ready to copy
        match = [p for p in ps if a.id in p["id"]] if a.id != "latest" else ps[-1:]
        if not match:
            sys.exit(f"No draft matching '{a.id}'. Run `buildinpublic posts` to see them.")
        p = match[-1]
        text = Path(p["path"]).read_text(encoding="utf-8") if Path(p["path"]).exists() else ""
        print(f"{p['title']}\n{' · '.join(x for x in (p.get('platform'), p['status'], (p.get('created') or '')[:10]) if x)}\n")
        body = text.split("\n---\n", 1)[-1].strip() if text.startswith("---") else text.strip()
        lines = body.splitlines()
        if lines and lines[0].lstrip("# ").strip() == p["title"]:  # the title is already printed above
            body = "\n".join(lines[1:]).strip()
        print(body)
        return
    today = dt.date.today().isoformat()
    if a.today:
        ps = [p for p in ps if (p.get("created") or "").startswith(today)]
    if a.status:
        ps = [p for p in ps if p["status"] == a.status]
    if not ps:
        print(f"No {a.status} drafts." if a.status else "No drafts today." if a.today else "No drafts yet.")
    for p in ps[-a.limit:]:
        print(f"{p['id']:<34} {p['status']:<8} {p['title'][:70]}\n    {p['path']}")
    if ps:
        print("\nShow one: buildinpublic posts <id>")
    n = nudge.days_since_post()
    print("No posts yet." if not any(p["status"] == "posted" for p in nudge.load_posts()) else f"{n} day(s) since your last post.")


def cmd_config(a):
    if a.action == "set":
        set_config_value(a.key, a.value)
        print(f"{a.key} = {a.value}")
        if a.key.split(".")[0] in ("capture", "summary_time", "screenshots", "localhost_check_minutes"):
            print("\n".join(scheduler.install()))
        if a.key == "capture":
            integrations.install_claude_hooks(load_config()["capture"] == "live+hourly")
            integrations.install_codex_hooks(load_config()["capture"] == "live+hourly")
    elif a.action == "path":
        print(app_home() / "config.json")
    else:
        print(json.dumps(load_config(), indent=2))


def cmd_schedule(a):
    if a.action == "remove":
        scheduler.remove()
        print("Removed scheduled jobs.")
    elif a.action == "status":
        print("\n".join(scheduler.status()))
    else:
        print("\n".join(scheduler.install()))


def cmd_setup(a):
    from . import setup
    setup.run(yes=a.yes)


def cmd_install_browser(a):
    if not shots.playwright_ok():
        sys.exit("Playwright isn't installed in this environment: pip install playwright")
    sys.exit(subprocess.call([sys.executable, "-m", "playwright", "install", "chromium"]))


def cmd_uninstall(a):
    scheduler.remove()
    for line in integrations.uninstall_all():
        print(line)
    print(f"Your journal is still in {app_home()}. Delete that folder to remove it too.")


def cmd_doctor(a):
    ok = lambda b: "✓" if b else "✗"
    print(f"Build Your Product in Public {__version__} · {platform.system()} {platform.release()} · Python {platform.python_version()}")
    print(f"Journal: {app_home()}")
    print("\nAgents")
    for name, dirs in agent_dirs().items():
        for d in dirs:
            if d.exists():
                print(f"  {ok(True)} {name}: {d}")
    counts = {}
    for name, fn in readers.READERS.items():
        try:
            counts[name] = len(fn((dt.datetime.now() - dt.timedelta(days=7)).timestamp()))
        except Exception as e:
            counts[name] = f"error: {e}"
    print("  sessions in the last 7 days: " + ", ".join(f"{k} {v}" for k, v in counts.items()))
    print("\nIntegrations")
    for k, v in integrations.hooks_status().items():
        print(f"  {ok(v)} {k}")
    for agent, dest in integrations.skill_targets().items():
        print(f"  {ok((dest / 'build-in-public').exists())} skill in {agent}")
    print("\nSchedule")
    for line in scheduler.status():
        print("  " + line)
    print("\nFeatures")
    print(f"  {ok(shots.playwright_ok())} Playwright (screenshots) "
          + ("" if shots.playwright_ok() else "→ pip install playwright && playwright install chromium"))
    try:
        import psutil  # noqa: F401
        ps = True
    except ImportError:
        ps = False
    print(f"  {ok(ps)} psutil (best localhost detection; optional)")
    cfg = load_config()
    if "email" in cfg["channels"]:
        es = notify.email_settings()
        ready = bool(es.get("to")) and (es["method"] != "smtp" or bool(notify.get_secret("smtp")))
        print(f"  {ok(ready)} email to {es.get('to') or '(no address)'} via {es['method']}")
    st = state()
    print(f"\nPosts: {nudge.days_since_post()} day(s) since last post · {len(nudge.waiting_drafts())} draft(s) waiting")
    if a.test:
        print("\nSending a test notification" + (" and email" if "email" in cfg["channels"] else "") + "…")
        print("  delivered via: " + (", ".join(notify.deliver("Test from Build Your Product in Public",
                                                            "If you see this, notifications work.",
                                                            "# It works\n\nYour daily summary will look like this.")) or "nothing"))

# ---------------------------------------------------------------- parser

def cmd_menu(a) -> None:
    from . import menu
    menu.run(main)


def utf8_output() -> None:
    """Windows writes to pipes (agents, hooks, redirects) in cp1252, which can't encode the
    check marks and dots this CLI prints, so setup crashed when an agent ran it."""
    for stream in (sys.stdout, sys.stderr):
        enc = (getattr(stream, "encoding", "") or "").lower().replace("-", "")
        if enc != "utf8" and hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def main(argv=None):
    utf8_output()
    if argv is None:
        argv = sys.argv[1:]
    if not argv or argv[0] in ("?", "help?", "-?", "-h", "--help"):  # show every command, not usage text
        argv = ["menu"]
    p = argparse.ArgumentParser(prog="buildinpublic", description="Build Your Product in Public: journal every AI coding session and turn it into posts.")
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("menu", aliases=["help"], help="every command in one list: pick a number to run it").set_defaults(fn=cmd_menu)
    s = sub.add_parser("setup", help="guided setup: capture timing, summary time, Gmail, hooks, schedule")
    s.add_argument("--yes", action="store_true", help="accept defaults, no questions")
    s.set_defaults(fn=cmd_setup)
    sub.add_parser("install-browser", help="download Chromium for screenshots (Playwright)").set_defaults(fn=cmd_install_browser)
    sub.add_parser("uninstall", help="remove hooks, skill and schedule (keeps your journal)").set_defaults(fn=cmd_uninstall)
    s = sub.add_parser("doctor", help="check that everything works on this machine")
    s.add_argument("--test", action="store_true", help="send a test notification/email")
    s.set_defaults(fn=cmd_doctor)

    s = sub.add_parser("hook", help=argparse.SUPPRESS)
    s.add_argument("event", choices=["claude-end", "codex-stop", "session-start"])
    s.set_defaults(fn=cmd_hook)
    s = sub.add_parser("capture", help="capture one session file")
    s.add_argument("--path", required=True)
    s.add_argument("--agent")
    s.add_argument("--quiet", action="store_true")
    s.set_defaults(fn=cmd_capture)
    s = sub.add_parser("sweep", help="capture all new sessions")
    s.add_argument("--days", type=int, default=2)
    s.add_argument("--agent")
    s.add_argument("--quiet", action="store_true")
    s.set_defaults(fn=cmd_sweep)

    s = sub.add_parser("today", help="today's journal across all projects")
    s.add_argument("date", nargs="?")
    s.set_defaults(fn=cmd_today)
    s = sub.add_parser("week", help="weekly rollup")
    s.add_argument("--project")
    s.add_argument("--date")
    s.set_defaults(fn=cmd_week)
    s = sub.add_parser("search", help="search every past session")
    s.add_argument("query", nargs="+")
    s.add_argument("--limit", type=int, default=20)
    s.set_defaults(fn=cmd_search)
    sub.add_parser("projects", help="list discovered projects").set_defaults(fn=cmd_projects)
    s = sub.add_parser("project", help="set a project's mode")
    s.add_argument("name")
    s.add_argument("action", choices=["content", "journal", "ignore", "shots-always", "shots-ask", "shots-never"])
    s.set_defaults(fn=cmd_project)

    s = sub.add_parser("shot", help="capture a screenshot: url | code | auto")
    s.add_argument("kind", nargs="?", choices=["url", "code", "auto"], default="auto")
    s.add_argument("target", nargs="?")
    s.add_argument("--lines", help="e.g. 10-40 (code)")
    s.add_argument("--theme", default="dusk", choices=list(shots.THEMES))
    s.add_argument("--caption")
    s.add_argument("--project")
    s.add_argument("--clear", action="store_true", help="clear pending screenshot offers")
    s.set_defaults(fn=cmd_shot)
    s = sub.add_parser("watch", help="look for localhost servers / agent browser tests and offer screenshots")
    s.add_argument("--quiet", action="store_true")
    s.set_defaults(fn=cmd_watch)
    s = sub.add_parser("research", help="related articles + hooks for the latest session")
    s.add_argument("--project")
    s.set_defaults(fn=cmd_research)

    s = sub.add_parser("summary", help="build (and optionally send) the daily summary")
    s.add_argument("--date")
    s.add_argument("--send", action="store_true")
    s.add_argument("--no-research", action="store_true")
    s.set_defaults(fn=cmd_summary)
    s = sub.add_parser("nudge", help="check / answer / snooze the posting reminder")
    s.add_argument("--reply")
    s.add_argument("--snooze", action="store_true")
    s.add_argument("--hours", type=int, default=24)
    s.add_argument("--force", action="store_true")
    s.set_defaults(fn=cmd_nudge)
    for name, status in (("posted", "posted"), ("skipped", "skipped")):
        s = sub.add_parser(name, help=f"mark a draft as {status}")
        s.add_argument("id", nargs="?", default="latest")
        s.set_defaults(fn=cmd_mark(status))
    s = sub.add_parser("posts", help="list drafts (--today, --status), or show one: posts <id>")
    s.add_argument("id", nargs="?", help="show this draft (any part of its id, or 'latest')")
    s.add_argument("--today", action="store_true", help="only drafts written today")
    s.add_argument("--status", choices=["drafted", "posted", "skipped"])
    s.add_argument("--limit", type=int, default=20)
    s.set_defaults(fn=cmd_posts)

    s = sub.add_parser("config", help="show or change settings")
    s.add_argument("action", nargs="?", choices=["show", "set", "path"], default="show")
    s.add_argument("key", nargs="?")
    s.add_argument("value", nargs="?")
    s.set_defaults(fn=cmd_config)
    s = sub.add_parser("schedule", help="install / remove / status of background jobs")
    s.add_argument("action", nargs="?", choices=["install", "remove", "status"], default="status")
    s.set_defaults(fn=cmd_schedule)

    a = p.parse_args(argv)
    if a.cmd == "config" and a.action == "set" and (not a.key or a.value is None):
        p.error("usage: buildinpublic config set <key> <value>")
    a.fn(a)


if __name__ == "__main__":
    main()
