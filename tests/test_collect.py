"""Tests for collect.py, run against the demo's sample session files.

    python3 -m unittest discover tests

Standard library only. Each test builds a fake home folder (agent session files) and a
small git repo in a temp folder, so nothing on your machine is read.
"""
import datetime as dt, os, subprocess, sys, tempfile, unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "skills" / "build-in-public" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import collect, demo  # noqa: E402

DAY = dt.date(2026, 10, 21)


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name).resolve()
        # A long path on purpose: file names must survive the repo prefix being stripped.
        self.repo = root / ("projects-" + "x" * 120) / "tinyinvoice"
        self.home = root / "home"
        demo.build_repo(self.repo, DAY)
        demo.build_fake_home(self.home, self.repo, DAY)
        self._home, collect.HOME = collect.HOME, self.home

    def tearDown(self):
        collect.HOME = self._home
        self.tmp.cleanup()


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
        r = subprocess.run([sys.executable, str(SCRIPTS / "collect.py"), "--repo", str(self.repo),
                            "--date", str(DAY)], env=dict(os.environ, HOME=str(self.home)),
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        out = self.repo / ".buildinpublic" / "daily" / str(DAY)
        digest = (out / "digest.md").read_text()

        self.assertIn("Sessions found: Claude Code 1, Codex 1, Antigravity 1 (total 3)", digest)
        [edited] = [l for l in digest.splitlines() if l.startswith("**Files edited:**")]
        self.assertIn("migrations/0007_due_date_as_date.sql", edited)  # full name, repo path stripped
        self.assertNotIn(str(self.repo), edited)
        self.assertNotIn(str(self.repo), digest.split("## Antigravity")[0])
        for commit in ("fix: due dates shift a day", "feat: retry Stripe webhooks", "feat: two-step onboarding"):
            self.assertIn(commit, digest)
        self.assertIn("#war-story", digest)  # agent log entries included
        self.assertTrue((out / "snapshots" / "demo-conv-onboarding-after.png").exists())

        for leaked in ("maya@", "demo_tok_", "Acme", "a-different-project"):
            self.assertNotIn(leaked, digest)


class DemoTest(unittest.TestCase):
    def test_demo_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = subprocess.run([sys.executable, str(SCRIPTS / "demo.py"), "--out", tmp, "--date", str(DAY)],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            out = Path(tmp) / "tinyinvoice" / ".buildinpublic" / "daily" / str(DAY)
            self.assertIn("Antigravity 1", (out / "digest.md").read_text())
            brief = (out / "brief.md").read_text()
            self.assertIn(f"brief · {DAY}", brief)
            self.assertNotIn("{{", brief)


class DoctorTest(unittest.TestCase):
    def test_doctor_on_demo(self):
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run([sys.executable, str(SCRIPTS / "demo.py"), "--out", tmp], check=True, capture_output=True)
            r = subprocess.run([sys.executable, str(SCRIPTS / "doctor.py"), "--repo", str(Path(tmp) / "tinyinvoice")],
                               env=dict(os.environ, HOME=str(Path(tmp) / "home")), capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            for line in ("✓ Claude Code: 1 session(s)", "✓ Codex: 1 session(s)", "✓ Antigravity: 1 session(s)",
                         "✓ narrative.md: filled in", "0 problem(s)"):
                self.assertIn(line, r.stdout)

    def test_doctor_flags_missing_setup(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = subprocess.run([sys.executable, str(SCRIPTS / "doctor.py"), "--repo", tmp],
                               env=dict(os.environ, HOME=tmp), capture_output=True, text=True)
            self.assertEqual(r.returncode, 1)
            self.assertIn("✗ .buildinpublic/: missing", r.stdout)


if __name__ == "__main__":
    unittest.main()
