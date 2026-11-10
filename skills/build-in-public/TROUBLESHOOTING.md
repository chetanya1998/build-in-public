# Troubleshooting: points of failure

The daily gist is a pipeline. Each step can fail on its own, and a later step can still run and look fine, so "I didn't get the email" can have several causes. This guide lists every point of failure, how to tell which one you hit, and how to fix it. It's written for you and for your agent: an agent asked "why didn't I get my gist?" should follow it from the top.

## Start here

1. Run the doctor. It's read-only and makes no network calls:
   ```sh
   python3 ~/.claude/skills/build-in-public/scripts/doctor.py --repo /path/to/your/project
   ```
   Anything marked ✗ is broken. `!` is a warning. The last section shows the most recent nightly run and its last error line.
2. Open the latest day's folder, `.buildinpublic/daily/<YYYY-MM-DD>/`. **The files that exist tell you where the run stopped:**

   | Files in the day's folder | The run stopped at | Read |
   |---|---|---|
   | No folder for that day | The schedule never fired | [3. Schedule](#3-schedule) |
   | `nightly.log` only | Collecting sessions | [4. Collect](#4-collect-sessions-git-log-captures) |
   | `digest.md`, `trends.md`, no `brief.md` | The agent writing the brief | [5. Brief](#5-the-agent-writes-the-brief) |
   | `brief.md`, but no email arrived | Sending the gist | [7. Email](#7-email) |
   | `brief-check.json` with errors | The link and format check | [6. Brief check](#6-brief-check) |

3. Read the end of that day's `nightly.log`. Every step appends its output there, including Python tracebacks. The last line of a traceback is usually enough to match a row below.

You can rerun one day at any time, from the project folder:

```sh
sh ~/.claude/skills/build-in-public/scripts/nightly.sh "$PWD" 2026-11-10            # the whole pipeline
python3 ~/.claude/skills/build-in-public/scripts/notify.py --date 2026-11-10        # only resend that day's gist
```

## The pipeline

```
schedule (launchd / cron / Task Scheduler)
  └─ nightly.sh
       1. collect.py      sessions + git + log + approved captures  -> digest.md
       2. trends.py       Hacker News, Reddit, GitHub, dev.to        -> trends.md
       3. agent, headless claude -p / codex exec                     -> brief.md
       4. brief_check.py  sections, fields, every link loads         -> brief-check.json
       5. notify.py       desktop notification + email               -> your inbox
```

---

## 1. Install

| Symptom | Cause | Fix |
|---|---|---|
| The agent doesn't react to "set up build in public" | The skill isn't installed, or the agent was already running when you installed it | `sh install.sh` from the clone, then restart the agent. Agents load skills when a session starts. |
| doctor: `Installed: running from …, not found in any agent's skills folder` | You ran the scripts from the clone only | `sh install.sh` |
| Changes you pulled don't show up | The agents use the copy in `~/.claude/skills` etc., not the clone | After `git pull`, run `sh install.sh` again |
| `zsh: command not found: pip` | macOS ships `pip3`, not `pip` | `python3 -m pip install --user …`, and run tools as `python3 -m playwright …` |

## 2. Project setup and logging

| Symptom | Cause | Fix |
|---|---|---|
| doctor ✗ `.buildinpublic/: missing` | Setup hasn't run in **this** folder. Running the doctor from a parent folder also shows this. | Open the project itself in your agent and say "set up build in public", or pass `--repo` to the doctor |
| doctor ✗ `config.json: invalid JSON` | A hand edit broke the file | Fix the JSON, or delete it and rerun setup |
| doctor `Trend topics: still template placeholders` | `topics` in `config.json` was never filled | Set 2 to 5 real phrases |
| The log stays empty though you code every day | The logging rule isn't in a file your agent reads. **Claude Code reads `CLAUDE.md`, not `AGENTS.md`.** | Make sure `CLAUDE.md` exists and contains the rule, or a line `@AGENTS.md` that imports it |
| Drafts sound generic | `Voice` is empty in `narrative.md` (doctor warns) | Fill in Voice, Origin and Off-limits |

## 3. Schedule

| Symptom | Cause | Fix |
|---|---|---|
| No folder at all for a day | The Mac was **off** at gist time. launchd runs a missed job when a sleeping Mac wakes, but not if it was shut down. | Rerun that day with `nightly.sh "$PWD" <date>` |
| `nightly.log` stops after the digest with no error | The Mac went to sleep in the middle of the run | Rerun that day |
| doctor ✗ `Scheduled script … no longer exists` | You moved or deleted the folder the schedule points to | `sh <skill>/scripts/schedule.sh --time 19:00` from the project |
| Not sure whether it's scheduled | | macOS: `launchctl list \| grep buildinpublic`. Linux: `crontab -l`. Windows: `buildinpublic schedule status` |

The schedule records your `PATH` when you set it. If you install `claude`, `codex` or Python somewhere new afterwards, rerun `schedule.sh` so the nightly job can find them.

## 4. Collect: sessions, git, log, captures

| Symptom | Cause | Fix |
|---|---|---|
| doctor: `Claude Code: 0 session(s)` though you use it | Sessions are matched to the folder the agent was **started** in. A session started in a parent folder doesn't count. | Start your agent inside the project folder |
| doctor: `N compressed Codex sessions can't be read` | Codex saves `.jsonl.zst` files | `brew install zstd` (or `apt install zstd`) |
| A source you use shows 0 sessions | The agent changed its session format | `python3 <skill>/scripts/collect.py --inspect`, then open an issue with the output |
| doctor: `git repo: not a git repo` | The project has no `.git` | `git init`, or ignore it: commits just won't be included |

## 5. The agent writes the brief

This step runs your agent with no window and nobody at the keyboard, so anything that needs a person fails here. When it fails, you still get `digest.md` and `trends.md`, but no `brief.md`.

| Line in `nightly.log` | Cause | Fix |
|---|---|---|
| `Failed to authenticate: OAuth session expired and could not be refreshed` | The terminal `claude` sign-in expired. **Signing in to the Claude desktop app doesn't renew it**: they're separate sign-ins. | In a terminal: `claude`, then `/login`, finish in the browser, then `/exit` |
| `API Error: Unable to connect to API (ConnectionRefused)` | Offline at gist time | Rerun the day once you're online |
| `Request timed out` | The agent call took too long | Rerun the day |
| `No headless agent configured` | `agent` is `none`, or `claude` / `codex` isn't on the schedule's `PATH` | Set `"agent"` in `config.json`, then rerun `schedule.sh` |

Check this step on its own, without spending a full run:

```sh
claude -p "Reply with just OK" < /dev/null      # should print OK
```

## 6. Brief check

`brief_check.py` writes `brief-check.json` and puts any problems at the top of the email.

| Symptom | Cause | Fix |
|---|---|---|
| `errors` in `brief-check.json` | The brief is missing a required section or field | Ask your agent: "build in public brief" to rewrite it |
| `dead_links` | A link in a suggested post doesn't load | Don't use that link in the post |
| `Couldn't check (HTTP 308)` | The site redirected, so the link couldn't be confirmed | Open it yourself before posting. Usually fine. |

## 7. Email

**First, find out which method you use:** the doctor's `Email:` line says `via Apple Mail`, `via sendmail` or `via SMTP`. Settings live in `~/.config/buildinpublic/email.json`, shared by all your projects. To test the email on its own:

```sh
python3 ~/.claude/skills/build-in-public/scripts/notify.py --test --no-desktop
```

### Apple Mail (macOS default)

| Symptom | Cause | Fix |
|---|---|---|
| The log says `Gist emailed … via mail-app`, but nothing arrives | That line only means **Mail accepted the message**, not that Mail sent it. It's usually stuck in Mail's Outbox because the account's sign-in expired. | Open Mail and check the Outbox and the warning next to your account. Also search Spam for "Build In Public". To get errors in the log instead, switch to SMTP. |
| `Not authorised to send Apple events to Mail (-1743)` | macOS blocked the script from controlling Mail | Run `notify.py --test` once from Terminal and click Allow, or turn it on in System Settings › Privacy & Security › Automation |
| `Apple Mail couldn't send it` | Mail has no account | Add an account in Mail, or switch to SMTP |

### Gmail SMTP

`email.json`:

```json
{"to": "you@gmail.com", "method": "smtp", "smtp_host": "smtp.gmail.com", "smtp_port": 587,
 "smtp_user": "you@gmail.com", "security": "starttls"}
```

| Symptom | Cause | Fix |
|---|---|---|
| `SMTPServerDisconnected: Connection unexpectedly closed` at `s.login` | **Gmail rejected the password.** It wants an app password: exactly 16 lowercase letters, often shown as `abcd efgh ijkl mnop`. Your normal Gmail password, or anything else, gets this. | Create one at [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords) (needs 2-Step Verification), then save it (below) |
| `The smtp method needs a password` | No Keychain entry for that exact `smtp_user` | Save it (below) |
| `socket.gaierror: nodename nor servname provided` | Offline or DNS down at gist time | Rerun the day once you're online |

Saving the password. Use your real address after `-a`, exactly as in `smtp_user`, without `<` `>`:

```sh
security add-generic-password -U -s buildinpublic-smtp -a you@gmail.com -w
```

Easy mistakes with this command:

- **The account must match `smtp_user` exactly.** An entry saved under a placeholder such as `you@gmail.com` is never found.
- **zsh reads `<…>` as a file redirect**, so `-a <your-gmail>` fails with `no such file or directory` and saves nothing.
- **Nothing is saved until you retype the password** at the second prompt and press Return.
- **`-U` overwrites** an existing entry. Without it, a second save fails.

Agents: **never print, read out or ask for the password.** To check it without seeing it, print only its shape:

```sh
python3 -c "import subprocess as s; p=s.run(['security','find-generic-password','-s','buildinpublic-smtp','-a','you@gmail.com','-w'],capture_output=True,text=True).stdout.strip().replace(' ',''); print(len(p), p.isalpha() and p.islower())"
```

`16 True` is what a Gmail app password looks like. Anything else will be rejected.

### sendmail (Linux) and Windows

| Symptom | Cause | Fix |
|---|---|---|
| `No sendmail found` | No mail transfer agent installed | Install and configure one, such as msmtp, or remove `email.json` |
| `sendmail failed: …` | The MTA is misconfigured | Test it with `echo test \| sendmail you@example.com` |
| Windows: no email | The CLI's Gmail app password isn't in Credential Manager | `buildinpublic setup`, then `buildinpublic doctor --test` |

## 8. Desktop notification

| Symptom | Cause | Fix |
|---|---|---|
| No notification | `"notify": false` in `config.json`, or Focus / Do Not Disturb was on | Check the config and your Focus settings. The gist is still in `brief.md`. |

## 9. Sharing posts with commits

| Symptom | Cause | Fix |
|---|---|---|
| doctor ✗ `Share with commits: … the pre-commit hook is missing` | `"share": "commits"` is set, but the hook isn't installed | `sh <skill>/scripts/init.sh --share` |
| doctor ✗ `the hook points to …, which no longer exists` | The skill folder moved | Rerun `init.sh --share` |
| A post isn't in the commit | Only posts with `status: approved` are shared, never suggestions | Approve it, or set the status yourself |
| Skip sharing for one commit | | `BIP_SKIP_SHARE=1 git commit …` |

If the repo is public, anyone can read shared posts and see their images.

## 10. Captures

| Symptom | Cause | Fix |
|---|---|---|
| `Playwright not installed` | Images need Playwright | `python3 -m pip install --user playwright`, then `python3 -m playwright install chromium` |
| `playwright install chromium` prints nothing | Chromium is already installed | Nothing to do. `python3 -m playwright install --dry-run chromium` shows where it is. |
| `Couldn't load http://localhost:…` | Your app isn't running, or `app_url` is wrong | Start the dev server, or fix `app_url` in `config.json` |
| `No URL` | No `--url` and no `app_url` | Pass `--url`, or set `app_url` |

---

Still stuck? Open an [issue](https://github.com/chetanya1998/build-in-public/issues) with the doctor's output and the end of the day's `nightly.log`. Both are redacted, but read them once before pasting.
