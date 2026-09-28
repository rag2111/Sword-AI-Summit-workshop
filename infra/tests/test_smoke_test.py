"""MCP smoke checks must inspect backend results, not just the outer HTTP 200."""

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
