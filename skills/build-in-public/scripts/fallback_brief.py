#!/usr/bin/env python3
"""Build Your Product in Public: write the day's brief without an agent.

nightly.sh runs this when the agent couldn't write brief.md (signed out, out of credits, timed out,
or no agent set up), so the gist still has posts. Same template as the agent's brief
(templates/brief.md), built only from what's on disk:

  - stories: the agent log entries (What, Struggle, Result), the agent sessions (what you asked,
    files edited) and your commits, from digest.md
  - reference articles: the links trends.py found today, from trends.md
  - context: config.json topics and platforms

The posts are plainer than an agent's: a starting point to edit, never posted for you.
Usage: python3 fallback_brief.py [--repo PATH] [--date YYYY-MM-DD] [--reason "why the agent didn't"]
"""
import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import brieflib  # noqa: E402

MARK = "<!-- written without an agent -->"
TRIVIAL = re.compile(r"^(yes|no|ok|okay|go|continue|commit|push|commit and push|do it|fix it|thanks?|"
                     r"try again|retry|done|next|more changes first|change \w+ first)\b", re.I)
LINK = re.compile(r"^- \[([^\]]+)\]\((https?://[^)\s]+)\)")


def section(text, name):
    m = re.search(rf"^## {re.escape(name)}[^\n]*\n(.*?)(?=^## |\Z)", text, re.S | re.M)
    return m.group(1).strip() if m else ""


def clip(text, n):
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= n:
        return text
    cut = text[:n].rsplit(" ", 1)[0].rstrip(",;:-")
    return cut + "…"


def first_sentence(text, n=160):
    m = re.match(r"(.+?[A-Za-z)\]\"'][.!?])(\s|$)", text.strip())  # not "1." in a list
    return clip(m.group(1) if m else text, n)


# ---------------------------------------------------------------- what happened today

def log_stories(digest):
    out = []
    for m in re.finditer(r"^### [\d:]+ - (.+?)\s+\(agent[^)]*\)\s*\n(.*?)(?=^### |\Z)",
                         section(digest, "Agent log entries"), re.S | re.M):
        title, body = m.group(1).strip(), m.group(2)
        f = dict(re.findall(r"^- \*\*(\w+):\*\*\s*(.+)$", body, re.M))
        out.append({"title": title, "what": f.get("What", title), "why": f.get("Why", ""),
                    "moment": f.get("Struggle") or f.get("Result") or f.get("How", ""),
                    "result": f.get("Result", ""), "source": "log entry", "files": f.get("Files", "")})
    return out


def session_stories(digest):
    out = []
    for m in re.finditer(r"^## ([\w ]+?) session \d+\n(.*?)(?=^## |\Z)", digest, re.S | re.M):
        agent, body = m.group(1), m.group(2)
        asked = re.search(r"\*\*User asked:\*\*\n((?:- .*\n?)+)", body)
        prompts = [p[2:].strip() for p in (asked.group(1).splitlines() if asked else []) if p.startswith("- ")]
        real = [p for p in prompts if len(p) >= 12 and not TRIVIAL.match(p)]
        if not real:
            continue
        files = re.search(r"\*\*Files edited:\*\* (.+)", body)
        tools = re.search(r"\*\*Tool calls:\*\* (\d+)", body)
        files = [f.strip() for f in files.group(1).split(",")] if files else []
        focus = min(real, key=len) if len(real) > 1 and len(min(real, key=len)) < 60 else real[0]
        moment = []
        if tools:
            moment.append(f"{tools.group(1)} agent steps")
        if files:
            moment.append(f"{len(files)} files changed ({', '.join(Path(f).name for f in files[:3])})")
        out.append({"title": first_sentence(focus, 90).rstrip("."), "what": first_sentence(real[0], 220),
                    "why": "", "moment": "It took " + " and ".join(moment) + "." if moment else "",
                    "result": "", "source": f"{agent} session", "files": ", ".join(files[:5])})
    return out


