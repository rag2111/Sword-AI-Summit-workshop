import importlib
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

from care_agent.instructions import BASE_INSTRUCTIONS, SAFETY_BOUNDARIES
from evals.upload_to_foundry import to_items
from loop.cluster import greedy_groups, label_failure, rank_clusters
from loop.propose import keeps_safety_boundaries, template_proposal, unified_diff
from loop.pull_failures import select_failures
from loop.validate import compare

ROWS = [
    {"id": "G01", "severity": "high", "row_score": 0.95, "failures": [], "query": "q1", "response": "ok"},
    {"id": "G09", "severity": "critical", "row_score": 0.4, "failures": ["emergency_escalation"], "query": "q9", "response": "booked",
     "raw": {"emergency_escalation": {"reason": "booked/referred during an emergency"}}, "trace_id": "t9"},
    {"id": "G03", "severity": "medium", "row_score": 0.65, "failures": ["groundedness"], "query": "q3", "response": "r3"},
    {"id": "G05", "severity": "high", "row_score": 0.8, "failures": ["tool_call_accuracy"], "query": "q5", "response": "r5"},
]


def test_select_failures_orders_worst_first():
    failures = select_failures(ROWS, threshold=0.7)
    assert [f["id"] for f in failures] == ["G09", "G03", "G05"]
    assert failures[0]["reasons"]["emergency_escalation"].startswith("booked")


def test_label_and_rank_by_impact():
    failures = select_failures(ROWS, threshold=0.7)
    assert label_failure(failures[0]) == ["missed_emergency_escalation"]
    clusters = rank_clusters(failures)
    assert clusters[0]["mode"] == "missed_emergency_escalation"
    assert clusters[0]["impact"] == 5 * 5  # critical × mode weight
    assert [c["mode"] for c in clusters[1:]] == ["wrong_or_missing_tool_call", "ungrounded_policy_answer"]  # 3×3 > 2×3


def test_greedy_groups():
    assert greedy_groups([[1, 0], [0.99, 0.01], [0, 1]]) == [[0, 1], [2]]


def test_template_proposal_keeps_boundaries_and_diffs():
    cluster = {"mode": "missed_emergency_escalation", "count": 1, "case_ids": ["G09"], "description": "", "examples": []}
    proposal = template_proposal(BASE_INSTRUCTIONS, cluster)
    assert keeps_safety_boundaries(proposal["instructions"])
    assert "## Additional guidance" in proposal["instructions"]
    diff = unified_diff(BASE_INSTRUCTIONS, proposal["instructions"], "v1", "v2")
    assert diff.startswith("--- v1") and "+- Before any tool call" in diff
    assert not keeps_safety_boundaries(BASE_INSTRUCTIONS.replace(SAFETY_BOUNDARIES[0][:40], ""))


def test_compare_gate():
    rubric = {"loop": {"min_improvement": 0.01}}
    base = {"run_id": "b", "overall": 0.80, "dimensions": {"safety": 0.95}, "gate": {"passed": False, "reasons": []}}
    better = {"run_id": "c", "overall": 0.86, "dimensions": {"safety": 1.0}, "gate": {"passed": True, "reasons": []}}
    assert compare(base, better, rubric)["passed"]
    worse_safety = {**better, "dimensions": {"safety": 0.9}}
    assert not compare(base, worse_safety, rubric)["passed"]
    no_gain = {**better, "overall": 0.805}
    assert "does not beat" in compare(base, no_gain, rubric)["reasons"][0]


def test_upload_items_shape():
    items = to_items([{**ROWS[0], "category": "discharge_planning", "dimension_scores": {"safety": 1.0}, "agent_version": "v1"}])
    assert items[0]["item"]["row_pass"] == "true" and items[0]["item"]["case_id"] == "G01"


@pytest.mark.parametrize("value", ["0", "-1", "abc", "1.5"])
def test_loop_rejects_invalid_limit_before_gateway_access(monkeypatch, value):
    from loop import run_loop

    settings = Mock()
    monkeypatch.setattr(run_loop, "get_settings", settings)
    with pytest.raises(SystemExit) as error:
        run_loop.main(["--limit", value])
    assert error.value.code == 2
    settings.assert_not_called()


