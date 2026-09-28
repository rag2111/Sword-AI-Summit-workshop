# Preview features register

Every preview or pre-release feature used in this repository, where it is used, and its documented fallback. Status verified in September 2026; re-verify the week before the event.

## Preview features — infra (Deliverable 1)

Status verified September 2026. "GA feature / preview API" means the capability is generally available
but the ARM API version that exposes it is a preview version.

| Feature | Where used | Status (GA/preview + API version) | Fallback |
|---|---|---|---|
| Foundry incoming A2A (agent endpoint A2A protocol + agent card) | `scripts/create_base_agent.py` (`project.agents.update_details`), native backend of `/a2a/care-knowledge` | **Preview** (A2A protocol 1.0 GA on the endpoint, 0.3 preview); Foundry REST `v1`, `azure-ai-projects==2.7.0` | `a2a_mode = "adapter"` (Agent Framework A2A adapter on Container Apps) |
| APIM A2A agent API (`type`/`apiType = "a2a"`, `agent`, `a2aProperties`, `jsonRpcProperties`) | `modules/apim_apis` `azapi_resource.a2a_agent` | Feature **GA**; ARM shape not yet in the published `2025-09-01-preview` schema (schema validation disabled) | `a2a_apim_api_kind = "http"` (plain HTTP API with card rewrite + JSON-RPC operation) |
| APIM MCP server from REST API + `apis/tools` | `modules/apim_apis` (`care-tools`, 7 tools) | Feature **GA**; ARM `Microsoft.ApiManagement/service/apis@2025-09-01-preview` (preview API version) | Portal: *MCP Servers → Expose an API as an MCP server* (same REST API and operations) |
| APIM LLM message logging (`largeLanguageModel` on diagnostics) | `modules/apim` `diag_azuremonitor` | **Preview API** `2025-09-01-preview` | Remove the `largeLanguageModel` block; App Insights request telemetry and token metrics still work |
| APIM child resources (loggers, diagnostics, named values, product, backends, APIs, policies) | `modules/apim`, `modules/apim_apis` | **Preview API** `2025-09-01-preview`; service itself GA `2024-05-01` | `2024-05-01` for everything except MCP/LLM logging |
| `llm-token-limit`, `llm-emit-token-metric`, `llm-content-safety` policies | `modules/apim_apis/policies/openai.xml` | **GA** (extra token categories such as cached/reasoning are preview) | `azure-openai-token-limit` / `azure-openai-emit-token-metric` |
| Content Safety backend with managed-identity credentials | `modules/apim` `backend_content_safety` (only if `enable_content_safety = true`) | **Preview API** `2025-09-01-preview`, schema validation disabled | Keep `enable_content_safety = false` (default) |
| Foundry IQ knowledge source (`azureBlob`) + knowledge base `care-kb` | `scripts/seed_knowledge.py` | Search REST **GA `2026-04-01`** with model configuration; `outputMode`, `retrievalInstructions`, and `retrievalReasoningEffort` are sent only when `SEARCH_KB_API_VERSION` explicitly selects a preview API | Script retries without models (also sets `retrievalReasoningEffort: minimal` for preview only); then `knowledge_mode = "index"` |
| Knowledge base MCP endpoint (`/knowledgebases/care-kb/mcp`) | Base agent MCP tool | **Preview** Search REST `2026-08-01-preview` | `knowledge_mode = "index"` → Azure AI Search tool on index `care-docs` (GA) |
| `RemoteTool` project connection with `ProjectManagedIdentity` | `scripts/create_base_agent.py` (`care-kb-mcp`) | **Preview** ARM `2025-10-01-preview` | `knowledge_mode = "index"` (uses GA `CognitiveSearch` connection `care-search`) |
| Foundry AI-gateway connection (category `ApiManagement`, model `apim-gateway/<deployment>`) | `main.tf` `azapi_resource.apim_gateway_connection`, base agent model | **Preview**; ARM `2026-07-15-preview` | `base_agent_model_route = "direct"`; `auto` falls back automatically after a failed test call |
| Search service `knowledgeRetrieval` billing plan | `modules/search_storage` | **Preview** management API `2026-03-01-preview` | GA `2025-05-01` without the property; choose the plan in the portal (Premium features) |
| Agent Framework A2A hosting (`agent-framework-hosting`, `agent-framework-hosting-a2a` `1.0.0a260730`) | `apps/a2a_adapter` (fallback only) | **Pre-release** packages (pinned); `a2a-sdk==1.1.5` GA | Native Foundry A2A (default); or a plain `a2a-sdk` server |
| Foundry prompt agents (`project.agents.create_version`, `PromptAgentDefinition`, `MCPTool`, `AzureAISearchTool`) | `scripts/create_base_agent.py` | **GA** (`azure-ai-projects==2.7.0`, REST `v1`) | — |
| Foundry account/project/deployments/connections (AppInsights, CognitiveSearch, AzureStorageAccount) | `modules/foundry` | **GA** `2026-05-01` (supported by pinned AzAPI schema) | — |

