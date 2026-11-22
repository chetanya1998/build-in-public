"""A long-lived token for the nightly agent: saved once, passed to `claude`, never logged.
Skill tests use the file store in a temp folder; CLI tests mock the secret store. Nothing here
touches the real Keychain."""
import datetime as dt
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "build-in-public"
sys.path.insert(0, str(SKILL / "scripts"))
sys.path.insert(0, str(ROOT / "src"))
import agent_auth  # noqa: E402

class StopAfterAgent(Exception):
    pass


def stop():
    raise StopAfterAgent


TOKEN = "sk-ant-oat01-" + "T" * 40
KEY = "sk-ant-api03-" + "K" * 40


class SkillAuth(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.env = {"BIP_SECRET_STORE": "file", "BIP_CONFIG_DIR": str(self.tmp / "conf")}
        self.patch = mock.patch.dict(os.environ, self.env)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def cli(self, *args, stdin=""):
        return subprocess.run([sys.executable, str(SKILL / "scripts" / "agent_auth.py"), *args], input=stdin,
                              capture_output=True, text=True, env={**os.environ, **self.env})

    def test_set_status_env_remove(self):
        r = self.cli("set", stdin=TOKEN + "\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn(TOKEN, r.stdout + r.stderr)  # never echoed
        f = self.tmp / "conf" / "agent-claude-token"
        self.assertEqual(stat.S_IMODE(f.stat().st_mode), 0o600)
        self.assertIn("Claude long-lived token saved", self.cli("status").stdout)
        self.assertEqual(self.cli("env").stdout.strip(), f"export CLAUDE_CODE_OAUTH_TOKEN={TOKEN}")
        self.cli("remove")
        self.assertFalse(f.exists())
        self.assertEqual(self.cli("env").stdout.strip(), "")

    def test_rejects_the_wrong_thing(self):
        r = self.cli("set", stdin=KEY)
        self.assertEqual(r.returncode, 1)
        self.assertIn("use --kind anthropic-key", r.stderr)
        self.assertEqual(self.cli("set", stdin="$(rm -rf ~); echo hi").returncode, 1)
        self.assertEqual(self.cli("set", "--kind", "anthropic-key", stdin=KEY).returncode, 0)
        self.assertIn("ANTHROPIC_API_KEY", self.cli("env").stdout)

    def test_expiry_and_doctor(self):
        self.cli("set", stdin=TOKEN)
        import doctor
        meta = agent_auth.meta_path()
        for saved, mark, words in ((dt.date.today(), "✓", "until about"),
                                   (dt.date.today() - dt.timedelta(days=350), "!", "expires in about"),
                                   (dt.date.today() - dt.timedelta(days=400), "✗", "probably expired")):
            m = json.loads(meta.read_text())
            m["saved"] = str(saved)
            meta.write_text(json.dumps(m))
            doctor.RESULTS.clear()
            doctor.check_agent_auth()
            self.assertEqual(doctor.RESULTS[0][0], mark, doctor.RESULTS)
            self.assertIn(words, doctor.RESULTS[0][2])
        self.cli("remove")
        doctor.RESULTS.clear()
        doctor.check_agent_auth()
        self.assertEqual(doctor.RESULTS[0][0], "!")
        self.assertIn("claude setup-token", doctor.RESULTS[0][2])


class NightlyUsesToken(unittest.TestCase):
    """The real nightly.sh, with a fake `claude` that only writes a brief when it gets the token."""

    def test_token_reaches_the_agent_but_not_the_log(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        repo = tmp / "app"
        repo.mkdir()
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        (repo / ".buildinpublic").mkdir()
        (repo / ".buildinpublic" / "config.json").write_text('{"agent": "claude"}')
        skill = tmp / "skill"
        shutil.copytree(SKILL, skill)
        (skill / "scripts" / "trends.py").write_text("print('trends skipped in tests')\n")
        bin_ = tmp / "bin"
        bin_.mkdir()
        fake = ('if [ "$CLAUDE_CODE_OAUTH_TOKEN" = "%s" ]; then d=$(ls -d .buildinpublic/daily/*/ | tail -1); '
                'printf "# Daily Gist\\n\\n## Today in one line\\nSigned in.\\n" > "$d/brief.md"; '
                'else echo "Failed to authenticate: OAuth session expired" >&2; exit 1; fi' % TOKEN)
        for name, body in (("claude", fake), ("osascript", "exit 0"), ("notify-send", "exit 0")):
            f = bin_ / name
            f.write_text("#!/bin/sh\n" + body + "\n")
            f.chmod(0o755)
        env = {**os.environ, "PATH": f"{bin_}{os.pathsep}{os.environ['PATH']}", "HOME": str(tmp / "home"),
               "BIP_SECRET_STORE": "file", "BIP_CONFIG_DIR": str(tmp / "conf")}
        day = str(dt.date.today())

        def nightly():
            subprocess.run(["sh", str(skill / "scripts" / "nightly.sh"), str(repo), day], env=env,
                           capture_output=True, text=True, timeout=120)
            return repo / ".buildinpublic" / "daily" / day

        out = nightly()
        self.assertFalse((out / "brief.md").exists())          # no token: signed out, as before
        self.assertTrue((out / "agent-error.txt").exists())
        subprocess.run([sys.executable, str(skill / "scripts" / "agent_auth.py"), "set"], input=TOKEN,
                       env=env, capture_output=True, text=True, check=True)
        out = nightly()
        self.assertTrue((out / "brief.md").exists())           # with it: the brief is written
        self.assertFalse((out / "agent-error.txt").exists())
        log = (out / "nightly.log").read_text()
        self.assertIn("Using the token saved with agent_auth.py", log)
        self.assertNotIn(TOKEN, log)


if __name__ == "__main__":
    unittest.main()
