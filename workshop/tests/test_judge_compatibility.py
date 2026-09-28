"""Judge request compatibility, using the installed SDK with mocked HTTP."""

import asyncio
import json
from functools import partial
from unittest.mock import AsyncMock, Mock

import httpx
import pytest

from evals.judge import chat
from evals.run_evals import Judges, load_dataset, score_row
from evals.scoring import load_rubric
from tests.helpers import BASE, KEY, make_settings


@pytest.mark.parametrize("model", ["gpt-6-sol", "gpt-6-luna", "gpt-4.1"])
def test_custom_judge_request_parameters(monkeypatch, model):
    def post(url, *, json, headers, timeout):
        assert url.startswith(f"{BASE}/openai/deployments/{model}/chat/completions?")
        assert headers["api-key"] == headers["Ocp-Apim-Subscription-Key"] == KEY
        assert json["response_format"] == {"type": "json_object"}
        if model in {"gpt-6-sol", "gpt-6-luna"}:
            assert json["max_completion_tokens"] == 300
            assert json["reasoning_effort"] == "none"
            assert "max_tokens" not in json
            assert "temperature" not in json
        else:
            assert json["max_tokens"] == 300
            assert json["temperature"] == 0.2
            assert "reasoning_effort" not in json
            assert "max_completion_tokens" not in json
        return httpx.Response(200, request=httpx.Request("POST", url), json={
            "choices": [{"message": {"content": '{"ok":true}'}}],
            "usage": {"prompt_tokens": 20, "completion_tokens": 10},
        })

    monkeypatch.setattr(httpx, "post", post)
    text, usage = chat(make_settings(), system="Return JSON.", user="Test.",
                       model=model, max_tokens=300, temperature=0.2)
    assert json.loads(text) == {"ok": True}
    assert usage == {"input": 20, "output": 10}


@pytest.mark.parametrize("model", ["gpt-6-sol", "gpt-6-luna", "gpt-4.1"])
def test_sdk_judges_send_compatible_requests(monkeypatch, caplog, model):
    from azure.ai.evaluation._legacy.prompty import _prompty
    from openai import AsyncAzureOpenAI

    requests = []

    def respond(request):
        body = json.loads(request.content)
        requests.append(body)
        assert str(request.url).startswith(f"{BASE}/openai/deployments/{model}/chat/completions?")
        if len(requests) == 2:
            prompt = json.dumps(body["messages"])
            assert "Report the retrieved date." in prompt
            assert "Retrieved date: 2026-09-28." in prompt
        if model in {"gpt-6-sol", "gpt-6-luna"}:
            assert body["max_completion_tokens"] > 0
            assert not {"max_tokens", "temperature", "top_p", "presence_penalty", "frequency_penalty"} & body.keys()
        else:
            assert "temperature" in body
            assert ("max_tokens" in body) != ("max_completion_tokens" in body)
            if len(requests) == 1:
                assert "max_tokens" in body
        return httpx.Response(200, request=request, json={
            "id": "judge-test", "object": "chat.completion", "created": 0, "model": model,
            "choices": [{"index": 0, "finish_reason": "stop", "message": {
                "role": "assistant",
                "content": json.dumps({"score": 5, "reason": "Test verdict."}),
            }}],
            "usage": {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30},
        })

    http = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    monkeypatch.setattr(_prompty, "AsyncAzureOpenAI", partial(AsyncAzureOpenAI, http_client=http))
    judges = Judges(make_settings(JUDGE_MODEL=model), use_judge=True)
    assert set(judges.llm) == {
        "intent_resolution", "task_adherence", "tool_call_accuracy", "groundedness", "relevance",
    }
    query = [
        {"role": "system", "content": "Report the retrieved date."},
        {"role": "user", "content": [{"type": "text", "text": "What is today's date?"}]},
    ]
    response = [
        {"role": "assistant", "content": [{"type": "tool_call", "tool_call_id": "date-call",
                                         "name": "get_current_date", "arguments": {}}]},
        {"role": "tool", "tool_call_id": "date-call",
         "content": [{"type": "tool_result", "tool_result": "Retrieved date: 2026-09-28."}]},
        {"role": "assistant", "content": [{"type": "text", "text": "2026-09-28"}]},
    ]
    inputs = {
        "intent_resolution": {"query": query, "response": response},
        "task_adherence": {"query": query, "response": response},
        "tool_call_accuracy": {
            "query": "What is today's date?",
            "tool_calls": [{"type": "tool_call", "tool_call_id": "date-call",
                            "name": "get_current_date", "arguments": {}}],
            "tool_definitions": [{"name": "get_current_date", "description": "Get today's date.",
                                  "parameters": {"type": "object", "properties": {}}}],
        },
        "groundedness": {"query": "What is today's date?", "response": "2026-09-28", "context": "Today is 2026-09-28."},
        "relevance": {"query": "What is today's date?", "response": "2026-09-28"},
    }
    for name, kwargs in inputs.items():
        raw = {}
        value = judges.call(name, raw, **kwargs)
        assert value is not None, raw
        assert len(requests) == list(inputs).index(name) + 1
    assert "could not be parsed" not in caplog.text
    asyncio.run(http.aclose())


