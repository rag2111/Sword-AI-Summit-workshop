"""`uv run poe rollback` — flip the active pointer back to the previous agent version (instant, no redeploy)."""

from __future__ import annotations

import sys

from care_agent.versions import rollback


def main() -> int:
    try:
        previous, active = rollback()
    except ValueError as exc:
        print(f"✗ {exc}")
        return 1
    print(f"✓ Rolled back: {previous} → {active} (status of {previous}: rolled_back). Restart `uv run poe chat`.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
