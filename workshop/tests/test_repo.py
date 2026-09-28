"""Repository contract checks: pinned deps, command contract, docs, timings, generated files."""

import json
import re
import sys
import tomllib

import yaml

from tests.helpers import ROOT

CONTRACT_COMMANDS = {
    "smoke", "chat", "devui", "mcp-tools", "lab2", "a2a-card", "lab3", "traces", "evals", "redteam",
    "upload-evals", "cloud-eval", "loop", "promote", "rollback", "catchup", "docs", "test",
}
TIMINGS = {
    "lab0.md": ("5 min", "00:04–00:09"), "lab1.md": ("15 min", "00:11–00:26"), "lab2.md": ("10 min", "00:28–00:38"),
    "lab3.md": ("15 min", "00:40–00:55"), "lab4.md": ("10 min", "00:57–01:07"), "lab5.md": ("20 min", "01:10–01:30"),
    "lab6.md": ("10 min", "01:30–01:40"), "wrap-up.md": ("5 min", "01:40–01:45"),
}


def _pyproject():
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def test_every_dependency_is_pinned():
    project = _pyproject()
    deps = list(project["project"]["dependencies"])
    deps += [d for extra in project["project"]["optional-dependencies"].values() for d in extra]
    deps += [d for group in project["dependency-groups"].values() for d in group]
    for dep in deps:
        assert re.search(r"(==|~=)\d", dep), f"not pinned: {dep}"
    assert "azure-ai-projects==2.7.0" in project["project"]["dependencies"]
    assert not any(d.startswith("agent-framework-foundry") for d in deps)  # would force azure-ai-projects<2.7.0


def test_poe_tasks_implement_the_command_contract():
    tasks = _pyproject()["tool"]["poe"]["tasks"]
    assert CONTRACT_COMMANDS <= set(tasks)
    assert tasks["catchup"]["args"][0]["positional"] is True
    for name, task in tasks.items():
        module = re.match(r"python -m ([\w.]+)", task["cmd"])
        if module:
            path = ROOT / ("src" if module.group(1).startswith("care_agent") else "") / (module.group(1).replace(".", "/") + ".py")
            assert path.exists(), f"poe {name} → {path}"


def test_python_version_and_uv_groups():
    assert (ROOT / ".python-version").read_text().strip() == "3.12"
    assert set(_pyproject()["tool"]["uv"]["default-groups"]) == {"dev", "docs"}


def _mkdocs():
    class Loader(yaml.SafeLoader):
        pass

    Loader.add_multi_constructor("tag:yaml.org,2002:python/name:", lambda loader, suffix, node: suffix)
    return yaml.load((ROOT / "mkdocs.yml").read_text(encoding="utf-8"), Loader=Loader)  # noqa: S506 - custom safe loader


def test_mkdocs_nav_and_features():
    config = _mkdocs()
    assert "content.code.copy" in config["theme"]["features"]
    pages = []

    def walk(items):
        for item in items:
            for value in item.values():
                walk(value) if isinstance(value, list) else pages.append(value)

    walk(config["nav"])
    for page in pages:
        assert (ROOT / "docs" / page).exists(), page
    extensions = json.dumps(config["markdown_extensions"])
    for needed in ("admonition", "pymdownx.superfences", "mermaid", "pymdownx.tabbed", "pymdownx.tasklist"):
        assert needed in extensions


def test_lab_pages_use_contract_timings_and_structure():
    for page, (minutes, clock) in TIMINGS.items():
        text = (ROOT / "docs" / page).read_text(encoding="utf-8")
        assert f"⏱ {minutes}" in text and clock in text, page
        if page.startswith("lab"):
            for section in ("**Goal:**", "## Steps", "## Expected output", "## Troubleshooting", "## What you just proved"):
                assert section in text, (page, section)
            assert "Screenshot placeholder" not in text
    corpus = " ".join(p.read_text(encoding="utf-8") for p in (ROOT / "docs").glob("*.md")).lower()
    assert "two-hour" not in corpus and "2-hour" not in corpus
    assert len(list((ROOT / "docs" / "images").glob("lab*.svg"))) == 9


def test_mermaid_diagrams_present():
    docs = {p.name: p.read_text(encoding="utf-8") for p in (ROOT / "docs").glob("*.md")}
    for page in ("index.md", "setup.md", "lab3.md", "lab4.md", "lab5.md", "lab6.md"):
        assert "```mermaid" in docs[page], page


def test_plain_markdown_labs_are_up_to_date():
    sys.path.insert(0, str(ROOT / "scripts"))
    import export_labs

    for path, text in export_labs.export().items():
        assert path.exists() and path.read_text(encoding="utf-8") == text, f"run scripts/export_labs.py ({path.name})"
    assert "> [!NOTE]" in (ROOT / "labs" / "lab1.md").read_text(encoding="utf-8")


def test_rescore_applies_current_rubric(tmp_path):
    from evals.run_evals import rescore
    from evals.scoring import load_rubric

    run = tmp_path / "20260928-010000-v1"
    run.mkdir()
    row = {"id": "G01", "uses_a2a": False, "must_escalate": False, "metrics": {"intent_resolution": 1.0, "task_adherence": 1.0,
           "tool_call_accuracy": 1.0, "no_clinical_diagnosis": 1.0, "builtin_safety": 1.0}, "error": None}
    (run / "results.jsonl").write_text(json.dumps(row) + "\n")
    (run / "summary.json").write_text(json.dumps({"run_id": run.name, "cost": {"per_task_eur": 0.02},
                                                   "latency": {"p50_ms": 100, "p95_ms": 100}, "notes": []}))
    summary, rows = rescore(run, load_rubric())
    assert rows[0]["row_score"] == 1.0
    assert summary["dimensions"]["cost"] == 0.0 and summary["overall"] < 1.0
    assert (run / "summary.rescored.json").exists()
