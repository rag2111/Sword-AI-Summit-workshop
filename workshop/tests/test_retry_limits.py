"""Token-limit recovery without gateway traffic or real sleeps."""

import asyncio
import json
from functools import partial
from unittest.mock import AsyncMock, Mock, call

import httpx
import pytest

from care_agent import errors
from evals import judge, run_evals
from tests.helpers import make_settings


def rate_limit(headers):
    response = httpx.Response(429, headers=headers, request=httpx.Request("POST", "https://example.invalid"))
    return httpx.HTTPStatusError("Token limit exceeded", request=response.request, response=response)


@pytest.mark.parametrize(("headers", "delay"), [
    ({"Retry-After": "38"}, 38),
    ({"Retry-After": "65"}, 65),
    ({"retry-after-ms": "45000"}, 45),
    ({"x-ms-retry-after-ms": "41000"}, 41),
    ({"Retry-After": "0"}, 0),
    ({}, 5),
    ({"Retry-After": "invalid"}, 5),
    ({"Retry-After": "nan"}, 5),
    ({"Retry-After": "inf"}, 5),
    ({"Retry-After": "-1"}, 5),
    ({"retry-after-ms": "invalid", "Retry-After": "38"}, 38),
])
def test_async_and_custom_judge_honor_full_delay(monkeypatch, headers, delay):
    failure = rate_limit(headers)
    wrapped = RuntimeError("Wrapped SDK failure")
    wrapped.__cause__ = failure
    operation = AsyncMock(side_effect=[wrapped, "ok"])
    sleep_async = AsyncMock()
    monkeypatch.setattr(errors.asyncio, "sleep", sleep_async)
    monkeypatch.setattr(errors.random, "uniform", lambda lower, upper: 0)
    assert asyncio.run(errors.retry_async(operation)) == "ok"
    sleep_async.assert_awaited_once_with(delay)

    post = Mock(side_effect=[
        failure.response,
        httpx.Response(200, request=failure.request, json={"ok": True}),
    ])
    sleep_sync = Mock()
    monkeypatch.setattr(httpx, "post", post)
    monkeypatch.setattr(judge.time, "sleep", sleep_sync)
    assert judge._post_with_retry(make_settings(), str(failure.request.url), {}, 60, 3) == {"ok": True}
    sleep_sync.assert_called_once_with(delay)
    assert post.call_count == 2


def test_async_retry_stays_bounded_and_keeps_fallback_cap(monkeypatch):
    failure = rate_limit({})
    operation = AsyncMock(side_effect=failure)
    sleep = AsyncMock()
    monkeypatch.setattr(errors.asyncio, "sleep", sleep)
    monkeypatch.setattr(errors.random, "uniform", lambda lower, upper: 0)
    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(errors.retry_async(operation, attempts=3, default_wait=40, max_wait=30))
    assert operation.await_count == 3
    assert sleep.await_args_list == [call(30), call(30)]


def test_custom_retry_exhaustion_preserves_error(monkeypatch):
    failure = rate_limit({"Retry-After": "65"})
    post = Mock(return_value=failure.response)
    sleep = Mock()
    monkeypatch.setattr(httpx, "post", post)
    monkeypatch.setattr(judge.time, "sleep", sleep)
    with pytest.raises(httpx.HTTPStatusError):
        judge._post_with_retry(make_settings(), str(failure.request.url), {}, 60, 3)
    assert post.call_count == 3
    assert sleep.call_args_list == [call(65), call(65)]


@pytest.mark.parametrize("concurrency", [None, 1, 2])
def test_judge_concurrency_is_bounded_and_preserves_row_order(monkeypatch, concurrency):
    active = peak = 0

    async def to_thread(fn, *args):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0)
        result = fn(*args)
        active -= 1
        return result

    monkeypatch.setattr(run_evals.asyncio, "to_thread", to_thread)
    monkeypatch.setattr(run_evals, "score_row", lambda row, *args: {"scored": row["id"]})
    rows = [{"id": i} for i in range(5)]
    kwargs = {} if concurrency is None else {"concurrency": concurrency}
    result = asyncio.run(run_evals.score_rows(rows, None, [], {}, **kwargs))
    assert peak == (concurrency or 1)
    assert result == [{"id": i, "scored": i} for i in range(5)]


def test_sdk_judge_retries_429_using_server_delay(monkeypatch):
    from azure.ai.evaluation._legacy.prompty import _prompty
    from openai import AsyncAzureOpenAI

    requests = []

    def respond(request):
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(429, headers={"Retry-After": "38"}, json={
                "statusCode": 429, "message": "Token limit is exceeded. Try again in 38 seconds.",
            })
        return httpx.Response(200, json={
            "id": "retry-test", "object": "chat.completion", "created": 0, "model": "gpt-6-sol",
            "choices": [{"index": 0, "finish_reason": "stop", "message": {
                "role": "assistant", "content": json.dumps({"score": 5, "reason": "Resolved."}),
            }}],
            "usage": {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30},
        })

    http = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    monkeypatch.setattr(_prompty, "AsyncAzureOpenAI", partial(AsyncAzureOpenAI, http_client=http))
    sleep = AsyncMock()
    monkeypatch.setattr(_prompty.asyncio, "sleep", sleep)
    try:
        judges = run_evals.Judges(make_settings(), use_judge=True)
        raw = {}
        score = judges.call(
            "intent_resolution", raw,
            query=[{"role": "user", "content": [{"type": "text", "text": "Hello"}]}],
            response=[{"role": "assistant", "content": [{"type": "text", "text": "Hello!"}]}],
        )
        assert score is not None, raw
        assert len(requests) == 2
        sleep.assert_awaited_once_with(38)
    finally:
        asyncio.run(http.aclose())
