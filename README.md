# Build In Public

**Your personal build-in-public content strategist, living in your repo.**

You ship something real almost every day, then post nothing. You forget what you did, or you can't see why anyone would care. Build In Public watches the work you already do with **Claude Code, Codex and Antigravity**, plus your git history and browser-testing screenshots. It connects that work to what people are talking about online this week. Every night at 12:00 am, or whenever you ask, it hands you a brief with what you shipped, the story behind it, and ready-to-post ideas.

```
 Claude Code ─┐
 Codex ───────┤                       ┌─ trends (HN, Reddit, GitHub, dev.to + web search)
 Antigravity ─┼─► digest ─► your agent ┤
 git ─────────┤                       └─ snapshots (your app + agents' browser tests)
 screenshots ─┘                                   │
                                                  ▼
                       brief.md: shipped · story · trends · post ideas · drafts
```

It **never posts for you**. You review, edit and post.

## What it does

| Mode | Say this | What happens |
|---|---|---|
| **Setup** | "set up build in public" | Asks 5 short questions (product, audience, problem, voice, off-limits) and picks trend topics. It adds a logging rule to `AGENTS.md`, `GEMINI.md` and `CLAUDE.md`, can install a git hook, and can schedule the nightly brief. |
| **Capture** | "log this" (or automatic after a task) | Adds a short entry to today's log (what, why, how, struggle, result) and tags story-worthy moments like `#war-story`, `#metric` and `#milestone`. |
| **Daily brief** | runs at 12:00 am, or "build in public brief" | Reads the day's agent sessions, git activity and screenshots, scans trends, and writes `brief.md` with a summary, the story, related trends, ranked post ideas and 1 or 2 full drafts. |
| **Create** | "what should I post?", "weekly recap", "write a thread" | Drafts for X, Threads, LinkedIn, Reddit, dev.to or a short video, in your voice, and keeps your story arc consistent over time. |

## Install

```sh
git clone https://github.com/chetanya1998/build-in-public.git
cd build-in-public
sh install.sh              # Claude Code, Codex and Antigravity, user-wide
sh install.sh --project    # or just the current project
sh install.sh --only codex # or a single agent
```

| Agent | User install path | Project install path |
|---|---|---|
| Claude Code | `~/.claude/skills/` | `.claude/skills/` |
| Codex | `~/.agents/skills/` | `.agents/skills/` |
| Antigravity | `~/.gemini/config/skills/` | `.agents/skills/` |

The scripts need only **Python 3**. App screenshots additionally need `pip install playwright && playwright install chromium`.

## Try it first (1 minute, no setup)

```sh
sh skills/build-in-public/scripts/nightly.sh --demo --show
```

This builds a throwaway fictional project in a temp folder, with a git history and sample Claude Code, Codex and Antigravity sessions. It runs the real collector on it, then shows the two outputs:

- `digest.md`: what the skill actually pulled out of those sessions, with an email, a token and an off-limits client name redacted.
- `brief.md`: a sample brief for that same day, written by hand to show the format, with the shipped work, the story, ranked post ideas and ready-to-post drafts. Your own brief is written by your agent.

Nothing outside the temp folder is read or changed, and there are no network calls. [See the sample brief](skills/build-in-public/demo/sample-brief.md).

## Quick start

1. Open your project in your agent and say **"set up build in public"**.
2. Build as usual.
3. At 12:00 am you get a notification that your brief is ready in `.buildinpublic/daily/<date>/brief.md`. You can also ask for **"build in public brief"** at any time.

To run the pipeline by hand:

```sh
SKILL=~/.claude/skills/build-in-public
python3 $SKILL/scripts/collect.py --inspect   # what sessions were found for this repo?
sh $SKILL/scripts/nightly.sh                  # full pipeline for today
sh $SKILL/scripts/schedule.sh --time 23:30    # change the schedule (--remove to stop)
python3 $SKILL/scripts/doctor.py              # check the setup if something seems off
```

## Troubleshooting

Run `python3 $SKILL/scripts/doctor.py` from your project. It checks the tools (Python, git, zstd, Playwright, your agent's CLI), the `.buildinpublic/` setup, the logging rules, the git hook, the nightly schedule, which agent sessions it can find for the last 7 days, and errors from the last nightly run. It's read-only and makes no network calls. Paste its output into an issue if you're stuck.

## Where the data comes from

| Source | Read from | Notes |
|---|---|---|
| Claude Code | `~/.claude/projects/<repo-path>/*.jsonl` | prompts, agent replies, edited files, commands |
| Codex | `~/.codex/sessions/YYYY/MM/DD/*.jsonl[.zst]` | filtered to sessions whose `cwd` is this repo; `.zst` needs `zstd` |
| Antigravity | `~/.gemini/antigravity*/brain/*/` | task, plan and walkthrough artifacts, browser screenshots and recordings |
| git | `git log`, `git diff --stat` | plus `commits.log` from the optional hook |
| Screenshots | `.playwright-mcp/`, `test-results/`, `playwright-report/`, `screenshots/` | plus `snapshot_urls` captured with Playwright |
| Trends | Hacker News, Reddit, GitHub, dev.to (no API keys) | the agent adds its own web search for X, LinkedIn and news |

Agent session formats change between releases, so the parser is deliberately tolerant. If a source shows 0 sessions, run `doctor.py` or `collect.py --inspect` and open an issue.

## What gets created in your project

```
.buildinpublic/
  narrative.md      config.json      log/      commits.log
  daily/2026-10-22/ digest.md  trends.md  snapshots/  brief.md  nightly.log
  posts/            assets/
```

## Privacy

- **Everything runs locally.** Session files are read on your machine and never uploaded by these scripts. The only network calls are the public trend searches, which send your topic keywords.
- **Secrets are redacted** before anything is written: API keys, tokens, JWTs, private keys and emails, plus every term you list under **Off-limits** in `narrative.md`.
- **Only this repo is read.** Sessions from other projects are skipped.
- **It's gitignored by default.** Setup asks whether you want to commit any of it.
- When the brief runs through your agent, the redacted digest is sent to that agent's model, the same as any other prompt.
- **No screen or keystroke recording.**

## Contributing

PRs are welcome for new agents (Cursor, Windsurf, Gemini CLI), new trend sources and better prompts. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT © Chetanya
