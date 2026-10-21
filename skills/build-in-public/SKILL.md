---
name: build-in-public
description: Personal build-in-public content strategist. Observes the day's Claude Code, Codex and Antigravity sessions, git activity and browser-test screenshots, links them to trending conversations, and writes a daily brief with post ideas and drafts. Use for "build in public", "daily brief", "what should I post", "log this", weekly recap.
---

# Build In Public

Builders ship something real almost every day, then post nothing. They forget what they did, or they can't see why it would interest anyone. Build In Public acts as the builder's personal content strategist. It **observes** the day's agent sessions (Claude Code, Codex, Antigravity), git activity and browser-testing screenshots. It **connects** that work to what people are talking about online right now. Then it **turns it into content** that tells one consistent story about the product, starting long before any formal marketing.

Everything lives inside the project, in a `.buildinpublic/` folder, so every agent and git itself can feed the same story.

```
.buildinpublic/
  narrative.md          # product, audience, problem, arc, voice, off-limits
  config.json           # topics, platforms, brief time, agent, snapshot URLs
  log/YYYY-MM-DD.md     # entries agents write during the day
  commits.log           # raw commit lines from the optional git hook
  daily/YYYY-MM-DD/
    digest.md           # sessions + git + log, redacted (scripts/collect.py)
    trends.md           # this week's discussions per topic (scripts/trends.py)
    snapshots/          # app screenshots + agents' browser-test screenshots
    brief.md            # the daily brief: summary, ideas, drafts
  posts/                # drafts, never auto-published
  assets/               # screenshots and clips the user saved
```

Templates live next to this file in `templates/`, and helper scripts live in `scripts/`. The scripts need only Python 3 (standard library). Playwright is optional and used only for app screenshots.

There are four modes. Choose one from what the user says. If it's unclear, use **Capture** at the end of a task, **Daily brief** at the end of the day or when the scheduled run fires, and **Create** for a specific post.

---

## Mode 1: Setup (once per project)

Use this mode when the user says "set up build in public". Also run it before either of the other modes if `.buildinpublic/` doesn't exist yet.

1. Create the folder structure. You can run `scripts/init.sh` from the project root (it's in this skill's folder), or create it by hand.
2. Fill `narrative.md` from `templates/narrative.md`. Ask the user only for what the README or code doesn't already answer:
   - What are you building, in one sentence?
   - Who is it for, and what pain do they have today?
   - Why you? (the personal reason or unfair insight)
   - Where are you now (idea, prototype, beta or paying users), and what's the next milestone?
   - Which platforms (X, LinkedIn, Threads, Reddit, dev.to, short video) and which voice (casual, technical, founder story)?
   - Is there anything that must never be shared (client names, revenue, internal URLs, stack details)?
3. **Make every agent log.** Append `templates/agents-snippet.md` to whichever of `AGENTS.md` (Codex and most other agents), `GEMINI.md` (Antigravity) and `CLAUDE.md` exist. Create `AGENTS.md` if none of them do. Agents that don't have this skill installed still write log entries this way.
4. Offer the optional git hook, which captures commits even when no agent is involved. If the user accepts, copy `scripts/post-commit.sh` to `.git/hooks/post-commit` and make it executable. If a hook already exists, append to it rather than replacing it.
5. Fill `config.json` from `templates/config.json`:
   - `topics`: 3 to 6 search phrases that connect the project to wider conversations. Include the problem space, the tech and the audience's pain, for example "saas pricing", "next.js", "cloud cost". Derive them from the narrative and confirm them with the user.
   - `platforms`, `brief_time` (default `00:00`), `agent` (`claude`, `codex` or `none`), and `agent_command` for any other headless CLI.
   - `snapshot_urls`: the local dev server or staging URLs to screenshot.
