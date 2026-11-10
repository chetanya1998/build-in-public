"""Build Your Product in Public: read a brief.md, and turn its Markdown into clean text or HTML.

Shared by notify.py (the gist email), posts.py (list and show posts) and brief_check.py.
Standard library only. Reads the template format (templates/brief.md) and older briefs:

  ### 1. Title (X / behind the scenes)        or   1. **Title** · X thread · ...
  **Hook:** "..."
  **Angle:** ...
"""
import html
import re

SECTIONS = ("Today in one line", "What you shipped", "Suggested posts", "The story",
            "Nearest trends", "Screenshots to review", "Capture tomorrow")
POST_FIELDS = ("Platform", "Hook", "Angle", "Anecdote", "Trend", "Capture", "Why it works")
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
        fields = {}
        for f in re.finditer(r"^\*\*([^*:]+):\*\*\s*(.*?)(?=^\*\*[^*:]+:\*\*|\Z)", m.group(3), re.S | re.M):
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
