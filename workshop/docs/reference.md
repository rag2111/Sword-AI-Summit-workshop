# Reference

## Environment variables

Only the first three are required. Everything else is derived by `src/care_agent/config.py`; set a value in
`.env` only to override it. The infra-generated participant file (`infra/out/participants/<name>.env`) contains
all of them explicitly.

| Variable | Default / derivation | Used by |
|---|---|---|
| `APIM_BASE_URL` | **required** — `https://<apim-name>.azure-api.net` | everything |
| `APIM_SUBSCRIPTION_KEY` | **required** — sent as `Ocp-Apim-Subscription-Key` **and** `api-key` | everything |
| `PARTICIPANT_ID` | **required** — e.g. `user07`; becomes `service.name` | telemetry, evals, Foundry run names |
| `OPENAI_ENDPOINT` | `= APIM_BASE_URL` (the SDK appends `/openai/...`) | chat client, judges |
| `OPENAI_API_VERSION` | `2024-10-21` (GA) | chat client, judges |
| `CHAT_MODEL` | `chatModel` from `/telemetry/config`, else `gpt-6-luna` | agent |
| `JUDGE_MODEL` | `judgeModel` from `/telemetry/config`, else `gpt-6-sol` | evaluators, red team, loop |
| `EMBEDDING_MODEL` | `text-embedding-3-large` | loop `--embeddings` |
| `CHAT_API` | `chat_completions` (or `responses`) | chat client class |
| `MCP_URL` | `${APIM_BASE_URL}/care-tools/mcp` | Lab 2 |
| `A2A_AGENT_CARD_URL` | `${APIM_BASE_URL}/a2a/care-knowledge/.well-known/agent-card.json` | Lab 3 |
| `FOUNDRY_PROJECT_NAME` | `foundryProjectName` from `/telemetry/config` | Lab 5 |
| `FOUNDRY_PROJECT_ENDPOINT` | `${APIM_BASE_URL}/foundry/api/projects/${FOUNDRY_PROJECT_NAME}` | Lab 5 |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | `connectionString` from `/telemetry/config` (`IngestionEndpoint=${APIM_BASE_URL}/telemetry/`) | Lab 4 |
| `ENABLE_SENSITIVE_DATA` | `false` — `true` records prompts/completions in spans | Lab 4 |
| `TELEMETRY_CONSOLE` | `false` — `true` also prints spans to the console | Lab 4 |
| `AGENT_VERSIONS_DIR` | `workshop/agent_versions` | Lab 6 |

## Commands

| Command | What it does |
|---|---|
| `uv sync` | install pinned deps (uv installs Python 3.12 automatically via `.python-version`) |
| `uv run poe smoke` | Lab 0 connectivity check against /openai, /care-tools/mcp, /a2a/care-knowledge, /telemetry, /foundry |
| `uv run poe chat` | interactive CLI chat with the Care Coordination Agent |
| `uv run poe devui` | launch Agent Framework DevUI (if installed: `uv sync --extra devui`) |
| `uv run poe mcp-tools` | list MCP tools from the managed endpoint |
| `uv run poe lab2` | run the scripted multi-step task "Plan discharge for patient P-1042 and book a cardiology follow-up within 7 days." |
| `uv run poe a2a-card` | fetch and pretty-print the base agent's Agent Card through APIM |
| `uv run poe lab3` | ask a prior-auth policy question that is delegated over A2A; prints citations |
| `uv run poe traces` | print the KQL / portal links to find your traces (filter by PARTICIPANT_ID) |
| `uv run poe evals` | run local evaluations with weighted rubric → `evals/out/<run-id>/` (`--ids`, `--limit`, `--judge-delay`, `--no-judge`, `--rescore`, `--candidate vN`) |
| `uv run poe redteam` | generate adversarial prompts from the escalation & safety policy and evaluate them (`--offline`, `--foundry` preview) |
| `uv run poe upload-evals` | upload the latest local run to the Foundry project via APIM /foundry |
| `uv run poe cloud-eval` | start a cloud evaluation in Foundry via APIM /foundry (preview; fallback = upload) |
| `uv run poe loop` | Lab 6 pipeline: pull low-scoring traces/results → cluster & rank failure modes → propose change → re-run evals → promote if better (`--quick`, `--limit N`, `--judge-delay`, `--offline`, `--no-promote`) |
| `uv run poe loop --limit 3` | use the first three golden cases throughout the loop, per version; overrides `--quick` and never auto-promotes |
| `uv run poe loop --limit 3 --offline` | same three-case rehearsal with deterministic scoring and a template proposal; agent calls still use the gateway |
| `uv run poe promote` | promote candidate agent version with lineage (version, eval run ID, trace IDs) into `agent_versions/registry.json` |
| `uv run poe promote-force --version v3` | **demo only:** activate an explicit existing version without requiring validation; alias for `uv run poe promote --version v3 --force`; does not run evaluations |
| `uv run poe rollback` | roll back to previous agent version |
| `uv run poe catchup <N>` | copy `solutions/labN/` into `src/care_agent/` |
| `uv run poe docs` | optionally serve the prebuilt static guide at http://127.0.0.1:8000; no server is needed when opening `guide/index.html` directly |
| `uv run poe docs-build` | rebuild the self-contained `guide/index.html` from `docs/` and `scripts/guide/` |
| `uv run poe test` | run `tests/` (offline unit tests; no Azure needed) |

