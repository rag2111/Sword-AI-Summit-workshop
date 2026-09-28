DISCLAIMER_TEXT = "does not provide clinical advice, diagnosis or treatment decisions"


def test_instructions_contain_safety_boundaries():
    from care_agent.instructions import BASE_INSTRUCTIONS

    text = BASE_INSTRUCTIONS.lower()
    assert "never diagnose" in text
    assert "dosing" in text and "treatment decisions" in text
    assert "emergency pathway" in text and "clinician" in text
    assert "cite" in text and "section" in text
    assert "synthetic" in text
    assert DISCLAIMER_TEXT in BASE_INSTRUCTIONS


def test_hash_is_stable_and_content_based():
    from care_agent.instructions import BASE_INSTRUCTIONS, build_instructions, instructions_hash

    assert instructions_hash(BASE_INSTRUCTIONS) == instructions_hash(BASE_INSTRUCTIONS + "\n")
    assert instructions_hash(build_instructions("extra rule")) != instructions_hash(BASE_INSTRUCTIONS)


def test_disclaimer_everywhere():
    from care_agent import DISCLAIMER
    from tests.helpers import ROOT

    assert DISCLAIMER_TEXT in DISCLAIMER
    for path in ("README.md", "docs/index.md"):
        assert DISCLAIMER_TEXT in (ROOT / path).read_text(encoding="utf-8"), path
