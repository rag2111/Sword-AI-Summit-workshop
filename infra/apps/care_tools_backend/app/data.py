"""Synthetic data and business rules for the mock clinical tools.

Everything here is FICTIONAL and exists only to exercise a workshop agent. The module is pure Python
(no web framework imports) so the rules can be unit-tested without FastAPI.

The data mirrors docs/CONTRACT.md section 3 and the knowledge documents in infra/data/care-docs/
(payers, procedure codes, SLAs, clinicians). Tests enforce that consistency.
"""

from __future__ import annotations

import itertools
import random
import threading
import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta

DISCLAIMER = (
    "Training use only. This workshop uses synthetic, fictional data. The Care Coordination Agent "
    "is not a medical device and does not provide clinical advice, diagnosis or treatment decisions."
)
INTERACTION_DISCLAIMER = "Synthetic rule set for training. Not clinical guidance."

SPECIALTIES = ("cardiology", "pulmonology", "endocrinology", "primary-care", "physiotherapy")
SLOT_PREFIX = {
    "cardiology": "CARD",
    "pulmonology": "PULM",
    "endocrinology": "ENDO",
    "primary-care": "PRIM",
    "physiotherapy": "PHYS",
}

# Clinicians match infra/data/care-docs/10-provider-directory.md (DIR-001).
CLINICIANS: dict[str, list[tuple[str, str]]] = {
    "cardiology": [
        ("Dr. Amara Lindqvist", "Lakeside Central Hospital, Building C, Level 2"),
        ("Dr. Tomasz Reyes", "Northshore Campus, Outpatients 1"),
    ],
    "pulmonology": [
        ("Dr. Ingrid Havel", "Lakeside Central Hospital, Building B, Level 1"),
        ("Dr. Kwame Mensah", "Northshore Campus, Outpatients 2"),
    ],
    "endocrinology": [
        ("Dr. Priya Raman", "Westbrook Clinic, Suite 3"),
        ("Dr. Lucas Ferreira", "Lakeside Central Hospital, Building D, Level 3"),
    ],
    "primary-care": [
        ("Dr. Hannah Olsen", "Harbourview Family Practice, Room 4"),
        ("Dr. Mateo Silva", "Eastgate Health Centre, Room 12"),
    ],
    "physiotherapy": [
        ("Noor Haddad, PT", "Lakeside Central Hospital, Building A, Ground Floor"),
        ("Oskar Berg, PT", "Westbrook Clinic, Gym 1"),
    ],
}

# Referral SLAs match REF-001 §REF-3 and §REF-4.
URGENT_SLA_DAYS = 2
ROUTINE_SLA_DAYS = {
    "cardiology": 7,
    "pulmonology": 14,
    "endocrinology": 14,
    "primary-care": 7,
    "physiotherapy": 7,
}

# Payers match PA-001 §PA-2.
PAYERS = {
    "NHP": "Northwind Health Plan",
    "CCI": "Contoso Care Insurance",
    "FMA": "Fabrikam Mutual Assurance",
}

# Prior-authorization matrix matches PA-001 §PA-3 exactly (True = PA required).
PROCEDURES = {
    "CARD-ECHO": "Transthoracic echocardiogram",
    "CARD-MRI": "Cardiac MRI",
    "CARD-HOLTER": "48-hour Holter monitor",
    "PULM-REHAB": "Pulmonary rehabilitation programme",
    "PULM-PFT": "Pulmonary function test",
    "ENDO-CGM": "Continuous glucose monitor",
    "ENDO-PUMP": "Insulin pump",
    "PHYS-HOME": "Home physiotherapy (6 sessions)",
    "HOME-O2": "Home oxygen therapy",
}
PRIOR_AUTH_MATRIX: dict[str, dict[str, bool]] = {
    "CARD-ECHO": {"NHP": False, "CCI": False, "FMA": True},
    "CARD-MRI": {"NHP": True, "CCI": True, "FMA": True},
    "CARD-HOLTER": {"NHP": False, "CCI": False, "FMA": False},
    "PULM-REHAB": {"NHP": True, "CCI": True, "FMA": True},
    "PULM-PFT": {"NHP": False, "CCI": False, "FMA": False},
    "ENDO-CGM": {"NHP": True, "CCI": False, "FMA": True},
    "ENDO-PUMP": {"NHP": True, "CCI": True, "FMA": True},
    "PHYS-HOME": {"NHP": False, "CCI": True, "FMA": False},
    "HOME-O2": {"NHP": True, "CCI": True, "FMA": True},
}
PRIOR_AUTH_NOTES: dict[tuple[str, str], str] = {
    ("NHP", "CARD-ECHO"): "No PA when ordered by a cardiologist for heart failure follow-up (PA-001 §PA-4.1).",
    ("NHP", "CARD-MRI"): "Attach the most recent echocardiogram report (PA-001 §PA-4.2).",
    ("CCI", "PULM-REHAB"): "Include the latest spirometry result (PA-001 §PA-5.1).",
    ("CCI", "PHYS-HOME"): "PA needed for more than two sessions (PA-001 §PA-5.2).",
    ("FMA", "ENDO-CGM"): "Include a recent HbA1c result (PA-001 §PA-6.1).",
    ("FMA", "CARD-ECHO"): "Fabrikam requires PA for all cardiac imaging (PA-001 §PA-6.2).",
}
TURNAROUND_DAYS = {"NHP": 3, "CCI": 5, "FMA": 2}

