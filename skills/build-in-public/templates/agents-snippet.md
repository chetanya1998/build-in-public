
## Build In Public
After finishing any meaningful task, append an entry to `.buildinpublic/log/<today YYYY-MM-DD>.md` (create the file if needed):

### HH:MM - <short title>  (agent: <your name>)
- **What:** what was built or changed, in plain words
- **Why:** the problem or user need behind it
- **How:** key decision, trick or tradeoff (one or two lines)
- **Struggle:** what broke or took longest, if anything
- **Result:** measurable outcome or before/after, if any
- **Files:** main files touched
- **Tags:** any of #war-story #metric #decision #visual #lesson #milestone #pivot

When a moment is worth showing (tests going green after a long fight, a benchmark, a deploy, a new screen in a browser test), ask the user first: "Capture this for today's story? 1) terminal output 2) browser screenshot 3) skip". Only if they say yes, run the build-in-public skill's `scripts/capture.py` with `--approved`. Never capture without asking, and skip this if `.buildinpublic/config.json` has `"capture": "off"`.

Skip trivial changes. Never include secrets, keys, customer data or anything listed under Off-limits in `.buildinpublic/narrative.md`.
