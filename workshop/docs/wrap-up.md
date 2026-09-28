# Wrap-up: "Cheap to change vs. follows you for two years"

<span class="lab-timer" data-minutes="5">⏱ 5 min</span> · 01:40–01:45

Some decisions you made today can be reversed in a minute. Others will shape your platform for years.
Spend your design time accordingly.

| Decision | Cost of change | Why |
|---|---|---|
| **Model choice** (`gpt-6-luna` vs `gpt-6-sol` …) | 🟢 Cheap | One setting behind the gateway (`CHAT_MODEL`). The eval suite tells you within minutes whether a swap is safe. |
| **Prompts / instructions** | 🟢 Cheap | Versioned data with hash, eval run and rollback (Lab 6). Change them often — but only through the gate. |
| **Tools behind MCP** | 🟡 Moderate | Adding tools is cheap; *renaming or re-shaping* them breaks every agent and every eval that expects them. Tool names and schemas are an API. |
| **Gateway & identity pattern** | 🔴 Follows you | Where keys, managed identities, quotas and policies live decides your security model, cost attribution and audit story. Retrofitting a gateway onto dozens of agents is a migration project. |
| **Trace schema & correlation IDs** | 🔴 Follows you | `participant.id`, `care_agent.version`, W3C propagation and GenAI semantic conventions become the columns of every dashboard, alert and investigation. Historical data cannot be re-labelled. |
| **Eval data & rubric ownership** | 🔴 Follows you | The golden set and weights encode what "good" means. Someone must own them (product + clinical safety), or every release argument starts from zero. They also become your regression history. |
| **Data residency** | 🔴 Follows you | Region of models, knowledge bases, traces and eval results is fixed by contracts and regulation. Moving later means re-certification and data migration. |
| **Agent-to-agent contracts** (Agent Cards) | 🔴 Follows you | Other teams build on your card: skills, inputs, citation format, versioning. Breaking it breaks them — treat it like a public API with deprecation windows. |

## What you proved today

- [ ] One gateway, one key: models, MCP tools, a remote agent, Foundry and telemetry — no Azure credentials on laptops.
- [ ] Safety boundaries written as testable rules, measured by custom and built-in evaluators.
- [ ] One trace from laptop to backend, carrying participant and version.
- [ ] A weighted rubric with a hard safety gate; a red-team suite generated from the policy itself.
- [ ] A closed loop: failures → proposal → validation → promotion with lineage → rollback.

!!! concept "Take it home"
    Keep `evals/`, `loop/` and `agent_versions/` — they are framework-agnostic. Swap the agent, keep the proof.

<div class="disclaimer" markdown>
**Training use only.** This workshop uses synthetic, fictional data. The Care Coordination Agent is not a medical device and does not provide clinical advice, diagnosis or treatment decisions.
</div>
