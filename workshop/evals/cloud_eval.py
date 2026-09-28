"""`uv run poe cloud-eval` — PREVIEW: let Foundry judge your latest responses (cloud evaluation via APIM /foundry).

Local evals (Lab 5) run judges on your laptop. A cloud evaluation runs Foundry's built-in evaluators
(`builtin.intent_resolution`, `builtin.task_adherence`, `builtin.relevance`, `builtin.groundedness`,
`builtin.violence`) server-side over the same responses, so you can compare "local judge" vs "Foundry
judge" in the portal. Uses the OpenAI-compatible evals API from `project.get_openai_client()`.

Fallback (documented): if the cloud evaluation is not allowed or not available (403/404/preview API change),
we upload the local results instead (`poe upload-evals`).
"""

from __future__ import annotations

import argparse
import sys
import time
from typing import Any

from care_agent.config import ConfigError, get_settings
from care_agent.errors import explain
from evals.runs import latest_run, load_run


def builtin(name: str, evaluator: str, mapping: dict[str, str], deployment: str | None) -> dict[str, Any]:
    criterion: dict[str, Any] = {"type": "azure_ai_evaluator", "name": name, "evaluator_name": evaluator, "data_mapping": mapping}
    if deployment:
        criterion["initialization_parameters"] = {"deployment_name": deployment}
    return criterion


def testing_criteria(judge_model: str) -> list[dict[str, Any]]:
    qr = {"query": "{{item.query}}", "response": "{{item.response}}"}
    return [
        builtin("intent_resolution", "builtin.intent_resolution", qr, judge_model),
        builtin("task_adherence", "builtin.task_adherence", qr, judge_model),
        builtin("relevance", "builtin.relevance", qr, judge_model),
        builtin("groundedness", "builtin.groundedness", {**qr, "context": "{{item.context}}"}, judge_model),
        builtin("violence", "builtin.violence", qr, None),
    ]


def to_cloud_items(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items = []
    for row in rows:
        context = "\n\n".join(r.get("result", "") for r in row.get("tool_results") or [])[:8000]
        items.append({"item": {"case_id": row["id"], "query": row["query"], "response": row.get("response") or "",
                               "context": context or "(no tool context)"}})
    return items


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Cloud evaluation in Foundry via APIM /foundry (preview).")
    parser.add_argument("--run", help="local run ID whose responses to evaluate (default: latest)")
    parser.add_argument("--no-wait", action="store_true")
    parser.add_argument("--timeout", type=int, default=600)
    args = parser.parse_args(argv)
    try:
        settings = get_settings()
        run_dir = latest_run(run_id=args.run)
        summary, rows = load_run(run_dir)
    except (ConfigError, FileNotFoundError) as exc:
        print(f"✗ {exc}")
        return 1

    from care_agent.apim_auth import foundry_openai_client, foundry_project_client

    try:
        client = foundry_openai_client(foundry_project_client(settings), settings)
        evaluation = client.evals.create(
            name=f"care-coordination-cloud-{settings.participant_id}",
            data_source_config={
                "type": "custom",
                "item_schema": {
                    "type": "object",
                    "properties": {k: {"type": "string"} for k in ("case_id", "query", "response", "context")},
                    "required": ["query", "response"],
                },
                "include_sample_schema": False,
            },
            testing_criteria=testing_criteria(settings.judge_model),
        )
        run = client.evals.runs.create(
            eval_id=evaluation.id,
            name=f"cloud-{summary['run_id']}",
            metadata={"agent_version": str(summary.get("agent_version")), "local_run_id": summary["run_id"]},
            data_source={"type": "jsonl", "source": {"type": "file_content", "content": to_cloud_items(rows)}},
        )
    except Exception as exc:  # noqa: BLE001 - documented fallback
        print(f"[preview] Cloud evaluation unavailable: {explain(exc, component='/foundry evals')}")
        print("Fallback: uploading your local results instead (poe upload-evals).")
        from evals.upload_to_foundry import main as upload_main

        return upload_main(["--run", run_dir.name])

    print(f"✓ Cloud evaluation started: eval {evaluation.id}, run {run.id}")
    if args.no_wait:
        return 0
    deadline = time.time() + args.timeout
    status = getattr(run, "status", "queued")
    while status not in ("completed", "failed", "canceled") and time.time() < deadline:
        time.sleep(10)
        run = client.evals.runs.retrieve(run_id=run.id, eval_id=evaluation.id)
        status = run.status
        print(f"  status: {status}")
    counts = getattr(run, "result_counts", None)
    print(f"Final status: {status} · result counts: {counts}")
    if getattr(run, "report_url", None):
        print(f"Open in Foundry: {run.report_url}")
    return 0 if status == "completed" else 1


if __name__ == "__main__":
    sys.exit(main())
