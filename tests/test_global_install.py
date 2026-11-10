"""Where `buildinpublic setup` finds the skill it installs into each agent.

Installed with pip, the skill lives at <site-packages>/buildinpublic/skills/build-in-public.
On Python 3.9, importlib.resources.files() raises TypeError for that namespace package,
which used to send setup to a repo-checkout path that doesn't exist, and crash.
"""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from buildinpublic import integrations  # noqa: E402


def fake_install(root):
    """A pip-style layout: <root>/site-packages/buildinpublic/{integrations.py, skills/build-in-public/SKILL.md}."""
    pkg = Path(root) / "site-packages" / "buildinpublic"
    skill = pkg / "skills" / "build-in-public"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("---\nname: build-in-public\n---\n")
    return pkg, skill


class SkillSourceTest(unittest.TestCase):
    def test_installed_layout_when_resources_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            pkg, skill = fake_install(tmp)
            with mock.patch.object(integrations, "__file__", str(pkg / "integrations.py")), \
                    mock.patch.object(integrations.resources, "files", side_effect=TypeError("3.9 namespace package")):
                self.assertEqual(integrations.skill_source(), skill.resolve())

    def test_git_checkout(self):
        src = integrations.skill_source()
        self.assertTrue((src / "SKILL.md").exists())
        self.assertEqual(src.name, "build-in-public")

    def test_missing_skill_is_a_clear_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp) / "a" / "b" / "buildinpublic"
            pkg.mkdir(parents=True)
            with mock.patch.object(integrations, "__file__", str(pkg / "integrations.py")), \
                    mock.patch.object(integrations.resources, "files", side_effect=TypeError):
                with self.assertRaises(FileNotFoundError) as e:
                    integrations.skill_source()
                self.assertIn("Reinstall", str(e.exception))


class Cp1252OutputTest(unittest.TestCase):
    """An agent runs the CLI with output on a pipe; on Windows that pipe is cp1252."""

    def test_cli_prints_check_marks_to_a_cp1252_pipe(self):
        import os, subprocess
        with tempfile.TemporaryDirectory() as tmp:
            env = dict(os.environ, PYTHONIOENCODING="cp1252", BIP_USER_HOME=tmp,
                       BUILDINPUBLIC_HOME=str(Path(tmp) / ".buildinpublic"), BIP_NO_GUI="1",
                       PYTHONPATH=str(Path(__file__).resolve().parents[1] / "src"))
            (Path(tmp) / ".claude").mkdir()
            r = subprocess.run([sys.executable, "-m", "buildinpublic", "doctor"], env=env,
                               capture_output=True, text=True, encoding="utf-8", errors="replace")
            self.assertNotIn("UnicodeEncodeError", r.stderr)
            self.assertIn("\u2713", r.stdout)


if __name__ == "__main__":
    unittest.main()
