"""Lab 4 — observability: OpenTelemetry → Azure Monitor, through APIM /telemetry.

Trace anatomy of one turn (GenAI semantic conventions, emitted by agent_framework.observability):

    care_agent.turn                       <- our span: participant.id, care_agent.version
    └─ invoke_agent care-coordination-agent
       ├─ chat gpt-6-luna               <- gen_ai.request.model, gen_ai.usage.input/output_tokens
       ├─ execute_tool get_care_plan      <- MCP call → APIM request span (W3C traceparent) → backend
       └─ execute_tool ask_policy_expert  <- A2A call → APIM → Foundry base agent

Exporters: Azure Monitor exporters with connection string IngestionEndpoint=${APIM_BASE_URL}/telemetry/
and an azure-core HeadersPolicy that adds `Ocp-Apim-Subscription-Key`. A local exporter always keeps
the last spans on disk (.care_agent/spans.jsonl) so `/trace` and `poe traces` work without portal
access. `service.name` = PARTICIPANT_ID, so App Insights `cloud_RoleName` is your participant ID.
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from . import CHECKPOINT
from .config import STATE_DIR, Settings

SPANS_FILE = STATE_DIR / "spans.jsonl"
TRACES_FILE = STATE_DIR / "last_traces.jsonl"
_KEEP_ATTRIBUTE_PREFIXES = ("gen_ai.", "participant.", "care_agent.", "workshop.", "server.", "http.", "error", "mcp.")


@dataclass
class TelemetryStatus:
    mode: str  # azure_monitor | local | off
    detail: str


_STATUS: TelemetryStatus | None = None


def parse_connection_string(connection_string: str) -> dict[str, str]:
    """'InstrumentationKey=...;IngestionEndpoint=...' -> {'instrumentationkey': ..., 'ingestionendpoint': ...}."""
    parts = (p.split("=", 1) for p in (connection_string or "").split(";") if "=" in p)
    return {key.strip().lower(): value.strip() for key, value in parts}


def telemetry_goes_through_apim(settings: Settings) -> bool:
    endpoint = parse_connection_string(settings.appinsights_connection_string or "").get("ingestionendpoint", "")
    return endpoint.rstrip("/").startswith(f"{settings.apim_base_url}/telemetry")


# ---------------------------------------------------------------------------------------------
# Local span capture (always on once telemetry is set up)
# ---------------------------------------------------------------------------------------------
def span_to_dict(span: Any) -> dict[str, Any]:
    ctx = span.get_span_context() if hasattr(span, "get_span_context") else span.context
    parent = getattr(span, "parent", None)
    attributes = dict(getattr(span, "attributes", None) or {})
    status = getattr(getattr(span, "status", None), "status_code", None)
    return {
        "trace_id": format(ctx.trace_id, "032x"),
        "span_id": format(ctx.span_id, "016x"),
        "parent_id": format(parent.span_id, "016x") if parent else None,
        "name": span.name,
        "start": span.start_time,
        "duration_ms": round(((span.end_time or span.start_time) - span.start_time) / 1e6, 1),
        "status": getattr(status, "name", None),
        "attributes": {
            k: (v if isinstance(v, (str, int, float, bool)) else str(v))
            for k, v in attributes.items()
            if k.startswith(_KEEP_ATTRIBUTE_PREFIXES)
        },
    }


def _append_jsonl(path: Any, rows: Sequence[dict[str, Any]], keep: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    lines = existing + [json.dumps(row, default=str) for row in rows]
    path.write_text("\n".join(lines[-keep:]) + "\n", encoding="utf-8")


def _local_exporter() -> Any:
    from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult

    class LocalSpanExporter(SpanExporter):
        """Writes finished spans to .care_agent/spans.jsonl (last 2,000)."""

        def export(self, spans: Sequence[Any]) -> Any:
            try:
                _append_jsonl(SPANS_FILE, [span_to_dict(s) for s in spans], keep=2000)
            except Exception:  # noqa: BLE001 - never break the app because of local telemetry
                pass
            return SpanExportResult.SUCCESS

        def shutdown(self) -> None:
            pass

    return LocalSpanExporter()


def _participant_processor(settings: Settings) -> Any:
    from opentelemetry.sdk.trace import SpanProcessor

    class ParticipantSpanProcessor(SpanProcessor):
        """Stamp every span with participant.id so any query can filter by participant."""

        def on_start(self, span: Any, parent_context: Any = None) -> None:
            span.set_attribute("participant.id", settings.participant_id)
            span.set_attribute("workshop.checkpoint", CHECKPOINT)

    return ParticipantSpanProcessor()


def build_azure_monitor_exporters(settings: Settings) -> list[Any]:
    """Trace/log/metric exporters that send to APIM /telemetry with the subscription key header."""
    from azure.monitor.opentelemetry.exporter import (
        AzureMonitorLogExporter,
        AzureMonitorMetricExporter,
        AzureMonitorTraceExporter,
    )

    from .apim_auth import make_headers_policy

    common: dict[str, Any] = {
        "connection_string": settings.appinsights_connection_string,
        "disable_offline_storage": True,  # no local retry cache on laptops
        # The exporter builds an azure-core pipeline; our HeadersPolicy replaces the default one.
        "headers_policy": make_headers_policy(settings.subscription_key),
    }
    return [AzureMonitorTraceExporter(**common), AzureMonitorLogExporter(**common), AzureMonitorMetricExporter(**common)]


def _prepare_environment(settings: Settings) -> None:
    os.environ.setdefault("OTEL_SERVICE_NAME", settings.participant_id)
    extra = f"participant.id={settings.participant_id},workshop.name=care-coordination"
    current = os.environ.get("OTEL_RESOURCE_ATTRIBUTES", "")
    if "participant.id=" not in current:
        os.environ["OTEL_RESOURCE_ATTRIBUTES"] = f"{current},{extra}".strip(",")
    os.environ.setdefault("ENABLE_SENSITIVE_DATA", "true" if settings.enable_sensitive_data else "false")
    os.environ.setdefault("ENABLE_CONSOLE_EXPORTERS", "true" if settings.telemetry_console else "false")
    # Statsbeat would send SDK usage stats directly to Microsoft, bypassing APIM: turn it off.
    os.environ.setdefault("APPLICATIONINSIGHTS_STATSBEAT_DISABLED_ALL", "true")


def setup_telemetry(settings: Settings) -> TelemetryStatus:
    """Configure OpenTelemetry once per process. Safe to call repeatedly."""
    global _STATUS
    if _STATUS is not None:
        return _STATUS
    _prepare_environment(settings)
    # TODO (Lab 4): send traces to Azure Monitor through APIM and keep a local copy.
    #   1. exporters = build_azure_monitor_exporters(settings)   (if a connection string is set)
    #   2. exporters.append(_local_exporter())
    #   3. from agent_framework.observability import configure_otel_providers, enable_instrumentation
    #      configure_otel_providers(exporters=exporters); enable_instrumentation()
    #   4. trace.get_tracer_provider().add_span_processor(_participant_processor(settings))
    #   5. return TelemetryStatus("azure_monitor", "...")
    _STATUS = TelemetryStatus("off", "Telemetry not configured yet — complete Lab 4 in src/care_agent/telemetry.py.")
    return _STATUS


def shutdown_telemetry() -> None:
    """Flush spans before the process exits (short-lived commands would otherwise lose them)."""
    try:
        from opentelemetry import trace

        provider = trace.get_tracer_provider()
        if hasattr(provider, "force_flush"):
            provider.force_flush(timeout_millis=5000)
    except Exception:  # noqa: BLE001
        pass


# ---------------------------------------------------------------------------------------------
# Our own span around each turn
# ---------------------------------------------------------------------------------------------
class SpanHandle:
    def __init__(self, span: Any = None) -> None:
        self.span = span
        ctx = span.get_span_context() if span is not None else None
        self.trace_id = format(ctx.trace_id, "032x") if ctx is not None and ctx.is_valid else None

    def set(self, key: str, value: Any) -> None:
        if self.span is not None and value is not None:
            self.span.set_attribute(key, value)


@contextmanager
def turn_span(name: str, attributes: dict[str, Any] | None = None) -> Iterator[SpanHandle]:
    """Start a span; a no-op handle if OpenTelemetry is not installed or not configured."""
    try:
        from opentelemetry import trace
    except ImportError:
        yield SpanHandle()
        return
    tracer = trace.get_tracer("care_agent")
    with tracer.start_as_current_span(name, attributes=attributes or {}) as span:
        yield SpanHandle(span)


def remember_trace(trace_id: str | None, query: str, latency_ms: float = 0.0) -> None:
    if not trace_id:
        return
    try:
        _append_jsonl(TRACES_FILE, [{"trace_id": trace_id, "query": query[:120], "latency_ms": latency_ms}], keep=50)
    except OSError:
        pass


def last_traces(limit: int = 5) -> list[dict[str, Any]]:
    if not TRACES_FILE.exists():
        return []
    rows = [json.loads(line) for line in TRACES_FILE.read_text(encoding="utf-8").splitlines() if line.strip()]
    return rows[-limit:]


def load_trace_spans(trace_id: str) -> list[dict[str, Any]]:
    if not SPANS_FILE.exists():
        return []
    spans = []
    for line in SPANS_FILE.read_text(encoding="utf-8").splitlines():
        if trace_id in line:
            row = json.loads(line)
            if row.get("trace_id") == trace_id:
                spans.append(row)
    return sorted(spans, key=lambda s: s.get("start") or 0)


def build_span_tree(spans: list[dict[str, Any]]) -> list[tuple[int, dict[str, Any]]]:
    """Flatten spans into (depth, span) in parent → child order (pure; unit-tested)."""
    ids = {s["span_id"] for s in spans}
    children: dict[str | None, list[dict[str, Any]]] = {}
    for span in spans:
        parent = span.get("parent_id") if span.get("parent_id") in ids else None
        children.setdefault(parent, []).append(span)
    ordered: list[tuple[int, dict[str, Any]]] = []

    def walk(parent: str | None, depth: int) -> None:
        for child in sorted(children.get(parent, []), key=lambda s: s.get("start") or 0):
            ordered.append((depth, child))
            walk(child["span_id"], depth + 1)

    walk(None, 0)
    return ordered


def kql_queries(participant_id: str, trace_id: str | None = None) -> dict[str, str]:
    trace = trace_id or "<trace-id>"
    return {
        "Your agent turns (last hour)": f"""dependencies
