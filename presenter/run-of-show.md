# Run of Show — 105 minutes

Clock = minutes since session start (00:00). Times are binding (`docs/CONTRACT.md` §7). Concept talk ≈25 min in total: 20 min in concept segments + ≈4 min Lab 6 presenter demo + ≈1 min of short lab briefings.

Checkpoint convention: **green sticky / thumbs-up reaction = done**, **red sticky = stuck** (helper goes to red first). For remote attendees use chat reactions — never ask anyone to paste keys or `.env` content in chat.

## Master timeline

<!-- timing-table:start -->
| Clock | Segment | Minutes | Who | Hard stop |
|---|---|---|---|---|
| 00:00–00:04 | Opening, disclaimer, architecture (concept) | 4 | Presenter | 00:04 |
| 00:04–00:09 | Lab 0 — Setup & smoke test | 5 | Participants | 00:09 |
| 00:09–00:11 | Concept: agent anatomy & safety boundaries | 2 | Presenter | 00:11 |
| 00:11–00:26 | Lab 1 — Build the local Care Coordination Agent | 15 | Participants | 00:26 |
| 00:26–00:28 | Concept: tools behind one managed MCP endpoint | 2 | Presenter | 00:28 |
| 00:28–00:38 | Lab 2 — Tools via managed MCP endpoint | 10 | Participants | 00:38 |
| 00:38–00:40 | Concept: A2A and agent contracts | 2 | Presenter | 00:40 |
| 00:40–00:55 | Lab 3 — Multi-agent via A2A | 15 | Participants | 00:55 |
| 00:55–00:57 | Concept: trace anatomy | 2 | Presenter | 00:57 |
| 00:57–01:07 | Lab 4 — Observability | 10 | Participants | 01:07 |
| 01:07–01:10 | Concept: defining "good" (weighted rubrics) | 3 | Presenter | 01:10 |
| 01:10–01:30 | Lab 5 — Evaluations | 20 | Participants | 01:30 |
| 01:30–01:40 | Lab 6 — Close the loop (≈4 min presenter demo) | 10 | Presenter, then participants | 01:40 |
| 01:40–01:45 | Wrap-up: "Cheap to change vs. follows you for two years" | 5 | Presenter | 01:45 |
<!-- timing-table:end -->

Catch-up rule (announce once in Lab 0 and repeat at every lab start): *"If you're behind, run `uv run poe catchup <N>` from `workshop/` — it copies `solutions/labN/` over `src/care_agent/`. It overwrites your edits, so copy anything you want to keep first."* At the start of Lab N+1 anyone not green on Lab N runs `uv run poe catchup <N>`.

---

## 00:00–00:04 · Opening, disclaimer, architecture (4 min) · Presenter

**Say**
- "Standing up an agent prototype takes an afternoon. Everything after that is the actual job." Today: build it, then *prove* it works.
- Read the disclaimer aloud: training use only, synthetic data, **not a medical device**, no clinical advice.
- Architecture in one breath: one agent you build (Agent Framework) → **one front door (APIM)** for models, tools (MCP), a second agent (A2A), Foundry data plane, telemetry → Foundry + Foundry IQ behind it.
- You leave with: a running agent, an evaluation harness, and a map of which decisions are cheap vs. follow you for two years.

**Show** Slides 1–4 (title, disclaimer, prototype vs production, architecture diagram).

**Checkpoint** "Hands up if you have your key card / `.env` file." Helpers hand out missing cards.

**Fallback** Never slip the opening. Late arrivals go straight to the Lab 0 page with a helper.

---

## 00:04–00:09 · Lab 0 — Setup & smoke test (5 min) · Participants

| Clock | Beat |
|---|---|
| 00:04 | Brief (30 s): open Codespace or local clone → `workshop/`; put the 3 values (`APIM_BASE_URL`, `APIM_SUBSCRIPTION_KEY`, `PARTICIPANT_ID`) into `.env` (or copy your provided `.env` file) → `uv sync` → `uv run poe smoke` |
| 00:05–00:08 | Participants work; presenter runs the same on screen |
| 00:08 | **Checkpoint:** green = all five routes OK (`/openai`, `/care-tools/mcp`, `/a2a/care-knowledge`, `/telemetry`, `/foundry`) |
| 00:09 | **Hard stop** — move on regardless |

