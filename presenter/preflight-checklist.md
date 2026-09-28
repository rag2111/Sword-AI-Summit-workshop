# Preflight Checklist

Infra commands run from `infra/` (admin). Participant commands run from `workshop/`. Use a **test participant** env (e.g. the first one in `out/participants/`) plus your own presenter subscription.

## One week before

- [ ] **Region availability** (single region for everything if possible): chat `gpt-6-luna`, judge `gpt-6-sol`, embeddings `text-embedding-3-large`; AI Search with agentic retrieval (Foundry IQ); Foundry Agent Service incoming A2A (preview); Foundry hosted agents (preview, only for the optional deploy demo); APIM tier that supports MCP and A2A APIs (Developer, Basic, Basic v2, Standard, Standard v2, Premium, Premium v2 — **not** Consumption).
- [ ] **Quota requested** for the TPM computed below (Foundry portal → Quotas). Requests can take days.
- [ ] Participant count confirmed; add ~10 % spare keys (e.g. 30 + 3 spare + presenter).
- [ ] Codespaces allowed for the audience's org / GitHub accounts (fallback for locked-down laptops).
- [ ] Feedback link / QR ready for slide 15.

### Quota sizing formula

```
Peak chat TPM  ≈ P × a × r × t
Peak judge TPM ≈ P × a_e × (N × E × t_j) / w
Per-subscription llm-token-limit (TPM) ≈ 0.8 × deployment TPM / (P × a)
```

| Symbol | Meaning | Example |
|---|---|---|
| P | participants + presenter + spares | 34 |
| a | fraction active at the same minute during labs | 0.6 |
| r | agent turns per minute per active participant | 2 |
| t | tokens per agent turn incl. tool loops, tool schemas, retrieved text | 8,000 |
| a_e | fraction running evals at the same time in Lab 5 | 0.8 |
| N | eval cases per run (dataset size) | 12 |
| E | judge calls per case (rubric evaluators) | 3 |
| t_j | tokens per judge call | 2,500 |
| w | minutes over which a run spreads | 5 |

Worked example (illustrative): chat ≈ 34 × 0.6 × 2 × 8k ≈ **326k TPM** in labs 2–4; in Lab 5 the agent-under-test also runs N cases: 34 × 0.8 × (12 × 8k) / 5 ≈ **522k TPM** chat; judge ≈ 34 × 0.8 × (12 × 3 × 2.5k) / 5 ≈ **490k TPM** on `gpt-6-sol`. Request quota ≥ the Lab 5 peak with 20 % headroom, or stagger rows (see `run-of-show.md`). **Replace `t`, `N`, `E` with numbers measured in your dry run** (token metrics by "User ID" in App Insights).

## The day before

### Deploy & verify platform

- [ ] `terraform init && terraform apply` from `infra/` — start early: **APIM classic tiers can take 30–60 min** to provision (v2 tiers are faster).
- [ ] Model deployments exist with expected names (`gpt-6-luna`, `gpt-6-sol`, `text-embedding-3-large`) and TPM as sized above.
- [ ] `token_limit_tpm` in `infra/terraform.tfvars` (per-subscription TPM, default 20000) matches the formula, so `llm-token-limit` on `/openai` is right; quick-fix path noted (FAQ §2).
- [ ] **Application Insights → Usage and estimated costs → Custom metrics → "With dimensions"** enabled — otherwise the workbook token panels are empty (User ID / Model dimensions dropped). Applies to new data only, so do it before the dry run.
- [ ] Know the fallback switches in `infra/terraform.tfvars` and their current values: `a2a_mode`, `a2a_apim_api_kind`, `care_tools_rest_in_product`, `telemetry_require_subscription_key`, `knowledge_mode` (FAQ §10). If a primary path fails in the dry run, flip it now, not in the room.
- [ ] `uv run scripts/smoke_test.py --env out/participants/<name>.env` from `infra/` passes for 2–3 random participants and for your presenter env.
- [ ] Copy one participant `.env` to `workshop/.env`, then from `workshop/`: `uv sync` and `uv run poe smoke` → all five routes green.
- [ ] **A2A card via APIM:** `uv run poe a2a-card` prints the `care-knowledge-agent` card; the URL in the card points to APIM, not to Foundry.
- [ ] **Foundry IQ citations:** `uv run poe lab3` returns a prior-auth answer with ≥1 citation from `care-kb`.
- [ ] **MCP tools:** `uv run poe mcp-tools` lists 7 tools; `uv run poe lab2` books a cardiology slot within 7 days for P-1042.
- [ ] **Traces:** after `uv run poe lab2`, wait 2–5 min; `uv run poe traces` → trace visible in App Insights filtered by `service.name` = PARTICIPANT_ID, with model, tool and A2A spans; the same trace visible in **Foundry portal → Tracing** (requires App Insights connected to the project).
- [ ] **Evals:** `uv run poe evals` writes `evals/out/<run-id>/`; `uv run poe evals --rescore` re-scores it after a weight change (no model calls); `uv run poe upload-evals` shows the run in the Foundry project (via APIM `/foundry`); `uv run poe redteam` completes with findings mapped to SAFE-001 rules (SAFE-NEVER-01..12); `uv run poe redteam --offline` works as a spare; optionally `uv run poe cloud-eval` (preview).
- [ ] **Loop fallbacks:** `uv run poe loop --quick` and `uv run poe loop --offline` both run on the presenter env (then restore `agent_versions/`).
- [ ] Token-usage metric shows the "User ID" dimension per subscription.
- [ ] Load test lightly: 5 terminals run `uv run poe evals` at once — no persistent 429s.

