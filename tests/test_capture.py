"""Tests for capture.py: nothing is captured without approval, and output is redacted."""
import json, os, sys, unittest
from pathlib import Path

from test_collect import DAY, SCRIPTS, Fixture, fx

sys.path.insert(0, str(SCRIPTS))
import capture  # noqa: E402

try:
    import playwright  # noqa: F401
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False


class CaptureTest(Fixture):
    def cap(self, *args):
        return self.run_script("capture.py", "--date", str(DAY), *args)

    def captures_dir(self):
        return self.repo / ".buildinpublic" / "daily" / str(DAY) / "captures"

    def manifest(self):
        return json.loads((self.captures_dir() / "captures.json").read_text())

    def test_refuses_without_approval(self):
        r = self.cap("terminal", "--cmd", "echo hello")
        self.assertEqual(r.returncode, 2)
        self.assertIn("Needs the user's approval", r.stderr)
        self.assertFalse((self.captures_dir() / "captures.json").exists())

    def test_refuses_when_turned_off(self):
        cfg = self.repo / ".buildinpublic" / "config.json"
        cfg.write_text(json.dumps(dict(json.loads(cfg.read_text()), capture="off")))
        r = self.cap("terminal", "--cmd", "echo hello", "--approved")
        self.assertEqual(r.returncode, 2)
        self.assertIn("turned off", r.stderr)

    def test_terminal_capture_is_redacted(self):
        cmd = "printf '\\033[32m214 passed\\033[0m token=abc123secret456 for Acme Corp\\n'"
        r = self.cap("terminal", "--cmd", cmd, "--title", "npm test", "--note", "green at last", "--approved")
        self.assertEqual(r.returncode, 0, r.stderr)
        [c] = self.manifest()["captures"]
        self.assertEqual((c["kind"], c["title"], c["note"], c["exit_code"]), ("terminal", "npm test", "green at last", 0))
        text = (self.captures_dir() / c["files"]["text"]).read_text()
        self.assertIn("214 passed", text)
        for leaked in ("abc123secret456", "Acme", "\x1b["):
            self.assertNotIn(leaked, text)
        if HAS_PLAYWRIGHT:
            self.assertTrue((self.captures_dir() / c["files"]["image"]).exists())
        else:
            self.assertNotIn("image", c["files"])
            self.assertIn("Playwright not installed", r.stdout)

    def test_terminal_from_file(self):
        out = self.repo.parent / "bench.txt"
        out.write_text("p95 latency: 840ms -> 120ms\n")
        r = self.cap("terminal", "--file", str(out), "--title", "bench", "--approved")
        self.assertEqual(r.returncode, 0, r.stderr)
        [c] = self.manifest()["captures"]
        self.assertIsNone(c["exit_code"])
        self.assertIn("840ms -> 120ms", (self.captures_dir() / c["files"]["text"]).read_text())

    def test_candidates_approve_reject(self):
        shot = self.repo / ".playwright-mcp" / "checkout.png"
        shot.parent.mkdir()
        shot.write_bytes(fx.png())
        fx.touch_on(shot, DAY)

        r = self.cap("candidates")
        self.assertIn(".playwright-mcp/checkout.png", r.stdout)
        self.assertIn("onboarding-after.png", r.stdout)  # from Antigravity
        ids = {line.split()[1]: line.split()[0] for line in r.stdout.splitlines() if line.startswith("  ")}
        keep = ids[".playwright-mcp/checkout.png"]
        skip = next(i for p, i in ids.items() if p.endswith("onboarding-after.png"))

        self.assertEqual(self.cap("approve", keep).returncode, 2)  # still needs a yes
        self.assertEqual(self.cap("approve", keep, "--approved").returncode, 0)
        self.assertEqual(self.cap("reject", skip).returncode, 0)
        self.assertIn("No new screenshots", self.cap("candidates").stdout)

        [c] = self.manifest()["captures"]
        self.assertEqual(c["kind"], "screenshot")
        self.assertTrue((self.captures_dir() / c["files"]["image"]).exists())

        digest = self.digest()
        approved = digest.split("## Approved captures")[1].split("## Screenshot candidates")[0]
        self.assertIn(c["id"], approved)
        self.assertIn("_none_", digest.split("## Screenshot candidates")[1])

    def test_browser_needs_url(self):
        cfg = self.repo / ".buildinpublic" / "config.json"
        cfg.write_text(json.dumps({k: v for k, v in json.loads(cfg.read_text()).items() if k != "app_url"}))
        r = self.cap("browser", "--approved")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("No URL", r.stderr)


class AnsiTest(unittest.TestCase):
    def test_colours_and_escaping(self):
        out = capture.ansi_to_html("\x1b[1;32mok\x1b[0m <b>&")
        self.assertIn('<span style="color:#89ca78;font-weight:700">ok</span>', out)
        self.assertIn("&lt;b&gt;&amp;", out)


if __name__ == "__main__":
    unittest.main()
