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


if __name__ == "__main__":
    unittest.main()