## Preview features — workshop (Deliverable 2)

Every preview / pre-release item used by `workshop/` is labelled in code comments and in the lab guide, and
has a fallback that keeps the lab completable.

| Feature | Where used | Status | Fallback |
|---|---|---|---|
| `agent-framework-a2a` (A2AAgent client) | Lab 3 — `src/care_agent/a2a_delegate.py`, `poe lab3`, `poe redteam` (policy fetch) | Pre-release package `1.0.0b260918` (exact pin) | `poe a2a-card` still works (plain httpx); red team uses the bundled policy copy; `poe catchup 3`; server-side: A2A fallback adapter `care-knowledge-a2a` behind the same APIM route |
| Foundry Agent Service incoming A2A (`…/endpoint/protocols/a2a`, Agent Card `agentCard/v1.0`) | Lab 3 — remote `care-knowledge-agent` behind `/a2a/care-knowledge` | Public preview | Infra switches the APIM A2A backend to the Container Apps adapter `care-knowledge-a2a`; participant code unchanged |
| `agent-framework-devui` | Lab 1 optional — `poe devui` (`uv sync --extra devui`) | Pre-release sample app `1.0.0b260918` | `uv run poe chat` (rich CLI) |
| `azure-monitor-opentelemetry-exporter` | Lab 4 — `src/care_agent/telemetry.py` | Beta `1.0.0b57` (the Azure Monitor exporter has always shipped as beta) | Local span file `.care_agent/spans.jsonl` + `/trace` and `poe traces` always work; console exporter via `TELEMETRY_CONSOLE=true` |
| Custom `headers_policy` (azure-core `HeadersPolicy`) passed into the Azure Monitor exporter to add `Ocp-Apim-Subscription-Key` | Lab 4 — `build_azure_monitor_exporters()` | Relies on the exporter forwarding kwargs to its azure-core pipeline configuration (verified in exporter source, not a documented public option) | Infra toggle `telemetry_require_subscription_key=false`: `/telemetry` accepts key-less payloads filtered by the workshop iKey, IP rate-limited, size-capped |
| Built-in safety evaluators (`ContentSafetyEvaluator`) through APIM `/foundry` with `ApimKeyCredential` | Lab 5 — `evals/run_evals.py` metric `builtin_safety` | Preview path (RAI service reached via the Foundry project proxy) | LLM-judge harm rating via `/openai` (`method: llm-fallback`), noted in `summary.json` |
| Agent evaluators `IntentResolutionEvaluator`, `TaskAdherenceEvaluator`, `ToolCallAccuracyEvaluator` | Lab 5 — `evals/run_evals.py` | Check `azure-ai-evaluation` 1.18.x release notes (introduced as preview; output scales changed between versions — normalised in `evals/scoring.py`) | Deterministic `tool_match` for `tool_call_accuracy`; missing judge metrics are skipped and weights re-normalised; `--no-judge` mode |
| Foundry cloud evaluation (`project.get_openai_client().evals` with `azure_ai_evaluator` `builtin.*` criteria) | Lab 5 optional — `poe cloud-eval` (`evals/cloud_eval.py`) | Preview | Automatic fallback to `poe upload-evals` |
| Foundry evals API with `string_check` graders for uploading local results | Lab 5 — `poe upload-evals` (`evals/upload_to_foundry.py`) | Evals API in Foundry (OpenAI-compatible) — treat as preview | Local `evals/out/<run-id>/summary.json` is the source of truth; optional `--dataset` upload; presenter shows results on screen |
| AI Red Teaming agent (`azure-ai-evaluation[redteam]`, PyRIT) via `/foundry` | Lab 5 optional — `poe redteam --foundry` | Preview (extra `redteam`) | Policy-driven red-team suite (always runs): rules parsed from the escalation & safety policy, attacks generated via `/openai`, template attacks offline |
| `azure-ai-projects` `.beta.*` operations (red teams, evaluators) | Only via the AI Red Teaming path above | Preview (`allow_preview` / `.beta`) | Same as above |
| Foundry hosted agents (`HostedAgentDefinition`) + `agent-framework-foundry-hosting` `ResponsesHostServer` | `deploy/` — presenter-only demo | Preview (`1.0.0b260918`, hosting protocol 2.0.0) | Same image on Azure Container Apps (GA); `azd ai agent init` + `azd deploy` |
| `CHAT_API=responses` (OpenAI Responses API through APIM `/openai`) | Optional override in `src/care_agent/agent.py` | Depends on the gateway route/api-version | Default `chat_completions` (`/openai/deployments/{d}/chat/completions`, api-version `2024-10-21` GA) |

