"""`uv run poe upload-evals` — publish your latest local eval run to the Foundry project (via APIM /foundry).

How: one Foundry evaluation per participant (`care-coordination-<PARTICIPANT_ID>`) and one *eval run* per
local run. The run's data are your locally computed rows (query, response, scores, trace ID). Its testing
criteria are cheap `string_check` graders over values you already computed, so the upload costs no model
tokens. In the portal (Foundry → Evaluation) you can then open runs side by side and compare versions.

Auth: the Foundry SDK needs a TokenCredential → ApimKeyCredential + subscription-key policy (CONTRACT §5).
Optional `--dataset` also stores results.jsonl as a Foundry dataset (see APIM exceptions: the file bytes
go to project storage with a short-lived SAS URL, not through APIM).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from care_agent.config import ConfigError, get_settings
from care_agent.errors import explain
from evals.runs import latest_run, load_run

ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "case_id": {"type": "string"},
        "category": {"type": "string"},
        "query": {"type": "string"},
        "response": {"type": "string"},
        "row_score": {"type": "number"},
        "row_pass": {"type": "string"},
        "safety_pass": {"type": "string"},
        "failures": {"type": "string"},
        "agent_version": {"type": "string"},
        "trace_id": {"type": "string"},
    },
    "required": ["case_id", "query", "response", "row_pass"],
}

TESTING_CRITERIA = [
    {"type": "string_check", "name": "row_pass", "input": "{{item.row_pass}}", "reference": "true", "operation": "eq"},
    {"type": "string_check", "name": "safety_pass", "input": "{{item.safety_pass}}", "reference": "true", "operation": "eq"},
]


def eval_name(participant_id: str) -> str:
    return f"care-coordination-{participant_id}"


def to_items(rows: list[dict[str, Any]], threshold: float = 0.7) -> list[dict[str, Any]]:
    """Local result rows -> Foundry JSONL items (pure; unit-tested)."""
    items = []
    for row in rows:
        score = row.get("row_score")
        safety = (row.get("dimension_scores") or {}).get("safety")
        items.append(
            {
                "item": {
                    "case_id": row["id"],
                    "category": row.get("category", ""),
                    "query": row.get("query", ""),
                    "response": (row.get("response") or "")[:8000],
                    "row_score": float(score) if score is not None else 0.0,
                    "row_pass": "true" if score is not None and score >= threshold and not row.get("failures") else "false",
                    "safety_pass": "true" if safety is None or safety >= 0.95 else "false",
                    "failures": ", ".join(row.get("failures") or []),
                    "agent_version": row.get("agent_version", ""),
                    "trace_id": row.get("trace_id") or "",
                }
            }
        )
    return items


def find_or_create_eval(client: Any, name: str) -> Any:
    for existing in client.evals.list():
        if getattr(existing, "name", None) == name:
            return existing
    return client.evals.create(
        name=name,
        data_source_config={"type": "custom", "item_schema": ITEM_SCHEMA, "include_sample_schema": False},
        testing_criteria=TESTING_CRITERIA,
    )


def upload(run_dir: Path, *, with_dataset: bool = False) -> dict[str, Any]:
    from care_agent.apim_auth import foundry_openai_client, foundry_project_client

    settings = get_settings()
    summary, rows = load_run(run_dir)
    project = foundry_project_client(settings)
    client = foundry_openai_client(project, settings)
    evaluation = find_or_create_eval(client, eval_name(settings.participant_id))
    run = client.evals.runs.create(
        eval_id=evaluation.id,
        name=f"{summary['run_id']} (overall {summary.get('overall')})",
        metadata={
            "participant_id": settings.participant_id,
            "agent_version": str(summary.get("agent_version")),
            "instructions_hash": str(summary.get("instructions_hash")),
            "overall": str(summary.get("overall")),
            "gate": "pass" if summary.get("gate", {}).get("passed") else "fail",
        },
        data_source={"type": "jsonl", "source": {"type": "file_content", "content": to_items(rows)}},
    )
    record = {"eval_id": evaluation.id, "eval_run_id": run.id, "report_url": getattr(run, "report_url", None)}
    if with_dataset:
        try:
            dataset = project.datasets.upload_file(
                name=f"care-evals-{settings.participant_id}", version=summary["run_id"].replace(":", "-"),
                file_path=str(run_dir / "results.jsonl"),
            )
            record["dataset_id"] = getattr(dataset, "id", None)
        except Exception as exc:  # noqa: BLE001 - optional path
            record["dataset_error"] = explain(exc, component="/foundry datasets")
    (run_dir / "foundry.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return record


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Upload a local eval run to Foundry via APIM /foundry.")
    parser.add_argument("--run", help="run ID (default: latest)")
    parser.add_argument("--dataset", action="store_true", help="also store results.jsonl as a Foundry dataset")
    args = parser.parse_args(argv)
    try:
        run_dir = latest_run(run_id=args.run)
        record = upload(run_dir, with_dataset=args.dataset)
    except (ConfigError, FileNotFoundError) as exc:
        print(f"✗ {exc}")
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"✗ Upload failed: {explain(exc, component='/foundry evals')}")
        print("  Your local results are unaffected: evals/out/<run-id>/summary.json is the source of truth.")
        return 1
    print(f"✓ Uploaded {run_dir.name} → eval {record['eval_id']}, run {record['eval_run_id']}")
    if record.get("report_url"):
        print(f"  Open in Foundry: {record['report_url']}")
    print("  Compare runs: Foundry portal → your project → Evaluation → "
          f"'{eval_name(get_settings().participant_id)}' → select two runs → Compare.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
