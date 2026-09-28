"""The committed OpenAPI spec is the MCP tool contract (CONTRACT §3): operationId == tool name."""

import json

import _helpers

SPEC = json.loads((_helpers.BACKEND / "app" / "openapi.json").read_text(encoding="utf-8"))


def operations():
    return {op["operationId"]: (method.upper(), path) for path, ops in SPEC["paths"].items() for method, op in ops.items()}


def test_exactly_the_seven_contract_tools():
    assert operations() == _helpers.CONTRACT_TOOLS


def test_openapi_version_and_descriptions_fit_mcp_tools():
    assert SPEC["openapi"].startswith("3.0.")
    for path, ops in SPEC["paths"].items():
        for op in ops.values():
            assert 80 <= len(op["description"]) <= 1000, op["operationId"]  # APIM tool description max 1000
            assert op["summary"]


def test_inputs_match_contract():
    params = {op["operationId"]: {p["name"] for p in op.get("parameters", [])}
              for ops in SPEC["paths"].values() for op in ops.values()}
    assert params["search_patient"] == {"query"}
    assert params["list_available_slots"] == {"specialty", "within_days"}
    assert params["check_prior_auth_requirement"] == {"payer", "procedure_code"}
    schemas = SPEC["components"]["schemas"]
    assert set(schemas["BookFollowUpRequest"]["required"]) == {"patient_id", "slot_id", "reason"}
    assert set(schemas["CreateReferralRequest"]["required"]) == {"patient_id", "specialty", "urgency", "reason"}
    assert schemas["CreateReferralRequest"]["properties"]["urgency"]["enum"] == ["routine", "urgent"]
    assert set(schemas["MedicationInteractionRequest"]["required"]) == {"medications"}
    assert "409" in SPEC["paths"]["/appointments"]["post"]["responses"]
