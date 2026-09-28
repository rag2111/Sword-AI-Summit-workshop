"""FastAPI app for the mock clinical tools (synthetic data only).

APIM imports `app/openapi.json` as the REST API `care-tools-api` and exposes the 7 operations as MCP
tools (operationId == tool name). This app serves that same committed spec at /openapi.json so the
contract has exactly one source of truth; tests check that the routes below match it.

Run locally:  uv run uvicorn app.main:app --reload   (from infra/apps/care_tools_backend)
"""

from __future__ import annotations

import hmac
import json
import os
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Annotated, Literal

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from . import data

SPEC_PATH = Path(__file__).with_name("openapi.json")
Specialty = Literal["cardiology", "pulmonology", "endocrinology", "primary-care", "physiotherapy"]
# Paths reachable without the APIM shared secret (health probes and the disclaimer page).
PUBLIC_PATHS = {"/", "/healthz"}

app = FastAPI(title="Care Tools API (synthetic)", version="1.0.0", docs_url=None, redoc_url=None)
app.openapi = lambda: json.loads(SPEC_PATH.read_text(encoding="utf-8"))  # type: ignore[method-assign]
state = data.CareToolsState()


def today() -> date:
    """'Today' in UTC; override with CARE_TOOLS_TODAY=YYYY-MM-DD for reproducible demos/tests."""
    override = os.environ.get("CARE_TOOLS_TODAY")
    return date.fromisoformat(override) if override else datetime.now(UTC).date()


@app.middleware("http")
async def require_gateway_secret(request: Request, call_next):
    """Only APIM knows BACKEND_SHARED_SECRET (APIM named value), so callers cannot bypass the gateway."""
    expected = os.environ.get("BACKEND_SHARED_SECRET", "")
    if expected and request.url.path not in PUBLIC_PATHS:
        provided = request.headers.get("x-backend-secret", "")
        if not hmac.compare_digest(provided.encode(), expected.encode()):
            return JSONResponse(status_code=403, content={"detail": "Call this API through the APIM gateway."})
    return await call_next(request)


@app.exception_handler(data.NotFoundError)
async def _not_found(_: Request, exc: data.NotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(data.ConflictError)
async def _conflict(_: Request, exc: data.ConflictError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(ValueError)
async def _invalid(_: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": str(exc)})


class BookFollowUpRequest(BaseModel):
    patient_id: str = Field(max_length=20)
    slot_id: str = Field(max_length=30)
    reason: str = Field(min_length=3, max_length=300)


class CreateReferralRequest(BaseModel):
    patient_id: str = Field(max_length=20)
    specialty: Specialty
    urgency: Literal["routine", "urgent"]
    reason: str = Field(min_length=3, max_length=300)


class MedicationInteractionRequest(BaseModel):
    medications: list[str] = Field(min_length=1, max_length=20)


# Set by APIM from the caller's subscription (callers cannot spoof it); isolates each participant's bookings.
Participant = Annotated[str, Header(alias="x-participant-id", max_length=64)]


@app.get("/", include_in_schema=False)
def root() -> dict:
    return {
        "service": "care-tools-backend",
        "organisation": "Lakeside Regional Health Network (fictional)",
        "disclaimer": data.DISCLAIMER,
        "usage": "Call the tools through the APIM MCP endpoint /care-tools/mcp with your subscription key.",
    }


@app.get("/healthz", include_in_schema=False)
def healthz() -> dict:
    return {"status": "ok"}


@app.get("/patients/search", operation_id="search_patient")
def search_patient(query: str = Query(min_length=1, max_length=100)) -> list[dict]:
    return data.search_patients(query)


@app.get("/patients/{patient_id}/care-plan", operation_id="get_care_plan")
def get_care_plan(patient_id: str) -> dict:
    return data.get_care_plan(patient_id, today())


@app.get("/slots", operation_id="list_available_slots")
def list_available_slots(
    specialty: Specialty,
    within_days: int = Query(default=14, ge=1, le=60),
    participant: Participant = "anonymous",
) -> list[dict]:
    return state.list_slots(participant, specialty, within_days, today())


@app.post("/appointments", operation_id="book_follow_up", status_code=201)
def book_follow_up(body: BookFollowUpRequest, participant: Participant = "anonymous") -> dict:
    return state.book(participant, body.patient_id, body.slot_id, body.reason, today())


@app.post("/referrals", operation_id="create_referral", status_code=201)
def create_referral(body: CreateReferralRequest, participant: Participant = "anonymous") -> dict:
    return state.create_referral(participant, body.patient_id, body.specialty, body.urgency, body.reason, today())


@app.post("/medications/interactions", operation_id="check_medication_interactions")
def check_medication_interactions(body: MedicationInteractionRequest) -> dict:
    return data.check_medication_interactions(body.medications)


@app.get("/prior-auth", operation_id="check_prior_auth_requirement")
def check_prior_auth_requirement(
    payer: str = Query(max_length=60),
    procedure_code: str = Query(max_length=30),
) -> dict:
    if not payer.strip() or not procedure_code.strip():
        raise HTTPException(status_code=422, detail="payer and procedure_code are required.")
    return data.check_prior_auth(payer, procedure_code)
