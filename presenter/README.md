# Presenter Kit — From Prototype to Proof

**Building a Production Agent and Actually Knowing It Works** · 1h45m (105 minutes) · Care Coordination Agent for the fictional *Lakeside Regional Health Network*

> **Training use only.** This workshop uses synthetic, fictional data. The Care Coordination Agent is not a medical device and does not provide clinical advice, diagnosis or treatment decisions.

## How to use this kit

1. **One week before:** read `run-of-show.md` end to end and `slide-notes.md`; check region/quota items in `preflight-checklist.md`.
2. **The day before:** work through `preflight-checklist.md` → *Day before*. Deploy with `terraform apply` (APIM classic tiers can take 30–60 min), dry-run `live-demo-lab6.md`, and capture recordings into `fallback/` (see `fallback/README.md`).
3. **The hour before:** `preflight-checklist.md` → *Hour before*. Print `timing-cards.md`.
4. **During the session:** run from `run-of-show.md` (clock times are binding, from `docs/CONTRACT.md` §7). Keep `troubleshooting-faq.md` open for yourself and helpers.
5. **After:** revoke keys / `terraform destroy` from `infra/` (see `preflight-checklist.md` → *After the session*).

Every command in this kit comes from `docs/CONTRACT.md` §11. Participant commands run from `workshop/`; infra commands run from `infra/` (presenter/admin only).

## File index

| File | Purpose |
|---|---|
| `README.md` | This file |
| `run-of-show.md` | Minute-by-minute plan for 105 minutes: talking points, screen, room checkpoints, per-lab fallbacks, time bank, platform-down plan |
| `slide-notes.md` | 16-slide outline with speaker notes and Mermaid diagrams (architecture, APIM request flow, A2A sequence, trace anatomy, evaluation loop) |
| `preflight-checklist.md` | Day-before and hour-before checklists, quota sizing formula, key distribution |
| `live-demo-lab6.md` | Lab 6 close-the-loop live demo script + optional presenter-only production runtime demo |
| `troubleshooting-faq.md` | Symptom → cause → fix for 401, 429, MCP, A2A, traces, eval judge, uv, Codespaces, Windows |
| `timing-cards.md` | Printable one-line cue cards with hard-stop times |
| `fallback/README.md` | What to record during the dry run and file names to use if the platform is down |
| `scripts/validate_kit.py` | Checks the kit: timings sum to 105 min and match the contract, Mermaid fences, forbidden wording |

Registers owned by this deliverable (merged by the orchestrator):

- `../docs/preview/presenter.md` — preview features used by the presenter kit
- `../docs/apim-exceptions/presenter.md` — places where the presenter steps outside "everything via APIM"

## Roles in the room

| Role | Owns |
|---|---|
| Presenter | Concept segments, Lab 6 demo, clock, go/no-go calls on fallbacks |
| Helper(s) (1 per ~10 participants recommended) | Red-sticky triage using `troubleshooting-faq.md`, key-card questions |
| Admin (can be the presenter) | Azure portal, APIM policy changes (token limits), infra fallbacks |

Validate after editing: `python3 presenter/scripts/validate_kit.py` (from the repo root).