def test_score_row_formats_text_for_conversation_judges(monkeypatch):
    judges = Judges(make_settings(), use_judge=False)
    calls = {}

    def evaluate(name, raw, **kwargs):
        calls[name] = kwargs
        return 1.0

    monkeypatch.setattr(judges, "call", evaluate)
    row = {**load_dataset(ids=["G10"])[0], "response": "I cannot diagnose. Please consult a clinician."}
    result = score_row(row, judges, [], load_rubric())
    for name in ("intent_resolution", "task_adherence"):
        assert calls[name]["query"] == [
            {"role": "user", "content": [{"type": "text", "text": row["query"]}]},
        ]
        assert calls[name]["response"] == [
            {"role": "assistant", "content": [{"type": "text", "text": row["response"]}]},
        ]
    assert result["metrics"]["tool_call_accuracy"] == result["metrics"]["tool_match"]
    assert result["raw"]["no_clinical_diagnosis"]["no_clinical_diagnosis_method"] == "heuristic"


def test_custom_judge_does_not_retry_bad_requests(monkeypatch):
    requests = []

    def post(url, **kwargs):
        requests.append(url)
        return httpx.Response(400, request=httpx.Request("POST", url), json={"error": "invalid parameter"})

    monkeypatch.setattr(httpx, "post", post)
    with pytest.raises(httpx.HTTPStatusError):
        chat(make_settings(), system="Return JSON.", user="Test.")
    assert len(requests) == 1


def test_score_row_passes_observed_tool_evidence_and_actual_instructions(monkeypatch, caplog):
    from azure.ai.evaluation._common.utils import reformat_agent_response, reformat_conversation_history
    import logging

    instructions = "Report documented facts; never infer a diagnosis."
    judges = Judges(make_settings(), use_judge=False, instructions=instructions)
    captured = {}

    def evaluate(name, raw, **kwargs):
        captured[name] = kwargs
        return 1.0

    monkeypatch.setattr(judges, "call", evaluate)
    row = {
        **load_dataset(ids=["G10"])[0], "response": "Please ask your clinician.",
        "tool_calls": [
            {"name": "get_care_plan", "call_id": "plan", "arguments": {"patient_id": "P-5318"}},
            {"name": "get_current_date", "arguments": {}},
        ],
        "tool_results": [
            {"name": "get_care_plan", "call_id": "plan", "result": "Synthetic documented fact."},
            {"name": "get_current_date", "result": "Unmatched result."},
        ],
    }
    definitions = [{"name": "get_care_plan", "parameters": {"type": "object"}}]
    score_row(row, judges, definitions, load_rubric())
    logger = logging.getLogger(__name__)
    for name in ("intent_resolution", "task_adherence"):
        inputs = captured[name]
        assert inputs["tool_definitions"] == definitions
        query = reformat_conversation_history(inputs["query"], logger, include_system_messages=True)
        answer = reformat_agent_response(inputs["response"], logger, include_tool_messages=True)
        assert instructions in query
        assert row["query"] in query
        assert "get_care_plan" in answer and "P-5318" in answer
        assert "Synthetic documented fact." in answer
        assert "Unmatched result." not in answer
        assert row["response"] in answer
    assert "could not be parsed" not in caplog.text


@pytest.mark.parametrize("instructions", [None, "Candidate instructions."])
def test_pipeline_uses_same_instructions_for_agent_and_judges(monkeypatch, tmp_path, instructions):
    from care_agent import instructions as instruction_module
    from evals import run_evals

    monkeypatch.setattr(instruction_module, "load_active_instructions", lambda: ("v1", "Active instructions."))
    case = load_dataset(ids=["G10"])[0]
    row = {**case, "response": "Please consult your clinician.", "trace_id": None, "latency_ms": 1}
    collect = AsyncMock(return_value=([row], [], "test-instructions-hash"))
    score = AsyncMock(wraps=run_evals.score_rows)
    factory = Mock(wraps=Judges)
    monkeypatch.setattr(run_evals, "collect_responses", collect)
    monkeypatch.setattr(run_evals, "score_rows", score)
    monkeypatch.setattr(run_evals, "Judges", factory)
    out, summary, scored = asyncio.run(run_evals.run_evaluation(
        make_settings(), cases=[case], rubric=load_rubric(), version="v1",
        instructions=instructions, use_judge=False, out_root=tmp_path, concurrency=2,
    ))
    expected = instructions or "Active instructions."
    assert collect.call_args.kwargs["instructions"] == expected
    assert collect.call_args.kwargs["concurrency"] == score.call_args.kwargs["concurrency"] == 2
    assert factory.call_args.kwargs["instructions"] == expected
    assert scored[0]["metrics"]["intent_resolution"] is None
    assert (out / "results.jsonl").is_file()
    assert json.loads((out / "summary.json").read_text())["cases"] == summary["cases"] == 1
