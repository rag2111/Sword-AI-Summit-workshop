"""Lab 3 — multi-agent via A2A: delegate policy questions to the base knowledge agent.

The base agent `care-knowledge-agent` lives in Foundry Agent Service (grounded on the
`care-kb` knowledge base). APIM publishes it as an A2A API:

    Agent Card : ${APIM_BASE_URL}/a2a/care-knowledge/.well-known/agent-card.json
    JSON-RPC   : ${APIM_BASE_URL}/a2a/care-knowledge/            (URL rewritten into the card by APIM)

Our agent treats it as a *tool* called `ask_policy_expert`: the local agent owns the workflow, the
remote agent owns the policy knowledge. The Agent Card is the contract between the two teams.

Run `uv run poe a2a-card` to see the card, `uv run poe lab3` to watch a delegation.
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
import time
from typing import Annotated, Any

from .config import Settings, get_settings
from .errors import LabIncomplete, explain, retry_async

POLICY_TOOL_NAME = "ask_policy_expert"

# Every delegation is logged here so lab3 / the CLI can show what crossed the A2A boundary.
DELEGATIONS: list[dict[str, Any]] = []


class AgentCardNotFound(RuntimeError):
    pass


async def fetch_agent_card(settings: Settings) -> dict[str, Any]:
    """GET the Agent Card through APIM (plain HTTP, so you can see exactly what the contract says)."""
    import httpx

    async with httpx.AsyncClient(timeout=30, headers=settings.apim_headers()) as client:
        response = await client.get(settings.a2a_agent_card_url)
    if response.status_code == 404:
        raise AgentCardNotFound(
            f"A2A Agent Card not found at {settings.a2a_agent_card_url} (404). The A2A API may not be deployed "
            "yet or the base agent's A2A endpoint is disabled; tell the presenter."
        )
    response.raise_for_status()
    return response.json()


# ---------------------------------------------------------------------------------------------
# Citations: the base agent cites documents; we surface them explicitly.
# ---------------------------------------------------------------------------------------------
_CITATION_PATTERNS = (
    # Knowledge-base document IDs with section IDs: PA-001 §PA-2, REF-001 §REF-3.1, SAFE-001 §SAFE-2
    re.compile(r"\b((?:[A-Z][A-Z0-9]*-)+\d{3})\s*§\s*((?:[A-Z]+-)*[\d.]*\d)"),
    # file-style citations: [prior-authorization-policy.md §3.2]  or  [referral-policy.md, section 2]
    re.compile(r"\[([\w./-]+\.md)(?:\s*[,;]?\s*(?:§|section|sec\.)\s*([\w.]+))?\]", re.IGNORECASE),
    # Foundry file-search style: 【4:0†prior-authorization-policy.md】
    re.compile(r"【[^】†]*†([^】]+)】"),
    # (prior-authorization-policy.md §3.2)
    re.compile(r"\(([\w./-]+\.md)(?:\s*[,;]?\s*(?:§|section|sec\.)\s*([\w.]+))?\)", re.IGNORECASE),
)


def extract_citations(text: str) -> list[str]:
    """Return unique citations like 'prior-authorization-policy.md §3.2' in order of appearance."""
    found: list[tuple[int, str]] = []
    for pattern in _CITATION_PATTERNS:
        for match in pattern.finditer(text or ""):
            doc = match.group(1).strip()
            section = match.group(2) if match.lastindex and match.lastindex >= 2 else None
            found.append((match.start(), f"{doc} §{section}" if section else doc))
    for line in (text or "").splitlines():  # "Sources: a.md §1; b.md §2"
        if line.strip().lower().startswith("sources:"):
            for item in re.split(r"[;,]\s*", line.split(":", 1)[1]):
                item = item.strip(" []()*")
                if item:
                    found.append((10**9, item.replace("section", "§").replace("  ", " ")))
    unique: list[str] = []
    for _, citation in sorted(found, key=lambda pair: pair[0]):
        if citation not in unique:
            unique.append(citation)
    return unique


class PolicyExpert:
    """Lazily connects to the remote A2A agent on first use (works in CLI, evals and DevUI)."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._agent: Any = None
        self._http: Any = None
        self.card_name: str | None = None

    async def _connect(self) -> Any:
        # [lab3:solution]
        import httpx
        from agent_framework.a2a import A2AAgent

        # One HTTP client carrying the APIM key for both the card and the JSON-RPC calls.
        self._http = httpx.AsyncClient(timeout=120, headers=self.settings.apim_headers())
        card = await _resolve_card(self._http, self.settings)
        self.card_name = getattr(card, "name", None) or "care-knowledge-agent"
        return A2AAgent(
            name=self.card_name,
            description=getattr(card, "description", None) or "Lakeside policy expert",
            agent_card=card,
            url=self.settings.a2a_base_url,
            http_client=self._http,
        )
        # [lab3:starter]
        # TODO (Lab 3): discover the Agent Card through APIM and wrap the remote agent.
        #   import httpx
        #   from agent_framework.a2a import A2AAgent
        #   self._http = httpx.AsyncClient(timeout=120, headers=self.settings.apim_headers())
        #   card = await _resolve_card(self._http, self.settings)
        #   return A2AAgent(name=card.name, description=card.description, agent_card=card,
        #                   url=self.settings.a2a_base_url, http_client=self._http)
        raise LabIncomplete(3, "src/care_agent/a2a_delegate.py → PolicyExpert._connect()")
        # [lab3:end]

    async def ask(self, question: str) -> str:
        if self._agent is None:
            self._agent = await self._connect()
        started = time.perf_counter()
        response = await retry_async(lambda: self._agent.run(question))
        answer = getattr(response, "text", None) or str(response)
        citations = extract_citations(answer)
        DELEGATIONS.append(
            {
                "question": question,
                "answer": answer,
                "citations": citations,
                "latency_ms": round((time.perf_counter() - started) * 1000, 1),
                "remote_agent": self.card_name,
            }
        )
        if citations and "sources:" not in answer.lower():
            answer += "\n\nSources: " + "; ".join(citations)
        return answer

    async def aclose(self) -> None:
        if self._http is not None:
            await self._http.aclose()


