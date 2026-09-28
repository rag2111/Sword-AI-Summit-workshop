import time

import pytest

from tests.helpers import KEY


def test_inject_headers_adds_both_key_headers_and_keeps_others():
    from care_agent.apim_auth import inject_headers

    headers = inject_headers({"traceparent": "00-abc-def-01"}, KEY)
    assert headers["Ocp-Apim-Subscription-Key"] == KEY
    assert headers["api-key"] == KEY
    assert headers["traceparent"] == "00-abc-def-01"  # W3C context passes through untouched


def test_credential_returns_placeholder_token_valid_for_an_hour():
    from care_agent.apim_auth import PLACEHOLDER_TOKEN, ApimKeyCredential

    token = ApimKeyCredential().get_token("https://ai.azure.com/.default")
    assert token.token == PLACEHOLDER_TOKEN
    assert token.expires_on > time.time() + 3000
    assert KEY not in token.token  # the real key never travels as a bearer token


def test_async_credential():
    import asyncio

    from care_agent.apim_auth import PLACEHOLDER_TOKEN, AsyncApimKeyCredential

    token = asyncio.run(AsyncApimKeyCredential().get_token("scope"))
    assert token.token == PLACEHOLDER_TOKEN


def test_azure_core_policy_injects_key():
    pytest.importorskip("azure.core")
    from azure.core.pipeline import PipelineRequest
    from azure.core.pipeline.transport import HttpRequest

    from care_agent.apim_auth import make_headers_policy, make_subscription_key_policy

    request = PipelineRequest(HttpRequest("GET", "https://apim/foundry/x"), None)
    make_subscription_key_policy(KEY).on_request(request)
    assert request.http_request.headers["Ocp-Apim-Subscription-Key"] == KEY
    assert make_headers_policy(KEY) is not None
