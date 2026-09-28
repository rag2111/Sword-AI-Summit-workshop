"""Business rules of the mock backend (pure Python, no FastAPI needed)."""

from datetime import date, timedelta

import pytest

import _helpers  # noqa: F401  (puts the backend on sys.path)
from app import data

TODAY = date(2026, 9, 28)


def test_patients_match_contract():
    expected = {
        "P-1042": ("Jordan Ellis", 68, "Northwind Health Plan", {"furosemide", "lisinopril", "spironolactone", "metoprolol"}),
        "P-2077": ("Sam Okafor", 72, "Contoso Care Insurance", {"tiotropium", "prednisolone", "salbutamol"}),
        "P-3150": ("Riley Chen", 55, "Fabrikam Mutual Assurance", {"metformin", "insulin glargine", "atorvastatin"}),
        "P-4203": ("Alex Moreno", 81, "Northwind Health Plan", {"warfarin", "paracetamol", "omeprazole"}),
        "P-5318": ("Taylor Brooks", 47, "Fabrikam Mutual Assurance", {"sacubitril/valsartan", "bisoprolol"}),
    }
    assert set(data.PATIENTS) == set(expected)
    for pid, (name, age, payer, meds) in expected.items():
        p = data.PATIENTS[pid]
        assert (p["display_name"], p["age"], p["payer"]) == (name, age, payer)
        assert {m["name"] for m in p["medications"]} == meds
    assert data.PATIENTS["P-1042"]["ward"] == "Cardiology 4B"
    assert data.PATIENTS["P-2077"]["ward"] == "Respiratory 2A"


def test_search_by_name_fragment_and_id():
    assert [p["patient_id"] for p in data.search_patients("ellis")] == ["P-1042"]
    assert [p["display_name"] for p in data.search_patients("p-2077")] == ["Sam Okafor"]
    assert data.search_patients("   ") == []
    assert set(data.search_patients("P-")[0]) == {"patient_id", "display_name", "age", "primary_condition",
                                                   "ward", "discharge_status"}


def test_care_plan_shape_and_follow_ups():
    plan = data.get_care_plan("P-1042", TODAY)
    for key in ("patient_id", "condition", "care_pathway", "discharge_readiness", "pending_tasks",
                "medications", "payer", "required_follow_ups"):
        assert key in plan
    cardio = [f for f in plan["required_follow_ups"] if f["specialty"] == "cardiology"]
    assert cardio and cardio[0]["within_days_of_discharge"] == 7
    with pytest.raises(data.NotFoundError):
        data.get_care_plan("P-9999", TODAY)


@pytest.mark.parametrize("offset", range(0, 60, 7))
def test_cardiology_has_two_slots_within_7_days_for_any_today(offset):
    today = TODAY + timedelta(days=offset)
    slots = data.CareToolsState().list_slots("user01", "cardiology", 7, today)
    assert len(slots) >= 2
    for s in slots:
        assert today < date.fromisoformat(s["start"][:10]) <= today + timedelta(days=7)


def test_slots_are_deterministic_and_unique():
    first, second = data.generate_slots(TODAY), data.generate_slots(TODAY)
    assert first == second
    ids = [s["slot_id"] for s in first]
    assert len(ids) == len(set(ids)) == 50
    assert {s["specialty"] for s in first} == set(data.SPECIALTIES)
    assert data.generate_slots(TODAY)[0]["slot_id"] == data.generate_slots(TODAY + timedelta(days=3))[0]["slot_id"]


def test_booking_conflict_and_participant_isolation():
    state = data.CareToolsState()
    slot = state.list_slots("user01", "cardiology", 7, TODAY)[0]["slot_id"]
    booked = state.book("user01", "P-1042", slot, "Heart failure review", TODAY)
    assert booked["status"] == "booked" and booked["appointment_id"].startswith("APT-")
    with pytest.raises(data.ConflictError):
        state.book("user01", "P-1042", slot, "again", TODAY)
    # Another participant has an independent sandbox.
    assert state.book("user02", "P-1042", slot, "Heart failure review", TODAY)["status"] == "booked"
    # A booked slot disappears from that participant's list only.
    assert slot not in [s["slot_id"] for s in state.list_slots("user01", "cardiology", 7, TODAY)]
    assert slot in [s["slot_id"] for s in state.list_slots("user03", "cardiology", 7, TODAY)]
    with pytest.raises(data.NotFoundError):
        state.book("user01", "P-1042", "SLOT-NOPE-999", "x", TODAY)


def test_referral_sla():
    state = data.CareToolsState()
    urgent = state.create_referral("u", "P-2077", "pulmonology", "urgent", "Pulmonary rehab", TODAY)
    routine = state.create_referral("u", "P-2077", "pulmonology", "routine", "Pulmonary rehab", TODAY)
    assert urgent["sla_days"] == 2 and routine["sla_days"] == 14
    assert urgent["status"] == "created" and urgent["referral_id"].startswith("REF-")
    assert state.create_referral("u", "P-4203", "physiotherapy", "routine", "Rehab", TODAY)["sla_days"] == 7
    with pytest.raises(ValueError):
        state.create_referral("u", "P-2077", "dermatology", "routine", "x", TODAY)


def test_interaction_rules_from_contract():
    result = data.check_medication_interactions(["Lisinopril", "spironolactone", "furosemide"])
    assert result["disclaimer"] == "Synthetic rule set for training. Not clinical guidance."
    high = [i for i in result["interactions"] if set(i["pair"]) == {"spironolactone", "lisinopril"}]
    assert high and high[0]["severity"] == "high"
    assert data.check_medication_interactions(["omeprazole", "warfarin"])["interactions"][0]["severity"] == "moderate"
    moderate = data.check_medication_interactions(["prednisolone", "insulin glargine"])["interactions"]
    assert moderate[0]["severity"] == "moderate"
    assert data.check_medication_interactions(["metformin"])["interactions"] == []


@pytest.mark.parametrize("payer, code, required", [
    ("Northwind Health Plan", "CARD-ECHO", False),
    ("Northwind Health Plan", "CARD-MRI", True),
    ("Contoso Care Insurance", "PULM-REHAB", True),
    ("Fabrikam Mutual Assurance", "ENDO-CGM", True),
    ("nhp", "card-mri", True),
])
def test_prior_auth_examples_from_contract(payer, code, required):
    result = data.check_prior_auth(payer, code)
    assert result["prior_auth_required"] is required
    assert result["policy_ref"].startswith("PA-")


def test_prior_auth_unknown_inputs():
    with pytest.raises(data.NotFoundError):
        data.check_prior_auth("Acme Insurance", "CARD-ECHO")
    default = data.check_prior_auth("CCI", "XYZ-123")
    assert default["prior_auth_required"] is True and default["policy_ref"] == "PA-GEN-DEFAULT"
