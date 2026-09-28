# Shared Architecture Contract (single source of truth)

All three deliverables (`/infra`, `/workshop`, `/presenter`) MUST follow this contract exactly so they fit together.
Everything is in English. Session length is **1h45m (105 minutes)** — never write "two-hour".

## 1. Names

| Thing | Value |
|---|---|
| Workshop title | From Prototype to Proof: Building a Production Agent and Actually Knowing It Works |
| Fictional hospital network | Lakeside Regional Health Network (fictional) |
| Fictional payers | Northwind Health Plan, Contoso Care Insurance, Fabrikam Mutual Assurance |
| Foundry project | `${prefix}-proj` (var-driven); Foundry resource `${prefix}-foundry-${suffix}` kind `AIServices`, `allowProjectManagement = true` |
| Base agent (Foundry Agent Service, versioned prompt agent) | `care-knowledge-agent` |
| AI Search index / knowledge source / knowledge base | `care-docs` / `care-docs-ks` / `care-kb` |
| Blob container with synthetic docs | `care-docs` |
| Mock tools backend (Container Apps, FastAPI) | `care-tools-backend` |
| Fallback A2A adapter (Container Apps) | `care-knowledge-a2a` |
| APIM product | `workshop-participants` |
| Participant/subscription name | `user` + 2 digits, from `user01` through `user99`, e.g. `user07` |
| Participant primary subscription key | Participant name + 3 random lowercase alphanumerics, e.g. `user07k3x` (illustrative only); suffix stable in Terraform state. Short-lived controlled workshop only, not production. Secondary keys remain APIM-generated. |
| Default model deployments | chat `gpt-6-luna`, judge `gpt-6-sol`, embeddings `text-embedding-3-large` (all configurable) |

Disclaimer text (must appear in workshop README, docs site, CLI banner, agent instructions, mock backend root):
> **Training use only.** This workshop uses synthetic, fictional data. The Care Coordination Agent is not a medical device and does not provide clinical advice, diagnosis or treatment decisions.

## 2. APIM routes (participant-facing)

Base: `APIM_BASE_URL = https://<apim-name>.azure-api.net`

| Route | Purpose | Backend | Backend auth | Key header accepted |
|---|---|---|---|---|
| `/openai/*` | Model calls (Azure OpenAI-compatible: `/openai/deployments/{d}/chat/completions?api-version=…` and `/openai/v1/*`) | `https://<foundry>.openai.azure.com/openai` (or `.services.ai.azure.com/openai`) | `authentication-managed-identity` resource `https://cognitiveservices.azure.com` | `api-key` (APIM subscription key header name for this API is set to `api-key`, so Azure OpenAI SDKs work unchanged) |
| `/care-tools/mcp` | MCP server (APIM "REST API as MCP server", `type: mcp`, API path `care-tools`) whose tools map to the REST API below | backing REST API `care-tools-api` at path `/care-tools-api` → Container Apps | none/internal (optional shared header secret from named value) | `Ocp-Apim-Subscription-Key` |
| `/a2a/care-knowledge/*` | A2A (JSON-RPC) to base agent; Agent Card at `/a2a/care-knowledge/.well-known/agent-card.json` | Preferred: native Foundry A2A `https://<foundry>.services.ai.azure.com/api/projects/<project>/agents/care-knowledge-agent/endpoint/protocols/a2a` (+ card `…/agentCard/v1.0`, header `A2A-Version: 1.0`). Fallback: Container Apps adapter | managed identity, resource `https://ai.azure.com` | `Ocp-Apim-Subscription-Key` |
| `/foundry/*` | Foundry project data-plane proxy; clients use `FOUNDRY_PROJECT_ENDPOINT = ${APIM_BASE_URL}/foundry/api/projects/<project>` | `https://<foundry>.services.ai.azure.com` (path passthrough) | managed identity, resource `https://ai.azure.com`; inbound strips caller `Authorization` | `Ocp-Apim-Subscription-Key` |
| `/telemetry/*` | Application Insights ingestion proxy (`/telemetry/v2.1/track`, `/telemetry/v2/track`) | App Insights regional `IngestionEndpoint` | none needed (ingestion uses iKey) | `Ocp-Apim-Subscription-Key` (primary). Fallback documented in §6 |
| `GET /telemetry/config` | Returns `{ "connectionString": "InstrumentationKey=<ikey>;IngestionEndpoint=${APIM_BASE_URL}/telemetry/", "foundryProjectName": "<project>", "chatModel": "...", "judgeModel": "..." }` via `return-response` (so participants only need 3 env values) | — | — | `Ocp-Apim-Subscription-Key` |

