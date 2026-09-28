"""Minimal LLM-judge / generator helper: chat completions and embeddings through APIM /openai.

Used by the custom evaluator, the red-team generator and the Lab 6 loop. Plain httpx keeps the
request visible for teaching: one POST to the gateway, the key in `api-key`, JSON back.
"""

from __future__ import annotations

import json
import re
import time
from typing import Any

from care_agent.config import Settings
from care_agent.errors import http_status_of


class JudgeError(RuntimeError):
    pass


def is_reasoning_model(model: str) -> bool:
    """Recognize the workshop's reasoning-model deployment names."""
    return model in {"gpt-6-sol", "gpt-6-luna"}


def extract_json(text: str) -> Any:
    """Parse JSON from a model answer, tolerating ```json fences or leading prose."""
    text = (text or "").strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    for opener, closer in (("{", "}"), ("[", "]")):
        start, end = text.find(opener), text.rfind(closer)
        if start != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                continue
    raise JudgeError(f"Model did not return JSON: {text[:200]!r}")


def _post_with_retry(settings: Settings, url: str, body: dict[str, Any], timeout: float, attempts: int) -> dict[str, Any]:
    import httpx

    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            response = httpx.post(url, json=body, headers=settings.apim_headers(), timeout=timeout)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            last_error = exc
            status, retry_after = http_status_of(exc)
            if status not in (429, 500, 502, 503, 504) or attempt == attempts:
                raise
            time.sleep(retry_after if retry_after is not None else min(30.0, 5.0 * attempt))
        except httpx.TransportError as exc:
            last_error = exc
            if attempt == attempts:
                raise
            time.sleep(2.0 * attempt)
    raise JudgeError(str(last_error))


def chat(
    settings: Settings,
    *,
    system: str,
    user: str,
    model: str | None = None,
    json_mode: bool = True,
    temperature: float = 0.0,
    max_tokens: int = 1200,
    timeout: float = 90.0,
    attempts: int = 3,
) -> tuple[str, dict[str, int]]:
    """One chat completion via ${APIM_BASE_URL}/openai/deployments/{model}/chat/completions."""
    model = model or settings.judge_model
    url = (
        f"{settings.openai_endpoint}/openai/deployments/{model}/chat/completions"
        f"?api-version={settings.openai_api_version}"
    )
    body: dict[str, Any] = {
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
    }
    if is_reasoning_model(model):
        # Keep small JSON verdict budgets for output rather than hidden reasoning.
        body.update(max_completion_tokens=max_tokens, reasoning_effort="none")
    else:
        body.update(max_tokens=max_tokens, temperature=temperature)
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    data = _post_with_retry(settings, url, body, timeout, attempts)
    usage = data.get("usage") or {}
    return data["choices"][0]["message"]["content"] or "", {
        "input": int(usage.get("prompt_tokens", 0)),
        "output": int(usage.get("completion_tokens", 0)),
    }


def chat_json(settings: Settings, *, system: str, user: str, model: str | None = None, **kwargs: Any) -> Any:
    text, _ = chat(settings, system=system, user=user, model=model, json_mode=True, **kwargs)
    return extract_json(text)


def embed(settings: Settings, texts: list[str], model: str | None = None, timeout: float = 60.0) -> list[list[float]]:
    """Embeddings via ${APIM_BASE_URL}/openai/deployments/{embedding-model}/embeddings."""
    model = model or settings.embedding_model
    url = f"{settings.openai_endpoint}/openai/deployments/{model}/embeddings?api-version={settings.openai_api_version}"
    data = _post_with_retry(settings, url, {"input": texts}, timeout, attempts=3)
    return [item["embedding"] for item in sorted(data["data"], key=lambda d: d["index"])]
