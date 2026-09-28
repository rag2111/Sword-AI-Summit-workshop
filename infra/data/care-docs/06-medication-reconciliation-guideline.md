---
doc_id: MED-001
title: Medication Reconciliation Guideline
organisation: Lakeside Regional Health Network (fictional)
version: 3.0
effective_date: 2026-04-01
owner: Pharmacy and Medicines Safety Committee
classification: SYNTHETIC TRAINING CONTENT
---

# Medication Reconciliation Guideline (MED-001)

> **Fictional training document.** The interaction rules below are a **synthetic rule set created
> for training**. They are deliberately simplified and are **not clinical guidance**.

## MED-1 Purpose

MED-1.1 Medication reconciliation compares the medicines a patient took before admission, during
the stay and at discharge, so that discrepancies are resolved before the patient leaves.

## MED-2 Roles

MED-2.1 The pharmacist signs off the reconciliation. The treating clinician decides on any change.

MED-2.2 Care coordinators and digital assistants may **run the interaction check tool and report
the flags**. They must never recommend starting, stopping or changing a medicine or a dose
(SAFE-001 §SAFE-NEVER-02).

## MED-3 Process

MED-3.1 Collect the medication list from the care plan.

MED-3.2 Run the network's interaction check (`check_medication_interactions`).

MED-3.3 Report every flag with its severity and note, and route `high` flags to the pharmacist
the same day.

MED-3.4 Record "reconciliation pending pharmacist review" until sign-off.

## MED-4 Synthetic interaction rule set (training only)

| Rule ID | Medicine A | Medicine B | Severity | Training note |
|---|---|---|---|---|
| MED-R01 | spironolactone | lisinopril | high | Fictional rule: combined use flagged for potassium (hyperkalaemia) risk; pharmacist review required. |
| MED-R02 | warfarin | omeprazole | moderate | Fictional rule: flagged for possible change in anticoagulant effect; INR monitoring reminder. |
| MED-R03 | prednisolone | insulin glargine | moderate | Fictional rule: steroid course may raise glucose; glucose monitoring reminder. |
| MED-R04 | sacubitril/valsartan | lisinopril | high | Fictional rule: combination flagged as not to be co-prescribed; pharmacist review required. |
| MED-R05 | metoprolol | salbutamol | moderate | Fictional rule: beta-blocker with bronchodilator flagged for review of effectiveness. |
| MED-R06 | furosemide | prednisolone | low | Fictional rule: flagged for potassium monitoring. |
| MED-R07 | warfarin | paracetamol | low | Fictional rule: regular use flagged for INR monitoring reminder. |

MED-4.1 Every result of the interaction check carries this disclaimer:
"Synthetic rule set for training. Not clinical guidance."

MED-4.2 "No flags" does **not** mean "safe". It means no rule in this synthetic set matched.

## MED-5 Reporting format

MED-5.1 Report flags as: pair, severity, note, and the rule ID where known, followed by the
disclaimer. Do not paraphrase a `high` flag as a lower severity.