Rules:
- All workshop HTTP clients send BOTH `Ocp-Apim-Subscription-Key: <key>` and `api-key: <key>` headers (harmless, simplifies code).
- W3C `traceparent`/`tracestate` pass through untouched; APIM Application Insights diagnostic uses `httpCorrelationProtocol = "W3C"`, so APIM's request span is a child of the participant's span.
- Every API sets header `x-participant-id` from `context.Subscription.Name` towards the backend and emits it as a custom dimension / token-metric dimension "User ID".

## 3. Mock clinical tools (REST → MCP tools). operationIds == MCP tool names

| operationId / tool | Method + path (on `care-tools-api`) | Inputs | Output (JSON) |
|---|---|---|---|
| `search_patient` | `GET /patients/search?query=` | `query` (name fragment or ID) | list of `{patient_id, display_name, age, primary_condition, ward, discharge_status}` |
| `get_care_plan` | `GET /patients/{patient_id}/care-plan` | `patient_id` | `{patient_id, condition, care_pathway, discharge_readiness, pending_tasks[], medications[], payer, required_follow_ups[]}` |
| `list_available_slots` | `GET /slots?specialty=&within_days=` | `specialty` (cardiology, pulmonology, endocrinology, primary-care, physiotherapy), `within_days` int (default 14) | list of `{slot_id, specialty, clinician, location, start}` |
| `book_follow_up` | `POST /appointments` | `{patient_id, slot_id, reason}` | `{appointment_id, status:"booked", ...}`; 409 if slot taken |
| `create_referral` | `POST /referrals` | `{patient_id, specialty, urgency: routine|urgent, reason}` | `{referral_id, status:"created", sla_days}` |
| `check_medication_interactions` | `POST /medications/interactions` | `{medications: [str]}` | `{interactions: [{pair, severity, note}], disclaimer}` (fake rules) |
| `check_prior_auth_requirement` | `GET /prior-auth?payer=&procedure_code=` | `payer`, `procedure_code` | `{payer, procedure_code, prior_auth_required: bool, policy_ref, notes}` |

Synthetic patients (all fictional):
- `P-1042` Jordan Ellis, 68, heart failure (HFrEF), ward Cardiology 4B, discharge pending; payer Northwind Health Plan; meds furosemide, lisinopril, spironolactone, metoprolol; requires cardiology follow-up within 7 days of discharge (per protocol).
- `P-2077` Sam Okafor, 72, COPD exacerbation, ward Respiratory 2A; payer Contoso Care Insurance; meds tiotropium, prednisolone, salbutamol; pulmonology follow-up within 14 days + pulmonary rehab referral.
- `P-3150` Riley Chen, 55, type 2 diabetes with hyperglycaemia episode; payer Fabrikam Mutual Assurance; meds metformin, insulin glargine, atorvastatin; endocrinology within 14 days.
- `P-4203` Alex Moreno, 81, hip fracture post-surgery; payer Northwind Health Plan; meds warfarin, paracetamol, omeprazole; physiotherapy referral + primary care within 7 days.
- `P-5318` Taylor Brooks, 47, heart failure new diagnosis; payer Fabrikam Mutual Assurance; meds sacubitril/valsartan, bisoprolol.

Fake interaction rules (examples): spironolactone+lisinopril → high (hyperkalaemia risk, fictional note); warfarin+omeprazole → moderate; prednisolone+insulin glargine → moderate (glucose). Always return disclaimer "Synthetic rule set for training. Not clinical guidance."
Prior-auth examples: Northwind + `CARD-ECHO` → false; Northwind + `CARD-MRI` → true; Contoso + `PULM-REHAB` → true; Fabrikam + `ENDO-CGM` → true.
Slots: generated relative to "today" so cardiology has at least 2 slots within 7 days; deterministic seed.

