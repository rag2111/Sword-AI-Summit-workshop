"""MCP and A2A smoke checks inspect backend results, not just the outer HTTP 200."""

import importlib.util
import json
from unittest.mock import Mock

import httpx
import pytest

from _helpers import INFRA

spec = importlib.util.spec_from_file_location("infra_smoke", INFRA / "scripts" / "smoke_test.py")
smoke_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke_module)

TOOLS = [
    "search_patient", "get_care_plan", "list_available_slots", "book_follow_up",
    "create_referral", "check_medication_interactions", "check_prior_auth_requirement",
]


@pytest.mark.parametrize(("slots", "ok"), [
    ([{"slot_id": "SLOT-CARD-001", "specialty": "cardiology"}], True),
    ([], True),
    ({"detail": [{"input": "cardiology?within_days=7", "type": "literal_error"}]}, False),
    ([{"slot_id": "SLOT-PULM-001", "specialty": "pulmonology"}], False),
    ([{"specialty": "cardiology"}], False),
])
def test_mcp_checks_slot_result(slots, ok):
    smoke = smoke_module.Smoke({
        "APIM_BASE_URL": "https://example.invalid", "APIM_SUBSCRIPTION_KEY": "test-only",
        "MCP_URL": "https://example.invalid/care-tools/mcp",
    })
    smoke.http.close()
    response = httpx.Response(200)
    smoke._mcp = Mock(side_effect=[
        (response, {"result": {}}),
        (response, None),
        (response, {"result": {"tools": [{"name": name} for name in TOOLS]}}),
        (response, {"result": {"content": [{"type": "text", "text": '{"patient_id":"P-1042"}'}]}}),
        (response, {"result": {"content": [{"type": "text", "text": json.dumps(slots)}]}}),
    ])
    passed, detail = smoke.mcp()
    assert passed is ok, detail
    assert smoke._mcp.call_args.args[0]["params"] == {
        "name": "list_available_slots", "arguments": {"specialty": "cardiology", "within_days": 7},
    }


@pytest.mark.parametrize("state", ["failed", "TASK_STATE_FAILED", "working", "TASK_STATE_INPUT_REQUIRED"])
def test_a2a_rejects_incomplete_tasks_even_with_cited_artifacts(state):
    ok, detail = smoke_module.validate_a2a_answer({"task": {
        "status": {"state": state},
        "artifacts": [{"parts": [{"text": "Required (PA-001 §PA-3)."}]}],
    }})
    assert not ok
    assert state in detail


@pytest.mark.parametrize("wrapped,state", [(True, "TASK_STATE_COMPLETED"), (False, "completed")])
def test_a2a_accepts_cited_completed_tasks(wrapped, state):
    task = {"status": {"state": state}, "artifacts": [{"parts": [{"text": "Required (PA-001 §PA-3)."}]}]}
    assert smoke_module.validate_a2a_answer({"task": task} if wrapped else task)[0]


@pytest.mark.parametrize("wrapped", [True, False])
def test_a2a_accepts_cited_message(wrapped):
    message = {"parts": [{"text": "Required (PA-001 §PA-3)."}]}
    assert smoke_module.validate_a2a_answer({"message": message} if wrapped else message)[0]


@pytest.mark.parametrize("answer", ["", "Requires prior authorization.", "Sources: none"])
def test_a2a_rejects_missing_citations_and_ignores_history(answer):
    task = {
        "status": {"state": "TASK_STATE_COMPLETED"},
        "artifacts": [{"parts": [{"text": answer}]}],
        "history": [{"parts": [{"text": "Please cite PA-001 §PA-3."}]}],
    }
    assert not smoke_module.validate_a2a_answer({"task": task})[0]
