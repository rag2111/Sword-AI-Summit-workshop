"""Weighted-rubric math (pure Python, unit-tested). See evals/rubric.yaml for the conventions."""

from __future__ import annotations

from pathlib import Path
from statistics import mean
from typing import Any

RUBRIC_PATH = Path(__file__).with_name("rubric.yaml")
TOLERANCE = 1e-6


def load_rubric(path: Path | str = RUBRIC_PATH) -> dict[str, Any]:
    import yaml

    rubric = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    problems = validate_rubric(rubric)
    if problems:
        raise ValueError("Invalid rubric: " + "; ".join(problems))
    return rubric


def validate_rubric(rubric: dict[str, Any]) -> list[str]:
    problems = []
    dims = rubric.get("dimensions") or {}
    total = sum(float(d.get("weight", 0)) for d in dims.values())
    if abs(total - 1.0) > TOLERANCE:
        problems.append(f"dimension weights sum to {total:.3f}, expected 1.0")
    for name, dim in dims.items():
        if dim.get("level", "row") == "row":
            metric_total = sum(float(m.get("weight", 0)) for m in (dim.get("metrics") or {}).values())
            if abs(metric_total - 1.0) > TOLERANCE:
                problems.append(f"metric weights in {name} sum to {metric_total:.3f}, expected 1.0")
    return problems


def normalize_judge(value: float, low: float = 1.0, high: float = 5.0) -> float:
    return max(0.0, min(1.0, (float(value) - low) / (high - low)))


def normalize_evaluator_output(output: dict[str, Any], key: str) -> float | None:
    """Map an azure-ai-evaluation result dict to 0..1, whatever scale that evaluator version uses."""
    if not isinstance(output, dict):
        return None
    value = output.get(key)
    result = str(output.get(f"{key}_result", "")).lower()
    threshold = output.get(f"{key}_threshold")
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        if isinstance(threshold, (int, float)) and threshold > 1:
            return normalize_judge(value)
        if value > 1:
            return normalize_judge(value)
        if value == 1 and result == "fail":
            return 0.0
        return max(0.0, min(1.0, float(value)))
    if result in ("pass", "fail"):
        return 1.0 if result == "pass" else 0.0
    return None


def applies(applies_to: str, case: dict[str, Any]) -> bool:
    if applies_to in (None, "", "all"):
        return True
    return bool(case.get(applies_to))


def row_dimension_scores(metrics: dict[str, float | None], case: dict[str, Any], rubric: dict[str, Any]) -> dict[str, float | None]:
    """Weighted average per row-level dimension over applicable, available metrics (re-normalised)."""
    scores: dict[str, float | None] = {}
    for dim_name, dim in rubric["dimensions"].items():
        if dim.get("level", "row") != "row":
            continue
        weighted, weights = 0.0, 0.0
        for metric_name, metric in dim["metrics"].items():
            value = metrics.get(metric_name)
            if value is None or not applies(metric.get("applies_to", "all"), case):
                continue
            weighted += float(metric["weight"]) * value
            weights += float(metric["weight"])
        scores[dim_name] = round(weighted / weights, 4) if weights else None
    return scores


def weighted_mean(scores: dict[str, float | None], rubric: dict[str, Any]) -> float | None:
    weighted, weights = 0.0, 0.0
    for dim_name, score in scores.items():
        if score is None:
            continue
        weight = float(rubric["dimensions"][dim_name]["weight"])
        weighted += weight * score
        weights += weight
    return round(weighted / weights, 4) if weights else None


def row_score(dimension_scores: dict[str, float | None], rubric: dict[str, Any]) -> float | None:
    return weighted_mean(dimension_scores, rubric)


def failed_metrics(metrics: dict[str, float | None], case: dict[str, Any], rubric: dict[str, Any]) -> list[str]:
    failures = []
    for dim in rubric["dimensions"].values():
        for metric_name, metric in (dim.get("metrics") or {}).items():
            value = metrics.get(metric_name)
            if value is not None and applies(metric.get("applies_to", "all"), case) and value < float(metric["pass_at"]):
                failures.append(metric_name)
    return failures


def linear_budget_score(actual: float, target: float) -> float:
    """1.0 at/below target, linear down to 0.0 at 2x target."""
    if target <= 0:
        return 1.0
    if actual <= target:
        return 1.0
    return round(max(0.0, 1.0 - (actual - target) / target), 4)


def cost_dimension(cost_per_task_eur: float, rubric: dict[str, Any]) -> float:
    return linear_budget_score(cost_per_task_eur, float(rubric["dimensions"]["cost"]["budget_eur_per_task"]))


def latency_dimension(p50_ms: float, p95_ms: float, rubric: dict[str, Any]) -> float:
    dim = rubric["dimensions"]["latency"]
    return round(
        (linear_budget_score(p50_ms, float(dim["p50_target_ms"])) + linear_budget_score(p95_ms, float(dim["p95_target_ms"])))
        / 2,
        4,
    )


def aggregate(
    rows: list[dict[str, Any]],
    rubric: dict[str, Any],
    *,
    cost_per_task_eur: float | None,
    p50_ms: float | None,
    p95_ms: float | None,
) -> dict[str, Any]:
    """Run-level dimension scores, overall weighted score and the pass gate."""
    dims: dict[str, float | None] = {}
    for dim_name, dim in rubric["dimensions"].items():
        if dim.get("level", "row") == "row":
            values = [r["dimension_scores"].get(dim_name) for r in rows if r["dimension_scores"].get(dim_name) is not None]
            dims[dim_name] = round(mean(values), 4) if values else None
    if "cost" in rubric["dimensions"]:
        dims["cost"] = cost_dimension(cost_per_task_eur, rubric) if cost_per_task_eur is not None else None
    if "latency" in rubric["dimensions"]:
        dims["latency"] = latency_dimension(p50_ms, p95_ms, rubric) if p50_ms is not None and p95_ms is not None else None
    overall = weighted_mean(dims, rubric)
    return {"dimensions": dims, "overall": overall, "gate": evaluate_gate(dims, overall, rows, rubric)}


def evaluate_gate(dims: dict[str, float | None], overall: float | None, rows: list[dict[str, Any]], rubric: dict[str, Any]) -> dict[str, Any]:
    gate = rubric.get("gate") or {}
    reasons = []
    if overall is None or overall < float(gate.get("overall_min", 0)):
        reasons.append(f"overall {overall} < {gate.get('overall_min')}")
    for dim_name, minimum in (gate.get("dimension_min") or {}).items():
        value = dims.get(dim_name)
        if value is not None and value < float(minimum):
            reasons.append(f"{dim_name} {value} < {minimum}")
    if gate.get("hard_gate", True):
        hard = {m for d in rubric["dimensions"].values() for m, spec in (d.get("metrics") or {}).items() if spec.get("hard_gate")}
        for row in rows:
            broken = sorted(hard.intersection(row.get("failures", [])))
            if broken:
                reasons.append(f"{row['id']} failed hard gate: {', '.join(broken)}")
    return {"passed": not reasons, "reasons": reasons}
