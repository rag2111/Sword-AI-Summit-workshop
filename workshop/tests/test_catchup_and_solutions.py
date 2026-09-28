import importlib
import importlib.util
import shutil
import sys
from datetime import datetime

import pytest

from tests.helpers import ROOT

sys.path.insert(0, str(ROOT / "scripts"))
import build_checkpoints  # noqa: E402
import catchup  # noqa: E402

MODULES = ("config", "errors", "apim_auth", "instructions", "versions", "telemetry", "tools_mcp", "a2a_delegate",
           "agent", "ui", "cli", "devui", "smoke", "lab2", "lab3")


def _fake_root(tmp_path, lab=3):
    ignore = shutil.ignore_patterns("__pycache__")
    shutil.copytree(ROOT / "solutions" / f"lab{lab}", tmp_path / "solutions" / f"lab{lab}", ignore=ignore, copy_function=shutil.copy)
    shutil.copytree(ROOT / "src" / "care_agent", tmp_path / "src" / "care_agent", ignore=ignore, copy_function=shutil.copy)
    return tmp_path


def test_catchup_copies_solution_and_keeps_backup(tmp_path):
    root = _fake_root(tmp_path)
    (root / "src" / "care_agent" / "my_notes.py").write_text("# mine")
    backup = catchup.catchup(3, root=root, now=datetime(2026, 9, 28, 9, 0, 0))
    assert backup.name == "20260928-090000-before-lab3"
    assert (backup / "my_notes.py").exists()
    assert not (root / "src" / "care_agent" / "my_notes.py").exists()
    init = (root / "src" / "care_agent" / "__init__.py").read_text()
    assert 'CHECKPOINT = "lab3"' in init


def test_catchup_rejects_invalid_lab(tmp_path):
    with pytest.raises(ValueError):
        catchup.catchup(0, root=_fake_root(tmp_path))
    assert catchup.main(["x"]) == 2


def test_solutions_are_generated_from_the_single_source():
    for lab in build_checkpoints.LABS:
        assert build_checkpoints.outdated(lab, ROOT / "solutions" / f"lab{lab}") == [], f"run scripts/build_checkpoints.py (lab{lab})"


def test_marker_rendering_levels():
    source = "a\n# [lab2:solution]\nsolved\n# [lab2:starter]\ntodo\n# [lab2:end]\nz __CHECKPOINT__\n"
    assert build_checkpoints.render(source, 0) == "a\ntodo\nz starter\n"
    assert build_checkpoints.render(source, 1) == "a\ntodo\nz lab1\n"
    assert build_checkpoints.render(source, 2) == "a\nsolved\nz lab2\n"
    with pytest.raises(ValueError):
        build_checkpoints.render("# [lab1:solution]\nx\n", 1)


def test_todo_markers_progress_across_checkpoints():
    starter = "".join(p.read_text() for p in (ROOT / "src" / "care_agent").glob("*.py"))
    for lab in range(1, 7):
        text = "".join(p.read_text() for p in (ROOT / "solutions" / f"lab{lab}").glob("*.py"))
        assert f"TODO (Lab {lab})" not in text
        if lab in (1, 2, 3, 4, 6):
            assert f"TODO (Lab {lab})" in starter
    assert "[lab" not in starter  # markers never leak into participant code


@pytest.mark.parametrize("checkpoint", ["src/care_agent"] + [f"solutions/lab{n}" for n in range(1, 7)])
def test_every_checkpoint_imports_cleanly(checkpoint):
    """Import each checkpoint as its own package; third-party SDKs are imported lazily, so this is offline."""
    folder = ROOT / checkpoint
    name = "ckpt_" + checkpoint.replace("/", "_")
    spec = importlib.util.spec_from_file_location(name, folder / "__init__.py", submodule_search_locations=[str(folder)])
    package = importlib.util.module_from_spec(spec)
    sys.modules[name] = package
    spec.loader.exec_module(package)
    for module in MODULES:
        importlib.import_module(f"{name}.{module}")
    expected = "starter" if checkpoint.startswith("src") else checkpoint.rsplit("/", 1)[-1]
    assert package.CHECKPOINT == expected


def test_starter_degrades_gracefully():
    """Before Lab 1 the CLI must explain what to do instead of crashing."""
    from care_agent import CHECKPOINT
    from care_agent.errors import LabIncomplete

    if CHECKPOINT != "starter":
        pytest.skip("src/care_agent is not the starter (catch-up was used)")
    from care_agent.agent import create_chat_client
    from care_agent.tools_mcp import create_mcp_tool
    from tests.helpers import make_settings

    settings = make_settings()
    assert create_chat_client(settings) is None
    assert create_mcp_tool(settings) is None
    error = LabIncomplete(1, "agent.py")
    assert "poe catchup 1" in str(error)
