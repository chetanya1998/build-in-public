"""Print the install commands shown on the landing page, exactly as a visitor copies them.

  python3 scripts/site_commands.py agent unix    # the commands inside the "Your agent" prompt
  python3 scripts/site_commands.py term win      # the Terminal tab, Windows

CI runs these on macOS, Linux and Windows, so the site never shows a command that doesn't work.
"""
import html
import re
import sys
from pathlib import Path

PAGE = Path(__file__).resolve().parents[1] / "docs" / "page.html"


def commands(panel: str, os_name: str, page: str = None) -> list:
    page = page if page is not None else PAGE.read_text(encoding="utf-8")
    boxes = re.findall(rf'<div class="cmd[^"]*" data-panel="{panel}" data-for="{os_name}"[^>]*><pre>(.*?)</pre>', page, re.S)
    if not boxes:
        sys.exit(f"No {panel}/{os_name} install box on the page")
    if len(set(boxes)) != 1:
        sys.exit(f"The install boxes for {panel}/{os_name} differ between sections of the page")
    return [html.unescape(re.sub(r"<[^>]+>", "", c)) for c in re.findall(r'<span class="run">(.*?)</span>', boxes[0], re.S)]


if __name__ == "__main__":
    print("\n".join(commands(sys.argv[1], sys.argv[2])))
