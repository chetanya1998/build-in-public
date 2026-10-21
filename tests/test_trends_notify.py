"""Tests for trends.py (what gets searched, no network) and notify.py (the gist, no email sent)."""
import contextlib, io, json, os, sys, unittest
from pathlib import Path
from unittest import mock

from test_collect import DAY, SCRIPTS, Fixture

sys.path.insert(0, str(SCRIPTS))
import notify, trends  # noqa: E402


class TrendsTest(Fixture):
    def test_day_themes(self):
        themes = trends.day_themes(self.repo, DAY)
        self.assertTrue(themes[0].startswith("due dates"), themes)
        self.assertLessEqual(len(themes), 3)
        self.assertEqual(len(themes), len(set(themes)))
        self.assertTrue(all(len(t.split()) >= 2 for t in themes))

    def test_stack_keywords(self):
        (self.repo / "package.json").write_text(json.dumps(
            {"dependencies": {"next": "15", "stripe": "17", "left-pad": "1"}, "devDependencies": {"tailwindcss": "4"}}))
        (self.repo / "requirements.txt").write_text("fastapi==0.115\n")
        self.assertEqual(trends.stack_keywords(self.repo), ["next.js", "stripe", "tailwind css"])
        self.assertEqual(trends.stack_keywords(self.repo, limit=9), ["next.js", "stripe", "tailwind css", "fastapi"])

    def test_trends_file_groups(self):
        (self.repo / "package.json").write_text(json.dumps({"dependencies": {"next": "15"}}))
        searched = []
        fake = lambda q, days: searched.append(q) or [(f"About {q}", "https://example.com/" + q.replace(" ", "-"), "1 pt")]
        argv = ["trends.py", "--repo", str(self.repo), "--date", str(DAY)]
        with mock.patch.object(trends, "SOURCES", {"Hacker News": fake}), \
                mock.patch.object(trends.time, "sleep"), mock.patch.object(sys, "argv", argv), \
                contextlib.redirect_stdout(io.StringIO()):
            trends.main()
        text = (self.repo / ".buildinpublic" / "daily" / str(DAY) / "trends.md").read_text()
        self.assertIn("## Today's work: due dates", text)
        self.assertIn("## Project: freelance invoicing", text)
        self.assertIn("## Stack: next.js", text)
        self.assertIn("next.js", searched)


class NotifyTest(Fixture):
    BRIEF = """# Brief

## Today in one line
Fixed due dates that moved a day west of UTC.

## What you shipped
- Due dates stay put (b1e8e15)

## Suggested posts
1. **CI lives in UTC** · X thread
2. **7 of 500 payments lost** · LinkedIn

## The story
Long story.
"""

    def out(self):
        d = self.repo / ".buildinpublic" / "daily" / str(DAY)
        d.mkdir(parents=True, exist_ok=True)
        return d

    def email_config(self):
        cfg = self.home / ".config" / "buildinpublic"
        cfg.mkdir(parents=True, exist_ok=True)
        (cfg / "email.json").write_text(json.dumps(
            {"to": "me@example.com", "smtp_host": "smtp.example.com", "smtp_user": "me@example.com"}))
        return cfg

    def test_gist_from_brief(self):
        (self.out() / "brief.md").write_text(self.BRIEF)
        headline, body = notify.build_gist(self.repo, DAY)
        self.assertEqual(headline, "Fixed due dates that moved a day west of UTC.")
        self.assertIn("SUGGESTED POSTS\n1. **CI lives in UTC**", body)
        self.assertIn("review my posts", body)
        self.assertNotIn("Long story", body)

    def test_gist_from_digest_when_no_brief(self):
        self.digest()
        headline, body = notify.build_gist(self.repo, DAY)
        self.assertEqual(headline, "Due dates no longer shift a day in US timezones")
        self.assertIn("Sessions: Claude Code 1, Codex 1, Antigravity 1", body)
        self.assertIn("build in public brief", body)

    def test_dry_run_email(self):
        (self.out() / "brief.md").write_text(self.BRIEF)
        self.email_config()
        r = self.run_script("notify.py", "--date", str(DAY), "--dry-run")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(f"Subject: Build In Public · tinyinvoice · {DAY}: Fixed due dates", r.stdout)
        self.assertIn("To: me@example.com", r.stdout)
        self.assertIn(f'filename="brief-{DAY}.md"', r.stdout)

    def test_no_email_settings(self):
        r = self.run_script("notify.py", "--date", str(DAY))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Email not set up", r.stdout)

    def test_password_sources(self):
        cfg = self.email_config()
        with mock.patch.object(notify, "CONFIG_DIR", cfg), mock.patch.dict(os.environ, {"BIP_SMTP_PASSWORD": "from-env"}):
            self.assertEqual(notify.smtp_password("me@example.com"), "from-env")
        pw = cfg / "smtp-password"
        pw.write_text("from-file\n")
        env = {k: v for k, v in os.environ.items() if k != "BIP_SMTP_PASSWORD"}
        with mock.patch.object(notify, "CONFIG_DIR", cfg), mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.object(notify.platform, "system", return_value="Linux"):
            os.chmod(pw, 0o644)
            with self.assertRaises(SystemExit) as e:
                notify.smtp_password("me@example.com")
            self.assertIn("chmod 600", str(e.exception.code))
            os.chmod(pw, 0o600)
            self.assertEqual(notify.smtp_password("me@example.com"), "from-file")


if __name__ == "__main__":
    unittest.main()
