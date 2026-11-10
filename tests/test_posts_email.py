"""Briefs: reading them (brieflib), listing posts (posts.py), the clean gist email, and brief_check.py."""
import datetime as dt
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "skills" / "build-in-public" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import brief_check, brieflib, notify  # noqa: E402

DAY = dt.date(2026, 10, 27)
# The heading style real agents write (as in a brief from 2026-10-27), with Markdown everywhere
BRIEF = """# Daily Gist · 2026-10-27

## Today in one line
Quiet day — no sessions, no commits. Yesterday's end-to-end loop is live; today is a good day to post about it.

---

## What you shipped
_Nothing shipped today. The last meaningful work landed on 2026-10-26._

---

## Suggested posts

### 1. "The loop is closed. Here's what it does now." (X / behind the scenes)
**Angle:** The full flow went live (log → gist → choose → approve).
**Hook:** "I built a Claude Code skill that turns your sessions into posts."
**Anecdote:** The notification fired and the list arrived.
**Trend:** Build in public has forked. [The 2026 Guide](https://example.com/guide) — workflow camp.
**Capture:** none
**Why it works:** Concrete end-to-end story.

---

### 2. "What I'm building next" (X or LinkedIn / what's next)
**Platform:** LinkedIn
**Hook:** "My tool suggests posts. It has no idea which ones are good."
**Trend:** [Dead guide](https://example.com/blog/blog/dead)
**Why it works:** Honest roadmap.

## The story
Nothing shipped today, which is fine.

## Nearest trends
1. **Forked** — see [buildinpublic.so](https://example.com/guide)

## Screenshots to review
_No captures today._

## Capture tomorrow
1. **The gist notification**
"""
MARKDOWN = re.compile(r"\*\*|^#+ |\]\(|^-{3,}$|(?<!\w)_[^_\s][^_]*_(?!\w)", re.M)


class BriefLibTest(unittest.TestCase):
    def test_reads_heading_style_posts(self):
        posts = brieflib.suggested_posts(BRIEF)
        self.assertEqual([p["n"] for p in posts], [1, 2])
        self.assertEqual(posts[0]["title"], "The loop is closed. Here's what it does now.")
        self.assertEqual(posts[0]["platform"], "X / behind the scenes")
        self.assertEqual(posts[1]["platform"], "LinkedIn")  # an explicit **Platform:** wins
        self.assertEqual(posts[0]["fields"]["Hook"], '"I built a Claude Code skill that turns your sessions into posts."')

    def test_reads_one_line_style_posts(self):
        old = "## Suggested posts\n1. **CI lives in UTC** · X thread · rides timezone bugs\n2. **Lost payments** · LinkedIn\n"
        posts = brieflib.suggested_posts(old)
        self.assertEqual([(p["title"], p["platform"]) for p in posts], [("CI lives in UTC", "X thread"), ("Lost payments", "LinkedIn")])

    def test_links_and_text(self):
        self.assertEqual(brieflib.links(BRIEF), ["https://example.com/guide", "https://example.com/blog/blog/dead"])
        self.assertEqual(brieflib.to_text("**Trend:** [Guide](https://x.y/z) _now_"), "Trend: Guide (https://x.y/z) now")
        self.assertIn('<a href="https://x.y/z"', brieflib.to_html("[Guide](https://x.y/z) & <b>"))
        self.assertIn("&amp; &lt;b&gt;", brieflib.to_html("[Guide](https://x.y/z) & <b>"))


