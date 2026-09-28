"""Build the Care Coordination Agent (Microsoft Agent Framework) — every call goes through APIM.

Anatomy of the agent (Lab 1 concept):

    Agent = chat client (model behind APIM /openai)
          + instructions (safety boundaries, how to work)
          + tools: local function (get_current_date)
                   + MCP tools behind ONE managed endpoint (Lab 2, APIM /care-tools/mcp)
                   + a policy-expert sub-agent over A2A (Lab 3, APIM /a2a/care-knowledge)
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any

from .a2a_delegate import create_policy_expert_tool
from .config import Settings, get_settings
from .errors import LabIncomplete, retry_async
from .instructions import AGENT_NAME, instructions_hash, load_active_instructions
from .telemetry import remember_trace, turn_span
from .tools_mcp import create_mcp_tool

AGENT_DESCRIPTION = (
    "Care Coordination Agent (Lakeside Regional Health Network, fictional): discharge planning, "
    "referrals, follow-up scheduling, medication reconciliation checks and prior-auth questions."
)


def get_current_date() -> str:
    """Return today's date in ISO format (YYYY-MM-DD) so you can reason about 'within N days'."""
    return date.today().isoformat()


def create_chat_client(settings: Settings) -> Any:
    """Chat client that talks to the model deployment through APIM /openai."""
    from agent_framework.openai import OpenAIChatClient, OpenAIChatCompletionClient

    # Chat Completions is the most gateway-friendly surface (/openai/deployments/{d}/chat/completions).
    # Set CHAT_API=responses to try the Responses API instead.
    client_cls = OpenAIChatClient if settings.chat_api == "responses" else OpenAIChatCompletionClient
    kwargs: dict[str, Any] = {
        "model": settings.chat_model,  # the deployment name behind APIM
        "azure_endpoint": settings.openai_endpoint,  # = APIM_BASE_URL; the SDK appends /openai/...
        "api_key": settings.subscription_key,  # sent as `api-key`, APIM's subscription key header for /openai
        "api_version": settings.openai_api_version,
    }
    try:
        # Also send Ocp-Apim-Subscription-Key (CONTRACT: every client sends both headers).
        return client_cls(**kwargs, default_headers=settings.apim_headers())
    except TypeError:  # older client signature without default_headers: api-key alone is enough
        return client_cls(**kwargs)


def create_agent(settings: Settings, instructions: str, tools: list[Any]) -> Any:
    """Assemble the Agent from chat client + instructions + tools."""
    chat_client = create_chat_client(settings)
    if chat_client is None:
        raise LabIncomplete(1, "src/care_agent/agent.py → create_chat_client()", "see the commented code")
    from agent_framework import Agent

    return Agent(
        client=chat_client,
        name=AGENT_NAME,
        description=AGENT_DESCRIPTION,
        instructions=instructions,
        tools=tools,
        # This model requires reasoning disabled for Chat Completions function tools.
        default_options=(
            {"reasoning_effort": "none"}
            if settings.chat_api != "responses" and settings.chat_model == "gpt-6-luna"
            else None
        ),
    )


@dataclass
class AgentHandle:
    """The agent plus the metadata we want in every trace and eval record."""

    agent: Any
    settings: Settings
    version: str
    instructions_hash: str
    tool_info: dict[str, Any]
    mcp_tool: Any = None


def build_agent(
    settings: Settings | None = None,
    *,
    instructions: str | None = None,
    version: str | None = None,
    include_mcp: bool = True,
    include_a2a: bool = True,
) -> AgentHandle:
    """Create the agent. Use `async with handle.agent:` so MCP connections open and close cleanly."""
    settings = settings or get_settings()
    if instructions is None:
        version, instructions = load_active_instructions()
    tools: list[Any] = [get_current_date]
    info: dict[str, Any] = {"local": ["get_current_date"], "mcp": None, "a2a": None}

    mcp_tool = create_mcp_tool(settings) if include_mcp else None  # None until Lab 2
    if mcp_tool is not None:
        tools.append(mcp_tool)
        info["mcp"] = settings.mcp_url
    expert = create_policy_expert_tool(settings) if include_a2a else None  # None until Lab 3
    if expert is not None:
        tools.append(expert)
        info["a2a"] = settings.a2a_agent_card_url

    agent = create_agent(settings, instructions, tools)
    return AgentHandle(agent, settings, version or "v1", instructions_hash(instructions), info, mcp_tool)


