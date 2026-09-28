<!-- Generated from docs/lab4.md by scripts/export_labs.py — edit the docs/ version. -->

# Lab 4 — Observability

**⏱ 10 min** · 00:57–01:07

**Goal:** every agent turn becomes one end-to-end trace — your laptop, the gateway, the tools and the remote
agent — using OpenTelemetry GenAI semantic conventions, exported to Application Insights **through APIM**.

> [!NOTE]
> **Concept: trace anatomy**
>
> ```mermaid
> flowchart TD
>     T["care_agent.turn<br/>participant.id · care_agent.version"] --> I["invoke_agent care-coordination-agent"]
>     I --> C1["chat gpt-6-luna<br/>gen_ai.usage.input_tokens / output_tokens"]
>     I --> X1["execute_tool get_care_plan"]
>     X1 --> H1["HTTP POST /care-tools/mcp"] --> G1["APIM request span<br/>(child via W3C traceparent)"] --> B1["care-tools-backend"]
>     I --> X2["execute_tool ask_policy_expert"]
>     X2 --> H2["HTTP POST /a2a/care-knowledge"] --> G2["APIM request span<br/>genai.agent.name"] --> K["care-knowledge-agent"]
>     I --> C2["chat gpt-6-luna (final answer)"]
> ```
>
> - `service.name` = your `PARTICIPANT_ID` → `cloud_RoleName` in App Insights.
> - Agent Framework emits `invoke_agent`, `chat` and `execute_tool` spans (GenAI semantic conventions).
> - APIM uses W3C correlation, so its request span becomes a **child** of your span: one operation ID
>   from laptop to backend.
> - Prompts/completions are **not** recorded unless you set `ENABLE_SENSITIVE_DATA=true` (synthetic data only!).

## Steps

**Before you start:** finish Lab 3 or run `uv run poe catchup 3`. Close the CLI before editing telemetry:
exporters are configured when the process starts. Check that `/telemetry` passes `uv run poe smoke`.
Participants do not need portal permissions; the presenter opens Application Insights.

> [!TIP]
> **1. Configure the exporters**
>
> Open `src/care_agent/telemetry.py`. In `setup_telemetry()` replace the `TODO (Lab 4)` block with:
>
> ```python
> exporters: list[Any] = []
> mode, detail = "local", "Local span file only (.care_agent/spans.jsonl)."
> if settings.appinsights_connection_string:
>     try:
>         exporters = build_azure_monitor_exporters(settings)   # → APIM /telemetry + key header policy
>         mode, detail = "azure_monitor", "Azure Monitor via APIM /telemetry"
>     except Exception as exc:
>         detail = f"Azure Monitor exporter unavailable ({exc}); local spans only."
> exporters.append(_local_exporter())                        # keeps a local copy for /trace
>
> from agent_framework.observability import configure_otel_providers, enable_instrumentation
> from opentelemetry import trace
>
> configure_otel_providers(exporters=exporters)
> enable_instrumentation()
> trace.get_tracer_provider().add_span_processor(_participant_processor(settings))
> _STATUS = TelemetryStatus(mode, detail)
> return _STATUS
> ```
>
> Then read `build_azure_monitor_exporters()` above it: the connection string's `IngestionEndpoint` is
> `${APIM_BASE_URL}/telemetry/`, and an azure-core `HeadersPolicy` adds your subscription key.

> [!TIP]
> **2. Produce a trace**
>
> ```bash
> uv run poe chat
> ```
> The banner line now says `telemetry: azure_monitor — Azure Monitor via APIM /telemetry`. Ask
> `Plan discharge for patient P-1042 and book a cardiology follow-up within 7 days.`, then type `/trace`.
> If the banner says `local`, the local trace is still useful, but it does not prove the Azure export
> works. Record the status and tell a helper. Wait a few seconds before `/trace` so the batch can flush.

> [!TIP]
> **3. Find it again later**
>
> ```bash
> uv run poe traces
> ```
> Prints your last trace IDs, the local span tree and ready-to-paste KQL filtered by your participant ID.
> First type `/exit` in the chat, then run this command at the shell. Copy a trace ID, not your key.
> Identify at least one model span (with tokens) and one tool span (with duration).

> [!TIP]
> **4. Watch the end-to-end view (presenter screen)**
>
> The presenter pastes one of your trace IDs into Application Insights → *Transaction search*. You see your
> `care_agent.turn` span, the APIM request spans as children, and the backend calls — one operation.

## Expected output

```text
trace 4bf92f3577b34da6a3ce929d0e0e4736
└── care_agent.turn 9412.3 ms
    └── invoke_agent care-coordination-agent 9398.0 ms
        ├── chat gpt-6-luna 1650.2 ms model=gpt-6-luna input_tokens=1702 output_tokens=58
        ├── execute_tool get_care_plan 612.4 ms
        ├── execute_tool list_available_slots 540.9 ms
        ├── execute_tool book_follow_up 701.3 ms
        └── chat gpt-6-luna 2410.8 ms model=gpt-6-luna input_tokens=2544 output_tokens=231
```

The IDs and timings above are illustrative. Match your local trace ID to the presenter's operation ID;
do not assume two similar-looking trees belong to the same request.

> [!IMPORTANT]
> **Checkpoint**
>
> `/trace` shows a tree with `invoke_agent`, `chat` and `execute_tool` spans. Stuck? `uv run poe catchup 4`.

## Troubleshooting

> [!WARNING]
> **`telemetry: local — No APPLICATIONINSIGHTS_CONNECTION_STRING`**
>
> `GET /telemetry/config` failed (see `uv run poe smoke`). Local traces still work; the presenter can give you
> the connection string to put in `.env`.

> [!WARNING]
> **`/trace` says no local spans**
>
> Spans are exported in batches every few seconds. Ask one more question, or wait 5 seconds and retry.

> [!WARNING]
> **Nothing in Application Insights**
>
> Ingestion takes 1–3 minutes. If `/telemetry` rejects the exporter's key header, the presenter can switch the
> documented fallback (iKey-filtered, rate-limited route without subscription key) — no code change.

## What you just proved

- [ ] One trace ID follows a request through your code, the gateway, MCP tools and the remote agent.
- [ ] Token usage and latency per model call are data, not guesses.
- [ ] Trace schema (`participant.id`, `care_agent.version`) is a decision you make now and query for years.

Next: [Lab 5 — Evaluations](lab5.md).
