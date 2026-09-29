# Infra — base platform for "From Prototype to Proof"

> **Training use only.** This workshop uses synthetic, fictional data. The Care Coordination Agent is
> not a medical device and does not provide clinical advice, diagnosis or treatment decisions.

This folder deploys everything the 1h45m workshop needs with one `terraform apply`: Microsoft Foundry
(new resource model), the base agent `care-knowledge-agent`, a Foundry IQ knowledge base over 12
synthetic documents, a mock clinical-tools backend, observability, and **Azure API Management as the
single front door**. Participants receive only two secrets-worthy values: the APIM gateway URL and a
personal subscription key.

```
participant laptop (local agent, OTel)
   │  Ocp-Apim-Subscription-Key / api-key + W3C traceparent
   ▼
Azure API Management (StandardV2, system MI)
   ├─ /openai/*            → Foundry models (MI, llm-token-limit, token metrics, LLM logs, retry)
   ├─ /care-tools/mcp      → MCP server (7 tools) → REST API care-tools-api → Container Apps (FastAPI mock)
   ├─ /a2a/care-knowledge  → Foundry incoming A2A of care-knowledge-agent (MI)  [fallback: A2A adapter]
   ├─ /foundry/*           → Foundry project data plane, allowlisted (MI; caller Authorization stripped)
   └─ /telemetry/*         → Application Insights ingestion (+ GET /telemetry/config)
                                   │
Foundry project <prefix>-proj ─────┴─ care-knowledge-agent ──MCP──► Foundry IQ KB care-kb (AI Search)
                                                                        └─ knowledge source care-docs-ks (blob care-docs)
Application Insights + Log Analytics: one trace per request (agent → APIM → model / tool / A2A → KB)
```

## Contents

| Path | What |
|---|---|
| `versions.tf`, `variables.tf`, `main.tf`, `rbac.tf`, `post_deploy.tf`, `outputs.tf` | Root module |
| `modules/monitoring` | Log Analytics + workspace-based Application Insights |
| `modules/search_storage` | Storage (`care-docs` container, Entra-only) + Azure AI Search (semantic ranker, agentic retrieval plan) |
| `modules/foundry` | AIServices account (`allowProjectManagement`), project, model deployments, project connections |
| `modules/container_apps` | ACR, Container Apps environment, `care-tools-backend`, optional `care-knowledge-a2a` |
| `modules/apim` | APIM service, loggers, diagnostics (W3C, LLM logging), global policy, product, backends |
| `modules/apim_apis` | `/openai`, `care-tools-api` + MCP server `care-tools`, `/a2a/care-knowledge`, `/foundry`, `/telemetry`; policies in `policies/*.xml` |
| `modules/participants` | Sensitive `random_password` key suffix + APIM subscription per participant, `.env` files, `participants.csv` |
| `modules/workbook` | Azure Monitor workbook (`workbook.json`) |
| `data/care-docs/` | 12 synthetic Markdown documents with section IDs |
| `apps/care_tools_backend/` | FastAPI mock tools; `app/openapi.json` is the MCP tool contract |
| `apps/a2a_adapter/` | FALLBACK A2A adapter (Agent Framework A2A hosting) |
| `scripts/` | `seed_knowledge.py`, `create_base_agent.py`, `smoke_test.py` (uv inline-script metadata) |
| `tests/` | pytest suites + `platform.tftest.hcl` (Terraform test with mock providers) |

## Prerequisites

| Tool / right | Version / detail |
|---|---|
| Terraform | **>= 1.9** (providers pinned: azurerm 5.7.0, azapi 2.13.0, random 3.9.1, local 2.9.1) |
| Azure CLI | logged in (`az login`) as a user with **Owner** (or Contributor + User Access Administrator) on the subscription; ACR Tasks must be allowed (`az acr build`) |
| uv | 0.12+ (runs the post-deploy scripts with their pinned inline dependencies; installs Python 3.12 itself) |
| Quota | Regional TPM quota for the three deployments (defaults: gpt-6-luna 500K, gpt-6-sol 200K, text-embedding-3-large 150K, GlobalStandard). Check with `az cognitiveservices usage list -l <region> -o table` |
| Resource providers | registered automatically by the azurerm provider (see `versions.tf`) |

### Download and install

These prerequisites are for the **presenter / admin deploying the infrastructure**, not workshop
participants. Install the tools on the machine where you will run Terraform. Internet access is
required to download providers, Python, script dependencies and container build dependencies.
Git is also needed to clone the repository and save the Terraform provider lock file.

