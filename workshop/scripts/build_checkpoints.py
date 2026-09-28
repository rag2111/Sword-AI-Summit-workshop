"""Maintainer tool: generate src/care_agent/ (starter) and solutions/lab1..lab6/ from one source.

The single source lives in scripts/checkpoints/source/care_agent/. Code that a lab fills in is
wrapped in marker comments:

    # [lab2:solution]
    ...code that exists from the end of Lab 2 onwards...
    # [lab2:starter]
    ...TODO block shown before Lab 2 is done...
    # [lab2:end]

Level 0 = starter (src/care_agent), level N = solutions/labN (cumulative: blocks with lab <= N use
the solution code). `__CHECKPOINT__` is replaced with "starter" / "labN".

    python scripts/build_checkpoints.py            # regenerate solutions/ only (safe for participants)
    python scripts/build_checkpoints.py --starter  # ALSO overwrite src/care_agent (maintainers only!)
    python scripts/build_checkpoints.py --check    # exit 1 if solutions/ are out of date
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts" / "checkpoints" / "source" / "care_agent"
LABS = range(1, 7)
MARKER = re.compile(r"^\s*# \[lab(\d):(solution|starter|end)\]\s*$")


def render(text: str, level: int) -> str:
    """Resolve lab markers for a checkpoint level (0 = starter)."""
    out: list[str] = []
    lab: int | None = None
    mode: str | None = None
    for line_no, line in enumerate(text.splitlines(keepends=True), start=1):
        match = MARKER.match(line)
        if match:
            marker_lab, kind = int(match.group(1)), match.group(2)
            if kind == "solution":
                if lab is not None:
                    raise ValueError(f"line {line_no}: nested lab block")
                lab, mode = marker_lab, "solution"
            elif kind == "starter":
                if lab != marker_lab or mode != "solution":
                    raise ValueError(f"line {line_no}: [lab{marker_lab}:starter] without matching solution")
                mode = "starter"
            else:
                if lab != marker_lab or mode != "starter":
                    raise ValueError(f"line {line_no}: [lab{marker_lab}:end] without matching starter")
                lab, mode = None, None
            continue
        if lab is None:
            out.append(line)
        elif (mode == "solution") == (lab <= level):
            out.append(line)
    if lab is not None:
        raise ValueError(f"unterminated [lab{lab}] block")
    label = "starter" if level == 0 else f"lab{level}"
    return "".join(out).replace("__CHECKPOINT__", label)


def build(level: int, target: Path) -> None:
    """Write every rendered module and delete stale .py files (bytecode caches are left alone)."""
    target.mkdir(parents=True, exist_ok=True)
    names = set()
    for path in sorted(SOURCE.glob("*.py")):
        names.add(path.name)
        (target / path.name).write_text(render(path.read_text(encoding="utf-8"), level), encoding="utf-8")
    for stale in target.glob("*.py"):
        if stale.name not in names:
            stale.unlink()


def outdated(level: int, target: Path) -> list[str]:
    problems = []
    for path in sorted(SOURCE.glob("*.py")):
        expected = render(path.read_text(encoding="utf-8"), level)
        actual_path = target / path.name
        if not actual_path.exists() or actual_path.read_text(encoding="utf-8") != expected:
            problems.append(str(actual_path.relative_to(ROOT)))
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--starter", action="store_true", help="also regenerate src/care_agent (overwrites!)")
    parser.add_argument("--check", action="store_true", help="only check that solutions/ are up to date")
    args = parser.parse_args(argv)
    if args.check:
        problems = [p for lab in LABS for p in outdated(lab, ROOT / "solutions" / f"lab{lab}")]
        print("\n".join(problems) or "solutions/ are up to date")
        return 1 if problems else 0
    for lab in LABS:
        build(lab, ROOT / "solutions" / f"lab{lab}")
    if args.starter:
        build(0, ROOT / "src" / "care_agent")
    print("Checkpoints generated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
