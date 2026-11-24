# Design: the desk pet (Bip or Sarthak's buddy)

Status: proposal · Related: [dashboard.md](dashboard.md) · Mockup: [pet-mockup.html](pet-mockup.html)

## What it is

A small, cute character that hangs out on your screen while you work on a project. It's the quickest way to use Build Your Product in Public without switching windows:

- **Glance** at it to see what's going on: what your agent is doing, whether something is worth capturing, whether you haven't posted in a while.
- **Click** it for a small ring of actions: capture, post, note, link, chat, or hold to talk.
- **Ignore** it and it stays out of the way. It never steals focus, never makes a sound, and moves aside if you need the spot it's in.

It appears when you start working on a project and goes away when you're done.

It keeps the project's promises:

- **It never posts.** "Post" asks your agent for a draft. You still approve and post it yourself.
- **It doesn't watch your screen.** It reacts to the events the tool already sees (agent sessions and tool calls, commits, dev servers, reminders), plus where your windows and cursor are. It captures or records only when you ask.
- **Nothing new leaves your machine.** It runs locally, voice notes are transcribed on your computer, and everything goes into the same `~/.buildinpublic` journal.

## Two mascots: you pick

Build in Public ships two characters. You choose one in settings (`pet.mascot: bip | buddy`), and the desk pet, the dashboard and the gist all use it. A character sheet with both is in [bip.html](bip.html).

| | **Bip** | **Sarthak's buddy** (name to be decided) |
|---|---|---|
| Look | a soft 3D jelly blob with bunny ears and little feet, peach by default | a charcoal felt block with a screen for a face and stubby arms and legs |
| Made by | code ([bip.js](bip.js)): shapes with gradient shading, a felt texture and glossy eyes | seven 3D renders by Sarthak in `Mascot/`, with web copies in `design/mascot/` |
| Moods | all 18, with ears, eyes, feet and props animating | each mood shows the closest of 7 poses; the pose breathes gently |
| Accessories | project scarf, headphones, party hat, night cap, streak flower | none yet |
| Colours | peach, mint, sky, lilac, charcoal | charcoal |

How the buddy's poses map to moods:

| Pose | Moods |
|---|---|
| notebook | idle, editing, has an idea |
| shipped | proud, party |
| excited | happy, surprised, giggle, petted |
| thinking | thinking, waiting, listening, dizzy |
| detective | reading, testing, curious |
| grumpy | confused, aimed at the bug, never at you |
| sleepy | sleepy |

**Asset note.** Five of Sarthak's seven renders (the ones exported from Gemini) have a grey checkerboard painted into the pixels instead of real transparency, plus a small watermark. The web copies in `design/mascot/` had that removed by a script, which leaves slightly soft edges on the lit top of the body. Re-exporting those five as transparent PNGs would fix it. The two "Cheerful" renders are already clean.

The rest of this document describes Bip. Everything about behaviour applies to both characters.

## Bip

**Bip** is a squishy jelly blob with bunny ears and two little feet. It has big glossy eyes, pink cheeks, long ears with pink insides, and a knitted scarf in your project's colour.

### How it's drawn

Bip looks like a small claymation toy but is drawn entirely in code, as SVG shapes:
- **body:** a rounded blob, wider at the bottom;
- **two ears:** that rotate at their base;
- **two feet;**
- **the face and props:** eyes, mouth, cheeks, a laptop, a book.

Each part is shaded like a 3D object, lit from the top left:
- a gradient from a warm highlight to a deeper shade;
- a soft shine on the forehead;
- a darker band near the bottom;
- a subtle felt texture;
- a contact shadow under the feet.

The eyes are glossy, with two catch-lights. Charcoal Bip borrows the buddy's big white eyes so it stays readable.

Because every part is a shape rather than a picture:

- **Ears can take any angle,** so they do half the acting.
- **Squash and stretch is real.** The body is redrawn wider-and-shorter or narrower-and-taller. It breathes, squashes on every step, bounces on hops and boings when surprised.
- **The feet walk.** One lifts, then the other, as Bip wanders.
- **New poses are cheap.** A mood is a list of settings (eyes, mouth, ear angles, brows, prop), not new artwork.

For the desk pet, `scripts/build_sprites.py` renders every frame Bip needs to a PNG with the same drawing code, using Playwright, which the screenshot feature already uses. That's about 150 frames at 2× size, around 8 KB each. The app only plays them back.

### Accessories

Accessories carry information as well as looking cute:

