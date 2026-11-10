#!/usr/bin/env python3
"""Build Your Product in Public: every skill command in one list.

Shows what you can say to your agent, then the scripts you can run yourself. In a terminal,
pick a number, answer only what that script needs, and it runs in this project.
Anywhere else (an agent, a pipe) it prints the list and exits.

Usage: python3 <skill-dir>/scripts/menu.py     (from your project's folder)
"""
import json, os, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

SAY = [
    ("set up build in public", "One-time setup in this project"),
    ("log this", "Add today's log entry now (your agent also does this after tasks)"),
    ("capture this", "Capture the terminal or browser, after asking you"),
    ("build in public brief", "Today's brief with 5 to 7 suggested posts"),
    ("review my posts", "List the suggested posts so you can pick one"),
    ("write post 2 for LinkedIn", "Draft it; revise it, then say \"approve it\""),
    ("I posted it: <link>", "Mark it posted and add it to your story so far"),
    ("weekly recap", "Recap angles from the week"),
    ("build in public help", "This list, from your agent"),
]

# (what it's for, script, args, [questions]). A question is (prompt, flag or None, required, default).
RUN = [
    ("Check", [
        ("Check that everything is set up", "doctor.py", [], []),
        ("Which agent sessions were found for this project", "collect.py", ["--inspect"], []),
    ]),
    ("Captures", [
        ("Capture a command's output (asks before saving)", "capture.py", ["terminal"], [("Command to run, e.g. npm test", "--cmd", True, None)]),
        ("Screenshot your running app (asks before saving)", "capture.py", ["browser"], [("URL", "--url", False, "app_url")]),
        ("Screenshots your agents took, waiting for a yes or no", "capture.py", ["candidates"], []),
        ("Today's approved captures", "capture.py", ["list"], []),
    ]),
    ("Today's gist", [
        ("Run the whole daily pipeline now", "nightly.sh", [], []),
        ("Find this week's trends near your work", "trends.py", [], []),
        ("Preview the gist email (doesn't send)", "notify.py", ["--dry-run"], []),
        ("Send a test email to your address", "notify.py", ["--test"], []),
        ("Rebuild posts/README.md, the page you open on GitHub", "share.py", [], []),
    ]),
    ("Setup", [
        ("Change when the gist arrives", "schedule.sh", [], [("Time, e.g. 19:00", "--time", True, None)]),
        ("Stop the daily gist", "schedule.sh", ["--remove"], []),
        ("Log every commit (git hook)", "init.sh", ["--hook"], []),
        ("Add approved posts and images to your commits", "init.sh", ["--share"], []),
    ]),
]
CONFIRM = {("notify.py", "--test"): "This sends a test email to your address.",
           ("schedule.sh", "--remove"): "This stops the daily gist for this project.",
           ("init.sh", "--share"): "Approved posts and their images will go into your commits. If this repo is public, anyone can read them."}


def entries():
    return [e for _, items in RUN for e in items]


def render():
    L = ["Build Your Product in Public · every command", "", "Say to your agent"]
    w = max(len(p) for p, _ in SAY) + 2
    L += [f"      {chr(34) + p + chr(34):<{w + 2}} {d}" for p, d in SAY]
    L += ["", "Or run a script yourself (from your project's folder)"]
    n = 0
    for group, items in RUN:
        L.append(f"  {group}")
        for label, script, args, _ in items:
            n += 1
            L.append(f"  {n:>2}  {label}")
            L.append(f"      {'sh' if script.endswith('.sh') else 'python3'} $SKILL/scripts/{script} {' '.join(args)}".rstrip())
    return "\n".join(L)


def app_url():
    try:
        return json.loads(Path(".buildinpublic/config.json").read_text()).get("app_url", "")
    except (OSError, ValueError):
        return ""


def ask_args(entry, ask, say):
    label, script, args, qs = entry
    argv = list(args)
    for prompt, flag, required, default in qs:
        default = app_url() if default == "app_url" else default
        while True:
            v = ask(f"  {prompt}{f' (Enter for {default})' if default else ''}: ").strip() or (default or "")
            if v or not required:
                break
            say("  This one's needed (Ctrl-C to go back).")
        if v:
            argv += [flag, v]
    warn = CONFIRM.get((script, *args))
    if warn and ask(f"  {warn} Continue? [y/N] ").strip().lower() not in ("y", "yes"):
        return None
    return argv


def command(script, argv):
    return (["sh"] if script.endswith(".sh") else [sys.executable]) + [str(HERE / script)] + argv


def run(execute=subprocess.call, interactive=None, ask=input, say=print):
    if interactive is None:
        interactive = sys.stdin.isatty() and sys.stdout.isatty()
    say(render())
    say("")
    if not interactive:
        say("Run this in a terminal to pick a script, or just say one of the phrases to your agent.")
        return
    items = entries()
    while True:
        try:
            pick = ask(f"Pick a number (1-{len(items)}), or Enter to quit: ").strip()
        except (EOFError, KeyboardInterrupt):
            say("")
            return
        if not pick:
            return
        if not pick.isdigit() or not 1 <= int(pick) <= len(items):
            say(f"  Pick a number from 1 to {len(items)}.")
            continue
        entry = items[int(pick) - 1]
        try:
            argv = ask_args(entry, ask, say)
        except (EOFError, KeyboardInterrupt):
            say("")
            continue
        if argv is None:
            say("  Skipped.")
            continue
        say(f"\n$ {' '.join(command(entry[1], argv)).replace(str(HERE), '$SKILL/scripts')}\n")
        execute(command(entry[1], argv), cwd=os.getcwd())
        say("")


if __name__ == "__main__":
    run()
