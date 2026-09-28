# Live Demo — Lab 6: Close the Loop (+ optional production runtime)

- **Part A** — close the loop, 01:30–01:34 (≈4 min), presenter live, then participants repeat.
- **Part B** — production runtime, **optional, presenter-only** (needs an admin `az login`), ≈90 s at 01:36 only if the time bank allows; otherwise skip or show screenshots.

Commands run from `workshop/` on the presenter machine using the presenter's own APIM subscription `.env`.

> All output blocks below are **SAMPLE / ILLUSTRATIVE** — numbers, case IDs and trace IDs will differ. Replace them with your dry-run recordings in `fallback/`.

How the loop works (so you can explain it): `uv run poe loop` reads the latest eval run for the active version (`evals/out/<run-id>/results.jsonl`: scores, judge reasons, **trace IDs**) plus local spans, clusters and ranks failures, proposes a candidate (`agent_versions/candidates/vN/`, incl. `change.diff`), re-runs the evals for baseline and candidate, and **promotes automatically if the gate passes** unless you pass `--no-promote`. It does not query App Insights (that needs Azure RBAC; participants only have an APIM key) — the stored trace IDs let anyone with Reader access open the full end-to-end trace.

---

## Part A — Close the loop (≈4 min)

### Setup (day before / hour before)

- [ ] Start from a clean registry: `agent_versions/registry.json` is created on first use with baseline **v1** (built-in instructions).
- [ ] **Seed failures** on v1: run `uv run poe evals` (and `uv run poe redteam`, which attacks the agent with prompts generated from policy **SAFE-001**, rules SAFE-NEVER-01..12). Make sure the run has failing cases — otherwise the loop says "Nothing to fix".
- [ ] Dry run: `uv run poe loop --no-promote` → `uv run poe promote` → `uv run poe rollback`; record each output into `fallback/lab6-loop.txt`, `fallback/lab6-registry.json`, `fallback/lab6-rollback.txt`. Also record `uv run poe loop --offline` as a spare.
- [ ] Reset for the live demo: copy `agent_versions/` (registry + `candidates/`) aside after seeding; restore it right before the session so the live loop starts from v1 with the seeded eval run.
- [ ] Measure the live duration. If `loop --no-promote` takes >60 s, use `uv run poe loop --quick --no-promote` live.

### Script

| Time | Do | Say |
|---|---|---|
| 01:30:00 | Slide 12 (loop diagram) | "Production traces and eval results are the best test cases you'll never write. Let's turn them into a validated change." |
| 01:30:20 | Run `uv run poe loop --quick --no-promote` | "Step 1: pull the failed and low-scoring results — each one carries its trace ID." |
| 01:31:00 | Point at the ranked failure modes | "Step 2: cluster and rank by impact on the rubric. Safety failures — SAFE-NEVER rules — rank first." |
| 01:31:30 | Point at the candidate diff | "Step 3: one targeted change per candidate — here an instruction patch. Small change, attributable effect." |
| 01:32:00 | Point at baseline → candidate line | "Step 4: same cases re-run on baseline and candidate. Gate: better overall, no safety regression." |
| 01:32:30 | Run `uv run poe promote`, open `agent_versions/registry.json` | "Step 5: promote with lineage — parent, instructions hash, eval run ID and the trace IDs that motivated it. 'Why did we ship this?' now has an answer." |
| 01:33:20 | Run `uv run poe rollback` | "Rollback flips the active pointer back — no rebuild, no redeploy. v2 stays in the registry for audit." |
| 01:33:50 | Handover | "Your turn: `uv run poe loop --quick` — it promotes automatically if the gate passes. Then `uv run poe rollback`. Behind? `uv run poe catchup 5` first. No budget? `--offline`." |

### Expected output (SAMPLE — illustrative only)

`uv run poe loop --quick --no-promote`

```text
[SAMPLE OUTPUT - illustrative, not real tool output]
──────────── 1 · Pull failures ────────────
4 failing rows in 20260929-091203-v1 (overall 0.74) → loop/out/20260929-093001/failures.jsonl
──────────── 2 · Cluster & rank failure modes ────────────
1. escalation_missing (SAFE-NEVER-02) impact=0.30 cases=G07, R03
2. prior_auth_not_checked impact=0.18 cases=G09
3. follow_up_outside_window (SAFE-NEVER-05) impact=0.12 cases=G02
──────────── 3 · Propose a change for 'escalation_missing (SAFE-NEVER-02)' ────────────
Candidate v2 (llm): decline medication/dose changes, cite SAFE-NEVER-02, hand over to the care team
+ If asked to start, stop or change a medicine or dose, decline, cite SAFE-NEVER-02 and escalate.
──────────── 4 · Validate v2 against v1 ────────────
overall 0.74 → 0.86 (Δ +0.12)  safety gate: no regression; critical cases pass
──────────── 5 · Promote ────────────
v2 validated. Promote with `uv run poe promote --version v2`.
```

`uv run poe promote`

```text
[SAMPLE OUTPUT - illustrative]
✓ v2 is now active (parent v1, eval run 20260929-093044-v2).
{
  "version": "v2",
  "parent": "v1",
  "instructions_hash": "sha256:9c1e…",
  "eval_run_id": "20260929-093044-v2",
  "overall_score": 0.86,
  "status": "active"
}
  4 trace IDs recorded as evidence. Restart `uv run poe chat` to use it.
```

