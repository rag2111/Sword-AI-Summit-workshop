import json
import os
import subprocess
import sys

import pytest

from care_agent.instructions import BASE_INSTRUCTIONS, build_instructions, instructions_hash
from care_agent.versions import (
    active_instructions,
    instructions_for,
    latest_candidate,
    load_registry,
    promote,
    record_eval,
    register_candidate,
    rollback,
)
from tests.helpers import ROOT


def test_registry_starts_with_builtin_baseline(tmp_path):
    registry = load_registry(tmp_path)
    assert registry["active"] == "v1"
    assert registry["versions"]["v1"]["instructions_hash"] == instructions_hash(BASE_INSTRUCTIONS)
    assert active_instructions(tmp_path) == ("v1", BASE_INSTRUCTIONS)


def test_candidate_promote_and_rollback_lineage(tmp_path):
    text = build_instructions("Always restate the goal first.")
    entry = register_candidate(text, notes="test", diff="--- a\n+++ b\n", root=tmp_path)
    assert entry["version"] == "v2" and entry["parent"] == "v1" and entry["status"] == "candidate"
    assert (tmp_path / "candidates" / "v2" / "instructions.md").read_text() == text
    assert (tmp_path / "candidates" / "v2" / "change.diff").exists()

    with pytest.raises(ValueError, match="validate"):
        promote("v2", root=tmp_path)  # not validated yet

    record_eval("v2", eval_run_id="run-2", overall_score=0.91, trace_ids=["t1", "t2"], passed_gate=True, root=tmp_path)
    assert latest_candidate(load_registry(tmp_path)) == "v2"
    promoted = promote("v2", root=tmp_path)
    assert promoted["status"] == "active" and promoted["eval_run_id"] == "run-2" and promoted["trace_ids"] == ["t1", "t2"]
    registry = load_registry(tmp_path)
    assert registry["active"] == "v2" and registry["versions"]["v1"]["status"] == "retired"
    assert active_instructions(tmp_path) == ("v2", text)

    previous, active = rollback(tmp_path)
    assert (previous, active) == ("v2", "v1")
    registry = json.loads((tmp_path / "registry.json").read_text())
    assert registry["active"] == "v1"
    assert registry["versions"]["v2"]["status"] == "rolled_back"
    assert [e["action"] for e in registry["history"]] == ["init", "promote", "rollback"]


def test_rejected_candidate_and_rollback_without_parent(tmp_path):
    register_candidate("x", root=tmp_path)
    record_eval("v2", eval_run_id="r", overall_score=0.1, passed_gate=False, root=tmp_path)
    assert load_registry(tmp_path)["versions"]["v2"]["status"] == "rejected"
    with pytest.raises(ValueError):
        rollback(tmp_path)  # v1 has no parent
    with pytest.raises(KeyError):
        instructions_for("v9", tmp_path)


def test_force_promote_for_demos(tmp_path):
    register_candidate("demo", root=tmp_path)
    assert promote("v2", require_validation=False, root=tmp_path)["status"] == "active"


@pytest.mark.parametrize("status", ["candidate", "rejected"])
def test_poe_force_promotion_preserves_evidence_and_can_roll_back(tmp_path, status):
    register_candidate("demo", root=tmp_path)
    if status == "rejected":
        record_eval("v2", eval_run_id="failed-run", overall_score=0.1, trace_ids=["trace"],
                    passed_gate=False, root=tmp_path)
    env = {**os.environ, "AGENT_VERSIONS_DIR": str(tmp_path)}
    before = load_registry(tmp_path)["versions"]["v2"]

    result = subprocess.run(
        [sys.executable, "-m", "poethepoet", "promote-force", "--version", "v2"],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=30,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "bypasses validation (demo only)" in result.stdout
    registry = load_registry(tmp_path)
    assert registry["active"] == "v2"
    for field in ("eval_run_id", "overall_score", "trace_ids", "instructions_hash", "parent"):
        assert registry["versions"]["v2"][field] == before[field]
    assert registry["history"][-1]["action"] == "promote"
    assert rollback(tmp_path) == ("v2", "v1")


@pytest.mark.parametrize("arguments", [[], ["--version", "v999"]])
def test_poe_force_promotion_requires_existing_explicit_version(tmp_path, arguments):
    register_candidate("demo", root=tmp_path)
    before = load_registry(tmp_path)
    result = subprocess.run(
        [sys.executable, "-m", "poethepoet", "promote-force", *arguments],
        cwd=ROOT, env={**os.environ, "AGENT_VERSIONS_DIR": str(tmp_path)},
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode != 0
    assert load_registry(tmp_path) == before