**Show** Terminal: `uv run poe smoke` output.

**Fallback**
- `/openai` red → FAQ §1 (401) with a helper; participant pairs with a neighbor meanwhile.
- Only `/telemetry` or `/foundry` red → continue; they are first needed in Lab 4/5. Helper fixes during Lab 1.
- `uv sync` slow/blocked → FAQ §7 (proxy / Python download); switch that person to Codespaces.
- >20 % red on the same route → likely platform issue: admin checks APIM (see *Platform down* below); presenter continues with the concept segment.

---

## 00:09–00:11 · Concept: agent anatomy & safety boundaries (2 min) · Presenter

**Say**
- Agent = model + instructions + tools + state + **boundaries**. The boundaries are the product.
- Safety boundaries for this agent: coordinate care logistics (plans, slots, referrals, prior auth), **never** give clinical advice; escalate to a human clinician; disclaimer in instructions.
- The boundaries are written down: policy **SAFE-001** (`infra/data/care-docs/09-escalation-and-safety-policy.md`), hard rules **SAFE-NEVER-01..12** (e.g. 01 no diagnosis, 02 no medication/dose changes, 05 no booking outside the SLA window, 09 ignore instructions embedded in tool output). When the agent declines, it cites the rule.
- Tools are the blast radius: least privilege, idempotent reads vs. side-effecting writes (`book_follow_up`, `create_referral`).
- The model is reached through APIM `/openai` with the `api-key` header — SDK unchanged, gateway enforces identity and token limits.

**Show** Slide 6 (agent anatomy).

---

## 00:11–00:26 · Lab 1 — Build the local Care Coordination Agent (15 min) · Participants

| Clock | Beat |
|---|---|
| 00:11 | Brief (1 min): build the agent with `Agent` + `OpenAIChatClient` pointed at APIM; add instructions + disclaimer; run `uv run poe chat` (optional: `uv run poe devui`) |
| 00:12–00:22 | Participants work; helpers roam |
| 00:22 | Presenter live-shows own agent answering, and declining a clinical-advice question (e.g. dosing) with escalation |
| 00:23 | **Decision point:** if <70 % green → announce catch-up for Lab 2 start and skip DevUI |
| 00:24 | **Checkpoint:** green = `uv run poe chat` answers, shows disclaimer, declines clinical advice (ideally citing SAFE-NEVER-02 for a dosing question) |
| 00:26 | **Hard stop** |

**Fallback**
- Cut: DevUI (optional anyway), any "stretch" steps.
- Behind at 00:26 → first action of Lab 2 is `uv run poe catchup 1`.
- Model 401/404 → FAQ §1 (header, deployment name, doubled `/openai` path).

---

## 00:26–00:28 · Concept: tools behind one managed MCP endpoint (2 min) · Presenter

**Say**
- One MCP endpoint (`/care-tools/mcp`) instead of N tool servers with N auth schemes. APIM turns an existing REST API into MCP tools; operationIds = tool names.
- Gateway gives you per-caller keys, rate limits, logging, `x-participant-id` to the backend — without touching the backend.
- Seven tools: `search_patient`, `get_care_plan`, `list_available_slots`, `book_follow_up`, `create_referral`, `check_medication_interactions`, `check_prior_auth_requirement`.
- Contracts matter: tool names and schemas are an API your agent (and evals) depend on.

**Show** Slide 7 + request-flow diagram (slide 5 if not yet shown).

---

## 00:28–00:38 · Lab 2 — Tools via managed MCP endpoint (10 min) · Participants

