"""`buildinpublic setup`: a short Q&A, then hooks, schedule and a first sweep.
Re-run any time to change answers (or use `buildinpublic config set`).
"""
from __future__ import annotations

import datetime as dt
import getpass
import re

from . import integrations, journal, notify, scheduler
from .core import app_home, load_config, os_name, save_config, save_state, state


def _ask(q: str, default: str, choices: list[str] | None = None) -> str:
    hint = f" [{'/'.join(choices)}]" if choices else ""
    while True:
        try:
            a = input(f"{q}{hint} (default: {default}): ").strip()
        except EOFError:
            return default
        if not a:
            return default
        if not choices or a in choices:
            return a
        print(f"  please pick one of: {', '.join(choices)}")


def run(yes: bool = False) -> None:
    cfg = load_config()
    print("\nBuild Your Product in Public · setup\n")
    print(f"Journal folder: {app_home()}   ({os_name()})")
    det = integrations.detected_agents()
    print("Agents found: " + ", ".join(f"{a} {'✓' if ok else '–'}" for a, ok in det.items()) + "\n")

    if not yes:
        print("1) When should sessions be captured?")
        print("   live    = right after each session (hooks) + hourly safety sweep")
        print("   hourly  = every hour")
        print("   nightly = once, just before your summary")
        cap = _ask("  capture", {"live+hourly": "live"}.get(cfg["capture"], cfg["capture"]), ["live", "hourly", "nightly"])
        cfg["capture"] = "live+hourly" if cap == "live" else cap

        t = _ask("2) What time should your daily summary arrive? (24h HH:MM)", cfg["summary_time"])
        cfg["summary_time"] = t if re.match(r"^\d{1,2}:\d{2}$", t) else "00:00"

        ch = _ask("3) Where should it arrive?", "+".join(cfg["channels"]) if len(cfg["channels"]) == 1 else "both",
                  ["notification", "email", "both"])
        cfg["channels"] = ["notification", "email"] if ch == "both" else [ch]
        if "email" in cfg["channels"]:
            addr = _ask("   Your email address", cfg["email"].get("to") or "")
            cfg["email"].update({"to": addr})
            from .core import read_json, user_home, write_json
            shared = user_home() / ".config" / "buildinpublic" / "email.json"
            write_json(shared, {**read_json(shared, {}), "to": addr})
            if os_name() == "mac":
                print("   Sent through Apple Mail from your default account: no password needed.")
            elif os_name() == "linux" and notify.email_settings()["method"] == "sendmail":
                print("   Sent through your system's sendmail: no password needed.")
            else:
                print("   Windows has no mail app to send through, so this uses Gmail with an app password:")
                print("   Google Account → Security → 2-Step Verification → App passwords.")
                cfg["email"].update({"from": addr, "method": "smtp"})
                pw = getpass.getpass("   App password (hidden, Enter to keep the current one): ").strip()
                if pw:
                    try:
                        print(f"   saved securely in {notify.set_secret('smtp', pw.replace(' ', ''))}")
                    except RuntimeError as e:
                        print(f"   ! {e}")

        cfg["screenshots"] = _ask("4) Offer to screenshot your app when you test on localhost? (always asks first)",
                                  cfg["screenshots"], ["ask", "never"])
        n = _ask("5) Remind you after how many days without a post?", str(cfg["nudge_after_days"]))
        cfg["nudge_after_days"] = int(n) if n.isdigit() else 2
        cfg["new_project_default"] = _ask("6) New projects: ask me, journal only, or content on?",
                                          cfg["new_project_default"], ["ask", "journal", "content"])
        ex = _ask("7) Folders never to record (comma separated globs, e.g. ~/work/client-*)",
                  ",".join(cfg["exclude"]) or "none")
        cfg["exclude"] = [] if ex == "none" else [e.strip() for e in ex.split(",") if e.strip()]
        pl = _ask("8) Platforms you post on (comma separated: x, linkedin, threads, reddit, devto, bluesky)",
                  ",".join(cfg["platforms"]))
        cfg["platforms"] = [p.strip().lower() for p in pl.split(",") if p.strip()]

    save_config(cfg)
    st = state()
    st.setdefault("installed_at", dt.datetime.now().isoformat(timespec="seconds"))
    save_state(st)

    print("\nConnecting agents…")
    for line in integrations.install_all(live=cfg["capture"] == "live+hourly"):
        print("  " + line)
    print("Scheduling…")
    for line in scheduler.install(cfg):
        print("  " + line)
    print("First sweep (last 14 days)…")
    rep = journal.sweep(days=14, quiet=True)
    projects = journal.load_projects()
    print(f"  {len(rep['captured'])} sessions in {len(projects)} projects")
    if not yes and cfg["new_project_default"] == "ask" and projects:
        print("\nWhich projects should produce posts? (others stay journal only)")
        for k, p in sorted(projects.items(), key=lambda kv: kv[1].get("last_active", ""), reverse=True)[:12]:
            a = _ask(f"  {p['name']}  ({p['path']})", "journal", ["content", "journal", "ignore"])
            journal.set_project(k, status={"ignore": "ignored"}.get(a, a))
        st = state()
        st["pending_projects"] = []
        save_state(st)
    notify.desktop("Setup complete. Your first summary arrives at " + cfg["summary_time"])
    print(f"\nDone. Try: buildinpublic today · buildinpublic projects · buildinpublic doctor\n")
