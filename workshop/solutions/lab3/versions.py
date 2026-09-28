"""Agent version registry: agent_versions/registry.json (Lab 6).

Every agent version records its lineage so you can answer "what changed, who proved it was better,
and which traces justify it?":

    version, parent, instructions_hash, instructions_file, eval_run_id, trace_ids, created_at, status

`status` is one of: active | candidate | validated | rejected | retired | rolled_back.
The registry is created on first use with the built-in baseline as v1.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .config import WORKSHOP_ROOT
from .instructions import BASE_INSTRUCTIONS, instructions_hash

SCHEMA = 1


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def registry_dir(root: Path | None = None) -> Path:
    if root is not None:
        return Path(root)
    return Path(os.environ.get("AGENT_VERSIONS_DIR") or WORKSHOP_ROOT / "agent_versions")


def registry_path(root: Path | None = None) -> Path:
    return registry_dir(root) / "registry.json"


def _baseline_registry() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "active": "v1",
        "versions": {
            "v1": {
                "version": "v1",
                "parent": None,
                "instructions_hash": instructions_hash(BASE_INSTRUCTIONS),
                "instructions_file": None,  # None = built-in BASE_INSTRUCTIONS
                "eval_run_id": None,
                "overall_score": None,
                "trace_ids": [],
                "created_at": _now(),
                "status": "active",
                "notes": "Built-in baseline instructions (care_agent/instructions.py).",
            }
        },
        "history": [{"at": _now(), "action": "init", "from": None, "to": "v1"}],
    }


def load_registry(root: Path | None = None) -> dict[str, Any]:
    path = registry_path(root)
    if not path.exists():
        return _baseline_registry()
    return json.loads(path.read_text(encoding="utf-8"))


def save_registry(registry: dict[str, Any], root: Path | None = None) -> Path:
    path = registry_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")
    return path


def next_version(registry: dict[str, Any]) -> str:
    numbers = [int(v[1:]) for v in registry["versions"] if v.startswith("v") and v[1:].isdigit()]
    return f"v{max(numbers, default=0) + 1}"


def instructions_for(version: str, root: Path | None = None, registry: dict[str, Any] | None = None) -> str:
    registry = registry or load_registry(root)
    entry = registry["versions"].get(version)
    if entry is None:
        raise KeyError(f"Unknown agent version {version!r}. Known: {', '.join(registry['versions'])}")
    if not entry.get("instructions_file"):
        return BASE_INSTRUCTIONS
    return (registry_dir(root) / entry["instructions_file"]).read_text(encoding="utf-8")


def active_instructions(root: Path | None = None) -> tuple[str, str]:
    registry = load_registry(root)
    version = registry["active"]
    return version, instructions_for(version, root, registry)


def register_candidate(
    instructions: str,
    *,
    parent: str | None = None,
    notes: str = "",
    diff: str | None = None,
    root: Path | None = None,
) -> dict[str, Any]:
    """Store a candidate's instructions under candidates/<version>/ and add it to the registry."""
    registry = load_registry(root)
    version = next_version(registry)
    folder = registry_dir(root) / "candidates" / version
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "instructions.md").write_text(instructions, encoding="utf-8")
    if diff:
        (folder / "change.diff").write_text(diff, encoding="utf-8")
    entry = {
        "version": version,
        "parent": parent or registry["active"],
        "instructions_hash": instructions_hash(instructions),
        "instructions_file": f"candidates/{version}/instructions.md",
        "eval_run_id": None,
        "overall_score": None,
        "trace_ids": [],
        "created_at": _now(),
        "status": "candidate",
        "notes": notes,
    }
    registry["versions"][version] = entry
    save_registry(registry, root)
    return entry


def record_eval(
    version: str,
    *,
    eval_run_id: str,
    overall_score: float | None,
    trace_ids: list[str] | None = None,
    passed_gate: bool | None = None,
    root: Path | None = None,
) -> dict[str, Any]:
    registry = load_registry(root)
    entry = registry["versions"][version]
    entry["eval_run_id"] = eval_run_id
    entry["overall_score"] = overall_score
    entry["trace_ids"] = list(trace_ids or [])[:50]
    if passed_gate is not None and entry["status"] in ("candidate", "validated", "rejected"):
        entry["status"] = "validated" if passed_gate else "rejected"
    save_registry(registry, root)
    return entry


def promote(
    version: str,
    *,
    eval_run_id: str | None = None,
    trace_ids: list[str] | None = None,
    require_validation: bool = True,
    root: Path | None = None,
) -> dict[str, Any]:
    """Make `version` active. By default only validated candidates can be promoted."""
    registry = load_registry(root)
    entry = registry["versions"].get(version)
    if entry is None:
        raise KeyError(f"Unknown agent version {version!r}")
    if require_validation and entry["status"] not in ("validated", "retired", "rolled_back"):
        raise ValueError(
            f"{version} has status {entry['status']!r}; run `uv run poe loop` (validate) first "
            "or pass --force."
        )
    previous = registry["active"]
    if previous == version:
        return entry
    registry["versions"][previous]["status"] = "retired"
    entry["status"] = "active"
    if eval_run_id:
        entry["eval_run_id"] = eval_run_id
    if trace_ids:
        entry["trace_ids"] = list(trace_ids)[:50]
    registry["active"] = version
    registry["history"].append({"at": _now(), "action": "promote", "from": previous, "to": version})
    save_registry(registry, root)
    return entry


def rollback(root: Path | None = None) -> tuple[str, str]:
    """Flip the active pointer back to the version that was active before the last promotion."""
    registry = load_registry(root)
    current = registry["active"]
    target = None
    for event in reversed(registry["history"]):
        if event["action"] == "promote" and event["to"] == current:
            target = event["from"]
            break
    target = target or registry["versions"][current].get("parent")
    if not target:
        raise ValueError(f"{current} has no previous version to roll back to.")
    registry["versions"][current]["status"] = "rolled_back"
    registry["versions"][target]["status"] = "active"
    registry["active"] = target
    registry["history"].append({"at": _now(), "action": "rollback", "from": current, "to": target})
    save_registry(registry, root)
    return current, target


def latest_candidate(registry: dict[str, Any], statuses: tuple[str, ...] = ("validated",)) -> str | None:
    matches = [v for v, e in registry["versions"].items() if e["status"] in statuses]
    return sorted(matches, key=lambda v: int(v[1:]) if v[1:].isdigit() else 0)[-1] if matches else None
