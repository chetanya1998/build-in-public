"""The landing page's install box: one OS per prompt, complete Windows steps, nothing cloned into a project.
(CI's site-commands jobs run these commands for real on macOS, Linux and Windows.)"""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import site_commands  # noqa: E402

PAGE = (ROOT / "docs" / "page.html").read_text(encoding="utf-8")


def panel_text(panel, os_name):
    m = re.search(rf'data-panel="{panel}" data-for="{os_name}"[^>]*><pre>(.*?)</pre>', PAGE, re.S)
    return re.sub(r"<[^>]+>", "", m.group(1))


class SiteCommandsTest(unittest.TestCase):
    def test_every_tab_has_both_systems(self):
        for panel in ("agent", "term", "cli"):
            for os_name in ("unix", "win"):
                self.assertTrue(site_commands.commands(panel, os_name), (panel, os_name))

    def test_each_prompt_is_for_one_system(self):
        unix, win = panel_text("agent", "unix"), panel_text("agent", "win")
        self.assertNotIn("Windows", unix)
        self.assertNotIn("powershell", unix.lower())
        self.assertNotIn("macOS", win)
        self.assertNotIn("install.sh", win)

    def test_never_clones_into_the_current_folder(self):
        for os_name, cmds in (("unix", site_commands.commands("agent", "unix") + site_commands.commands("term", "unix")),):
            for c in cmds:
                if "git clone" in c:
                    self.assertTrue(c.rstrip().endswith("~/build-in-public"), c)
        for panel in ("term", "cli"):
            win = site_commands.commands(panel, "win")
            self.assertEqual(win[0], "cd ~")
            self.assertEqual(win[-1], "powershell -ExecutionPolicy Bypass -File install.ps1")
        self.assertIn("'cd ~;", site_commands.commands("agent", "win")[0])

    def test_windows_box_is_not_squeezed(self):
        # .ps is the problem/solution grid; it once cut the Windows commands off mid-word
        self.assertNotRegex(PAGE, r'class="cmd[^"]*\bps\b')

    def test_built_page_matches(self):
        built = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
        for panel in ("agent", "term", "cli"):
            for os_name in ("unix", "win"):
                self.assertEqual(site_commands.commands(panel, os_name, built), site_commands.commands(panel, os_name),
                                 "docs/index.html is stale: run python3 scripts/build_pages.py")


if __name__ == "__main__":
    unittest.main()