### Key distribution (never post keys in chat)

- [ ] `participants.csv` and `out/participants/*.env` stay on the admin machine (git-ignored). Do not email the CSV.
- [ ] One `.env` per participant. Choose a channel: **printed cards** (name, `APIM_BASE_URL`, `PARTICIPANT_ID`, key) handed out face-down, **QR code** per card that encodes the `.env` content, or a **secure share** (per-person link with expiry, access restricted to that person).
- [ ] Spare cards in a separate envelope; record who gets which spare.
- [ ] Plan to regenerate/revoke keys (or `terraform destroy`) right after the session.

### Demo & fallbacks

- [ ] Dry-run `live-demo-lab6.md` Part A twice on the presenter env (seed failures first, see that file).
- [ ] Optional: admin `az login`, then from `workshop/` `uv run python deploy/deploy_hosted_agent.py --project-endpoint https://<foundry>.services.ai.azure.com/api/projects/<project> --acr <registry-name> --tag 1` (`live-demo-lab6.md` Part B); confirm its traffic appears in APIM logs and traces.
- [ ] Record fallback outputs into `presenter/fallback/` (list in `fallback/README.md`): terminal output per lab + screenshots of trace tree, eval run in Foundry, registry lineage.
- [ ] Copy `workshop/agent_versions/` (registry + `candidates/`) in its seeded pre-demo state so you can restore it.
- [ ] Walk the whole run of show once with a timer.

## The hour before

- [ ] `uv run scripts/smoke_test.py --env out/participants/<name>.env` (from `infra/`) for your env + 2 random participants.
- [ ] `uv run poe smoke` from `workshop/` on the presenter machine.
- [ ] Generate fresh traffic (`uv run poe lab2`, `uv run poe lab3`) so a recent trace exists for the Lab 4 screen share.
- [ ] Browser tabs open & signed in: App Insights (transaction search + token workbook/dashboard), Foundry portal (Tracing, Evaluations, Agents), APIM (APIs → `/openai` policy, for token-limit edits).
- [ ] Token limit sanity: current `token_limit_tpm` and deployment TPM noted on your timing card; workbook token panels show data per User ID.
- [ ] Wi-Fi: venue network tested from a participant-like laptop to `APIM_BASE_URL` (no proxy/TLS interception on `*.azure-api.net`); phone hotspot charged.
- [ ] Codespaces: open and warm one Codespace (dependencies installed via `uv sync`) to verify startup time; share the "open in Codespaces" link on slide 2.
- [ ] Catch-up commands visible on a slide / sticky: `uv run poe catchup 1` … `uv run poe catchup 5`.
- [ ] Timer ready (visible countdown), `timing-cards.md` printed, stickies (green/red) on every seat.
- [ ] Key cards sorted; spare envelope ready.
- [ ] Terminal font size ≥ 18 pt; notifications off; screen share tested.

## After the session

- [ ] Revoke/regenerate participant keys or `terraform destroy` from `infra/`.
- [ ] Revert any temporary portal policy changes and fallback switches in `terraform.tfvars`, then re-run `terraform apply` (or go straight to `terraform destroy`).
- [ ] Delete printed cards / QR shares.
