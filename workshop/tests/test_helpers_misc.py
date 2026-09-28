"""Pure helpers: tool matching, telemetry, MCP/SSE parsing, citations, errors, Lab 2 checks."""

import asyncio

import pytest

from evals.tool_match import arguments_match, short_name, tool_match_score


def test_tool_match_scoring():
    expected = [{"name": "get_care_plan", "arguments": {"patient_id": "P-1042"}},
                {"name": "list_available_slots", "arguments": {"specialty": "cardiology", "within_days": 7}}]
    actual = [{"name": "care_tools__get_care_plan", "arguments": {"patient_id": "p-1042"}},
              {"name": "list_available_slots", "arguments": {"specialty": "Cardiology", "within_days": 5}}]
    assert tool_match_score(expected, actual) == 1.0
    assert tool_match_score(expected, actual[:1]) == 0.5
    assert tool_match_score([], [{"name": "book_follow_up"}], ["book_follow_up"]) == 0.0
    assert tool_match_score([], [], ["book_follow_up"]) == 1.0
    assert not arguments_match({"within_days": 7}, {"within_days": 14})
    assert arguments_match({"medications": ["b", "a"]}, {"medications": ["A", "B"]})
    assert short_name("care_tools.search_patient") == "search_patient"


def test_connection_string_and_apim_routing():
    from care_agent.telemetry import parse_connection_string, telemetry_goes_through_apim
    from tests.helpers import make_settings

    parsed = parse_connection_string("InstrumentationKey=abc;IngestionEndpoint=https://x/telemetry/")
    assert parsed == {"instrumentationkey": "abc", "ingestionendpoint": "https://x/telemetry/"}
    assert telemetry_goes_through_apim(make_settings())


def test_span_tree_order():
    from care_agent.telemetry import build_span_tree

    spans = [
        {"span_id": "c", "parent_id": "b", "name": "execute_tool get_care_plan", "start": 3},
        {"span_id": "a", "parent_id": None, "name": "care_agent.turn", "start": 1},
        {"span_id": "b", "parent_id": "a", "name": "invoke_agent", "start": 2},
        {"span_id": "d", "parent_id": "b", "name": "chat gpt-6-luna", "start": 2.5},
    ]
    assert [(d, s["span_id"]) for d, s in build_span_tree(spans)] == [(0, "a"), (1, "b"), (2, "d"), (2, "c")]


def test_kql_filters_by_participant():
    from care_agent.telemetry import kql_queries

    queries = kql_queries("user07", "0af7651916cd43dd8448eb211c80319c")
    assert all("user07" in q or "0af7651916cd43dd8448eb211c80319c" in q for q in queries.values())


def test_turn_span_without_provider_is_safe():
    from care_agent.telemetry import turn_span

    with turn_span("care_agent.turn", {"participant.id": "user07"}) as span:
        span.set("x", 1)  # never raises, even with no SDK/provider


def test_mcp_payload_parsing_json_and_sse():
    from care_agent.smoke import parse_mcp_payload

    assert parse_mcp_payload('{"jsonrpc":"2.0","id":1,"result":{}}', "application/json")["id"] == 1
    sse = 'event: message\ndata: {"jsonrpc":"2.0","id":2,"result":{"tools":[{"name":"search_patient"}]}}\n\n'
    assert parse_mcp_payload(sse, "text/event-stream")["result"]["tools"][0]["name"] == "search_patient"
    with pytest.raises(ValueError):
        parse_mcp_payload("event: ping\n\n", "text/event-stream")


def test_citation_extraction():
    from care_agent.a2a_delegate import extract_citations

    text = ("Yes, prior authorization is required [prior-authorization-policy.md §3.2]. See also 【4:0†payer-northwind.md】.\n"
            "Sources: referral-policy.md §2; prior-authorization-policy.md §3.2")
    cites = extract_citations(text)
    assert cites[0] == "prior-authorization-policy.md §3.2"
    assert "payer-northwind.md" in cites and "referral-policy.md §2" in cites
    assert len(cites) == len(set(cites))
    assert extract_citations("no sources here") == []
    kb = "Yes (PA-001 §PA-2). Urgent referrals must not be downgraded (SAFE-001 §SAFE-2, REF-001 §REF-3.1).\nSources: PA-001 §PA-2"
    assert extract_citations(kb) == ["PA-001 §PA-2", "SAFE-001 §SAFE-2", "REF-001 §REF-3.1"]


class _Response:
    def __init__(self, status, headers=None):
        self.status_code = status
        self.headers = headers or {}


class _HTTPError(Exception):
    def __init__(self, status, headers=None):
        super().__init__(f"status {status}")
        self.response = _Response(status, headers)


def test_error_explanations():
    from care_agent.errors import explain, http_status_of

    wrapped = RuntimeError("service failed")
    wrapped.__cause__ = _HTTPError(429, {"retry-after": "12"})
    assert http_status_of(wrapped) == (429, 12.0)
    assert "Retry after ~12s" in explain(wrapped)
    assert "APIM_SUBSCRIPTION_KEY" in explain(_HTTPError(401))
    assert "MCP" in explain(RuntimeError("boom"), component="MCP /care-tools/mcp")


def test_retry_async_honours_429():
    from care_agent.errors import retry_async

    attempts = []

    async def flaky():
        attempts.append(1)
        if len(attempts) < 2:
            raise _HTTPError(429, {"retry-after-ms": "10"})
        return "ok"

    assert asyncio.run(retry_async(flaky, attempts=3)) == "ok" and len(attempts) == 2


def test_lab2_step_checker():
    from care_agent.lab2 import check_steps

    assert check_steps(["get_care_plan", "list_available_slots", "book_follow_up"]) == [
        ("get_care_plan", True), ("list_available_slots", True), ("book_follow_up", True)]
    assert check_steps(["book_follow_up"]) == [("get_care_plan", False), ("list_available_slots", False), ("book_follow_up", True)]


def test_extract_tool_activity_and_usage():
    from types import SimpleNamespace as NS

    from care_agent.agent import extract_tool_activity, extract_usage

    response = NS(messages=[
        NS(contents=[NS(type="function_call", name="get_care_plan", arguments='{"patient_id": "P-1042"}', call_id="c1")]),
        NS(contents=[NS(type="function_result", call_id="c1", result="{\"payer\": \"Northwind Health Plan\"}")]),
        NS(contents=[NS(type="text", text="done")]),
    ], usage_details={"input_token_count": 120, "output_token_count": 30})
    calls, results = extract_tool_activity(response)
    assert calls == [{"name": "get_care_plan", "arguments": {"patient_id": "P-1042"}, "call_id": "c1"}]
    assert results[0]["name"] == "get_care_plan" and "Northwind" in results[0]["result"]
    assert extract_usage(response) == (120, 30, 150)