@pytest.mark.parametrize("limit", [None, 1, 3, 99])
@pytest.mark.parametrize("quick", [False, True])
@pytest.mark.parametrize("baseline", ["missing", "complete", "incomplete"])
def test_loop_limits_all_phases_without_promotion(monkeypatch, limit, quick, baseline):
    from evals.run_evals import load_dataset
    from loop import run_loop

    cases = load_dataset()
    expected = [case["id"] for case in cases[:limit]]
    rows = [{"id": case["id"], "row_score": 0.2} for case in cases]
    monkeypatch.setattr(run_loop, "get_settings", lambda: object())
    monkeypatch.setattr(run_loop, "load_registry", lambda: {"active": "v1"})
    monkeypatch.setattr(run_loop, "resolve_version", lambda _: ("v1", BASE_INSTRUCTIONS))
    monkeypatch.setattr(run_loop, "find_run_for_version",
                        lambda _: None if baseline == "missing" else Path("existing"))
    monkeypatch.setattr(run_loop, "load_run",
                        lambda _: ({}, rows if baseline == "complete" else rows[-1:]))
    evaluation = AsyncMock(return_value=(Path("initial"), {}, []))
    monkeypatch.setattr(run_loop, "run_evaluation", evaluation)
    pull = Mock(return_value=(Path("source"), {"overall": 0.2}, rows))
    monkeypatch.setattr(run_loop, "pull", pull)
    write = Mock(return_value=Path("failures"))
    monkeypatch.setattr(run_loop, "write_failures", write)
    cluster = {"mode": "test", "impact": 1, "case_ids": expected}
    clusters = Mock(return_value=[cluster])
    monkeypatch.setattr(run_loop, "cluster_failures", clusters)
    monkeypatch.setattr(run_loop, "propose", lambda *a, **kw: {
        "entry": {"version": "v2", "parent": "v1"},
        "proposal": {"method": "template", "rationale": "test"},
        "diff": "",
    })
    validation = Mock(return_value=({
        "passed": True, "baseline_overall": 0.2, "candidate_overall": 0.9,
        "delta_overall": 0.7, "reasons": [],
    }, Path("candidate")))
    monkeypatch.setattr(run_loop, "validate", validation)
    promotion = Mock(return_value={"eval_run_id": "candidate", "trace_ids": []})
    monkeypatch.setattr(run_loop, "promote", promotion)

    args = ["--offline"]
    if limit is not None:
        args.extend(["--limit", str(limit)])
    if quick:
        args.append("--quick")
    assert run_loop.main(args) == 0

    if baseline == "complete" or (baseline == "incomplete" and limit is None):
        evaluation.assert_not_called()
        assert pull.call_args.args[0] == "existing"
    else:
        assert [case["id"] for case in evaluation.call_args.kwargs["cases"]] == expected
        assert pull.call_args.args[0] == "initial"
    assert [row["id"] for row in write.call_args.args[0]] == expected
    assert [row["id"] for row in clusters.call_args.args[0]] == expected
    assert validation.call_args.kwargs["ids"] == (expected if limit is not None or quick else None)
    assert validation.call_args.kwargs["use_judge"] is False
    if limit is not None:
        promotion.assert_not_called()
    else:
        promotion.assert_called_once_with("v2")


def test_limited_loop_stops_when_only_unselected_cases_fail(monkeypatch, capsys):
    from evals.run_evals import load_dataset
    from loop import run_loop

    monkeypatch.setattr(run_loop, "get_settings", lambda: object())
    monkeypatch.setattr(run_loop, "load_registry", lambda: {"active": "v1"})
    monkeypatch.setattr(run_loop, "find_run_for_version", lambda _: Path("existing"))
    monkeypatch.setattr(run_loop, "load_run", lambda _: ({}, load_dataset()))
    monkeypatch.setattr(run_loop, "pull", lambda *a: (Path("existing"), {}, [{"id": "G09"}]))
    write = Mock(return_value=Path("failures"))
    monkeypatch.setattr(run_loop, "write_failures", write)
    clusters = Mock()
    monkeypatch.setattr(run_loop, "cluster_failures", clusters)
    promotion = Mock()
    monkeypatch.setattr(run_loop, "promote", promotion)

    assert run_loop.main(["--limit", "3", "--offline"]) == 0

    assert write.call_args.args[0] == []
    clusters.assert_not_called()
    promotion.assert_not_called()
    assert "every selected case passed" in capsys.readouterr().out


def test_validation_runs_both_versions_on_selected_three_cases(monkeypatch, tmp_path):
    validation = importlib.import_module("loop.validate")
    ids = ["G01", "G02", "G03"]
    monkeypatch.setattr(validation, "get_settings", lambda: object())
    monkeypatch.setattr(validation, "load_registry", lambda: {
        "active": "v1", "versions": {"v2": {"parent": "v1"}},
    })
    monkeypatch.setattr(validation, "instructions_for", lambda version, **kw: f"Instructions for {version}")
    candidate_dir = tmp_path / "candidate"
    candidate_dir.mkdir()
    baseline_summary = {
        "run_id": "baseline", "overall": 0.2, "dimensions": {"safety": 1.0}, "gate": {"passed": True},
    }
    candidate_summary = {**baseline_summary, "run_id": "candidate", "overall": 0.9}
    evaluation = AsyncMock(side_effect=[
        (tmp_path / "baseline", baseline_summary, []),
        (candidate_dir, candidate_summary, []),
    ])
    monkeypatch.setattr(validation, "run_evaluation", evaluation)
    record = Mock()
    monkeypatch.setattr(validation, "record_eval", record)

    comparison, path = validation.validate("v2", ids=ids, judge_delay_seconds=5)

    assert evaluation.await_count == 2
    for call, version in zip(evaluation.await_args_list, ["v1", "v2"]):
        assert [case["id"] for case in call.kwargs["cases"]] == ids
        assert call.kwargs["version"] == version
        assert call.kwargs["judge_delay_seconds"] == 5
    assert comparison["passed"]
    assert (path / "comparison.json").is_file()
    record.assert_called_once()
