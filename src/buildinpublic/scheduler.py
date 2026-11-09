"""Background jobs on every OS.

  sweep    capture new sessions, check reminders        hourly (or nightly)
  watch    look for localhost dev servers to screenshot  every N minutes
  summary  build and deliver the daily summary           daily at summary_time

macOS: launchd agents · Linux: systemd --user timers (cron fallback) ·
Windows: Task Scheduler.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from .core import app_home, load_config, os_name, python_cmd, user_home

LABEL = "ai.buildyourproductinpublic"
WIN_FOLDER = "BuildYourProductInPublic"


def jobs(cfg: dict | None = None) -> dict[str, dict]:
    cfg = cfg or load_config()
    h, m = (cfg.get("summary_time") or "00:00").split(":")
    out = {"summary": {"args": ["summary", "--send"], "daily": (int(h), int(m))}}
    cap = cfg.get("capture", "live+hourly")
    if cap in ("live+hourly", "hourly"):
        out["sweep"] = {"args": ["sweep", "--quiet"], "every_min": 60}
    else:  # nightly-only capture still sweeps once, just before the summary
        out["sweep"] = {"args": ["sweep", "--quiet"], "daily": ((int(h) - 1) % 24, int(m))}
    if cfg.get("screenshots", "ask") != "never":
        out["watch"] = {"args": ["watch", "--quiet"], "every_min": max(2, int(cfg.get("localhost_check_minutes", 5)))}
    return out


def _run(cmd, **kw):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=30, **kw)
    except (OSError, subprocess.SubprocessError) as e:
        return subprocess.CompletedProcess(cmd, 1, "", str(e))

# ---------------------------------------------------------------- macOS

def _plist(name: str, job: dict) -> str:
    args = "".join(f"<string>{a}</string>" for a in python_cmd() + job["args"])
    when = (f"<key>StartInterval</key><integer>{job['every_min'] * 60}</integer>" if "every_min" in job else
            f"<key>StartCalendarInterval</key><dict><key>Hour</key><integer>{job['daily'][0]}</integer>"
            f"<key>Minute</key><integer>{job['daily'][1]}</integer></dict>")
    log = app_home() / "logs" / f"{name}.log"
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>{LABEL}.{name}</string>
  <key>ProgramArguments</key><array>{args}</array>
  <key>EnvironmentVariables</key><dict><key>PATH</key><string>{os.environ.get('PATH', '/usr/bin:/bin')}</string></dict>
  {when}
  <key>StandardOutPath</key><string>{log}</string>
  <key>StandardErrorPath</key><string>{log}</string>
</dict></plist>
"""


def _mac_install(js):
    d = user_home() / "Library" / "LaunchAgents"
    d.mkdir(parents=True, exist_ok=True)
    out = []
    for name, job in js.items():
        f = d / f"{LABEL}.{name}.plist"
        _run(["launchctl", "unload", str(f)])
        f.write_text(_plist(name, job))
        r = _run(["launchctl", "load", str(f)])
        out.append(f"{name}: launchd {'ok' if r.returncode == 0 else 'error ' + r.stderr.strip()}")
    return out


def _mac_remove():
    d = user_home() / "Library" / "LaunchAgents"
    for f in d.glob(f"{LABEL}.*.plist"):
        _run(["launchctl", "unload", str(f)])
        f.unlink(missing_ok=True)

# ---------------------------------------------------------------- Linux

def _systemd_ok() -> bool:
    return bool(shutil.which("systemctl")) and _run(["systemctl", "--user", "show-environment"]).returncode == 0


def _quote(a: str) -> str:
    return f'"{a}"' if " " in a else a


