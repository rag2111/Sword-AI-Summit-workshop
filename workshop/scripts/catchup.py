"""`uv run poe catchup <N>` — jump to the end of lab N.

Copies solutions/labN/ over src/care_agent/. Your current code is first backed up to
.catchup_backups/<timestamp>-before-labN/ so nothing is ever lost.
"""

from __future__ import annotations

import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VALID_LABS = range(1, 7)


def catchup(lab: int, root: Path = ROOT, now: datetime | None = None) -> Path:
    """Copy solutions/lab<lab>/ into src/care_agent/ and return the backup folder."""
    if lab not in VALID_LABS:
        raise ValueError(f"Lab must be 1-6 (got {lab}). Lab 0 has no code to catch up on.")
    source = root / "solutions" / f"lab{lab}"
    target = root / "src" / "care_agent"
    if not source.is_dir():
        raise FileNotFoundError(f"{source} does not exist")
    stamp = (now or datetime.now()).strftime("%Y%m%d-%H%M%S")
    backup = root / ".catchup_backups" / f"{stamp}-before-lab{lab}"
    if target.exists():
        shutil.copytree(target, backup, ignore=shutil.ignore_patterns("__pycache__"), copy_function=shutil.copy)
        for item in target.iterdir():
            if item.is_dir():
                shutil.rmtree(item, ignore_errors=True)  # e.g. __pycache__
            else:
                item.unlink()
    else:
        target.mkdir(parents=True)
    for item in source.iterdir():
        if item.name == "__pycache__":
            continue
        if item.is_dir():
            shutil.copytree(item, target / item.name, copy_function=shutil.copy)
        else:
            shutil.copy(item, target / item.name)
    return backup


def main(argv: list[str]) -> int:
    if len(argv) != 1 or not argv[0].isdigit():
        print("Usage: uv run poe catchup <lab-number 1-6>")
        return 2
    lab = int(argv[0])
    try:
        backup = catchup(lab)
    except (ValueError, FileNotFoundError) as exc:
        print(f"✗ {exc}")
        return 1
    print(f"✓ src/care_agent/ now matches the end of Lab {lab}.")
    print(f"  Your previous code is backed up in {backup.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
