#!/usr/bin/env python3
"""Build Your Product in Public: check a brief before it's emailed.

  - all seven sections are there (templates/brief.md)
  - every suggested post has its fields, and a ready-to-post text (the **Post:** block)
  - every post fits its platform: X 280 characters a post, LinkedIn 3,000 characters and 300
    words (override with "post_limits" in config.json); a missing question or hashtags is a warning
  - every link opens: a 404 or a domain that doesn't exist is an error; a site that blocks
    checks (403, 429, timeouts) is a warning, because it may still work in a browser.
    Redirects are followed, including 308.

Writes daily/<date>/brief-check.json for the gist email, and prints the problems.
Exit code 1 when something must be fixed.

Usage: python3 brief_check.py [--repo PATH] [--date YYYY-MM-DD] [--offline] [FILE]
"""
import argparse, datetime as dt, json, socket, subprocess, sys, urllib.error, urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import brieflib  # noqa: E402

UA = {"User-Agent": "Mozilla/5.0 (build-in-public link check; +https://github.com/chetanya1998/build-in-public)"}
NEEDED = ("Platform", "Post", "Trend", "Why it works")


class Redirects(urllib.request.HTTPRedirectHandler):
    """Follow 308 too: Python before 3.11 treats it as an error, though browsers follow it."""
    def http_error_308(self, req, fp, code, msg, headers):
        return self.http_error_301(req, fp, 301, msg, headers)

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        new = super().redirect_request(req, fp, 302 if code == 308 else code, msg, headers, newurl)
        if new is not None and req.get_method() == "HEAD":
            new.method = "HEAD"
        return new


OPENER = urllib.request.build_opener(Redirects)


def check_link(url, timeout=12):
    """('ok' | 'dead' | 'unsure', detail)."""
    for method in ("HEAD", "GET"):
        try:
            req = urllib.request.Request(url, method=method, headers=UA)
            with OPENER.open(req, timeout=timeout) as r:
                return "ok", str(r.status)
        except urllib.error.HTTPError as e:
            if e.code in (404, 410):
                return "dead", f"HTTP {e.code}"
            if method == "HEAD" and e.code in (403, 405, 400, 501):
                continue  # some sites refuse HEAD; try a real GET
            return "unsure", f"HTTP {e.code}"
        except urllib.error.URLError as e:
            if isinstance(e.reason, socket.gaierror):
                return "dead", "domain not found"
            return "unsure", str(e.reason)[:60]
        except (socket.timeout, TimeoutError, OSError) as e:
            return "unsure", str(e)[:60] or "timeout"
    return "unsure", "no answer"


def check(text, offline=False, link_check=check_link, limits=None):
    errors, warnings = [], []
    for name in brieflib.SECTIONS:
        if f"## {name}" not in text:
            errors.append(f"Missing section: ## {name}")
    posts = brieflib.suggested_posts(text)
    if "## Suggested posts" in text and not posts:
        errors.append("No suggested posts found (use '### 1. Title' with **Field:** lines, as in templates/brief.md)")
    for p in posts:
        name = f"Post {p['n']} ({p['title'][:40]})"
        missing = [f for f in NEEDED if not (p["fields"].get(f) or (f == "Platform" and p["platform"]))]
        if "Post" in missing:
            missing.remove("Post")
            if p["fields"].get("Hook"):  # an older brief: still readable, but not ready to copy
                warnings.append(f"{name}: older format, with a Hook but no ready-to-post text")
            else:
                errors.append(f"{name}: no ready-to-post text (a **Post:** line followed by a ```text block)")
        if missing:
            warnings.append(f"{name}: missing {', '.join(missing)}")
        if p["fields"].get("Post"):
            stats = brieflib.post_stats(p["platform"], p["fields"]["Post"], limits)
            errors += [f"{name}: {e}" for e in stats["errors"]]
            warnings += [f"{name}: {w}" for w in stats["warnings"]]
    dead, unsure = [], []
    if not offline:
        for url in brieflib.links(text):
            state, detail = link_check(url)
            if state == "dead":
                dead.append(url)
                errors.append(f"Dead link ({detail}): {url}")
            elif state == "unsure":
                unsure.append(url)
                warnings.append(f"Couldn't check ({detail}): {url}")
    return {"errors": errors, "warnings": warnings, "dead_links": dead, "unchecked_links": unsure}


def post_limits(repo):
    """'post_limits' from the project's config.json, if any."""
    try:
        return json.loads((repo / ".buildinpublic" / "config.json").read_text()).get("post_limits") or {}
    except (OSError, ValueError):
        return {}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("file", nargs="?")
    ap.add_argument("--repo", default=".")
    ap.add_argument("--date")
    ap.add_argument("--offline", action="store_true", help="skip the link checks")
    a = ap.parse_args(argv)
    if a.file:
        brief, out, limits = Path(a.file), None, None
    else:
        repo = Path(subprocess.run(["git", "-C", a.repo, "rev-parse", "--show-toplevel"],
                                   capture_output=True, text=True).stdout.strip() or a.repo).resolve()
        day = a.date or str((dt.datetime.now() - dt.timedelta(hours=4)).date())
        brief = repo / ".buildinpublic" / "daily" / day / "brief.md"
        out = brief.parent / "brief-check.json"
        limits = post_limits(repo)
    if not brief.exists():
        sys.exit(f"No brief at {brief}")
    result = check(brief.read_text(), offline=a.offline, limits=limits)
    if out:
        out.write_text(json.dumps(result, indent=2) + "\n")
    for e in result["errors"]:
        print(f"✗ {e}")
    for w in result["warnings"]:
        print(f"! {w}")
    if not result["errors"] and not result["warnings"]:
        print("✓ Brief looks good: all sections, every post within its limit, every link opens.")
    sys.exit(1 if result["errors"] else 0)


if __name__ == "__main__":
    main()
