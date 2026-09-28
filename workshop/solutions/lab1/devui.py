"""`uv run poe devui` — the same agent in Agent Framework DevUI (a local debug web UI).

DevUI is a pre-release sample app (agent-framework-devui), not a production surface.
Install it with `uv sync --extra devui`. Fallback if it is unavailable: `uv run poe chat`.
"""

from __future__ import annotations

import os
import secrets
import sys

from .config import ConfigError, get_settings
from .errors import LabIncomplete
from .telemetry import setup_telemetry


def main() -> int:
    try:
        settings = get_settings()
    except ConfigError as exc:
        print(f"✗ {exc}")
        return 1
    try:
        from agent_framework.devui import serve
    except ImportError:
        print("DevUI is not installed. Run `uv sync --extra devui` (preview package) or use `uv run poe chat`.")
        return 1
    setup_telemetry(settings)
    try:
        from .agent import build_agent

        handle = build_agent(settings)
    except LabIncomplete as exc:
        print(exc)
        return 0
    # Do NOT `async with` the agent here: DevUI connects MCP tools lazily and cleans them up itself.
    auth_token = os.getenv("DEVUI_AUTH_TOKEN") or secrets.token_urlsafe(32)
    print("Training use only — synthetic data. Opening DevUI on http://127.0.0.1:8080 …")
    print(f"DevUI access token: {auth_token}", flush=True)
    print("Paste this token into DevUI's authentication prompt (not your APIM subscription key). Keep it private.")
    serve(
        entities=[handle.agent], host="127.0.0.1", port=8080, auto_open=True,
        auth_enabled=True, auth_token=auth_token,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
