---
name: build-in-public
description: Personal build-in-public content strategist that lives in the user's project repo. Logs what the user builds during Claude Code, Codex and Antigravity sessions, asks before capturing terminal or browser output, searches the internet for trends near the project and the day's work, sends a scheduled daily gist (notification, plus email if the user gives an address) with a list of suggested posts, drafts the one the user picks, and can add approved posts and images to the user's commits so they're on GitHub. Never posts. With the optional `buildinpublic` CLI it also journals every session across all projects (macOS, Windows, Linux) and reminds the user when they haven't posted. Use for "build in public", "log this", "capture this", "daily gist", "build in public brief", "review my posts", "my posts", "today's posts", "show post 2", "write post 2", "what should I post", "build in public help", "help?", weekly recap, "what did I do today/this week", "across my projects", and Build Your Product in Public reminders.
---

# Build Your Product in Public

Builders ship something real almost every day, then post nothing. They forget what they did, or they can't see why it would interest anyone. Build Your Product in Public is the builder's personal content strategist, living in their own project:

1. **During the session** it logs what was built, and asks before capturing a terminal output or a browser screen worth showing.
2. **At the time the user chose** it reads the day's agent sessions and git history, searches the internet for the trends nearest to the project and that day's work, and sends a **gist** (a desktop notification, plus an email if they gave an address) with a list of suggested posts.
3. **When the user picks one** it writes the post in their voice, with an anecdote from the day, a trend it rides and the approved capture to attach. The user reviews it, approves it and posts it themselves.
4. **If they turned sharing on**, each commit also carries their approved posts and images, so after a push they can open them on GitHub, on any device, and copy them.

Everything lives in the user's repo, in `.buildinpublic/`:

```
.buildinpublic/
  narrative.md          # product, audience, problem, voice, off-limits, story so far
  config.json           # topics, platforms, gist time, agent, app URL, capture, notify, email
  log/YYYY-MM-DD.md     # entries agents write during the day
  commits.log           # raw commit lines from the optional git hook
  daily/YYYY-MM-DD/
    digest.md           # sessions + git + log + captures, redacted (scripts/collect.py)
    trends.md           # discussions near today's work, the project and its stack (scripts/trends.py)
    captures/           # approved terminal and browser captures + captures.json (scripts/capture.py)
    brief.md            # the daily gist: shipped, story, trends, suggested posts
  posts/                # drafts the user chose, with status suggested | approved | posted
    README.md           # approved posts with their images, for GitHub (scripts/share.py)
    images/             # the capture images those posts attach
  assets/               # anything else the user saved for posts
```

Templates are in `templates/` and scripts in `scripts/`, next to this file (`<skill-dir>`). The scripts need only Python 3.9+. Captured images need Playwright (`pip install playwright && playwright install chromium`).

## Hard rules

- **Never post, publish or send anything on the user's behalf** except the gist email to their own address. Sharing posts with commits only puts files in their repo; it never posts.
- **Never capture without a yes.** Ask first, every time. Run `capture.py` with `--approved` only after the user said yes in chat.
- **Only approved captures go into posts.** Screenshots agents took on their own are candidates until the user approves them.
- **Never ask for, read out or store a password.** Email needs only the user's address.
- Leave out secrets, customer details and anything under Off-limits in `narrative.md`.