# Synthetic interaction rules match MED-001 §MED-4 (training only, NOT clinical guidance).
INTERACTION_RULES: list[tuple[str, str, str, str, str]] = [
    ("MED-R01", "spironolactone", "lisinopril", "high",
     "Fictional rule: combined use flagged for potassium (hyperkalaemia) risk; pharmacist review required."),
    ("MED-R02", "warfarin", "omeprazole", "moderate",
     "Fictional rule: flagged for possible change in anticoagulant effect; INR monitoring reminder."),
    ("MED-R03", "prednisolone", "insulin glargine", "moderate",
     "Fictional rule: steroid course may raise glucose; glucose monitoring reminder."),
    ("MED-R04", "sacubitril/valsartan", "lisinopril", "high",
     "Fictional rule: combination flagged as not to be co-prescribed; pharmacist review required."),
    ("MED-R05", "metoprolol", "salbutamol", "moderate",
     "Fictional rule: beta-blocker with bronchodilator flagged for review of effectiveness."),
    ("MED-R06", "furosemide", "prednisolone", "low",
     "Fictional rule: flagged for potassium monitoring."),
    ("MED-R07", "warfarin", "paracetamol", "low",
     "Fictional rule: regular use flagged for INR monitoring reminder."),
]
_MED_ALIASES = {"sacubitril-valsartan": "sacubitril/valsartan", "sacubitril valsartan": "sacubitril/valsartan",
                "glargine": "insulin glargine", "albuterol": "salbutamol", "acetaminophen": "paracetamol"}


class NotFoundError(Exception):
    """Maps to HTTP 404."""


class ConflictError(Exception):
    """Maps to HTTP 409."""


def _med(name: str, dose: str, frequency: str) -> dict[str, str]:
    return {"name": name, "dose": dose, "frequency": frequency}


def _follow_up(kind: str, specialty: str, within_days: int, reason: str, policy_ref: str,
               procedure_code: str | None = None) -> dict:
    item = {"kind": kind, "specialty": specialty, "within_days_of_discharge": within_days,
            "reason": reason, "policy_ref": policy_ref}
    if procedure_code:
        item["procedure_code"] = procedure_code
    return item


