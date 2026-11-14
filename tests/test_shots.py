"""CLI screenshots (buildinpublic shot / watch): URLs, code images, offers, preferences.
Browser tests run only where Playwright and Chromium are installed (the CI captures job)."""
import http.server
import io
import os
import socketserver
import subprocess
import sys
import tempfile
import threading
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))


def chromium_ok():
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            p.chromium.launch().close()
        return True
    except Exception:
        return False


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name) / "home"
        self.home.mkdir()
        self.env = {"BIP_USER_HOME": str(self.home), "BUILDINPUBLIC_HOME": str(self.home / ".buildinpublic"),
                    "BIP_NO_GUI": "1"}
        self.patch = mock.patch.dict(os.environ, self.env)
        self.patch.start()
        from buildinpublic import journal, shots
        self.journal, self.shots = journal, shots
        self.app = self.home / "code" / "shop"
        self.app.mkdir(parents=True)
        (self.app / "app.py").write_text("def total(o):\n    return sum(o)\n\n\ndef tax(x):\n    return x * 0.18\n")
        projects = journal.load_projects()
        projects["shop"] = {"name": "shop", "path": str(self.app)}
        journal.save_projects(projects)
        self.server = {"url": "http://localhost:5173", "port": 5173, "process": "node",
                       "project_path": str(self.app), "via": "dev server"}

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def cli(self, *args, cwd=None):
        return subprocess.run([sys.executable, "-m", "buildinpublic", *args], cwd=cwd or self.app,
                              capture_output=True, text=True, env={**os.environ, "PYTHONPATH": str(SRC)})

    def watch(self, answer=None):
        with mock.patch.object(self.shots, "dev_servers", return_value=[self.server]), \
             mock.patch.object(self.shots, "agent_testing", return_value=[]), \
             mock.patch.object(self.shots.notify, "ask", return_value=answer) as ask, \
             mock.patch.object(self.shots, "capture_url", return_value=[self.app / "x.png"]) as cap, \
             mock.patch.object(self.shots.notify, "desktop"):
            out = io.StringIO()
            with redirect_stdout(out):
                self.shots.watch()
        return out.getvalue(), ask, cap


class UrlTest(Base):
    def test_normalize(self):
        self.assertEqual(self.shots.normalize_url("localhost:3000"), "http://localhost:3000")
        self.assertEqual(self.shots.normalize_url(" https://a.b/x "), "https://a.b/x")
        with self.assertRaises(self.shots.ShotError):
            self.shots.normalize_url(None)
        self.assertEqual(self.shots.url_base("http://localhost:3000/a?b"), "http://localhost:3000")

    def test_clear_one_or_all(self):
        st = self.shots.state()
        st["pending_shots"] = [{"url": "http://localhost:5173/"}, {"url": "http://localhost:3000"}]
        self.shots.save_state(st)
        self.shots.clear_pending("localhost:5173")
        self.assertEqual([p["url"] for p in self.shots.pending()], ["http://localhost:3000"])
        self.shots.clear_pending()
        self.assertEqual(self.shots.pending(), [])


class WatchTest(Base):
    def test_no_gui_queues_an_offer_with_its_project(self):
        out, ask, cap = self.watch(answer=None)
        self.assertIn("queued http://localhost:5173", out)
        self.assertEqual(self.shots.pending()[0]["project"], "shop")
        cap.assert_not_called()
        from buildinpublic import nudge
        text = nudge.session_start_context()
        self.assertIn("`buildinpublic shot url http://localhost:5173 --project shop`", text)
        self.assertIn("`buildinpublic shot url http://localhost:5173 --clear`", text)

    def test_cooldown_says_why_it_did_not_ask(self):
        self.watch(answer="Not now")
        out, ask, _ = self.watch(answer="Capture")
        ask.assert_not_called()
        self.assertIn("not asking again yet", out)
        self.assertNotIn("No local dev servers", out)

    def test_capture_and_never(self):
        out, _, cap = self.watch(answer="Capture")
        cap.assert_called_once_with("http://localhost:5173", "shop", None)
        st = self.shots.state()
        st["shot_prompted"] = {}
        self.shots.save_state(st)
        self.watch(answer="Never for this project")
        self.assertEqual(self.journal.load_projects()["shop"]["shots"], "never")
        st = self.shots.state()
        st["shot_prompted"] = {}
        self.shots.save_state(st)
        _, ask, cap = self.watch(answer="Capture")
        ask.assert_not_called()
        cap.assert_not_called()

    def test_always_skips_the_question(self):
        self.journal.set_project("shop", shots="always")
        _, ask, cap = self.watch(answer=None)
        ask.assert_not_called()
        cap.assert_called_once()


