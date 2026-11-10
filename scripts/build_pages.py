"""Wrap docs/page.html (the page body, also used for previews) into docs/index.html for GitHub Pages."""
from pathlib import Path

docs = Path(__file__).resolve().parents[1] / "docs"
body = (docs / "page.html").read_text(encoding="utf-8")
head_extra = """<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta property="og:title" content="Build Your Product in Public">
<meta property="og:description" content="Journals every Claude Code, Codex and Antigravity session across all your projects and turns it into build-in-public posts.">
<meta property="og:image" content="https://chetanya1998.github.io/build-in-public/assets/shot-code.webp">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="favicon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="apple-touch-icon.png">
<style>:root{padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}body{margin:0}img{max-width:100%}[hidden]{display:none!important}</style>
"""
title_end = body.index("</title>") + len("</title>")
style_start = body.index("<style>")
style_end = body.index("</style>") + len("</style>")
head = body[:title_end] + "\n" + head_extra + body[title_end:style_end]
html = f"<!doctype html>\n<html lang=\"en\">\n<head>\n{head}\n</head>\n<body>\n{body[style_end:].strip()}\n</body>\n</html>\n"
(docs / "index.html").write_text(html, encoding="utf-8")
print(f"wrote {docs / 'index.html'} ({len(html)//1024} KB)")
