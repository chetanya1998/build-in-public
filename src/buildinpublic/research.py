"""Per-session research: related articles and post hooks.

articles.md  related discussions and articles for what the session touched
hooks.md     opening lines tailored to the session, plus openers that are
             performing well this week in the same space (real post titles)

Uses free, key-less endpoints (Hacker News Algolia, dev.to, Reddit, GitHub).
Network failures are recorded, never fatal. The agent can widen this with its
own web search when it writes drafts.
"""
from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

from .core import load_config

UA = {"User-Agent": "build-in-public/0.3 (+https://github.com/chetanya1998/build-in-public)"}
ERRORS: list[str] = []

EXT_TECH = {
    ".tsx": "react", ".jsx": "react", ".vue": "vue", ".svelte": "svelte", ".py": "python",
    ".rs": "rust", ".go": "golang", ".swift": "swift", ".kt": "kotlin", ".rb": "rails",
    ".php": "php", ".java": "java", ".dart": "flutter", ".sql": "postgres", ".ts": "typescript",
    ".astro": "astro", ".ex": "elixir", ".cs": "dotnet", ".tf": "terraform",
}
KNOWN = ["next.js", "nextjs", "react", "vue", "svelte", "tailwind", "supabase", "firebase", "stripe",
         "postgres", "prisma", "drizzle", "redis", "docker", "kubernetes", "vercel", "cloudflare",
         "aws", "lambda", "fastapi", "django", "flask", "express", "nestjs", "graphql", "trpc",
         "openai", "anthropic", "claude", "gemini", "llm", "rag", "embeddings", "langchain",
         "playwright", "cypress", "vite", "bun", "deno", "electron", "tauri", "react native", "expo",
         "auth", "oauth", "webhooks", "websocket", "pricing", "seo", "analytics", "saas",
         "mcp", "agent", "chrome extension", "shopify", "pwa", "ios", "android"]


def keywords(meta: dict, n: int = 4) -> list[str]:
    text = " ".join([meta.get("title", "")] + meta.get("prompts", []) + meta.get("outcome", [])).lower()
    c: Counter = Counter()
    for k in KNOWN:
        hits = len(re.findall(r"\b" + re.escape(k) + r"\b", text))
        if hits:
            c[k] += hits * 2
    for f in meta.get("files", []):
        t = EXT_TECH.get(Path(f).suffix)
        if t:
            c[t] += 1
    for cmd in meta.get("commands", []):
        for pkg in re.findall(r"(?:npm i(?:nstall)?|pnpm add|yarn add|bun add|pip install|uv add|cargo add)\s+([@\w/\-.]+)", cmd):
            c[pkg.split("/")[-1].lstrip("@")] += 2
    if "next.js" in c and "nextjs" in c:
        c["next.js"] += c.pop("nextjs")
    words = [w for w, _ in c.most_common(n)]
    return words or [meta.get("project_name", "indie hacking")]


def _get(url: str):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=12) as r:
            return json.loads(r.read().decode("utf-8", "ignore"))
    except Exception as e:
        ERRORS.append(f"{urllib.parse.urlparse(url).netloc}: {e}")
        return {}


def hn(q: str, days: int = 30):
    since = int(time.time() - days * 86400)
    d = _get("https://hn.algolia.com/api/v1/search?" + urllib.parse.urlencode(
        {"query": q, "tags": "story", "numericFilters": f"created_at_i>{since},points>15", "hitsPerPage": 5}))
    return [{"title": h.get("title"), "url": h.get("url") or f"https://news.ycombinator.com/item?id={h['objectID']}",
             "discussion": f"https://news.ycombinator.com/item?id={h['objectID']}", "source": "Hacker News",
             "meta": f"{h.get('points', 0)} points · {h.get('num_comments', 0)} comments",
             "engagement": h.get("points", 0)} for h in d.get("hits", []) if h.get("title")]


def devto(q: str, days: int = 30):
    tag = re.sub(r"[^a-z0-9]", "", q.lower())
    d = _get("https://dev.to/api/articles?" + urllib.parse.urlencode({"tag": tag, "top": days, "per_page": 5}))
    if not isinstance(d, list):
        return []
    return [{"title": a.get("title"), "url": a.get("url"), "source": "dev.to",
             "meta": f"{a.get('public_reactions_count', 0)} reactions",
             "engagement": a.get("public_reactions_count", 0)} for a in d]


def reddit(q: str, days: int = 30):
    d = _get("https://www.reddit.com/search.json?" + urllib.parse.urlencode(
        {"q": q, "sort": "top", "t": "month" if days > 7 else "week", "limit": 5}))
    kids = d.get("data", {}).get("children", []) if isinstance(d.get("data"), dict) else []
    return [{"title": c["data"].get("title"), "url": "https://reddit.com" + c["data"].get("permalink", ""),
             "source": f"r/{c['data'].get('subreddit')}",
             "meta": f"{c['data'].get('score', 0)} upvotes · {c['data'].get('num_comments', 0)} comments",
             "engagement": c["data"].get("score", 0)} for c in kids]


