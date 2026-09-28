<!-- Generated from docs/troubleshooting.md by scripts/export_labs.py — edit the docs/ version. -->

# Troubleshooting

Start with `uv run poe smoke`: it tests all five routes and prints a one-line explanation per failure.

## Gateway responses

| Symptom | Meaning | Fix |
|---|---|---|
| **401** on every route | wrong or missing subscription key | Re-copy `APIM_SUBSCRIPTION_KEY` (no quotes/spaces). Check `.env` is in `workshop/`. |
| **403** | operation not allow-listed (e.g. a Foundry call the labs don't need) | Use the workshop commands unchanged; tell the presenter which command failed. |
| **404** on `/openai` | deployment name mismatch | Remove `CHAT_MODEL` / `JUDGE_MODEL` overrides from `.env`. |
| **404** on the Agent Card | A2A API/endpoint not enabled (Foundry incoming A2A is preview) | Presenter switches the gateway to the fallback adapter; no code change. |
| **429** | your per-participant token or rate limit | Wait for `Retry-After` (the code retries). For evals use `--ids` or `--no-judge`. |
| **5xx** | backend hiccup | Retry once, then tell a helper. |

## Local environment

> [!WARNING]
> **`uv: command not found`**
>
> Open a new terminal after installing uv (PATH update). On Windows, restart VS Code.

> [!WARNING]
> **Corporate proxy / TLS inspection**
>
> Set `HTTPS_PROXY` and let uv and Python use the OS trust store:
> `uv sync --native-tls`, and `export SSL_CERT_FILE=/path/to/corp-ca.pem` (PowerShell: `$env:SSL_CERT_FILE="…"`).
> Or use Codespaces.

> [!WARNING]
> **Wrong Python version**
>
> Run `uv python install 3.12` and `uv sync`. Never `pip install` into the project; `uv run` always uses `.venv/`.

> [!WARNING]
> **`.env` values not picked up**
>
> The file must be `workshop/.env` (not `.env.txt`). Values in your shell environment win over `.env`.

## Labs

> [!WARNING]
> **`Function tools with reasoning_effort are not supported for gpt-6-luna` (400)**
>
> The chat agent sends tools even in Lab 1 (`get_current_date`). For `gpt-6-luna` on Chat Completions,
> set `default_options={"reasoning_effort": "none"}` on `Agent(...)` in `create_agent()`, not on
> `OpenAIChatCompletionClient(...)`. See the model/API guard in [Lab 1, step 3](lab1.md).
> Updated catch-up solutions include this setting. The Responses API does not need this override.

> [!WARNING]
> **`This step needs Lab N …`**
>
> A later lab's TODO is still open. Complete it, or `uv run poe catchup N`. Your code is backed up in
> `.catchup_backups/`.

> [!WARNING]
> **MCP handshake failed**
>
> `uv run poe mcp-tools` for a focused error. The MCP route needs `Ocp-Apim-Subscription-Key`
> (`static_headers=settings.apim_headers()`).

> [!WARNING]
> **DevUI not installed**
>
> `uv sync --extra devui` (preview package) — or use `uv run poe chat`.

> [!WARNING]
> **No traces in Application Insights**
>
> Ingestion takes 1–3 minutes. `uv run poe traces` shows your local span tree immediately.

> [!WARNING]
> **Evals are slow or expensive**
>
> `uv run poe evals --ids G01,G09` for a subset; `--no-judge` skips LLM judges; `--rescore` re-applies weights for free.

> [!WARNING]
> **`builtin_safety` uses the LLM fallback**
>
> The Foundry safety evaluators (preview) were unavailable through `/foundry`. Scores are still produced; see `notes` in `summary.json`.

> [!WARNING]
> **Upload/cloud eval fails**
>
> Local results are the source of truth. `poe cloud-eval` falls back to `poe upload-evals` automatically.

## Still stuck?

Raise your hand, or post your `PARTICIPANT_ID`, the command and the last line of output in the workshop chat
(never your key). Everything in this workshop is synthetic training data.