async def _resolve_card(http_client: Any, settings: Settings) -> Any:
    """Resolve the AgentCard object with the a2a SDK, falling back to parsing the JSON ourselves."""
    try:
        from a2a.client import A2ACardResolver

        resolver = A2ACardResolver(httpx_client=http_client, base_url=settings.a2a_base_url)
        return await resolver.get_agent_card()
    except Exception as first_error:  # noqa: BLE001 - try the manual path before giving up
        response = await http_client.get(settings.a2a_agent_card_url)
        if response.status_code == 404:
            raise AgentCardNotFound(f"A2A Agent Card not found at {settings.a2a_agent_card_url}") from first_error
        response.raise_for_status()
        from a2a.types import AgentCard

        data = response.json()
        if hasattr(AgentCard, "model_validate"):  # a2a-sdk with pydantic types
            return AgentCard.model_validate(data)
        from google.protobuf.json_format import ParseDict  # a2a-sdk with protobuf types

        return ParseDict(data, AgentCard(), ignore_unknown_fields=True)


_EXPERTS: list[PolicyExpert] = []


def create_policy_expert_tool(settings: Settings) -> Any:
    """Return the `ask_policy_expert` tool function (or None before Lab 3)."""
    # [lab3:solution]
    expert = PolicyExpert(settings)
    _EXPERTS.append(expert)

    async def ask_policy_expert(
        question: Annotated[str, "A self-contained policy question, including payer and procedure code if relevant."],
    ) -> str:
        """Ask the Lakeside policy expert (remote knowledge agent over A2A) about care pathways,
        prior-authorization policy, referral SLAs and escalation rules. Returns an answer with citations
        (document ID + section, e.g. PA-001 §PA-2)."""
        return await expert.ask(question)

    return ask_policy_expert
    # [lab3:starter]
    # TODO (Lab 3): expose the remote agent as a tool named `ask_policy_expert`.
    #   expert = PolicyExpert(settings); _EXPERTS.append(expert)
    #   async def ask_policy_expert(question: Annotated[str, "A self-contained policy question"]) -> str:
    #       """Ask the Lakeside policy expert (remote knowledge agent over A2A) ... with citations."""
    #       return await expert.ask(question)
    #   return ask_policy_expert
    return None
    # [lab3:end]


async def close_policy_experts() -> None:
    for expert in _EXPERTS:
        await expert.aclose()
    _EXPERTS.clear()


def summarize_card(card: dict[str, Any]) -> dict[str, Any]:
    """The parts of the contract worth looking at in Lab 3."""
    return {
        "name": card.get("name"),
        "description": card.get("description"),
        "url": card.get("url") or [i.get("url") for i in card.get("supportedInterfaces", []) or []],
        "protocolVersion": card.get("protocolVersion") or card.get("version"),
        "skills": [s.get("name") or s.get("id") for s in card.get("skills", []) or []],
        "securitySchemes": list((card.get("securitySchemes") or {}).keys()),
    }


def main() -> int:
    """`uv run poe a2a-card`: fetch and pretty-print the Agent Card through APIM."""
    from .ui import console, print_error, print_json

    try:
        settings = get_settings()
        card = asyncio.run(fetch_agent_card(settings))
    except Exception as exc:  # noqa: BLE001
        print_error(str(exc) if isinstance(exc, AgentCardNotFound) else explain(exc, component="A2A card"))
        return 1
    console().rule(f"Agent Card — {settings.a2a_agent_card_url}")
    print_json(json.dumps(card))
    console().rule("Contract summary")
    print_json(json.dumps(summarize_card(card)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
