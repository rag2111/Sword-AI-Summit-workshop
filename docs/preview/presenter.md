# Preview features — presenter kit

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
