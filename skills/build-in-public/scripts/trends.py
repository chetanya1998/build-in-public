#!/usr/bin/env python3
"""Build In Public: what are people talking about this week around your project?

Pulls the top recent discussions for each topic in .buildinpublic/config.json
from free, key-less public sources (Hacker News, Reddit, GitHub, dev.to) and writes
.buildinpublic/daily/<date>/trends.md. The agent adds its own web search on top
(X, LinkedIn, news) when it writes the brief.

Usage: python3 trends.py [--date YYYY-MM-DD] [--repo PATH] [--days 7]
"""
import argparse, datetime as dt, json, subprocess, time, urllib.parse, urllib.request
from pathlib import Path

ERRORS = []
UA = {"User-Agent": "build-in-public/0.2 (+https://github.com/build-in-public)"}


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
    topics = cfg.get("topics") or []
    if not topics:
        print("No topics in .buildinpublic/config.json; skipping trends.")
        return
    enabled = cfg.get("trend_sources") or list(SOURCES)

    L = [f"# Trends {day} (last {a.days} days)", "",
         "Raw signals. The agent picks which ones genuinely connect to today's work.", ""]
    for topic in topics:
        L.append(f"## {topic}")
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