| Clock | Beat |
|---|---|
| 00:28 | Brief (30 s): behind? `uv run poe catchup 1`. Then `uv run poe mcp-tools` → wire `MCPStreamableHTTPTool` → `uv run poe lab2` |
| 00:29–00:35 | Participants work |
| 00:35 | Presenter shows `uv run poe lab2`: "Plan discharge for patient P-1042 and book a cardiology follow-up within 7 days." |
| 00:36 | **Checkpoint:** green = `mcp-tools` lists 7 tools AND `lab2` ends with a booked appointment ID inside the 7-day window |
| 00:38 | **Hard stop** |

**Fallback**
- Short on time: participants run `uv run poe catchup 2` then `uv run poe lab2` — they still see the result.
- `409` slot taken = expected contention between participants; agent should pick another slot (good teaching moment).
- MCP handshake errors → FAQ §3. MCP tool calls return 401 for everyone → admin sets `care_tools_rest_in_product = true` + `terraform apply`. If MCP route is down for everyone → presenter demo from `fallback/lab2-output.txt`.

---

## 00:38–00:40 · Concept: A2A and agent contracts (2 min) · Presenter

**Say**
- Sub-agents are services: discover via an **Agent Card**, call via JSON-RPC. Here: `care-knowledge-agent` (Foundry, grounded on Foundry IQ `care-kb`) answers policy questions with citations.
- Card at `/a2a/care-knowledge/.well-known/agent-card.json` via APIM; APIM rewrites the hostname and uses **managed identity** to Foundry (native card needs Entra).
- The card is a contract: skills, input/output modes, version. Changing it breaks callers you don't know about.

**Show** Slide 8 (A2A sequence).

---

## 00:40–00:55 · Lab 3 — Multi-agent via A2A (15 min) · Participants

| Clock | Beat |
|---|---|
| 00:40 | Brief (1 min): behind? `uv run poe catchup 2`. `uv run poe a2a-card` → add `A2AAgent` as a sub-agent/tool → `uv run poe lab3` |
| 00:41–00:50 | Participants work |
| 00:50 | Presenter shows `uv run poe lab3` prior-auth answer with citations (e.g. Northwind + `CARD-MRI` → prior auth required) |
| 00:52 | **Decision point:** <70 % green → announce `uv run poe catchup 3` at Lab 4 start |
| 00:53 | **Checkpoint:** green = card printed AND `lab3` answer shows at least one citation |
| 00:55 | **Hard stop** |

**Fallback**
- Cut: any custom-question exploration; keep only `uv run poe lab3`.
- Card 404/401 for everyone → admin sets `a2a_mode = "adapter"` (Container Apps adapter `care-knowledge-a2a`) + `terraform apply`; APIM A2A API type rejected at deploy → `a2a_apim_api_kind = "http"`. Meanwhile presenter shows `fallback/lab3-output.txt`.
- No citations → FAQ §4 (KB/knowledge source; `knowledge_mode = "index"` fallback) — continue; Lab 4 does not depend on citations.

---

## 00:55–00:57 · Concept: trace anatomy (2 min) · Presenter

**Say**
- One user request = one trace: `invoke_agent` → `chat` (model) → `execute_tool` (MCP) → `invoke_agent` (A2A hop) — GenAI semantic conventions from Agent Framework's built-in instrumentation.
- W3C `traceparent` flows through APIM untouched; APIM's span is a child of yours → gateway, backend and sub-agent in one tree.
- Your `service.name` = your `PARTICIPANT_ID`; that's how you find *your* traces among 30.
- Telemetry itself goes via APIM `/telemetry` — same key, same front door.

**Show** Slide 9 (trace anatomy).

---

## 00:57–01:07 · Lab 4 — Observability (10 min) · Participants

| Clock | Beat |
|---|---|
| 00:57 | Brief (30 s): behind? `uv run poe catchup 3`. **Generate traffic first** (`uv run poe lab2`, `uv run poe lab3`) — ingestion takes 2–5 min. Then `uv run poe traces` |
| 00:58–01:04 | Participants work; at 01:00 presenter screen-shares App Insights / Foundry Tracing with own trace |
| 01:04 | **Checkpoint:** green = found own trace (filter `service.name` = PARTICIPANT_ID) and can name the model, tool and A2A spans |
| 01:07 | **Hard stop** |

