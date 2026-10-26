"""Tests for share.py and the pre-commit hook: approved posts and their images go out with commits."""
import os, subprocess, sys, unittest

from test_collect import DAY, SCRIPTS, Fixture, fx

sys.path.insert(0, str(SCRIPTS))
import share  # noqa: E402

POST = """---
status: {status}
platform: {platform}
date: {date}
attach: {attach}
trend: none
{extra}---
# {title}

{body}
"""


class ShareTest(Fixture):
    def setUp(self):
        super().setUp()
        self.posts = self.repo / ".buildinpublic" / "posts"
        self.posts.mkdir(parents=True, exist_ok=True)
        caps = self.repo / ".buildinpublic" / "daily" / str(DAY) / "captures"
        caps.mkdir(parents=True)
        (caps / "3ca93f-terminal-npm-run-bench.png").write_bytes(fx.png())
        self.attach = f"daily/{DAY}/captures/3ca93f-terminal-npm-run-bench.png"

    def post(self, name, status, title, date=str(DAY), platform="x", attach="none", extra=""):
        (self.posts / name).write_text(POST.format(status=status, platform=platform, date=date, attach=attach,
                                                   title=title, body=f"Text of {title}.", extra=extra))

    def git(self, *args, env=None):
        return subprocess.run(["git", "-C", str(self.repo), *args], capture_output=True, text=True,
                              env=env or self.git_env, check=True).stdout

    @property
    def git_env(self):
        return dict(self.env, GIT_AUTHOR_NAME="T", GIT_AUTHOR_EMAIL="t@example.com",
                    GIT_COMMITTER_NAME="T", GIT_COMMITTER_EMAIL="t@example.com")

    def add_posts(self):
        self.post(f"{DAY}-x-ci-utc.md", "approved", "CI lives in UTC", attach=self.attach)
        self.post("2026-10-20-linkedin-webhooks.md", "posted", "7 of 500 payments", date="2026-10-20",
                  platform="linkedin", extra="link: https://www.linkedin.com/posts/example\n")
        self.post(f"{DAY}-x-draft.md", "suggested", "Not approved yet")

    def test_page_has_only_approved_and_posted(self):
        self.add_posts()
        r = self.run_script("share.py")
        self.assertEqual(r.returncode, 0, r.stderr)
        page = (self.posts / "README.md").read_text()
        self.assertIn("## CI lives in UTC", page)
        self.assertIn("## 7 of 500 payments", page)
        self.assertNotIn("Not approved yet", page)
        self.assertLess(page.index("CI lives in UTC"), page.index("7 of 500 payments"))  # newest first
        self.assertIn("![CI lives in UTC](images/3ca93f-terminal-npm-run-bench.png)", page)
        self.assertIn("[Posted here](https://www.linkedin.com/posts/example)", page)
        self.assertIn("LinkedIn · 2026-10-20 · ✅ posted", page)
        self.assertIn("Text of CI lives in UTC.", page)
        self.assertTrue((self.posts / "images" / "3ca93f-terminal-npm-run-bench.png").exists())

    def test_hook_adds_posts_to_code_commit(self):
        r = subprocess.run(["sh", str(SCRIPTS / "init.sh"), "--share"], cwd=self.repo, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('"share": "commits"', (self.repo / ".buildinpublic" / "config.json").read_text())
        self.add_posts()

        (self.repo / "src" / "app.ts").write_text("// new code\n")
        self.git("add", "src/app.ts")
        self.git("commit", "-q", "-m", "feat: new code")
        files = self.git("show", "--name-only", "--pretty=format:", "HEAD").split()
        self.assertIn("src/app.ts", files)
        self.assertIn(".buildinpublic/posts/README.md", files)
        self.assertIn(f".buildinpublic/posts/{DAY}-x-ci-utc.md", files)
        self.assertIn(".buildinpublic/posts/images/3ca93f-terminal-npm-run-bench.png", files)
        self.assertNotIn(f".buildinpublic/posts/{DAY}-x-draft.md", files)  # suggestions stay private

        # Nothing new to share: the next commit carries only its own code.
        (self.repo / "src" / "more.ts").write_text("// more\n")
        self.git("add", "src/more.ts")
        self.git("commit", "-q", "-m", "feat: more")
        self.assertEqual(self.git("show", "--name-only", "--pretty=format:", "HEAD").split(), ["src/more.ts"])

    def test_skip_once_and_off(self):
        subprocess.run(["sh", str(SCRIPTS / "init.sh"), "--share"], cwd=self.repo, check=True, capture_output=True)
        self.add_posts()
        (self.repo / "src" / "app.ts").write_text("// new code\n")
        self.git("add", "src/app.ts")
        self.git("commit", "-q", "-m", "skip", env=dict(self.git_env, BIP_SKIP_SHARE="1"))
        self.assertEqual(self.git("show", "--name-only", "--pretty=format:", "HEAD").split(), ["src/app.ts"])

        cfg = self.repo / ".buildinpublic" / "config.json"
        cfg.write_text(cfg.read_text().replace('"share": "commits"', '"share": "off"'))
        (self.repo / "src" / "b.ts").write_text("// b\n")
        self.git("add", "src/b.ts")
        self.git("commit", "-q", "-m", "off")
        self.assertEqual(self.git("show", "--name-only", "--pretty=format:", "HEAD").split(), ["src/b.ts"])

    def test_keeps_existing_pre_commit_hook(self):
        hook = self.repo / ".git" / "hooks" / "pre-commit"
        hook.write_text("#!/bin/sh\necho existing-check\n")
        os.chmod(hook, 0o755)
        subprocess.run(["sh", str(SCRIPTS / "init.sh"), "--share"], cwd=self.repo, check=True, capture_output=True)
        subprocess.run(["sh", str(SCRIPTS / "init.sh"), "--share"], cwd=self.repo, check=True, capture_output=True)
        text = hook.read_text()
        self.assertIn("echo existing-check", text)
        self.assertEqual(text.count('share.py" --repo'), 1)  # not added twice
        self.assertIn(str(SCRIPTS / "share.py"), text)

    def test_parse_front_matter(self):
        self.post("p.md", "approved   # comment", "Title here", attach=self.attach)
        meta, title, body = share.parse(self.posts / "p.md")
        self.assertEqual((meta["status"], meta["platform"], title, body), ("approved", "x", "Title here", "Text of Title here."))


if __name__ == "__main__":
    unittest.main()