Synthetic knowledge documents (in `infra/data/care-docs/`, markdown, 12 files) must be consistent with the above (same payers, procedure codes, SLAs, patient-agnostic).

## 4. Participant environment

`workshop/.env.example` contains ONLY:
```
APIM_BASE_URL=https://<apim-name>.azure-api.net
APIM_SUBSCRIPTION_KEY=<your-personal-key>
PARTICIPANT_ID=user00
```
plus a commented "derived values (optional overrides)" section. `care_agent/config.py` derives:
- `OPENAI_ENDPOINT = APIM_BASE_URL` (SDK appends `/openai/...`), `OPENAI_API_VERSION` pinned (verify current GA/preview), `CHAT_MODEL=gpt-6-luna`, `JUDGE_MODEL=gpt-6-sol`
- `MCP_URL = ${APIM_BASE_URL}/care-tools/mcp`
- `A2A_AGENT_CARD_URL = ${APIM_BASE_URL}/a2a/care-knowledge/.well-known/agent-card.json`
- `FOUNDRY_PROJECT_ENDPOINT = ${APIM_BASE_URL}/foundry/api/projects/${FOUNDRY_PROJECT_NAME}` (FOUNDRY_PROJECT_NAME read from `/telemetry/config` field `foundryProjectName` if not set)
- `APPLICATIONINSIGHTS_CONNECTION_STRING` fetched from `GET /telemetry/config` if not set.

Infra-generated `/infra/out/participants/<name>.env` contains the 3 values AND all derived values explicitly (no need to call `/telemetry/config`).

## 5. Credentials trick for Foundry SDK through APIM

`azure-ai-projects` only accepts Entra `TokenCredential`. The workshop provides `care_agent/apim_auth.py` with:
- `ApimKeyCredential(TokenCredential)` that returns a static placeholder token (APIM discards `Authorization` and uses its own managed identity), and
- an azure-core per-call policy / headers injecting `Ocp-Apim-Subscription-Key`.
Mark clearly as a workshop pattern; the APIM `/foundry` policy allowlists only the operations needed (evaluations/evals, datasets, agents read/versions, redTeams, openai evals/responses for the agent) and blocks everything else with 403.

## 6. Telemetry through APIM

Primary: Azure Monitor OpenTelemetry exporter with connection string `IngestionEndpoint=${APIM_BASE_URL}/telemetry/` and a custom azure-core policy adding `Ocp-Apim-Subscription-Key` (verify the exporter accepts extra pipeline policies/headers; pin versions).
Fallback (documented, toggled by infra var `telemetry_require_subscription_key`, default true): `/telemetry` API with `subscriptionRequired=false`, but the policy only forwards payloads whose iKey equals the workshop iKey, rate-limits by IP, and caps body size. List this in `docs/APIM_EXCEPTIONS.md`.
`service.name` = `PARTICIPANT_ID`. GenAI semantic conventions via Agent Framework's built-in instrumentation (`agent_framework.observability`).

## 7. Labs and timing (total 105 min, ~25 min concept talk interleaved)

| Clock | Segment | Minutes |
|---|---|---|
| 00:00–00:04 | Opening, disclaimer, architecture (concept) | 4 |
| 00:04–00:09 | Lab 0 — Setup & smoke test | 5 |
| 00:09–00:11 | Concept: agent anatomy & safety boundaries | 2 |
| 00:11–00:26 | Lab 1 — Build the local Care Coordination Agent | 15 |
| 00:26–00:28 | Concept: tools behind one managed MCP endpoint | 2 |
| 00:28–00:38 | Lab 2 — Tools via managed MCP endpoint | 10 |
| 00:38–00:40 | Concept: A2A and agent contracts | 2 |
| 00:40–00:55 | Lab 3 — Multi-agent via A2A | 15 |
| 00:55–00:57 | Concept: trace anatomy | 2 |
| 00:57–01:07 | Lab 4 — Observability | 10 |
| 01:07–01:10 | Concept: defining "good" (weighted rubrics) | 3 |
| 01:10–01:30 | Lab 5 — Evaluations | 20 |
| 01:30–01:40 | Lab 6 — Close the loop (≈4 min presenter demo) | 10 |
| 01:40–01:45 | Wrap-up: "Cheap to change vs. follows you for two years" | 5 |

