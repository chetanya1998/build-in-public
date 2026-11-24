# Design: the dashboard

Status: proposal · Roadmap item: "A dashboard for all your projects"

## What it is

A local content hub for everything Build Your Product in Public has collected, across every project. You open it with one command:

```
buildinpublic dashboard
```

It shows each post from suggestion to posted, lets you edit and schedule posts, and keeps the work behind each post (sessions, research, screenshots) one click away, sorted by date and time.

It keeps the project's three promises:

- **It never posts.** "Scheduled" means *remind me at this time, with the post ready to copy*. Nothing leaves your machine.
- **It's local.** It runs on `127.0.0.1` and reads `~/.buildinpublic` and the `.buildinpublic/` folders of your registered projects. It makes no network calls of its own.
- **No new dependencies.** It uses Python's standard library (`http.server`) and one HTML page with plain JavaScript. There's no build step and no npm. It works on macOS, Windows and Linux like the rest of the CLI.

## Problems in today's data to fix first

The dashboard sits on top of the files that already exist. Three things there need fixing before a UI can be trusted:

1. **Two status lists.** The skill writes `status: suggested | approved | posted` in each post's front matter ([SKILL.md](../skills/build-in-public/SKILL.md), Mode 5). The CLI tracks `drafted | posted | skipped` in `~/.buildinpublic/posts.json` ([nudge.py](../src/buildinpublic/nudge.py)).
2. **Two places for one fact.** A post's status lives in both its front matter and `posts.json`, and nothing keeps them in step.
3. **Posts in repos are missed.** `scan_drafts()` only reads `~/.buildinpublic/posts/`. Posts the skill saves in a project's own `.buildinpublic/posts/` never reach the global list.

### The fix: front matter is the truth, `posts.json` is an index

- **One lifecycle** for every post:

  ```
  suggested ─▶ draft ─▶ approved ─▶ scheduled ─▶ posted
                  │          │            │
                  └──────────┴────────────┴──▶ skipped
  ```

  `drafted` (CLI) reads as `draft`. Old files keep working. A small `normalize_status()` maps the old words to the new ones.

- **The `.md` file is the source of truth.** Its front matter grows a few optional fields:

  ```yaml
  ---
  id: 1109-stripe-webhook-retries      # stable, set on first index
  status: scheduled
  format: x-short                      # x-short | x-long | linkedin
  project: build-in-public             # project key from projects.json
  sub: cli                             # optional sub-project key
  date: 2026-11-09                     # day of the work it's about
  session: 2026-11-09-claude-3f2a91c0  # session folder it came from
  attach: [shots/code-webhook.png]     # approved images only
  trend: https://news.ycombinator.com/item?id=…
  scheduled_for: 2026-11-10T09:30      # "post on": planned date, and the reminder time
  posted_at:                           # set when you mark it posted, editable to backfill
  link:                                # the live post, once posted
  metrics: {impressions: 4210, likes: 96, reposts: 12, replies: 18, bookmarks: 21}  # you type these in
  ---
  ```

- **Sub-projects live in `projects.json`,** under each project:

  ```json
  "invoice-ai": { "mode": "content", "color": "#ef7d32",
    "subs": [{ "key": "stripe", "name": "Stripe webhooks", "formats": ["x-short", "x-long", "linkedin"] }] }
  ```

  Removing a sub-project never deletes posts; they go back to the project.

- **`posts.json` becomes a cache** that `index.rebuild()` can recreate at any time from every post folder:
  - `~/.buildinpublic/posts/*.md`
  - `<project>/.buildinpublic/posts/*.md` for every project in `projects.json` with `mode: content`

  It holds just enough to list posts fast: path, id, status, title, platform, project, dates and mtime. `buildinpublic posts`, `posted`, `skipped` and the nudge all switch to the index, so the CLI and the dashboard always agree.

