"""APIM policy templates render (like Terraform templatefile) to well-formed, contract-conform XML."""

import itertools
import re
import xml.etree.ElementTree as ET

import pytest

import _helpers

SECRET = {"secret_nv": "backend-shared-secret"}
BACKENDS = {"openai_backend": "foundry-openai", "content_safety_backend": "content-safety"}
CASES = [
    ("openai.xml", {"tokens_per_minute": 20000, "content_safety": cs, **BACKENDS}) for cs in (False, True)
] + [
    ("a2a.xml", {"adapter": a, "http_kind": h, "backend_base_url": "https://example.invalid/protocols", **SECRET})
    for a, h in itertools.product((False, True), repeat=2)
] + [
    ("telemetry.xml", {"anonymous": anon, "ikey": "00000000-0000-0000-0000-000000000000", "max_body_bytes": 3145728})
    for anon in (False, True)
] + [
    ("care-tools-api.xml", SECRET),
    ("care-tools-mcp.xml", SECRET),
    ("foundry.xml", {"project": "carews-proj", "project_backend": "foundry-project"}),
    ("a2a-card-operation.xml", {"card_path": "/a2a/agentCard/v1.0", "replace_from": "https://b/a2a", "replace_to": "https://g/a2a/care-knowledge"}),
    ("a2a-jsonrpc-operation.xml", {"jsonrpc_path": "/a2a"}),
    ("telemetry-config.xml", {"config_json": '{"connectionString":"InstrumentationKey=x;IngestionEndpoint=https://g/telemetry/"}'}),
]


def without_comments(text: str) -> str:
    return re.sub(r"<!--.*?-->", "", text, flags=re.S)


def render(name: str, variables: dict) -> ET.Element:
    text = _helpers.render_template((_helpers.POLICIES / name).read_text(encoding="utf-8"), variables)
    root = ET.fromstring(text)
    assert root.tag == "policies"
    assert [child.tag for child in root] == ["inbound", "backend", "outbound", "on-error"]
    return root


@pytest.mark.parametrize("name, variables", CASES)
def test_policy_renders_to_well_formed_xml(name, variables):
    render(name, variables)


def test_every_policy_template_is_covered():
    assert {p.name for p in _helpers.POLICIES.glob("*.xml")} == {name for name, _ in CASES}


def test_global_policy_sets_participant_header_and_never_touches_response_body():
    text = without_comments(_helpers.GLOBAL_POLICY.read_text(encoding="utf-8"))
    root = ET.fromstring(text)
    header = root.find("./inbound/set-header[@name='x-participant-id']")
    assert header is not None and header.get("exists-action") == "override"
    assert "context.Subscription" in header.findtext("value")
    assert "context.Response.Body" not in text


def test_openai_policy_limits_and_meters_per_subscription():
    for safety in (False, True):
        root = render("openai.xml", {"tokens_per_minute": 1234, "content_safety": safety, **BACKENDS})
        limit = root.find("./inbound/llm-token-limit")
        assert limit.get("counter-key") == "@(context.Subscription.Id)" and limit.get("tokens-per-minute") == "1234"
        dims = {d.get("name") for d in root.findall("./inbound/llm-emit-token-metric/dimension")}
        assert dims == {"Subscription ID", "User ID", "API ID", "Model"}
        assert root.find("./inbound/authentication-managed-identity").get("resource") == "https://cognitiveservices.azure.com"
        assert root.find("./backend/retry") is not None
        assert (root.find("./inbound/llm-content-safety") is not None) is safety


def test_mcp_policy_does_not_buffer_responses():
    text = without_comments((_helpers.POLICIES / "care-tools-mcp.xml").read_text(encoding="utf-8"))
    assert "context.Response.Body" not in text and "find-and-replace" not in text


def test_foundry_policy_strips_caller_auth_and_uses_managed_identity():
    root = render("foundry.xml", {"project": "carews-proj", "project_backend": "foundry-project"})
    deleted = {h.get("name") for h in root.findall("./inbound/set-header") if h.get("exists-action") == "delete"}
    assert {"Authorization", "Ocp-Apim-Subscription-Key", "api-key"} <= deleted
    assert root.find("./inbound/authentication-managed-identity").get("resource") == "https://ai.azure.com"
    assert root.find("./inbound/choose/when/return-response/set-status").get("code") == "403"
    allow = root.find("./inbound/set-variable[@name='foundryAllowed']").get("value")
    assert "/api/projects/carews-proj/" in allow and "care-knowledge-agent" in allow


def test_a2a_native_uses_managed_identity_and_a2a_version():
    root = render("a2a.xml", {"adapter": False, "http_kind": False, "backend_base_url": "x", **SECRET})
    assert root.find("./inbound/authentication-managed-identity").get("resource") == "https://ai.azure.com"
    assert root.find("./inbound/set-header[@name='A2A-Version']").findtext("value") == "1.0"
    adapter = render("a2a.xml", {"adapter": True, "http_kind": True, "backend_base_url": "https://x", **SECRET})
    assert adapter.find("./inbound/authentication-managed-identity") is None
    assert adapter.find("./inbound/set-header[@name='x-backend-secret']").findtext("value") == "{{backend-shared-secret}}"


def test_telemetry_fallback_filters_ikey_and_rate_limits_by_ip():
    anon = render("telemetry.xml", {"anonymous": True, "ikey": "IKEY-123", "max_body_bytes": 10})
    assert anon.find("./inbound/rate-limit-by-key").get("counter-key") == "@(context.Request.IpAddress)"
    assert "IKEY-123" in anon.find("./inbound/choose/when").get("condition")
    keyed = render("telemetry.xml", {"anonymous": False, "ikey": "IKEY-123", "max_body_bytes": 10})
    assert keyed.find("./inbound/choose") is None
    assert keyed.find("./inbound/validate-content").get("max-size") == "10"


def test_policies_are_uploaded_as_xml_encoded_documents():
    # The templates are XML-encoded (e.g. As&lt;JObject&gt;), so ARM must receive format "xml", not "rawxml".
    for tf in _helpers.INFRA.rglob("*.tf"):
        assert 'format = "rawxml"' not in tf.read_text(encoding="utf-8"), tf