def _linux_install(js):
    out = []
    if _systemd_ok():
        d = Path(os.environ.get("XDG_CONFIG_HOME", user_home() / ".config")) / "systemd" / "user"
        d.mkdir(parents=True, exist_ok=True)
        for name, job in js.items():
            unit = f"buildinpublic-{name}"
            cmd = " ".join(_quote(a) for a in python_cmd() + job["args"])
            (d / f"{unit}.service").write_text(
                f"[Unit]\nDescription=Build Your Product in Public: {name}\n\n"
                f"[Service]\nType=oneshot\nExecStart={cmd}\nEnvironment=PATH={os.environ.get('PATH', '')}\n")
            when = (f"OnBootSec=3min\nOnUnitActiveSec={job['every_min']}min" if "every_min" in job else
                    f"OnCalendar=*-*-* {job['daily'][0]:02d}:{job['daily'][1]:02d}:00")
            (d / f"{unit}.timer").write_text(
                f"[Unit]\nDescription=Build Your Product in Public: {name}\n\n"
                f"[Timer]\n{when}\nPersistent=true\n\n[Install]\nWantedBy=timers.target\n")
        _run(["systemctl", "--user", "daemon-reload"])
        for name in js:
            r = _run(["systemctl", "--user", "enable", "--now", f"buildinpublic-{name}.timer"])
            out.append(f"{name}: systemd {'ok' if r.returncode == 0 else 'error ' + r.stderr.strip()}")
        return out
    if not shutil.which("crontab"):
        return ["No systemd user session or crontab found: run `buildinpublic sweep` and `buildinpublic summary --send` yourself."]
    cur = _run(["crontab", "-l"]).stdout
    keep = [l for l in cur.splitlines() if "# buildinpublic:" not in l]
    for name, job in js.items():
        cmd = " ".join(_quote(a) for a in python_cmd() + job["args"])
        when = (f"*/{job['every_min']} * * * *" if job.get("every_min", 60) < 60 else "0 * * * *") \
            if "every_min" in job else f"{job['daily'][1]} {job['daily'][0]} * * *"
        keep.append(f"{when} {cmd} >> {app_home() / 'logs' / (name + '.log')} 2>&1 # buildinpublic:{name}")
    r = _run(["crontab", "-"], input="\n".join(keep) + "\n")
    return [f"{n}: cron {'ok' if r.returncode == 0 else 'error'}" for n in js]


def _linux_remove():
    if _systemd_ok():
        d = Path(os.environ.get("XDG_CONFIG_HOME", user_home() / ".config")) / "systemd" / "user"
        for f in d.glob("buildinpublic-*.timer"):
            _run(["systemctl", "--user", "disable", "--now", f.name])
        for f in list(d.glob("buildinpublic-*.timer")) + list(d.glob("buildinpublic-*.service")):
            f.unlink(missing_ok=True)
        _run(["systemctl", "--user", "daemon-reload"])
    if shutil.which("crontab"):
        cur = _run(["crontab", "-l"]).stdout
        keep = [l for l in cur.splitlines() if "# buildinpublic:" not in l]
        _run(["crontab", "-"], input="\n".join(keep) + ("\n" if keep else ""))

# ---------------------------------------------------------------- Windows

def _win_install(js):
    out = []
    for name, job in js.items():
        tr = " ".join(f'"{a}"' for a in python_cmd() + job["args"])
        cmd = ["schtasks", "/Create", "/F", "/TN", f"{WIN_FOLDER}\\{name}", "/TR", tr]
        if "every_min" in job:
            cmd += (["/SC", "HOURLY"] if job["every_min"] >= 60 else ["/SC", "MINUTE", "/MO", str(job["every_min"])])
        else:
            cmd += ["/SC", "DAILY", "/ST", f"{job['daily'][0]:02d}:{job['daily'][1]:02d}"]
        r = _run(cmd)
        out.append(f"{name}: Task Scheduler {'ok' if r.returncode == 0 else 'error ' + (r.stderr or r.stdout).strip()}")
    return out


def _win_remove():
    for name in ("summary", "sweep", "watch"):
        _run(["schtasks", "/Delete", "/F", "/TN", f"{WIN_FOLDER}\\{name}"])

# ---------------------------------------------------------------- public

def install(cfg: dict | None = None) -> list[str]:
    (app_home() / "logs").mkdir(exist_ok=True)
    remove()
    js = jobs(cfg)
    o = os_name()
    return _mac_install(js) if o == "mac" else _win_install(js) if o == "windows" else _linux_install(js)


def remove() -> None:
    o = os_name()
    (_mac_remove if o == "mac" else _win_remove if o == "windows" else _linux_remove)()


def status() -> list[str]:
    o = os_name()
    if o == "mac":
        r = _run(["launchctl", "list"])
        return [l for l in r.stdout.splitlines() if LABEL in l] or ["no launchd jobs"]
    if o == "windows":
        r = _run(["schtasks", "/Query", "/FO", "LIST", "/TN", f"{WIN_FOLDER}\\"])
        return [l for l in r.stdout.splitlines() if l.startswith(("TaskName", "Next Run", "Status"))] or ["no scheduled tasks"]
    if _systemd_ok():
        r = _run(["systemctl", "--user", "list-timers", "--all"])
        return [l for l in r.stdout.splitlines() if "buildinpublic" in l] or ["no systemd timers"]
    r = _run(["crontab", "-l"]) if shutil.which("crontab") else None
    return [l for l in (r.stdout.splitlines() if r else []) if "buildinpublic" in l] or ["no cron jobs"]