Catch-up command: `uv run poe catchup <N>` (copies `solutions/labN/` over `src/care_agent/`). Task runner: poethepoet.

## 8. Repository layout (top level)

```
care-coordination-workshop/
├── README.md                 # root overview, disclaimer, quick links, preview-features table, APIM exceptions
├── .gitignore                # ignores .env, infra/out/, *.tfstate*, participants.csv, .terraform/
├── docs/CONTRACT.md          # this file
├── docs/PREVIEW_FEATURES.md
├── docs/APIM_EXCEPTIONS.md
├── infra/                    # Deliverable 1
├── workshop/                 # Deliverable 2
└── presenter/                # Deliverable 3
```

## 9. Preview features & APIM-exception registers

Each deliverable writes its own file: `docs/preview/<deliverable>.md` (table: feature | where used | status | fallback) and `docs/apim-exceptions/<deliverable>.md` (table: what | why | mitigation). The orchestrator merges them into `docs/PREVIEW_FEATURES.md` and `docs/APIM_EXCEPTIONS.md`.

## 10. Verified research facts (September 2026) — use these, re-verify if in doubt

- Microsoft Agent Framework Python: `agent-framework` / `agent-framework-core` **1.19.0** (2026-09-18), GA, no `--pre`. `from agent_framework import Agent`; `from agent_framework.openai import OpenAIChatClient` (also `OpenAIChatCompletionClient`); constructor accepts `api_key`, `azure_endpoint`, `model`, `api_version`. Tools: plain Python functions / `@tool`. MCP: `MCPStreamableHTTPTool` (HTTP client no longer persists cookies; `header_provider` receives only trusted runtime kwargs). A2A client: `agent_framework.a2a.A2AAgent` (package `agent-framework-a2a`); A2A hosting package `agent-framework-hosting-a2a`. DevUI: `agent-framework-devui`. Lab modules are separate (`agent-framework-lab`). `agent-framework-foundry` supports `azure-ai-projects>=2.2.0,<2.7.0`.
- Observability: `from agent_framework.observability import configure_otel_providers, enable_instrumentation`; instrumentation is on by default; reads `OTEL_*` env vars, `ENABLE_SENSITIVE_DATA`; can pass custom `exporters=[...]`, or set up Azure Monitor yourself and call `enable_instrumentation()`. Samples require Azure Monitor OpenTelemetry **1.8.10** for Foundry trace propagation.
- `azure-ai-projects` latest **2.7.0** (2026-09-18); v1 data-plane REST; Entra-only auth; preview features need `allow_preview=True` or `.beta.*` (red teams: `.beta.red_teams`, evaluators: `.beta.evaluators`). Because Agent Framework Foundry pins `<2.7.0`, pin `azure-ai-projects==2.6.1` if `agent-framework-foundry` is installed, else 2.7.0. `project.get_openai_client()` for evals/responses. Agents: `project.agents.create_version(...)`, `project.agents.update_details(agent_name=..., agent_endpoint=AgentEndpointConfig(protocol_configuration=ProtocolConfiguration(responses=ResponsesProtocolConfiguration(), a2a=A2AProtocolConfiguration())), agent_card=AgentCard(...))` (requires >=2.5.0).
- Foundry incoming A2A: public preview; A2A protocol 1.0 GA + 0.3 preview on `…/agents/{agent}/endpoint/protocols/a2a`; cards at `…/agentCard/v1.0` and `…/agentCard/v0.3`; version via `A2A-Version: 1.0` header; Entra required even for the card (APIM import wizard fetches anonymously and fails → create the APIM A2A API with explicit runtime URL / agent card config, or plain HTTP API with MI auth). REST: `PATCH {project}/agents/{name}?api-version=v1` body `{agent_card:{...}, agent_endpoint:{protocol_configuration:{responses:{}, a2a:{}}}}`. Role for APIM MI: Foundry User (formerly Azure AI User).
- APIM A2A agent API: GA; tiers Developer, Basic, Basic v2, Standard, Standard v2, Premium, Premium v2; JSON-RPC only; APIM rewrites card hostname and adds subscription key requirement; adds `genai.agent.id`/`genai.agent.name` to App Insights telemetry.
- APIM MCP (REST API as MCP server): tiers Developer, Basic, Basic v2, Standard, Standard v2, Premium, Premium v2 (NOT Consumption). Tools only (no resources/prompts). Not in workspaces. If global App Insights diagnostics are on, set frontend response payload bytes to 0 (log payloads per-API instead). Don't touch `context.Response.Body` in MCP policies. ARM: `Microsoft.ApiManagement/service/apis@2025-09-01-preview` with `properties.type = "mcp"`, `path`, `displayName`, `protocols`, `subscriptionRequired`; tools as `Microsoft.ApiManagement/service/apis/tools@2025-09-01-preview` with `properties.displayName`, `description`, `operationId` (= full ARM id of backing REST operation); policy `apis/policies` name `policy` format `rawxml`; product binding `Microsoft.ApiManagement/service/products/apis@2025-09-01-preview` body `{}`. AzureRM has no native MCP resource → use `azapi_resource`.
- Foundry IQ: knowledge bases on Azure AI Search (agentic retrieval); some GA, some preview depending on Search REST API version; knowledge source types include blob (indexed). Agents connect to a knowledge base over MCP (knowledge base MCP endpoint) via a project connection; requires search MI "Cognitive Services User" on Foundry if KB uses an LLM, project MI "Search Index Data Reader" on search. Foundry agent REST `2026-08-01-preview` / SDK `azure-ai-projects>=2.0.0`. Hub-based projects not supported.
- Foundry RBAC renamed: Foundry User (ex Azure AI User), Foundry Project Manager, Foundry Owner, Foundry Account Owner. Role IDs unchanged.

