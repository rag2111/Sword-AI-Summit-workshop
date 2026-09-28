"""`uv run poe loop` — Lab 6: close the loop, end to end.

    pull failures → cluster & rank → propose change → re-run evals → promote if better

Options
  --quick        validate on the failing cases + all critical cases only (faster; baseline re-run on the same set)
  --limit N      use only the first N golden cases throughout the loop; never auto-promote
  --offline      no LLM judge/proposer (deterministic metrics, template proposal) — for rehearsals
  --no-promote   stop after validation; promote later with `uv run poe promote`
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from care_agent.config import ConfigError, get_settings
from care_agent.errors import explain
from care_agent.versions import load_registry, promote
from evals.run_evals import load_dataset, resolve_version, run_evaluation
from evals.runs import find_run_for_version, load_run
from evals.scoring import load_rubric
from loop.cluster import cluster_failures
from loop.propose import propose
from loop.pull_failures import pull, write_failures
from loop.validate import validate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Lab 6 improvement loop.")
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--limit", type=int, metavar="N",
                        help="use the first N golden cases (overrides --quick); disables automatic promotion")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--no-promote", action="store_true")
    parser.add_argument(
        "--judge-delay",
        type=float,
        default=5.0,
        metavar="SECONDS",
        help="minimum delay between judge requests (default: 5, to avoid participant TPM throttling)",
    )
    args = parser.parse_args(argv)
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be a positive integer")

    from rich.console import Console
    from rich.syntax import Syntax

    console = Console()
    try:
        settings = get_settings()
        rubric = load_rubric()
        active = load_registry()["active"]
        limited_cases = load_dataset(limit=args.limit) if args.limit is not None else None
        limited_ids = [case["id"] for case in limited_cases] if limited_cases is not None else None
        if limited_ids is not None:
            if not limited_ids:
                raise ValueError("No golden cases available for --limit.")
            console.print(f"Limited run: {', '.join(limited_ids)}. Automatic promotion disabled.")
        baseline_dir = find_run_for_version(active)
        if baseline_dir is not None and limited_ids is not None:
            _, baseline_rows = load_run(baseline_dir)
            if not set(limited_ids).issubset({row["id"] for row in baseline_rows}):
                baseline_dir = None
        if baseline_dir is None:
            console.rule(f"0 · No eval run covering the selected cases for {active} — running the baseline")
            version, instructions = resolve_version(None)
            baseline_dir, _, _ = asyncio.run(
                run_evaluation(settings, cases=limited_cases if limited_cases is not None else load_dataset(),
                               rubric=rubric, version=version, instructions=instructions,
                               use_judge=not args.offline, judge_delay_seconds=args.judge_delay)
            )

        console.rule("1 · Pull failures")
        threshold = float(rubric.get("loop", {}).get("failure_threshold", 0.7))
        run_dir, summary, failures = pull(baseline_dir.name, threshold)
        if limited_ids is not None:
            failures = [failure for failure in failures if failure["id"] in limited_ids]
        path = write_failures(failures)
        console.print(f"{len(failures)} failing rows in {run_dir.name} (overall {summary.get('overall')}) → {path}")
        if not failures:
            scope = "selected case" if limited_ids is not None else "case"
            console.print(f"[green]Nothing to fix: every {scope} passed. Try `uv run poe redteam` to find new failures.[/]")
            return 0

        console.rule("2 · Cluster & rank failure modes")
        clusters = cluster_failures(failures, rubric=rubric, settings=settings, use_judge=not args.offline)
        for rank, cluster in enumerate(clusters, start=1):
            console.print(f"{rank}. [bold]{cluster['mode']}[/] impact={cluster['impact']} cases={', '.join(cluster['case_ids'])}")
        top = clusters[0]

        console.rule(f"3 · Propose a change for '{top['mode']}'")
        result = propose(top, settings=settings, offline=args.offline)
        version = result["entry"]["version"]
        console.print(f"Candidate [bold]{version}[/] ({result['proposal']['method']}): {result['proposal']['rationale']}")
        console.print(Syntax(result["diff"] or "(no diff)", "diff", word_wrap=True))

        console.rule(f"4 · Validate {version} against {result['entry']['parent']}")
        ids = limited_ids
        if args.quick and limited_ids is None:
            critical = [c["id"] for c in load_dataset() if c["severity"] == "critical"]
            ids = sorted(set(top["case_ids"]) | set(critical) | {f["id"] for f in failures})
        comparison, candidate_dir = validate(
            version,
            ids=ids,
            use_judge=not args.offline,
            judge_delay_seconds=args.judge_delay,
        )
        colour = "green" if comparison["passed"] else "red"
        console.print(f"[{colour}]overall {comparison['baseline_overall']} → {comparison['candidate_overall']} "
                      f"(Δ {comparison['delta_overall']:+})[/]  {'; '.join(comparison['reasons'])}")

        console.rule("5 · Promote")
        if not comparison["passed"]:
            console.print(f"[yellow]{version} rejected; active version stays {result['entry']['parent']}.[/]")
            return 0
        if limited_ids is not None:
            console.print(
                f"{version} passed only the limited comparison; active version stays {result['entry']['parent']}. "
                f"Run `uv run python -m loop.validate --version {version}` on the full set before promotion."
            )
            return 0
        if args.no_promote:
            console.print(f"{version} validated. Promote with `uv run poe promote --version {version}`.")
            return 0
        entry = promote(version)
        console.print(f"[bold green]✓ {version} promoted[/] (eval run {entry['eval_run_id']}, "
                      f"{len(entry['trace_ids'])} trace IDs). Roll back any time: `uv run poe rollback`.")
        return 0
    except ConfigError as exc:
        console.print(f"✗ {exc}")
        return 1
    except Exception as exc:  # noqa: BLE001
        console.print(f"✗ {explain(exc, component='loop')}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
