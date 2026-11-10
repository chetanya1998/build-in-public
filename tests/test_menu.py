"""The skill's scripts/menu.py: every entry points at a real script and flag, and it never waits without a terminal."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "skills" / "build-in-public" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import menu  # noqa: E402


class SkillMenuTest(unittest.TestCase):
    def test_every_entry_is_a_real_script_and_flag(self):
        for label, script, args, qs in menu.entries():
            with self.subTest(script=script, args=args):
                src = (SCRIPTS / script).read_text()
                for word in args + [q[1] for q in qs if q[1]]:
                    self.assertIn(word.lstrip("-") if script.endswith(".sh") else word, src)

    def test_without_a_terminal_it_lists_and_returns(self):
        out = []
        menu.run(execute=lambda *a, **k: self.fail("ran a script"), interactive=False,
                 ask=lambda p: self.fail("asked for input"), say=out.append)
        text = "\n".join(out)
        for phrase, _ in menu.SAY:
            self.assertIn(phrase, text)
        self.assertIn("$SKILL/scripts/doctor.py", text)

    def test_pick_runs_the_script_in_this_project(self):
        answers = iter(["3", "npm test", ""])
        ran = []
        menu.run(execute=lambda cmd, cwd: ran.append((cmd, cwd)), interactive=True,
                 ask=lambda p: next(answers), say=lambda s: None)
        [(cmd, cwd)] = ran
        self.assertEqual(cmd[1:], [str(SCRIPTS / "capture.py"), "terminal", "--cmd", "npm test"])
        self.assertEqual(cwd, os.getcwd())

    def test_browser_url_defaults_to_the_project_app_url(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / ".buildinpublic").mkdir()
            (Path(tmp) / ".buildinpublic" / "config.json").write_text('{"app_url": "http://localhost:4321"}')
            here = os.getcwd()
            os.chdir(tmp)
            try:
                entry = next(e for e in menu.entries() if e[2] == ["browser"])
                self.assertEqual(menu.ask_args(entry, ask=lambda p: "", say=lambda s: None),
                                 ["browser", "--url", "http://localhost:4321"])
            finally:
                os.chdir(here)

    def test_agents_learn_help_question_mark(self):
        root = SCRIPTS.parent
        self.assertIn('"help?"', (root / "templates" / "agents-snippet.md").read_text())
        self.assertIn('"help?"', (root / "SKILL.md").read_text().split("---")[1])  # in the trigger description

    def test_risky_scripts_ask_first(self):
        entry = next(e for e in menu.entries() if e[2] == ["--share"])
        self.assertIsNone(menu.ask_args(entry, ask=lambda p: "n", say=lambda s: None))


if __name__ == "__main__":
    unittest.main()