- **Edits are written where the post lives.** A post in a repo stays in that repo, so `share.py` and the pre-commit hook keep working unchanged.

## History: the change log for each post

Every save from the dashboard, and every status change from the CLI, appends one line to a history file next to the index:

```
~/.buildinpublic/history/<post-id>.jsonl
{"at":"2026-11-09T21:14:03","by":"dashboard","change":"edit","before_sha":"…","text":"<full previous body>"}
{"at":"2026-11-09T21:20:41","by":"cli","change":"status","from":"approved","to":"scheduled"}
```

- It's kept outside the repo, so drafts' history never lands in your commits.
- Each edit stores the full previous body, which is small and makes "restore this version" trivial.
- The post page shows it as a timeline with a word diff between any two versions.
- The existing retention setting prunes it along with sessions.

## Screens

A clickable mockup with sample data lives in [dashboard-mockup.html](dashboard-mockup.html). It's plain HTML and JavaScript with no outside requests, the same constraints as the real page, so it can become the starting point for `src/buildinpublic/dashboard/`. To open it with working navigation:

```
python3 -m http.server 4817 --bind 127.0.0.1 --directory design
```

Then go to http://127.0.0.1:4817/dashboard-mockup.html.

**Look and feel: calm, minimal, mostly text.**
- **Colour:** a warm paper background in light mode and near-black in dark mode, with hairline dividers instead of boxed cards. Colour appears only in small status dots and project dots; black is the only button colour.
- **Type:** page titles in a serif, everything else in one sans at 14px.
- **Navigation:** text tabs in a slim top bar.
- **Quiet by default:** row actions appear when you hover (they're always shown on touch screens), and the post editor keeps its context (session, research, hooks, images, history) in tabs below the text instead of a third column.
- **A mascot you choose** ([bip.html](bip.html)): **Bip**, a soft 3D bunny-blob, or **Sarthak's buddy**, a charcoal felt block. A switch in the top bar picks one. The mascot:
  - greets you on Today, with a mood (or pose) that matches what's waiting;
  - appears in empty states and in the confirmation toasts;
  - is your avatar in post previews.

  Bip also wears the scarf colour of the selected project. Both are drawn by the same `bip.js` as the [desk pet](pet.md), so the choice applies everywhere.

Five tabs: **Today, Posts, Calendar, Timeline, Media**. There's no Projects tab. The **project switcher** in the top bar picks a project or one of its sub-projects for every screen, creates sub-projects, and opens **Projects and settings**: each project's mode (content, journal only, ignored, the same as `buildinpublic project <name> <mode>`) and its sub-projects.

### Formats: X Short, X Long, LinkedIn

Every post has one format, and each format has its own preview, limits and measures. Hard limits are the platforms'; guidelines are labelled as guidelines in the UI.

| | X · Short | X · Long | LinkedIn |
|---|---|---|---|
| Limit | 280 characters a post; blank lines split it into a thread | 25,000 characters in one post (needs X Premium) | 3,000 characters |
| Counting | links count as 23, most emoji as 2 | same | plain characters |
| Preview | the thread, post by post, with a count on each | the post with “Show more” after 280 characters | the post with “…see more” after about 210 characters |
| Measures | longest post, thread length, hook length, hashtags (0 to 2), image (up to 4) | length, what shows before “Show more”, paragraphs, reading time, hashtags, image | length, what shows before “…see more”, hashtags (3 to 5), paragraphs, reading time, image |
| After posting | impressions, likes, reposts, replies, bookmarks | same as Short | impressions, reactions, comments, reposts |

**Engagement rate** is interactions divided by impressions. You type the numbers from X or LinkedIn analytics; the dashboard never connects to your accounts.

### Generate and edit

- **New post** (on Posts and Today) asks for:
  - a project and optional sub-project;
  - a format (only the sub-project's formats are offered);
  - what to write from (a session, or nothing);
  - an optional post-on date.

  **Generate draft** has your agent write it (`agent_command`, for example `claude -p`, or a request file it picks up at the next session). **Write it myself** opens an empty draft.
- **Adapt for…** in the editor turns any post into another format, for example an X Long post into a LinkedIn one. It's a new draft in the same sub-project and on the same date.
- An empty post (from a planned date) shows **Generate draft** above the editor.
- Nothing is ever posted for you. Copy, post it yourself, then **Mark posted**.

### Sub-projects and the trail

A sub-project groups the posts about one thread of work: a feature, a launch, a series. Each one has its own set of formats. Picking one under Posts opens its **trail**, a dated timeline of everything planned and posted:

- **Add a posting date:** pick a date and a format, and an empty draft appears on the trail, ready to generate or write.
- Posted entries show their posted date and their numbers. Planned ones show "date passed" if the date went by without a post.
- The posted date stays editable, so you can backfill posts you made by hand.

### 1. Today

What needs you: posts that are due (Copy, Mark posted), drafts to approve, approved posts to schedule, tonight's ideas (each with **Generate**), screenshots to review and what you built today. Each row shows its format.

### 2. Posts

A side list of projects and sub-projects. Above the posts, filters for **All, X · Short, X · Long, LinkedIn**, and three views:
- **Board:** one column per status; drag a card to change it.
- **List:** with each post's format, sub-project, dates, impressions and engagement.
- **Trail:** for a sub-project.

### 3. Post

The editor has the title and a quiet line of properties: status, format, project › sub-project, and post-on (or posted) date. Below the text are context tabs: Session, Research, Hooks, Images, History.

The right column holds:
- the format-aware preview;
- Copy (or Copy thread);
- **Measures** for the format;
- **How it did**, once the post is posted.

**Saving** checks the file's mtime first. If your agent changed the file since you opened it, the dashboard shows both versions instead of overwriting.

### 4. Calendar

The month, showing every post with a planned or posted date, marked by platform and time, plus sessions as dots on the days you worked. Drag a planned post to another day to move it.

### 5. Timeline

Your work log, newest first. Each session opens to its summary, files, commands, research, screenshots and the posts made from it, with **New post from this**.

### 6. Media

Every screenshot, pending ones first. **Clicking one opens the viewer:**
- **Inspect:** the image large. Click or scroll to zoom up to 4×, drag to pan, and use ← and → to move between screenshots.
- **Details:** status, project, when it was captured and by whom, its size and its session.
- **Act on it:** Approve or Discard, or attach it to a draft.
- **Every post that uses it, in full:** format, status, dates, the whole text and its numbers, with a link to the editor.

## Scheduling and reminders

The scheduler already runs background jobs on each OS (launchd, systemd/cron, Task Scheduler) ([scheduler.py](../src/buildinpublic/scheduler.py)). Add one job:

- **`remind`** runs every 15 minutes. It finds posts with `status: scheduled` and `scheduled_for <= now` that haven't been reminded yet, and sends a notification through the existing [notify.py](../src/buildinpublic/notify.py), for example "Time to post: Stripe retries (X)". Clicking it opens the dashboard on that post, with the text ready to copy.
- It doesn't change the status. You mark it posted, and add the link if you want, from the notification's page or with `buildinpublic posted <id>`.
- A reminder that's been due for over 24 hours shows in **Today** as overdue. It never sends again on its own.

## How it's built

```
src/buildinpublic/
  index.py        post index: scan folders, parse/write front matter, normalize status, history
  dashboard.py    http.server app: JSON API + static files, token + origin checks
  dashboard/      index.html, app.js, app.css  (package data, no build step)
```

### Server

- `buildinpublic dashboard [--port 0] [--no-open]` starts a `ThreadingHTTPServer` on `127.0.0.1` (a free port by default) and opens the browser at `http://127.0.0.1:<port>/#token=<random>`.
- It runs while the command runs, like a dev server. There's no background daemon. Closing the terminal stops it.

### API (JSON)

| Method | Path | Does |
|---|---|---|
| GET | `/api/summary` | the Today screen in one call |
| GET | `/api/posts?project=&status=&from=&to=` | the index |
| GET | `/api/posts/<id>` | post body, front matter, linked session, history |
| PUT | `/api/posts/<id>` | save body and fields (`If-Match: <mtime>`, 409 on conflict) |
| POST | `/api/posts/<id>/status` | change status (`{"to":"scheduled","at":"…"}`) |
| POST | `/api/posts/<id>/restore` | restore a version from history |
| GET | `/api/sessions?project=&from=&to=&q=` | timeline / search |
| GET | `/api/sessions/<project>/<dir>` | meta, summary, articles, hooks, shots |
| GET | `/api/media?project=&state=` | screenshots |
| POST | `/api/media/approve` · `/discard` | review captures |
| GET/PATCH | `/api/projects` | list projects, change mode |
| GET | `/file?path=` | serve an image or markdown from an allowed folder |

### Security

It's a local server that can read your journal and write files, so:

- **Token.** A random token on every launch. It's passed in the URL fragment, kept in `sessionStorage`, and sent as a header. Requests without it get 403.
- **DNS rebinding.** Requests are rejected unless `Host` is `127.0.0.1:<port>` or `localhost:<port>`. Writes are rejected unless `Origin` matches as well.
- **Paths.** `/file` and every write resolve the real path and refuse anything outside `app_home()` and the `.buildinpublic/` folders of registered projects. Writes only touch `posts/*.md`.
- **No outbound requests.** The page sets a `Content-Security-Policy` of `default-src 'self'`. Links in research open in your normal browser.
- **Off-limits stays off-limits.** The dashboard shows what's already redacted on disk and never reads agent session files directly.

### Writes

Every write goes to a temp file and then `os.replace` (atomic on every OS). It checks the mtime first, then appends to history. The same `index.py` functions back the CLI commands, so there's one code path.

## Build order

Each step works on its own and ships as its own PR.

1. **The index.** Add `index.py`, one status list, scanning of the repo post folders, history, and the CLI moved onto it (`posts`, `posted`, `skipped`, nudge). Tests cover old and new front matter and both folders. *This is useful even without a UI: `buildinpublic posts` would finally see every post.*
2. **Read-only dashboard.** The server, token, Today, Posts list, Post (view and copy), Timeline. It's safe to try because it can't change anything.
3. **Editing.** Saving with conflict checks, status changes, the board, history and restore.
4. **Scheduling.** The schedule field, the Calendar, the `remind` job and notifications that open the post.
5. **Media and projects.** The screenshot review grid, attaching from the grid, changing project modes.
6. **README and site.** A dashboard section, screenshots, and the roadmap item checked.

## Tests

- Unit tests for `index.py`: parsing every past front matter shape, `normalize_status`, rebuilding from both folders, history appends and restores, and mtime conflicts.
- API tests that run the server on a free port with `BUILDINPUBLIC_HOME` set to a temp folder, using the fixtures in `tests/fixtures/`. They check the token, Host/Origin rejection, path escapes (`../`, absolute paths, symlinks) and every endpoint.
- These stay standard-library only, and CI runs them on macOS, Linux and Windows like the other CLI tests.

## Open questions

1. **Should the dashboard write drafts itself?** Today only your agent writes posts. The design keeps that and hands you a prompt to copy. Calling `agent_command` (already in config) to draft in the background would be smoother, but it's a bigger trust step.
2. **Should repo-only users get it too?** This design needs the CLI. Someone who only installed the skill could run `python3 scripts/dashboard.py` against one repo. That's cheap to add once `index.py` exists.
3. **Should it record post metrics?** Adding `likes` and `replies` fields when you mark a post posted would feed the "Learns what works" roadmap item. It's worth reserving the fields now even if the UI comes later.
