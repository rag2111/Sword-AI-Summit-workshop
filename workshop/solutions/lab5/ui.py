"""Small `rich` helpers shared by the CLI and the lab scripts (banner, tables, trace tree)."""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from . import CHECKPOINT, DISCLAIMER, TITLE


@lru_cache(maxsize=1)
def console() -> Any:
    from rich.console import Console

    return Console()


def print_error(message: str) -> None:
    console().print(f"[bold red]✗[/] {message}")


def print_json(text: str) -> None:
    from rich.json import JSON

    console().print(JSON(text))


def banner(settings: Any, subtitle: str = "Care Coordination Agent") -> None:
    from rich.panel import Panel

    lines = [
        f"[bold]{TITLE}[/]",
        f"{subtitle} · Lakeside Regional Health Network (fictional)",
        "",
        f"[yellow]{DISCLAIMER.replace('**', '')}[/]",
        "",
        f"participant [cyan]{settings.participant_id}[/] · checkpoint [cyan]{CHECKPOINT}[/] · "
        f"model [cyan]{settings.chat_model}[/] · gateway [cyan]{settings.apim_base_url}[/]",
    ]
    console().print(Panel("\n".join(lines), border_style="blue"))
    for warning in settings.warnings:
        console().print(f"[yellow]! {warning}[/]")


def tools_table(tools: list[tuple[str, str]], title: str) -> Any:
    from rich.table import Table

    table = Table(title=title, show_lines=False)
    table.add_column("Tool", style="cyan", no_wrap=True)
    table.add_column("Description")
    for name, description in tools:
        table.add_row(name, description[:120])
    return table


def render_record(record: Any, *, show_answer: bool = True) -> None:
    """Pretty-print a RunRecord: tool calls, answer, tokens, latency and trace ID."""
    from rich.markdown import Markdown
    from rich.table import Table

    out = console()
    if record.tool_calls:
        table = Table(title="Tool calls (in order)")
        table.add_column("#", justify="right")
        table.add_column("Tool", style="cyan")
        table.add_column("Arguments")
        for index, call in enumerate(record.tool_calls, start=1):
            table.add_row(str(index), call["name"], json.dumps(call["arguments"], ensure_ascii=False)[:100])
        out.print(table)
    if show_answer:
        out.print(Markdown(record.response or "_(empty response)_"))
    out.print(
        f"[dim]tokens in/out {record.input_tokens}/{record.output_tokens} · {record.latency_ms:.0f} ms · "
        f"version {record.agent_version} · trace {record.trace_id or 'n/a (complete Lab 4)'}[/]"
    )


def render_trace_tree(spans: list[dict[str, Any]], title: str) -> None:
    from rich.tree import Tree

    from .telemetry import build_span_tree

    if not spans:
        console().print("[dim]No local spans for this trace (complete Lab 4, spans flush every few seconds).[/]")
        return
    root = Tree(f"[bold]{title}[/]")
    nodes: dict[int, Any] = {-1: root}
    for depth, span in build_span_tree(spans):
        attrs = span.get("attributes", {})
        extra = []
        for key in ("gen_ai.request.model", "gen_ai.usage.input_tokens", "gen_ai.usage.output_tokens", "gen_ai.tool.name"):
            if key in attrs:
                extra.append(f"{key.split('.')[-1]}={attrs[key]}")
        label = f"[cyan]{span['name']}[/] [dim]{span['duration_ms']} ms {' '.join(extra)}[/]"
        parent = nodes.get(depth - 1, root)
        nodes[depth] = parent.add(label)
    console().print(root)
