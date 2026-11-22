"""Screenshots from Claude Code sessions become candidates, approved ones get a window frame, and
the gist shows them: thumbnails on the saved page, attachments in the email, ids to approve."""
import datetime as dt
import json
import os
import random
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest import mock

SKILL = Path(__file__).resolve().parent.parent / "skills" / "build-in-public"
sys.path.insert(0, str(SKILL / "scripts"))
import capture, collect, fallback_brief, notify  # noqa: E402

DAY = dt.date.today()


def noisy_png(path, w=640, h=400, seed=0):
    """A real PNG big enough to count as a screenshot (noise doesn't compress)."""
    rnd = random.Random(seed)
    raw = b"".join(b"\x00" + bytes(rnd.getrandbits(8) for _ in range(w * 3)) for _ in range(h))
    chunk = lambda t, d: struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(raw, 1)) + chunk(b"IEND", b""))
    return path


def playwright_ok():
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            p.chromium.launch().close()
        return True
    except Exception:
        return False


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.home = self.tmp / "home"
        self.repo = self.tmp / "code" / "shop"
        self.repo.mkdir(parents=True)
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        enc = "".join(c if c.isalnum() else "-" for c in str(self.repo))
        self.results = self.home / ".claude" / "projects" / enc / "abc123" / "tool-results"
        self.patch = mock.patch.object(collect, "HOME", self.home)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)


class FindTest(Base):
    def test_session_screenshots_are_candidates(self):
        a = noisy_png(self.results / "mcp-Claude_Browser-blob-1-a.png", seed=1)
        shutil.copy(a, self.results / "mcp-Claude_Browser-blob-2-copy.png")          # duplicate
        noisy_png(self.results / "mcp-Claude_Browser-blob-3-b.png", seed=2)
        (self.results / "tiny-crop.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 500)  # too small
        old = noisy_png(self.results / "yesterday.png", seed=3)
        t = (dt.datetime.now() - dt.timedelta(days=2)).timestamp()
        os.utime(old, (t, t))
        found = collect.claude_media(self.repo, DAY)
        self.assertEqual(len(found), 2)
        self.assertNotIn("yesterday.png", [f.name for f in found])
        self.assertEqual(len(collect.find_candidates(self.repo, DAY, [])), 2)

    def test_other_projects_screenshots_are_not(self):
        other = self.home / ".claude" / "projects" / "-tmp-elsewhere" / "s" / "tool-results"
        noisy_png(other / "x.png")
        self.assertEqual(collect.claude_media(self.repo, DAY), [])

    def test_image_size(self):
        self.assertEqual(capture.image_size(noisy_png(self.tmp / "a.png", 320, 200)), (320, 200))


class GistTest(Base):
    def setUp(self):
        super().setUp()
        noisy_png(self.results / "blob-1.png", seed=1)
        self.out = self.repo / ".buildinpublic" / "daily" / str(DAY)
        (self.out / "captures").mkdir(parents=True)
        approved = noisy_png(self.out / "captures" / "c0ffee-screenshot.png", seed=9)
        (self.out / "captures" / "captures.json").write_text(json.dumps({"captures": [
            {"id": "c0ffee", "kind": "screenshot", "title": "Billing page", "note": "", "source": "x",
             "files": {"image": approved.name}, "time": "18:00"}], "rejected": []}))

    def test_saved_page_shows_thumbnails_email_does_not(self):
        g = notify.gist(self.repo, DAY)
        self.assertEqual([s["id"] for s in g["shots"]], ["c0ffee"])
        self.assertEqual(len(g["waiting"]), 1)
        wid = g["waiting"][0]["id"]
        text = notify.render_text(g)
        self.assertIn("c0ffee  Billing page  (attached)", text)
        self.assertIn(f"capture.py approve {wid}", text)
        email = notify.render_html(g)
        self.assertNotIn("file://", email)                      # nothing local in the email
        page = notify.render_html(g, local=True)
        self.assertEqual(page.count("<img src=\"file://"), 2)   # approved + waiting
        msg = notify.compose({"to": "me@example.com"}, self.repo, DAY, "h", text, email,
                             [s["path"] for s in g["shots"]])
        names = [p.get_filename() for p in msg.iter_attachments()]
        self.assertIn("c0ffee-screenshot.png", names)
        self.assertNotIn("blob-1.png", names)                   # waiting ones are never sent

    def test_no_agent_brief_suggests_a_waiting_screenshot(self):
        (self.out / "captures" / "captures.json").write_text('{"captures": [], "rejected": []}')
        (self.out / "digest.md").write_text(f"# Digest {DAY}\n\n## Git commits\n- 10:00 abc1234 Billing page redesign\n")
        path, n = fallback_brief.build(self.repo, DAY)
        wid = capture.pending(self.repo, DAY)[0][0]
        self.assertIn(f"Screenshot {wid} from today's session could fit: approve it first", path.read_text())


@unittest.skipUnless(playwright_ok(), "needs Playwright + Chromium")
class FrameTest(Base):
    def test_approve_saves_a_framed_copy(self):
        noisy_png(self.results / "blob-1.png", 900, 560, seed=4)
        cid = capture.pending(self.repo, DAY)[0][0]
        with mock.patch.object(sys, "argv", ["capture.py", "--repo", str(self.repo), "--date", str(DAY), "approve", cid,
                                             "--approved", "--label", "localhost:3000/billing"]):
            capture.main()
        out = self.repo / ".buildinpublic" / "daily" / str(DAY) / "captures"
        c = json.loads((out / "captures.json").read_text())["captures"][0]
        self.assertEqual(c["files"]["image"], f"{cid}-screenshot.png")
        w, h = capture.image_size(out / c["files"]["image"])
        self.assertGreater(w, 900)          # the frame adds a border and a window bar
        self.assertTrue((out / c["files"]["raw"]).exists())
        self.assertEqual(capture.pending(self.repo, DAY), [])  # decided: not offered again

    def test_tall_screenshots_get_a_phone(self):
        src = noisy_png(self.tmp / "tall.png", 300, 650, seed=5)
        self.assertIn("border-radius:44px", capture.frame_html(src))
        self.assertIsNone(capture.frame_png(src, self.tmp / "framed.png"))
        self.assertTrue((self.tmp / "framed.png").exists())


if __name__ == "__main__":
    unittest.main()