#### Windows (PowerShell)

Install [WinGet via App Installer](https://learn.microsoft.com/windows/package-manager/winget/)
if `winget --version` is not available, then run:

```powershell
winget install --exact --id Git.Git
winget install --exact --id Hashicorp.Terraform
winget install --exact --id Microsoft.AzureCLI
winget install --exact --id astral-sh.uv
```

Approve any installer elevation prompts. Close and reopen your terminal (and VS Code, if using its
integrated terminal) so the updated `PATH` is loaded.

If WinGet is unavailable, use the official downloads:

* [Git for Windows](https://git-scm.com/downloads/win): run the installer and enable Git on `PATH`.
* [Terraform](https://developer.hashicorp.com/terraform/install): download the Windows ZIP for your
  CPU architecture, extract `terraform.exe` to a permanent folder, and add that folder to your user
  `Path` environment variable.
* [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli-windows): download and run the
  Windows MSI installer.
* [uv](https://docs.astral.sh/uv/getting-started/installation/): follow the Windows standalone
  installer instructions.

#### macOS (Terminal)

Install [Homebrew](https://brew.sh/) using its official instructions, including its shell setup step,
then run:

```bash
brew tap hashicorp/tap
brew install git hashicorp/tap/terraform azure-cli uv
```

#### Linux / WSL (Bash)

Follow the official instructions for your distribution:

1. Install [Git](https://git-scm.com/downloads/linux) using your distribution's package manager.
2. Install [Terraform](https://developer.hashicorp.com/terraform/install) using HashiCorp's
   Ubuntu/Debian or RHEL/Fedora repository instructions. Alternatively, download the Linux ZIP
   matching your CPU architecture, extract it, and put the `terraform` binary in a directory on `PATH`.
3. Install [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli-linux) using the
   instructions for your distribution.
4. Install [uv](https://docs.astral.sh/uv/getting-started/installation/) using the standalone installer:

   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

   Review the linked installer instructions before running it, and restart your shell afterward.

For WSL, install and run **all tools inside the same Linux distribution**, including `az login`;
do not mix Windows executables or authentication with the Linux deployment environment.

### Verify the tools and prepare Python

In a new terminal, run these commands on any platform:

```text
git --version
terraform version
az version
uv --version
uv python install 3.12
uv run --python 3.12 python --version
```

Confirm Terraform is **1.9 or newer**, uv is **0.12 or newer**, and Python reports **3.12.x**.
If an installed version is too old, upgrade it using the same package manager or installer.
If a command is not found, resolve its installation or `PATH` issue before deploying.
uv manages Python and the scripts' inline dependencies; a separate Python or pip installation is
not required. Terraform downloads its pinned providers during `terraform init`.
Local Docker is **not required** for the default deployment: images are built remotely with
`az acr build`. Only the local-build fallback in Troubleshooting needs
[Docker](https://docs.docker.com/get-started/get-docker/).

### Sign in and select the Azure subscription

Obtain access to an Azure subscription with the roles listed above; installing the tools does not
grant permissions or model quota. Then run:

```text
az login
az account list --output table
az account set --subscription "<subscription-id>"
az account show --query "{name:name, subscriptionId:id, tenantId:tenantId}" --output table
```

Replace `<subscription-id>` with the intended subscription's ID. For a terminal without a browser,
use `az login --use-device-code` if your organization's sign-in policy allows it.
If you set `subscription_id` in `terraform.tfvars`, use the same ID as the active CLI subscription.
Check regional model availability and quota in **Region choice** below before running `terraform apply`.

## Region choice

Pick a region that offers **all** of: the model versions in `model_deployments`, APIM v2 tiers,
Azure AI Search agentic retrieval (knowledge bases), Foundry Agent Service with incoming A2A (preview)
and Container Apps. The default is `swedencentral`; `eastus2` is a common alternative. Verify before
the event:

```bash
az cognitiveservices model list -l swedencentral --query "[?model.name=='gpt-6-luna' || model.name=='gpt-6-sol' || model.name=='text-embedding-3-large'].{name:model.name, version:model.version, skus:model.skus[].name}" -o table
az cognitiveservices usage list -l swedencentral -o table
```

plus the APIM v2 region list (<https://learn.microsoft.com/azure/api-management/api-management-region-availability>)
and the Search region table for agentic retrieval (<https://learn.microsoft.com/azure/search/search-region-support>).

## Deploy (do it the day before)

```bash
cd infra
cp terraform.tfvars.example terraform.tfvars      # set publisher_email; adjust region/SKUs/quotas
terraform init
terraform apply                                  # ~25-40 min with StandardV2; 45-90 min with classic tiers
git add .terraform.lock.hcl                      # commit the provider lock file (hashes), never the state
```

Deployment time is dominated by APIM (**StandardV2: ~5-15 min; Developer/Standard/Premium classic:
30-60+ min**), then the post-deploy steps (image builds 2-5 min, knowledge ingestion 2-10 min, agent
creation < 1 min). Deploy at least one day before the session and run the smoke test.

What `apply` does after the ARM resources exist (`post_deploy.tf`, all idempotent — re-running `apply`
only re-runs a step whose inputs changed):

1. `az acr build` for the mock backend (and the adapter in fallback mode).
2. `uv run scripts/seed_knowledge.py` — uploads the docs (skips unchanged), creates the fallback
   index `care-docs`, the knowledge source `care-docs-ks` and the knowledge base `care-kb`; writes
   `out/knowledge.json` (`mode: kb` or `index`).
3. `uv run scripts/create_base_agent.py` — creates a new version of `care-knowledge-agent` only if its
   definition changed, verifies the model route (APIM gateway connection, falls back to direct), enables
   incoming A2A + agent card; writes `out/base_agent.json`.

Plan-only / CI: `terraform plan -var run_post_deploy=false`.

## Verify

```bash
uv run scripts/smoke_test.py --env out/participants/<name>.env
```

Checks, with one participant key only: model call (`/openai/deployments/*` and `/openai/v1/*`), MCP
`initialize` + `tools/list` (7 tools) + read-only `search_patient` and `list_available_slots` calls
(including required and optional query arguments), A2A agent card + `message/send`
(`SendMessage` for A2A 1.0), `GET /telemetry/config` + a test envelope to `/telemetry/v2.1/track`,
Foundry list agents via `/foundry`, and that a forbidden Foundry call (DELETE of the base agent) gets
403. Prints a PASS/FAIL table; the trace ID printed at the top can be searched in Application Insights.

## Handing out keys

* `out/participants.csv` (`name,key,env_file`) and `out/participants/<name>.env` are **git-ignored** and
  written with mode 0600. `terraform output -json participant_keys` returns the same map.
* Give each participant **only their own** `.env` (or the three values `APIM_BASE_URL`,
  `APIM_SUBSCRIPTION_KEY`, `PARTICIPANT_ID`) through a 1:1 channel: printed card at the desk, a direct
  chat message, or a per-person link to a file share. Never email the CSV, never paste keys into a
  group chat or a slide, never commit them.
* Keep 2-3 spare subscriptions (`participant_count` = attendees + 3).
* Revoke one participant: APIM → Subscriptions → suspend. To rotate a primary key, replace that
  participant's `random_password.key_suffix` resource through Terraform and redistribute the updated
  `.env`. A manual primary-key rotation in the portal will be reverted by the next apply.
  After the workshop run `terraform destroy` (or suspend all participant subscriptions).

## Cost estimate (clearly an ESTIMATE — verify with the pricing pages)

Approximate USD list prices, pay-as-you-go, September 2026; your region, currency and agreements differ.

| Item | Assumption | ~ per hour | ~ per day |
|---|---|---|---|
| APIM StandardV2 (default) | 1 unit | 0.96 | 23 |
| APIM Developer (cheap option, no SLA) | 1 unit | 0.07 | 1.6 |
| APIM BasicV2 | 1 unit | 0.21 | 5 |
| Azure AI Search Basic | 1 replica, 1 partition, semantic ranker + agentic retrieval usage | 0.10 + usage | 2.5 + usage |
| Container Apps | 1 always-on replica 0.5 vCPU / 1 GiB (x2 in adapter mode) | 0.05 | 1.3 |
| Container Registry Basic | | 0.01 | 0.17 |
| Log Analytics / App Insights | 1-3 GB ingested during the session (~2.3-2.8 per GB) | — | 3-8 per session |
| Models (tokens) for 30 participants | ~1.5M in + 0.2M out gpt-6-luna and ~0.5M in + 0.05M out gpt-6-sol per participant; embeddings negligible | — | ≈ 60-90 per session |
| **Total (StandardV2, deployed ~48 h around the event)** | | | **≈ 140-200 overall** |

Pricing pages to verify: [API Management](https://azure.microsoft.com/pricing/details/api-management/),
[Azure AI Search](https://azure.microsoft.com/pricing/details/search/),
[Container Apps](https://azure.microsoft.com/pricing/details/container-apps/),
[Container Registry](https://azure.microsoft.com/pricing/details/container-registry/),
[Azure Monitor](https://azure.microsoft.com/pricing/details/monitor/),
[Foundry models / Azure OpenAI](https://azure.microsoft.com/pricing/details/cognitive-services/openai-service/),
[Pricing calculator](https://azure.microsoft.com/pricing/calculator/).

## Key decisions

* **APIM tier: StandardV2** by default. MCP servers, A2A agent APIs and the `llm-*` policies are
  available on Developer, Basic, Basic v2, Standard, Standard v2, Premium and Premium v2 — **not**
  Consumption (validated in `variables.tf`). v2 deploys in minutes and has an SLA; Developer is the
  budget option but deploys slowly (classic) and has no SLA.
* **A2A default: `a2a_mode = "native_foundry"`** — Foundry's incoming A2A endpoint (preview) exposed
  as an APIM A2A agent API with managed identity (`https://ai.azure.com`), `A2A-Version: 1.0`, and an
  explicitly configured card URL (the import wizard cannot fetch the Entra-protected card).
  Fallbacks: `a2a_apim_api_kind = "http"` (plain HTTP API: card operation rewrites
  `/.well-known/agent-card.json` → `…/agentCard/v1.0` and replaces backend URLs in the card) and
  `a2a_mode = "adapter"` (Agent Framework A2A adapter on Container Apps). The participant URL never
  changes: `https://<apim>/a2a/care-knowledge`.
* **Telemetry: APIM ingestion proxy with subscription key** (`telemetry_require_subscription_key =
  true`). Participant connection string: `InstrumentationKey=<ikey>;IngestionEndpoint=<APIM>/telemetry/`
  (no `LiveEndpoint`: keep Live Metrics off). Fallback `false`: anonymous, but only envelopes containing
  the workshop iKey, rate-limited per client IP, body capped at 3 MB.
* **Knowledge:** Foundry IQ knowledge base `care-kb` (MCP tool on the agent) with the classic index
  `care-docs` always created as a ready fallback (`knowledge_mode`).
* **Base agent model route:** `auto` — try the Foundry AI-gateway connection to APIM (preview), verify
  with one call, fall back to the direct deployment and record why in `out/base_agent.json`.
  The APIM-backed base agent sets reasoning effort to `none` because the gateway's Chat Completions
  route rejects function tools with reasoning enabled for the default model. Direct agent definitions
  and participant model calls are unchanged. Cached gateway failures apply only to the attempted
  definition hash; changing the definition retries APIM. Smoke tests target the created agent version,
  and failures without a successful fallback stop the script.
  `base_agent_model_deployment` optionally selects an existing deployment for the remote knowledge
  agent without changing participant chat. For example, use `gpt-6-sol` if `gpt-6-luna` is rejected by
  Foundry Agent Service; availability must be verified with a cited policy answer, not just model chat.
* **Identity:** keys are disabled on Foundry and Storage; APIM, Search, the Foundry project and the
  Container Apps use managed identities with least-privilege roles (`rbac.tf`). Backends reachable from
  the internet (Container Apps) require a shared secret header that only APIM (named value) knows.
* **In-memory mock state:** bookings/referrals are isolated **per participant** (`x-participant-id` set
  by APIM from the subscription), so 30 people can book "the first cardiology slot"; the app runs with
  exactly one replica.
* **Container Apps profile:** the environment explicitly retains its `Consumption` workload profile;
  both the tools backend and optional A2A adapter select it.
* **Foundry connections:** the Application Insights, Search, and Storage connections keep
  `isSharedToAll = false`; recovery does not broaden their existing sharing configuration.

Preview features and every fallback are listed in [`../docs/preview/infra.md`](../docs/preview/infra.md);
things that do not strictly go through APIM are in [`../docs/apim-exceptions/infra.md`](../docs/apim-exceptions/infra.md).

## Observability

* APIM Application Insights diagnostic uses `httpCorrelationProtocol = W3C`: APIM's request span is a
  child of the participant's span, and the backend call carries a new `traceparent` (Foundry,
  Container Apps). Frontend/backend response bodies are **never** logged globally (MCP guidance).
* LLM prompts/completions are logged by the Azure Monitor diagnostic (`largeLanguageModel`) to the
  Log Analytics table `ApiManagementGatewayLlmLog` (portal: APIM → Monitoring → Language models).
* Token usage: `llm-emit-token-metric` → Application Insights custom metrics (namespace `care-workshop`,
  dimensions Subscription ID, User ID = participant, API ID, Model). **Enable** *Application Insights →
  Usage and estimated costs → Custom metrics → With dimensions* once, otherwise dimensions are dropped.
* Foundry portal tracing works through the project's Application Insights connection.
* Workbook: `terraform output workbook_url` — tokens per participant, latency/errors per route and
  participant, MCP tool calls, A2A calls.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Foundry `embedded schema validation failed` / API version invalid | The Foundry module uses ARM `2026-05-01`, supported by the pinned AzAPI provider. Keep schema validation enabled; run `terraform validate` after changing API versions. |
| Search KB PUT rejects `outputMode` with API `2026-04-01` | The seeder sends GA fields on the initial GA request. If query-planning models are rejected, the model-less fallback uses the preview MCP API version to persist `retrievalReasoningEffort = minimal` and `outputMode = extractiveData`. Without these settings, the KB exists but MCP retrieval fails. Re-apply after updating the script; its hash triggers reseeding. |
| APIM `azuremonitor` logger / global `policy` already exists | These built-in objects use `azapi_update_resource`, not creation. No import is needed after the failed initial apply. Removing an update resource does not revert its properties; destroying the APIM service removes its children. |
| Product/API association returns `405 Method Not Allowed` on GET | Bindings use `azurerm_api_management_product_api`, which checks existence with HEAD. All participant routes, including optional REST access, use this resource. |
| `InsufficientQuota` / `DeploymentModelNotSupported` on a deployment | Lower `capacity`, change `sku` (e.g. `Standard`) or region; check `az cognitiveservices usage list`. |
| `az acr build` fails (ACR Tasks not allowed in the subscription) | Build and push locally: `docker build -t <acr>.azurecr.io/care-tools-backend:<tag> apps/care_tools_backend && az acr login -n <acr> && docker push …`, then `terraform apply` again. |
| Scripts print `HTTP 403 (RBAC propagating?)` | They retry for ~3 min; if it still fails wait a few minutes and run `terraform apply` again (idempotent). |
| Base agent latest-version lookup returns `InternalServerError: Unable to get resource information` or `Timeout` | This is a Foundry data-plane failure, not a WSL error. Agent setup retries transient HTTP 408/429/500/502/503/504 responses and status-less `Timeout`/`InternalServerError` errors up to four attempts, waiting 5/10/15 seconds between attempts (in addition to SDK retries). If exhausted, it fails without replacing the agent or overwriting its cached output. Keep the Terraform state and re-run `terraform apply` after Foundry recovers; do not delete the agent or skip latest-version validation. |
| Name conflict after destroy + apply | Soft-deleted resources: `az apim deletedservice purge -n <apim> -l <region>`; `az cognitiveservices account purge -n <foundry> -g <rg> -l <region>`. |
| Token tiles in the workbook are empty | Enable custom metrics **with dimensions** on Application Insights (see Observability). |
| `/a2a/care-knowledge` 401/403/404 | Check `out/base_agent.json` (`a2a_enabled`), APIM MI has *Foundry User* on the project; try `a2a_apim_api_kind = "http"`, else `a2a_mode = "adapter"`. |
| A2A returns a failed task or an answer without citations | Inspect adapter logs and the knowledge MCP response, not just HTTP 200. Agent setup revalidates cached versions for a policy citation and republishes the working definition if a newer failed version displaced it: unversioned A2A calls use the latest version. The A2A smoke check rejects failed/incomplete tasks, empty answers, and missing policy citations. |
| `/a2a/care-knowledge` read timeout while other routes pass | In adapter mode, check `az containerapp revision list -g <rg> -n care-knowledge-a2a -o table` and `az containerapp logs show -g <rg> -n care-knowledge-a2a --type console --tail 60`. A startup crash can leave APIM waiting for a backend; increasing the client timeout will not fix it. `An A2A agent card requires a description` means the image predates the fix that supplies public metadata to `AgentA2AAdapter` before `get_card()`. Review a Terraform plan and re-apply to rebuild the source-hashed image and deploy a new revision. |
| MCP `tools/list` misses tools / tool creation 400 | The tool `operationId` must be the ARM ID of an imported operation named after the OpenAPI `operationId`: `az apim api operation list -g <rg> -n <apim> --api-id care-tools-api -o table`. |
| MCP client hangs / streaming breaks | A diagnostic or policy is reading the response body; keep frontend response bytes = 0 and do not use `context.Response.Body` in MCP policies. |
| Lab 2 reads the care plan but cannot book; slot search reports `cardiology?within_days=7` | The backing REST import promoted required query arguments into URL templates, and MCP appended optional arguments with a second `?`. Keep `translateRequiredQueryParameters = "query"` on the REST API import and re-apply the reviewed Terraform plan. The slot operation should use `/slots`, with both arguments in `request.queryParameters`. The infra MCP smoke check now validates the slot-search result even when MCP returns HTTP 200 around a backend validation error. |
| MCP tool call returns 401 from APIM | The backing REST API requires a subscription; set `care_tools_rest_in_product = true` (documented fallback). |
| `/foundry` returns 403 `WorkshopAllowlist` | The operation is not allowlisted; extend the allowlist in `modules/apim_apis/policies/foundry.xml`. |
| Knowledge base was not created (`out/knowledge.json` `mode: index`) | The agent automatically uses the Azure AI Search tool on `care-docs`; set `knowledge_mode = "kb"` to make KB failures fatal and see the error. |
| Base agent model calls went direct (`apim_route_error` in `out/base_agent.json`) | APIM-backed definitions set reasoning effort to `none` for tool compatibility. Re-apply after updating the script: its hash reruns agent setup, and legacy/different-definition failure caches are retried automatically. Set `base_agent_model_route = "apim"` to retry strictly without a direct fallback. |
| Telemetry exporter cannot send the subscription header | Set `telemetry_require_subscription_key = false` (fallback) and re-apply. |

After the partial-apply errors above, run `terraform validate`, `terraform plan`, then
`terraform apply` from this folder. Keep the existing state; do not destroy the platform or
manually delete APIM defaults. The failed resources are not in state and will use the corrected
definitions on the next apply.

Adapter startup regression tests run separately from the infra test harness because the adapter
requires a different Foundry SDK version. From `apps/a2a_adapter`, run
`uv run python -m unittest test_app`. These offline tests use the real pinned A2A SDK to verify
startup, Agent Card metadata, the health endpoint, and shared-secret enforcement without Azure calls.

For a deployment that **already tracks** the old `azapi_resource.logger_azuremonitor`,
`azapi_resource.global_policy`, or `azapi_resource.product_api` addresses, back up state first.
Remove only those old addresses from state (`terraform state rm`, not a cloud delete) before
applying the updated definitions. Import any existing product/API associations into their new
`module.apim_apis.azurerm_api_management_product_api.product_api["<key>"]` addresses using their
full ARM IDs. The built-in logger/policy updates need no import. Inspect the plan and stop if it
proposes deleting these objects.

## Destroy

```bash
terraform destroy
az apim deletedservice purge -n <apim-name> -l <region>          # optional: frees the name immediately
az cognitiveservices account purge -n <foundry-name> -g <rg> -l <region>
```

`out/` keeps the old keys and env files — delete it after the workshop.

## Tests and validation

```bash
uv run pytest                        # backend, naming, docs, policy XML, Search KB payloads (from infra/)
terraform fmt -check -recursive
terraform init -backend=false && terraform validate
terraform test                       # tests/platform.tftest.hcl, mock providers, no Azure access
```

Focused APIM regression tests (WSL Bash, no Azure access):

```bash
terraform test -filter=tests/apim_resources.tftest.hcl
```

These cover built-in logger/policy updates, all five default product bindings, optional REST
access, and the HTTP A2A fallback.
* Participant names are `user01` through `user99`. Each primary key is the name followed by three
  random lowercase letters/digits, with no separator (for example, `user07k3x`, illustrative only).
  Suffixes are generated separately from the former public name suffixes, are sensitive in Terraform,
  and remain stable across applies. Secondary keys are left APIM-generated.
* **Workshop-only credentials:** there are only 46,656 possible suffixes per participant. Use these
  short keys only for a short-lived, controlled workshop, never for production or sensitive data.
* **Migration:** applying this naming change replaces existing subscriptions with the new IDs and
  replaces their tracked `.env` files. Old primary and secondary keys stop working. Redistribute
  the regenerated `out/participants/userNN.env` files and CSV; historical telemetry retains the old
  participant names. Review the plan and migrate outside an active workshop.
