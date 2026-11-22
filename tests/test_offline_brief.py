"""When the agent can't write the brief, the gist still has posts (fallback_brief.py), is saved on
this computer exactly as emailed, and the email says where. A stuck agent is stopped on time."""
import datetime as dt
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent / "skills" / "build-in-public"
sys.path.insert(0, str(SKILL / "scripts"))
import brief_check, brieflib, fallback_brief, notify  # noqa: E402

DAY = dt.date.today()
DIGEST = f"""# Digest {DAY} · shop

Sessions found: Claude Code 1, Codex 0, Antigravity 0 (total 1)

## Claude Code session 1
**User asked:**
- Add Stripe webhooks so payments that fail at night get retried. Right now we lose them.
- yes
- commit and push
**Agent said (last messages):**
- Done.
**Tool calls:** 84
**Files edited:** api/webhooks.py, api/retry.py, tests/test_retry.py

## Git commits
- 18:20 a1b2c3d Retry failed Stripe webhooks
 3 files changed, 214 insertions(+), 9 deletions(-)
- 17:02 d4e5f6a Update logo (by Sam)
 1 file changed, 0 insertions(+), 0 deletions(-)

## Uncommitted changes
_none_

## Agent log entries (.buildinpublic/log)
### 18:30 - Webhook retries  (agent: claude)
- **What:** Failed Stripe webhooks now retry with backoff
- **Why:** We lost 3 payments last week when the server restarted at night
- **Struggle:** Stripe signs each retry again, so the signature check kept failing until we verified the raw body
- **Result:** 0 lost payments in the replay test of 1,000 events

## Approved captures (use only these in posts)
_none_

## Screenshot candidates (not approved: ask the user before using any)
_none_
"""
TRENDS = """# Trends

## Project: payments reliability
**Hacker News**
- [Why webhooks fail silently](https://example.com/webhooks) · 120 points

## Stack: stripe
**dev.to**
- [Idempotency keys in practice](https://example.com/idempotency) · 30 reactions

## Unreachable sources
- www.reddit.com: HTTP Error 403
"""


class FallbackBriefTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.repo = self.tmp / "shop"
        self.out = self.repo / ".buildinpublic" / "daily" / str(DAY)
        self.out.mkdir(parents=True)
        (self.out / "digest.md").write_text(DIGEST)
        (self.out / "trends.md").write_text(TRENDS)
        (self.repo / ".buildinpublic" / "config.json").write_text('{"platforms": ["x", "linkedin"], "topics": ["payments"]}')
        (self.repo / "README.md").write_text("# Shop\n\nShop is a checkout for small online stores that never loses a payment.\n")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_posts_from_the_day(self):
        path, n = fallback_brief.build(self.repo, DAY, "claude was signed out")
        text = path.read_text()
        self.assertTrue(text.startswith(fallback_brief.MARK))
        posts = brieflib.suggested_posts(text)
        self.assertEqual(len(posts), n)
        self.assertGreaterEqual(n, 4)
        first = posts[0]["fields"]["Post"]
        self.assertIn("Webhook retries", posts[0]["title"])
        self.assertIn("signature check kept failing", first)   # the real moment from the log entry
        self.assertIn("Sam", text)                             # someone else's commit: listed as shipped...
        self.assertNotIn("### 5. Update logo", text)           # ...but not made into a post
        for p in posts:
            self.assertEqual(brieflib.post_stats(p["platform"], p["fields"]["Post"])["errors"], [], p["platform"])
        self.assertIn("https://example.com/webhooks", text)    # today's reference articles
        self.assertNotIn("reddit", text)
        self.assertEqual(brief_check.check(text, offline=True)["errors"], [])

    def test_quiet_day(self):
        (self.out / "digest.md").write_text(f"# Digest {DAY}\n\nSessions found: (total 0)\n\n## Git commits\n_none_\n")
        path, n = fallback_brief.build(self.repo, DAY)
        self.assertEqual(n, 0)
        self.assertEqual(brief_check.check(path.read_text(), offline=True)["errors"], [])

    def test_email_and_local_copy_say_where_it_is(self):
        fallback_brief.build(self.repo, DAY, "signed out")
        (self.out / "agent-error.txt").write_text("agent: claude\nexit: 1\nFailed to authenticate: OAuth session expired\n")
        g = notify.gist(self.repo, DAY)
        text = notify.render_text(g)
        self.assertTrue(text.startswith("WRITTEN WITHOUT YOUR AGENT: claude stopped"), text[:120])
        self.assertIn(f"Everything is saved in {g['saved']}", text)
        self.assertIn("index.html", text)
        self.assertIn("Written without your agent.", notify.render_html(g))
        saved = notify.save_local(self.repo, DAY, g, notify.subject(self.repo, DAY, g["headline"]))
        self.assertEqual(saved, self.out / "gist.html")
        self.assertIn("Written without your agent.", saved.read_text())
        self.assertTrue((self.out / "gist.txt").read_text().startswith("Build Your Product in Public · shop"))
        index = (self.out.parent / "index.html").read_text()
        self.assertIn(f'href="{DAY}/gist.html"', index)


