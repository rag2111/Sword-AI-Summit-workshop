---
doc_id: REF-001
title: Specialist Referral Policy
organisation: Lakeside Regional Health Network (fictional)
version: 4.1
effective_date: 2026-01-01
owner: Care Coordination Office
classification: SYNTHETIC TRAINING CONTENT
---

# Specialist Referral Policy (REF-001)

> **Fictional training document.** Synthetic content for a workshop. Not clinical guidance.

## REF-1 Purpose

REF-1.1 Defines how referrals from inpatient wards to specialist and community services are
created, prioritised and tracked.

## REF-2 Who may create a referral

REF-2.1 Referrals are requested by the treating clinician. A care coordinator (or a digital
assistant acting for the coordinator) may **create the referral record** once the clinical request
exists in the care plan (for example "pulmonary rehab referral" in `required_follow_ups`).

REF-2.2 A digital assistant must not invent a clinical reason. The referral reason is copied from
the care plan or provided by the coordinator.

## REF-3 Urgency levels

| Urgency | When to use | SLA (days until first contact) |
|---|---|---|
| `urgent` | Clinician marked the request urgent, or a safety trigger applies | **2** (all specialties) |
| `routine` | All other referrals | see REF-4 table |

REF-3.1 A coordinator may never downgrade an `urgent` request to `routine`.

## REF-4 Routine referral SLAs by specialty

| Specialty | Routine SLA (days) |
|---|---|
| cardiology | 7 |
| pulmonology | 14 |
| endocrinology | 14 |
| primary-care | 7 |
| physiotherapy | 7 |

REF-4.1 Specialty names above are the canonical identifiers used by the network's scheduling and
referral systems (`cardiology`, `pulmonology`, `endocrinology`, `primary-care`, `physiotherapy`).

## REF-5 Referral content

REF-5.1 Every referral contains: patient ID, specialty, urgency, reason, and the referring ward.

REF-5.2 The referral system returns a referral ID (format `REF-` followed by digits) and the SLA in
days. The coordinator records both in the discharge summary (DP-001 §DP-7.1).

## REF-6 Tracking and breaches

REF-6.1 If the receiving service cannot meet the SLA, the coordinator escalates to the service
lead (SAFE-001 §SAFE-ESC-05). The SLA is never silently extended.

REF-6.2 Duplicate referrals for the same patient, specialty and reason within 30 days must be
avoided; check existing referrals first.
