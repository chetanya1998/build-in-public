"""`buildinpublic menu` (or just `buildinpublic`): every command in one numbered list.

In a terminal you pick a number, answer only the questions that command needs, and it runs.
Anywhere else (an agent, a pipe) it prints the list and exits, so it never waits for input.
"""
from __future__ import annotations

import sys
from typing import Callable

# (what it's for, args, [questions]). A question is (prompt, flag or None for positional,
# required, choices or None). Commands that change or remove things ask to confirm.
Q = tuple
MENU: list[tuple[str, list[tuple[str, list[str], list[Q]]]]] = [
    ("Your journal", [
        ("What you did today, across every project", ["today"], [("Which day (YYYY-MM-DD)? Enter for today", None, False, None)]),
        ("This week: time per project and the best story", ["week"], [("Only one project? Its name, or Enter for all", "--project", False, None)]),
        ("Search every past session", ["search"], [("Search for", None, True, None)]),
        ("Projects it found, and what each is used for", ["projects"], []),
        ("Capture new sessions now (normally runs every hour)", ["sweep"], []),
    ]),
    ("Posts and reminders", [
        ("Build today's summary (doesn't send it)", ["summary"], []),
        ("Build today's summary and send it now", ["summary", "--send"], []),
        ("All your drafts, and which are posted", ["posts"], []),
        ("Today's drafts", ["posts", "--today"], []),
        ("Show one draft, ready to copy", ["posts"], [("Which draft? Its id, or Enter for the latest", None, False, None)]),
        ("Mark a draft as posted (resets the reminder)", ["posted"], [("Which draft? Its id, or Enter for the latest", None, False, None)]),
        ("Check the posting reminder", ["nudge"], []),
        ("Tell it what you're working on, for a post", ["nudge"], [("What are you working on", "--reply", True, None)]),
        ("Snooze the reminder for a day", ["nudge", "--snooze"], []),
    ]),
    ("Screenshots and research", [
        ("Screenshot your running app", ["shot", "url"], [("URL, e.g. http://localhost:3000", None, True, None)]),
        ("Make an image of some code", ["shot", "code"], [("File", None, True, None),
                                                         ("Lines, e.g. 20-48 (Enter for all)", "--lines", False, None),
                                                         ("Caption (Enter for none)", "--caption", False, None)]),
        ("Look for running apps and browser tests to screenshot", ["watch"], []),
        ("Related articles and post openers for your latest session", ["research"], []),
    ]),
    ("Projects", [
        ("Choose what a project is used for", ["project"], [
            ("Project name (see 'Projects it found')", None, True, None),
            ("Use it for", None, True, ["content", "journal", "ignore", "shots-always", "shots-ask", "shots-never"])]),
    ]),
    ("Setup and upkeep", [
        ("Check that everything works", ["doctor"], []),
        ("Send a test notification and email", ["doctor", "--test"], []),
        ("Run setup again (questions, hooks, schedule)", ["setup"], []),
        ("Background jobs: are they scheduled?", ["schedule", "status"], []),
        ("Show your settings", ["config", "show"], []),
        ("Download the browser used for screenshots", ["install-browser"], []),
        ("Uninstall: remove hooks, skill and schedule (keeps your journal)", ["uninstall"], []),
    ]),
]
CONFIRM = {("uninstall",): "This removes the agent hooks, the skill and the schedule. Your journal stays.",
           ("summary", "--send"): "This sends today's summary to your notification and email now.",
           ("doctor", "--test"): "This sends a test notification, and a test email if you set one up."}


def entries() -> list[tuple[str, list[str], list[Q]]]:
    return [e for _, items in MENU for e in items]


def render() -> str:
    lines, n = ["Build Your Product in Public · every command", ""], 0
    for group, items in MENU:
        lines.append(group)
        for label, args, qs in items:
            n += 1
            needs = " <" + "> <".join(q[0].split(",")[0].split("?")[0].split(" (")[0].lower() for q in qs if q[2]) + ">" if any(q[2] for q in qs) else ""
            lines.append(f"  {n:>2}  {label}")
            lines.append(f"      buildinpublic {' '.join(args)}{needs}")
        lines.append("")
    return "\n".join(lines)


def ask_args(entry, ask: Callable[[str], str], say: Callable[[str], None]) -> list[str] | None:
    """The command's argv, after asking only for what it needs; None if the user backs out."""
    label, args, qs = entry
    argv = list(args)
    for prompt, flag, required, choices in qs:
        if choices:
            say("  " + "  ".join(f"{i}) {c}" for i, c in enumerate(choices, 1)))
        while True:
            v = ask(f"  {prompt}: ").strip()
            if choices and v.isdigit() and 1 <= int(v) <= len(choices):
                v = choices[int(v) - 1]
            if choices and v and v not in choices:
                say(f"  Pick 1-{len(choices)}.")
                continue
            if v or not required:
                break
            say("  This one's needed (Ctrl-C to go back).")
        if v:
            argv += ([flag, v] if flag else v.split() if args[0] == "search" else [v])
    warn = CONFIRM.get(tuple(args))
    if warn and ask(f"  {warn} Continue? [y/N] ").strip().lower() not in ("y", "yes"):
        return None
    return argv


def run(dispatch: Callable[[list[str]], None], interactive: bool | None = None,
        ask: Callable[[str], str] = input, say: Callable[[str], None] = print) -> None:
    if interactive is None:
        interactive = sys.stdin.isatty() and sys.stdout.isatty()
    say(render())
    if not interactive:
        say("Run `buildinpublic menu` in a terminal to pick one, or ask your agent: \"build in public help\".")
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
        try:
            argv = ask_args(items[int(pick) - 1], ask, say)
        except (EOFError, KeyboardInterrupt):
            say("")
            continue
        if argv is None:
            say("  Skipped.")
            continue
        say(f"\n$ buildinpublic {' '.join(argv)}\n")
        try:
            dispatch(argv)
        except SystemExit:
            pass
        say("")