**Fallback**
- Participants cannot sign in to the portal → presenter screen share is the primary view (see `docs/apim-exceptions/presenter.md`).
- No traces after 5 min → FAQ §5; show presenter's trace; do not debug exporters in the room beyond 2 min. `/telemetry` failing for everyone → admin sets `telemetry_require_subscription_key = false` + `terraform apply` (revert after).
- Cut: portal tour details; keep one span tree walkthrough. `uv run poe catchup 4` at Lab 5 start for anyone red.

---

## 01:07–01:10 · Concept: defining "good" (weighted rubrics) (3 min) · Presenter

**Say**
- "Works" is not a vibe. Define it before you measure: **task success, safety, cost, latency** — weighted.
- Safety is a gate, not a weight you can trade off: any safety fail → case fails.
- Adversarial tests come from the **policy** (SAFE-001), not from imagination: each of SAFE-NEVER-01..12 becomes attack prompts, so every red-team finding maps to a rule ID.
- Local harness first (`uv run poe evals`), then upload the run to Foundry via APIM `/foundry` so the team shares one history.

**Show** Slides 10–11 (rubric, adversarial tests).

---

## 01:10–01:30 · Lab 5 — Evaluations (20 min) · Participants

| Clock | Beat |
|---|---|
| 01:10 | Brief (1 min): behind? `uv run poe catchup 4`. `uv run poe evals` → inspect `evals/out/<run-id>/` → change rubric weights and `uv run poe evals --rescore` → `uv run poe redteam` → `uv run poe upload-evals`; optional `uv run poe cloud-eval` |
| 01:11–01:22 | Participants work. **Stagger** if 429s appear: odd rows start `evals` now, even rows at 01:13. Weight exercise uses `--rescore` (re-applies weights to the stored run, **no model calls**) — never re-run the full eval just to change weights |
| 01:22 | Presenter shows own run: weighted score, one failing case, one red-team finding; uploaded run in Foundry (screen share) |
| 01:25 | **Decision point:** behind → skip `cloud-eval` and `redteam`, presenter shows `fallback/lab5-redteam.txt` |
| 01:27 | **Checkpoint:** green = a local run in `evals/out/<run-id>/` with a weighted score (+ uploaded) |
| 01:30 | **Hard stop** |

**Fallback**
- Cut order: `cloud-eval` (preview, optional) → `redteam` (becomes presenter demo) → `upload-evals` (presenter shows theirs).
- Budget savers: `uv run poe evals --limit <n>` or `--ids G01,G09` (subset), `--no-judge` (offline scoring only), `uv run poe redteam --offline` (template prompts + heuristic scoring), `--rescore` for the weight exercise.
- Judge 429 / content-filter / version errors → FAQ §6. Token limit: quick fix = edit `llm-token-limit` on the `/openai` API in the portal; permanent fix = change `token_limit_tpm` in `infra/terraform.tfvars` and `terraform apply` (FAQ §2).
- Never cut: one local `uv run poe evals` run per participant — Lab 6 needs it (or `uv run poe catchup 5`).

---

## 01:30–01:40 · Lab 6 — Close the loop (10 min) · Presenter demo, then participants

| Clock | Beat |
|---|---|
| 01:30–01:34 | **Presenter live demo** (`live-demo-lab6.md` Part A): `uv run poe loop --no-promote` → `uv run poe promote` → show lineage → `uv run poe rollback` |
| 01:34 | Participants: behind? `uv run poe catchup 5`. Run `uv run poe loop` (promotes automatically if the gate passes; `--quick` if short on time/budget), then `uv run poe rollback` / `uv run poe promote` |
| 01:36–01:38 | Optional (only if ≥2 min in the time bank): presenter shows pre-deployed production runtime (`live-demo-lab6.md` Part B, 90 s) |
| 01:38 | **Checkpoint:** green = `agent_versions/registry.json` shows a promoted version with eval run ID + trace IDs |
| 01:40 | **Hard stop** |

