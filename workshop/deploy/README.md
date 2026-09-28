# deploy/ — presenter-only production runtime demo (optional)

> **Training use only.** This workshop uses synthetic, fictional data. The Care Coordination Agent is not a medical device and does not provide clinical advice, diagnosis or treatment decisions.

**Participants: you can skip this folder.** It needs an admin Azure identity (`az login`, AcrPush, Foundry
Project Manager), which the participant path deliberately never requires. It is listed as an exception in
`docs/apim-exceptions/workshop.md`.

| File | Purpose |
|---|---|
| `Dockerfile` | Image with `src/care_agent`, the version registry and `app.py` (non-root, port 8088) |
| `requirements.txt` | Image dependencies; pins `azure-ai-projects==2.6.1` because `agent-framework-foundry` requires `<2.7.0` |
| `app.py` | Serves the same `build_agent()` with `ResponsesHostServer` (`agent-framework-foundry-hosting`, **preview**) |
| `deploy_hosted_agent.py` | Builds with `az acr build` and creates a **Foundry hosted agent** version (**preview**) |

## Run locally (5 minutes before the session)

```bash
cd workshop
docker build -f deploy/Dockerfile -t care-coordination-agent:1 .
docker run --rm -p 8088:8088 --env-file .env care-coordination-agent:1
curl -s -X POST http://localhost:8088/responses -H "Content-Type: application/json" \
  -d '{"input": "Plan discharge for patient P-1042 and book a cardiology follow-up within 7 days."}'
```

## Foundry hosted agent (preview)

```bash
python deploy/deploy_hosted_agent.py \
  --project-endpoint https://<foundry>.services.ai.azure.com/api/projects/<project> \
  --acr <registry> --tag 1 --apim-base-url https://<apim>.azure-api.net --key-secret-ref <secret-reference>
```

The hosted agent keeps calling models and tools **through APIM** with a presenter subscription key held as a
secret — so the gateway, token limits and traces are identical to the laptop version. Store the key as a
Foundry/Container Apps secret; never pass the raw key on the command line in a recorded demo.

## Fallback: Azure Container Apps (GA)

```bash
az containerapp up --name care-agent-demo --resource-group <rg> --image <acr>.azurecr.io/care-coordination-agent:1 \
  --ingress external --target-port 8088 \
  --env-vars APIM_BASE_URL=https://<apim>.azure-api.net PARTICIPANT_ID=presenter-hosted APIM_SUBSCRIPTION_KEY=secretref:apim-key
```

Set the `apim-key` secret first (`az containerapp secret set ...`). Put Container Apps behind APIM as well if the
endpoint is shared with anyone.
