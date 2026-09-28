"""Helpers to find and load local evaluation runs in evals/out/<run-id>/."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

OUT_DIR = Path(__file__).with_name("out")


def list_runs(out_root: Path = OUT_DIR, *, include_redteam: bool = False) -> list[Path]:
    runs = [p for p in out_root.glob("*") if (p / "summary.json").exists()]
    if not include_redteam:
        runs = [p for p in runs if "redteam" not in p.name]
    return sorted(runs, key=lambda p: p.name)


def latest_run(out_root: Path = OUT_DIR, run_id: str | None = None, *, include_redteam: bool = False) -> Path:
    if run_id:
        path = out_root / run_id
        if not (path / "summary.json").exists():
            raise FileNotFoundError(f"No eval run {run_id!r} in {out_root}")
        return path
    runs = list_runs(out_root, include_redteam=include_redteam)
    if not runs:
        raise FileNotFoundError(f"No eval runs in {out_root}. Run `uv run poe evals` first.")
    return runs[-1]


def load_run(run_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    rows = [json.loads(line) for line in (run_dir / "results.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    return summary, rows


def find_run_for_version(version: str, out_root: Path = OUT_DIR) -> Path | None:
    for run_dir in reversed(list_runs(out_root)):
        summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
        if summary.get("agent_version") == version:
            return run_dir
    return None
