"""Why a gist can arrive empty, and that it no longer does so silently:
commits on other branches or pushed from elsewhere, and an agent that can't write the brief."""
import datetime as dt
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent / "skills" / "build-in-public"
sys.path.insert(0, str(SKILL / "scripts"))
import collect, notify  # noqa: E402

TODAY = dt.date.today()


def git(repo, *args, who="Me", when=None):
    env = {**os.environ, "GIT_AUTHOR_NAME": who, "GIT_AUTHOR_EMAIL": f"{who}@x", "GIT_COMMITTER_NAME": who,
           "GIT_COMMITTER_EMAIL": f"{who}@x"}
    if when:
        env["GIT_AUTHOR_DATE"] = env["GIT_COMMITTER_DATE"] = when
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True, env=env).stdout


def commit(repo, msg, who="Me", when=None):
    (repo / f"{abs(hash(msg))}.txt").write_text(msg)
    git(repo, "add", ".", who=who)
    git(repo, "commit", "-qm", msg, who=who, when=when)


class Repo(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.origin = self.tmp / "origin.git"
        subprocess.run(["git", "init", "-q", "--bare", str(self.origin)], check=True)
        self.repo = self.tmp / "app"            # the folder the gist is scheduled for
        self.repo.mkdir()
        git(self.repo, "init", "-q", "-b", "main")
        git(self.repo, "config", "user.name", "Me")
        noon = f"{TODAY - dt.timedelta(days=3)}T12:00:00"
        commit(self.repo, "init", when=noon)
        git(self.repo, "remote", "add", "origin", str(self.origin))
        git(self.repo, "push", "-q", "origin", "main")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


class CommitsTest(Repo):
    def test_other_branches_and_pushes_from_elsewhere(self):
        # a branch you worked on, then switched away from
        git(self.repo, "switch", "-q", "-c", "dashboard-design")
        commit(self.repo, "Dashboard mockup")
        git(self.repo, "switch", "-q", "main")
        # a teammate (or you, in another folder) pushes to the remote
        other = self.tmp / "other"
        git(self.tmp, "clone", "-q", str(self.origin), str(other))
        git(other, "switch", "-q", "-c", "mascots")
        commit(other, "Add mascot images", who="Sarthak")
        git(other, "push", "-q", "origin", "mascots")

        before, _ = collect.git_info(self.repo, TODAY, fetch=False)
        self.assertIn("Dashboard mockup (on dashboard-design)", before)
        self.assertNotIn("mascot", before)  # not fetched yet
        after, _ = collect.git_info(self.repo, TODAY)
        self.assertIn("Add mascot images (on origin/mascots, by Sarthak)", after)
        self.assertEqual(after.count("Dashboard mockup"), 1)

    def test_each_commit_is_in_one_day(self):
        git(self.repo, "switch", "-q", "-c", "late")
        commit(self.repo, "After midnight", when=f"{TODAY}T01:30:00")
        yesterday, _ = collect.git_info(self.repo, TODAY - dt.timedelta(days=1), fetch=False)
        today, _ = collect.git_info(self.repo, TODAY, fetch=False)
        self.assertNotIn("After midnight", yesterday)
        self.assertIn("- 01:30 ", today)

    def test_current_branch_has_no_label(self):
        commit(self.repo, "On main")
        log, _ = collect.git_info(self.repo, TODAY, fetch=False)
        self.assertRegex(log, r"- \d\d:\d\d [0-9a-f]{7,} On main\n")


class AgentFailureTest(Repo):
    def nightly(self, agent_script):
        """Run the real nightly.sh with a fake agent, no network (trends stubbed) and no email."""
        skill = self.tmp / "skill"
        shutil.copytree(SKILL, skill)
        (skill / "scripts" / "trends.py").write_text("print('trends skipped in tests')\n")
        bin_ = self.tmp / "bin"
        bin_.mkdir()
        for name, body in (("claude", agent_script), ("osascript", "exit 0"), ("notify-send", "exit 0")):
            f = bin_ / name
            f.write_text("#!/bin/sh\n" + body + "\n")
            f.chmod(f.stat().st_mode | stat.S_IEXEC)
        (self.repo / ".buildinpublic").mkdir()
        (self.repo / ".buildinpublic" / "config.json").write_text('{"agent": "claude"}')
        env = {**os.environ, "PATH": f"{bin_}{os.pathsep}{os.environ['PATH']}", "HOME": str(self.tmp / "home")}
        subprocess.run(["sh", str(skill / "scripts" / "nightly.sh"), str(self.repo), str(TODAY)],
                       env=env, capture_output=True, text=True, timeout=120)
        return self.repo / ".buildinpublic" / "daily" / str(TODAY)

    def test_signed_out_agent_is_explained(self):
        out = self.nightly('echo "Failed to authenticate: OAuth session expired and could not be refreshed" >&2; exit 1')
        self.assertTrue((out / "agent-error.txt").exists())
        self.assertIn("OAuth session expired", (out / "nightly.log").read_text())
        g = notify.gist(self.repo, TODAY)
        text, page = notify.render_text(g), notify.render_html(g)
        self.assertTrue(text.startswith("THE BRIEF WASN'T WRITTEN: claude stopped"), text[:200])
        self.assertIn("signed out", text)
        self.assertIn("The brief wasn't written.", page)
        self.assertIn("No posts today", notify.subject(self.repo, TODAY, g["headline"]))

    def test_out_of_credits(self):
        out = self.nightly('echo "Fable 5.1 requires usage credits. Switch to another model."; exit 1')
        g = notify.gist(self.repo, TODAY)
        self.assertIn("ran out of usage", g["problem"]["fix"])

    def test_brief_written_means_no_error(self):
        out = self.nightly('d=$(ls -d .buildinpublic/daily/*/ | tail -1); printf "# Daily Gist\\n\\n## Today in one line\\nGood day.\\n" > "$d/brief.md"')
        self.assertFalse((out / "agent-error.txt").exists())
        self.assertNotIn("problem", notify.gist(self.repo, TODAY))


if __name__ == "__main__":
    unittest.main()
