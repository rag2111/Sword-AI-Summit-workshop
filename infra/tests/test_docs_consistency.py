"""Knowledge documents are synthetic, citable and consistent with the mock backend rules."""

import re

import _helpers
from app import data

DOCS = {p.name: p.read_text(encoding="utf-8") for p in sorted(_helpers.DOCS.glob("*.md"))}


def doc(prefix: str) -> str:
    return next(text for name, text in DOCS.items() if name.startswith(prefix))


def test_twelve_fictional_documents_with_ids_and_sections():
    assert len(DOCS) == 12
    ids = set()
    for name, text in DOCS.items():
        assert text.startswith("---\ndoc_id: "), name
        assert "fictional" in text.lower() and "SYNTHETIC TRAINING CONTENT" in text, name
        ids.add(re.search(r"^doc_id: (\S+)$", text, flags=re.M).group(1))
        sections = re.findall(r"^## ([A-Z0-9]+-\d+) ", text, flags=re.M)
        assert len(sections) >= 3, f"{name} needs section IDs for citations"
    assert len(ids) == 12


def test_payers_and_prior_auth_matrix_match_backend():
    rows = _helpers.markdown_table(doc("07"), "Procedure code")
    header = ["Northwind Health Plan", "Contoso Care Insurance", "Fabrikam Mutual Assurance"]
    assert header == [data.PAYERS[c] for c in ("NHP", "CCI", "FMA")]
    parsed = {}
    for code, description, *cells in rows:
        assert cells and all(c in ("Required", "Not required") for c in cells), code
        parsed[code] = {short: cell == "Required" for short, cell in zip(("NHP", "CCI", "FMA"), cells)}
        assert data.PROCEDURES[code] == description
    assert parsed == data.PRIOR_AUTH_MATRIX
    # Contract examples (CONTRACT §3).
    assert parsed["CARD-ECHO"]["NHP"] is False and parsed["CARD-MRI"]["NHP"] is True
    assert parsed["PULM-REHAB"]["CCI"] is True and parsed["ENDO-CGM"]["FMA"] is True


def test_payer_short_codes_documented():
    rows = {name: code for name, code in _helpers.markdown_table(doc("07"), "Payer")}
    assert {code: name for name, code in rows.items()} == data.PAYERS


def test_referral_sla_matches_backend():
    rows = {spec: int(days) for spec, days in _helpers.markdown_table(doc("05"), "Specialty")}
    assert rows == data.ROUTINE_SLA_DAYS
    assert "**2** (all specialties)" in doc("05") and data.URGENT_SLA_DAYS == 2


def test_follow_up_sla_matches_care_plans():
    rows = _helpers.markdown_table(doc("08"), "Condition")
    table = {(r[0], r[1]): int(r[2]) for r in rows}
    assert table[("Heart failure (HFrEF)", "cardiology")] == 7
    assert table[("COPD exacerbation", "pulmonology")] == 14
    assert table[("Type 2 diabetes with hyperglycaemia", "endocrinology")] == 14
    assert table[("Hip fracture, post-surgery", "primary-care")] == 7
    plans = {pid: {f["specialty"]: f["within_days_of_discharge"] for f in p["required_follow_ups"] if f["kind"] == "appointment"}
             for pid, p in data.PATIENTS.items()}
    assert plans["P-1042"]["cardiology"] == 7 and plans["P-2077"]["pulmonology"] == 14
    assert plans["P-3150"]["endocrinology"] == 14 and plans["P-4203"]["primary-care"] == 7


def test_interaction_rules_match_backend():
    rows = _helpers.markdown_table(doc("06"), "Rule ID")
    documented = [(r[0], r[1], r[2], r[3], r[4]) for r in rows]
    assert documented == data.INTERACTION_RULES
    assert data.INTERACTION_DISCLAIMER in doc("06")


def test_provider_directory_lists_every_clinician():
    directory = doc("10")
    for specialty, clinicians in data.CLINICIANS.items():
        for name, location in clinicians:
            assert name in directory and location in directory, name


def test_safety_policy_is_red_team_ready():
    safety = doc("09")
    never = re.findall(r"^SAFE-NEVER-(\d{2}) The agent must never ", safety, flags=re.M)
    escalations = re.findall(r"^SAFE-ESC-(\d{2}) \*\*", safety, flags=re.M)
    assert len(never) >= 10 and never == [f"{i:02d}" for i in range(1, len(never) + 1)]
    assert len(escalations) >= 6 and escalations == [f"{i:02d}" for i in range(1, len(escalations) + 1)]
    assert "not a medical device" in safety


def test_docs_use_only_contract_specialties_and_payers():
    everything = "\n".join(DOCS.values())
    for payer in data.PAYERS.values():
        assert payer in everything
    assert "two-hour" not in everything.lower()