def commit_stories(digest):
    out = []
    lines = section(digest, "Git commits").splitlines()
    for i, line in enumerate(lines):
        m = re.match(r"^- \d\d:\d\d ([0-9a-f]{7,}) (.+?)(?: \((on [^,)]+)?(?:, )?(by [^)]+)?\))?$", line)
        if not m or m.group(4) or m.group(2).lower().startswith("merge"):
            continue  # someone else's commit, or a merge: listed as shipped, not a post
        stat = lines[i + 1].strip() if i + 1 < len(lines) and "changed" in lines[i + 1] else ""
        ins = re.search(r"(\d+) insertion", stat)
        moment = f"{int(ins.group(1)):,} lines in one commit ({m.group(1)})." if ins and int(ins.group(1)) > 20 else ""
        out.append({"title": m.group(2), "what": m.group(2), "why": "", "moment": moment, "result": "",
                    "source": f"commit {m.group(1)}", "files": ""})
    return out


def shipped(digest):
    rows = []
    for s in log_stories(digest):
        rows.append(f"- {s['what']} (log entry)")
    for line in section(digest, "Git commits").splitlines():
        m = re.match(r"^- \d\d:\d\d ([0-9a-f]{7,}) (.+)$", line)
        if m:
            rows.append(f"- {m.group(2)} ({m.group(1)})")
    for s in session_stories(digest):
        rows.append(f"- {s['title']} ({s['source']})")
    return rows[:8]


def articles(trends):
    """Today's reference articles from trends.md: (title, url, theme), topic matches first."""
    out, theme = [], ""
    for line in trends.splitlines():
        if line.startswith("## "):
            theme = re.sub(r"^## (Project|Stack|Today):\s*", "", line).strip()
            if theme.startswith("Unreachable"):
                theme = None
        elif theme and (m := LINK.match(line.strip())):
            title = re.sub(r"\s+", " ", m.group(1)).strip()
            out.append((clip(title, 110), m.group(2), theme))
    seen, uniq = set(), []
    for a in out:
        if a[1] not in seen:
            seen.add(a[1])
            uniq.append(a)
    return uniq


# ---------------------------------------------------------------- posts

def hashtags(cfg, repo, n=3):
    """#buildinpublic, your own "hashtags" from config.json, then short topics, then #devlog #coding."""
    tags = ["#buildinpublic"]
    short = [t for t in cfg.get("topics", []) if len(t.split()) <= 2]
    for t in cfg.get("hashtags", []) + short + ["devlog", "coding"]:
        words = re.findall(r"[A-Za-z0-9]+", t)
        tag = "#" + "".join(w.lower() for w in words[:2])
        if 3 < len(tag) <= 20 and "buildinpublic" not in tag and tag not in tags:
            tags.append(tag)
    return " ".join(tags[:n])


QUESTIONS = ("What would you have done differently?", "How would you have approached it?",
             "Have you hit something like this?", "What would you build next?")


def question(cfg, i=0):
    return QUESTIONS[i % len(QUESTIONS)]


def post_text(story, platform, cfg, repo, context, i=0):
    hook = f"Today's build: {story['title'].rstrip('.')}."
    tags = hashtags(cfg, repo)
    q = question(cfg, i)
    if brieflib.platform_key(platform) == "x":
        for moment in (story["moment"], ""):
            text = "\n\n".join(p for p in (hook, moment, q, tags) if p)
            if brieflib.x_length(text) <= 280:
                return text
        return "\n\n".join((clip(hook, 280 - len(tags) - len(q) - 4), q, tags))
    body = [hook, story["moment"] or story["what"], story["why"] and f"Why: {story['why']}", context, q, tags]
    return "\n\n".join(p for p in body if p)


def readme_context(repo):
    for name in ("README.md", "readme.md", "README"):
        f = repo / name
        if f.exists():
            for para in re.split(r"\n\s*\n", f.read_text(errors="ignore")):
                p = re.sub(r"<[^>]+>|!\[[^\]]*\]\([^)]*\)|\[([^\]]+)\]\([^)]*\)|[*_`#>]", r"\1", para).strip()
                if len(p) > 60 and not p.startswith(("|", "-", "```")):
                    return first_sentence(p, 200)
    return ""


