"""Build Your Product in Public: read a brief.md, and turn its Markdown into clean text or HTML.

Shared by notify.py (the gist email), posts.py (list and show posts) and brief_check.py.
Standard library only. Reads the template format (templates/brief.md) and older briefs:

  ### 1. Title                                or   1. **Title** · X thread · ...
  **Platform:** LinkedIn
  **Post:**
  ```text
  <the post, ready to copy: hook, anecdote, context, engagement question, hashtags>
  ```
  **Screenshot:** ...
  **Angle:** ...

Older briefs have a **Hook:** line instead of a **Post:** block; they still read.
"""
import html
import re

SECTIONS = ("Today in one line", "What you shipped", "Suggested posts", "The story",
            "Nearest trends", "Screenshots to review", "Capture tomorrow")
POST_FIELDS = ("Platform", "Post", "Screenshot", "Angle", "Anecdote", "Context", "Trend", "Why it works")
# How each post was made, shown under the post itself (Hook and Capture are from older briefs)
DETAIL_FIELDS = ("Angle", "Anecdote", "Context", "Trend", "Why it works", "Hook", "Capture", "Notes")
POST_BLOCK = re.compile(r"^\*\*Post:\*\*[ \t]*\n+```[\w-]*[ \t]*\n(.*?)\n```[ \t]*$", re.S | re.M)

# Platform limits. "chars" is the platform's hard limit; "words" is a length to stay under.
# X counts every link as 23 characters. Override any of these with "post_limits" in config.json.
LIMITS = {
    "x": {"chars": 280},
    "linkedin": {"chars": 3000, "words": 300},
    "threads": {"chars": 500},
    "bluesky": {"chars": 300},
    "mastodon": {"chars": 500},
}
LINKEDIN_FOLD = 210  # characters LinkedIn shows before "...see more"
URL = re.compile(r"https?://\S+")
THREAD_PART = re.compile(r"^\s*\d+\s*/\s*(?:\d+)?\s", re.M)
LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")
BARE_URL = re.compile(r"(?<![(\"'=])\bhttps?://[^\s)<>\"]+")


def section(text, name):
    m = re.search(rf"^##\s+{re.escape(name)}\s*\n(.*?)(?=^##\s(?!#)|\Z)", text, re.S | re.M)
    if not m:
        return ""
    return re.sub(r"^\s*-{3,}\s*$", "", m.group(1), flags=re.M).strip()


def _split_title(raw):
    """'"The loop is closed." (X / behind the scenes)' -> ('The loop is closed.', 'X / behind the scenes')."""
    raw = raw.strip()
    m = re.match(r"^(.*?)\s*\(([^()]*)\)\s*$", raw)
    title, platform = (m.group(1), m.group(2)) if m else (raw, "")
    return to_text(title).strip().strip("\"“”'"), to_text(platform).strip()


def suggested_posts(text):
    """The numbered suggestions in a brief, as [{n, title, platform, fields: {name: text}}]."""
    body = section(text, "Suggested posts")
    posts = []
    # template / heading style
    for m in re.finditer(r"^###\s*(\d+)[.)]\s*(.+?)\n(.*?)(?=^###\s*\d+[.)]|\Z)", body, re.S | re.M):
        title, platform = _split_title(m.group(2))
        fields, chunk = {}, m.group(3)
        block = POST_BLOCK.search(chunk)
        if block:  # the post itself keeps its line breaks
            fields["Post"] = block.group(1).strip("\n")
            chunk = chunk[:block.start()] + chunk[block.end():]
        for f in re.finditer(r"^\*\*([^*:]+):\*\*\s*(.*?)(?=^\*\*[^*:]+:\*\*|\Z)", chunk, re.S | re.M):
            fields[f.group(1).strip()] = " ".join(f.group(2).split())
        platform = fields.pop("Platform", "") or platform
        posts.append({"n": int(m.group(1)), "title": title, "platform": platform, "fields": fields})
    if posts:
        return posts
    # older one-line style: 1. **Title** · X thread · rides ... · attach ...
    for m in re.finditer(r"^\s*(\d+)[.)]\s+(.+)$", body, re.M):
        parts = [p.strip() for p in re.split(r"\s+·\s+", m.group(2))]
        title = to_text(parts[0]).strip().strip("\"“”'")
        posts.append({"n": int(m.group(1)), "title": title, "platform": parts[1] if len(parts) > 1 else "",
                      "fields": {"Notes": " · ".join(parts[2:])} if len(parts) > 2 else {}})
    return posts


def platform_key(platform):
    """'X thread' -> 'x', 'LinkedIn post' -> 'linkedin', 'dev.to' -> 'dev.to'."""
    p = platform.lower()
    for key, names in (("x", ("x ", "x/", "twitter")), ("linkedin", ("linkedin",)), ("threads", ("threads",)),
                       ("bluesky", ("bluesky",)), ("mastodon", ("mastodon",))):
        if p.strip() == key or any(n in p + " " for n in names):
            return key
    return p.split()[0] if p.split() else ""


