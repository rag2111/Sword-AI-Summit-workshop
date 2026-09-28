"""`uv run poe lab2` — a scripted multi-step task through the managed MCP endpoint."""

from __future__ import annotations

import asyncio
import sys

from .agent import build_agent, run_turn
from .config import ConfigError, get_settings
from .errors import LabIncomplete, explain
from .telemetry import setup_telemetry, shutdown_telemetry
from .ui import banner, console, print_error, render_record

TASK = "Plan discharge for patient P-1042 and book a cardiology follow-up within 7 days."
EXPECTED_STEPS = ("get_care_plan", "list_available_slots", "book_follow_up")


def check_steps(tool_names: list[str]) -> list[tuple[str, bool]]:
    """Did the agent use each expected tool, in a sensible order? (pure; unit-tested)"""
    results, position = [], -1
    for step in EXPECTED_STEPS:
        index = next((i for i, name in enumerate(tool_names) if name.endswith(step) and i > position), None)
        results.append((step, index is not None))
        position = index if index is not None else position
    return results


async def run() -> int:
    try:
        settings = get_settings()
    except ConfigError as exc:
        print_error(str(exc))
        return 1
    banner(settings, subtitle="Lab 2 — tools via managed MCP endpoint")
    setup_telemetry(settings)
    try:
        handle = build_agent(settings)
        if handle.mcp_tool is None:
            raise LabIncomplete(2, "src/care_agent/tools_mcp.py → create_mcp_tool()")
        console().print(f"[bold]Task:[/] {TASK}\n")
        async with handle.agent as agent:
            with console().status("agent working (MCP tools through APIM)…"):
                record = await run_turn(agent, TASK, settings=settings, version=handle.version,
                                        attributes={"workshop.lab": "lab2"})
    except LabIncomplete as exc:
        console().print(f"[yellow]{exc}[/]")
        return 0
    except Exception as exc:  # noqa: BLE001
        print_error(explain(exc, component="Lab 2"))
        return 1
    finally:
        shutdown_telemetry()
    render_record(record)
    console().rule("What you just proved")
    for step, ok in check_steps([c["name"] for c in record.tool_calls]):
        console().print(f"{'[green]✓' if ok else '[red]✗'}[/] {step}")
    return 0


def main() -> int:
    return asyncio.run(run())


if __name__ == "__main__":
    sys.exit(main())
