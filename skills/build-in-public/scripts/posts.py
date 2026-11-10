#!/usr/bin/env python3
"""Build Your Product in Public: your posts, from the terminal or your agent.

  posts.py                   every saved post (suggested, approved, posted), newest first
  posts.py --today           today's suggested posts from the brief, plus posts saved today
  posts.py --status approved only approved (or suggested, posted)
  posts.py show 2            suggestion 2 from today's brief, as clean text
  posts.py show <id>         a saved post (any part of its file name), ready to copy

Run from your project's folder. --date YYYY-MM-DD looks at another day's brief.
"""
import argparse, datetime as dt, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import brieflib  # noqa: E402
import share  # noqa: E402  (reads a post's front matter)

ROOT = Path(".buildinpublic")
STATUS_ORDER = {"suggested": 0, "approved": 1, "posted": 2}


def saved_posts():
    out = []
    for f in sorted((ROOT / "posts").glob("*.md")) if (ROOT / "posts").is_dir() else []:
        if f.name == "README.md":
            continue
        meta, title, body = share.parse(f)
        out.append({"id": f.stem, "path": f, "title": title, "body": body,
                    "status": (meta.get("status") or "suggested").lower(),
                    "platform": share.PLATFORMS.get(meta.get("platform", "").lower(), meta.get("platform", "")),
                    "date": meta.get("date") or f.stem[:10],
                    "link": meta.get("link", ""), "attach": meta.get("attach", "")})
    return sorted(out, key=lambda p: (p["date"], p["id"]), reverse=True)


def brief_for(day):
    """(day, brief text) for the asked day, or the latest brief before it."""
    daily = ROOT / "daily"
    exact = daily / str(day) / "brief.md"
    if exact.exists():
        return day, exact.read_text()
    older = sorted(p for p in daily.glob("*/brief.md") if p.parent.name <= str(day)) if daily.is_dir() else []
    if older:
        return dt.date.fromisoformat(older[-1].parent.name), older[-1].read_text()
    return None, ""


def row(p):
    plat = (p["platform"] or "-")[:10]
    return f"  {p['status']:<9} {p['date']:<10}  {plat:<10}  {p['title'][:60]}\n            {p['id']}"


def show_suggestion(post, day):
    f = post["fields"]
    L = [f"Suggested post {post['n']} · {day}", "", post["title"]]
    if post["platform"]:
        L.append(post["platform"])
    if f.get("Post"):
        stats = brieflib.post_stats(post["platform"], f["Post"])
        L += ["", f"Ready to post ({stats['chars']:,} characters, {stats['words']:,} words):", "", f["Post"]]
        L += [f"! {e}" for e in stats["errors"]]
    elif f.get("Hook"):
        L += ["", "Hook (ready to post):", "  " + brieflib.to_text(f["Hook"])]
    shot = brieflib.to_text(f.get("Screenshot") or f.get("Capture") or "")
    L += ["", f"Screenshot: {shot}" if shot and shot.lower().strip('".') not in ("none", "no screenshot") else "No screenshot"]
    details = [n for n in brieflib.DETAIL_FIELDS if f.get(n) and not (n == "Hook" and not f.get("Post"))]
    if details:
        L += ["", "How this post was made:"]
        L += ["  " + f"{n}: " + brieflib.to_text(f[n]) for n in details]
    L += ["", f'To change it, tell your agent: "write post {post["n"]}".']
    return "\n".join(L)


def show_saved(p):
    L = [p["title"], " · ".join(x for x in (p["platform"], p["date"], p["status"]) if x), ""]
    L.append(p["body"].strip())
    if p["attach"] and p["attach"] != "none":
        L += ["", f"Attach: .buildinpublic/{p['attach']}"]
    if p["link"]:
        L += [f"Posted: {p['link']}"]
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(description="List and show your posts.")
    ap.add_argument("show", nargs="*", help='"show 2" or "show <id>"')
    ap.add_argument("--today", action="store_true")
    ap.add_argument("--status", choices=["suggested", "approved", "posted"])
    ap.add_argument("--date")
    a = ap.parse_args(argv)
    day = dt.date.fromisoformat(a.date) if a.date else (dt.datetime.now() - dt.timedelta(hours=4)).date()
    if not ROOT.is_dir():
        sys.exit("No .buildinpublic/ here. Run this from your project's folder, after \"set up build in public\".")

    if a.show:
        what = a.show[-1] if a.show[0] == "show" else a.show[0]
        if what.isdigit():
            bday, text = brief_for(day)
            match = [p for p in brieflib.suggested_posts(text) if p["n"] == int(what)]
            if not match:
                sys.exit(f"No suggested post {what} in {'the brief for ' + str(bday) if bday else 'any brief yet'}.")
            print(show_suggestion(match[0], bday))
        else:
            match = [p for p in saved_posts() if what in p["id"]]
            if not match:
                sys.exit(f"No saved post matching '{what}'. Run posts.py to see them.")
            print(show_saved(match[0]))
        return

    saved = saved_posts()
    if a.status:
        saved = [p for p in saved if p["status"] == a.status]
    if a.today:
        bday, text = brief_for(day)
        sugg = brieflib.suggested_posts(text) if bday == day else []
        print(f"Today's suggested posts · {day}")
        if sugg:
            for p in sugg:
                plat = f"  ({p['platform']})" if p["platform"] else ""
                print(f"  {p['n']}. {p['title']}{plat}")
            print('     Show one: posts.py show 2 · draft one: tell your agent "write post 2"')
        else:
            print("  None yet: no brief for today. Ask your agent: \"build in public brief\".")
        saved = [p for p in saved if p["date"] == str(day)]
        print(f"\nSaved today ({len(saved)})")
    else:
        counts = {s: sum(1 for p in saved if p["status"] == s) for s in STATUS_ORDER}
        print(f"Your posts ({len(saved)}): " + ", ".join(f"{n} {s}" for s, n in counts.items() if n) if saved
              else "Your posts (0)")
    for p in saved:
        print(row(p))
    if not saved:
        print("  None yet. Pick a suggestion and tell your agent \"write post 2\"; approved drafts are saved here.")
    else:
        print("\n  Show one: posts.py show <id>")


if __name__ == "__main__":
    main()
