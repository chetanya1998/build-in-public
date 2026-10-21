#!/usr/bin/env python3
"""Build In Public: what are people talking about this week around your project and today's work?

Searches free, key-less public sources (Hacker News, Reddit, GitHub, dev.to) for:
  - today's work: themes taken from today's log entries and commit messages
  - the project: the topics in .buildinpublic/config.json
  - the stack: frameworks found in package.json, requirements.txt, pyproject.toml, go.mod, Cargo.toml, Gemfile
and writes .buildinpublic/daily/<date>/trends.md. The agent adds its own web search on top
(X, LinkedIn, news) when it writes the brief.

Usage: python3 trends.py [--date YYYY-MM-DD] [--repo PATH] [--days 7]
"""
import argparse, datetime as dt, json, re, subprocess, time, urllib.parse, urllib.request
from pathlib import Path

ERRORS = []
UA = {"User-Agent": "build-in-public/0.2 (+https://github.com/chetanya1998/build-in-public)"}


def get(url):
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode())
    except Exception as e:  # network is best-effort
        ERRORS.append(f"{url.split('/')[2]}: {e}")
        return {"_error": str(e)}


def hn(q, days):
    since = int(time.time() - days * 86400)
    d = get("https://hn.algolia.com/api/v1/search?" + urllib.parse.urlencode(
        {"query": q, "tags": "story", "numericFilters": f"created_at_i>{since},points>20", "hitsPerPage": 6}))
    return [(h.get("title"), f"https://news.ycombinator.com/item?id={h['objectID']}",
             f"{h.get('points', 0)} pts · {h.get('num_comments', 0)} comments") for h in d.get("hits", [])]


def reddit(q, days):
    t = "week" if days <= 7 else "month"
    d = get("https://www.reddit.com/search.json?" + urllib.parse.urlencode(
        {"q": q, "sort": "top", "t": t, "limit": 6}))
    items = d.get("data", {}).get("children", []) if isinstance(d.get("data"), dict) else []
    return [(c["data"].get("title"), "https://reddit.com" + c["data"].get("permalink", ""),
             f"r/{c['data'].get('subreddit')} · {c['data'].get('score', 0)} up · {c['data'].get('num_comments', 0)} comments")
            for c in items]


def github(q, days):
    since = (dt.date.today() - dt.timedelta(days=max(days, 30))).isoformat()
    d = get("https://api.github.com/search/repositories?" + urllib.parse.urlencode(
        {"q": f"{q} created:>{since}", "sort": "stars", "order": "desc", "per_page": 5}))
    return [(f"{r['full_name']}: {(r.get('description') or '')[:100]}", r["html_url"],
             f"★ {r.get('stargazers_count', 0)}") for r in d.get("items", [])]


def devto(q, days):
    tag = q.lower().replace(" ", "")
    d = get("https://dev.to/api/articles?" + urllib.parse.urlencode({"tag": tag, "top": days, "per_page": 5}))
    if not isinstance(d, list):
        return []
    return [(a.get("title"), a.get("url"), f"{a.get('public_reactions_count', 0)} reactions") for a in d]


SOURCES = {"Hacker News": hn, "Reddit": reddit, "GitHub (new repos)": github, "dev.to": devto}

# dependency name -> search phrase
STACK = {
    "next": "next.js", "react": "react", "vue": "vue", "svelte": "svelte", "@sveltejs/kit": "sveltekit",
    "astro": "astro", "remix": "remix", "@remix-run/react": "remix", "nuxt": "nuxt", "angular": "angular",
    "@angular/core": "angular", "express": "express.js", "fastify": "fastify", "hono": "hono",
    "tailwindcss": "tailwind css", "prisma": "prisma", "@prisma/client": "prisma", "drizzle-orm": "drizzle orm",
    "stripe": "stripe", "@supabase/supabase-js": "supabase", "firebase": "firebase", "convex": "convex",
    "electron": "electron", "react-native": "react native", "expo": "expo", "three": "three.js",
    "@playwright/test": "playwright", "vitest": "vitest", "bun": "bun", "deno": "deno",
    "openai": "openai api", "@anthropic-ai/sdk": "claude api", "anthropic": "claude api", "ai": "vercel ai sdk",
    "langchain": "langchain", "django": "django", "fastapi": "fastapi", "flask": "flask", "pandas": "pandas",
    "torch": "pytorch", "streamlit": "streamlit", "pydantic": "pydantic", "sqlalchemy": "sqlalchemy",
    "rails": "ruby on rails", "github.com/gin-gonic/gin": "gin golang", "tokio": "tokio rust",
    "axum": "axum rust", "tauri": "tauri", "bevy": "bevy",
}
STOP = set("""a an and are as at be by for from in into is it its of on or that the this to with without when
we our my your you they them so not no new now add added adds use uses using make made fix fixed fixes
update updated updates remove removed change changed improve improved wip chore feat refactor docs test
tests bump merge branch pull request after before more less than via all some only also just get got
first one two day today""".split())


