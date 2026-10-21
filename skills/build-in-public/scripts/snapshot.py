#!/usr/bin/env python3
"""Build In Public: screenshot your running app for today's posts.

Takes desktop + mobile screenshots of every URL in config.json "snapshot_urls"
(for example your local dev server or staging) using Playwright, and saves them to
.buildinpublic/daily/<date>/snapshots/. Screenshots your agents already took while
browser-testing are collected separately by collect.py.

Needs:  pip install playwright && playwright install chromium
Usage:  python3 snapshot.py [--date YYYY-MM-DD] [--repo PATH] [--url URL ...]
"""
import argparse, datetime as dt, json, re, subprocess, sys
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=None)
    ap.add_argument("--repo", default=".")
    ap.add_argument("--url", action="append", default=[])
    a = ap.parse_args()
    day = a.date or str((dt.datetime.now() - dt.timedelta(hours=4)).date())
    repo = Path(subprocess.run(["git", "-C", a.repo, "rev-parse", "--show-toplevel"],
                               capture_output=True, text=True).stdout.strip() or a.repo).resolve()
    cfg_path = repo / ".buildinpublic" / "config.json"
    cfg = json.loads(cfg_path.read_text()) if cfg_path.exists() else {}
    urls = a.url or cfg.get("snapshot_urls") or []
    if not urls:
        print("No snapshot_urls configured; skipping.")
        return
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright not installed: pip install playwright && playwright install chromium")
        return

    out = repo / ".buildinpublic" / "daily" / day / "snapshots"
    out.mkdir(parents=True, exist_ok=True)
    views = {"desktop": {"width": 1440, "height": 900}, "mobile": {"width": 390, "height": 844}}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for url in urls:
            slug = re.sub(r"[^a-z0-9]+", "-", url.lower().split("//")[-1]).strip("-")[:60]
            for name, vp in views.items():
                page = browser.new_page(viewport=vp, device_scale_factor=2)
                try:
                    page.goto(url, wait_until="networkidle", timeout=20000)
                    f = out / f"app-{slug}-{name}.png"
                    page.screenshot(path=str(f))
                    print(f)
                except Exception as e:
                    print(f"skip {url} ({name}): {e}", file=sys.stderr)
                finally:
                    page.close()
        browser.close()


if __name__ == "__main__":
    main()
