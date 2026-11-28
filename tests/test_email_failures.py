"""When the gist email can't be sent, say why and how to fix it: in the log, in email-error.txt,
in a desktop notification and in doctor. No traceback, and no silent failure."""
import datetime as dt
import json
import os
import shutil
import smtplib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SKILL = Path(__file__).resolve().parent.parent / "skills" / "build-in-public"
sys.path.insert(0, str(SKILL / "scripts"))
import doctor, notify  # noqa: E402

GMAIL = {"to": "me@example.com", "method": "smtp", "smtp_host": "smtp.gmail.com", "smtp_port": 587,
         "smtp_user": "me@example.com", "security": "starttls"}
DAY = dt.date(2026, 11, 24)


def fake_smtp(fail_at=None, exc=None):
    """An smtplib.SMTP stand-in that fails at one step: 'connect', 'starttls', 'login' or 'send'."""
    class FakeSMTP:
        def __init__(self, *a, **k):
            if fail_at == "connect":
                raise exc

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def starttls(self, **k):
            if fail_at == "starttls":
                raise exc

        def login(self, *a):
            if fail_at == "login":
                raise exc

        def send_message(self, msg):
            if fail_at == "send":
                raise exc
    return FakeSMTP


class SendTest(unittest.TestCase):
    def send(self, fail_at, exc):
        msg = notify.compose(GMAIL, Path(tempfile.gettempdir()), DAY, "Headline", "body")
        with mock.patch.dict(os.environ, {"BIP_SMTP_PASSWORD": "abcd efgh ijkl mnop"}), \
             mock.patch.object(notify.smtplib, "SMTP", fake_smtp(fail_at, exc)):
            return notify.send(GMAIL, msg)

    def test_gmail_hangs_up_at_sign_in(self):
        with self.assertRaises(notify.EmailFailed) as c:
            self.send("login", smtplib.SMTPServerDisconnected("Connection unexpectedly closed"))
        self.assertIn("closed the connection while signing in", c.exception.reason)
        self.assertIn("myaccount.google.com/apppasswords", c.exception.fix)
        self.assertNotIn("abcd", c.exception.reason + c.exception.fix)  # never the password

    def test_password_rejected(self):
        with self.assertRaises(notify.EmailFailed) as c:
            self.send("login", smtplib.SMTPAuthenticationError(535, b"Username and Password not accepted"))
        self.assertIn("rejected the password", c.exception.reason)

    def test_offline(self):
        with self.assertRaises(notify.EmailFailed) as c:
            self.send("connect", OSError("nodename nor servname provided"))
        self.assertIn("Couldn't reach smtp.gmail.com:587", c.exception.reason)
        self.assertIn("online", c.exception.fix)

    def test_no_password_saved(self):
        msg = notify.compose(GMAIL, Path(tempfile.gettempdir()), DAY, "Headline", "body")
        with mock.patch.dict(os.environ, {}, clear=False), \
             mock.patch.object(notify, "smtp_password", side_effect=SystemExit("The smtp method needs a password.")):
            os.environ.pop("BIP_SMTP_PASSWORD", None)
            with self.assertRaises(notify.EmailFailed) as c:
                notify.send(GMAIL, msg)
        self.assertEqual(c.exception.reason, "No email password is saved.")

    def test_works(self):
        self.assertEqual(self.send(None, None), "smtp")


class NightlyFailureTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.repo = self.tmp / "shop"
        self.out = self.repo / ".buildinpublic" / "daily" / str(DAY)
        self.out.mkdir(parents=True)
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        (self.out / "digest.md").write_text(f"# Digest {DAY}\n\n## Git commits\n- 10:00 abc1234 Billing page\n")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_main(self, send_effect):
        argv = ["notify.py", "--repo", str(self.repo), "--date", str(DAY)]
        with mock.patch.object(sys, "argv", argv), \
             mock.patch.object(notify, "email_settings", return_value=GMAIL), \
             mock.patch.object(notify, "send", side_effect=send_effect), \
             mock.patch.object(notify, "desktop") as desk:
            try:
                notify.main()
                code = 0
            except SystemExit as e:
                code = e.code
        return code, desk

    def test_failure_is_saved_notified_and_exits_1(self):
        code, desk = self.run_main(notify.EmailFailed("smtp.gmail.com closed the connection while signing in.",
                                                      "Make a new app password."))
        self.assertEqual(code, 1)
        err = (self.out / "email-error.txt").read_text()
        self.assertIn("reason: smtp.gmail.com closed the connection", err)
        self.assertIn("fix: Make a new app password.", err)
        self.assertTrue((self.out / "gist.html").exists())               # saved before sending
        self.assertIn("email not sent", desk.call_args_list[-1][0][0])

    def test_success_clears_an_old_failure(self):
        (self.out / "email-error.txt").write_text("reason: old\n")
        code, _ = self.run_main(lambda *a, **k: "smtp")
        self.assertEqual(code, 0)
        self.assertFalse((self.out / "email-error.txt").exists())


class DoctorTest(unittest.TestCase):
    def test_reports_failed_days_until_one_sends(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        daily = tmp / ".buildinpublic" / "daily"
        for d, log, err in (("2026-11-23", "Gist emailed to me via smtp.\n", None),
                            ("2026-11-24", "smtplib.SMTPServerDisconnected: Connection unexpectedly closed\n", None),
                            ("2026-11-25", "✗ Email not sent\n", "reason: Gmail closed it.\nfix: New app password.\n")):
            (daily / d).mkdir(parents=True)
            (daily / d / "nightly.log").write_text(log)
            if err:
                (daily / d / "email-error.txt").write_text(err)
        doctor.RESULTS.clear()
        doctor.check_last_email(tmp)
        mark, _, detail = doctor.RESULTS[0]
        self.assertEqual(mark, "✗")
        self.assertIn("not sent for 2026-11-24, 2026-11-25", detail)
        self.assertIn("Gmail closed it.", detail)
        (daily / "2026-11-26").mkdir()
        (daily / "2026-11-26" / "nightly.log").write_text("Gist emailed to me via smtp.\n")
        doctor.RESULTS.clear()
        doctor.check_last_email(tmp)
        self.assertEqual(doctor.RESULTS[0][:2], ("✓", "Last email"))


if __name__ == "__main__":
    unittest.main()
