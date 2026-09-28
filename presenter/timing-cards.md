# Timing Cards (print, cut along the lines)

Total: 1h45m (105 minutes). Hard stop = move on no matter what. Behind → `uv run poe catchup <N>`.

<!-- timing-table:start -->
| Clock | Segment | Minutes | Cue | Hard stop |
|---|---|---|---|---|
| 00:00–00:04 | Opening, disclaimer, architecture (concept) | 4 | Read disclaimer aloud; slides 1–4; "key card in hand?" | 00:04 |
| 00:04–00:09 | Lab 0 — Setup & smoke test | 5 | `uv sync` → `uv run poe smoke`; green check 00:08 | 00:09 |
| 00:09–00:11 | Concept: agent anatomy & safety boundaries | 2 | Slide 6: boundaries are the product | 00:11 |
| 00:11–00:26 | Lab 1 — Build the local Care Coordination Agent | 15 | `uv run poe chat`; decide catch-up 00:23; check 00:24 | 00:26 |
| 00:26–00:28 | Concept: tools behind one managed MCP endpoint | 2 | Slide 7: one endpoint, 7 tools, contracts | 00:28 |
| 00:28–00:38 | Lab 2 — Tools via managed MCP endpoint | 10 | `catchup 1` → `mcp-tools` → `lab2`; check 00:36 | 00:38 |
| 00:38–00:40 | Concept: A2A and agent contracts | 2 | Slide 8: card = contract, MI to Foundry | 00:40 |
| 00:40–00:55 | Lab 3 — Multi-agent via A2A | 15 | `catchup 2` → `a2a-card` → `lab3`; decide 00:52; check 00:53 | 00:55 |
| 00:55–00:57 | Concept: trace anatomy | 2 | Slide 9: one request = one trace | 00:57 |
| 00:57–01:07 | Lab 4 — Observability | 10 | `catchup 3`; traffic first; `traces`; screen share 01:00; check 01:04 | 01:07 |
| 01:07–01:10 | Concept: defining "good" (weighted rubrics) | 3 | Slides 10–11: safety is a gate | 01:10 |
| 01:10–01:30 | Lab 5 — Evaluations | 20 | `catchup 4` → `evals` → weights + `evals --rescore` → `redteam` (SAFE-001) → `upload-evals`; stagger rows; decide 01:25; check 01:27 | 01:30 |
| 01:30–01:40 | Lab 6 — Close the loop (≈4 min presenter demo) | 10 | Demo `loop --quick --no-promote`/`promote`/`rollback` until 01:34; then participants (`catchup 5`, `loop --quick`; no budget → `--offline`); check 01:38 | 01:40 |
| 01:40–01:45 | Wrap-up: "Cheap to change vs. follows you for two years" | 5 | Slide 14 table; keys expire; feedback QR | 01:45 |
<!-- timing-table:end -->

---

**Emergency card:** <70 % green at a checkpoint → announce catch-up, move at hard stop. Platform down → recorded mode (`fallback/`), same clock. Never cut: disclaimer, smoke test, safety concept, one eval run, the two-year table.

**Admin card (`infra/terraform.tfvars` → `terraform apply`):** APIM 429 → `token_limit_tpm` (quick: portal `llm-token-limit` on `/openai`) · A2A down → `a2a_mode = "adapter"` · A2A API type rejected → `a2a_apim_api_kind = "http"` · MCP tool 401 → `care_tools_rest_in_product = true` · telemetry down → `telemetry_require_subscription_key = false` · KB down → `knowledge_mode = "index"`.
