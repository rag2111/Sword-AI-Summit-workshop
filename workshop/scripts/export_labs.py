"""Maintainer tool: export docs/*.md (MkDocs Material) to labs/*.md (plain GitHub / VS Code markdown).

Conversions
  !!! concept "Title"      -> > [!NOTE]       (dothis -> TIP, checkpoint -> IMPORTANT, troubleshoot -> WARNING)
  === "Tab"                -> **Tab** heading + un-indented content
  <span class="lab-timer"> -> **⏱ N min**
  <div class="disclaimer"> -> > [!CAUTION]
  images/...               -> ../docs/images/...

    python scripts/export_labs.py          # write labs/
    python scripts/export_labs.py --check  # exit 1 if labs/ is stale
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS, LABS = ROOT / "docs", ROOT / "labs"
ALERTS = {"concept": "NOTE", "dothis": "TIP", "checkpoint": "IMPORTANT", "troubleshoot": "WARNING",
          "warning": "WARNING", "note": "NOTE", "info": "NOTE", "tip": "TIP"}
ADMONITION = re.compile(r'^!!! (\w+)(?: "(.*)")?\s*$')
TAB = re.compile(r'^=== "(.*)"\s*$')
TIMER = re.compile(r'<span class="lab-timer" data-minutes="(\d+)">[^<]*</span>')
HEADER = "<!-- Generated from docs/{name} by scripts/export_labs.py — edit the docs/ version. -->\n\n"


def _take_block(lines: list[str], start: int) -> tuple[list[str], int]:
    """Collect the 4-space-indented block that follows an admonition/tab line."""
    block, index = [], start
    while index < len(lines) and (lines[index].startswith("    ") or not lines[index].strip()):
        block.append(lines[index][4:] if lines[index].startswith("    ") else "")
        index += 1
    while block and not block[-1].strip():
        block.pop()
        index -= 1
    return block, index


def convert(text: str) -> str:
    lines = TIMER.sub(r"**⏱ \1 min**", text).replace("](images/", "](../docs/images/").splitlines()
    out: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if match := ADMONITION.match(line):
            kind, title = match.group(1), match.group(2)
            block, index = _take_block(lines, index + 1)
            body = convert("\n".join(block)).splitlines()
            out.append(f"> [!{ALERTS.get(kind, 'NOTE')}]")
            if title:
                out.append(f"> **{title}**")
                out.append(">")
            out.extend(f"> {b}".rstrip() for b in body)
            continue
        if match := TAB.match(line):
            block, index = _take_block(lines, index + 1)
            out.append(f"**{match.group(1)}**")
            out.append("")
            out.extend(convert("\n".join(block)).splitlines())
            continue
        if line.startswith('<div class="disclaimer"'):
            index += 1
            out.append("> [!CAUTION]")
            while index < len(lines) and not lines[index].startswith("</div>"):
                out.append(f"> {lines[index]}".rstrip())
                index += 1
            index += 1
            continue
        out.append(line)
        index += 1
    return "\n".join(out) + "\n"


def export() -> dict[Path, str]:
    return {LABS / path.name: HEADER.format(name=path.name) + convert(path.read_text(encoding="utf-8")) for path in sorted(DOCS.glob("*.md"))}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export docs/ to plain-markdown labs/.")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    outputs = export()
    if args.check:
        stale = [str(p.relative_to(ROOT)) for p, text in outputs.items() if not p.exists() or p.read_text(encoding="utf-8") != text]
        print("\n".join(stale) or "labs/ is up to date")
        return 1 if stale else 0
    LABS.mkdir(exist_ok=True)
    for path, text in outputs.items():
        path.write_text(text, encoding="utf-8")
    print(f"Exported {len(outputs)} pages to {LABS.relative_to(ROOT)}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