def github(q: str, days: int = 60):
    import datetime as dt
    since = (dt.date.today() - dt.timedelta(days=days)).isoformat()
    d = _get("https://api.github.com/search/repositories?" + urllib.parse.urlencode(
        {"q": f"{q} created:>{since}", "sort": "stars", "per_page": 3}))
    return [{"title": f"{r['full_name']} — {(r.get('description') or '')[:90]}", "url": r["html_url"],
             "source": "GitHub", "meta": f"★ {r.get('stargazers_count', 0)}",
             "engagement": r.get("stargazers_count", 0)} for r in d.get("items", [])]


SOURCES = {"hn": hn, "devto": devto, "reddit": reddit, "github": github}

# ---------------------------------------------------------------- hooks

# Original hook patterns, keyed by story signal. {x} placeholders are filled from the session.
PATTERNS = {
    "#war-story": [
        "I lost {time} to a bug in {thing}. The fix was one line.",
        "{thing} broke in a way I've never seen. Here's what was actually going on:",
        "The error said one thing. The real problem was somewhere else entirely.",
    ],
    "#metric": [
        "{thing}: before vs after. The difference surprised me.",
        "One change, one number that moved. Here's the change:",
        "I measured {thing} instead of guessing. Glad I did.",
    ],
    "#decision": [
        "I almost went with the obvious choice for {thing}. Here's why I didn't.",
        "Two ways to build {thing}. I picked the boring one.",
    ],
    "#milestone": [
        "{project} just hit a milestone I've been chasing for weeks.",
        "Shipped: {thing}. Here's what it took.",
    ],
    "#visual": [
        "Before / after on {thing}. Swipe to see the difference.",
        "Same feature, new UI. Which one would you use?",
    ],
    "#lesson": [
        "Something building {project} taught me about {thing}:",
        "I was wrong about {thing}. Here's what changed my mind.",
    ],
    "#pivot": ["I threw away {thing} today. Best decision this week."],
    "default": [
        "Building {project} in public, day {n}: {thing}.",
        "What I built today with an AI agent, and what I had to fix myself.",
        "Small win on {project} today: {thing}.",
        "If you're building with {tech}, this might save you an afternoon.",
    ],
}


def hooks_for(meta: dict, trending: list[dict]) -> str:
    thing = re.sub(r"^(please|can you|could you|let's|lets|now|ok|okay)\s+", "", meta.get("title", "this"), flags=re.I)
    thing = clip_words(thing.rstrip(".?!"), 9).lower()
    kws = keywords(meta, 2)
    fill = {"thing": thing, "project": meta.get("project_name", "my project"),
            "time": f"{int(meta.get('minutes') or 60)} minutes", "tech": kws[0] if kws else "AI agents",
            "n": "N"}
    L = [f"# Hooks · {meta.get('title')}", "", "## Tailored to this session"]
    tags = meta.get("tags") or []
    used = 0
    for tag in tags + ["default"]:
        for p in PATTERNS.get(tag, [])[:2]:
            L.append(f"- {p.format(**fill)}  _{tag}_")
            used += 1
        if used >= 8:
            break
    L += ["", "## Openers performing well this month in your space",
          "_Real titles with high engagement. Study the shape, don't copy the words._"]
    top = sorted([t for t in trending if t.get("engagement")], key=lambda t: -t["engagement"])[:6]
    L += [f"- \"{t['title']}\" · {t['source']} · {t['meta']}" for t in top] or ["- _no data (offline or sources unreachable)_"]
    L.append("")
    return "\n".join(L)


def clip_words(s: str, n: int) -> str:
    w = s.split()
    return " ".join(w[:n]) + ("…" if len(w) > n else "")


def research_session(session_dir: Path, force: bool = False) -> tuple[Path, Path] | None:
    session_dir = Path(session_dir)
    meta = json.loads((session_dir / "meta.json").read_text(encoding="utf-8"))
    art, hk = session_dir / "articles.md", session_dir / "hooks.md"
    if art.exists() and hk.exists() and not force:
        return art, hk
    cfg = load_config()
    ERRORS.clear()
    kws = keywords(meta)
    found: list[dict] = []
    for k in kws[:3]:
        for name in cfg.get("trend_sources", SOURCES):
            fn = SOURCES.get(name)
            if fn:
                for item in fn(k):
                    item["keyword"] = k
                    found.append(item)
                time.sleep(0.4)
    seen, items = set(), []
    for it in sorted(found, key=lambda x: -x.get("engagement", 0)):
        if it["url"] not in seen:
            seen.add(it["url"])
            items.append(it)
    L = [f"# Related reading · {meta.get('title')}", "", f"Keywords: {', '.join(kws)}", ""]
    for k in kws[:3]:
        group = [i for i in items if i["keyword"] == k][:6]
        if group:
            L.append(f"## {k}")
            L += [f"- [{i['title']}]({i['url']}) · {i['source']} · {i['meta']}" for i in group]
            L.append("")
    if not items:
        L.append("_Nothing found. You may be offline, or these topics are quiet this month._")
    if ERRORS:
        L += ["", "## Unreachable sources"] + [f"- {e}" for e in sorted(set(ERRORS))[:6]]
    art.write_text("\n".join(L) + "\n", encoding="utf-8")
    hk.write_text(hooks_for(meta, items), encoding="utf-8")
    (session_dir / "research.json").write_text(json.dumps(items[:30], indent=1), encoding="utf-8")
    return art, hk
