# From Prototype to Proof: Building a Production Agent and Actually Knowing It Works

**Participant workshop repo · 1h45m · hands-on**

> **Training use only.** This workshop uses synthetic, fictional data. The Care Coordination Agent is not a medical device and does not provide clinical advice, diagnosis or treatment decisions.

You build a **Care Coordination Agent** for the fictional *Lakeside Regional Health Network*: it helps care
coordinators with discharge planning, specialist referrals, follow-up scheduling, medication reconciliation
checks and prior-authorization policy questions. Then you prove it works: traces, weighted evaluations,
red teaming, and a closed improvement loop with promotion and rollback.

Everything goes through **one Azure API Management gateway**. You need exactly three values — no Azure
account, no `az login`, no Entra credentials:

```
APIM_BASE_URL=https://<apim-name>.azure-api.net
APIM_SUBSCRIPTION_KEY=<your-personal-key>
PARTICIPANT_ID=user00
```

## Quickstart

**Open the visual guide first:** double-click [`guide/index.html`](guide/index.html) in your file manager.
It is a self-contained, English-language website: no server, installation, CDN or internet connection is
needed to read it. It includes all seven labs, copyable code, offline flow diagrams, step checklists,
browser-local progress, troubleshooting and print/PDF support. Running the labs still requires the tools
and gateway connection below. The guide never requests or stores your subscription key.

