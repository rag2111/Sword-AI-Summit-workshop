"""Lab 2 — tools behind ONE managed MCP endpoint.

APIM exposes the mock clinical REST API (`care-tools-api`) as an MCP server at
`${APIM_BASE_URL}/care-tools/mcp`. The agent does not know where the backend runs, how it is
authenticated, or that it is REST underneath: it only sees MCP tools. The gateway adds
rate limits, the `x-participant-id` header and telemetry for every tool call.

Run `uv run poe mcp-tools` to list the tools.
"""

from __future__ import annotations

import asyncio
import sys
from typing import Any

from .config import Settings, get_settings
from .errors import LabIncomplete, explain

# CONTRACT section 3: operationIds == MCP tool names.
EXPECTED_TOOLS = (
    "search_patient",
    "get_care_plan",
    "list_available_slots",
    "book_follow_up",
    "create_referral",
    "check_medication_interactions",
    "check_prior_auth_requirement",
)


def create_mcp_tool(settings: Settings) -> Any:
    """Return an MCPStreamableHTTPTool for the managed endpoint (or None before Lab 2)."""
    # [lab2:solution]
    from agent_framework import MCPStreamableHTTPTool

    return MCPStreamableHTTPTool(
        name="care_tools",
        description="Lakeside care-coordination tools (synthetic data) behind the APIM managed MCP endpoint.",
        url=settings.mcp_url,
        # The key is fixed for the process, so static headers (not a header_provider) are right here.
        static_headers=settings.apim_headers(),
        load_prompts=False,  # APIM MCP servers expose tools only (no prompts/resources)
        request_timeout=30,
    )
    # [lab2:starter]
    # TODO (Lab 2): connect the agent to the managed MCP endpoint.
    #   from agent_framework import MCPStreamableHTTPTool
    #   return MCPStreamableHTTPTool(
    #       name="care_tools",
    #       description="Lakeside care-coordination tools behind the APIM managed MCP endpoint.",
    #       url=settings.mcp_url,                     # ${APIM_BASE_URL}/care-tools/mcp
    #       static_headers=settings.apim_headers(),   # Ocp-Apim-Subscription-Key authenticates you
    #       load_prompts=False,                       # APIM MCP = tools only
    #       request_timeout=30,
    #   )
    return None
    # [lab2:end]


async def list_mcp_tools(settings: Settings) -> list[tuple[str, str]]:
    """Connect (MCP initialize + tools/list) and return (name, description) pairs."""
    tool = create_mcp_tool(settings)
    if tool is None:
        raise LabIncomplete(2, "src/care_agent/tools_mcp.py → create_mcp_tool()")
    async with tool as mcp:
        return [(fn.name, (fn.description or "").strip()) for fn in mcp.functions]


def main() -> int:
    from .ui import console, print_error, tools_table

    try:
        settings = get_settings()
        tools = asyncio.run(list_mcp_tools(settings))
    except LabIncomplete as exc:
        console().print(f"[yellow]{exc}[/]")
        return 0
    except Exception as exc:  # noqa: BLE001
        print_error(explain(exc, component="MCP /care-tools/mcp"))
        return 1
    console().print(tools_table(tools, title=f"MCP tools at {settings.mcp_url}"))
    missing = [name for name in EXPECTED_TOOLS if name not in {n for n, _ in tools}]
    if missing:
        console().print(f"[yellow]Missing expected tools:[/] {', '.join(missing)}")
        return 1
    console().print(f"[green]✓ All {len(EXPECTED_TOOLS)} expected tools are available through APIM.[/]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
