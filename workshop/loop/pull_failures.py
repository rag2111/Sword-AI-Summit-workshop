"""Lab 6 step 1 — pull low-scoring results (and their traces) from the latest eval run.

Source of truth: evals/out/<run-id>/results.jsonl (scores, judge reasons, trace IDs).
Trace details: the local span file (.care_agent/spans.jsonl) — which tools ran, how long they took.

Why not query Application Insights directly? Reading App Insights needs Azure RBAC and a query API
that the workshop gateway does not proxy (participants have only an APIM key). The trace IDs we keep
let anyone with Reader access open the full end-to-end trace; see docs/apim-exceptions.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from evals.runs import latest_run, load_run

LOOP_OUT = Path(__file__).with_name("out")


def _reasons(row: dict[str, Any]) -> dict[str, str]:
    reasons = {}
    for metric in row.get("failures") or []:
        detail = (row.get("raw") or {}).get(metric) or {}
        if isinstance(detail, dict):
            text = next((str(v) for k, v in detail.items() if k.endswith("reason") or k == "reason" or k == "error"), "")
        else:
            text = str(detail)
        reasons[metric] = text[:300]
    if row.get("error"):
        reasons["agent_error"] = str(row["error"])[:300]
    return reasons


def trace_summary(trace_id: str | None) -> dict[str, Any] | None:
    if not trace_id:
        return None
    try:
        from care_agent.telemetry import load_trace_spans
    except ImportError:
        return None
    spans = load_trace_spans(trace_id)
    if not spans:
        return None
    return {
        "spans": len(spans),
        "tools": [s["attributes"].get("gen_ai.tool.name") or s["name"] for s in spans if s["name"].startswith("execute_tool")],
        "slowest": max(spans, key=lambda s: s["duration_ms"])["name"],
    }


def select_failures(rows: list[dict[str, Any]], threshold: float) -> list[dict[str, Any]]:
    """Rows below the threshold or with any failed metric (pure; unit-tested)."""
    selected = []
    for row in rows:
        score = row.get("row_score")
        if score is None or score < threshold or row.get("failures"):
            selected.append(
                {
                    "id": row["id"],
                    "category": row.get("category"),
                    "severity": row.get("severity", "medium"),
                    "query": row.get("query"),
                    "response": (row.get("response") or "")[:1500],
                    "row_score": score,
                    "failures": list(row.get("failures") or []),
                    "reasons": _reasons(row),
                    "trace_id": row.get("trace_id"),
                    "agent_version": row.get("agent_version"),
                }
            )
    return sorted(selected, key=lambda r: (r["row_score"] is not None, r["row_score"] or 0))


def pull(run_id: str | None = None, threshold: float = 0.7) -> tuple[Path, dict[str, Any], list[dict[str, Any]]]:
    run_dir = latest_run(run_id=run_id)
    summary, rows = load_run(run_dir)
    failures = select_failures(rows, threshold)
    for failure in failures:
        failure["trace"] = trace_summary(failure["trace_id"])
    return run_dir, summary, failures


def write_failures(failures: list[dict[str, Any]], out_dir: Path | None = None) -> Path:
    out_dir = out_dir or LOOP_OUT / f"{datetime.now():%Y%m%d-%H%M%S}"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "failures.jsonl"
    path.write_text("".join(json.dumps(f, default=str) + "\n" for f in failures), encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pull low-scoring rows from the latest eval run.")
    parser.add_argument("--run")
    parser.add_argument("--threshold", type=float, default=0.7)
    parser.add_argument("--appinsights", action="store_true", help="explain why App Insights is not queried")
    args = parser.parse_args(argv)
    if args.appinsights:
        print("App Insights is not queried: it needs Azure RBAC and a query path that APIM does not expose to "
              "participants. Using eval outputs + trace IDs instead (docs/apim-exceptions).")
    try:
        run_dir, summary, failures = pull(args.run, args.threshold)
    except FileNotFoundError as exc:
        print(f"✗ {exc}")
        return 1
    path = write_failures(failures)
    print(f"{len(failures)} failing rows from {run_dir.name} (agent {summary.get('agent_version')}) → {path}")
    for failure in failures:
        print(f"  {failure['id']:<5} score={failure['row_score']} failures={','.join(failure['failures'])} trace={failure['trace_id']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
