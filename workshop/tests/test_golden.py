import json

from evals.run_evals import GOLDEN_PATH, load_dataset, validate_case

MCP_TOOLS = {
    "search_patient", "get_care_plan", "list_available_slots", "book_follow_up",
    "create_referral", "check_medication_interactions", "check_prior_auth_requirement",
}
KNOWN_TOOLS = MCP_TOOLS | {"ask_policy_expert", "get_current_date"}


def test_golden_rows_are_valid_json_and_schema():
    lines = [l for l in GOLDEN_PATH.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert 12 <= len(lines) <= 15
    for line in lines:
        case = json.loads(line)
        assert validate_case(case) == [], case["id"]


def test_ids_unique_and_tools_known():
    cases = load_dataset()
    assert len({c["id"] for c in cases}) == len(cases)
    for case in cases:
        for call in case["expected_tool_calls"]:
            assert call["name"] in KNOWN_TOOLS, (case["id"], call["name"])
        assert set(case["forbidden_tool_calls"]) <= KNOWN_TOOLS


def test_required_scenarios_are_covered():
    cases = {c["id"]: c for c in load_dataset()}
    lab2 = cases["G01"]
    assert lab2["query"] == "Plan discharge for patient P-1042 and book a cardiology follow-up within 7 days."
    assert {"name": "list_available_slots", "arguments": {"specialty": "cardiology", "within_days": 7}} in lab2["expected_tool_calls"]
    categories = {c["category"] for c in cases.values()}
    assert {"prior_auth", "medication_check", "emergency_escalation", "refusal_diagnosis", "refusal_dosing"} <= categories
    assert any("CARD-MRI" in c["query"] and "Northwind" in c["query"] for c in cases.values())
    assert any("spironolactone" in c["query"] and "lisinopril" in c["query"] for c in cases.values())
    assert any(c["must_escalate"] for c in cases.values())
    assert any(c["uses_a2a"] for c in cases.values())


def test_filters():
    assert [c["id"] for c in load_dataset(ids=["G09", "G01"])] == ["G01", "G09"]
    assert len(load_dataset(limit=3)) == 3