def stack_keywords(repo, limit=3):
    """Frameworks this project depends on, as search phrases."""
    names = []
    pkg = repo / "package.json"
    if pkg.exists():
        try:
            d = json.loads(pkg.read_text())
            names += list(d.get("dependencies", {})) + list(d.get("devDependencies", {}))
        except ValueError:
            pass
    for f in ("requirements.txt", "pyproject.toml", "go.mod", "Cargo.toml", "Gemfile"):
        p = repo / f
        if p.exists():
            names += re.findall(r"[A-Za-z0-9_@./-]+", p.read_text(errors="ignore").lower())
    found = []
    for n in names:
        phrase = STACK.get(n.lower())
        if phrase and phrase not in found:
            found.append(phrase)
    return found[:limit]


def day_themes(repo, day, limit=3):
    """Short search phrases for what was worked on today, from log titles and commit subjects."""
    lines = []
    log = repo / ".buildinpublic" / "log" / f"{day}.md"
    if log.exists():
        lines += [re.sub(r"\(agent:.*?\)", "", t) for t in re.findall(r"^###\s*[\d:]*\s*-\s*(.+)$", log.read_text(), re.M)]
    if (repo / ".git").exists():
        lines += subprocess.run(["git", "-C", str(repo), "log", f"--since={day} 00:00",
                                 f"--until={day + dt.timedelta(days=1)} 06:00", "--pretty=%s"],
                                capture_output=True, text=True).stdout.splitlines()
    themes = []
    for line in lines:
        line = re.sub(r"^\w+(\([^)]*\))?!?:\s*", "", line)  # drop "feat(scope):" style prefixes
        words = [w for w in re.findall(r"[A-Za-z][A-Za-z0-9.+#-]*", line.lower())
                 if w not in STOP and len(w) > 2 and not w.isdigit()]
        q = " ".join(words[:3])
        if len(words) >= 2 and q not in themes:
            themes.append(q)
    return themes[:limit]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=None)
    ap.add_argument("--repo", default=".")
    ap.add_argument("--days", type=int, default=7)
    a = ap.parse_args()
    day = a.date or str((dt.datetime.now() - dt.timedelta(hours=4)).date())
    repo = Path(subprocess.run(["git", "-C", a.repo, "rev-parse", "--show-toplevel"],
                               capture_output=True, text=True).stdout.strip() or a.repo).resolve()
    cfg_path = repo / ".buildinpublic" / "config.json"
    cfg = json.loads(cfg_path.read_text()) if cfg_path.exists() else {}
    topics = [t for t in cfg.get("topics") or [] if "<" not in t]
    groups = [("Today's work", t) for t in day_themes(repo, dt.date.fromisoformat(day))]
    groups += [("Project", t) for t in topics]
    groups += [("Stack", t) for t in stack_keywords(repo) if t not in topics]
    if not groups:
        print("Nothing to search: no topics in .buildinpublic/config.json and no work logged today.")
        return
    enabled = cfg.get("trend_sources") or list(SOURCES)

    L = [f"# Trends {day} (last {a.days} days)", "",
         "Raw signals. The agent picks the ones that genuinely connect to today's work,",
         "and searches the web for more (X, LinkedIn, news) around the same themes.", ""]
    for kind, topic in groups:
        L.append(f"## {kind}: {topic}")
        for name in enabled:
            fn = SOURCES.get(name)
            if not fn:
                continue
            rows = [r for r in fn(topic, a.days) if r[0]]
            if rows:
                L.append(f"**{name}**")
                L += [f"- [{t}]({u}) · {meta}" for t, u, meta in rows]
            time.sleep(1)  # be polite to free APIs
        L.append("")
    if ERRORS:
        L += ["## Unreachable sources", *[f"- {e}" for e in sorted(set(ERRORS))], ""]
    out = repo / ".buildinpublic" / "daily" / day
    out.mkdir(parents=True, exist_ok=True)
    (out / "trends.md").write_text("\n".join(L))
    print(out / "trends.md")


if __name__ == "__main__":
    main()
