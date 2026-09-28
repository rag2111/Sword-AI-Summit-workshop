<!-- Generated from docs/lab0.md by scripts/export_labs.py — edit the docs/ version. -->

# Lab 0 — Setup & smoke test

**⏱ 5 min** · 00:04–00:09

**Goal:** prove that your laptop can reach all five gateway routes with nothing but your subscription key.

> [!NOTE]
> **Concept: one gateway, five routes, zero Azure credentials**
>
> | Route | What is behind it | How APIM authenticates to it |
> |---|---|---|
> | `/openai/*` | Foundry model deployments (`gpt-6-luna`, `gpt-6-sol`) | managed identity |
> | `/care-tools/mcp` | the mock clinical REST API, exposed **as an MCP server** by APIM | internal |
> | `/a2a/care-knowledge/*` | the base knowledge agent in Foundry Agent Service | managed identity |
> | `/foundry/*` | an allow-listed slice of the Foundry project data plane | managed identity |
> | `/telemetry/*` | Application Insights ingestion | instrumentation key |
>
> Your key identifies you (`PARTICIPANT_ID`), carries your rate and token limits, and is what shows up as
> "User ID" in the gateway's token metrics.

## Steps

> [!TIP]
> **1. Open the workshop workspace**
>
> Open the `workshop/` folder in VS Code, then choose **Terminal > New Terminal**.
> All commands in this guide run from that folder, which contains `pyproject.toml`.
> Keep the guide open in a browser beside your editor. If you have not installed uv, follow [Setup](setup.md) first.

> [!TIP]
> **2. Install the workshop dependencies**
>
> ```bash
> uv sync
> ```
> Wait for the command to finish before continuing. It installs Python 3.12 and creates `.venv/`.
> If you already completed Setup, confirm the environment is ready; do not overwrite your configuration.

> [!TIP]
> **3. Configure your personal gateway access**
>
> If `.env` already contains your participant values, keep it. Otherwise copy `.env.example` to `.env`
> in the VS Code Explorer (copy, paste, rename), then open the new file.
> Set `APIM_BASE_URL`, `APIM_SUBSCRIPTION_KEY` and `PARTICIPANT_ID` to the values supplied by the presenter.
> Save the file. Do not paste credentials into the guide, chat prompts or a shared screen.
> See [Setup](setup.md#your-three-values) for shell-specific copy commands.

> [!TIP]
> **4. Run the smoke test**
>
> ```bash
> uv run poe smoke
> ```
> Read each route's **Result** and **Detail** columns. A working browser page does not prove gateway
> connectivity: this command does. If any route fails, use the troubleshooting section before retrying.

> [!TIP]
> **5. Record your readiness**
>
> Confirm `/openai`, `/care-tools/mcp` and `/a2a/care-knowledge` pass before starting the agent labs.
> Confirm `/telemetry` and `/foundry` pass before Labs 4 and 5. If only these last two fail, notify a helper;
> you can continue to Lab 1 while they investigate.

> [!IMPORTANT]
> **Checkpoint**
>
> All five routes show **PASS**. If a helper has approved a temporary exception, leave this checkpoint
> unchecked until the remaining routes work.

## Expected output

```text
╭──────────────────────────────────────────────────────────────────────────────╮
│ From Prototype to Proof: Building a Production Agent and Actually Knowing … │
│ Lab 0 — smoke test · Lakeside Regional Health Network (fictional)            │
│ Training use only. This workshop uses synthetic, fictional data. …           │
╰──────────────────────────────────────────────────────────────────────────────╯
                                APIM routes
┏━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Route               ┃ Result ┃ Detail                                        ┃
┡━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ /openai             │ PASS   │ gpt-6-luna answered 'ready'                 │
│ /care-tools/mcp     │ PASS   │ 7 tools: book_follow_up, check_medication_…   │
│ /a2a/care-knowledge │ PASS   │ Agent Card 'care-knowledge-agent' · skills: … │
│ /telemetry          │ PASS   │ config OK · test event accepted: 1            │
│ /foundry            │ PASS   │ base agent 'care-knowledge-agent' (latest …)  │
└─────────────────────┴────────┴───────────────────────────────────────────────┘
✓ All five routes work with nothing but your subscription key.
```

The table is illustrative; model names and tool details may differ. The five route results are what matter.

## Troubleshooting

> [!WARNING]
> **Every route fails with 401**
>
> The key is wrong. Re-copy `APIM_SUBSCRIPTION_KEY` from your card — no quotes, no spaces. The gateway
> accepts it in both `Ocp-Apim-Subscription-Key` and `api-key` headers; the code sends both.

> [!WARNING]
> **`Missing or placeholder values in .env`**
>
> You still have `<...>` or `user00` in `.env`, or the file is named `.env.txt` (Windows). Run
> `ls -a` (macOS/Linux) or `Get-ChildItem -Force` (PowerShell) and check.

> [!WARNING]
> **Only /telemetry or /foundry fails**
>
> You can start Lab 1 anyway — those routes are needed from Lab 4 / Lab 5. Tell a helper.

More: [Troubleshooting](troubleshooting.md).

## What you just proved

- [ ] One key + one base URL is the entire client-side configuration.
- [ ] Models, tools, a remote agent, the Foundry project and telemetry all sit behind the same policy point.
- [ ] Nothing on your laptop holds an Azure credential — the gateway's managed identity does the work.

Next: [Lab 1 — Build the local Care Coordination Agent](lab1.md).
