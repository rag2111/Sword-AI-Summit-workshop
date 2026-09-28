"""Chat Completions tool compatibility for the workshop model."""

import asyncio
import importlib
import importlib.util
import json
import sys
from unittest.mock import Mock

import httpx
import pytest

from tests.helpers import BASE, KEY, ROOT, make_settings


@pytest.fixture(params=range(1, 7))
def checkpoint_agent(request):
    folder = ROOT / "solutions" / f"lab{request.param}"
    name = f"chat_options_lab{request.param}"
    spec = importlib.util.spec_from_file_location(
        name, folder / "__init__.py", submodule_search_locations=[str(folder)]
    )
    package = importlib.util.module_from_spec(spec)
    sys.modules[name] = package
    spec.loader.exec_module(package)
    return importlib.import_module(f"{name}.agent")


@pytest.mark.parametrize(("api", "model", "expected"), [
    ("chat_completions", "gpt-6-luna", {"reasoning_effort": "none"}),
    ("responses", "gpt-6-luna", None),
    ("chat_completions", "gpt-4.1", None),
])
def test_reasoning_override_is_scoped(checkpoint_agent, monkeypatch, api, model, expected):
    import agent_framework

    factory = Mock()
    monkeypatch.setattr(agent_framework, "Agent", factory)
    client = Mock()
    monkeypatch.setattr(checkpoint_agent, "create_chat_client", lambda settings: client)
    tools = [checkpoint_agent.get_current_date]
    checkpoint_agent.create_agent(make_settings(CHAT_API=api, CHAT_MODEL=model), "Test instructions", tools)
    kwargs = factory.call_args.kwargs
    assert kwargs.get("default_options") == expected
    assert kwargs["client"] is client
    assert kwargs["tools"] is tools
    assert kwargs["instructions"] == "Test instructions"


def test_reasoning_effort_reaches_every_tool_loop_request(checkpoint_agent, monkeypatch):
    from agent_framework.openai import OpenAIChatCompletionClient
    from openai import AsyncOpenAI

    requests = []

    def respond(request):
        body = json.loads(request.content)
        requests.append(body)
        assert body["model"] == "gpt-6-luna"
        assert body["reasoning_effort"] == "none"
        assert body["tools"][0]["function"]["name"] == "get_current_date"
        message = {"role": "assistant", "content": "Date retrieved."}
        if len(requests) == 1:
            message = {"role": "assistant", "content": None, "tool_calls": [{
                "id": "date-call", "type": "function",
                "function": {"name": "get_current_date", "arguments": "{}"},
            }]}
        return httpx.Response(200, json={
            "id": "test-completion", "object": "chat.completion", "created": 0,
            "model": "gpt-6-luna", "choices": [{
                "index": 0, "message": message,
                "finish_reason": "tool_calls" if len(requests) == 1 else "stop",
            }],
        })

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            async with AsyncOpenAI(api_key=KEY, base_url=f"{BASE}/openai/v1", http_client=http) as sdk:
                client = OpenAIChatCompletionClient(model="gpt-6-luna", async_client=sdk)
                monkeypatch.setattr(checkpoint_agent, "create_chat_client", lambda settings: client)
                agent = checkpoint_agent.create_agent(
                    make_settings(), "Use the date tool.", [checkpoint_agent.get_current_date]
                )
                async with agent:
                    response = await agent.run("What is today's date?")
                    assert response.text == "Date retrieved."

    asyncio.run(run())
    assert len(requests) == 2
    tool_results = [m for m in requests[1]["messages"] if m["role"] == "tool"]
    assert tool_results[0]["tool_call_id"] == "date-call"
