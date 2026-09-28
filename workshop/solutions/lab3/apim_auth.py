"""Credentials trick for the Foundry SDK through APIM (CONTRACT section 5).

WORKSHOP PATTERN — read this before copying it into a real project.

`azure-ai-projects` only accepts an Entra `TokenCredential`. Participants have no Entra identity
in the workshop tenant, so instead:

1. `ApimKeyCredential` hands the SDK a static placeholder token. APIM's /foundry policy DISCARDS the
   caller's `Authorization` header and calls Foundry with the gateway's own managed identity.
2. `ApimSubscriptionKeyPolicy` (an azure-core per-call policy) adds `Ocp-Apim-Subscription-Key`,
   which is what actually authenticates you at the gateway.
3. The /foundry policy allow-lists only the operations the labs need (evals, datasets, agents read,
   red teams, OpenAI evals/responses) and answers 403 for everything else.

In production you would give each caller a real identity (Entra ID / managed identity) and let APIM
validate the token (validate-azure-ad-token) instead of a shared-secret subscription key.
"""

from __future__ import annotations

import time
from typing import Any, NamedTuple

from .config import SUBSCRIPTION_KEY_HEADER, Settings, apim_headers

PLACEHOLDER_TOKEN = "apim-uses-its-own-managed-identity"  # noqa: S105 - not a secret, APIM discards it


class _AccessToken(NamedTuple):
    """Shape-compatible with azure.core.credentials.AccessToken (token, expires_on)."""

    token: str
    expires_on: int


def _access_token() -> Any:
    expires = int(time.time()) + 3600
    try:
        from azure.core.credentials import AccessToken

        return AccessToken(PLACEHOLDER_TOKEN, expires)
    except ImportError:
        return _AccessToken(PLACEHOLDER_TOKEN, expires)


def _access_token_info() -> Any:
    expires = int(time.time()) + 3600
    try:
        from azure.core.credentials import AccessTokenInfo

        return AccessTokenInfo(PLACEHOLDER_TOKEN, expires)
    except ImportError:
        return _AccessToken(PLACEHOLDER_TOKEN, expires)


class ApimKeyCredential:
    """Synchronous TokenCredential that returns a placeholder token (see module docstring)."""

    def get_token(self, *scopes: str, **kwargs: Any) -> Any:
        return _access_token()

    def get_token_info(self, *scopes: str, options: Any = None) -> Any:
        return _access_token_info()

    def close(self) -> None:
        pass

    def __enter__(self) -> ApimKeyCredential:
        return self

    def __exit__(self, *args: Any) -> None:
        pass


class AsyncApimKeyCredential:
    """Async variant for `azure.ai.projects.aio` / async SDK clients."""

    async def get_token(self, *scopes: str, **kwargs: Any) -> Any:
        return _access_token()

    async def get_token_info(self, *scopes: str, options: Any = None) -> Any:
        return _access_token_info()

    async def close(self) -> None:
        pass

    async def __aenter__(self) -> AsyncApimKeyCredential:
        return self

    async def __aexit__(self, *args: Any) -> None:
        pass


def inject_headers(headers: dict[str, str], key: str) -> dict[str, str]:
    """Pure helper used by the policy (and unit tests): add both key headers, keep the rest."""
    for name, value in apim_headers(key).items():
        headers[name] = value
    return headers


def make_subscription_key_policy(key: str) -> Any:
    """Return an azure-core SansIOHTTPPolicy that adds the APIM subscription key to every request."""
    from azure.core.pipeline.policies import SansIOHTTPPolicy

    class ApimSubscriptionKeyPolicy(SansIOHTTPPolicy):
        def on_request(self, request: Any) -> None:
            inject_headers(request.http_request.headers, key)

    return ApimSubscriptionKeyPolicy()


def make_headers_policy(key: str) -> Any:
    """azure-core HeadersPolicy with the key as base header (used for the Azure Monitor exporter)."""
    from azure.core.pipeline.policies import HeadersPolicy

    return HeadersPolicy(base_headers=apim_headers(key))


def foundry_project_client(settings: Settings) -> Any:
    """AIProjectClient pointed at ${APIM_BASE_URL}/foundry/api/projects/<project> (sync)."""
    if not settings.foundry_project_endpoint:
        raise RuntimeError(
            "FOUNDRY_PROJECT_ENDPOINT is unknown: /telemetry/config did not return foundryProjectName. "
            "Set FOUNDRY_PROJECT_NAME in .env (ask the presenter)."
        )
    from azure.ai.projects import AIProjectClient

    return AIProjectClient(
        endpoint=settings.foundry_project_endpoint,
        credential=ApimKeyCredential(),
        per_call_policies=[make_subscription_key_policy(settings.subscription_key)],
    )


def foundry_openai_client(project_client: Any, settings: Settings) -> Any:
    """OpenAI client for Foundry evals/responses, also carrying the APIM key header."""
    client = project_client.get_openai_client()
    # with_options() returns a copy whose default headers are merged with ours.
    return client.with_options(default_headers={SUBSCRIPTION_KEY_HEADER: settings.subscription_key})
