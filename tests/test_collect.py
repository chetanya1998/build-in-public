"""Tests for collect.py and doctor.py, run against sample session files.

    python3 -m unittest discover tests

Standard library only. Each test builds a fake home folder (agent session files) and a
small git repo in a temp folder, so nothing on your machine is read.
"""
import datetime as dt, os, subprocess, sys, tempfile, unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "skills" / "build-in-public" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import collect  # noqa: E402
import fixtures_setup as fx  # noqa: E402

DAY = dt.date(2026, 10, 21)


class Fixture(unittest.TestCase):
    day = DAY

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name).resolve()
        # A long path on purpose: file names must survive the repo prefix being stripped.
        self.repo = root / ("projects-" + "x" * 120) / "tinyinvoice"
        self.home = root / "home"
        fx.build_repo(self.repo, self.day)
        fx.build_fake_home(self.home, self.repo, self.day)
        self.env = dict(os.environ, HOME=str(self.home))
        self.env.pop("BIP_SMTP_PASSWORD", None)
        for cache in ("Library/Caches/ms-playwright", ".cache/ms-playwright"):  # browsers live in the real home
            if "PLAYWRIGHT_BROWSERS_PATH" not in self.env and (Path.home() / cache).is_dir():
                self.env["PLAYWRIGHT_BROWSERS_PATH"] = str(Path.home() / cache)
        self._home, collect.HOME = collect.HOME, self.home

    def tearDown(self):
        collect.HOME = self._home
        self.tmp.cleanup()

    def run_script(self, name, *args, **kw):
        return subprocess.run([sys.executable, str(SCRIPTS / name), "--repo", str(self.repo), *args],
                              env=self.env, capture_output=True, text=True, stdin=subprocess.DEVNULL, **kw)

    def digest(self):
        r = self.run_script("collect.py", "--date", str(self.day))
        self.assertEqual(r.returncode, 0, r.stderr)
        return (self.repo / ".buildinpublic" / "daily" / str(self.day) / "digest.md").read_text()


class SourcesTest(Fixture):
    def test_claude_code_session(self):
        [s] = collect.claude_sessions(self.repo, DAY)
        users = [t for r, t in s["messages"] if r == "user"]
        self.assertEqual(len(users), 2)  # the tool_result record is not a user message
        self.assertTrue(users[0].startswith("Invoices exported to PDF"))
        edited = {t for n, t in s["tools"] if n == "Edit"}
        self.assertIn(str(self.repo / "src/lib/dates.ts"), edited)
        self.assertIn(("Bash", "npm test -- dates pdf"), s["tools"])

    def test_codex_only_this_repo(self):
        [s] = collect.codex_sessions(self.repo, DAY)  # the other project's session is skipped
        self.assertEqual(s["cwd"], str(self.repo))
        self.assertTrue(any("7 to 0" in t for r, t in s["messages"] if r == "assistant"))
        self.assertIn(("shell", "bash -lc npm test -- webhooks"), s["tools"])

    def test_antigravity_artifacts_and_media(self):
        [s] = collect.antigravity_sessions(self.repo, DAY)
        self.assertEqual(sorted(t.split("]")[0] for _, t in s["messages"]), ["[task", "[walkthrough"])
        self.assertEqual([Path(m).name for m in s["media"]], ["onboarding-after.png"])

    def test_antigravity_other_repo_skipped(self):
        other = self.repo.parent / "something-else"
        other.mkdir()
        self.assertEqual(collect.antigravity_sessions(other, DAY), [])

    def test_other_days_ignored(self):
        day = DAY - dt.timedelta(days=3)
        self.assertEqual(collect.claude_sessions(self.repo, day), [])
        self.assertEqual(collect.codex_sessions(self.repo, day), [])
        self.assertEqual(collect.antigravity_sessions(self.repo, day), [])

    def test_offlimits_from_narrative(self):
        self.assertEqual(collect.read_offlimits(self.repo), ["Acme Corp"])


class RedactTest(unittest.TestCase):
    def test_secrets_and_emails(self):
        text = ("key sk-ant-abcdefghijklmnop1234 and ghp_abcdefghijklmnopqrstuvwxyz123 "
                "password: hunter2hunter2 mail maya@tinyinvoice.example for Acme Corp")
        out = collect.redact(text, ["acme corp"])
        for leaked in ("sk-ant-", "ghp_", "hunter2", "maya@", "Acme"):
            self.assertNotIn(leaked, out)
        self.assertEqual(out.count("[REDACTED]"), 3)
        self.assertIn("[email]", out)
        self.assertIn("[off-limits]", out)


class DigestTest(Fixture):
    def test_full_digest(self):
        digest = self.digest()
        self.assertIn("Sessions found: Claude Code 1, Codex 1, Antigravity 1 (total 3)", digest)
        [edited] = [l for l in digest.splitlines() if l.startswith("**Files edited:**")]
        self.assertIn("migrations/0007_due_date_as_date.sql", edited)  # full name, repo path stripped
        self.assertNotIn(str(self.repo), edited)
        for commit in ("fix: due dates shift a day", "feat: retry Stripe webhooks", "feat: two-step onboarding"):
            self.assertIn(commit, digest)
        self.assertIn("#war-story", digest)  # agent log entries included
        for leaked in ("maya@", "demo_tok_", "Acme", "a-different-project"):
            self.assertNotIn(leaked, digest)

    def test_agent_screenshots_are_only_candidates(self):
        digest = self.digest()
        approved = digest.split("## Approved captures")[1].split("## Screenshot candidates")[0]
        candidates = digest.split("## Screenshot candidates")[1]
        self.assertIn("_none_", approved)
        self.assertIn("onboarding-after.png", candidates)
        self.assertFalse((self.repo / ".buildinpublic" / "daily" / str(DAY) / "snapshots").exists())


class DoctorTest(Fixture):
    day = (dt.datetime.now() - dt.timedelta(hours=4)).date()  # doctor looks at the last 7 days

    def test_doctor_on_fixture(self):
        r = self.run_script("doctor.py")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        for line in ("✓ Claude Code: 1 session(s)", "✓ Codex: 1 session(s)", "✓ Antigravity: 1 session(s)",
                     "✓ narrative.md: filled in", "! Email: not set up", "0 problem(s)"):
            self.assertIn(line, r.stdout)

    def test_doctor_email_without_password(self):
        cfg = self.home / ".config" / "buildinpublic"
        cfg.mkdir(parents=True)
        (cfg / "email.json").write_text('{"to": "a@b.example", "smtp_host": "smtp.b.example", '
                                        '"smtp_user": "bip-test-nobody@b.example"}')
        r = self.run_script("doctor.py")
        self.assertEqual(r.returncode, 1)
        self.assertIn("✗ Email: no SMTP password", r.stdout)

    def test_doctor_flags_missing_setup(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = subprocess.run([sys.executable, str(SCRIPTS / "doctor.py"), "--repo", tmp],
                               env=dict(os.environ, HOME=tmp), capture_output=True, text=True)
            self.assertEqual(r.returncode, 1)
            self.assertIn("✗ .buildinpublic/: missing", r.stdout)


if __name__ == "__main__":
    unittest.main()
