# Troubleshooting FAQ (symptom → cause → fix)

First move for any participant issue: `uv run poe smoke` from `workshop/` — it tells you which route is failing. Never ask anyone to paste their key or `.env` into chat; look at their screen instead.

Quick reference

| Route | Key header | Notes |
|---|---|---|
| `/openai/*` | `api-key` | Azure OpenAI SDKs use it unchanged |
| `/care-tools/mcp`, `/a2a/care-knowledge/*`, `/foundry/*`, `/telemetry/*` | `Ocp-Apim-Subscription-Key` | Workshop clients send both headers |

## 1 · 401 Unauthorized — bad or missing key

| Symptom | Cause | Fix |
|---|---|---|
| 401 "Access denied due to missing subscription key" | Wrong header for the route (e.g. `api-key` on `/care-tools/mcp`, or `Ocp-Apim-Subscription-Key` only on `/openai`) | Send both headers (workshop code does); for `/openai` the header is `api-key` |
| 401 "invalid subscription key" | Typo, trailing space/quote, CRLF in `.env`; key copied from a spare card that was revoked | Re-copy the key; no quotes around values; save `.env` with LF; compare `PARTICIPANT_ID` with the card |
| 401 on one API only | Subscription/key not in product `workshop-participants`, or API not added to the product | Admin: APIM → Subscriptions → check scope = product `workshop-participants`; check the API is in the product |
| 401 from backend (not APIM) | APIM managed identity lacks role (e.g. Foundry User) | Admin: fix role assignment in infra, `terraform apply` |
| 404 on `/openai` | Wrong deployment name, or endpoint includes `/openai` so the SDK builds `/openai/openai/...` | `OPENAI_ENDPOINT` = `APIM_BASE_URL` (SDK appends `/openai/...`); deployment `gpt-6-luna` |
| 403 on `/foundry` | Operation not on the `/foundry` allowlist | Expected for non-workshop operations; use only the `uv run poe` commands |

## 2 · 429 Too Many Requests — token limit

| Symptom | Cause | Fix |
|---|---|---|
| 429 from APIM with `Retry-After` header | Per-subscription `llm-token-limit` (tokens per minute) hit — typical in Lab 5 | Wait `Retry-After` seconds (SDKs retry automatically); don't run evals in parallel loops; stagger rows |
| 429 for everyone, low per-user usage | Backend deployment TPM/quota exhausted | Stagger; reduce concurrent runs; presenter demos from recording; request more quota next time (preflight formula) |
| 429 on judge only | Judge `gpt-6-sol` deployment smaller than chat | Same as above; run `uv run poe evals` once, not repeatedly |

**Presenter: raise limits**
- Quick fix (seconds, live): Azure portal → APIM → APIs → `/openai` API → policy → increase `tokens-per-minute` in `llm-token-limit` → Save. Only if the backend deployment has headroom, otherwise you just move the 429 to the backend.
- Permanent fix: change `token_limit_tpm` (per-subscription tokens per minute, default 20000) in `infra/terraform.tfvars` and run `terraform apply` from `infra/`.
- A portal edit is drift: the next `terraform apply` resets it to `token_limit_tpm`. Set the tfvar to the value you want to keep. Logged in `docs/apim-exceptions/presenter.md`.
- Save participants' tokens: `uv run poe evals --rescore` (weights only, no model calls), `--limit <n>` / `--ids G01,G09`, `--no-judge`; `uv run poe loop --quick` or `--offline`.
- Token tiles in the workbook are empty → Application Insights custom metrics **with dimensions** not enabled (§5).

## 3 · MCP handshake errors (`/care-tools/mcp`)

| Symptom | Cause | Fix |
|---|---|---|
| 404 / "not an MCP server" | Wrong URL (`/care-tools`, `/care-tools-api`, trailing `/sse`) | `MCP_URL = ${APIM_BASE_URL}/care-tools/mcp` exactly |
| Handshake hangs, then timeout | Client uses SSE transport | Use streamable HTTP (`MCPStreamableHTTPTool`), not an SSE client |
| 401 on `initialize` | Missing `Ocp-Apim-Subscription-Key` on MCP requests | Pass the header via the tool's headers/`header_provider` |
| `initialize` / `tools/list` OK, but **tool calls** return 401 (everyone) | Backing REST API `care-tools-api` not reachable with the participant subscription | Admin: `care_tools_rest_in_product = true` in `infra/terraform.tfvars` → `terraform apply` |
| Works for small calls, hangs/truncates for all users | APIM buffering the response body: global App Insights/Azure Monitor diagnostic logs frontend response payload bytes, or a policy reads `context.Response.Body` | Admin: set frontend response payload bytes to 0 on global diagnostics (log payloads per-API instead); remove body access from MCP policies |
| Works on phone hotspot, fails on venue/corporate network | Proxy / TLS inspection breaks streaming or strips headers | Use Codespaces or hotspot; set `HTTPS_PROXY` if a proxy is mandatory |
| `mcp-tools` lists fewer than 7 tools | Tool not exposed on the MCP API / product | Admin: check APIM MCP server tools; `terraform apply` |
| 409 from `book_follow_up` | Slot already booked by another participant | Expected; the agent should list slots again and pick another |

