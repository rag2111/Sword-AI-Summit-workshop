"""Friendly error handling shared by every workshop command.

Participants only ever talk to Azure API Management (APIM), so almost every failure is one of:
401 (bad key), 403 (operation not allow-listed), 404 (wrong route/deployment), 429 (token limit)
or a network problem. `explain()` turns those into one actionable sentence.
"""

from __future__ import annotations

import asyncio
import math
import random
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

T = TypeVar("T")


class LabIncomplete(RuntimeError):
    """Raised when code that a later lab fills in is still a TODO."""

    def __init__(self, lab: int, where: str, hint: str = "") -> None:
        self.lab = lab
        self.where = where
        message = f"This step needs Lab {lab}: complete the `TODO (Lab {lab})` block in {where}."
        if hint:
            message += f" Hint: {hint.rstrip('.')}."
        message += f" Stuck? Run `uv run poe catchup {lab}`."
        super().__init__(message)


def _iter_causes(exc: BaseException, max_depth: int = 8):
    """Walk an exception and its causes (SDKs love to wrap HTTP errors several times)."""
    seen: set[int] = set()
    stack: list[BaseException] = [exc]
    while stack and len(seen) < max_depth:
        current = stack.pop(0)
        if id(current) in seen:
            continue
        seen.add(id(current))
        yield current
        for attr in ("__cause__", "__context__", "inner_exception"):
            nested = getattr(current, attr, None)
            if isinstance(nested, BaseException):
                stack.append(nested)
        # ExceptionGroup (anyio / MCP task groups) keeps children in .exceptions
        for nested in getattr(current, "exceptions", ()) or ():
            if isinstance(nested, BaseException):
                stack.append(nested)


def _retry_after_from_headers(headers: Any) -> float | None:
    if not headers:
        return None
    for name, scale in (("retry-after-ms", 1000.0), ("x-ms-retry-after-ms", 1000.0), ("retry-after", 1.0)):
        value = headers.get(name)
        if value is None:
            continue
        try:
            seconds = float(value) / scale
        except (TypeError, ValueError):
            continue
        if math.isfinite(seconds) and seconds >= 0:
            return seconds
    return None


def http_status_of(exc: BaseException) -> tuple[int | None, float | None]:
    """Return (HTTP status, retry-after seconds) found anywhere in the exception chain."""
    for current in _iter_causes(exc):
        response = getattr(current, "response", None)
        status = getattr(current, "status_code", None) or getattr(response, "status_code", None)
        if isinstance(status, int):
            return status, _retry_after_from_headers(getattr(response, "headers", None))
    # Last resort: some wrappers only keep the status in the message text.
    text = " ".join(str(c) for c in _iter_causes(exc))
    for code in (401, 403, 404, 409, 429, 500, 502, 503, 504):
        if f"{code}" in text and ("status" in text.lower() or "error code" in text.lower()):
            return code, None
    return None, None


def explain(exc: BaseException, *, component: str = "") -> str:
    """Translate an exception into a helpful, workshop-specific message."""
    status, retry_after = http_status_of(exc)
    where = f" ({component})" if component else ""
    if isinstance(exc, LabIncomplete):
        return str(exc)
    if status == 401:
        return (
            f"APIM rejected your subscription key (401){where}. Check APIM_SUBSCRIPTION_KEY in .env: "
            "copy it again from your participant card, without quotes or spaces."
        )
    if status == 403:
        return (
            f"Forbidden (403){where}. The gateway only allow-lists the operations the labs need. "
            "If you did not change any URLs, tell the presenter which command you ran."
        )
    if status == 404:
        return (
            f"Not found (404){where}. Check APIM_BASE_URL (no trailing path) and the model/deployment "
            "names (CHAT_MODEL / JUDGE_MODEL)."
        )
    if status == 429:
        wait = f" Retry after ~{retry_after:.0f}s." if retry_after else " Wait ~30s and retry."
        return (
            f"Rate or token limit reached (429){where}. Your per-participant token budget refills "
            f"every minute.{wait}"
        )
    if status and status >= 500:
        return f"The backend returned {status}{where}. Retry once; if it persists, tell the presenter."
    names = " ".join(type(c).__name__ for c in _iter_causes(exc)).lower()
    text = str(exc).lower()
    if "mcp" in names or "mcp" in text or "mcp" in component.lower():
        return (
            f"MCP handshake/tool call failed{where}: {exc}. Check `uv run poe mcp-tools`; the MCP endpoint is "
            "${APIM_BASE_URL}/care-tools/mcp and needs the Ocp-Apim-Subscription-Key header."
        )
    if "connect" in names or "timeout" in names or "name or service not known" in text:
        return f"Cannot reach the gateway{where}: {exc}. Check APIM_BASE_URL and your network/proxy."
    return f"{type(exc).__name__}{where}: {exc}"


def is_retryable(exc: BaseException) -> bool:
    status, _ = http_status_of(exc)
    return status in (429, 500, 502, 503, 504)


async def retry_async(
    fn: Callable[[], Awaitable[T]],
    *,
    attempts: int = 3,
    default_wait: float = 5.0,
    max_wait: float = 30.0,
    on_retry: Callable[[int, float, BaseException], None] | None = None,
) -> T:
    """Retry 429/5xx; max_wait caps fallback backoff, never the server's Retry-After."""
    for attempt in range(1, attempts + 1):
        try:
            return await fn()
        except Exception as exc:  # noqa: BLE001 - we re-raise below
            if attempt == attempts or not is_retryable(exc):
                raise
            _, retry_after = http_status_of(exc)
            wait = retry_after if retry_after is not None else min(max_wait, default_wait * attempt)
            wait += random.uniform(0, 0.5)
            if on_retry:
                on_retry(attempt, wait, exc)
            await asyncio.sleep(wait)
    raise RuntimeError("unreachable")
