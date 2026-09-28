"""`uv run poe lab3` — a prior-auth policy question delegated over A2A, with citations."""

from __future__ import annotations

import asyncio
import sys

from .a2a_delegate import DELEGATIONS, POLICY_TOOL_NAME, close_policy_experts, extract_citations
from .agent import build_agent, run_turn
from .config import ConfigError, get_settings
from .errors import LabIncomplete, explain
from .telemetry import setup_telemetry, shutdown_telemetry
from .ui import banner, console, print_error, render_record

QUESTION = (
    "Patient P-1042 is covered by Northwind Health Plan. Does a cardiac MRI (procedure code CARD-MRI) "
    "need prior authorization, and what does our policy say about how to request it? Cite the policy."
)


async def run() -> int:
    try:
        settings = get_settings()
    except ConfigError as exc:
        print_error(str(exc))
        return 1
    banner(settings, subtitle="Lab 3 — multi-agent via A2A")
    setup_telemetry(settings)
    try:
        handle = build_agent(settings)
        if not handle.tool_info["a2a"]:
            raise LabIncomplete(3, "src/care_agent/a2a_delegate.py → create_policy_expert_tool()")
        console().print(f"[bold]Question:[/] {QUESTION}\n")
        async with handle.agent as agent:
            with console().status("agent working (delegating over A2A)…"):
                record = await run_turn(agent, QUESTION, settings=settings, version=handle.version,
                                        attributes={"workshop.lab": "lab3"})
    except LabIncomplete as exc:
        console().print(f"[yellow]{exc}[/]")
        return 0
    except Exception as exc:  # noqa: BLE001
        print_error(explain(exc, component="Lab 3"))
        return 1
    finally:
        await close_policy_experts()
        shutdown_telemetry()

    render_record(record)
    console().rule("What crossed the A2A boundary")
    if not DELEGATIONS:
        console().print(f"[yellow]The agent did not call {POLICY_TOOL_NAME}. Try rephrasing, or check the tool description.[/]")
    for delegation in DELEGATIONS:
        console().print(f"[magenta]→ {delegation['remote_agent']}[/] ({delegation['latency_ms']:.0f} ms): {delegation['question']}")
        console().print(f"  citations from the remote agent: {', '.join(delegation['citations']) or '[red]none[/]'}")
    final_citations = extract_citations(record.response)
    console().print(f"[bold]Citations in the final answer:[/] {', '.join(final_citations) or '[red]none[/]'}")
    return 0


def main() -> int:
    return asyncio.run(run())


if __name__ == "__main__":
    sys.exit(main())
