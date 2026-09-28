"""PRESENTER-ONLY (PREVIEW): deploy the agent image as a Foundry hosted agent.

Needs an ADMIN Azure identity (`az login`, Foundry Project Manager on the project, AcrPush on the
registry). This is deliberately outside the participant path: participants never need Azure RBAC.
It is listed in docs/apim-exceptions/workshop.md because it talks to Foundry and ACR directly.

Steps
  1. az acr build   -> pushes deploy/Dockerfile as <acr>.azurecr.io/care-coordination-agent:<tag>
  2. agents.create_version(HostedAgentDefinition(...))  (azure-ai-projects 2.x hosted agents, PREVIEW)
Fallbacks
  - `azd ai agent init` + `azd deploy` (documented Foundry hosted-agent workflow), or
  - Azure Container Apps with the same image (see deploy/README.md).

    python deploy/deploy_hosted_agent.py --project-endpoint https://<foundry>.services.ai.azure.com/api/projects/<p> \
        --acr <registry-name> --tag 1 [--skip-build]
"""

from __future__ import annotations

import argparse
import subprocess
import sys

AGENT_NAME = "care-coordination-agent-hosted"


def build_image(acr: str, tag: str) -> str:
    image = f"{acr}.azurecr.io/care-coordination-agent:{tag}"
    subprocess.run(
        ["az", "acr", "build", "--registry", acr, "--image", f"care-coordination-agent:{tag}", "--file", "deploy/Dockerfile", "."],
        check=True,
    )
    return image


def create_hosted_version(project_endpoint: str, image: str, env: dict[str, str]) -> None:
    from azure.ai.projects import AIProjectClient
    from azure.ai.projects.models import ContainerConfiguration, HostedAgentDefinition, ProtocolVersionRecord
    from azure.identity import DefaultAzureCredential

    try:
        container = ContainerConfiguration(image=image, environment_variables=env)
    except TypeError:  # older/newer preview shape: set variables in the portal instead
        container = ContainerConfiguration(image=image)
        print("! environment_variables not supported by this SDK version: set them on the agent in the Foundry portal.")
    with AIProjectClient(endpoint=project_endpoint, credential=DefaultAzureCredential()) as project:
        created = project.agents.create_version(
            agent_name=AGENT_NAME,
            definition=HostedAgentDefinition(
                cpu="1",
                memory="2Gi",
                container_configuration=container,
                protocol_versions=[ProtocolVersionRecord(protocol="responses", version="1.0.0")],
            ),
            description="Care Coordination Agent (training, synthetic data) — hosted demo",
        )
        print(f"✓ Hosted agent {created.name} version {created.version} created. Start it from the Foundry portal.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--project-endpoint", required=True, help="direct Foundry project endpoint (admin path, not APIM)")
    parser.add_argument("--acr", required=True)
    parser.add_argument("--tag", default="1")
    parser.add_argument("--skip-build", action="store_true")
    parser.add_argument("--apim-base-url", default="", help="APIM_BASE_URL for the hosted agent")
    parser.add_argument("--key-secret-ref", default="", help="reference to the presenter APIM key secret (never the key)")
    args = parser.parse_args(argv)
    image = f"{args.acr}.azurecr.io/care-coordination-agent:{args.tag}" if args.skip_build else build_image(args.acr, args.tag)
    env = {"APIM_BASE_URL": args.apim_base_url, "PARTICIPANT_ID": "presenter-hosted", "APIM_SUBSCRIPTION_KEY": args.key_secret_ref}
    try:
        create_hosted_version(args.project_endpoint, image, env)
    except Exception as exc:  # noqa: BLE001 - preview API: print the documented fallbacks
        print(f"✗ Hosted agent creation failed ({type(exc).__name__}: {exc}).")
        print("Fallback 1: azd ai agent init -m <agent.manifest.yaml> && azd deploy")
        print(f"Fallback 2: az containerapp up --name care-agent-demo --image {image} --ingress external --target-port 8088 "
              "--env-vars APIM_BASE_URL=... PARTICIPANT_ID=presenter-hosted APIM_SUBSCRIPTION_KEY=secretref:apim-key")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
