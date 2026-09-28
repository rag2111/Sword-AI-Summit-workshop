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