**Help.** When the user says "build in public help", "help?", "help", "menu", "what can you do" or "what are the commands", show one numbered list and ask which one to do, then do it:
1. What they can say to you: set up build in public, log this, capture this, build in public brief, my posts, today's posts, show post 2, review my posts, write post 2 for LinkedIn, I posted it, weekly recap.
2. If `buildinpublic --version` works, the CLI commands too (run `buildinpublic menu`, which prints them all when it isn't in a terminal), grouped as journal, posts and reminders, screenshots, projects, setup.
Keep each line to the command and what it's for. Point terminal users to `python3 <skill-dir>/scripts/menu.py` and `buildinpublic menu`, which list everything and run the one they pick.

Choose the mode from what the user says. At the end of a task, use **Log**. When something worth showing just happened, use **Capture**. When the scheduled run fires, or the user asks for the brief, use **Daily gist**. When they want to see or choose posts, use **Review and choose**.

---

## Mode 1: Setup (once per project)

Use this when the user says "set up build in public", or before any other mode if `.buildinpublic/` doesn't exist.

1. Run `sh <skill-dir>/scripts/init.sh` from the project root. It can be rerun later with `--hook` (step 5) or `--share` (step 6).
2. Fill `narrative.md` from what the README and code already say, and ask only for the rest:
   - What are you building, in one sentence? Who is it for, and what pain do they have today?
   - Why you? Where are you now (idea, prototype, beta, paying users), and what's the next milestone?
   - Which platforms (X, LinkedIn, Threads, Reddit, dev.to, short video) and which voice?
   - Anything that must never be shared (client names, revenue, internal URLs)?
3. Fill `config.json`:
   - `topics`: 2 to 5 phrases for the problem space and the audience's pain. `trends.py` also searches the project's stack (from `package.json`, `requirements.txt` and similar) and each day's work on its own, so don't list frameworks here.
   - `brief_time`: **ask when they want the daily gist** (default `00:00`, many prefer `19:00` or `08:00`).
   - `agent` (`claude`, `codex` or `none`) or `agent_command`, for writing the brief headlessly.
   - `app_url`: their local dev server or staging URL, for browser captures.
   - `capture`: `ask` (default) or `off`.
4. **Email (optional).** Ask: "Want the daily gist emailed too? If so, which address?" If they give one, write `~/.config/buildinpublic/email.json` as `{"to": "<address>"}`. That's all: no password and no server. On macOS it's sent through Apple Mail from their default account, and on Linux through the system `sendmail`. If they skip it, they still get the desktop notification. On macOS, have them run `python3 <skill-dir>/scripts/notify.py --test` once from a terminal, so macOS can ask them to allow access to Mail, and tell them Mail needs at least one account set up. (Only if they ask for SMTP instead: the extra fields are at the top of `scripts/notify.py`, and they add the password to the Keychain themselves. Never ask for it.)
5. **Make every agent log and ask before capturing.** Append `templates/agents-snippet.md` to whichever of `AGENTS.md`, `GEMINI.md` and `CLAUDE.md` exist (create `AGENTS.md` if none do). Offer the git hook that logs commits (`init.sh --hook`).
6. **Posts on GitHub (optional).** Ask: "Want your approved posts and their images added to your commits, so you can open them on GitHub after you push?" If yes, run `init.sh --share`. It installs a pre-commit hook and sets `"share": "commits"`. Only posts the user approved are added, never suggestions. **If the repo is public, say plainly that anyone will be able to read those posts and see their images**, and check that this is what they want.
7. **Schedule the gist:** `sh <skill-dir>/scripts/schedule.sh --time <brief_time>`. It uses launchd on macOS (runs on wake if the Mac was asleep) or cron on Linux. `--remove` undoes it.
8. Ask whether the rest of `.buildinpublic/` should be committed. The default is to ignore `daily/` and `assets/`, and also `posts/` unless sharing is on.
9. Finish with `python3 <skill-dir>/scripts/doctor.py` and fix anything marked ✗.

Be upfront: it doesn't watch the screen or keystrokes. It reads the session files the agents already save, filtered to this repo, plus git history and whatever the user approves. Everything is local except the trend searches (topic keywords only), the optional gist email to the user, and posts they approved if they turned sharing on.

---

## Mode 2: Log (during the session)

At the end of any meaningful task, or when the user says "log this":

1. Collect the facts: what was asked, what was built, what failed on the way, which decision was made and why. Check `git log --since=midnight --stat` and new lines in `.buildinpublic/commits.log` for work done outside the session.
2. Append one entry per unit of work to `.buildinpublic/log/<today>.md` using `templates/entry.md`. Set `agent:` to yourself (claude, codex, antigravity) or `manual`.
3. Tag what's story-worthy: `#war-story` (a long bug hunt and the fix), `#metric` (a number moved), `#decision` (a real tradeoff), `#visual` (something to show), `#lesson`, `#milestone` (a first), `#pivot`.
4. **Keep the anecdote.** Write down the specific moment: the exact error, the wrong guess, the "oh, it's the timezone" line. Posts are built from these.
5. Keep it short and factual, skip trivial changes, and scrub secrets and Off-limits terms.

Mention it in one line ("Logged to today's Build Your Product in Public log.").

---

## Mode 3: Capture (with the user's approval)

When something worth showing just happened (tests going green after a fight, a benchmark result, a deploy, a migration's output, a new screen in a Playwright or browser test), or the user says "capture this":

1. **Ask first**, in one line, with the choices:
   > Capture this for today's story? 1) terminal output of `npm test` 2) browser screenshot of http://localhost:3000/onboarding 3) skip
   Offer only what makes sense. Skip this if `config.json` has `"capture": "off"`, and don't ask more than a few times a day.
2. Only if they say yes, run from the project root:
   ```sh
   python3 <skill-dir>/scripts/capture.py terminal --cmd "npm test" --note "green after 2 hours" --approved
   python3 <skill-dir>/scripts/capture.py terminal --file /tmp/bench.txt --title "bench" --approved   # output you already have
   python3 <skill-dir>/scripts/capture.py browser --url http://localhost:3000/onboarding --mobile --approved
   ```
   Terminal captures keep the redacted text and render a terminal-window PNG. Browser captures take a desktop (and optionally mobile) screenshot. Without `--approved`, the script refuses when it isn't on a terminal.
3. **Screenshots your agents took** (Playwright MCP, test reports, Antigravity) are candidates. Run `capture.py candidates`, show the list, and ask which to keep. Then run `capture.py approve <ids> --approved` and `capture.py reject <ids>`.
4. Add the capture id to the matching log entry (`- **Capture:** a1b2c3`).

---

## Mode 4: Daily gist (scheduled, or "build in public brief")

The default day is today, or yesterday if it's before 4am.

1. **Gather.** If `daily/<day>/digest.md` doesn't exist, run from the project root:
   ```sh
   python3 <skill-dir>/scripts/collect.py    # sessions + git + log + approved captures -> digest.md
   python3 <skill-dir>/scripts/trends.py     # trends near today's work, the project and the stack -> trends.md
   ```
2. **Understand the day.** Read `narrative.md`, `digest.md`, `trends.md` and `captures/captures.json`. Work out what was really accomplished, the struggle, the decision and the result. Group sessions on the same feature into one story. Pick out the anecdotes: the moment that went wrong, the surprising cause, the number that moved.
3. **Search the internet for the nearest trend.** `trends.md` is only the start. Run 3 to 5 web searches built from the project's context and the day's actual work, for example "<today's problem> <stack>", "<audience> <pain> this week", "<technique used today> debate". Look at what builders on X, LinkedIn, Reddit and Hacker News and the tech news are discussing **this week**. For each story, find the closest real conversation it proves, contradicts or answers. Never force a link: a strong story with no trend beats a fake tie-in.
4. **Write `daily/<day>/brief.md` by filling in `templates/brief.md`**: the same headings, and for each suggested post a `### N. Title` heading with `**Platform:**`, `**Hook:**`, `**Angle:**`, `**Anecdote:**`, `**Trend:**`, `**Capture:**` and `**Why it works:**` lines. The gist email and `posts.py` read this format. The sections:
   - `## Today in one line`: the headline of the day.
   - `## What you shipped`: 3 to 6 bullets in plain words, each with its source (session, commit hash, log entry).
   - `## Suggested posts`: **5 to 7 numbered options** for the user to choose from. Each has a title, the platform, the angle, a hook line, the anecdote it uses, the trend it rides (with link) or "no trend", the approved capture id to attach (or "none"), and one line on why it works. Rank them, best first. Mix types: a war story, a lesson, a demo, a metric, a behind-the-scenes, a take on the trend.
   - `## The story`: one short paragraph on where today moves the product arc.
   - `## Nearest trends`: 3 to 5 items with links, each tied to a line of today's work.
   - `## Screenshots to review`: candidates from the digest that look useful, with their ids, so the user can approve them.
   - `## Capture tomorrow`: 1 or 2 moments worth capturing next time.
   Don't write full drafts here. The user chooses first.

   Before you finish, hold every post to these rules, because the user may post it as written:
   - **Only links you opened.** Fetch each link and keep it only if it loads; never guess or rebuild a URL. Use the article's own title as the link text.
   - **Numbers from their source.** Quote a statistic only from the original source (the survey or report itself, not a blog that repeats it), name that source, and word it the same way everywhere in the brief.
   - **An anecdote is a moment**, not a summary: the error, the wrong guess, the number that moved. On a quiet day, say so instead of inventing one.
   - **Facts about the product match the code**, e.g. which agents are supported.
   Then run `python3 <skill-dir>/scripts/brief_check.py --repo . --date <day>` and fix every ✗ (missing sections, dead links) before you stop. Warnings (a site that blocks checks) are fine to leave.
5. Append any milestone to `## Arc so far` in `narrative.md`.
6. In a scheduled run, write the files and stop. `nightly.sh` then sends the gist (a notification, plus an email if set up). If the user is present, show the headline and the list of suggested posts, and ask which one to write.

If the digest shows nothing, write a short brief that says it was a quiet day, with 2 suggested posts based on the narrative (what's next, behind the scenes).

---

## Mode 5: Review and choose (the user picks what to post)

Use this when the user says "review my posts", "write post 2", "what should I post" or replies to the gist.

**Listing posts.** For "my posts", "all my posts", "today's posts" or "show post 2", run from the project root and show the result:
- all saved posts with their status: `python3 <skill-dir>/scripts/posts.py`
- today's suggestions plus anything saved today: `python3 <skill-dir>/scripts/posts.py --today`
- one post as clean text to copy: `python3 <skill-dir>/scripts/posts.py show 2` (a suggestion number) or `show <id>` (a saved post)
- with the CLI, its drafts across all projects: `buildinpublic posts` (`--today`, or `buildinpublic posts <id>`)

1. Read the latest `brief.md` (and earlier days' if the user asks), and show the suggested posts as a numbered list, one line each. Mark the ones already drafted or posted (from `posts/`).
2. The user picks one or more. Ask which platform if it isn't clear.
3. Write the draft for each platform, in their voice from `narrative.md`:
   - **X / Threads:** a hook that stands on its own, then 3 to 7 short posts with one idea each, ending with a question or what's next. Also a single post under 280 characters.
   - **LinkedIn:** two strong opening lines (above "see more"), short paragraphs covering the problem, what was built and the lesson, and a soft invitation to follow along.
   - **Reddit / Indie Hackers:** plain and useful, no marketing tone, ending with a question for the community.
   - **dev.to / blog:** a title, the problem, the approach, a snippet or diagram, the result and what's next.
   - **Short video:** a 30 to 45 second script with a hook, a demo and one takeaway.
   Rules for every draft: lead with the moment, not "Today I worked on...". Use the real anecdote and real numbers. One idea per post. Name the capture file to attach (from `captures/`). No hype words, nothing that isn't in the log or sessions, nothing from Off-limits.
4. Show the draft and revise it until the user is happy. Then save it to `.buildinpublic/posts/<date>-<platform>-<slug>.md` in this format (`share.py` reads it):
   ```
   ---
   status: approved
   platform: x
   date: <date>
   attach: daily/<date>/captures/<file>.png
   trend: <link or none>
   ---
   # <title>

   <the post text, exactly as it should be posted>
   ```
   Use `status: suggested` for a draft they haven't approved yet.
5. If sharing is on (`"share": "commits"`), run `python3 <skill-dir>/scripts/share.py` so they can preview `posts/README.md`, and tell them the post and its image go out with their next commit. They can open it on GitHub after pushing.
6. The user copies and posts it. When they say they posted, set `status: posted`, add `link:`, and add a line to `## Arc so far` in `narrative.md`, so later posts can call back ("Two weeks ago I said X. Here's what happened.").

For a **weekly recap**, read the week's `brief.md` files and posts, and offer 3 recap angles to choose from in the same way.

### When there is no brief yet

Don't refuse. Run the Gather step of Mode 4, or rebuild the day from `git log`, ask one question ("What was the hardest part today?"), and then suggest posts.


---

## Mode 6: Across all projects (optional `buildinpublic` CLI)

Some users work on many projects, or want a record of every AI coding session without setting up each repo. The optional companion CLI keeps a **global journal** in `~/.buildinpublic/` (on Windows `%USERPROFILE%\.buildinpublic\`). It's separate from a project's `.buildinpublic/` folder, and works on macOS, Windows and Linux.

Check whether it's installed with `buildinpublic --version`. If it isn't and the user wants it, point them to the README's "Across all your projects" section. It installs with `sh install-cli.sh` on macOS or Linux, or `irm …/install.ps1 | iex` on Windows.

| The user asks | Run |
|---|---|
| "what did I do today / on Tuesday?" | `buildinpublic today` · `buildinpublic today 2026-11-03` |
| "this week", "how much time on X?" | `buildinpublic week` · `buildinpublic week --project <name>` |
| "when did I fix the webhook bug?" | `buildinpublic search stripe webhook` |
| "which projects?" | `buildinpublic projects` |
| "screenshot my app / this code" | `buildinpublic shot url <url>` · `buildinpublic shot code <file> --lines 20-48 --caption "…"` |

Read the `summary.md` files these commands point to for detail.

**New projects.** The journal finds new projects on its own. When the session-start context or the summary lists one, ask the user once: *content on* (used for posts), *journal only*, or *ignored*. Then run `buildinpublic project <name> content|journal|ignore`.

A project that's also set up with Mode 1 keeps using its own `.buildinpublic/` gist and posts. The global journal is the record across everything.

## Mode 7: Reminders (when the user hasn't posted)

The CLI tracks drafts. When nothing has been posted for `nudge_after_days` (default 2), it sends a notification and writes `~/.buildinpublic/nudge.md`.

If your session context contains a `<build-in-public>` block, or that file exists:

1. Bring it up briefly at the start, before the user's task. Ask one question at a time and keep it friendly:
   - a waiting draft: post it, edit it, or skip it?
   - the last session: turn it into a post?
   - "What are you working on right now?"
   - otherwise, a low-effort idea: a lesson, a question for their audience, or a look at their setup
2. When they answer what they're working on, run `buildinpublic nudge --reply "<their words>"` and offer to draft a "what I'm building" post. If they say not now, run `buildinpublic nudge --snooze`.
3. When they post something, run `buildinpublic posted <id>`, or `buildinpublic posted latest`. This also resets the reminder.

Don't nag: once per session at most.

**Screenshot offers.** The CLI notices localhost dev servers and agent browser tests, and asks through a native dialog. If there was no desktop to ask on, the session-start context includes a **Screenshot offer**. Ask about it, and only on a yes run `buildinpublic shot url <url>`. Then run `buildinpublic shot --clear`.

---

## Tone

Write like a builder talking to other builders: concrete, honest and a little personal. The Voice section in `narrative.md` overrides these defaults.