## Where things live

| Path | Contents |
|---|---|
| `src/care_agent/` | `config.py` (settings), `apim_auth.py` (Foundry credential trick), `instructions.py`, `agent.py`, `tools_mcp.py`, `a2a_delegate.py`, `telemetry.py`, `cli.py`, `devui.py`, `smoke.py`, `lab2.py`, `lab3.py`, `versions.py` |
| `solutions/labN/` | end-of-lab checkpoints (generated from `scripts/checkpoints/source/` by `scripts/build_checkpoints.py`) |
| `evals/` | `golden.jsonl`, `rubric.yaml`, `run_evals.py`, `evaluators/no_clinical_diagnosis.py`, `cost.py`, `latency.py`, `redteam_from_policy.py`, `upload_to_foundry.py`, `cloud_eval.py`, `policy/` |
| `loop/` | `pull_failures.py`, `cluster.py`, `propose.py`, `validate.py`, `promote.py`, `rollback.py`, `run_loop.py` |
| `agent_versions/` | `registry.json` (created on first use), `candidates/vN/{instructions.md, change.diff, proposal.json}` |
| `deploy/` | presenter-only hosted-agent / Container Apps demo |

## Pinned versions

| Package | Version | Notes |
|---|---|---|
| agent-framework-core | 1.19.0 | GA |
| mcp | 1.30.0 | required for Lab 2 `MCPStreamableHTTPTool`; installed by default |
| agent-framework-openai | 1.14.4 | `OpenAIChatClient` / `OpenAIChatCompletionClient` |
| agent-framework-a2a | 1.0.0b260918 | pre-release (exact pin) |
| agent-framework-devui | 1.0.0b260918 | optional extra `devui`, pre-release |
| azure-ai-projects | 2.7.0 | use 2.6.1 if you add `agent-framework-foundry` (requires `<2.7.0`) |
| azure-ai-evaluation | 1.18.6 | optional extra `redteam` adds PyRIT |
| azure-monitor-opentelemetry-exporter | 1.0.0b57 | exporters used directly (custom headers policy) |
| azure-monitor-opentelemetry | 1.8.10 | optional extra `distro` |
| opentelemetry-sdk | ~=1.44.0 | |
| pytest / poethepoet / mkdocs-material | 9.1.1 / 0.48.0 / 9.7.7 | dev & docs groups |

## Synthetic patients

| ID | Name | Condition | Payer | Follow-up rule |
|---|---|---|---|---|
| P-1042 | Jordan Ellis, 68 | heart failure (HFrEF), Cardiology 4B | Northwind Health Plan | cardiology ≤ 7 days after discharge |
| P-2077 | Sam Okafor, 72 | COPD exacerbation, Respiratory 2A | Contoso Care Insurance | pulmonology ≤ 14 days + pulmonary rehab referral |
| P-3150 | Riley Chen, 55 | type 2 diabetes, hyperglycaemia episode | Fabrikam Mutual Assurance | endocrinology ≤ 14 days |
| P-4203 | Alex Moreno, 81 | hip fracture post-surgery | Northwind Health Plan | physiotherapy referral + primary care ≤ 7 days |
| P-5318 | Taylor Brooks, 47 | heart failure, new diagnosis | Fabrikam Mutual Assurance | — |

All data is fictional; interaction and prior-auth results come from a synthetic rule set: *"Synthetic rule set for training. Not clinical guidance."*
