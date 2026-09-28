# APIM exceptions — presenter kit

Places where the presenter (not participants) steps outside "everything via APIM with a subscription key".

| What | Why | Mitigation |
|---|---|---|
| Optional production deploy (`workshop/deploy/`: image build/push, Foundry hosted agent or Container Apps creation) uses the presenter's **admin Entra identity** | Control-plane operations; the APIM `/foundry` allowlist intentionally blocks agent creation/deployment for participants | Presenter-only, from the presenter machine, least-privilege role scoped to the workshop resource group/project; the deployed agent's runtime traffic (models, MCP tools, A2A, telemetry) still goes via APIM with a dedicated presenter subscription key stored as a secret; demo shows this in traces |
| Invoking the hosted agent directly on its Foundry endpoint (Entra) during the Part B demo | Hosted agent endpoints are Foundry-native | Presenter-only; participants never call it; its outbound calls remain via APIM |
| Portal viewing of traces and evaluation runs (App Insights, Foundry portal Tracing/Evaluations) requires Azure / Foundry portal sign-in | Portals are not proxied by APIM; participants have keys only, no Entra roles | Primary: presenter screen share (Lab 4, Lab 5). Optional: grant participants with tenant accounts temporary read-only access (Reader on the Foundry project, Monitoring/Log Analytics Reader on App Insights), time-boxed and removed after the session. Local artifacts (`evals/out/<run-id>/`, console output) need no portal |
| Preflight verification in portals (App Insights, Foundry, APIM) with admin identity | Needed to confirm traces, eval uploads, token metrics | Read-only actions; performed before the session |
| Temporary live edit of `llm-token-limit` in the APIM portal | Incident response to 429s during Lab 5 | Only if backend TPM has headroom; noted on the timing card; reverted by `terraform apply` from `infra/` after the session |
| Telemetry fallback toggle (`telemetry_require_subscription_key` = false) if `/telemetry` fails for everyone | Keep Lab 4 running | Owned by infra: iKey-filtered, IP rate-limited, body-size capped; switch back after the session |
| Participant keys distributed out-of-band (printed cards / QR / secure share) from `participants.csv` | Keys must reach people before they can use APIM | Never post keys in chat or email the CSV; spare cards tracked; keys revoked or `terraform destroy` right after the session |