# Synthetic patients from docs/CONTRACT.md §3. `discharge_offset_days` is relative to "today".
PATIENTS: dict[str, dict] = {
    "P-1042": {
        "patient_id": "P-1042", "display_name": "Jordan Ellis", "age": 68,
        "primary_condition": "Heart failure (HFrEF)", "ward": "Cardiology 4B", "discharge_status": "pending",
        "care_pathway": "CP-HF-001", "payer": "Northwind Health Plan", "discharge_offset_days": 1,
        "medications": [_med("furosemide", "40 mg", "once daily"), _med("lisinopril", "10 mg", "once daily"),
                        _med("spironolactone", "25 mg", "once daily"), _med("metoprolol", "47.5 mg", "once daily")],
        "pending_tasks": [
            "Book cardiology follow-up within 7 days of discharge (FU-001 §FU-3)",
            "Book primary care review within 14 days of discharge (FU-001 §FU-3)",
            "Medication reconciliation: pharmacist sign-off pending (MED-001 §MED-3)",
            "Arrange daily-weight diary and scales (CP-HF-001 §HF-2.2)",
        ],
        "required_follow_ups": [
            _follow_up("appointment", "cardiology", 7, "Heart failure post-discharge review", "FU-001 §FU-3"),
            _follow_up("appointment", "primary-care", 14, "Primary care review after heart failure admission",
                       "FU-001 §FU-3"),
        ],
    },
    "P-2077": {
        "patient_id": "P-2077", "display_name": "Sam Okafor", "age": 72,
        "primary_condition": "COPD exacerbation", "ward": "Respiratory 2A", "discharge_status": "pending",
        "care_pathway": "CP-COPD-001", "payer": "Contoso Care Insurance", "discharge_offset_days": 2,
        "medications": [_med("tiotropium", "18 mcg inhaled", "once daily"),
                        _med("prednisolone", "30 mg", "once daily (5-day course)"),
                        _med("salbutamol", "100 mcg inhaled", "as needed")],
        "pending_tasks": [
            "Book pulmonology follow-up within 14 days of discharge (FU-001 §FU-3)",
            "Create pulmonary rehabilitation referral before discharge (CP-COPD-001 §COPD-4)",
            "Check prior authorization for PULM-REHAB with Contoso Care Insurance (PA-001 §PA-3)",
            "Record steroid course end date (CP-COPD-001 §COPD-2.2)",
        ],
        "required_follow_ups": [
            _follow_up("appointment", "pulmonology", 14, "COPD exacerbation follow-up", "FU-001 §FU-3"),
            _follow_up("referral", "pulmonology", 28, "Pulmonary rehabilitation programme",
                       "CP-COPD-001 §COPD-4", procedure_code="PULM-REHAB"),
        ],
    },
    "P-3150": {
        "patient_id": "P-3150", "display_name": "Riley Chen", "age": 55,
        "primary_condition": "Type 2 diabetes with hyperglycaemia episode", "ward": "Endocrinology 3C",
        "discharge_status": "pending", "care_pathway": "CP-DM2-001", "payer": "Fabrikam Mutual Assurance",
        "discharge_offset_days": 2,
        "medications": [_med("metformin", "1 g", "twice daily"),
                        _med("insulin glargine", "18 units", "once daily at bedtime"),
                        _med("atorvastatin", "20 mg", "once daily")],
        "pending_tasks": [
            "Book endocrinology follow-up within 14 days of discharge (FU-001 §FU-3)",
            "Check prior authorization for ENDO-CGM with Fabrikam Mutual Assurance (PA-001 §PA-3)",
            "Diabetes specialist nurse education session (CP-DM2-001 §DM2-2.1)",
        ],
        "required_follow_ups": [
            _follow_up("appointment", "endocrinology", 14, "Diabetes review after hyperglycaemia admission",
                       "FU-001 §FU-3", procedure_code="ENDO-CGM"),
            _follow_up("appointment", "primary-care", 14, "Primary care review", "FU-001 §FU-3"),
        ],
    },
    "P-4203": {
        "patient_id": "P-4203", "display_name": "Alex Moreno", "age": 81,
        "primary_condition": "Hip fracture, post-surgery", "ward": "Orthopaedics 5A", "discharge_status": "pending",
        "care_pathway": "LRHN-DP-001 §DP-6", "payer": "Northwind Health Plan", "discharge_offset_days": 3,
        "medications": [_med("warfarin", "3 mg", "once daily (dose per INR)"),
                        _med("paracetamol", "1 g", "up to four times daily"),
                        _med("omeprazole", "20 mg", "once daily")],
        "pending_tasks": [
            "Create physiotherapy referral; first session within 7 days of discharge (DP-001 §DP-6.1)",
            "Book primary care review within 7 days of discharge, including INR check (DP-001 §DP-5.3, §DP-6.2)",
            "Document falls-risk assessment (DP-001 §DP-6.3)",
        ],
        "required_follow_ups": [
            _follow_up("referral", "physiotherapy", 7, "Post-operative rehabilitation after hip fracture",
                       "LRHN-DP-001 §DP-6.1"),
            _follow_up("appointment", "primary-care", 7, "Primary care review and INR check",
                       "LRHN-DP-001 §DP-6.2"),
        ],
    },
    "P-5318": {
        "patient_id": "P-5318", "display_name": "Taylor Brooks", "age": 47,
        "primary_condition": "Heart failure, new diagnosis", "ward": "Cardiology 4B",
        "discharge_status": "not-started", "care_pathway": "CP-HF-001", "payer": "Fabrikam Mutual Assurance",
        "discharge_offset_days": 5,
        "medications": [_med("sacubitril/valsartan", "24/26 mg", "twice daily"),
                        _med("bisoprolol", "1.25 mg", "once daily")],
        "pending_tasks": [
            "Start discharge planning (day-one rule, DP-001 §DP-3.1)",
            "Book cardiology follow-up within 7 days of discharge (FU-001 §FU-3)",
            "Check prior authorization for CARD-ECHO with Fabrikam Mutual Assurance (PA-001 §PA-3)",
        ],
        "required_follow_ups": [
            _follow_up("appointment", "cardiology", 7, "New heart failure diagnosis review", "FU-001 §FU-3",
                       procedure_code="CARD-ECHO"),
        ],
    },
}

