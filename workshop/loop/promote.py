"""`uv run poe promote` — make a validated candidate the active agent version, with lineage.

The registry entry keeps: version, parent, instructions_hash, eval_run_id, trace_ids, timestamp, status.
The agent reads the active version at startup (care_agent.instructions.load_active_instructions, Lab 6).
`uv run poe promote-force --version vN` is the demo-only alias for `promote --version vN --force`.
"""

from __future__ import annotations

import argparse
import json
import sys

from care_agent.versions import latest_candidate, load_registry, promote


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Promote a candidate agent version.")
    parser.add_argument("--version", help="version to promote (default: latest validated candidate)")
    parser.add_argument("--force", action="store_true", help="promote even if not validated (demo only!)")
    args = parser.parse_args(argv)
    registry = load_registry()
    version = args.version or latest_candidate(registry, statuses=("validated",) if not args.force else ("validated", "candidate"))
    if not version:
        print("No validated candidate. Run `uv run poe loop` first (or use --version vN --force for a demo).")
        return 1
    if args.force:
        print(f"WARNING: forced promotion of {version} bypasses validation (demo only). "
              "It does not run evaluations or prove that safety gates passed.")
    try:
        entry = promote(version, require_validation=not args.force)
    except (KeyError, ValueError) as exc:
        print(f"✗ {exc}")
        return 1
    print(f"✓ {version} is now active (parent {entry['parent']}, eval run {entry['eval_run_id']}).")
    print(json.dumps({k: entry[k] for k in ("version", "parent", "instructions_hash", "eval_run_id", "overall_score", "status")}, indent=2))
    print(f"  {len(entry.get('trace_ids') or [])} trace IDs recorded as evidence. Restart `uv run poe chat` to use it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
