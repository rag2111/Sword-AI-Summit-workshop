# Where "everything through APIM" is not strictly met

Every participant call (models, MCP tools, A2A, telemetry ingestion, Foundry evaluation data-plane) goes through Azure API Management with only a subscription key. The tables below list every remaining exception, the reason and the mitigation.

## APIM exceptions — infra (Deliverable 1)

Everything a **participant** calls goes through APIM (`/openai`, `/care-tools/mcp`, `/a2a/care-knowledge`,
`/foundry`, `/telemetry`). The items below are the traffic paths that do not strictly pass through APIM.

| What cannot strictly go through APIM | Why | Mitigation |
|---|---|---|
| Base agent `care-knowledge-agent` → Foundry IQ knowledge base / Azure AI Search (MCP tool, or Search tool in fallback) | Internal service-to-service call made by Foundry Agent Service through a project connection (project managed identity); the platform does not route tool calls to its own knowledge layer via an external gateway | Read-only RBAC (project MI: *Search Index Data Reader*); calls appear in Foundry traces; the knowledge base is not exposed to participants directly |
| Base agent → model, when `base_agent_model_route` resolves to `direct` | The Foundry AI-gateway connection to APIM (category `ApiManagement`) is preview; if the test call fails the script falls back to the direct deployment (reason recorded in `out/base_agent.json`) | Default `auto` tries APIM first (dedicated subscription `svc-foundry-agent`, metered like a participant); in direct mode usage is still bounded by deployment capacity and visible in Foundry monitoring |
| Azure AI Search → Foundry models (embeddings during ingestion, LLM query planning at retrieval) | Search calls the model endpoint with its own managed identity; not configurable to a gateway URL with MI auth | Search MI has *Cognitive Services User* on the Foundry account only; deployment capacity limits apply |
| Foundry cloud evaluations / red-team runs → judge model | Executed inside Foundry with the project managed identity after the participant submits them via APIM `/foundry` | Submission itself goes through APIM (allowlisted, metered per participant); project MI has *Cognitive Services OpenAI User* only |
| Dataset/file uploads started via `/foundry` (`startPendingUpload` returns a SAS URL) | The SDK uploads the blob **directly** to project storage using the returned SAS URL | Only small evaluation files; the SAS is short-lived and scoped; allowlist only permits dataset operations on the workshop project |
| Post-deploy admin scripts (`seed_knowledge.py`, `create_base_agent.py`) → Storage, Search, Foundry, ARM | Run by the admin with the Azure CLI identity before the workshop to create data-plane objects | Admin-only RBAC granted to the deployer; idempotent; never used by participants |
| Terraform / `az acr build` → ARM and ACR | Control-plane provisioning and image builds | Admin-only; no participant credentials involved |
| APIM → Container Apps (`care-tools-backend`, fallback `care-knowledge-a2a`) over public ingress | APIM is not VNet-integrated in this workshop setup, so the apps need external ingress | Every request must carry `x-backend-secret` (APIM named value, random 40 chars); apps return 403 otherwise. Production: VNet-integrated APIM + internal ingress |
| A2A adapter (fallback) → Foundry agent | Service-to-service call from behind APIM with the adapter's user-assigned identity | Identity has *Foundry User* on the project only; participants still reach it only via `/a2a/care-knowledge` |
| Telemetry fallback mode (`telemetry_require_subscription_key = false`) | Some exporters cannot add the subscription-key header | `/telemetry` still goes through APIM but anonymously: only envelopes containing the workshop iKey are forwarded (non-gzip), rate limit 300/min per client IP, body ≤ 3 MB; switch back after the workshop |
| Application Insights Live Metrics (QuickPulse) | Would connect to the regional live endpoint directly | Participant connection string has no `LiveEndpoint`; keep Live Metrics disabled in the exporter |
| Presenter/admin use of the Foundry portal and Azure portal | Human admin access for demos and troubleshooting | Entra ID + RBAC; not part of the participant path |

## APIM exceptions — workshop (Deliverable 2)

Everything a participant runs goes through APIM with only `APIM_BASE_URL`, `APIM_SUBSCRIPTION_KEY` and
`PARTICIPANT_ID`. The items below are the places where traffic, access or identity does **not** follow that
rule, why, and how the workshop contains them.

