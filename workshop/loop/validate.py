"""Lab 6 step 4 — re-run the evals on the candidate and compare with the baseline (the gate).

A candidate passes only if ALL of these hold:
  - its own rubric gate passes (including hard safety gates),
  - overall score >= baseline overall + loop.min_improvement,
  - the safety dimension does not regress.
Both runs use the same cases, so the comparison is apples to apples.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from care_agent.config import get_settings
from care_agent.versions import instructions_for, latest_candidate, load_registry, record_eval
from evals.run_evals import load_dataset, run_evaluation
from evals.runs import find_run_for_version, load_run
from evals.scoring import load_rubric


def compare(baseline: dict[str, Any], candidate: dict[str, Any], rubric: dict[str, Any]) -> dict[str, Any]:
    """Pure comparison of two run summaries (unit-tested)."""
    min_improvement = float((rubric.get("loop") or {}).get("min_improvement", 0.0))
    reasons = []
    base_overall, cand_overall = baseline.get("overall") or 0.0, candidate.get("overall") or 0.0
    if not candidate.get("gate", {}).get("passed"):
        reasons.append("candidate fails its rubric gate: " + "; ".join(candidate.get("gate", {}).get("reasons", [])))
    if cand_overall < base_overall + min_improvement:
        reasons.append(f"overall {cand_overall:.3f} does not beat baseline {base_overall:.3f} by {min_improvement}")
    base_safety = (baseline.get("dimensions") or {}).get("safety")
    cand_safety = (candidate.get("dimensions") or {}).get("safety")
    if base_safety is not None and cand_safety is not None and cand_safety < base_safety:
        reasons.append(f"safety regressed {base_safety:.3f} → {cand_safety:.3f}")
    deltas = {
        name: None if value is None or (baseline.get("dimensions") or {}).get(name) is None
        else round(value - baseline["dimensions"][name], 4)
        for name, value in (candidate.get("dimensions") or {}).items()
    }
    return {
        "passed": not reasons,
        "reasons": reasons,
        "baseline_run": baseline.get("run_id"),
        "candidate_run": candidate.get("run_id"),
        "baseline_overall": base_overall,
        "candidate_overall": cand_overall,
        "delta_overall": round(cand_overall - base_overall, 4),
        "dimension_deltas": deltas,
    }


def validate(version: str, *, ids: list[str] | None = None, use_judge: bool = True) -> tuple[dict[str, Any], Path]:
    settings = get_settings()
    rubric = load_rubric()
    registry = load_registry()
    cases = load_dataset(ids=ids)
    baseline_version = registry["versions"][version]["parent"] or registry["active"]

    baseline_dir = None if ids else find_run_for_version(baseline_version)
    if baseline_dir is None or load_run(baseline_dir)[0].get("cases") != len(cases):
        print(f"Running baseline {baseline_version} on the same {len(cases)} cases…")
        baseline_dir, baseline, _ = asyncio.run(
            run_evaluation(settings, cases=cases, rubric=rubric, version=baseline_version,
                           instructions=instructions_for(baseline_version, registry=registry), use_judge=use_judge)
        )
    else:
        baseline = load_run(baseline_dir)[0]
    print(f"Running candidate {version} on {len(cases)} cases…")
    candidate_dir, candidate, _ = asyncio.run(
        run_evaluation(settings, cases=cases, rubric=rubric, version=version,
                       instructions=instructions_for(version, registry=registry), use_judge=use_judge)
    )
    comparison = compare(baseline, candidate, rubric)
    (candidate_dir / "comparison.json").write_text(json.dumps(comparison, indent=2) + "\n", encoding="utf-8")
    record_eval(version, eval_run_id=candidate["run_id"], overall_score=candidate.get("overall"),
                trace_ids=candidate.get("trace_ids"), passed_gate=comparison["passed"])
    return comparison, candidate_dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a candidate agent version against the baseline.")
    parser.add_argument("--version", help="candidate version (default: latest candidate)")
    parser.add_argument("--ids", help="comma-separated case IDs (baseline is re-run on the same cases)")
    parser.add_argument("--no-judge", action="store_true")
    args = parser.parse_args(argv)
    version = args.version or latest_candidate(load_registry(), statuses=("candidate",))
    if not version:
        print("No candidate to validate. Run `uv run poe loop` (or loop/propose.py) first.")
        return 1
    comparison, _ = validate(version, ids=args.ids.split(",") if args.ids else None, use_judge=not args.no_judge)
    print(json.dumps(comparison, indent=2))
    return 0 if comparison["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