| where timestamp > ago(1h) and cloud_RoleName == "{participant_id}"
| where name startswith "care_agent.turn" or name startswith "invoke_agent"
| project timestamp, operation_Id, name, duration, customDimensions
| order by timestamp desc""",
        "One trace, end to end (client + APIM + backends)": f"""union dependencies, requests, traces, exceptions
| where operation_Id == "{trace}"
| project timestamp, itemType, cloud_RoleName, name, duration, success, customDimensions
| order by timestamp asc""",
        "Token usage by model (GenAI semantic conventions)": f"""dependencies
| where cloud_RoleName == "{participant_id}" and isnotempty(customDimensions["gen_ai.usage.input_tokens"])
| summarize input_tokens=sum(toint(customDimensions["gen_ai.usage.input_tokens"])),
            output_tokens=sum(toint(customDimensions["gen_ai.usage.output_tokens"]))
    by model=tostring(customDimensions["gen_ai.request.model"])""",
        "Gateway view: your token metrics in APIM": f"""customMetrics
| where timestamp > ago(1h) and tostring(customDimensions["User ID"]) == "{participant_id}"
| summarize tokens=sum(valueSum) by name, bin(timestamp, 5m)""",
    }


def main() -> int:
    """`uv run poe traces`: last local traces + KQL to find them in Application Insights."""
    from .config import get_settings
    from .ui import console, render_trace_tree

    settings = get_settings()
    out = console()
    traces = last_traces()
    out.rule(f"Your last traces (service.name = {settings.participant_id})")
    if not traces:
        out.print("No traces recorded yet. Complete Lab 4, then run `uv run poe chat` and ask something.")
    for row in traces:
        out.print(f"[bold]{row['trace_id']}[/]  {row.get('latency_ms', 0):>8.0f} ms  {row['query']}")
    if traces:
        render_trace_tree(load_trace_spans(traces[-1]["trace_id"]), title=f"Local span tree for {traces[-1]['trace_id']}")
    out.rule("Find them in Application Insights (presenter screen, or anyone with Reader access)")
    for title, query in kql_queries(settings.participant_id, traces[-1]["trace_id"] if traces else None).items():
        out.print(f"[bold cyan]// {title}[/]\n{query}\n")
    out.print(
        "Portal: Application Insights → Transaction search → paste the trace ID (operation ID).\n"
        "Foundry: project → Observability → Tracing shows the same GenAI spans."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