def x_length(text):
    """Characters as X counts them: every link is 23."""
    return len(URL.sub("x" * 23, text))


def thread_parts(text):
    """An X thread's posts, split where a line starts with 1/, 2/ ... (or 1/5, 2/5)."""
    starts = [m.start() for m in THREAD_PART.finditer(text)]
    if len(starts) < 2:
        return [text]
    return [text[a:b].strip() for a, b in zip(starts, starts[1:] + [len(text)])]


def post_stats(platform, text, limits=None):
    """Length and shape of a ready-to-post text: {chars, words, limit, errors, warnings}."""
    key = platform_key(platform)
    limit = dict(LIMITS.get(key, {}))
    limit.update((limits or {}).get(key, {}))
    errors, warnings = [], []
    chars, words = len(text), len(text.split())
    if key == "x":
        parts = thread_parts(text) if "thread" in platform.lower() else [text]
        for i, part in enumerate(parts, 1):
            n = x_length(part)
            if limit.get("chars") and n > limit["chars"]:
                where = f"part {i} of the thread" if len(parts) > 1 else "the post"
                hint = " Start each post of a thread with 1/, 2/ ..." if len(parts) == 1 and "thread" in platform.lower() else ""
                errors.append(f"{where} is {n} characters; X allows {limit['chars']}.{hint}")
        chars = max(x_length(p) for p in parts)
    else:
        if limit.get("chars") and chars > limit["chars"]:
            errors.append(f"{chars} characters; {platform} allows {limit['chars']}")
        if limit.get("words") and words > limit["words"]:
            errors.append(f"{words} words; keep {platform} posts under {limit['words']}")
        if key == "linkedin":
            first = text.strip().split("\n\n")[0]
            if len(first) > LINKEDIN_FOLD:
                warnings.append(f"the hook is {len(first)} characters, so LinkedIn cuts it at '...see more' ({LINKEDIN_FOLD})")
    if re.search(r"`|\*\*|\[[^\]]+\]\(", text):
        warnings.append("Markdown (` ** [](...)) shows up as-is when posted: use plain text")
    lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
    if not lines or not re.fullmatch(r"(#[\w-]+\s*)+", lines[-1]):
        warnings.append("no hashtags line at the end")
    if "?" not in "\n".join(lines[-3:]):
        warnings.append("no engagement question near the end")
    return {"key": key, "chars": chars, "words": words, "limit": limit, "errors": errors, "warnings": warnings}


def links(text):
    """Every http(s) link in the text, Markdown or bare, in order, without duplicates."""
    found = [u for _, u in LINK.findall(text)] + BARE_URL.findall(LINK.sub("", text))
    return list(dict.fromkeys(u.rstrip(".,;") for u in found))


# ---------- Markdown -> clean text / HTML (the small subset briefs use)

def to_text(s):
    """Inline Markdown to plain text: [t](u) -> t (u), no ** _ ` markers."""
    s = LINK.sub(lambda m: f"{m.group(1)} ({m.group(2)})", s)
    s = re.sub(r"\*\*(.+?)\*\*", r"\1", s)
    s = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"\1", s)
    s = re.sub(r"(?<![\w])_(?!\s)(.+?)(?<!\s)_(?![\w])", r"\1", s)
    return s.replace("`", "")


def to_html(s):
    """Inline Markdown to HTML, escaped, with clickable links."""
    out, pos = [], 0
    for m in LINK.finditer(s):
        out.append(_inline_html(s[pos:m.start()]))
        out.append(f'<a href="{html.escape(m.group(2), quote=True)}" style="color:#2c4bd4">{_inline_html(m.group(1))}</a>')
        pos = m.end()
    out.append(_inline_html(s[pos:]))
    return "".join(out)


def _inline_html(s):
    s = html.escape(s, quote=False)
    s = BARE_URL.sub(lambda m: f'<a href="{m.group(0)}" style="color:#2c4bd4">{m.group(0)}</a>', s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", s)
    s = re.sub(r"(?<![\w/])_(?!\s)(.+?)(?<!\s)_(?![\w])", r"<em>\1</em>", s)
    s = re.sub(r"`([^`]+)`", r'<code style="background:#f1f3f6;padding:1px 5px;border-radius:4px">\1</code>', s)
    return s


def block_lines(block):
    """A section's lines with headings and rules dropped: [('li'|'p'|'quote', text)]."""
    out = []
    for line in block.splitlines():
        t = line.strip()
        if not t or re.fullmatch(r"-{3,}|\*{3,}", t):
            continue
        if re.match(r"^[-*]\s+", t):
            out.append(("li", re.sub(r"^[-*]\s+", "", t)))
        elif re.match(r"^\d+[.)]\s+", t):
            out.append(("li", t))
        elif t.startswith(">"):
            out.append(("quote", t.lstrip("> ")))
        else:
            out.append(("p", re.sub(r"^#+\s*", "", t)))
    return out
