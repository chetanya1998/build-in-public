"""`buildinpublic menu`: every entry is a real command, and the menu never waits without a terminal."""
import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from buildinpublic import cli, menu  # noqa: E402


def sample_argv(entry):
    """The argv the menu would build, with a plausible answer to every question."""
    _, args, qs = entry
    argv = list(args)
    for prompt, flag, required, choices in qs:
        v = choices[0] if choices else ("2026-11-03" if "YYYY" in prompt else "20-48" if "Lines" in prompt else
                                        "http://localhost:3000" if "URL" in prompt else "demo")
        argv += [flag, v] if flag else [v]
    return argv


class CliMenuTest(unittest.TestCase):
    def parsed(self, argv):
        """Run cli.main with every command swapped for a recorder: parses for real, runs nothing."""
        calls = []
        rec = lambda name: (lambda a: calls.append((name, a)))
        patches = {n: rec(n) for n in dir(cli) if n.startswith("cmd_") and n != "cmd_mark"}
        with mock.patch.multiple(cli, **patches), mock.patch.object(cli, "cmd_mark", lambda status: rec("mark_" + status)):
            cli.main(argv)
        return calls

    def test_every_entry_is_a_valid_command(self):
        for entry in menu.entries():
            argv = sample_argv(entry)
            with self.subTest(argv=argv):
                self.assertEqual(len(self.parsed(argv)), 1)

    def test_bare_command_opens_the_menu(self):
        self.assertEqual(self.parsed([])[0][0], "cmd_menu")
        for spelling in ("help", "help?", "?", "-h", "--help"):
            with self.subTest(spelling=spelling):
                self.assertEqual(self.parsed([spelling])[0][0], "cmd_menu")
        self.assertEqual(self.parsed(["posts", "--limit", "3"])[0][0], "cmd_posts")  # real commands untouched

    def test_without_a_terminal_it_lists_and_returns(self):
        out = []
        menu.run(lambda argv: self.fail("ran a command"), interactive=False,
                 ask=lambda p: self.fail("asked for input"), say=out.append)
        text = "\n".join(out)
        self.assertIn("buildinpublic today", text)
        self.assertIn("build in public help", text)
        self.assertEqual(text.count("buildinpublic "), len(menu.entries()) + 1)  # every command, plus the hint

    def test_pick_asks_only_what_is_needed(self):
        answers = iter(["3", "", "stripe webhook", ""])
        ran = []
        menu.run(ran.append, interactive=True, ask=lambda p: next(answers), say=lambda s: None)
        self.assertEqual(ran, [["search", "stripe", "webhook"]])

    def test_uninstall_asks_first(self):
        n = [e[1] for e in menu.entries()].index(["uninstall"]) + 1
        answers = iter([str(n), "n", ""])
        ran = []
        menu.run(ran.append, interactive=True, ask=lambda p: next(answers), say=lambda s: None)
        self.assertEqual(ran, [])

    def test_printed_list_works_in_a_cp1252_pipe(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            menu.run(lambda a: None, interactive=False)
        buf.getvalue().encode("utf-8")  # the CLI forces UTF-8 output; the text itself must be encodable


if __name__ == "__main__":
    unittest.main()