## 4 · A2A Agent Card not found / A2A errors (`/a2a/care-knowledge`)

| Symptom | Cause | Fix |
|---|---|---|
| 404 on card | Wrong path (e.g. `agent.json`, missing `/a2a`) | `${APIM_BASE_URL}/a2a/care-knowledge/.well-known/agent-card.json`; test with `uv run poe a2a-card` |
| 401/403 from backend on card or call | Native Foundry card requires Entra; APIM not using managed identity, or MI lacks **Foundry User** | Admin: APIM backend auth = managed identity, resource `https://ai.azure.com`; grant Foundry User |
| 400 / version error | Missing `A2A-Version: 1.0` header towards Foundry | Admin: APIM policy sets `A2A-Version: 1.0` |
| Card returned but calls go to `*.services.ai.azure.com` and fail | Card URL not rewritten to APIM | Admin: ensure APIM A2A API rewrites hostname (or adapter rewrites) |
| Card 404 for everyone | Incoming A2A (preview) not enabled on `care-knowledge-agent`, or region issue | Admin: `a2a_mode = "adapter"` (Container App `care-knowledge-a2a`) → `terraform apply`; presenter demos from `fallback/lab3-output.txt` meanwhile |
| `terraform apply` rejects the APIM A2A API type | APIM A2A agent API ARM shape not accepted | Admin: `a2a_apim_api_kind = "http"` (plain HTTP API with card + JSON-RPC operations, MI auth) → `terraform apply` |
| Answer without citations | KB `care-kb` / knowledge source `care-docs-ks` not indexed, or role missing (Search Index Data Reader for project MI) | Admin: check indexer on `care-docs`; if the knowledge base is the problem, `knowledge_mode = "index"` (plain AI Search index + Azure AI Search tool) → `terraform apply`; continue the session — Lab 4+ don't need citations |

## 5 · Missing traces

| Symptom | Cause | Fix |
|---|---|---|
| Nothing in App Insights after 1 min | Normal ingestion delay 2–5 min | Generate traffic early (`uv run poe lab2`), wait, then `uv run poe traces` |
| Nothing after 5 min | Connection string not pointing at APIM | `IngestionEndpoint=${APIM_BASE_URL}/telemetry/` (trailing slash); in the provided `.env` or from `/telemetry/config` |
| Exporter logs 401 (often silent) | Subscription key header not added to the exporter pipeline | Use the workshop telemetry setup (it adds `Ocp-Apim-Subscription-Key`); don't replace it with a plain exporter |
| Short script ends, no spans | Process exits before the exporter flushes | Use the lab entry points (they flush on shutdown) |
| Only some spans | Sampling configured (`OTEL_TRACES_SAMPLER*`) | Unset sampling env vars for the workshop |
| Can't find *my* trace | Filtering wrong | Filter `service.name` (App Insights `cloud_RoleName`) = your `PARTICIPANT_ID` |
| Traces in App Insights but not in Foundry portal Tracing | App Insights not connected to the Foundry project | Admin: connect App Insights in the project; participants use presenter screen share |
| No prompt/response content in spans | Sensitive-data capture off (default) | Expected; keep it off |
| Everyone fails on `/telemetry` | Telemetry API / exporter-header issue | Admin: `telemetry_require_subscription_key = false` → `terraform apply` (anonymous ingestion limited to the workshop iKey, IP rate-limited, body capped); revert after |
| Workbook token panels empty (traces fine) | App Insights custom metrics **with dimensions** not enabled — dimensions (User ID, Model…) are dropped | Admin: Application Insights → Usage and estimated costs → Custom metrics → *With dimensions*; new data only |
| `uv run poe loop` doesn't show App Insights data | By design: the loop reads eval results + trace IDs + local spans; querying App Insights needs Azure RBAC not proxied by APIM | Expected; open a trace ID in App Insights on the presenter screen |

Sample KQL (illustrative — `uv run poe traces` prints the real one):

```kusto
dependencies
| where timestamp > ago(30m)
| where cloud_RoleName == "user07"
| project timestamp, operation_Id, name, duration, success
| order by timestamp desc
```

## 6 · Eval judge errors (`uv run poe evals`, `redteam`, `upload-evals`, `cloud-eval`)