6. Offer the **nightly brief**. Running `sh scripts/schedule.sh` from the project root schedules `scripts/nightly.sh` at `brief_time`, using launchd on macOS (it runs on wake if the Mac was asleep) or cron on Linux. The pipeline collects, fetches trends, takes snapshots, runs the agent headless to write `brief.md`, and sends a desktop notification. `--remove` undoes it.
7. Ask whether `.buildinpublic/` should be committed or added to `.gitignore`. The default is to ignore `daily/`, `posts/` and `assets/` and to commit the rest only if the user says so.

Be upfront about what this skill does and doesn't do. It doesn't watch the screen or keystrokes. It reads the session files Claude Code, Codex and Antigravity already save on the user's machine, filtered to this repo. It reads git history, the screenshots agents took while testing, and whatever the user tells it. Everything stays local, and secrets are redacted before anything is written.

---

## Mode 2: Capture (log the work)

Use this mode at the end of any meaningful task in the session. Also use it when the user says "log this", "add to the log" or "note what we did".

1. Collect the facts you already have:
   - **This session:** what the user asked for, what was built, what failed along the way, and which decision was made and why.
   - **Git:** run `git log --since=midnight --stat` and `git diff --stat` to catch work done outside the session.
   - **Hook output:** read the lines in `.buildinpublic/commits.log` added since the last entry.
2. Append one entry per meaningful unit of work to `.buildinpublic/log/<today>.md`, using `templates/entry.md`. Set `agent:` to whichever agent you are (claude, codex, antigravity), or to `manual`.
3. Tag anything **story-worthy** in the entry's `Tags:` line. Create mode looks for these hooks:
   - `#war-story`: a bug that took hours to find, and the one-line fix
   - `#metric`: a number that moved (speed, cost, size, users)
   - `#decision`: a choice with a real tradeoff
   - `#visual`: something that can be screenshotted or recorded
   - `#lesson`: something other builders can learn from
   - `#milestone`: a first, such as the first deploy, first user or first payment
   - `#pivot`: a change of direction, and why
4. If something visual shipped, suggest a screenshot and a filename to save it under in `assets/`.
5. Keep entries short and factual. Don't log trivial changes (typos, renames) unless the user asks.
6. **Scrub before you write.** Leave out API keys, tokens, passwords, customer names, private URLs and anything listed under Off-limits.

When you capture automatically at the end of a task, do it quietly and mention it in one line ("Logged to today's Build In Public log.").

---

## Mode 3: Daily brief (end of day, scheduled or on demand)

Use this mode when the nightly run fires, or when the user says "build in public brief", "end of day", "what did I do today" or "daily brief". The default day is today, or yesterday if it's before 4am.

1. **Gather.** If `daily/<day>/digest.md` doesn't exist yet, run these from the project root:
   ```sh
   python3 <skill-dir>/scripts/collect.py      # sessions + git + log  -> digest.md + snapshots/
   python3 <skill-dir>/scripts/trends.py       # topic discussions     -> trends.md
   python3 <skill-dir>/scripts/snapshot.py     # app screenshots       -> snapshots/  (optional)
   ```
   If a source finds nothing, check with `collect.py --inspect`, or run `scripts/doctor.py` to check the whole setup. Session file formats change between agent releases.
2. **Understand the day.** Read `narrative.md`, `digest.md`, `trends.md` and the list of `snapshots/`. Work out what was really accomplished, as opposed to just touched. Spot the struggle, the decision and the result. Group several sessions on the same feature into one story.
3. **Widen the trend scan.** If you have web search, run 2 or 3 searches on the day's actual themes, not only the configured topics. Look at what builders on X, LinkedIn and Reddit and the news are discussing this week. `trends.md` only covers HN, Reddit, GitHub and dev.to. Note any unreachable sources listed at the bottom.
4. **Connect, honestly.** For each candidate story, look for a trend it really relates to: the day's work proves a point, contradicts a popular take, solves a problem people are complaining about, or reflects a shift everyone is noticing. Don't force a link. A strong story with no trend beats a forced tie-in.
5. **Write `daily/<day>/brief.md`** with these sections:
   - **Today in one line:** the headline of the day.
   - **What you shipped:** 3 to 6 bullets in plain words, each with a source (the session, a commit hash or a log entry).
   - **The story:** one short paragraph covering where this moves the product arc and what the struggle and result were.
   - **What people are talking about:** 3 to 5 trend items with links, each tied to a line of today's work.
   - **Post ideas:** 3 to 5 ideas, ranked. Each has an angle, a hook line, a platform, the trend it rides (if any), the snapshot to attach, and why it works.
   - **Ready-to-post drafts:** full drafts for the top 1 or 2 ideas, following the Create mode rules below. Also save them to `posts/`.
   - **Capture tomorrow:** 1 or 2 things worth screenshotting or noting next time.
