# Fallback recordings

Fill this folder during the day-before dry run (see `../preflight-checklist.md`). Use the presenter env only — outputs must contain **synthetic data only** and **no keys** (check before saving: search each file for your key and for `Ocp-Apim-Subscription-Key` values).

| File | Captured from (run in `workshop/`) | Used in |
|---|---|---|
| `lab0-smoke.txt` | `uv run poe smoke` | Lab 0 |
| `lab1-chat.txt` | `uv run poe chat` session incl. a declined clinical-advice question | Lab 1 |
| `lab2-output.txt` | `uv run poe mcp-tools` + `uv run poe lab2` | Lab 2 |
| `lab3-output.txt` | `uv run poe a2a-card` + `uv run poe lab3` (with citations) | Lab 3 |
| `lab4-trace.png` | App Insights end-to-end transaction / Foundry Tracing span tree | Lab 4 |
| `lab5-evals.txt` | `uv run poe evals` summary + path of `evals/out/<run-id>/` | Lab 5 |
| `lab5-redteam.txt` | `uv run poe redteam` | Lab 5 |
| `lab5-foundry-eval.png` | Uploaded run in Foundry portal (`uv run poe upload-evals`) | Lab 5 |
| `lab6-loop.txt` | `uv run poe loop` | Lab 6 |
| `lab6-registry.json` | `agent_versions/registry.json` after `uv run poe promote` | Lab 6 |
| `lab6-rollback.txt` | `uv run poe rollback` | Lab 6 |
| `prod-*.png` | Optional production runtime: agent in portal, APIM request log, trace | Lab 6 Part B |

Do not commit recordings that contain keys or environment-specific hostnames you do not want public; keep them on the presenter machine.
