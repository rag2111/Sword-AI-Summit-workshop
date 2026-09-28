# agent_versions/

Version registry for the Care Coordination Agent (Lab 6). Created on first use by `care_agent/versions.py`.

- `registry.json` — `active` pointer, one entry per version (`version`, `parent`, `instructions_hash`,
  `instructions_file`, `eval_run_id`, `overall_score`, `trace_ids`, `created_at`, `status`) and a `history`
  of promotions and rollbacks.
- `candidates/vN/` — `instructions.md` (full candidate instructions), `change.diff` (vs. its parent) and
  `proposal.json` (failure cluster, rationale, suggested tool-description changes for the MCP owners).

`v1` is always the built-in baseline in `src/care_agent/instructions.py`. Use `uv run poe promote` /
`uv run poe rollback`; do not edit `registry.json` by hand during the lab.

For a three-case rehearsal, use `uv run poe loop --limit 3` (optionally `--offline`).
This compares the same first three golden cases per version and never auto-promotes.
Validate on the full set before normal promotion.

For an explicit synthetic demo override, use `uv run poe promote-force --version v3`
(replace `v3` with your existing version). It is equivalent to
`uv run poe promote --version v3 --force` and can activate an unvalidated or rejected candidate.
It preserves existing evidence but does not run evaluations or prove that safety gates passed.
Restart chat to load the active version; use `uv run poe rollback` to undo the promotion.