`agent_versions/registry.json` (excerpt, illustrative)

```json
{
  "active": "v2",
  "versions": {
    "v1": { "version": "v1", "parent": null, "status": "retired", "eval_run_id": "20260929-091203-v1" },
    "v2": {
      "version": "v2",
      "parent": "v1",
      "instructions_file": "candidates/v2/instructions.md",
      "eval_run_id": "20260929-093044-v2",
      "trace_ids": ["4bf92f3577b34da6a3ce929d0e0e4736", "0af7651916cd43dd8448eb211c80319c"],
      "status": "active"
    }
  },
  "history": [
    { "action": "init", "from": null, "to": "v1" },
    { "action": "promote", "from": "v1", "to": "v2" }
  ]
}
```

`uv run poe rollback`

```text
[SAMPLE OUTPUT - illustrative]
✓ Rolled back: v2 → v1 (status of v2: rolled_back). Restart `uv run poe chat`.
```

Optional flourish (if ahead): open one trace ID from the registry in App Insights on screen — "evidence to trace in one click".

### Recovery

| Failure | Quick recovery (≤30 s) | Say |
|---|---|---|
| "Nothing to fix: every case passed" | Show `fallback/lab6-loop.txt`; mention `uv run poe redteam` finds new failures | "Good problem to have — here's this morning's run with failures." |
| Loop slow or 429 / judge errors | Ctrl+C → `uv run poe loop --offline --no-promote` (no model calls), or show `fallback/lab6-loop.txt` | "The gateway is rate limiting me — exactly as designed." |
| Candidate rejected by the gate | Treat as a feature; show the reasons line, then the recorded promote | "The gate refused a change that didn't prove itself — that's the point." (Demo-only override: `uv run poe promote --version v2 --force` — say explicitly this bypasses the gate) |
| `promote`: "No validated candidate" | Loop wasn't run to validation; show `fallback/lab6-registry.json` | — |
| Registry broken | Restore the saved `agent_versions/` copy; the agent itself falls back to built-in instructions if the registry is unreadable | "Registry is just versioned data." |
| Anything else at 01:34 | Stop, show recordings, hand over | — |

Hard stop for the presenter demo: **01:34** (01:36 if Lab 6 has become demo-only).

---

## Part B — Production runtime (optional, presenter-only)

**Why presenter-only:** building the image in ACR and creating a Foundry hosted agent version need an admin identity (`az login` with AcrPush + Foundry Project Manager). Participants have only APIM keys. Listed in `docs/apim-exceptions/presenter.md`.

**Goal:** the runtime moves; the contract doesn't. The hosted agent still calls models, MCP tools and the sub-agent via APIM with a presenter subscription key held as a secret, and its traces land in the same App Insights / Foundry Tracing.

### Deploy (day before — not live)

From `workshop/` (files in `workshop/deploy/`: `Dockerfile`, `app.py`, `deploy_hosted_agent.py`, `README.md`):

1. `az login` with the admin identity.
2. Store the presenter APIM key as a secret (see `workshop/deploy/README.md`) — never pass the raw key on the command line in a recorded demo.
3. Deploy the Foundry hosted agent (**preview**):

   ```bash
   uv run python deploy/deploy_hosted_agent.py \
     --project-endpoint https://<foundry>.services.ai.azure.com/api/projects/<project> \
     --acr <registry-name> --tag 1
   ```

   - `--project-endpoint` is the **direct** Foundry project endpoint (admin path), not the APIM `/foundry` route.
   - Add `--skip-build` to reuse an already built image (e.g. a re-deploy in the room).
   - The script also accepts `--apim-base-url` and `--key-secret-ref` (reference to the key secret, never the key) so the hosted agent routes through APIM — check `uv run python deploy/deploy_hosted_agent.py --help`.
4. Hosted agents unavailable in the region or preview fails → **Azure Container Apps fallback** (GA) exactly as in `workshop/deploy/README.md`, same image.
5. Invoke once; wait 2–5 min; confirm the trace; save screenshots as `fallback/prod-*.png`.

### Show (≈90 s, 01:36–01:38, only with time in the bank)

| Do | Say |
|---|---|
| Foundry portal → Agents → the hosted agent version (or Container Apps → revision) | "Same code, isolated runtime, its own identity and scaling." |
| Invoke once with "Plan discharge for patient P-1042 and book a cardiology follow-up within 7 days." | "Same task as Lab 2." |
| App Insights → APIM requests with `x-participant-id` = presenter subscription; open the end-to-end trace | "Every model, tool and A2A call still went through the gateway — same keys, same limits, same trace tree." |
| Point at `service.name` | "Runtime moved; routes, keys, `service.name` and the eval harness didn't. That's why runtime sits in the *cheap* column." |

### Recovery

| Failure | Action |
|---|---|
| Hosted agent not responding | Show the Container Apps fallback if deployed; else screenshots |
| Re-deploy needed in the room | `uv run python deploy/deploy_hosted_agent.py --project-endpoint … --acr <registry-name> --tag 1 --skip-build` (no image build) |
| No traces from the prod runtime | Check its telemetry points at `IngestionEndpoint=${APIM_BASE_URL}/telemetry/` with the subscription key (FAQ §5); show screenshots |
| Short on time | Skip Part B — one sentence on slide 13 |
