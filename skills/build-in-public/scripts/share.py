#!/usr/bin/env python3
"""Build In Public: put your approved posts and their images where GitHub can show them.

Reads the post files in .buildinpublic/posts/ and, for every post with status approved or
posted, copies its attached capture images into .buildinpublic/posts/images/ and writes
.buildinpublic/posts/README.md: one page with each post's text and image, newest first,
ready to open on GitHub (on your phone too) and copy.

With --stage it also adds those files to git. The optional pre-commit hook (init.sh --share)
runs it that way, so your posts ride along with each code commit and are on GitHub when you
push. Suggested posts you haven't approved are never added. It only runs when
.buildinpublic/config.json has "share": "commits".

Post files start with front matter:
  ---
  status: approved            # suggested | approved | posted
  platform: x
  date: 2026-10-22
  attach: daily/2026-10-22/captures/3ca93f-terminal-npm-run-bench.png
  trend: https://...
  link: https://x.com/...     # once posted
  ---
  # Title
  The post text...

Usage: python3 share.py [--repo PATH] [--stage] [--quiet]
"""
import argparse, json, re, shutil, subprocess, sys
from pathlib import Path

SHARED = ("approved", "posted")
PLATFORMS = {"x": "X", "linkedin": "LinkedIn", "threads": "Threads", "reddit": "Reddit", "devto": "dev.to",
             "dev.to": "dev.to", "blog": "Blog", "video": "Short video", "bluesky": "Bluesky"}


def parse(path):
    """(front matter dict, title, body) of a post file."""
    text = path.read_text()
    meta, body = {}, text
    m = re.match(r"---\s*\n(.*?)\n---\s*\n?(.*)", text, re.S)
    if m:
        for line in m.group(1).splitlines():
            k, sep, v = line.partition(":")
            if sep and k.strip():
                meta[k.strip().lower()] = v.split(" #")[0].strip()
        body = m.group(2)
    t = re.search(r"^#\s+(.+)$", body, re.M)
    title = t.group(1).strip() if t else path.stem
    if t:
        body = body[:t.start()] + body[t.end():]
    return meta, title, body.strip()


def shared_posts(repo):
    posts = repo / ".buildinpublic" / "posts"
    out = []
    for f in sorted(posts.glob("*.md")) if posts.is_dir() else []:
        if f.name == "README.md":
            continue
        meta, title, body = parse(f)
        if meta.get("status", "").lower() in SHARED:
            out.append((f, meta, title, body))
    # newest first, by date then file name
    return sorted(out, key=lambda p: (p[1].get("date") or p[0].name[:10], p[0].name), reverse=True)


def copy_images(repo, meta):
    base, images = repo / ".buildinpublic", repo / ".buildinpublic" / "posts" / "images"
    copied = []
    for rel in [a.strip() for a in meta.get("attach", "").split(",") if a.strip() and a.strip() != "none"]:
        src = (base / rel) if not Path(rel).is_absolute() else Path(rel)
        if src.suffix.lower() not in (".png", ".jpg", ".jpeg", ".gif", ".webp"):
            continue
        dst = images / src.name
        if src.exists():
            images.mkdir(parents=True, exist_ok=True)
            if not dst.exists() or dst.read_bytes() != src.read_bytes():
                shutil.copy2(src, dst)
        if dst.exists():
            copied.append(dst)
    return copied


def render(repo, posts, images):
    L = [f"# Build In Public · {repo.name}", "",
         "Posts you approved, ready to copy and post. Newest first.", "",
         "<sub>Written by [Build In Public](https://github.com/chetanya1998/build-in-public). "
         "Edit the post files next to this page, not the page itself.</sub>", ""]
    for f, meta, title, body in posts:
        status = meta.get("status", "").lower()
        bits = [PLATFORMS.get(meta.get("platform", "").lower(), meta.get("platform", "")),
                meta.get("date", ""), "✅ posted" if status == "posted" else "📝 ready to post"]
        L += ["---", "", f"## {title}", "", " · ".join(b for b in bits if b), ""]
        for img in images[f]:
            L += [f"![{title}](images/{img.name})", ""]
        L += [body, ""]
        links = [f"[Post file]({f.name})"]
        if meta.get("link"):
            links.append(f"[Posted here]({meta['link']})")
        if meta.get("trend") and meta["trend"] != "none":
            links.append(f"[Trend it rides]({meta['trend']})")
        L += [" · ".join(links), ""]
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    ap.add_argument("--stage", action="store_true", help="git add the shared files (used by the pre-commit hook)")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()
    repo = Path(subprocess.run(["git", "-C", a.repo, "rev-parse", "--show-toplevel"],
                               capture_output=True, text=True).stdout.strip() or a.repo).resolve()
    say = (lambda *x: None) if a.quiet else print

    cfg_path = repo / ".buildinpublic" / "config.json"
    try:
        cfg = json.loads(cfg_path.read_text()) if cfg_path.exists() else {}
    except ValueError:
        cfg = {}
    if a.stage and cfg.get("share") != "commits":
        return  # sharing with commits is off

    posts = shared_posts(repo)
    if not posts:
        say("No approved posts to share yet.")
        return
    images = {f: copy_images(repo, meta) for f, meta, _, _ in posts}
    page = repo / ".buildinpublic" / "posts" / "README.md"
    page.write_text(render(repo, posts, images))
    say(f"Shared {len(posts)} post(s) in {page}")

    if a.stage:
        files = [page] + [f for f, *_ in posts] + [i for imgs in images.values() for i in imgs]
        # -f: posts/ may be in .gitignore from an older setup; only these files are added.
        r = subprocess.run(["git", "-C", str(repo), "add", "-f", "--", *map(str, files)],
                           capture_output=True, text=True)
        if r.returncode:
            print(f"Build In Public: couldn't add posts to the commit: {r.stderr.strip()}", file=sys.stderr)


if __name__ == "__main__":
    main()
