"""`buildinpublic agent-auth` (the CLI, on every OS): the saved token reaches scheduled agent runs.
On Windows it also saves, reads and removes a real token in the DPAPI store."""
import datetime as dt
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

TOKEN = "sk-ant-oat01-" + "T" * 40
KEY = "sk-ant-api03-" + "K" * 40


class StopAfterAgent(Exception):
    pass


def stop():
    raise StopAfterAgent


class CliAuth(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.patch = mock.patch.dict(os.environ, {"BUILDINPUBLIC_HOME": str(self.tmp / "bip"),
                                                  "BIP_USER_HOME": str(self.tmp)})
        self.patch.start()
        from buildinpublic import agent_auth as cli_auth, notify
        self.auth = cli_auth
        self.secrets = {}
        self.mocks = [mock.patch.object(notify, "set_secret", lambda n, v: self.secrets.__setitem__(n, v) or "test store"),
                      mock.patch.object(notify, "get_secret", lambda n: self.secrets.get(n))]
        for m in self.mocks:
            m.start()

    def tearDown(self):
        for m in self.mocks:
            m.stop()
        self.patch.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_set_and_agent_env(self):
        self.assertNotIn("CLAUDE_CODE_OAUTH_TOKEN", self.auth.agent_env({}))
        self.assertEqual(self.auth.set_token("claude-token", TOKEN), "test store")
        self.assertEqual(self.auth.agent_env({})["CLAUDE_CODE_OAUTH_TOKEN"], TOKEN)
        self.assertIn("lasts until about", " ".join(self.auth.status()))
        with self.assertRaises(SystemExit):
            self.auth.set_token("claude-token", KEY)

    def test_drafts_get_the_token(self):
        self.auth.set_token("claude-token", TOKEN)
        from buildinpublic import brief
        seen = {}
        with mock.patch.object(brief, "_agent_cmd", return_value=["claude", "-p", "{prompt}"]), \
             mock.patch.object(brief.subprocess, "run", side_effect=lambda *a, **k: seen.update(k.get("env") or {}) or stop()):
            with self.assertRaises(StopAfterAgent):  # only the agent call matters here
                brief.write_drafts(dt.date.today(), [{"dir": str(self.tmp), "project_name": "app"}], {})
        self.assertEqual(seen.get("CLAUDE_CODE_OAUTH_TOKEN"), TOKEN)



@unittest.skipUnless(sys.platform == "win32", "Windows secret store")
class WindowsStore(unittest.TestCase):
    def test_real_round_trip(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        with mock.patch.dict(os.environ, {"BUILDINPUBLIC_HOME": str(tmp / "bip"), "BIP_USER_HOME": str(tmp)}):
            from buildinpublic import agent_auth, notify
            name = "claude-token"
            # a throwaway service name, so a developer's real saved token is never touched
            with mock.patch.object(agent_auth, "KINDS", {name: agent_auth.KINDS[name]}), \
                 mock.patch.object(notify, "SERVICE", "build-in-public-test"):
                where = agent_auth.set_token(name, TOKEN)
                self.addCleanup(agent_auth.remove)
                self.assertTrue(where)
                self.assertEqual(agent_auth.agent_env({})["CLAUDE_CODE_OAUTH_TOKEN"], TOKEN)
                agent_auth.remove()
                self.assertNotIn("CLAUDE_CODE_OAUTH_TOKEN", agent_auth.agent_env({}))


if __name__ == "__main__":
    unittest.main()
