# Contributing to Build In Public

Thanks for helping builders share their work.

- **New platform formats** (Bluesky, YouTube, newsletters): add a bullet under Mode 3, step 3 in `skills/build-in-public/SKILL.md`.
- **New agents:** add their instruction file to Setup step 3 and their skills path to `install.sh`.
- **Story tags:** propose new tags in an issue first, so the list stays short.
- Keep the skill agent-neutral. It must work in Claude Code, Codex and Antigravity.
- Never add anything that posts automatically. Drafts only.

Open a PR with a short description and, if you can, a sample log plus the post it produced.

## Adding a session source

Collectors live in `skills/build-in-public/scripts/collect.py`. Each one returns a list of
`{"path", "cwd", "messages": [(role, text)], "tools": [(name, target)], "media": [paths]}` for
the given repo and day. Keep them read-only, tolerant of format changes, and filtered to the repo.
Test with `collect.py --inspect`.
