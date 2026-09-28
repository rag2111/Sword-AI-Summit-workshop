"""Workshop settings: three values in, everything else derived (CONTRACT section 4).

Participants set only APIM_BASE_URL, APIM_SUBSCRIPTION_KEY and PARTICIPANT_ID. Every other endpoint
is a path on the same API Management gateway, so we derive it here. Values that only the platform
knows (Application Insights connection string, Foundry project name) come from
`GET ${APIM_BASE_URL}/telemetry/config`, unless you override them in .env.

This module uses only the standard library (plus optional python-dotenv) so it is easy to test.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from functools import lru_cache
from pathlib import Path
from typing import Any

# workshop/ root (src/care_agent/config.py -> parents[2]; solutions/labN/config.py has the same depth)
WORKSHOP_ROOT = Path(__file__).resolve().parents[2]
STATE_DIR = WORKSHOP_ROOT / ".care_agent"  # local, git-ignored run state (last trace IDs, ...)

# Azure OpenAI data-plane API version used through APIM /openai (GA). The gateway also exposes
# /openai/v1/*; switch by setting OPENAI_API_VERSION if your presenter asks you to.
DEFAULT_OPENAI_API_VERSION = "2024-10-21"
DEFAULT_CHAT_MODEL = "gpt-6-luna"
DEFAULT_JUDGE_MODEL = "gpt-6-sol"
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-large"

REQUIRED = ("APIM_BASE_URL", "APIM_SUBSCRIPTION_KEY", "PARTICIPANT_ID")
PARTICIPANT_ID_PATTERN = re.compile(r"^user[0-9]{2}$")

# Header names (CONTRACT section 2): send both on every call; harmless and simpler.
SUBSCRIPTION_KEY_HEADER = "Ocp-Apim-Subscription-Key"
OPENAI_KEY_HEADER = "api-key"


class ConfigError(RuntimeError):
    """Raised when the three participant values are missing or still placeholders."""


@dataclass(frozen=True)
class Settings:
    apim_base_url: str
    subscription_key: str = field(repr=False)
    participant_id: str
    openai_endpoint: str
    openai_api_version: str
    chat_model: str
    judge_model: str
    embedding_model: str
    chat_api: str  # "chat_completions" (default, most compatible) or "responses"
    mcp_url: str
    a2a_agent_card_url: str
    foundry_project_name: str | None
    foundry_project_endpoint: str | None
    appinsights_connection_string: str | None = field(repr=False)
    enable_sensitive_data: bool = False
    telemetry_console: bool = False
    warnings: tuple[str, ...] = ()

    @property
    def a2a_base_url(self) -> str:
        """Base URL of the A2A API (the Agent Card URL without the well-known suffix)."""
        return self.a2a_agent_card_url.split("/.well-known/")[0].rstrip("/")

    @property
    def telemetry_config_url(self) -> str:
        return f"{self.apim_base_url}/telemetry/config"

    def apim_headers(self) -> dict[str, str]:
        return apim_headers(self.subscription_key)

    def redacted_key(self) -> str:
        key = self.subscription_key
        return f"{key[:4]}…{key[-2:]}" if len(key) > 9 else "****"


def apim_headers(key: str) -> dict[str, str]:
    """Both subscription-key header names accepted by the workshop APIs."""
    return {SUBSCRIPTION_KEY_HEADER: key, OPENAI_KEY_HEADER: key}


def _is_placeholder(value: str) -> bool:
    return not value or "<" in value or ">" in value or value.strip() in {"user00", "user00-xxx"}


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def normalize_base_url(url: str) -> str:
    """Strip whitespace, quotes and trailing slashes; APIM_BASE_URL must be the gateway root."""
    url = url.strip().strip('"').strip("'").rstrip("/")
    for suffix in ("/openai", "/care-tools/mcp", "/foundry"):
        if url.endswith(suffix):
            url = url[: -len(suffix)]
    return url


def fetch_telemetry_config(base_url: str, key: str, timeout: float = 10.0) -> dict[str, Any]:
    """GET ${APIM_BASE_URL}/telemetry/config -> connectionString, foundryProjectName, chatModel, judgeModel."""
    request = urllib.request.Request(
        f"{base_url}/telemetry/config", headers={**apim_headers(key), "Accept": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - https gateway URL
        return json.loads(response.read().decode("utf-8"))


def derive_settings(
    env: Mapping[str, str],
    fetch_remote: Callable[[str, str], dict[str, Any]] | None = fetch_telemetry_config,
) -> Settings:
    """Build Settings from an environment mapping. Pure function except for the optional fetch."""
    missing = [name for name in REQUIRED if _is_placeholder(env.get(name, ""))]
    if missing:
        raise ConfigError(
            "Missing or placeholder values in .env: "
            + ", ".join(missing)
            + ". Copy .env.example to .env and paste the three values from your participant card."
        )

    base = normalize_base_url(env["APIM_BASE_URL"])
    if not base.startswith("https://"):
        raise ConfigError(f"APIM_BASE_URL must start with https:// (got {base!r}).")
    key = env["APIM_SUBSCRIPTION_KEY"].strip().strip('"').strip("'")
    participant = env["PARTICIPANT_ID"].strip()

    warnings: list[str] = []
    if not PARTICIPANT_ID_PATTERN.match(participant):
        warnings.append(f"PARTICIPANT_ID {participant!r} does not look like 'user07'.")

    project_name = env.get("FOUNDRY_PROJECT_NAME") or None
    project_endpoint = env.get("FOUNDRY_PROJECT_ENDPOINT") or None
    conn_str = env.get("APPLICATIONINSIGHTS_CONNECTION_STRING") or None
    chat_model = env.get("CHAT_MODEL") or None
    judge_model = env.get("JUDGE_MODEL") or None

    # Only call /telemetry/config when something is still unknown.
    if fetch_remote and (not conn_str or not (project_endpoint or project_name)):
        try:
            remote = fetch_remote(base, key) or {}
            conn_str = conn_str or remote.get("connectionString") or None
            project_name = project_name or remote.get("foundryProjectName") or None
            chat_model = chat_model or remote.get("chatModel") or None
            judge_model = judge_model or remote.get("judgeModel") or None
        except urllib.error.HTTPError as exc:
            warnings.append(f"GET /telemetry/config returned HTTP {exc.code}; telemetry falls back to local.")
        except Exception as exc:  # noqa: BLE001 - config must never crash the CLI
            warnings.append(f"Could not fetch /telemetry/config ({type(exc).__name__}); using local fallbacks.")

    if not project_endpoint and project_name:
        project_endpoint = f"{base}/foundry/api/projects/{project_name}"

    return Settings(
        apim_base_url=base,
        subscription_key=key,
        participant_id=participant,
        # The OpenAI SDK appends /openai/... itself, so the "endpoint" is the gateway root.
        openai_endpoint=normalize_base_url(env.get("OPENAI_ENDPOINT") or base),
        openai_api_version=env.get("OPENAI_API_VERSION") or DEFAULT_OPENAI_API_VERSION,
        chat_model=chat_model or DEFAULT_CHAT_MODEL,
        judge_model=judge_model or DEFAULT_JUDGE_MODEL,
        embedding_model=env.get("EMBEDDING_MODEL") or DEFAULT_EMBEDDING_MODEL,
        chat_api=(env.get("CHAT_API") or "chat_completions").strip().lower(),
        mcp_url=env.get("MCP_URL") or f"{base}/care-tools/mcp",
        a2a_agent_card_url=env.get("A2A_AGENT_CARD_URL")
        or f"{base}/a2a/care-knowledge/.well-known/agent-card.json",
        foundry_project_name=project_name,
        foundry_project_endpoint=project_endpoint,
        appinsights_connection_string=conn_str,
        enable_sensitive_data=_truthy(env.get("ENABLE_SENSITIVE_DATA")),
        telemetry_console=_truthy(env.get("TELEMETRY_CONSOLE")),
        warnings=tuple(warnings),
    )


def load_env_file(path: Path | None = None) -> None:
    """Load workshop/.env into os.environ (existing variables win)."""
    path = path or WORKSHOP_ROOT / ".env"
    try:
        from dotenv import load_dotenv
    except ImportError:  # tiny fallback parser so tests do not need python-dotenv
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    name, _, value = line.partition("=")
                    os.environ.setdefault(name.strip(), value.split(" #")[0].strip())
        return
    load_dotenv(path, override=False)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Settings for the current process (cached). Raises ConfigError with a helpful message."""
    load_env_file()
    return derive_settings(os.environ)


def with_overrides(settings: Settings, **changes: Any) -> Settings:
    return replace(settings, **changes)