| What | Why | Mitigation |
|---|---|---|
| Reading traces in Application Insights / Foundry tracing (querying, not ingestion) | Querying Log Analytics / App Insights requires Azure RBAC and a query API that the gateway does not proxy; participants have no Azure identity by design | Local span capture (`.care_agent/spans.jsonl`, `/trace`, `poe traces`) shows the full client-side trace tree; every eval row stores its trace ID; the presenter shows the end-to-end transaction on screen; `poe traces` prints KQL for anyone with Reader access. Lab 6 `pull_failures` uses eval outputs + trace IDs instead of App Insights queries |
| Telemetry fallback route without subscription key | Only if the Azure Monitor exporter cannot send the `Ocp-Apim-Subscription-Key` header (custom `headers_policy` stops working in a future exporter version) | Infra toggle `telemetry_require_subscription_key` (default `true`). When `false`, `/telemetry` forwards only payloads whose iKey equals the workshop iKey, rate-limits by IP and caps body size. Statsbeat is disabled in `telemetry.py` so no SDK telemetry bypasses APIM |
| Foundry dataset upload (`poe upload-evals --dataset`, optional) | `project.datasets.upload_file` obtains a short-lived SAS URL and uploads the file bytes directly to the project's storage account | Off by default; the default upload path sends results inline through `/foundry` (evals API). SAS is scoped to one blob container and expires quickly; data is synthetic |
| Foundry portal (compare eval runs, view red-team results) | The portal requires an Entra sign-in with project access | Presenter screen; local `summary.json`, `results.jsonl`, `comparison.json` hold the same information |
| SDK-derived safety service endpoints (`ContentSafetyEvaluator`, AI Red Teaming agent) | `azure-ai-evaluation` may derive Responsible-AI service URLs from the project endpoint; if it builds a host other than the APIM `/foundry` proxy, the call has no valid credential and fails | Both are labelled preview; failures switch to the LLM-judge safety fallback (via `/openai`) and to the policy-driven red-team suite; noted in `summary.json` |
| Cloud evaluation judge calls (`poe cloud-eval`) | Foundry runs the built-in evaluators server-side and calls the judge deployment inside Azure, not through APIM | Token usage for cloud evals is not in APIM's per-participant token metrics; eval runs carry `participant_id` / agent version in metadata; cloud eval is optional |
| Presenter-only deployment (`workshop/deploy/`: `az acr build`, `HostedAgentDefinition`, Container Apps) | Building images and creating hosted agents are control-plane operations that need an admin Azure identity (AcrPush, Foundry Project Manager) | Never part of the participant path; clearly marked presenter-only. The hosted agent itself still calls models/tools through APIM with a presenter key stored as a secret |
| Package and tool downloads during setup (uv, Python, PyPI, GitHub) | Standard developer tooling; not an Azure data-plane call | Exact version pins in `pyproject.toml` / `uv.lock`; Codespaces/devcontainer as a controlled alternative |

## APIM exceptions — presenter kit

Places where the presenter (not participants) steps outside "everything via APIM with a subscription key".

| What | Why | Mitigation |
|---|---|---|
| Optional production deploy (`workshop/deploy/`: image build/push, Foundry hosted agent or Container Apps creation) uses the presenter's **admin Entra identity** | Control-plane operations; the APIM `/foundry` allowlist intentionally blocks agent creation/deployment for participants | Presenter-only, from the presenter machine, least-privilege role scoped to the workshop resource group/project; the deployed agent's runtime traffic (models, MCP tools, A2A, telemetry) still goes via APIM with a dedicated presenter subscription key stored as a secret; demo shows this in traces |
| Invoking the hosted agent directly on its Foundry endpoint (Entra) during the Part B demo | Hosted agent endpoints are Foundry-native | Presenter-only; participants never call it; its outbound calls remain via APIM |
| Portal viewing of traces and evaluation runs (App Insights, Foundry portal Tracing/Evaluations) requires Azure / Foundry portal sign-in | Portals are not proxied by APIM; participants have keys only, no Entra roles | Primary: presenter screen share (Lab 4, Lab 5). Optional: grant participants with tenant accounts temporary read-only access (Reader on the Foundry project, Monitoring/Log Analytics Reader on App Insights), time-boxed and removed after the session. Local artifacts (`evals/out/<run-id>/`, console output) need no portal |
| Preflight verification in portals (App Insights, Foundry, APIM) with admin identity | Needed to confirm traces, eval uploads, token metrics | Read-only actions; performed before the session |
| Temporary live edit of `llm-token-limit` in the APIM portal | Incident response to 429s during Lab 5 | Only if backend TPM has headroom; noted on the timing card; reverted by `terraform apply` from `infra/` after the session |
| Telemetry fallback toggle (`telemetry_require_subscription_key` = false) if `/telemetry` fails for everyone | Keep Lab 4 running | Owned by infra: iKey-filtered, IP rate-limited, body-size capped; switch back after the session |
| Participant keys distributed out-of-band (printed cards / QR / secure share) from `participants.csv` | Keys must reach people before they can use APIM | Never post keys in chat or email the CSV; spare cards tracked; keys revoked or `terraform destroy` right after the session |