_SEARCH_FIELDS = ("patient_id", "display_name", "age", "primary_condition", "ward", "discharge_status")


def search_patients(query: str) -> list[dict]:
    """Case-insensitive match on patient ID or any part of the display name."""
    q = query.strip().lower()
    if not q:
        return []
    return [
        {k: p[k] for k in _SEARCH_FIELDS}
        for p in PATIENTS.values()
        if q in p["patient_id"].lower() or q in p["display_name"].lower()
    ]


def get_care_plan(patient_id: str, today: date) -> dict:
    p = PATIENTS.get(patient_id.strip().upper())
    if p is None:
        raise NotFoundError(f"Patient '{patient_id}' not found.")
    return {
        "patient_id": p["patient_id"],
        "condition": p["primary_condition"],
        "care_pathway": p["care_pathway"],
        "discharge_readiness": p["discharge_status"],
        "expected_discharge_date": (today + timedelta(days=p["discharge_offset_days"])).isoformat(),
        "pending_tasks": list(p["pending_tasks"]),
        "medications": [dict(m) for m in p["medications"]],
        "payer": p["payer"],
        "required_follow_ups": [dict(f) for f in p["required_follow_ups"]],
        "disclaimer": DISCLAIMER,
    }


def generate_slots(today: date) -> list[dict]:
    """Deterministic appointment slots relative to `today` (fixed seed, stable slot IDs).

    Cardiology always has at least two slots within 7 days (CONTRACT §3), so the Lab 2 task
    "book a cardiology follow-up within 7 days" is always solvable.
    """
    rng = random.Random(1042)
    hours, minutes = (8, 9, 10, 11, 13, 14, 15, 16), (0, 30)
    slots: list[dict] = []
    for specialty in SPECIALTIES:
        fixed = [(2, 9, 30), (5, 14, 0)] if specialty == "cardiology" else [(3, 10, 0)]
        entries = list(fixed)
        while len(entries) < 10:
            candidate = (rng.randint(1, 28), rng.choice(hours), rng.choice(minutes))
            if candidate not in entries:
                entries.append(candidate)
        entries.sort()
        clinicians = CLINICIANS[specialty]
        for index, (day, hour, minute) in enumerate(entries, start=1):
            clinician, location = clinicians[(index - 1) % len(clinicians)]
            start = datetime.combine(today + timedelta(days=day), time(hour, minute), tzinfo=UTC)
            slots.append({
                "slot_id": f"SLOT-{SLOT_PREFIX[specialty]}-{index:03d}",
                "specialty": specialty,
                "clinician": clinician,
                "location": location,
                "start": start.isoformat().replace("+00:00", "Z"),
            })
    return slots


def normalise_specialty(specialty: str) -> str:
    s = specialty.strip().lower().replace("_", "-").replace(" ", "-")
    if s == "primarycare":
        s = "primary-care"
    if s not in SPECIALTIES:
        raise ValueError(f"Unknown specialty '{specialty}'. Use one of: {', '.join(SPECIALTIES)}.")
    return s


def check_medication_interactions(medications: list[str]) -> dict:
    normalised = []
    for m in medications:
        name = " ".join(m.strip().lower().split())
        normalised.append(_MED_ALIASES.get(name, name))
    present = set(normalised)
    interactions = [
        {"pair": [a, b], "severity": severity, "note": note, "rule_id": rule_id}
        for rule_id, a, b, severity, note in INTERACTION_RULES
        if a in present and b in present
    ]
    return {"checked": sorted(present), "interactions": interactions, "disclaimer": INTERACTION_DISCLAIMER}


def resolve_payer(payer: str) -> str:
    """Accept the payer's full name or its short code (case-insensitive); return the short code."""
    key = payer.strip().lower()
    for code, name in PAYERS.items():
        if key in (code.lower(), name.lower()):
            return code
    raise NotFoundError(f"Unknown payer '{payer}'. Known payers: {', '.join(PAYERS.values())}.")