| Symptom | Cause | Fix |
|---|---|---|
| 404 DeploymentNotFound | Judge deployment name mismatch | `JUDGE_MODEL=gpt-6-sol` (or the name in your `.env`) |
| 400 unsupported api-version | Pinned `OPENAI_API_VERSION` overridden | Remove the override from `.env` |
| Content filter errors on red-team prompts | Adversarial prompts (generated from SAFE-001 rules SAFE-NEVER-01..12) tripped the model's filter | Expected; counts as blocked — the harness should record, not crash |
| `redteam` can't fetch the policy / too slow | Policy fetched via A2A, or budget exhausted | `uv run poe redteam --offline` (template prompts + heuristic scoring); the policy source is `infra/data/care-docs/09-escalation-and-safety-policy.md` |
| 429 during judging | Token limit (see §2) | Stagger; run once; `--limit <n>` or `--no-judge` |
| Participant wants to try other rubric weights | Re-running the full eval burns tokens | `uv run poe evals --rescore` re-applies the edited rubric to the stored run with no model calls |
| Import errors / evaluator signature errors | `azure-ai-evaluation` version drift (manually installed package) | `uv sync` (restores pinned versions); never `pip install` into the venv |
| Safety evaluators fail with 403/404 | Safety evaluators via the `/foundry` proxy are preview / operation not allowlisted | Continue with the local rubric safety checks; presenter shows recorded safety results |
| `cloud-eval` fails | Preview API | Use `uv run poe upload-evals` instead |
| `upload-evals` 401 | Placeholder credential / key header missing | Use the workshop `ApimKeyCredential` path (the command does); check key |

## 7 · `uv sync` failures

| Symptom | Cause | Fix |
|---|---|---|
| TLS / certificate errors | Corporate proxy with TLS inspection | Set `HTTPS_PROXY`; set `UV_NATIVE_TLS=1` to use the OS trust store |
| "Failed to download Python" | Python download blocked | Install Python 3.12 locally and set `UV_PYTHON_DOWNLOADS=never`; or use Codespaces |
| Very slow first sync | Cold cache / antivirus scanning | Start `uv sync` in Lab 0 immediately; Windows: exclude the repo folder from real-time scanning if policy allows |
| Resolution errors | Local edits to `pyproject.toml` / `uv.lock` | Restore the files from git, then `uv sync` |

## 8 · Codespaces

| Symptom | Fix |
|---|---|
| Slow start | Open before the session; keep the tab active |
| DevUI / docs site not reachable | Open the forwarded port from the Ports tab (docs at port 8000) |
| Codespace stopped after idle | Restart; `.env` persists in the workspace |
| Where do I put my key? | `workshop/.env` in the Codespace (git-ignored); never commit it |

## 9 · Windows

| Symptom | Fix |
|---|---|
| "Activate.ps1 cannot be loaded" | No activation needed — always use `uv run ...` |
| `.env` not picked up | Notepad saved it as `.env.txt`; enable file extensions and rename |
| Path too long / file lock errors | Clone to a short path outside OneDrive-synced folders (e.g. `C:\src\`) |
| Values with stray `\r` | Save `.env` with LF line endings (VS Code status bar) |
| Backslashes in paths | Commands in this kit use forward slashes; they work in PowerShell too |

## 10 · Infra switches (admin, `infra/terraform.tfvars` → `terraform apply` from `infra/`)

Each apply changes shared infrastructure for everyone. Announce it, and allow a few minutes (APIM policy/API changes are usually quick; new Container Apps take longer). Revert after the session if it was a fallback.

| Variable | Values (default first) | Flip when | Effect |
|---|---|---|---|
| `token_limit_tpm` | `20000` | APIM 429s for normal usage (§2) | Per-subscription tokens per minute in `llm-token-limit` on `/openai` |
| `a2a_mode` | `native_foundry` / `adapter` | Card or A2A calls fail for everyone (§4) | `/a2a/care-knowledge` backed by the Container Apps adapter `care-knowledge-a2a` instead of Foundry incoming A2A (preview) |
| `a2a_apim_api_kind` | `a2a` / `http` | APIM A2A API type rejected at apply (§4) | Plain HTTP API with explicit card + JSON-RPC operations |
| `care_tools_rest_in_product` | `false` / `true` | MCP tool calls return 401 (§3) | Adds backing REST API `care-tools-api` to product `workshop-participants` |
| `telemetry_require_subscription_key` | `true` / `false` | `/telemetry` fails for everyone (§5) | Anonymous ingestion, iKey-filtered, IP rate-limited, body capped |
| `knowledge_mode` | `auto` / `kb` / `index` | Knowledge base returns nothing / errors (§4) | `index` = plain AI Search index + Azure AI Search tool instead of the Foundry IQ knowledge base |

## 11 · Lab 6 loop (`uv run poe loop`, `promote`, `rollback`)

| Symptom | Cause | Fix |
|---|---|---|
| "Nothing to fix: every case passed" | Baseline passed all cases | `uv run poe redteam` to find new failures, then `uv run poe loop` again |
| Loop too slow / 429 | Full validation re-runs the dataset with judges | `uv run poe loop --quick` (failing + critical cases only) |
| No model budget left | Token limit / quota | `uv run poe loop --offline` (deterministic metrics + template proposal, no model calls) |
| Candidate rejected | Gate: needs a real improvement (Δ ≥ +0.01) and no safety regression | Expected — the gate works. Run without `--quick`, or accept it. For a demo only: `uv run poe promote --version vN --force` |
| `promote`: "No validated candidate" | Loop was not run, or candidate rejected | Run `uv run poe loop` first |
| `rollback` error | Active version has no parent (already at v1) | Nothing to roll back to; promote a candidate first |
| Agent still behaves like the old version | Active version is read at startup | Restart `uv run poe chat` |
