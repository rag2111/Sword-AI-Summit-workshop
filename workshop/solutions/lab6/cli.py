"""`uv run poe chat` — interactive CLI chat with the Care Coordination Agent.

Commands:  /tools  list the agent's tools     /trace  show the last trace (Lab 4)
           /reset  start a new conversation   /help   this help      /exit  quit
"""

from __future__ import annotations

import asyncio
import sys

from .a2a_delegate import DELEGATIONS, close_policy_experts
from .agent import build_agent, new_session, run_turn
from .config import ConfigError, get_settings
from .errors import LabIncomplete, explain
from .telemetry import kql_queries, load_trace_spans, setup_telemetry, shutdown_telemetry
from .ui import banner, console, print_error, render_record, render_trace_tree, tools_table

HELP = "[bold]/tools[/] list tools · [bold]/trace[/] last trace · [bold]/reset[/] new conversation · [bold]/exit[/] quit"


async def _show_tools(handle) -> None:
    rows = [(name, "local Python function") for name in handle.tool_info["local"]]
    if handle.mcp_tool is not None:
        functions = getattr(handle.mcp_tool, "functions", None) or []
        rows += [(fn.name, f"MCP · {fn.description or ''}".strip()) for fn in functions]
        if not functions:
            rows.append(("care_tools", f"MCP server (not connected yet) · {handle.tool_info['mcp']}"))
    else:
        rows.append(("—", "MCP tools arrive in Lab 2"))
    if handle.tool_info["a2a"]:
        rows.append(("ask_policy_expert", f"A2A sub-agent · {handle.tool_info['a2a']}"))
    else:
        rows.append(("—", "A2A policy expert arrives in Lab 3"))
    console().print(tools_table(rows, title=f"Tools of {handle.agent.name if handle.agent else 'agent'}"))


def _show_trace(last_record, participant_id: str) -> None:
    if last_record is None or not last_record.trace_id:
        console().print("[yellow]No trace yet.[/] Complete Lab 4 (telemetry.py), then ask a question.")
        return
    render_trace_tree(load_trace_spans(last_record.trace_id), title=f"trace {last_record.trace_id}")
    query = kql_queries(participant_id, last_record.trace_id)["One trace, end to end (client + APIM + backends)"]
    console().print(f"[dim]App Insights KQL:[/]\n{query}")


async def chat() -> int:
    try:
        settings = get_settings()
    except ConfigError as exc:
        print_error(str(exc))
        return 1
    banner(settings)
    status = setup_telemetry(settings)
    console().print(f"[dim]telemetry: {status.mode} — {status.detail}[/]")
    try:
        handle = build_agent(settings)
    except LabIncomplete as exc:
        console().print(f"[yellow]{exc}[/]")
        return 0
    console().print(f"[dim]agent version {handle.version} ({handle.instructions_hash}) · {HELP}[/]\n")

    last_record = None
    try:
        async with handle.agent as agent:
            session = new_session(agent)
            while True:
                try:
                    text = console().input("[bold cyan]you ›[/] ").strip()
                except (EOFError, KeyboardInterrupt):
                    break
                if not text:
                    continue
                command = text.lower()
                if command in ("/exit", "/quit", "exit", "quit"):
                    break
                if command == "/help":
                    console().print(HELP)
                    continue
                if command == "/tools":
                    await _show_tools(handle)
                    continue
                if command == "/trace":
                    _show_trace(last_record, settings.participant_id)
                    continue
                if command == "/reset":
                    session = new_session(agent)
                    console().print("[dim]New conversation started.[/]")
                    continue
                delegations_before = len(DELEGATIONS)
                try:
                    with console().status("thinking…"):
                        last_record = await run_turn(agent, text, session=session, settings=settings, version=handle.version)
                except LabIncomplete as exc:
                    console().print(f"[yellow]{exc}[/]")
                    continue
                except Exception as exc:  # noqa: BLE001 - keep the chat alive
                    print_error(explain(exc))
                    continue
                console().print("[bold green]agent ›[/]")
                render_record(last_record)
                for delegation in DELEGATIONS[delegations_before:]:
                    cites = "; ".join(delegation["citations"]) or "none"
                    console().print(f"[magenta]A2A → {delegation['remote_agent']}[/] [dim]citations: {cites}[/]")
                console().print()
    except Exception as exc:  # noqa: BLE001 - e.g. MCP handshake failure while connecting
        print_error(explain(exc, component="agent startup"))
        return 1
    finally:
        await close_policy_experts()
        shutdown_telemetry()
    console().print("[dim]Bye. Remember: synthetic data only.[/]")
    return 0


def main() -> int:
    return asyncio.run(chat())


if __name__ == "__main__":
    sys.exit(main())
