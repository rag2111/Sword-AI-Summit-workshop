"""PRESENTER-ONLY production runtime demo: host the Care Coordination Agent behind a Responses endpoint.

Participants never need this. It shows where the agent goes after "it works on my laptop":
the same `build_agent()` (same instructions version, same APIM routes, same telemetry) served by
Agent Framework's hosting adapter, as a Foundry hosted agent (PREVIEW) or on Azure Container Apps.

    POST http://localhost:8088/responses   {"input": "Plan discharge for patient P-1042 ..."}

Runtime configuration comes from the container environment (APIM_BASE_URL, APIM_SUBSCRIPTION_KEY from a
secret / Key Vault reference, PARTICIPANT_ID=presenter-hosted). Never bake keys into the image.
"""

from __future__ import annotations

import sys

from care_agent import DISCLAIMER
from care_agent.agent import build_agent
from care_agent.config import get_settings
from care_agent.telemetry import setup_telemetry


def main() -> int:
    settings = get_settings()
    status = setup_telemetry(settings)
    print(f"{DISCLAIMER}\ntelemetry: {status.mode} — {status.detail}")
    handle = build_agent(settings)
    try:
        # PREVIEW package agent-framework-foundry-hosting (deploy/requirements.txt), protocol 2.0.0.
        from agent_framework.foundry import ResponsesHostServer
    except ImportError:
        print("agent-framework-foundry-hosting is not installed: pip install -r deploy/requirements.txt")
        return 1
    # history_source="agent": our agent keeps its own session history; hosting passes only the new input.
    server = ResponsesHostServer(handle.agent, history_source="agent")
    server.run()  # listens on :8088 (Foundry hosted-agent contract; also fine on Container Apps)
    return 0


if __name__ == "__main__":
    sys.exit(main())