## 11. Command contract (implemented by /workshop in `pyproject.toml` `[tool.poe.tasks]`; referenced by /presenter)

Run from `workshop/`:

| Command | What it does |
|---|---|
| `uv sync` | install pinned deps (uv installs Python 3.12 automatically via `.python-version`) |
| `uv run poe smoke` | Lab 0 connectivity check against /openai, /care-tools/mcp, /a2a/care-knowledge, /telemetry, /foundry |
| `uv run poe chat` | interactive CLI chat with the Care Coordination Agent |
| `uv run poe devui` | launch Agent Framework DevUI (if installed) |
| `uv run poe mcp-tools` | list MCP tools from the managed endpoint |
| `uv run poe lab2` | run the scripted multi-step task "Plan discharge for patient P-1042 and book a cardiology follow-up within 7 days." |
| `uv run poe a2a-card` | fetch and pretty-print the base agent's Agent Card through APIM |
| `uv run poe lab3` | ask a prior-auth policy question that is delegated over A2A; prints citations |
| `uv run poe traces` | print the KQL / portal links to find your traces (filter by PARTICIPANT_ID) |
| `uv run poe evals` | run local evaluations with weighted rubric → `evals/out/<run-id>/` |
| `uv run poe redteam` | generate adversarial prompts from the escalation & safety policy and evaluate them |
| `uv run poe upload-evals` | upload the latest local run to the Foundry project via APIM /foundry |
| `uv run poe cloud-eval` | start a cloud evaluation in Foundry via APIM /foundry (preview; fallback = upload) |
| `uv run poe loop` | Lab 6 pipeline: pull low-scoring traces/results → cluster & rank failure modes → propose change → re-run evals → promote if better |
| `uv run poe promote` | promote candidate agent version with lineage (version, eval run ID, trace IDs) into `agent_versions/registry.json` |
| `uv run poe rollback` | roll back to previous agent version |
| `uv run poe catchup <N>` | copy `solutions/labN/` into `src/care_agent/` |
| `uv run poe docs` | optionally serve the prebuilt static lab guide at http://127.0.0.1:8000; `workshop/guide/index.html` also opens directly without a server |
| `uv run poe test` | run `tests/` (offline unit tests; no Azure needed) |

Infra (run from `infra/`, presenter/admin only): `terraform init && terraform apply`, `uv run scripts/smoke_test.py --env out/participants/<name>.env`, `terraform destroy`.
Optional production runtime (presenter demo, owned by /workshop): `workshop/deploy/` with Dockerfile + `deploy_hosted_agent.py` (Foundry hosted agent, preview) and a Container Apps fallback.