6. Append the day's milestone, if there was one, to `## Arc so far` in `narrative.md`.
7. Never post anything. In a scheduled (headless) run, write the files and stop. If the user is present, show a short summary and the top idea, and tell them where `brief.md` is.

If the digest shows no sessions, commits or log entries, write a one-line `brief.md` saying it was a quiet day, with one idea for a "behind the scenes" or "what's next" post based on the narrative.

---

## Mode 4: Create (turn the log into content)

Use this mode when the user says "what should I post", "make a post from today", "weekly recap", "write a thread" or "build in public update". For a weekly recap, read the `daily/*/brief.md` files for the week first.

1. Read `narrative.md` and the log entries for the window the user asked about. The default is today, and "this week" means the last 7 days. Skim `commits.log` and `git log` for the same window to fill gaps.
2. **Pick angles instead of summarizing.** A changelog isn't a post. Rank candidate stories by these factors:
   - **Tension:** a problem, struggle or surprise beats a list of features.
   - **Specificity:** a number, a screenshot or a line of code beats a claim.
   - **Relevance:** what matters to the audience in `narrative.md`.
   - **Arc:** whether the story moves the product forward.
   Show the user the top 3 to 5 angles, one line each, with the log entry each comes from. Recommend one.
3. Draft the chosen angle for the user's platforms, in their voice:
   - **X / Threads:** a hook line that stands on its own, then 3 to 7 short posts with one idea each. End with a question or what comes next. Include a single-post version under 280 characters as well.
   - **LinkedIn:** two strong opening lines (everything above "see more"), then short paragraphs covering the problem, what was built and the lesson. Close with a soft invitation to follow along.
   - **Reddit / Indie Hackers:** a plain, useful write-up with no marketing tone, ending in a question for the community.
   - **Dev blog / dev.to:** a title, then the problem, the approach, a code snippet or diagram, the result and what's next.
   - **Weekly recap:** what shipped, what you learned, the numbers, the struggles and next week's plan, under a one-line theme.
   - **Short video script:** 30 to 45 seconds with a hook, a demo of the thing and one takeaway.
4. Follow these rules in every draft:
   - Lead with the problem or the moment, not "Today I worked on...".
   - Use real numbers and real struggles. Honesty lands better than polish.
   - Keep to one idea per post.
   - Suggest which `assets/` file to attach, or what to capture.
   - Don't use hype words, fake metrics or anything that isn't in the log.
   - Don't include anything from Off-limits, any secrets or any customer details.
5. Save drafts to `.buildinpublic/posts/<date>-<platform>-<slug>.md` and show them in the reply. **Never publish or post anything on the user's behalf.** The user copies the draft and posts it.
6. Add a line to the `## Arc so far` section of `narrative.md` for any milestone or theme the content established. Future posts then stay consistent and can refer back ("Two weeks ago I said X. Here's what happened.").

### When the log is empty

Don't refuse. Rebuild the window from `git log`, ask the user one question ("What was the hardest part this week?"), then draft. Offer to run Setup so the log fills itself from now on.

---

## Content calendar (optional)

If the user asks for a plan, propose a weekly rhythm based on the log. For example: Monday, what I'm building this week. Wednesday, a struggle or lesson. Friday, a demo or screenshot. Sunday, a weekly recap. Fill each slot with a real entry, and mark the gaps where more capture is needed.

## Tone

Write like a builder talking to other builders: concrete, honest and a little personal. The Voice section in `narrative.md` overrides these defaults.