class Project(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name) / "build-in-public"
        out = self.repo / ".buildinpublic" / "daily" / str(DAY)
        out.mkdir(parents=True)
        (out / "brief.md").write_text(BRIEF)
        posts = self.repo / ".buildinpublic" / "posts"
        posts.mkdir()
        (posts / f"{DAY}-x-loop.md").write_text(f"---\nstatus: approved\nplatform: x\ndate: {DAY}\n---\n# The loop is closed\n\nI built a skill.\n")
        (posts / "2026-10-20-linkedin-old.md").write_text("---\nstatus: posted\nplatform: linkedin\ndate: 2026-10-20\nlink: https://l.in/p\n---\n# Old one\n\nText.\n")
        (posts / "README.md").write_text("# shared page\n")

    def tearDown(self):
        self.tmp.cleanup()

    def posts(self, *args):
        r = subprocess.run([sys.executable, str(SCRIPTS / "posts.py"), *args, "--date", str(DAY)],
                           cwd=self.repo, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout


class PostsTest(Project):
    def test_all_posts(self):
        out = self.posts()
        self.assertIn("Your posts (2): 1 approved, 1 posted", out)
        self.assertLess(out.index("The loop is closed"), out.index("Old one"))  # newest first
        self.assertNotIn("shared page", out)

    def test_today(self):
        out = self.posts("--today")
        self.assertIn("1. The loop is closed. Here's what it does now.  (X / behind the scenes)", out)
        self.assertIn("Saved today (1)", out)
        self.assertNotIn("Old one", out)

    def test_status_filter(self):
        out = self.posts("--status", "posted")
        self.assertIn("Old one", out)
        self.assertNotIn("The loop is closed\n", out)

    def test_show_suggestion_and_saved(self):
        out = self.posts("show", "2")
        self.assertIn("Hook (ready to post):", out)
        self.assertIn("Dead guide (https://example.com/blog/blog/dead)", out)
        self.assertIsNone(MARKDOWN.search(out))
        out = self.posts("show", "loop")
        self.assertIn("The loop is closed\nX · 2026-10-27 · approved\n\nI built a skill.", out)


class EmailTest(Project):
    def test_plain_text_has_no_markdown(self):
        g = notify.gist(self.repo, DAY)
        text = notify.render_text(g)
        self.assertIsNone(MARKDOWN.search(text), MARKDOWN.search(text))
        self.assertIn("1 · X / behind the scenes\nThe loop is closed. Here's what it does now.\nHook: ", text)
        self.assertIn("The 2026 Guide (https://example.com/guide)", text)

    def test_html_has_links_and_hooks(self):
        html = notify.render_html(notify.gist(self.repo, DAY))
        self.assertIn('<a href="https://example.com/guide"', html)
        self.assertNotIn("**", html)
        self.assertEqual(html.count("border-left:3px solid #2c4bd4"), 2)  # one highlighted hook per post

    def test_short_subject(self):
        s = notify.subject(self.repo, DAY, notify.gist(self.repo, DAY)["headline"])
        self.assertTrue(s.startswith("Build Your Product in Public · build-in-public · 27 Oct: Quiet day"))
        self.assertTrue(s.endswith("…"))
        self.assertLess(len(s), 130)

    def test_dead_links_are_flagged_first(self):
        out = self.repo / ".buildinpublic" / "daily" / str(DAY)
        (out / "brief-check.json").write_text(json.dumps({"dead_links": ["https://example.com/blog/blog/dead"]}))
        g = notify.gist(self.repo, DAY)
        self.assertTrue(notify.render_text(g).startswith("CHECK BEFORE POSTING: 1 link(s)"))
        self.assertIn("Check before posting:", notify.render_html(g))


class BriefCheckTest(unittest.TestCase):
    def fake(self, url):
        return ("dead", "HTTP 404") if "dead" in url else ("ok", "200")

    def test_dead_link_is_an_error(self):
        r = brief_check.check(BRIEF, link_check=self.fake)
        self.assertEqual(r["dead_links"], ["https://example.com/blog/blog/dead"])
        self.assertEqual(r["errors"], ["Dead link (HTTP 404): https://example.com/blog/blog/dead"])

    def test_missing_fields_and_sections(self):
        r = brief_check.check(BRIEF.replace("## Capture tomorrow", "## Later"), offline=True)
        self.assertIn("Missing section: ## Capture tomorrow", r["errors"])
        self.assertTrue(any("Post 1" in w and "Platform" not in w for w in r["warnings"]) or r["warnings"] == [])

    def test_template_itself_has_every_section(self):
        tpl = (SCRIPTS.parent / "templates" / "brief.md").read_text()
        r = brief_check.check(tpl, offline=True)
        self.assertEqual(r["errors"], [])


# A brief in the current format: each post written out, ready to copy
READY = """## Today in one line
Windows installs work when an agent runs them.

## What you shipped
- Fixed setup crashing on Windows (f0de887)

## Suggested posts

### 1. The check mark that crashed my installer
**Platform:** LinkedIn
**Post:**
```text
My installer worked on Windows when I ran it. It crashed when an AI agent ran it.

The cause was a check mark: a pipe on Windows uses cp1252, which can't encode ✓.

I build a skill that turns coding sessions into posts, and agents now run most installs.

Do you test your CLI with its output piped?

#buildinpublic #python #windows
```
**Screenshot:** daily/2026-11-10/captures/a1b2c3.png
**Angle:** A bug that only exists when nobody is at the keyboard.
**Anecdote:** The UnicodeEncodeError from the session on Nov 10.
**Context:** Commit f0de887 and the README's install section.
**Trend:** no trend
**Why it works:** One tiny, concrete cause.

### 2. One check mark, two bugs
**Platform:** X thread
**Post:**
```text
1/ My installer crashed only when an agent ran it.

2/ Windows pipes use cp1252. ✓ isn't in it.

3/ Have you hit this? #python
```
**Screenshot:** No screenshot
**Trend:** [A thread](https://example.com/thread)
**Why it works:** Short and specific.

## The story
x

## Nearest trends
x

## Screenshots to review
none

## Capture tomorrow
x
"""


class ReadyPostTest(unittest.TestCase):
    def test_post_block_keeps_its_line_breaks(self):
        posts = brieflib.suggested_posts(READY)
        self.assertEqual([p["platform"] for p in posts], ["LinkedIn", "X thread"])
        post = posts[0]["fields"]["Post"]
        self.assertTrue(post.startswith("My installer worked on Windows when I ran it."))
        self.assertIn("encode ✓.\n\nI build", post)
        self.assertTrue(post.endswith("#buildinpublic #python #windows"))
        self.assertFalse(any("```" in v for v in posts[0]["fields"].values()))  # the block isn't left in another field
        self.assertEqual(posts[0]["fields"]["Context"], "Commit f0de887 and the README's install section.")

    def test_good_brief_has_no_errors(self):
        r = brief_check.check(READY, offline=True)
        self.assertEqual(r["errors"], [])

    def test_x_counts_each_post_and_links_as_23(self):
        self.assertEqual(brieflib.x_length("see https://example.com/" + "a" * 100), 4 + 23)
        s = brieflib.post_stats("X post", "a" * 281 + "?\n#x")
        self.assertTrue(s["errors"] and "X allows 280" in s["errors"][0])
        thread = "1/ " + "a" * 200 + "\n\n2/ " + "b" * 279 + "\n\n3/ ok? #x"
        s = brieflib.post_stats("X thread", thread)
        self.assertEqual(len(s["errors"]), 1)
        self.assertIn("part 2 of the thread", s["errors"][0])

    def test_linkedin_characters_words_and_fold(self):
        body = " ".join(["word"] * 320)
        s = brieflib.post_stats("LinkedIn", body + "\n\nThoughts?\n\n#a #b")
        self.assertTrue(any("words" in e for e in s["errors"]))
        s = brieflib.post_stats("LinkedIn", "x" * 3001)
        self.assertTrue(any("3000" in e for e in s["errors"]))
        s = brieflib.post_stats("LinkedIn", "h" * 230 + "\n\nWhy?\n\n#a")
        self.assertEqual(s["errors"], [])
        self.assertTrue(any("see more" in w for w in s["warnings"]))

    def test_limits_from_config_win(self):
        s = brieflib.post_stats("LinkedIn", " ".join(["w"] * 60) + "?\n#a", {"linkedin": {"words": 50}})
        self.assertTrue(any("under 50" in e for e in s["errors"]))

    def test_missing_question_and_hashtags_are_warnings(self):
        s = brieflib.post_stats("LinkedIn", "Just a statement.")
        self.assertEqual(s["errors"], [])
        self.assertEqual(len(s["warnings"]), 2)

    def test_markdown_in_a_post_is_a_warning(self):
        s = brieflib.post_stats("LinkedIn", "Run `setup` now.\n\nWhy?\n\n#a")
        self.assertTrue(any("Markdown" in w for w in s["warnings"]))

    def test_over_the_limit_is_an_error_in_the_check(self):
        r = brief_check.check(READY.replace("Do you test", "x" * 3000 + " Do you test"), offline=True)
        self.assertTrue(any("Post 1" in e and "LinkedIn allows 3000" in e for e in r["errors"]))

    def test_older_hook_only_post_is_a_warning(self):
        r = brief_check.check(BRIEF, offline=True)
        self.assertFalse(any("ready-to-post" in e for e in r["errors"]))
        self.assertTrue(any("older format" in w for w in r["warnings"]))


class ReadyEmailTest(Project):
    def setUp(self):
        super().setUp()
        (self.repo / ".buildinpublic" / "daily" / str(DAY) / "brief.md").write_text(READY)

    def test_text_puts_the_post_first(self):
        text = notify.render_text(notify.gist(self.repo, DAY))
        self.assertIn("1 · LinkedIn · ", text)
        start = text.index("----- copy from here -----\nMy installer worked")
        self.assertLess(start, text.index("How this post was made"))
        self.assertIn("#buildinpublic #python #windows\n----- to here -----", text)
        self.assertIn("Screenshot: daily/2026-11-10/captures/a1b2c3.png", text)
        self.assertIn("No screenshot", text)
        self.assertIn("   Angle: A bug that only exists", text)

    def test_html_has_copy_box_and_link_that_round_trips(self):
        g = notify.gist(self.repo, DAY)
        html = notify.render_html(g)
        self.assertIn("white-space:pre-wrap", html)
        self.assertIn(">Copy post</a>", html)
        self.assertIn("How this post was made", html)
        link = g["posts"][0]["copy"]
        self.assertTrue(link.startswith(notify.COPY_PAGE + "#p=LinkedIn&t="))
        data = link.split("&t=", 1)[1]
        import base64
        decoded = base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode()
        self.assertEqual(decoded, g["posts"][0]["fields"]["Post"])

    def test_copy_page_can_be_turned_off(self):
        (self.repo / ".buildinpublic" / "config.json").write_text('{"copy_page": ""}')
        g = notify.gist(self.repo, DAY)
        self.assertEqual(g["posts"][0]["copy"], "")
        self.assertNotIn(">Copy post</a>", notify.render_html(g))

    def test_unchecked_links_are_listed(self):
        out = self.repo / ".buildinpublic" / "daily" / str(DAY)
        (out / "brief-check.json").write_text(json.dumps({"dead_links": [], "unchecked_links": ["https://example.com/x"]}))
        g = notify.gist(self.repo, DAY)
        self.assertTrue(notify.render_text(g).startswith("OPEN BEFORE POSTING: 1 link(s)"))


class RedirectTest(unittest.TestCase):
    def test_308_is_followed(self):
        import http.server, threading

        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_HEAD(self):
                if self.path == "/old":
                    self.send_response(308)
                    self.send_header("Location", "/new")
                else:
                    self.send_response(200 if self.path == "/new" else 404)
                self.end_headers()

        server = http.server.HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            base = f"http://127.0.0.1:{server.server_port}"
            self.assertEqual(brief_check.check_link(base + "/old"), ("ok", "200"))
            self.assertEqual(brief_check.check_link(base + "/gone")[0], "dead")
        finally:
            server.shutdown()


if __name__ == "__main__":
    unittest.main()
