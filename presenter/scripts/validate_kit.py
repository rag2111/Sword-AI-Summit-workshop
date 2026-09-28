"""Validate the presenter kit: timings, Mermaid fences, forbidden wording.

Run from the repo root: python3 presenter/scripts/validate_kit.py
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PRESENTER = ROOT / "presenter"
REGISTERS = [ROOT / "docs/preview/presenter.md", ROOT / "docs/apim-exceptions/presenter.md"]
TIMED_FILES = [PRESENTER / "run-of-show.md", PRESENTER / "timing-cards.md"]
TOTAL = 105
ROW = re.compile(r"^\|\s*(\d\d):(\d\d)[–-](\d\d):(\d\d)\s*\|\s*([^|]+?)\s*\|\s*(\d+)\s*\|")
FORBIDDEN = re.compile("two" + r"[\s-]*hour|2[\s-]*hour|2h\b", re.IGNORECASE)

errors: list[str] = []


def rows(text: str, start: str | None = None, end: str | None = None):
    if start:
        text = text.split(start, 1)[1].split(end, 1)[0]
    out = []
    for line in text.splitlines():
        m = ROW.match(line)
        if m:
            h1, m1, h2, m2, seg, mins = m.groups()
            out.append((int(h1) * 60 + int(m1), int(h2) * 60 + int(m2), seg.strip(), int(mins)))
    return out


contract = rows((ROOT / "docs/CONTRACT.md").read_text(encoding="utf-8").split("## 7.", 1)[1].split("## 8.", 1)[0])

for path in TIMED_FILES:
    r = rows(path.read_text(encoding="utf-8"), "<!-- timing-table:start -->", "<!-- timing-table:end -->")
    name = path.relative_to(ROOT)
    cursor = 0
    for s, e, seg, mins in r:
        if s != cursor:
            errors.append(f"{name}: gap/overlap before '{seg}' (starts {s}, expected {cursor})")
        if e - s != mins:
            errors.append(f"{name}: '{seg}' clock span {e - s} != minutes {mins}")
        cursor = e
    total = sum(x[3] for x in r)
    if total != TOTAL or cursor != TOTAL:
        errors.append(f"{name}: total {total} min, ends at {cursor} (expected {TOTAL})")
    if [(s, e, seg, m) for s, e, seg, m in r] != contract:
        errors.append(f"{name}: timing rows differ from CONTRACT §7")
    print(f"{name}: {len(r)} segments, {total} min, ends {cursor // 60:02d}:{cursor % 60:02d}")

files = sorted(PRESENTER.rglob("*.md")) + REGISTERS
mermaid_count = 0
for path in files:
    text = path.read_text(encoding="utf-8")
    name = path.relative_to(ROOT)
    in_fence, fence_lang, line_no = False, "", 0
    for i, line in enumerate(text.splitlines(), 1):
        if line.startswith("```"):
            if not in_fence:
                in_fence, fence_lang, line_no = True, line[3:].strip(), i
                if fence_lang == "mermaid":
                    mermaid_count += 1
            elif line.strip() == "```":
                in_fence = False
            else:
                errors.append(f"{name}:{i}: fence opened inside open fence (line {line_no})")
    if in_fence:
        errors.append(f"{name}: unclosed ``` fence from line {line_no}")
    for i, line in enumerate(text.splitlines(), 1):
        if FORBIDDEN.search(line):
            errors.append(f"{name}:{i}: forbidden duration wording: {line.strip()}")

print(f"Mermaid blocks: {mermaid_count}; markdown files checked: {len(files)}")
if errors:
    print("FAILED:\n  " + "\n  ".join(errors))
    sys.exit(1)
print("OK: timings match CONTRACT §7 and sum to 105 min; fences balanced; no forbidden wording")
