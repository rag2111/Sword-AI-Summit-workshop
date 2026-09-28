# Full repository tree

```
care-coordination-workshop/
├── .devcontainer/
│   └── workshop/
│       └── devcontainer.json
├── .gitignore
├── README.md
├── docs/
│   ├── APIM_EXCEPTIONS.md
│   ├── CONTRACT.md
│   ├── PREVIEW_FEATURES.md
│   ├── apim-exceptions/
│   │   ├── infra.md
│   │   ├── presenter.md
│   │   └── workshop.md
│   └── preview/
│       ├── infra.md
│       ├── presenter.md
│       └── workshop.md
├── infra/
│   ├── .gitignore
│   ├── README.md
│   ├── apps/
│   │   ├── a2a_adapter/
│   │   │   ├── Dockerfile
│   │   │   ├── app.py
│   │   │   └── pyproject.toml
│   │   └── care_tools_backend/
│   │       ├── .dockerignore
│   │       ├── Dockerfile
│   │       ├── app/
│   │       │   ├── __init__.py
│   │       │   ├── data.py
│   │       │   ├── main.py
│   │       │   └── openapi.json
│   │       └── pyproject.toml
│   ├── data/
│   │   └── care-docs/
│   │       ├── 01-discharge-planning-protocol.md
│   │       ├── 02-care-pathway-heart-failure.md
│   │       ├── 03-care-pathway-copd.md
│   │       ├── 04-care-pathway-type2-diabetes.md
│   │       ├── 05-specialist-referral-policy.md
│   │       ├── 06-medication-reconciliation-guideline.md
│   │       ├── 07-prior-authorization-rules.md
│   │       ├── 08-post-discharge-follow-up-sla.md
│   │       ├── 09-escalation-and-safety-policy.md
│   │       ├── 10-provider-directory.md
│   │       ├── 11-care-coordinator-handbook.md
│   │       └── 12-glossary.md
│   ├── main.tf
│   ├── modules/
│   │   ├── apim/
│   │   │   ├── main.tf
│   │   │   ├── outputs.tf
│   │   │   ├── policies/
│   │   │   │   └── global.xml
│   │   │   ├── variables.tf
│   │   │   └── versions.tf
│   │   ├── apim_apis/
│   │   │   ├── main.tf
│   │   │   ├── outputs.tf
│   │   │   ├── policies/
│   │   │   │   ├── a2a-card-operation.xml
│   │   │   │   ├── a2a-jsonrpc-operation.xml
│   │   │   │   ├── a2a.xml
│   │   │   │   ├── care-tools-api.xml
│   │   │   │   ├── care-tools-mcp.xml
│   │   │   │   ├── foundry.xml
│   │   │   │   ├── openai.xml
│   │   │   │   ├── telemetry-config.xml
│   │   │   │   └── telemetry.xml
│   │   │   ├── variables.tf
│   │   │   └── versions.tf
│   │   ├── container_apps/
│   │   │   ├── main.tf
│   │   │   ├── outputs.tf
│   │   │   ├── variables.tf
│   │   │   └── versions.tf
│   │   ├── foundry/
│   │   │   ├── main.tf
│   │   │   ├── outputs.tf
│   │   │   ├── variables.tf
│   │   │   └── versions.tf
│   │   ├── monitoring/
│   │   │   ├── main.tf
│   │   │   ├── outputs.tf
│   │   │   ├── variables.tf
│   │   │   └── versions.tf
│   │   ├── participants/
│   │   │   ├── main.tf
│   │   │   ├── outputs.tf
│   │   │   ├── participant.env.tftpl
│   │   │   ├── variables.tf
│   │   │   └── versions.tf
│   │   ├── search_storage/
│   │   │   ├── main.tf
│   │   │   ├── outputs.tf
│   │   │   ├── variables.tf
│   │   │   └── versions.tf
│   │   └── workbook/
│   │       ├── main.tf
│   │       ├── outputs.tf
│   │       ├── variables.tf
│   │       ├── versions.tf
│   │       └── workbook.json
│   ├── outputs.tf
│   ├── post_deploy.tf
│   ├── pyproject.toml
│   ├── rbac.tf
│   ├── scripts/
│   │   ├── create_base_agent.py
│   │   ├── seed_knowledge.py
│   │   └── smoke_test.py
│   ├── terraform.tfvars.example
│   ├── tests/
│   │   ├── _helpers.py
│   │   ├── platform.tftest.hcl
│   │   ├── test_backend_api.py
│   │   ├── test_backend_rules.py
│   │   ├── test_docs_consistency.py
│   │   ├── test_openapi_contract.py
│   │   ├── test_participant_naming.py
│   │   └── test_policies.py
│   ├── variables.tf
│   └── versions.tf
├── presenter/
│   ├── README.md
│   ├── fallback/
│   │   └── README.md
│   ├── live-demo-lab6.md
│   ├── preflight-checklist.md
│   ├── run-of-show.md
│   ├── scripts/
│   │   └── validate_kit.py
│   ├── slide-notes.md
│   ├── timing-cards.md
│   └── troubleshooting-faq.md
└── workshop/
    ├── .devcontainer/
    │   ├── README.md
    │   └── devcontainer.json
    ├── .env.example
    ├── .gitignore
    ├── .python-version
    ├── .vscode/
    │   ├── extensions.json
    │   ├── launch.json
    │   ├── settings.json
    │   └── tasks.json
    ├── README.md
    ├── agent_versions/
    │   ├── README.md
    │   └── candidates/
    │       └── .gitkeep
    ├── deploy/
    │   ├── Dockerfile
    │   ├── README.md
    │   ├── app.py
    │   ├── deploy_hosted_agent.py
    │   └── requirements.txt
    ├── docs/
    │   ├── images/
    │   │   ├── lab0-smoke-test.svg
    │   │   ├── lab1-safety-boundaries.svg
    │   │   ├── lab2-tool-orchestration.svg
    │   │   ├── lab3-a2a-citations.svg
    │   │   ├── lab4-local-trace.svg
    │   │   ├── lab4-end-to-end-trace.svg
    │   │   ├── lab5-evaluation-gate.svg
    │   │   ├── lab5-run-comparison.svg
    │   │   └── lab6-improvement-lineage.svg
    │   ├── index.md
    │   ├── javascripts/
    │   │   └── timer.js
    │   ├── lab0.md
    │   ├── lab1.md
    │   ├── lab2.md
    │   ├── lab3.md
    │   ├── lab4.md
    │   ├── lab5.md
    │   ├── lab6.md
    │   ├── reference.md
    │   ├── setup.md
    │   ├── stylesheets/
    │   │   └── extra.css
    │   ├── troubleshooting.md
    │   └── wrap-up.md
    ├── evals/
    │   ├── __init__.py
    │   ├── cloud_eval.py
    │   ├── cost.py
    │   ├── evaluators/
    │   │   ├── __init__.py
    │   │   └── no_clinical_diagnosis.py
    │   ├── golden.jsonl
    │   ├── judge.py
    │   ├── latency.py
    │   ├── out/
    │   │   └── .gitkeep
    │   ├── policy/
    │   │   └── escalation-and-safety-policy.md
    │   ├── redteam_from_policy.py
    │   ├── rubric.yaml
    │   ├── run_evals.py
    │   ├── runs.py
    │   ├── scoring.py
    │   ├── tool_match.py
    │   └── upload_to_foundry.py
    ├── labs/
    │   ├── index.md
    │   ├── lab0.md
    │   ├── lab1.md
    │   ├── lab2.md
    │   ├── lab3.md
    │   ├── lab4.md
    │   ├── lab5.md
    │   ├── lab6.md
    │   ├── reference.md
    │   ├── setup.md
    │   ├── troubleshooting.md
    │   └── wrap-up.md
    ├── loop/
    │   ├── __init__.py
    │   ├── cluster.py
    │   ├── promote.py
    │   ├── propose.py
    │   ├── pull_failures.py
    │   ├── rollback.py
    │   ├── run_loop.py
    │   └── validate.py
    ├── mkdocs.yml
    ├── pyproject.toml
    ├── scripts/
    │   ├── build_checkpoints.py
    │   ├── catchup.py
    │   ├── checkpoints/
    │   │   └── source/
    │   │       └── care_agent/
    │   │           ├── __init__.py
    │   │           ├── a2a_delegate.py
    │   │           ├── agent.py
    │   │           ├── apim_auth.py
    │   │           ├── cli.py
    │   │           ├── config.py
    │   │           ├── devui.py
    │   │           ├── errors.py
    │   │           ├── instructions.py
    │   │           ├── lab2.py
    │   │           ├── lab3.py
    │   │           ├── smoke.py
    │   │           ├── telemetry.py
    │   │           ├── tools_mcp.py
    │   │           ├── ui.py
    │   │           └── versions.py
    │   └── export_labs.py
    ├── solutions/
    │   ├── lab1/
    │   │   ├── __init__.py
    │   │   ├── a2a_delegate.py
    │   │   ├── agent.py
    │   │   ├── apim_auth.py
    │   │   ├── cli.py
    │   │   ├── config.py
    │   │   ├── devui.py
    │   │   ├── errors.py
    │   │   ├── instructions.py
    │   │   ├── lab2.py
    │   │   ├── lab3.py
    │   │   ├── smoke.py
    │   │   ├── telemetry.py
    │   │   ├── tools_mcp.py
    │   │   ├── ui.py
    │   │   └── versions.py
    │   ├── lab2/
    │   │   ├── __init__.py
    │   │   ├── a2a_delegate.py
    │   │   ├── agent.py
    │   │   ├── apim_auth.py
    │   │   ├── cli.py
    │   │   ├── config.py
    │   │   ├── devui.py
    │   │   ├── errors.py
    │   │   ├── instructions.py
    │   │   ├── lab2.py
    │   │   ├── lab3.py
    │   │   ├── smoke.py
    │   │   ├── telemetry.py
    │   │   ├── tools_mcp.py
    │   │   ├── ui.py
    │   │   └── versions.py
    │   ├── lab3/
    │   │   ├── __init__.py
    │   │   ├── a2a_delegate.py
    │   │   ├── agent.py
    │   │   ├── apim_auth.py
    │   │   ├── cli.py
    │   │   ├── config.py
    │   │   ├── devui.py
    │   │   ├── errors.py
    │   │   ├── instructions.py
    │   │   ├── lab2.py
    │   │   ├── lab3.py
    │   │   ├── smoke.py
    │   │   ├── telemetry.py
    │   │   ├── tools_mcp.py
    │   │   ├── ui.py
    │   │   └── versions.py
    │   ├── lab4/
    │   │   ├── __init__.py
    │   │   ├── a2a_delegate.py
    │   │   ├── agent.py
    │   │   ├── apim_auth.py
    │   │   ├── cli.py
    │   │   ├── config.py
    │   │   ├── devui.py
    │   │   ├── errors.py
    │   │   ├── instructions.py
    │   │   ├── lab2.py
    │   │   ├── lab3.py
    │   │   ├── smoke.py
    │   │   ├── telemetry.py
    │   │   ├── tools_mcp.py
    │   │   ├── ui.py
    │   │   └── versions.py
    │   ├── lab5/
    │   │   ├── __init__.py
    │   │   ├── a2a_delegate.py
    │   │   ├── agent.py
    │   │   ├── apim_auth.py
    │   │   ├── cli.py
    │   │   ├── config.py
    │   │   ├── devui.py
    │   │   ├── errors.py
    │   │   ├── instructions.py
    │   │   ├── lab2.py
    │   │   ├── lab3.py
    │   │   ├── smoke.py
    │   │   ├── telemetry.py
    │   │   ├── tools_mcp.py
    │   │   ├── ui.py
    │   │   └── versions.py
    │   └── lab6/
    │       ├── __init__.py
    │       ├── a2a_delegate.py
    │       ├── agent.py
    │       ├── apim_auth.py
    │       ├── cli.py
    │       ├── config.py
    │       ├── devui.py
    │       ├── errors.py
    │       ├── instructions.py
    │       ├── lab2.py
    │       ├── lab3.py
    │       ├── smoke.py
    │       ├── telemetry.py
    │       ├── tools_mcp.py
    │       ├── ui.py
    │       └── versions.py
    ├── src/
    │   └── care_agent/
    │       ├── __init__.py
    │       ├── a2a_delegate.py
    │       ├── agent.py
    │       ├── apim_auth.py
    │       ├── cli.py
    │       ├── config.py
    │       ├── devui.py
    │       ├── errors.py
    │       ├── instructions.py
    │       ├── lab2.py
    │       ├── lab3.py
    │       ├── smoke.py
    │       ├── telemetry.py
    │       ├── tools_mcp.py
    │       ├── ui.py
    │       └── versions.py
    └── tests/
        ├── __init__.py
        ├── conftest.py
        ├── helpers.py
        ├── test_apim_auth.py
        ├── test_catchup_and_solutions.py
        ├── test_config.py
        ├── test_cost_latency.py
        ├── test_golden.py
        ├── test_helpers_misc.py
        ├── test_instructions.py
        ├── test_loop.py
        ├── test_no_clinical_diagnosis.py
        ├── test_redteam.py
        ├── test_registry.py
        ├── test_repo.py
        └── test_scoring.py
```
