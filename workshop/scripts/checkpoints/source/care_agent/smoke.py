"""`uv run poe smoke` — Lab 0: prove you can reach all five APIM routes with only your key.

    /openai              one tiny chat completion (model behind APIM, managed identity to Foundry)
    /care-tools/mcp      MCP initialize + tools/list (REST API exposed as an MCP server)
    /a2a/care-knowledge  Agent Card of the base knowledge agent
    /telemetry           /telemetry/config + one test event through the ingestion proxy
    /foundry             read the base agent's metadata from the Foundry project
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from .config import ConfigError, Settings, get_settings
from .errors import explain
from .telemetry import parse_connection_string

MCP_PROTOCOL_VERSION = "2025-06-18"


@dataclass
class Check:
    route: str
    ok: bool
    detail: str


def parse_mcp_payload(body: str, content_type: str) -> dict[str, Any]:
    """MCP Streamable HTTP answers with JSON or with an SSE stream; return the JSON-RPC message."""
    if "text/event-stream" not in (content_type or ""):
        return json.loads(body)
    messages = [line[5:].strip() for line in body.splitlines() if line.startswith("data:")]
    for message in reversed(messages):
        if message:
            data = json.loads(message)
            if "result" in data or "error" in data:
                return data
    raise ValueError("No JSON-RPC result in the SSE stream")


def check_openai(client: Any, s: Settings) -> Check:
    url = f"{s.openai_endpoint}/openai/deployments/{s.chat_model}/chat/completions?api-version={s.openai_api_version}"
    body = {
        "messages": [{"role": "user", "content": "Reply with the single word: ready"}],
        "max_completion_tokens": 5,
    }
    response = client.post(url, json=body)
    response.raise_for_status()
    answer = response.json()["choices"][0]["message"]["content"].strip()
    return Check("/openai", True, f"{s.chat_model} answered {answer!r}")


def check_mcp(client: Any, s: Settings) -> Check:
    headers = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
    init = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": MCP_PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "care-agent-smoke", "version": "1.0"},
        },
    }
    response = client.post(s.mcp_url, json=init, headers=headers)
    response.raise_for_status()
    parse_mcp_payload(response.text, response.headers.get("content-type", ""))
    session_headers = dict(headers, **{"MCP-Protocol-Version": MCP_PROTOCOL_VERSION})
    if session_id := response.headers.get("mcp-session-id"):
        session_headers["Mcp-Session-Id"] = session_id
    client.post(s.mcp_url, json={"jsonrpc": "2.0", "method": "notifications/initialized"}, headers=session_headers)
    listed = client.post(s.mcp_url, json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, headers=session_headers)
    listed.raise_for_status()
    tools = parse_mcp_payload(listed.text, listed.headers.get("content-type", "")).get("result", {}).get("tools", [])
    names = sorted(t["name"] for t in tools)
    return Check("/care-tools/mcp", len(names) >= 7, f"{len(names)} tools: {', '.join(names)}")


def check_a2a(client: Any, s: Settings) -> Check:
    response = client.get(s.a2a_agent_card_url)
    if response.status_code == 404:
        return Check("/a2a/care-knowledge", False, "Agent Card not found (404) — tell the presenter")
    response.raise_for_status()
    card = response.json()
    skills = [skill.get("name") or skill.get("id") for skill in card.get("skills", []) or []]
    return Check("/a2a/care-knowledge", True, f"Agent Card '{card.get('name')}' · skills: {', '.join(skills) or '-'}")


def check_telemetry(client: Any, s: Settings) -> Check:
    response = client.get(s.telemetry_config_url)
    response.raise_for_status()
    connection = parse_connection_string(response.json().get("connectionString", ""))
    ikey = connection.get("instrumentationkey")
    if not ikey:
        return Check("/telemetry", False, "/telemetry/config returned no InstrumentationKey")
    envelope = [
        {
            "name": "Microsoft.ApplicationInsights.Event",
            "time": datetime.now(UTC).isoformat(),
            "iKey": ikey,
            "tags": {"ai.cloud.role": s.participant_id},
            "data": {
                "baseType": "EventData",
                "baseData": {"ver": 2, "name": "workshop-smoke", "properties": {"participant.id": s.participant_id}},
            },
        }
    ]
    track = client.post(f"{s.apim_base_url}/telemetry/v2.1/track", json=envelope)
    track.raise_for_status()
    accepted = track.json().get("itemsAccepted", "?")
    return Check("/telemetry", True, f"config OK · test event accepted: {accepted}")


def check_foundry(client: Any, s: Settings) -> Check:
    if not s.foundry_project_endpoint:
        return Check("/foundry", False, "Foundry project name unknown (set FOUNDRY_PROJECT_NAME)")
    # APIM strips this placeholder Authorization header and uses its managed identity (CONTRACT §5).
    headers = {"Authorization": "Bearer apim-uses-its-own-managed-identity"}
    response = client.get(f"{s.foundry_project_endpoint}/agents/care-knowledge-agent?api-version=v1", headers=headers)
    response.raise_for_status()
    data = response.json()
    version = (data.get("versions") or {}).get("latest", {}).get("version") or data.get("version") or "?"
    return Check("/foundry", True, f"base agent '{data.get('name', 'care-knowledge-agent')}' (latest version {version})")


CHECKS = (check_openai, check_mcp, check_a2a, check_telemetry, check_foundry)
ROUTES = ("/openai", "/care-tools/mcp", "/a2a/care-knowledge", "/telemetry", "/foundry")


def run_checks(settings: Settings) -> list[Check]:
    import httpx

    results: list[Check] = []
    with httpx.Client(timeout=45, headers=settings.apim_headers()) as client:
        for route, check in zip(ROUTES, CHECKS, strict=True):
            try:
                results.append(check(client, settings))
            except Exception as exc:  # noqa: BLE001 - one failing route must not hide the others
                results.append(Check(route, False, explain(exc, component=route)))
    return results


def main() -> int:
    from rich.table import Table

    from .ui import banner, console, print_error

    try:
        settings = get_settings()
    except ConfigError as exc:
        print_error(str(exc))
        return 1
    banner(settings, subtitle="Lab 0 — smoke test")
    table = Table(title="APIM routes")
    table.add_column("Route", style="cyan")
    table.add_column("Result")
    table.add_column("Detail")
    results = run_checks(settings)
    for result in results:
        table.add_row(result.route, "[green]PASS[/]" if result.ok else "[red]FAIL[/]", result.detail)
    console().print(table)
    if all(r.ok for r in results):
        console().print("[bold green]✓ All five routes work with nothing but your subscription key.[/]")
        return 0
    console().print("[yellow]Some routes failed — see docs/troubleshooting.md, or ask a helper.[/]")
    return 1


if __name__ == "__main__":
    sys.exit(main())
