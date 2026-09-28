"""A2A adapter for the base agent `care-knowledge-agent` (FALLBACK path, a2a_mode = "adapter").

Why this exists: the preferred path exposes Foundry's native incoming A2A endpoint (public preview)
through APIM. If that preview is unavailable in your region/tenant, Terraform deploys this small
container instead. It:

  1. publishes an A2A Agent Card at /.well-known/agent-card.json whose interface URL is the APIM URL
     (participants never see this container's own hostname), and
  2. answers A2A JSON-RPC requests at "/" by running the Foundry prompt agent through Agent Framework
     (`FoundryAgent`), authenticating with this container's user-assigned managed identity.

Pattern taken from the Agent Framework sample `python/samples/04-hosting/a2a/agent_framework_to_a2a.py`
(`agent-framework-hosting-a2a` is a PRE-RELEASE package; versions are pinned in pyproject.toml).
Only APIM can call this app: every request except /healthz must carry the shared secret header.
"""

from __future__ import annotations

import hmac
import logging
import os
import uuid
from typing import Any

import uvicorn
from a2a.helpers import new_task_from_user_message
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore, TaskUpdater
from a2a.types import AgentCapabilities, AgentInterface, AgentSkill, Part, TaskState
from agent_framework.foundry import FoundryAgent
from agent_framework_hosting import AgentState
from agent_framework_hosting_a2a import AgentA2AAdapter
from azure.identity.aio import ManagedIdentityCredential
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

logger = logging.getLogger("care-knowledge-a2a")

PROJECT_ENDPOINT = os.environ["FOUNDRY_PROJECT_ENDPOINT"]      # direct Foundry endpoint (service-to-service)
AGENT_NAME = os.environ.get("FOUNDRY_AGENT_NAME", "care-knowledge-agent")
PUBLIC_A2A_URL = os.environ["PUBLIC_A2A_URL"]                  # https://<apim>.azure-api.net/a2a/care-knowledge
SHARED_SECRET = os.environ.get("BACKEND_SHARED_SECRET", "")
UNPROTECTED_PATHS = {"/healthz"}

SKILLS = [
    AgentSkill(
        id="care-policy-qa",
        name="Care policy and protocol Q&A",
        description=(
            "Answers questions about the fictional Lakeside Regional Health Network's discharge protocol, care "
            "pathways, referral policy, follow-up SLAs, medication reconciliation guideline and prior-authorization "
            "rules, with citations to document and section IDs. Synthetic data; no clinical advice."
        ),
        tags=["policy", "prior-authorization", "discharge", "citations"],
        examples=["Does Northwind Health Plan require prior authorization for CARD-MRI?"],
    )
]


class FoundryAgentExecutor(AgentExecutor):
    """Native A2A executor that delegates each message to the Foundry prompt agent."""

    def __init__(self, adapter: AgentA2AAdapter[Any]) -> None:
        self.adapter = adapter

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        updater = TaskUpdater(event_queue, context.task_id or "", context.context_id or "")
        await updater.cancel()

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        if context.message is None or context.context_id is None:
            raise ValueError("A2A message and context id are required")
        task = context.current_task or new_task_from_user_message(context.message)
        if context.current_task is None:
            await event_queue.enqueue_event(task)
        updater = TaskUpdater(event_queue, task.id, context.context_id)
        await updater.submit()
        try:
            await updater.start_work()
            run = self.adapter.a2a_to_run(context.message, stream=False)
            agent = await self.adapter.state.get_target()
            # Session key is protocol-level only; APIM authenticates callers (subscription key) upstream.
            session_id = f"a2a:{context.context_id}"
            session = await self.adapter.state.get_or_create_session(session_id)
            result = await agent.run(run["messages"], session=session, options=run["options"], stream=False)
            await self.adapter.state.set_session(session_id, session)
            parts = self.adapter.a2a_from_run(result)
            if parts:
                await updater.add_artifact(parts=parts, artifact_id=uuid.uuid4().hex)
            await updater.complete()
        except Exception:
            logger.exception("Foundry agent run failed")
            await updater.update_status(
                state=TaskState.TASK_STATE_FAILED,
                message=updater.new_agent_message([Part(text="The care knowledge agent failed to answer.")]),
            )


class SharedSecretMiddleware:
    """Pure ASGI middleware: reject requests that did not come through APIM."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and SHARED_SECRET and scope["path"] not in UNPROTECTED_PATHS:
            headers = dict(scope.get("headers") or [])
            provided = headers.get(b"x-backend-secret", b"")
            if not hmac.compare_digest(provided, SHARED_SECRET.encode()):
                await JSONResponse({"detail": "Call this agent through the APIM gateway."}, status_code=403)(
                    scope, receive, send)
                return
        await self.app(scope, receive, send)


async def healthz(_: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})


async def build_app() -> Starlette:
    credential = ManagedIdentityCredential(client_id=os.environ.get("AZURE_CLIENT_ID"))
    agent = FoundryAgent(project_endpoint=PROJECT_ENDPOINT, agent_name=AGENT_NAME, credential=credential)
    adapter = AgentA2AAdapter(
        AgentState(agent),
        version="1.0.0",
        name="Care Knowledge Agent",
        description=(
            "Policy and protocol Q&A for the fictional Lakeside Regional Health Network, grounded on synthetic "
            "documents with citations. Training use only; not a medical device; no clinical advice."
        ),
        capabilities=AgentCapabilities(streaming=False),
        supported_interfaces=[AgentInterface(url=PUBLIC_A2A_URL, protocol_binding="JSONRPC")],
        skills=SKILLS,
    )
    card = await adapter.get_card()
    handler = DefaultRequestHandler(agent_executor=FoundryAgentExecutor(adapter), task_store=InMemoryTaskStore(),
                                    agent_card=card)
    routes = [Route("/healthz", healthz), *create_agent_card_routes(card), *create_jsonrpc_routes(handler, "/")]
    app = Starlette(routes=routes)
    app.add_middleware(SharedSecretMiddleware)
    return app


if __name__ == "__main__":
    import asyncio

    logging.basicConfig(level=logging.INFO)
    uvicorn.run(asyncio.run(build_app()), host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
