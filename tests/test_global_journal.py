"""End-to-end tests with synthetic Claude Code, Codex and Antigravity sessions.
Runs on macOS, Windows and Linux with only the standard library:
    python -m unittest discover -s tests -v
"""
import datetime as dt
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def git(repo: Path, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True,
                   env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"})


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.home = self.tmp / "home"
        self.home.mkdir()
        os.environ["BIP_USER_HOME"] = str(self.home)
        os.environ["BUILDINPUBLIC_HOME"] = str(self.home / ".buildinpublic")
        os.environ["BIP_NO_GUI"] = "1"
        self.repo = self.home / "code" / "saas-cost-estimator"
        self.repo.mkdir(parents=True)
        git(self.repo, "init", "-q")
        (self.repo / "app.py").write_text("def price(x):\n    return round(x * 1.18, 2)\n")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-qm", "init")
        self.other = self.home / "code" / "client-work"
        self.other.mkdir(parents=True)
        now = dt.datetime.now().astimezone()
        self.ts = (now - dt.timedelta(minutes=50)).isoformat(), now.isoformat()
        self.make_claude()
        self.make_codex()
        self.make_antigravity()

    def make_claude(self):
        d = self.home / ".claude" / "projects" / "-code-saas-cost-estimator"
        d.mkdir(parents=True)
        recs = [
            {"type": "user", "timestamp": self.ts[0], "cwd": str(self.repo),
             "message": {"role": "user", "content": "Fix the pricing rounding bug, key sk-ant-abcdefghijklmnopqrstuv"}},
            {"type": "assistant", "timestamp": self.ts[1], "message": {"role": "assistant", "content": [
                {"type": "text", "text": "Fixed: totals showed $9.999 due to float error. Cut page load 4.2s -> 0.9s."},
                {"type": "tool_use", "name": "Edit", "input": {"file_path": str(self.repo / "app.py")}},
                {"type": "tool_use", "name": "Bash", "input": {"command": "npm run dev"}},
                {"type": "tool_use", "name": "mcp__playwright__browser_navigate", "input": {"url": "http://localhost:3000/pricing"}},
            ]}},
        ]
        (d / "abc12345-claude.jsonl").write_text("\n".join(json.dumps(r) for r in recs))

    def make_codex(self):
        today = dt.date.today()
        d = self.home / ".codex" / "sessions" / f"{today:%Y}" / f"{today:%m}" / f"{today:%d}"
        d.mkdir(parents=True)
        recs = [
            {"timestamp": self.ts[0], "type": "session_meta", "payload": {"cwd": str(self.other)}},
            {"timestamp": self.ts[0], "type": "response_item", "payload": {"type": "message", "role": "user",
             "content": [{"type": "input_text", "text": "Refactor the invoice exporter"}]}},
            {"timestamp": self.ts[1], "type": "response_item", "payload": {"type": "function_call", "name": "shell",
             "arguments": json.dumps({"command": ["bash", "-lc", "pytest"]})}},
            {"timestamp": self.ts[1], "type": "response_item", "payload": {"type": "message", "role": "assistant",
             "content": [{"type": "output_text", "text": "Refactored exporter, tests pass."}]}},
        ]
        (d / "rollout-2026-xyz98765.jsonl").write_text("\n".join(json.dumps(r) for r in recs))

    def make_antigravity(self):
        d = self.home / ".gemini" / "antigravity" / "brain" / "conv-7777"
        d.mkdir(parents=True)
        (d / "task.md").write_text(f"Add a signup page to file://{self.repo}/app.py")
        (d / "walkthrough.md").write_text("Verified the signup flow in the browser. Shipped the first signup.")
        (d / "screenshot_signup.png").write_bytes(b"\x89PNG\r\n\x1a\nfake")


class TestJournal(Base):
    def test_sweep_captures_all_agents_and_projects(self):
        from buildinpublic import journal
        rep = journal.sweep(days=2, quiet=True)
        self.assertEqual(len(rep["captured"]), 3, rep)
        projects = journal.load_projects()
        self.assertIn("saas-cost-estimator", projects)
        self.assertIn("client-work", projects)
        p = projects["saas-cost-estimator"]
        self.assertEqual(sorted(p["agents"]), ["antigravity", "claude-code"])
        self.assertEqual(p["status"], "new")

    def test_redaction_and_tags(self):
        from buildinpublic import journal
        journal.sweep(days=2, quiet=True)
        m = next(m for m in journal.all_meta() if m["agent"] == "claude-code")
        blob = json.dumps(m)
        self.assertNotIn("sk-ant-abcdef", blob)
        self.assertIn("[REDACTED]", blob)
        self.assertIn("#metric", m["tags"])
        self.assertIn("#war-story", m["tags"])
        self.assertEqual(m["files"], ["app.py"])
        self.assertIn("http://localhost:3000/pricing", m["browser_urls"])
        self.assertGreaterEqual(m["score"], 4)

    def test_incremental_is_idempotent(self):
        from buildinpublic import journal
        journal.sweep(days=2, quiet=True)
        rep = journal.sweep(days=2, quiet=True)
        self.assertEqual(rep["captured"], [])
        self.assertEqual(journal.load_projects()["saas-cost-estimator"]["sessions"], 2)

    def test_exclude(self):
        from buildinpublic import journal
        from buildinpublic.core import set_config_value
        set_config_value("exclude", json.dumps([str(self.home / "code" / "client-*")]))
        rep = journal.sweep(days=2, quiet=True)
        self.assertEqual(rep["skipped_excluded"], 1)
        self.assertNotIn("client-work", journal.load_projects())

    def test_day_week_search(self):
        from buildinpublic import journal
        from buildinpublic.core import today
        journal.sweep(days=2, quiet=True)
        day = journal.build_day(today()).read_text()
        self.assertIn("saas-cost-estimator", day)
        week = journal.build_week().read_text()
        self.assertIn("| saas-cost-estimator |", week)
        hits = journal.search("rounding")
        self.assertEqual(len(hits), 1)

    def test_antigravity_project_and_media(self):
        from buildinpublic import journal
        journal.sweep(days=2, quiet=True)
        m = next(m for m in journal.all_meta() if m["agent"] == "antigravity")
        self.assertEqual(m["project"], "saas-cost-estimator")
        self.assertTrue(any("screenshot_signup" in s for s in m["shots"]))
        self.assertIn("#milestone", m["tags"])


class TestBriefAndNudge(Base):
    def test_summary_no_content_projects_is_honest(self):
        from buildinpublic import brief
        out = brief.build(send=False, research_on=False).read_text()
        self.assertIn("No strong story today", out)
        self.assertIn("journal-only", out)
        self.assertIn("New projects found", out)

    def test_summary_with_content_writes_starter_draft(self):
        from buildinpublic import brief, journal, nudge
        from buildinpublic.core import set_config_value
        set_config_value("draft_agent", "none")
        journal.sweep(days=2, quiet=True)
        journal.set_project("saas-cost-estimator", status="content")
        out = brief.build(send=False, research_on=False).read_text()
        self.assertIn("Today's story", out)
        self.assertEqual(len(nudge.waiting_drafts()), 1)

    def test_nudge_after_two_days_and_session_start(self):
        from buildinpublic import journal, nudge
        from buildinpublic.core import save_state, state
        journal.sweep(days=2, quiet=True)
        st = state()
        st["installed_at"] = (dt.datetime.now() - dt.timedelta(days=3)).isoformat()
        save_state(st)
        text = nudge.check()
        self.assertIsNotNone(text)
        self.assertIn("3 day(s)", text)
        ctx = nudge.session_start_context()
        self.assertIn("<build-in-public>", ctx)
        self.assertIn("New projects found", ctx)
        nudge.reply("Working on Stripe usage billing")
        self.assertTrue((Path(os.environ["BUILDINPUBLIC_HOME"]) / "inbox").exists())

    def test_posted_resets_timer(self):
        from buildinpublic import nudge
        f = Path(os.environ["BUILDINPUBLIC_HOME"]) / "posts" / "x.md"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("# Hello world post\n")
        nudge.scan_drafts()
        nudge.mark("latest", "posted")
        self.assertEqual(nudge.days_since_post(), 0)
        self.assertEqual(nudge.waiting_drafts(), [])


class TestIntegrations(Base):
    def test_install_and_uninstall_hooks(self):
        from buildinpublic import integrations
        (self.home / ".claude" / "settings.json").write_text(json.dumps(
            {"hooks": {"SessionEnd": [{"hooks": [{"type": "command", "command": "echo mine"}]}]}, "model": "x"}))
        integrations.install_all()
        s = json.loads((self.home / ".claude" / "settings.json").read_text())
        self.assertEqual(len(s["hooks"]["SessionEnd"]), 2)
        self.assertIn("SessionStart", s["hooks"])
        self.assertIn("codex_hooks = true", (self.home / ".codex" / "config.toml").read_text())
        self.assertIn("buildinpublic:start", (self.home / ".gemini" / "GEMINI.md").read_text())
        self.assertTrue((self.home / ".claude" / "skills" / "build-in-public" / "SKILL.md").exists())
        integrations.install_all()  # idempotent
        s = json.loads((self.home / ".claude" / "settings.json").read_text())
        self.assertEqual(len(s["hooks"]["SessionEnd"]), 2)
        integrations.uninstall_all()
        s = json.loads((self.home / ".claude" / "settings.json").read_text())
        self.assertEqual(s["hooks"]["SessionEnd"][0]["hooks"][0]["command"], "echo mine")
        self.assertEqual(s["model"], "x")
        self.assertNotIn("buildinpublic", (self.home / ".codex" / "config.toml").read_text())

    def test_cli_smoke(self):
        from buildinpublic import cli
        buf = io.StringIO()
        with redirect_stdout(buf):
            cli.main(["sweep", "--quiet"])
            cli.main(["today"])
            cli.main(["projects"])
            cli.main(["project", "saas-cost-estimator", "content"])
            cli.main(["search", "invoice"])
            cli.main(["posts"])
            cli.main(["config", "set", "nudge_after_days", "3"])
        out = buf.getvalue()
        self.assertIn("Journal ·", out)
        self.assertIn("content on", out)
        self.assertIn("client-work", out)

    def test_email_address_shared_with_skill(self):
        from buildinpublic import notify
        shared = self.home / ".config" / "buildinpublic" / "email.json"
        shared.parent.mkdir(parents=True)
        shared.write_text(json.dumps({"to": "me@example.com"}))
        es = notify.email_settings()
        self.assertEqual(es["to"], "me@example.com")
        self.assertIn(es["method"], ("mail-app", "sendmail", "smtp"))

    def test_skill_source_is_repo_skill(self):
        from buildinpublic import integrations
        self.assertTrue((integrations.skill_source() / "SKILL.md").exists())
        self.assertEqual(integrations.skill_source().name, "build-in-public")

    def test_code_image_html_fallback_or_png(self):
        from buildinpublic import shots
        out = shots.code_image(self.repo / "app.py", self.tmp / "code.png", title="app.py")
        self.assertTrue(out.exists())
        self.assertIn(out.suffix, (".png", ".html"))


if __name__ == "__main__":
    unittest.main()