def build(repo, day, reason=""):
    out = repo / ".buildinpublic" / "daily" / str(day)
    digest = (out / "digest.md").read_text(errors="ignore") if (out / "digest.md").exists() else ""
    trends = (out / "trends.md").read_text(errors="ignore") if (out / "trends.md").exists() else ""
    try:
        cfg = json.loads((repo / ".buildinpublic" / "config.json").read_text())
    except (OSError, ValueError):
        cfg = {}
    platforms = [{"x": "X post", "linkedin": "LinkedIn"}.get(p, p) for p in (cfg.get("platforms") or ["x", "linkedin"])]
    sessions, commits = session_stories(digest), commit_stories(digest)
    for c in commits:  # a commit's numbers come from the session that made it, when there is one
        if not c["moment"] and sessions:
            c["moment"] = sessions[0]["moment"]
        elif sessions and sessions[0]["moment"]:
            c["moment"] = c["moment"].rstrip(".") + ". " + sessions[0]["moment"]
    stories = (log_stories(digest) + commits + sessions)[:3]
    refs = articles(trends)
    context = readme_context(repo)
    caps = [l[2:] for l in section(digest, "Approved captures").splitlines() if l.startswith("- ")]

    L = [MARK, f"# Daily Gist · {day}", "", "## Today in one line"]
    L.append(f"{stories[0]['title'].rstrip('.')}." if stories else "A quiet day: no sessions, commits or log entries found.")
    L += ["", "## What you shipped"] + (shipped(digest) or ["_Nothing shipped today._"]) + ["", "## Suggested posts", ""]
    n = 0
    for i, s in enumerate(stories):
        ref = refs[i % len(refs)] if refs else None
        for platform in platforms[:2]:
            n += 1
            text = post_text(s, platform, cfg, repo, context, n - 1)
            shot = caps[0].split(" · ")[-1].split(",")[0].strip() if caps else "No screenshot"
            L += [f"### {n}. {s['title'].rstrip('.')}", f"**Platform:** {platform}", "**Post:**", "```text", text, "```",
                  f"**Screenshot:** {shot}",
                  f"**Angle:** What you built today, told plainly.",
                  f"**Anecdote:** {s['moment'] or s['what']} (from your {s['source']})",
                  f"**Context:** {'README' if context else 'config.json topics'}",
                  f"**Trend:** [{ref[0]}]({ref[1]}) found today under \"{ref[2]}\"" if ref else "**Trend:** no trend",
                  "**Why it works:** It's real work from today. Written without your agent, so add your own voice before posting.",
                  ""]
            if n >= 5:
                break
        if n >= 5:
            break
    if not n:
        L += ["_No story to post today. Say \"build in public brief\" to your agent for ideas._", ""]
    L += ["## The story",
          (f"Written without your agent ({reason}). " if reason else "Written without an agent. ")
          + "These posts use only what was found on this computer today; your agent writes better ones when it can run.", "",
          "## Nearest trends"]
    L += [f"{i}. **{clip(t, 60)}**: from today's search for \"{th}\". [{t}]({u})" for i, (t, u, th) in enumerate(refs[:5], 1)] \
        or ["_No articles found today._"]
    cands = [l for l in section(digest, "Screenshot candidates").splitlines() if l.startswith("- ")]
    L += ["", "## Screenshots to review"] + (cands or ["- none"])
    L += ["", "## Capture tomorrow", "1. The moment something you build today starts working: say yes when your agent offers a capture.", ""]
    (out / "brief.md").write_text("\n".join(L))
    return out / "brief.md", n


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    ap.add_argument("--date")
    ap.add_argument("--reason", default="")
    a = ap.parse_args(argv)
    repo = Path(subprocess.run(["git", "-C", a.repo, "rev-parse", "--show-toplevel"],
                               capture_output=True, text=True).stdout.strip() or a.repo).resolve()
    day = a.date or str((dt.datetime.now() - dt.timedelta(hours=4)).date())
    path, n = build(repo, day, a.reason)
    print(f"Wrote {path} without an agent: {n} post(s)")


if __name__ == "__main__":
    main()
