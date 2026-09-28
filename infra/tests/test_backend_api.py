"""HTTP-level tests of the mock backend with FastAPI's TestClient (skipped if FastAPI is missing)."""

import json
import os
from datetime import date, timedelta

import pytest

import _helpers

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient  # noqa: E402

os.environ["CARE_TOOLS_TODAY"] = "2026-09-28"
from app import main  # noqa: E402

TODAY = date(2026, 9, 28)
client = TestClient(main.app)


def headers(participant="user01"):
    return {"x-participant-id": participant}


def test_root_shows_disclaimer_and_health():
    body = client.get("/").json()
    assert "not a medical device" in body["disclaimer"]
    assert client.get("/healthz").json() == {"status": "ok"}


def test_openapi_is_the_committed_spec():
    committed = json.loads((_helpers.BACKEND / "app" / "openapi.json").read_text(encoding="utf-8"))
    assert client.get("/openapi.json").json() == committed


def test_search_patient():
    r = client.get("/patients/search", params={"query": "Ellis"})
    assert r.status_code == 200 and r.json()[0]["patient_id"] == "P-1042"
    assert client.get("/patients/search", params={"query": ""}).status_code == 422


def test_get_care_plan():
    r = client.get("/patients/P-1042/care-plan")
    assert r.status_code == 200 and r.json()["payer"] == "Northwind Health Plan"
    assert client.get("/patients/P-0000/care-plan").status_code == 404


def test_p1042_cardiology_slots_within_7_days_exist():
    r = client.get("/slots", params={"specialty": "cardiology", "within_days": 7}, headers=headers("user09"))
    slots = r.json()
    assert r.status_code == 200 and len(slots) >= 2
    assert all(date.fromisoformat(s["start"][:10]) <= TODAY + timedelta(days=7) for s in slots)
    assert client.get("/slots", params={"specialty": "dermatology"}).status_code == 422


def test_book_follow_up_and_409_on_double_booking():
    slot = client.get("/slots", params={"specialty": "cardiology", "within_days": 7}, headers=headers("user10")).json()[0]
    payload = {"patient_id": "P-1042", "slot_id": slot["slot_id"], "reason": "Heart failure post-discharge review"}
    first = client.post("/appointments", json=payload, headers=headers("user10"))
    assert first.status_code == 201 and first.json()["status"] == "booked"
    assert client.post("/appointments", json=payload, headers=headers("user10")).status_code == 409
    assert client.post("/appointments", json=payload, headers=headers("user11")).status_code == 201
    assert client.post("/appointments", json={**payload, "slot_id": "SLOT-X-1"}, headers=headers()).status_code == 404


def test_create_referral():
    r = client.post("/referrals", json={"patient_id": "P-2077", "specialty": "pulmonology", "urgency": "routine",
                                        "reason": "Pulmonary rehabilitation programme"})
    assert r.status_code == 201 and r.json()["sla_days"] == 14 and r.json()["status"] == "created"
    bad = client.post("/referrals", json={"patient_id": "P-2077", "specialty": "pulmonology", "urgency": "asap",
                                          "reason": "x" * 5})
    assert bad.status_code == 422


def test_medication_interactions():
    r = client.post("/medications/interactions", json={"medications": ["spironolactone", "lisinopril"]})
    body = r.json()
    assert r.status_code == 200 and body["interactions"][0]["severity"] == "high"
    assert body["disclaimer"] == "Synthetic rule set for training. Not clinical guidance."
    assert client.post("/medications/interactions", json={"medications": []}).status_code == 422


def test_prior_auth():
    r = client.get("/prior-auth", params={"payer": "Northwind Health Plan", "procedure_code": "CARD-ECHO"})
    assert r.status_code == 200 and r.json()["prior_auth_required"] is False
    r = client.get("/prior-auth", params={"payer": "Northwind Health Plan", "procedure_code": "CARD-MRI"})
    assert r.json()["prior_auth_required"] is True
    assert client.get("/prior-auth", params={"payer": "Nobody", "procedure_code": "CARD-MRI"}).status_code == 404


def test_shared_secret_blocks_direct_calls():
    os.environ["BACKEND_SHARED_SECRET"] = "s3cr3t"
    try:
        assert client.get("/patients/search", params={"query": "Ellis"}).status_code == 403
        ok = client.get("/patients/search", params={"query": "Ellis"}, headers={"x-backend-secret": "s3cr3t"})
        assert ok.status_code == 200
        assert client.get("/healthz").status_code == 200
    finally:
        del os.environ["BACKEND_SHARED_SECRET"]


def test_routes_match_committed_openapi_operation_ids():
    spec = json.loads((_helpers.BACKEND / "app" / "openapi.json").read_text(encoding="utf-8"))
    routes = {(m, r.path): r.operation_id for r in main.app.routes if hasattr(r, "methods") for m in r.methods}
    for path, ops in spec["paths"].items():
        for method, op in ops.items():
            assert routes.get((method.upper(), path)) == op["operationId"], (method, path)