class NightlyEndToEnd(unittest.TestCase):
    """The real nightly.sh with a fake agent, no network, no email."""

    def run_nightly(self, agent, extra_env=None):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        repo = tmp / "shop"
        repo.mkdir()
        env_git = {**os.environ, "GIT_AUTHOR_NAME": "Me", "GIT_AUTHOR_EMAIL": "m@x", "GIT_COMMITTER_NAME": "Me",
                   "GIT_COMMITTER_EMAIL": "m@x"}
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.name", "Me"], check=True)
        (repo / "retry.py").write_text("def retry(): pass\n")
        subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-qm", "Retry failed Stripe webhooks"], check=True, env=env_git)
        (repo / ".buildinpublic").mkdir()
        (repo / ".buildinpublic" / "config.json").write_text('{"agent": "claude", "platforms": ["x", "linkedin"]}')
        skill = tmp / "skill"
        shutil.copytree(SKILL, skill)
        (skill / "scripts" / "trends.py").write_text(
            "import sys,pathlib\na=sys.argv\nd=a[a.index('--date')+1]\n"
            "p=pathlib.Path('.buildinpublic/daily')/d\np.mkdir(parents=True,exist_ok=True)\n"
            f"(p/'trends.md').write_text({TRENDS!r})\n")
        bin_ = tmp / "bin"
        bin_.mkdir()
        for name, body in (("claude", agent), ("osascript", "exit 0"), ("notify-send", "exit 0")):
            f = bin_ / name
            f.write_text("#!/bin/sh\n" + body + "\n")
            f.chmod(0o755)
        env = {**os.environ, "PATH": f"{bin_}{os.pathsep}{os.environ['PATH']}", "HOME": str(tmp / "home"),
               "BIP_SECRET_STORE": "file", "BIP_CONFIG_DIR": str(tmp / "conf"), **(extra_env or {})}
        start = time.time()
        subprocess.run(["sh", str(skill / "scripts" / "nightly.sh"), str(repo), str(DAY)], env=env,
                       capture_output=True, text=True, timeout=180)
        return repo / ".buildinpublic" / "daily" / str(DAY), time.time() - start

    def test_signed_out_agent_still_gives_posts(self):
        out, _ = self.run_nightly('echo "Failed to authenticate: OAuth session expired" >&2; exit 1')
        brief = (out / "brief.md").read_text()
        self.assertTrue(brief.startswith(fallback_brief.MARK))
        self.assertIn("Retry failed Stripe webhooks", brief)
        self.assertTrue((out / "gist.html").exists())
        self.assertIn("WRITTEN WITHOUT YOUR AGENT", (out / "gist.txt").read_text())
        self.assertTrue((out.parent / "index.html").exists())

    def test_stuck_agent_is_stopped(self):
        out, took = self.run_nightly("sleep 120", {"BIP_AGENT_TIMEOUT_SECONDS": "3"})
        self.assertLess(took, 60)
        self.assertIn("Stopped after", (out / "nightly.log").read_text())
        self.assertTrue((out / "brief.md").read_text().startswith(fallback_brief.MARK))

    def test_a_working_agent_writes_the_brief(self):
        good = ('d=$(ls -d .buildinpublic/daily/*/ | tail -1); grep -q "written without" "$d/brief.md" 2>/dev/null && exit 3; '
                'printf "# Daily Gist\\n\\n## Today in one line\\nAgent wrote this.\\n" > "$d/brief.md"')
        out, _ = self.run_nightly(good)
        self.assertIn("Agent wrote this.", (out / "brief.md").read_text())
        self.assertNotIn("WRITTEN WITHOUT", (out / "gist.txt").read_text())


if __name__ == "__main__":
    unittest.main()