Prerequisites: **VS Code**, **Git**, **[uv](https://docs.astral.sh/uv/)** (uv installs Python 3.12 for you).
Zero-install alternative: open the repo in **GitHub Codespaces** / a **Dev Container** (`.devcontainer/`).

```bash
# Open the repository's workshop/ folder in your terminal first.
uv sync                       # installs Python 3.12 + pinned dependencies
cp .env.example .env          # Windows PowerShell: Copy-Item .env.example .env
# paste your three values into .env
uv run poe smoke              # Lab 0: all five APIM routes should PASS
uv run poe docs               # OPTIONAL: serve the same static guide at http://127.0.0.1:8000
```

The Markdown alternatives remain in [`labs/`](labs/) (GitHub/VS Code) and [`docs/`](docs/) (canonical source).
The static file can be copied on its own. Checkmarks are local to the browser and file/origin; moving the
file or clearing browser storage can reset them. If automatic copy is blocked, press Ctrl+C / Command+C
after the guide selects the code. Use **Reset progress** to clear checkmarks, not workshop code or results.

## Agenda (105 minutes)

| Clock | Segment | Minutes |
|---|---|---|
| 00:00–00:04 | Opening, disclaimer, architecture (concept) | 4 |
| 00:04–00:09 | Lab 0 — Setup & smoke test | 5 |
| 00:09–00:11 | Concept: agent anatomy & safety boundaries | 2 |
| 00:11–00:26 | Lab 1 — Build the local Care Coordination Agent | 15 |
| 00:26–00:28 | Concept: tools behind one managed MCP endpoint | 2 |
| 00:28–00:38 | Lab 2 — Tools via managed MCP endpoint | 10 |
| 00:38–00:40 | Concept: A2A and agent contracts | 2 |
| 00:40–00:55 | Lab 3 — Multi-agent via A2A | 15 |
| 00:55–00:57 | Concept: trace anatomy | 2 |
| 00:57–01:07 | Lab 4 — Observability | 10 |
| 01:07–01:10 | Concept: defining "good" (weighted rubrics) | 3 |
| 01:10–01:30 | Lab 5 — Evaluations | 20 |
| 01:30–01:40 | Lab 6 — Close the loop (≈4 min presenter demo) | 10 |
| 01:40–01:45 | Wrap-up: "Cheap to change vs. follows you for two years" | 5 |

Fell behind? `uv run poe catchup <N>` copies the end-of-lab-N solution into `src/care_agent/` (your code is backed up in `.catchup_backups/`).

## Commands

| Command | What it does |
|---|---|
| `uv sync` | install pinned deps (uv installs Python 3.12 automatically via `.python-version`) |
| `uv run poe smoke` | Lab 0 connectivity check against /openai, /care-tools/mcp, /a2a/care-knowledge, /telemetry, /foundry |
| `uv run poe chat` | interactive CLI chat (`/tools`, `/trace`, `/reset`, `/exit`) |
| `uv run poe devui` | Agent Framework DevUI (`uv sync --extra devui` first; preview) |
| `uv run poe mcp-tools` | list MCP tools from the managed endpoint |
| `uv run poe lab2` | "Plan discharge for patient P-1042 and book a cardiology follow-up within 7 days." |
| `uv run poe a2a-card` | fetch and pretty-print the base agent's Agent Card through APIM |
| `uv run poe lab3` | prior-auth policy question delegated over A2A; prints citations |
| `uv run poe traces` | your last traces + KQL / portal steps (filtered by PARTICIPANT_ID) |
| `uv run poe evals` | local evaluations with the weighted rubric → `evals/out/<run-id>/` |
| `uv run poe redteam` | adversarial prompts from the escalation & safety policy, evaluated |
| `uv run poe upload-evals` | upload the latest local run to the Foundry project via APIM /foundry |
| `uv run poe cloud-eval` | cloud evaluation in Foundry via APIM /foundry (preview; fallback = upload) |
| `uv run poe loop` | Lab 6: failures → clusters → proposal → re-run evals → promote if better |
| `uv run poe promote` / `rollback` | move the active agent version (lineage in `agent_versions/registry.json`) |
| `uv run poe catchup <N>` | copy `solutions/labN/` into `src/care_agent/` |
| `uv run poe docs` | optionally serve the prebuilt static guide at http://127.0.0.1:8000 |
| `uv run poe docs-build` | regenerate `guide/index.html` after editing the source docs or UI |
| `uv run poe test` | offline unit tests (no Azure needed) |

## Repository map

```
workshop/
├── src/care_agent/        # the agent — starter code with `# TODO (Lab N)` blocks
├── solutions/lab1..lab6/  # checkpoint copies of src/care_agent/ (generated by scripts/build_checkpoints.py)
├── evals/                 # golden set, weighted rubric, evaluators, red team, Foundry upload (Lab 5)
├── loop/                  # failures → clusters → proposal → validation → promotion (Lab 6)
├── agent_versions/        # version registry + candidate instructions (created on first use)
├── deploy/                # PRESENTER-ONLY hosted-agent / Container Apps demo
├── guide/index.html      # self-contained visual guide; open directly in a browser
├── docs/  labs/           # canonical guide source and generated plain-markdown copy
├── scripts/guide/         # static guide template, styles and browser interactions
└── tests/                 # offline pytest suite
```

## Preview features and gateway exceptions

Preview features are labelled in code comments and in the docs, each with a documented fallback — see
`../docs/preview/workshop.md`. The few things that do *not* go through APIM (all presenter/admin paths) are
listed with mitigations in `../docs/apim-exceptions/workshop.md`.

## Maintainers

- Run `uv lock` once before the event (network needed) and commit `uv.lock` so every laptop resolves identically.
- Edit agent code in `scripts/checkpoints/source/care_agent/` (with `# [labN:solution|starter|end]` markers), then
  `python scripts/build_checkpoints.py --starter` regenerates `src/care_agent/` and `solutions/lab1..6/`.
- Edit the guide in `docs/`, then `python scripts/export_labs.py` refreshes the plain-markdown `labs/`.
- Run `uv run poe docs-build` to regenerate and commit `guide/index.html`. Markdown rendering uses the
  existing docs dependency group; participants do not need these packages to open the generated file.
  `scripts/guide/` contains the UI assets, which are inlined at build time. No runtime fetches are used.
  The nine lab-specific SVG illustrations in `docs/images/` are embedded as data URLs, so the HTML
  remains portable. Each illustration is labeled as an example or conceptual view, not a captured
  run or portal screenshot. Keep their captions and accessible descriptions when updating the images.
  The optional localhost server serves only `guide/`, not `.env`, code or other workshop files.
- `python scripts/build_guide.py --check` checks whether the static guide is current.
- `uv run poe test` checks that the generated trees and static guide are up to date.
- The existing `mkdocs.yml` remains available for maintainers who want a conventional documentation build
  (`uv run mkdocs build --strict`); it is not the participant web experience.

## Security notes

- `.env` is git-ignored. Never commit your key; it is personal and revoked after the session.
- The Foundry SDK "credential" in `src/care_agent/apim_auth.py` is a **workshop pattern**: a placeholder token
  that APIM discards before calling Foundry with its own managed identity. Do not copy it into production.
