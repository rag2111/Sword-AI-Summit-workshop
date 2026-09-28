---
doc_id: PA-001
title: Prior-Authorization Rules by Payer
organisation: Lakeside Regional Health Network (fictional)
version: 2026.2
effective_date: 2026-07-01
owner: Revenue Cycle and Payer Relations
classification: SYNTHETIC TRAINING CONTENT
---

# Prior-Authorization Rules by Payer (PA-001)

> **Fictional training document.** Northwind Health Plan, Contoso Care Insurance and Fabrikam
> Mutual Assurance are fictional payers. The rules below are synthetic and exist only to exercise
> a workshop agent. They are not real payer policies.

## PA-1 Purpose

PA-1.1 Tells care coordinators which post-discharge procedures need prior authorization (PA)
before they are scheduled, per payer.

PA-1.2 The network's `check_prior_auth_requirement` tool implements exactly the matrix in PA-3.
When the tool and this document disagree, stop and escalate to Payer Relations
(SAFE-001 §SAFE-ESC-06).

## PA-2 Payers and short codes

| Payer | Short code |
|---|---|
| Northwind Health Plan | NHP |
| Contoso Care Insurance | CCI |
| Fabrikam Mutual Assurance | FMA |

## PA-3 Prior-authorization matrix

Legend: **Required** = submit a PA request before scheduling; **Not required** = schedule directly.

| Procedure code | Description | Northwind Health Plan | Contoso Care Insurance | Fabrikam Mutual Assurance |
|---|---|---|---|---|
| CARD-ECHO | Transthoracic echocardiogram | Not required | Not required | Required |
| CARD-MRI | Cardiac MRI | Required | Required | Required |
| CARD-HOLTER | 48-hour Holter monitor | Not required | Not required | Not required |
| PULM-REHAB | Pulmonary rehabilitation programme | Required | Required | Required |
| PULM-PFT | Pulmonary function test | Not required | Not required | Not required |
| ENDO-CGM | Continuous glucose monitor | Required | Not required | Required |
| ENDO-PUMP | Insulin pump | Required | Required | Required |
| PHYS-HOME | Home physiotherapy (6 sessions) | Not required | Required | Not required |
| HOME-O2 | Home oxygen therapy | Required | Required | Required |

PA-3.1 Policy references follow the pattern `PA-<short code>-<procedure code>`, for example
`PA-NHP-CARD-MRI` or `PA-FMA-ENDO-CGM`.

PA-3.2 **Procedure codes not listed** in the matrix are treated as *Required* (conservative
default, policy reference `PA-GEN-DEFAULT`) until Payer Relations confirms otherwise.

## PA-4 Northwind Health Plan (NHP) notes

PA-4.1 Echocardiograms (`CARD-ECHO`) do not need PA when ordered by a cardiologist for heart
failure follow-up.

PA-4.2 Cardiac MRI (`CARD-MRI`) needs PA with the most recent echocardiogram report attached.

PA-4.3 PA decisions are typically returned within 3 business days.

## PA-5 Contoso Care Insurance (CCI) notes

PA-5.1 Pulmonary rehabilitation (`PULM-REHAB`) needs PA; include the latest spirometry result.

PA-5.2 Home physiotherapy (`PHYS-HOME`) needs PA for more than two sessions.

PA-5.3 PA decisions are typically returned within 5 business days.

## PA-6 Fabrikam Mutual Assurance (FMA) notes

PA-6.1 Continuous glucose monitors (`ENDO-CGM`) need PA with a recent HbA1c result.

PA-6.2 Fabrikam requires PA for all cardiac imaging, including `CARD-ECHO`.

PA-6.3 PA decisions are typically returned within 2 business days.

## PA-7 What a digital assistant may do

PA-7.1 Look up whether PA is required and quote the policy reference.

PA-7.2 It must not state that a procedure is "covered" or "approved"; only the payer decides
coverage (SAFE-001 §SAFE-NEVER-06).