**Fallback**
- Running late → Lab 6 becomes presenter-demo only (01:30–01:36), participants run it after the session; recover up to 6 min.
- Slow or rate-limited → `uv run poe loop --quick` (validates on failing + critical cases only).
- No model budget / 429s everywhere → `uv run poe loop --offline` (deterministic metrics + template proposal, no model calls).
- `loop` fails live → switch to `fallback/lab6-loop.txt` (recorded in dry run) and keep talking; see `live-demo-lab6.md` Recovery.
- Skip Part B entirely if anything is late — it is optional.

---

## 01:40–01:45 · Wrap-up: "Cheap to change vs. follows you for two years" (5 min) · Presenter

**Say**
- Walk the table (slide 14): prompts, model deployment, rubric weights are cheap; gateway/identity pattern, tool & agent contracts, trace schema, lineage format follow you for two years.
- Recap what they now own: running agent, eval harness, a loop with lineage and rollback.
- Next steps: open `workshop/guide/index.html` directly for the visual lab guide (or `uv run poe docs` for optional localhost access); `uv run poe test` works offline; keys expire after the session.
- Feedback link / QR.

**Show** Slides 14–15.

**Hard stop 01:45.** Minimum wrap-up if squeezed: 3 min (table + keys-expire notice).

---

## Time bank — where to recover minutes

| Source | Normal | Compressed | Minutes recovered | Decide by |
|---|---|---|---|---|
| Lab 1: skip DevUI + stretch steps | 15 | 13 | 2 | 00:23 |
| Lab 3: presenter show-and-tell only for custom questions | 15 | 13 | 2 | 00:52 |
| Lab 4: one span-tree walkthrough, no portal tour | 10 | 7 | 3 | 01:02 |
| Lab 5: drop `cloud-eval`; `redteam` as presenter demo | 20 | 15 | 5 | 01:25 |
| Lab 6: presenter demo only | 10 | 4–6 | 4–6 | 01:30 |
| Skip Lab 6 Part B (production runtime) | 1.5 | 0 | 1.5 | 01:34 |
| Concept segments: cut to headline + diagram | 2–3 each | 1–2 each | 1 each (max 3) | any |
| Wrap-up: table + keys notice only | 5 | 3 | 2 | 01:40 |

**Do not cut:** disclaimer, Lab 0 smoke test, safety-boundaries concept, one local eval run, the cheap-vs-two-year table.

Rule of thumb: when a lab's checkpoint shows <70 % green, stop waiting — announce catch-up and move on at the hard stop. The next lab's first command is `uv run poe catchup <N>`.

## If the platform is down

| Situation | Signal | Action |
|---|---|---|
| One route down (e.g. `/a2a`, `/foundry`) | Same route red for many in `uv run poe smoke` | Admin flips the matching switch in `infra/terraform.tfvars` and runs `terraform apply` (FAQ §10: `a2a_mode = "adapter"`, `a2a_apim_api_kind = "http"`, `care_tools_rest_in_product = true`, `telemetry_require_subscription_key = false`, `knowledge_mode = "index"`). Presenter demos that lab from `fallback/` while it applies; others continue |
| Everyone hits APIM 429 | Per-subscription limit too low for Lab 5 | Quick: edit `llm-token-limit` on `/openai` in the portal; permanent: `token_limit_tpm` in `terraform.tfvars` + `terraform apply` (FAQ §2) |
| Model quota exhausted (429 from backend, not APIM) | 429s even with low per-user usage | Stagger rows; `--no-judge` / `--limit` / `--rescore` for evals, `uv run poe loop --offline` for Lab 6; raise per-subscription limit only if the backend has headroom; else presenter-demo evals from recording |
| APIM / region fully down | All routes fail, portal shows outage | Switch to **recorded mode**: slides + `fallback/*.txt` + screenshots per lab; participants read code in `solutions/labN/`, run `uv run poe test` (offline) and browse `uv run poe docs` |
| Wi-Fi down | Local participants offline | Phone hotspot for presenter; Codespaces users unaffected if they have any connection; otherwise recorded mode |

Recorded mode keeps the same clock: each lab becomes "presenter walks through recorded output + participants read the solution code" and ends at the same hard stop.
