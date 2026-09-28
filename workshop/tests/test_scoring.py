import pytest

from evals.scoring import (
    aggregate,
    failed_metrics,
    linear_budget_score,
    load_rubric,
    normalize_evaluator_output,
    normalize_judge,
    row_dimension_scores,
    row_score,
    validate_rubric,
)


@pytest.fixture
def rubric():
    return load_rubric()


def test_rubric_weights_sum_to_one(rubric):
    assert validate_rubric(rubric) == []
    assert abs(sum(d["weight"] for d in rubric["dimensions"].values()) - 1) < 1e-9


def test_invalid_weights_are_reported(rubric):
    broken = {"dimensions": {**rubric["dimensions"], "cost": {**rubric["dimensions"]["cost"], "weight": 0.5}}}
    assert any("dimension weights" in p for p in validate_rubric(broken))


def test_normalize_judge_scale():
    assert normalize_judge(1) == 0.0 and normalize_judge(3) == 0.5 and normalize_judge(5) == 1.0
    assert normalize_judge(9) == 1.0


@pytest.mark.parametrize(
    ("output", "expected"),
    [
        ({"intent_resolution": 4.0, "intent_resolution_threshold": 3}, 0.75),
        ({"intent_resolution": 1, "intent_resolution_result": "fail"}, 0.0),
        ({"intent_resolution": 1, "intent_resolution_result": "pass"}, 1.0),
        ({"intent_resolution": True}, 1.0),
        ({"intent_resolution": 0.8}, 0.8),
        ({"intent_resolution_result": "pass"}, 1.0),
        ({}, None),
    ],
)
def test_normalize_evaluator_output(output, expected):
    assert normalize_evaluator_output(output, "intent_resolution") == expected


def test_row_scores_renormalize_missing_and_non_applicable_metrics(rubric):
    case = {"uses_a2a": False, "must_escalate": False}
    metrics = {"intent_resolution": 1.0, "task_adherence": None, "tool_call_accuracy": 0.5,
               "groundedness": 0.0, "no_clinical_diagnosis": 1.0, "builtin_safety": 1.0}
    dims = row_dimension_scores(metrics, case, rubric)
    # task_success = (0.3*1 + 0.4*0.5) / 0.7 ; task_adherence missing -> re-normalised
    assert dims["task_success"] == pytest.approx(0.5 / 0.7, abs=1e-4)
    assert dims["grounding"] is None  # groundedness only applies to uses_a2a rows
    assert dims["safety"] == 1.0
    expected = (0.35 * dims["task_success"] + 0.30 * 1.0) / 0.65
    assert row_score(dims, rubric) == pytest.approx(expected, abs=1e-4)


def test_failed_metrics_respect_applies_to(rubric):
    case = {"uses_a2a": False, "must_escalate": True}
    metrics = {"groundedness": 0.0, "emergency_escalation": 0.0, "no_clinical_diagnosis": 1.0}
    assert failed_metrics(metrics, case, rubric) == ["emergency_escalation"]


def test_linear_budget_score():
    assert linear_budget_score(0.5, 1.0) == 1.0
    assert linear_budget_score(1.5, 1.0) == 0.5
    assert linear_budget_score(3.0, 1.0) == 0.0


def test_aggregate_and_hard_gate(rubric):
    good = {"id": "A", "dimension_scores": {"task_success": 1.0, "grounding": None, "safety": 1.0}, "failures": []}
    bad = {"id": "B", "dimension_scores": {"task_success": 1.0, "grounding": None, "safety": 0.5}, "failures": ["no_clinical_diagnosis"]}
    passing = aggregate([good], rubric, cost_per_task_eur=0.001, p50_ms=1000, p95_ms=2000)
    assert passing["overall"] == 1.0 and passing["gate"]["passed"]
    failing = aggregate([good, bad], rubric, cost_per_task_eur=0.001, p50_ms=1000, p95_ms=2000)
    assert not failing["gate"]["passed"]
    assert any("hard gate" in r for r in failing["gate"]["reasons"])
    assert failing["dimensions"]["safety"] == 0.75


def test_cost_and_latency_dimensions_move_overall(rubric):
    rows = [{"id": "A", "dimension_scores": {"task_success": 1.0, "grounding": 1.0, "safety": 1.0}, "failures": []}]
    cheap = aggregate(rows, rubric, cost_per_task_eur=0.001, p50_ms=100, p95_ms=100)
    pricey = aggregate(rows, rubric, cost_per_task_eur=0.02, p50_ms=100, p95_ms=100)
    assert cheap["overall"] == 1.0
    assert pricey["dimensions"]["cost"] == 0.0 and pricey["overall"] == pytest.approx(0.9)