class ShotCommandTest(Base):
    def test_errors_are_messages_not_tracebacks(self):
        for args, msg in ((["shot", "url"], "Which URL?"),
                          (["shot", "code", "nope.py"], "No file at nope.py"),
                          (["shot", "code", "app.py", "--lines", "abc"], "--lines should look like"),
                          (["shot", "code", "app.py", "--lines", "90-99"], "aren't in app.py"),
                          (["shot", "url", "localhost:1", "--project", "zzz"], "No project called 'zzz'")):
            r = self.cli(*args)
            self.assertEqual(r.returncode, 1, (args, r.stderr))
            self.assertIn(msg, r.stderr)
            self.assertNotIn("Traceback", r.stderr)

    def test_clear_one_offer(self):
        st = self.shots.state()
        st["pending_shots"] = [{"url": "http://localhost:5173"}, {"url": "http://localhost:3000"}]
        self.shots.save_state(st)
        r = self.cli("shot", "url", "localhost:5173", "--clear")
        self.assertIn("Cleared the screenshot offer for localhost:5173", r.stdout)
        self.assertEqual([p["url"] for p in self.shots.pending()], ["http://localhost:3000"])


@unittest.skipUnless(chromium_ok(), "needs Playwright + Chromium")
class BrowserTest(Base):
    def setUp(self):
        super().setUp()
        site = self.home / "site"
        site.mkdir()
        (site / "index.html").write_text("<!doctype html><title>Shop</title><h1>Orders today: 42</h1>")
        handler = lambda *a, **k: http.server.SimpleHTTPRequestHandler(*a, directory=str(site), **k)
        http.server.SimpleHTTPRequestHandler.log_message = lambda *a: None
        self.httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
               "GIT_COMMITTER_EMAIL": "t@t"}
        for cmd in (["init", "-q"], ["add", "."], ["commit", "-qm", "init"]):
            subprocess.run(["git", "-C", str(self.app), *cmd], check=True, env=env, capture_output=True)

    def tearDown(self):
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
        super().tearDown()

    def test_url_without_scheme_goes_to_the_project(self):
        r = self.cli("shot", "url", f"127.0.0.1:{self.port}")
        self.assertEqual(r.returncode, 0, r.stderr)
        files = [Path(f) for f in r.stdout.split()]
        self.assertEqual([f.name.split("-")[-2] for f in files], ["desktop", "mobile"])
        self.assertTrue(all(f.exists() and f.stat().st_size > 5000 for f in files))
        self.assertIn(os.sep + "shop" + os.sep, str(files[0]))  # filed under the project you're in

    def test_app_not_running_is_an_error_not_a_blank_image(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.httpd = None  # nothing listens on the port now
        r = self.cli("shot", "url", f"http://127.0.0.1:{self.port}")
        self.assertEqual(r.returncode, 1)
        self.assertIn("Is the app running?", r.stderr)
        self.assertEqual(list((self.home / ".buildinpublic").rglob("app-*.png")), [])

    def test_code_shot_of_uncommitted_change(self):
        with (self.app / "app.py").open("a") as f:
            f.write("\n\ndef discount(x):\n    return x * 0.9\n")
        r = self.cli("shot", "code")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(Path(r.stdout.strip()).name.startswith("code-app-"))


if __name__ == "__main__":
    unittest.main()