def new_session(agent: Any) -> Any:
    """Multi-turn memory (AgentSession). Returns None if the installed version has no sessions."""
    for name in ("create_session", "get_new_session"):
        factory = getattr(agent, name, None)
        if callable(factory):
            return factory()
    return None


# ---------------------------------------------------------------------------------------------
# One agent turn -> RunRecord (used by chat, lab2, lab3, evals and the Lab 6 loop)
# ---------------------------------------------------------------------------------------------
@dataclass
class RunRecord:
    query: str
    response: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    tool_results: list[dict[str, Any]] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    latency_ms: float = 0.0
    trace_id: str | None = None
    agent_version: str = "v1"
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _parse_arguments(arguments: Any) -> Any:
    if isinstance(arguments, str):
        try:
            return json.loads(arguments)
        except json.JSONDecodeError:
            return arguments
    return arguments


def _to_text(value: Any, limit: int = 4000) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        items = value if isinstance(value, list) else [value]
        parts = [getattr(item, "text", None) or str(item) for item in items]
        value = "\n".join(parts)
    return value[:limit]


def extract_tool_activity(response: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Pull function calls/results out of an AgentResponse (MCP and A2A tools look the same here)."""
    calls: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []
    for message in getattr(response, "messages", None) or []:
        for content in getattr(message, "contents", None) or []:
            kind = getattr(content, "type", None)
            if kind == "function_call":
                calls.append(
                    {
                        "name": getattr(content, "name", ""),
                        "arguments": _parse_arguments(getattr(content, "arguments", None)),
                        "call_id": getattr(content, "call_id", None),
                    }
                )
            elif kind == "function_result":
                results.append(
                    {"call_id": getattr(content, "call_id", None), "result": _to_text(getattr(content, "result", None))}
                )
    names = {c["call_id"]: c["name"] for c in calls}
    for result in results:
        result["name"] = names.get(result["call_id"], "")
    return calls, results


def extract_usage(response: Any) -> tuple[int, int, int]:
    usage = getattr(response, "usage_details", None) or getattr(response, "usage", None)
    if usage is None:
        return 0, 0, 0

    def pick(*names: str) -> int:
        for name in names:
            value = usage.get(name) if isinstance(usage, dict) else getattr(usage, name, None)
            if isinstance(value, (int, float)):
                return int(value)
        return 0

    input_tokens = pick("input_token_count", "input_tokens", "prompt_tokens")
    output_tokens = pick("output_token_count", "output_tokens", "completion_tokens")
    total = pick("total_token_count", "total_tokens") or input_tokens + output_tokens
    return input_tokens, output_tokens, total


async def run_turn(
    agent: Any,
    query: str,
    *,
    session: Any = None,
    settings: Settings | None = None,
    version: str = "v1",
    attributes: dict[str, Any] | None = None,
) -> RunRecord:
    """Run one turn inside a `care_agent.turn` span and capture everything evals need."""
    settings = settings or get_settings()
    record = RunRecord(query=query, agent_version=version)
    span_attributes = {
        "participant.id": settings.participant_id,
        "care_agent.version": version,
        **(attributes or {}),
    }
    started = time.perf_counter()
    with turn_span("care_agent.turn", span_attributes) as span:
        record.trace_id = span.trace_id

        async def call() -> Any:
            if session is not None:
                return await agent.run(query, session=session)
            return await agent.run(query)

        response = await retry_async(call)
        record.response = getattr(response, "text", None) or str(response)
        record.tool_calls, record.tool_results = extract_tool_activity(response)
        record.input_tokens, record.output_tokens, record.total_tokens = extract_usage(response)
        span.set("care_agent.tool_calls", ",".join(c["name"] for c in record.tool_calls))
        span.set("gen_ai.usage.total_tokens", record.total_tokens)
    record.latency_ms = round((time.perf_counter() - started) * 1000, 1)
    remember_trace(record.trace_id, query, record.latency_ms)
    return record