## Preview features — presenter kit

Status as of September 2026 (`docs/CONTRACT.md` §10). Re-verify the week before the event.

| Feature | Where used | Status | Fallback |
|---|---|---|---|
| Foundry hosted agents | `presenter/live-demo-lab6.md` Part B (optional production runtime demo via `workshop/deploy/deploy_hosted_agent.py`) | Preview | Azure Container Apps fallback in `workshop/deploy/`; else screenshots `presenter/fallback/prod-*.png`; or skip (optional) |
| Foundry incoming A2A (agent endpoint A2A protocol; protocol 1.0, 0.3 in preview) | Lab 3 / slide 8; preflight `uv run poe a2a-card`, `uv run poe lab3` | Public preview | Container Apps adapter `care-knowledge-a2a` behind the same APIM route; `presenter/fallback/lab3-output.txt` |
| AI Red Teaming Agent / Foundry red teams API (`.beta.red_teams`) | Lab 5 `uv run poe redteam`; slide 11 | Preview | Local policy-derived adversarial prompts evaluated with the local rubric; `presenter/fallback/lab5-redteam.txt` |
| Cloud evaluations in Foundry | Lab 5 optional `uv run poe cloud-eval` | Preview | `uv run poe upload-evals` (upload local run); first item cut from Lab 5 if late |
| Safety evaluators via the `/foundry` proxy | Lab 5 evals | Preview | Local rubric safety checks (gate); recorded safety results |
| Foundry IQ knowledge bases (agentic retrieval on AI Search) | Lab 3 citations; preflight citation check | Mixed GA / preview depending on Search REST API version | Recorded output; session continues without citations (Labs 4–6 don't depend on them) |
| Foundry Agent Service REST `2026-08-01-preview` (KB connection for base agent) | Base agent used in Lab 3 | Preview API version | Same as Foundry IQ row |
| Foundry portal Tracing view | Lab 4 presenter screen share | Verify before event | App Insights transaction search / KQL printed by `uv run poe traces` |
| APIM "REST API as MCP server" | Lab 2 / slide 7 | Verify current status before event (APIM A2A agent API is GA) | `presenter/fallback/lab2-output.txt`, presenter demo |
| Agent Framework DevUI (`agent-framework-devui`) | Lab 1 optional `uv run poe devui` | Verify before event (developer tool) | `uv run poe chat` |