def check_prior_auth(payer: str, procedure_code: str) -> dict:
    code = resolve_payer(payer)
    proc = procedure_code.strip().upper()
    if proc not in PRIOR_AUTH_MATRIX:
        return {
            "payer": PAYERS[code], "procedure_code": proc, "prior_auth_required": True,
            "policy_ref": "PA-GEN-DEFAULT",
            "notes": "Procedure code not on the payer matrix: treat as requiring prior authorization and "
                     "confirm with Payer Relations (PA-001 §PA-3.2).",
        }
    required = PRIOR_AUTH_MATRIX[proc][code]
    note = PRIOR_AUTH_NOTES.get((code, proc))
    if note is None:
        note = (f"Submit a PA request before scheduling; typical decision within {TURNAROUND_DAYS[code]} "
                "business days." if required else "Schedule directly; no PA request needed.")
    return {
        "payer": PAYERS[code], "procedure_code": proc, "procedure": PROCEDURES[proc],
        "prior_auth_required": required, "policy_ref": f"PA-{code}-{proc}", "notes": note,
    }


@dataclass
class CareToolsState:
    """In-memory, per-participant state for bookings and referrals.

    Bookings are isolated per participant (APIM sets `x-participant-id` from the subscription), so
    30 participants can all book "the first cardiology slot" without colliding, while double
    booking within one participant's sandbox still returns 409.
    """

    max_items_per_participant: int = 200
    _bookings: dict[str, dict[str, dict]] = field(default_factory=dict)
    _referrals: dict[str, list[dict]] = field(default_factory=dict)
    _referral_ids: itertools.count = field(default_factory=lambda: itertools.count(100001))
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def list_slots(self, participant: str, specialty: str, within_days: int, today: date) -> list[dict]:
        spec = normalise_specialty(specialty)
        booked = self._bookings.get(participant, {})
        horizon = today + timedelta(days=within_days)
        return [
            s for s in generate_slots(today)
            if s["specialty"] == spec and s["slot_id"] not in booked
            and today < date.fromisoformat(s["start"][:10]) <= horizon
        ]

    def book(self, participant: str, patient_id: str, slot_id: str, reason: str, today: date) -> dict:
        pid = patient_id.strip().upper()
        if pid not in PATIENTS:
            raise NotFoundError(f"Patient '{patient_id}' not found.")
        slot = next((s for s in generate_slots(today) if s["slot_id"] == slot_id.strip().upper()), None)
        if slot is None:
            raise NotFoundError(f"Slot '{slot_id}' not found.")
        with self._lock:
            booked = self._bookings.setdefault(participant, {})
            if slot["slot_id"] in booked:
                raise ConflictError(f"Slot '{slot['slot_id']}' is already booked. Choose another slot.")
            if len(booked) >= self.max_items_per_participant:
                raise ConflictError("Booking limit for this participant reached.")
            appointment = {
                "appointment_id": "APT-" + uuid.uuid5(uuid.NAMESPACE_URL, f"{participant}/{slot['slot_id']}").hex[:8].upper(),
                "status": "booked", "patient_id": pid, "reason": reason, **slot,
            }
            booked[slot["slot_id"]] = appointment
        return appointment

    def create_referral(self, participant: str, patient_id: str, specialty: str, urgency: str,
                        reason: str, today: date) -> dict:
        pid = patient_id.strip().upper()
        if pid not in PATIENTS:
            raise NotFoundError(f"Patient '{patient_id}' not found.")
        spec = normalise_specialty(specialty)
        if urgency not in ("routine", "urgent"):
            raise ValueError("urgency must be 'routine' or 'urgent'.")
        sla_days = URGENT_SLA_DAYS if urgency == "urgent" else ROUTINE_SLA_DAYS[spec]
        with self._lock:
            items = self._referrals.setdefault(participant, [])
            if len(items) >= self.max_items_per_participant:
                raise ConflictError("Referral limit for this participant reached.")
            referral = {
                "referral_id": f"REF-{next(self._referral_ids)}", "status": "created", "patient_id": pid,
                "specialty": spec, "urgency": urgency, "reason": reason, "sla_days": sla_days,
                "first_contact_due_by": (today + timedelta(days=sla_days)).isoformat(),
                "policy_ref": "REF-001 §REF-3" if urgency == "urgent" else "REF-001 §REF-4",
            }
            items.append(referral)
        return referral
