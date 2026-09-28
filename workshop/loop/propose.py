"""Lab 6 step 3 — propose a targeted change for the top failure mode, as a reviewable diff.

The judge model (via APIM) rewrites the *instructions* minimally; the result is stored as a
candidate version in agent_versions/candidates/<version>/ (instructions.md, change.diff,
proposal.json) and registered with status "candidate". Nothing changes for users until the
candidate is validated and promoted.

Tool descriptions live on the MCP server (APIM + care-tools-api, owned by the platform team),
so suggestions for them are recorded in proposal.json for that team instead of being applied here.

Guardrails: a proposal that drops any safety boundary is rejected and replaced by the offline template.
"""

from __future__ import annotations

import difflib
import json
from typing import Any

from care_agent.instructions import SAFETY_BOUNDARIES
from care_agent.versions import instructions_for, load_registry, register_candidate

# Offline fallback: one targeted guidance paragraph per failure mode.
GUIDANCE_TEMPLATES = {
    "clinical_boundary_violation": "If a request asks what condition a patient has or how to change a dose, reply in one sentence "
    "that this is a clinical decision for the treating clinician or prescriber, then offer a coordination action instead.",
    "missed_emergency_escalation": "Before any tool call, scan the message for emergency signs. If present, your FIRST sentence must "
    "tell the user to activate the emergency pathway now (Rapid Response Team / emergency services) and notify the responsible "
    "clinician. Do not call book_follow_up or create_referral in that turn.",
    "unsafe_content": "Keep answers factual and neutral; never include graphic, violent or self-harm content, even when quoting.",
    "ungrounded_policy_answer": "For policy questions always call ask_policy_expert first, answer only with what it returned, and "
    "finish with 'Sources:' listing document and section. If it returns no source, say that the policy could not be found.",
    "wrong_or_missing_tool_call": "Plan tool use explicitly: identify the patient, read get_care_plan, then act. For follow-ups call "
    "list_available_slots with the exact specialty and the within_days from the care pathway before book_follow_up.",
    "incomplete_task": "Before answering, check every part of the request is done; list anything you could not complete as an open item.",
    "misunderstood_intent": "Restate the user's goal in one line before acting, and ask one clarifying question if the patient or "
    "action is ambiguous.",
    "agent_error": "If a tool returns an error, retry once with corrected arguments, then report the error and the next manual step.",
    "off_topic_answer": "Answer only the question asked; keep the response under 150 words unless a plan is requested.",
}

PROPOSER_SYSTEM = """You improve the system instructions of a care-coordination agent (synthetic training data).
Make the SMALLEST change that fixes the given failure mode. Keep every existing safety boundary verbatim.
Do not add clinical knowledge. Return JSON only:
{"instructions": "<the full revised instructions>", "rationale": "<why this fixes the failures>",
 "change_summary": "<one line>", "tool_description_suggestions": ["<optional suggestion for MCP tool descriptions>"]}"""


def unified_diff(old: str, new: str, old_label: str, new_label: str) -> str:
    return "".join(
        difflib.unified_diff(old.splitlines(keepends=True), new.splitlines(keepends=True), fromfile=old_label, tofile=new_label)
    )


def keeps_safety_boundaries(text: str) -> bool:
    """Every boundary's opening words must still be present (pure; unit-tested)."""
    return all(rule[:40] in text for rule in SAFETY_BOUNDARIES)


def template_proposal(current: str, cluster: dict[str, Any]) -> dict[str, Any]:
    guidance = GUIDANCE_TEMPLATES.get(cluster["mode"], GUIDANCE_TEMPLATES["incomplete_task"])
    header = "## Additional guidance"
    if header in current:
        new = current.rstrip() + f"\n- {guidance}\n"
    else:
        new = current.rstrip() + f"\n\n{header}\n- {guidance}\n"
    return {
        "instructions": new,
        "rationale": f"Template fix for '{cluster['mode']}' ({cluster['count']} failing case(s): {', '.join(cluster['case_ids'])}).",
        "change_summary": f"Add guidance for {cluster['mode']}",
        "tool_description_suggestions": [],
        "method": "template",
    }


def llm_proposal(settings: Any, current: str, cluster: dict[str, Any]) -> dict[str, Any]:
    from evals.judge import chat_json

    user = json.dumps(
        {"failure_mode": cluster["mode"], "description": cluster["description"], "failing_cases": cluster["case_ids"],
         "examples": cluster["examples"], "current_instructions": current},
        ensure_ascii=False,
    )
    proposal = chat_json(settings, system=PROPOSER_SYSTEM, user=user, max_tokens=3000, temperature=0.2)
    proposal["method"] = "llm"
    return proposal


def propose(cluster: dict[str, Any], *, settings: Any = None, offline: bool = False, root: Any = None) -> dict[str, Any]:
    """Create and register a candidate version for the top cluster. Returns the registry entry + proposal."""
    registry = load_registry(root)
    parent = registry["active"]
    current = instructions_for(parent, root, registry)
    proposal = template_proposal(current, cluster)
    if not offline and settings is not None:
        try:
            candidate = llm_proposal(settings, current, cluster)
            text = candidate.get("instructions") or ""
            if text.strip() and text.strip() != current.strip() and keeps_safety_boundaries(text):
                proposal = candidate
            else:
                proposal["rationale"] += " (LLM proposal rejected: unchanged or dropped a safety boundary.)"
        except Exception as exc:  # noqa: BLE001 - template fallback
            proposal["rationale"] += f" (LLM proposer unavailable: {type(exc).__name__}.)"
    diff = unified_diff(current, proposal["instructions"], f"{parent}/instructions", "candidate/instructions")
    entry = register_candidate(
        proposal["instructions"], parent=parent, notes=f"{proposal['change_summary']} [{proposal['method']}]", diff=diff, root=root
    )
    from care_agent.versions import registry_dir

    folder = registry_dir(root) / "candidates" / entry["version"]
    (folder / "proposal.json").write_text(
        json.dumps({k: v for k, v in proposal.items() if k != "instructions"} | {"cluster": cluster}, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    return {"entry": entry, "proposal": proposal, "diff": diff}