| Accessory | When | Why |
|---|---|---|
| **Scarf** in the project's colour | always (can be turned off) | Tells you at a glance which project Bip is following |
| **Headphones** | an agent session has run for 45+ minutes | Deep work: Bip keeps even quieter |
| **Party hat** | a milestone | Celebration |
| **Night cap** | sleepy, late at night | Bedtime |
| **Flower clip** on the right ear | your posting streak | Bud, then flower, then two flowers. Never taken away. |

### Moods

Bip has 18 moods in five groups. Changes are slow and small; nothing flashes to get your attention.

**What your agent is doing** (live, from Claude Code's tool hooks):

| Mood | Signal | Looks like |
|---|---|---|
| **Reading** | `Read`, `Grep`, `Glob` tool calls | eyes scanning a tiny open book, one ear tilted |
| **Editing** | `Edit`, `Write` tool calls | peeking over a laptop that types, ears back |
| **Testing** | a `Bash` call that runs tests | watching a bubbling green flask, ears perked |
| **Waiting for you** | the `Notification` hook (your agent needs an answer or permission) | holds up a "?" sign and bounces gently. No bubble, because your agent already notifies you. |
| **Done** | the `Stop` hook | a happy stretch, then idle |

**Resting:**
- **Idle:** shiny eyes, small smile, breathing and blinking.
- **Sleepy:** late at night with no session. Closed eyes, droopy ears, night cap, a slow "z".

**Reactions to your work:**

| Mood | When | Looks like |
|---|---|---|
| **Curious** | something is worth capturing | looks to the side, ear twitches, ✦ sparkle |
| **Has an idea** | a post suggestion is ready | holds a little note card |
| **Happy** | you saved something | ^ ^ eyes, hop, ear wiggle |
| **Surprised** | tests finally pass, a huge commit, you grab it | big round eyes, boings taller, "!" |
| **Proud** | you posted | content eyes, smug smile, gold star |
| **Thinking** | waiting on a draft, answering a question, transcribing | eyes up, "…" |
| **Confused** | the same test fails 3×, a capture was cancelled | one eye squinting, wavy mouth, one ear flopped, "?". **It never makes suggestions while you're stuck.** |

**Reactions to you:**
- **Giggle:** a single click. A squish, a "w" mouth, wiggling ears, and the menu opens.
- **Dizzy:** three quick clicks. Swirly eyes, little stars circling, a wobble. The menu stays shut.
- **Petted:** rub the cursor back and forth over Bip. Content eyes, droopy relaxed ears, a purr shake and floating hearts.

**Special:**
- **Party:** a milestone (see below).
- **Listening:** while you record a voice note. Ears forward, a "♪".

### Milestones

Bip celebrates with a party hat, a little dance (hops left and right) and a burst of pixel confetti:
- your **first post**;
- your **10th** post, then every 25th;
- a **7-day streak**;
- **launch day**, when you tag a `v1.0.0` release or tell Bip "we launched".

A celebration ignores the 45-minute bubble limit. It still waits out Focus mode, quiet hours and full screen, and then plays the next time you're around.

### Make it yours

Pick a colour (peach, mint, sky, lilac, charcoal), turn accessories on or off, and name it with `buildinpublic config pet.*`. Characters are just a shape recipe plus face patterns, so new ones can be contributed later.

## Where Bip sits and how it moves

### Home: on top of your active window

By default Bip sits on top of the active window's title bar, with its feet on the top edge near the right end. It's close to your work but never on top of it.
- **Switching windows:** Bip hops over to the new one.
- **Moving a window:** Bip rides along.
- **No room above the window** (maximized, or touching the menu bar): Bip sits in the screen corner above the Dock or taskbar.
- **A full-screen app is in front:** Bip hides.
- **Prefer it fixed?** Choose *Screen corner* (`pet.home: corner`).

### Drag it anywhere

Drop Bip on a window's top edge to perch there, near the bottom of the screen to sit above the Dock, or near a side to dock it to that edge. Docked to a side, it can **peek**: tuck half out of view, then slide out when something happens or your cursor comes near.

### Wanders a little

Every few minutes (randomly 3 to 6), when nothing is going on, Bip toddles 50 to 140px along whatever it's sitting on, one foot at a time, and later walks back to its spot. It doesn't wander when:
- the menu, a card or a bubble is open;
- you're hovering over it or recording;
- Focus is on, or the OS's "reduce motion" setting is on;
- you chose "Stay put".

### Reacts to your cursor

- **Looks at it** when it's within about 240px.
- **Hops 80px aside** if the cursor *rushes* straight at it (faster than about 1 px/ms from within 110px), at most once every few seconds. A slow approach means you want Bip, so it stays put.
- **Rubbing over it** makes it purr (see Petted).

## Staying out of the way

- **Small.** The body is about 48px, the whole window 64×61, and only Bip's own pixels show.
- **Never takes focus.** The window doesn't activate, so your typing never goes to it.
- **Never covers what you're doing.** It sits above title bars, moves when your cursor heads its way, and steps out of the shot when you capture a window.
- **Speech bubbles are rare and short.** One line, gone after 10 seconds. If you miss one, a small dot stays on Bip and the message waits in the chat.
- **At most one bubble every 45 minutes,** and no more than 6 a day. Replies to something you just did ("Saved 📝") and celebrations don't count toward the limit.
- **Quiet when it should be:**
  - Hides for full-screen apps.
  - Under Focus or Do Not Disturb, it stays visible but makes no bubbles.
  - Quiet hours (default 22:00 to 08:00).
  - The right-click menu has "Stay put", "Hide for 1 hour", "Hide until tomorrow" and "Hide for this project".
- **Screen sharing.** Bubbles never show content, only a headline. The details are in the chat, which opens only on a click.

## The menu: a small ring around Bip

Click Bip and six round buttons fan out around it, always toward the middle of the screen so they never fall off an edge. Each has a short label on its outside:

```
            🎙 Hold to talk
     💬 Chat           📸 Capture
            ( Bip )
     🔗 Link           ✍️ Post
            📝 Note
```

Arrow keys move between buttons. Esc or a click elsewhere closes the ring. Picking an action opens a **compact card** (about 310px wide) for just that action, next to Bip.

| Button | Card | What it writes |
|---|---|---|
| **Capture** | Region, Active window (Bip steps out of the shot), Dev server, or Code | A screenshot in today's `shots/`, already approved because you asked. Region and Window use the OS's own capture tool. |
| **Post** | From today's work, a capture, a note or a link; for X, LinkedIn or Threads | A request in `~/.buildinpublic/requests/`. Your agent writes the draft next time you talk to it, and it shows up on the dashboard. |
| **Note** | One text box. ⌘↩ saves. | Today's `notes.md` for the project |
| **Link** | URL, plus "what did it help you solve?" | The session's `articles.md`, as **source: you** |
| **Chat** | A small conversation with Bip (below). Its badge counts waiting suggestions. | Whatever you ask for |
| **Hold to talk** | No card: hold the button and speak | A voice note (below) |

⌥⇧B (Alt+Shift+B) opens the Note card directly.

### Chat

The chat is the one place to tell Bip anything, and it's also where suggestions wait. When Bip has something for you, it appears here as a message with quick-reply buttons ("Capture" / "Not now").

Bip understands plain phrases with a small set of **local rules, not an AI model**:

| You type | Bip does |
|---|---|
| `note: Stripe retries in 10s` or `remember that …` | saves a note |
| a URL, optionally followed by `because …` | saves a link with your reason |
| `capture`, `capture the window`, `capture my app`, `capture the code` | the matching capture |
| `post about today for linkedin`, `draft from my note` | asks your agent for a draft |
| `what should I post?` | its best suggestion from today |
| `what did I do today?`, `how long this week?` | answers from your journal |
| `posted` | marks the last draft posted; Bip looks proud |
| `we launched` | launch-day celebration |
| `hide`, `later` | hides for an hour |
| anything else | passed to your agent as a request |

The composer has its own 🎙 button, so you can talk instead of type.

### Voice notes

Hold 🎙 (on the ring or in the chat) and talk. Release to save. A quick tap starts recording and a second tap stops, for when holding is awkward. While recording, Bip listens with its ears forward, and a small red bar shows the time. The limit is 60 seconds.

The recording is **transcribed on your computer** and saved as a note marked 🎙, together with the audio file. Nothing is uploaded.

This needs an optional extra, `pip install "build-in-public[voice]"`:
- **`sounddevice`** records from the microphone. macOS asks for microphone permission the first time.
- **`faster-whisper`** with the small English model transcribes. It's a one-time download of about 75MB, and Bip asks before downloading it.

Without the extra, the 🎙 buttons are hidden. `pet.keep_audio: false` deletes the audio once it's transcribed.

## Suggestions: when Bip speaks up

| Trigger | Signal | Mood | Suggestion (in the chat) | Bubble? |
|---|---|---|---|---|
| Dev server started | `shots.watch()` | curious | "Your app is running on :3000. Capture it?" | once per server |
| Tests green after failing | test commands in the live session | surprised, then curious | "Tests pass after 40 min. Capture the terminal?" | yes |
| Same test failed 3× | test commands in the live session | confused | none | no |
| Big commit | the post-commit hook | surprised | "Big commit (212 lines). Note down why?" | if more than ~150 lines |
| Session ended | the SessionEnd or Stop hooks | idle | "Anything worth remembering?" | no, just the dot |
| Post idea ready | the daily gist | has an idea | "Post idea: …" | yes, once |
| Reminder due | a scheduled post (dashboard plan) | has an idea | "Time to post: …" | yes |
| You posted | `buildinpublic posted`, the dashboard, or "posted" in the chat | proud | the clip blooms | a short reply |
| Milestone | post count, streak, release tag | party | none | yes (celebration) |
| Quiet 2+ days | the existing nudge | idle | "Haven't posted in 2 days. Want an easy one?" | once a day at most |

Say "Not now" three times to the same kind and Bip asks, in the chat, whether to stop those for good.

## When it appears and leaves

- **Starts** with the Claude Code or Codex `SessionStart` hook, or a new Antigravity session found by the sweep, for content projects only. It runs `buildinpublic pet --project <root>`; if Bip is already running, the command just switches the project, and the scarf changes colour.
- **One Bip per user,** with a lock file.
- **Leaves** when you quit it, or after 20 minutes with no agent session in any content project. Before going, it waves: "2 notes and a capture today."
- `buildinpublic pet` starts it by hand, `--stop` stops it, and `pet: off` disables it.

## How it's built

### Why Tkinter

Bip needs a small borderless window that stays on top, has a transparent background and moves around the screen, on macOS, Windows and Linux, without new required dependencies. Tkinter ships with Python:

- `overrideredirect(True)`: no title bar or border.
- `attributes("-topmost", True)`: stays above other windows.
- Transparency:
  - **Windows:** `-transparentcolor`, all-or-nothing per pixel. Soft 3D edges would get a fringe, so the Windows frames are rendered with a crisp 1px edge in the background's colour (see the open questions).
  - **macOS:** `-transparent` with a `systemTransparent` background.
  - **Linux:** `-alpha` on compositing desktops; otherwise a small rounded tile.
- **Moving:** `geometry("+x+y")` on a timer.
- **The cursor:** `winfo_pointerxy()`, about 20 times a second.
- **Frames are PNGs with real transparency.** That needs Tk 8.6. Apple's system Python 3.9 still ships Tk 8.5, and the installer uses whichever `python3` is on your PATH, so `buildinpublic doctor` checks the Tk version. On Tk 8.5, Bip falls back to GIF frames on a small rounded tile, and doctor suggests installing Python from python.org.
- **The menu, cards and chat** are small Tk `Toplevel` windows with the same no-focus-until-clicked behaviour. Only the chat text box takes focus, and only after you click it.

### Live agent states: hooks that cost nothing

The agent moods need events on every tool call, so the hooks must be practically free. With the pet turned on, the installer adds these Claude Code hooks:
- `PreToolUse`, matching `Read|Grep|Glob|Edit|Write|MultiEdit|Bash`;
- `Notification`;
- `Stop`.

Each one is a **single append command, not a Python start-up**: `cat >> ~/.buildinpublic/pet/agent.jsonl` on macOS and Linux, `Add-Content` in PowerShell on Windows. It takes about a millisecond. Bip reads that file twice a second and only looks at the tool name and the command's first word. It never reads file contents.

Other agents get what their hooks allow:
- **Codex:** `SessionStart` and `Stop`, so only working and done.
- **Antigravity:** no live hooks yet, so Bip stays idle and still gets everything the sweep finds.

### Finding the active window

| OS | How | Permission |
|---|---|---|
| Windows | `GetForegroundWindow` + `DwmGetWindowAttribute(EXTENDED_FRAME_BOUNDS)` via `ctypes` | none |
| macOS | front window's position and size from System Events via `osascript`, once a second | Accessibility, asked once. Without it, Bip uses the corner. |
| Linux (X11) | `_NET_ACTIVE_WINDOW` + geometry via `xprop` / `xdotool` | none |
| Linux (Wayland) | not possible for apps | Bip uses the corner; cursor reactions work only over Bip |

### Processes and files

```
src/buildinpublic/
  pet/
    app.py         Tk windows: Bip, ring, cards, chat; playback; drag/snap/peek
    brain.py       moods, suggestions, rate limits, milestones (no Tk)
    motion.py      perch, wander, dodge, petting: pure functions (no Tk)
    chat.py        the phrase rules → actions (no Tk)
    voice.py       optional: record + transcribe locally
    desktop.py     active window, full screen, Focus, cursor: per OS
    actions.py     capture / note / link / post-request / ask
    sprites/       generated PNG frames (GIF on Tk 8.5)
scripts/build_sprites.py   bip.js → PNG frames (Playwright), plus GIFs for Tk 8.5
```

- `brain.py`, `motion.py` and `chat.py` have no UI and are fully unit-tested.
- Hook events arrive through two append-only files: `pet/events.jsonl` (journal events) and `pet/agent.jsonl` (tool calls). No sockets, no ports.
- Actions call the existing modules (`shots`, `journal`, `nudge`, `research`), so the CLI, the dashboard and Bip share one code path.
- Requests to the agent go in `~/.buildinpublic/requests/<id>.md`, which the `SessionStart` hook and the skill pick up.

### Full-screen and Focus detection

| OS | Full screen in front | Do Not Disturb / Focus |
|---|---|---|
| macOS | front window size = screen size (same `osascript` call) | Focus state file, read only |
| Windows | `SHQueryUserNotificationState` | same call |
| Linux | `_NET_WM_STATE_FULLSCREEN` via `xprop` | GNOME `show-banners` |

## Privacy

- Bip doesn't record the screen, keystrokes or clipboard. It reads the active window's *position and size* (never its title or contents), the cursor position, and the *names* of your agent's tools. None of it is stored except the events it turns into journal entries.
- Captures and recordings happen only when you ask. Voice is transcribed on your computer; audio can be deleted after transcription.
- Bubbles show only headlines.
- Notes, links and voice notes reach a post only through a draft you approve.
- Bip makes one kind of network request: fetching the title of a link *you* add (`pet.fetch_titles: false` turns it off). The voice extra downloads its model once, after asking.

## Build order

1. **Spike (3–4 days).** On macOS (Tk 8.5 and 8.6), Windows 11, and Ubuntu (X11 and Wayland), test:
   - a transparent, always-on-top, non-focusing 64×61 PNG window;
   - `winfo_pointerxy`;
   - active-window bounds;
   - how smooth `geometry()` moves are;
   - how long the one-line hook takes.

   Also generate the first sprite sheet with `build_sprites.py`, and see how the soft edges look on each OS's transparency.
2. **Bip appears and leaves.** Idle, sleepy and editing moods, breathing, blinking, the corner home, drag/snap/peek, start and stop from hooks, the lock file, the doctor check.
3. **The ring with Note and Link cards.**
4. **Perching and motion.** The active window, following it, walking with feet, cursor look and dodge, petting, poke and dizzy.
5. **Live agent states.** The one-line hooks, `agent.jsonl`, and the reading, editing, testing, waiting and done moods.
6. **Capture.**
7. **Events, suggestions and the chat.** `brain.py` rules, bubbles, suggestions as chat messages, `chat.py` phrases.
8. **Post and Ask** via request files.
9. **Delight.** Milestones and confetti, accessories, colours, the streak clip, the global shortcut.
10. **Voice (optional extra).** Recording, local transcription, the 🎙 buttons.

## Tests

- `brain.py`: rate limits, quiet hours, "Not now" ×3, mood priority (confused beats suggestions; waiting beats editing), milestones fire once, celebrations wait out Focus.
- `motion.py`: perching, falling back, wander bounds and return, the dodge threshold and cooldown, freezing mid-walk, petting detection (needs back-and-forth, not a single swipe), three clicks → dizzy.
- `chat.py`: every phrase in the table, `linkedin` not mistaken for `link`, URLs with and without a reason, and unknown text going to the agent.
- `build_sprites.py`: every mood × frame renders inside the frame, and nothing is clipped at any ear angle or hat.
- `actions.py` and `voice.py`: write to a temp `BUILDINPUBLIC_HOME`, with the OS capture tool, microphone and model stubbed.
- The hook one-liner: appends a valid line in under 10ms on each OS.
- The Tk windows are smoke-tested where CI has a display; the rest is checked by hand on each OS.

## Open questions

1. **What's the buddy's name?** And should it get accessories (a scarf, headphones) and more poses so it can show all 18 moods?
1. **Soft edges on Windows.** Tk's transparency there is all-or-nothing, so Bip's soft 3D edges need a crisp outline on Windows. The spike decides if that looks good enough, or if the pet should use a small native window there instead.
1. **Should Post write the draft right away?** With `agent_command` (for example `claude -p`), Bip could write drafts in the background and show *thinking* until they're ready. Off by default?
2. **Should "Waiting for you" also bubble?** Your agent already notifies you, so it's off by default. Some people may want Bip to be the only signal.
3. **Where should voice notes live?** Today's `notes.md` with the audio next to it, or a separate `voice/` folder per session?
4. **Should "Not now" memory be per project or global?**
5. **How fast must the cursor rush to make Bip dodge?** About 1 px/ms with a mouse; trackpads may differ, so the spike should measure it.
