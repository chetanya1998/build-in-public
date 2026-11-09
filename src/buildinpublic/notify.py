"""Notifications, permission dialogs, Gmail delivery and secret storage on
macOS, Windows and Linux. Every function degrades gracefully: if a desktop
feature is missing (a headless server, say) it returns False/None and the
caller falls back to email or to asking inside the next agent session.
"""
from __future__ import annotations

import html
import os
import re
import shutil
import smtplib
import ssl
import subprocess
from email.message import EmailMessage
from pathlib import Path

from .core import load_config, os_name

SERVICE = "build-in-public"
TITLE = "Build Your Product in Public"


def _run(cmd: list[str], timeout: int = 20, **kw) -> subprocess.CompletedProcess | None:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, **kw)
    except (OSError, subprocess.SubprocessError):
        return None


def _ps(script: str, timeout: int = 90, stdin: str | None = None) -> subprocess.CompletedProcess | None:
    exe = shutil.which("powershell") or shutil.which("pwsh") or "powershell"
    kw = {"input": stdin} if stdin is not None else {}
    return _run([exe, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script], timeout=timeout, **kw)


def _esc_as(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _esc_ps(s: str) -> str:
    return s.replace("'", "''")

# ---------------------------------------------------------------- desktop notification

def desktop(message: str, title: str = TITLE) -> bool:
    if os.environ.get("BIP_NO_GUI"):
        return False
    o = os_name()
    if o == "mac":
        r = _run(["osascript", "-e", f'display notification "{_esc_as(message)}" with title "{_esc_as(title)}"'])
        return bool(r and r.returncode == 0)
    if o == "windows":
        script = f"""
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
$x = New-Object Windows.Data.Xml.Dom.XmlDocument
$x.LoadXml('<toast><visual><binding template="ToastGeneric"><text>{html.escape(_esc_ps(title))}</text><text>{html.escape(_esc_ps(message))}</text></binding></visual></toast>')
$app = '{{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}}\\WindowsPowerShell\\v1.0\\powershell.exe'
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($app).Show([Windows.UI.Notifications.ToastNotification]::new($x))
"""
        r = _ps(script, timeout=20)
        return bool(r and r.returncode == 0)
    if shutil.which("notify-send") and (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        r = _run(["notify-send", "-a", TITLE, title, message])
        return bool(r and r.returncode == 0)
    return False

# ---------------------------------------------------------------- permission dialog

def ask(question: str, buttons: list[str], title: str = TITLE, timeout: int = 120) -> str | None:
    """Show a native dialog. Returns the chosen button label, or None if no GUI / no answer."""
    if os.environ.get("BIP_NO_GUI") or not buttons:
        return None
    o = os_name()
    if o == "mac":
        b = ", ".join(f'"{_esc_as(x)}"' for x in buttons[:3])
        r = _run(["osascript", "-e",
                  f'display dialog "{_esc_as(question)}" with title "{_esc_as(title)}" buttons {{{b}}} '
                  f'default button "{_esc_as(buttons[0])}" giving up after {timeout}'], timeout=timeout + 10)
        if r and r.returncode == 0:
            m = re.search(r"button returned:([^,]*)", r.stdout)
            gave_up = "gave up:true" in r.stdout
            return None if gave_up or not m else m.group(1).strip()
        return None
    if o == "windows":
        # Yes/No/Cancel mapped onto the first three buttons
        script = f"""
Add-Type -AssemblyName System.Windows.Forms
$r = [System.Windows.Forms.MessageBox]::Show('{_esc_ps(question)}`n`nYes = {_esc_ps(buttons[0])}`nNo = {_esc_ps(buttons[1] if len(buttons) > 1 else 'No')}`nCancel = {_esc_ps(buttons[2] if len(buttons) > 2 else 'Cancel')}', '{_esc_ps(title)}', 'YesNoCancel', 'Question')
Write-Output $r
"""
        r = _ps(script, timeout=timeout + 10)
        if not r or r.returncode != 0:
            return None
        ans = r.stdout.strip()
        idx = {"Yes": 0, "No": 1, "Cancel": 2}.get(ans)
        return buttons[idx] if idx is not None and idx < len(buttons) else None
    if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        return None
    if shutil.which("zenity"):
        cmd = ["zenity", "--question", f"--title={title}", f"--text={question}", f"--timeout={timeout}",
               f"--ok-label={buttons[0]}", f"--cancel-label={buttons[1] if len(buttons) > 1 else 'No'}"]
        if len(buttons) > 2:
            cmd.append(f"--extra-button={buttons[2]}")
        r = _run(cmd, timeout=timeout + 10)
        if not r:
            return None
        if r.returncode == 0:
            return buttons[0]
        if r.stdout.strip() and len(buttons) > 2 and r.stdout.strip() == buttons[2]:
            return buttons[2]
        return buttons[1] if r.returncode == 1 and len(buttons) > 1 else None
    if shutil.which("kdialog"):
        r = _run(["kdialog", "--title", title, "--yesnocancel", question,
                  "--yes-label", buttons[0], "--no-label", buttons[1] if len(buttons) > 1 else "No",
                  "--cancel-label", buttons[2] if len(buttons) > 2 else "Cancel"], timeout=timeout + 10)
        if r:
            return {0: buttons[0], 1: buttons[1] if len(buttons) > 1 else None,
                    2: buttons[2] if len(buttons) > 2 else None}.get(r.returncode)
    return None

# ---------------------------------------------------------------- secrets

def set_secret(name: str, value: str) -> str:
    try:
        import keyring  # type: ignore
        keyring.set_password(SERVICE, name, value)
        return "keyring"
    except Exception:
        pass
    o = os_name()
    if o == "mac":
        _run(["security", "delete-generic-password", "-s", SERVICE, "-a", name])
        r = _run(["security", "add-generic-password", "-s", SERVICE, "-a", name, "-w", value])
        if r and r.returncode == 0:
            return "macOS Keychain"
    if o == "linux" and shutil.which("secret-tool"):
        try:
            p = subprocess.run(["secret-tool", "store", "--label", SERVICE, "service", SERVICE, "account", name],
                               input=value, text=True, capture_output=True, timeout=20)
            if p.returncode == 0:
                return "Secret Service"
        except (OSError, subprocess.SubprocessError):
            pass
    if o == "windows":
        # DPAPI-protected file, readable only by this Windows user
        from .core import app_home
        enc = ("$v = [Console]::In.ReadToEnd().Trim(); $s = ConvertTo-SecureString $v -AsPlainText -Force; "
               f"ConvertFrom-SecureString $s | Set-Content -Path '{app_home() / ('secret-' + name)}'")
        r = _ps(enc, stdin=value)
        if r and r.returncode == 0:
            return "Windows DPAPI"
    raise RuntimeError("No secure store available. Install `keyring` (pip install keyring) "
                       "or set the BUILDINPUBLIC_SMTP_PASSWORD environment variable.")


def get_secret(name: str) -> str | None:
    env = os.environ.get("BUILDINPUBLIC_SMTP_PASSWORD") if name == "smtp" else None
    if env:
        return env
    try:
        import keyring  # type: ignore
        v = keyring.get_password(SERVICE, name)
        if v:
            return v
    except Exception:
        pass
    o = os_name()
    if o == "mac":
        r = _run(["security", "find-generic-password", "-s", SERVICE, "-a", name, "-w"])
        if r and r.returncode == 0:
            return r.stdout.strip()
    if o == "linux" and shutil.which("secret-tool"):
        r = _run(["secret-tool", "lookup", "service", SERVICE, "account", name])
        if r and r.returncode == 0 and r.stdout:
            return r.stdout.strip()
    if o == "windows":
        from .core import app_home
        f = app_home() / f"secret-{name}"
        if f.exists():
            r = _ps(f"$s = Get-Content '{f}' | ConvertTo-SecureString; "
                    "[Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($s))")
            if r and r.returncode == 0:
                return r.stdout.strip()
    return None

# ---------------------------------------------------------------- email

def md_to_html(md: str) -> str:
    out, in_list = [], False
    for line in md.splitlines():
        e = html.escape(line)
        e = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", e)
        e = re.sub(r"`(.+?)`", r"<code>\1</code>", e)
        e = re.sub(r"\[(.+?)\]\((https?://[^)\s]+)\)", r'<a href="\2">\1</a>', e)
        if line.startswith(("- ", "* ")):
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{e[2:]}</li>")
            continue
        if in_list:
            out.append("</ul>")
            in_list = False
        if line.startswith("### "):
            out.append(f"<h3>{e[4:]}</h3>")
        elif line.startswith("## "):
            out.append(f"<h2>{e[3:]}</h2>")
        elif line.startswith("# "):
            out.append(f"<h1>{e[2:]}</h1>")
        elif line.startswith("> "):
            out.append(f"<blockquote>{e[5:]}</blockquote>")
        elif line.strip():
            out.append(f"<p>{e}</p>")
    if in_list:
        out.append("</ul>")
    style = ("font-family:-apple-system,Segoe UI,Roboto,sans-serif;max-width:640px;margin:auto;"
             "color:#111;line-height:1.55")
    return f'<div style="{style}">' + "\n".join(out) + "</div>"


MAIL_APP_SCRIPT = """on run argv
  set {theTo, theSubject, theBody} to argv
  tell application "Mail"
    set m to make new outgoing message with properties {subject:theSubject, content:theBody & return, visible:false}
    tell m to make new to recipient at end of to recipients with properties {address:theTo}
    send m
  end tell
end run"""


def email_settings() -> dict:
    """Merged email settings. The address can come from this tool's config or from
    ~/.config/buildinpublic/email.json, which the per-project skill also uses."""
    from .core import read_json, user_home
    cfg = dict(load_config().get("email", {}))
    shared = read_json(user_home() / ".config" / "buildinpublic" / "email.json", {})
    for k, v in shared.items():
        cfg.setdefault(k, v)
        if not cfg.get(k):
            cfg[k] = v
    if not cfg.get("method"):
        o = os_name()
        if get_secret("smtp"):
            cfg["method"] = "smtp"
        elif o == "mac":
            cfg["method"] = "mail-app"
        elif o == "linux" and any(Path(p).exists() for p in ("/usr/sbin/sendmail", "/usr/lib/sendmail")):
            cfg["method"] = "sendmail"
        else:
            cfg["method"] = "smtp"
    return cfg


def email(subject: str, body_md: str, attachments: list[str] | None = None) -> bool:
    """Send to the user's own address. mail-app (macOS, no password), sendmail (Linux,
    no password) or smtp (any OS, app password from the system keychain)."""
    cfg = email_settings()
    to = cfg.get("to")
    if not to:
        return False
    method = cfg["method"]
    if method == "mail-app":
        r = _run(["osascript", "-e", MAIL_APP_SCRIPT, to, subject, body_md], timeout=60)
        return bool(r and r.returncode == 0)
    sender = cfg.get("from") or to
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = subject, sender, to
    msg.set_content(body_md)
    msg.add_alternative(md_to_html(body_md), subtype="html")
    for a in (attachments or [])[:4]:
        try:
            p = Path(a)
            if p.stat().st_size < 4_000_000:
                msg.add_attachment(p.read_bytes(), maintype="image",
                                   subtype=p.suffix.lstrip(".").replace("jpg", "jpeg"), filename=p.name)
        except OSError:
            pass
    if method == "sendmail":
        sm = next((p for p in ("/usr/sbin/sendmail", "/usr/lib/sendmail") if Path(p).exists()), None)
        if not sm:
            return False
        try:
            r = subprocess.run([sm, "-t", "-oi"], input=msg.as_bytes(), capture_output=True, timeout=60)
            return r.returncode == 0
        except (OSError, subprocess.SubprocessError):
            return False
    pwd = get_secret("smtp")
    if not pwd:
        return False
    try:
        host, port = cfg.get("smtp_host", "smtp.gmail.com"), int(cfg.get("smtp_port", 465))
        user = cfg.get("smtp_user") or sender
        if port == 465:
            with smtplib.SMTP_SSL(host, port, context=ssl.create_default_context(), timeout=30) as s:
                s.login(user, pwd)
                s.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=30) as s:
                s.starttls(context=ssl.create_default_context())
                s.login(user, pwd)
                s.send_message(msg)
        return True
    except (OSError, smtplib.SMTPException) as e:
        import sys
        print(f"[buildinpublic] email failed: {e}", file=sys.stderr)
        return False


def deliver(subject: str, short: str, body_md: str, attachments: list[str] | None = None) -> list[str]:
    """Send through every configured channel. Returns the channels that worked."""
    channels = load_config().get("channels", ["notification"])
    done = []
    if "notification" in channels and desktop(short, subject):
        done.append("notification")
    if "email" in channels and email(subject, body_md, attachments):
        done.append("email")
    return done
