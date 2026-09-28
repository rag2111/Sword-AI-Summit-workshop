"""Participant names and workshop-only primary keys (CONTRACT section 1)."""

import random
import re
import string

import _helpers

NAME = re.compile(r"^user(?:0[1-9]|[1-9][0-9])$")
KEY = re.compile(r"^user(?:0[1-9]|[1-9][0-9])[a-z0-9]{3}$")
MODULE = (_helpers.INFRA / "modules" / "participants" / "main.tf").read_text(encoding="utf-8")
ENV_TEMPLATE = (_helpers.INFRA / "modules" / "participants" / "participant.env.tftpl").read_text(encoding="utf-8")


def terraform_format(i: int) -> str:
    return "user%02d" % i


def test_contract_example():
    assert terraform_format(7) == "user07"
    assert NAME.fullmatch("user07")
    assert KEY.fullmatch("user07" + "k3x")


def test_generated_names_are_valid_and_unique():
    rng = random.Random(0)
    alphabet = string.ascii_lowercase + string.digits
    names = [terraform_format(i + 1) for i in range(99)]
    keys = [name + "".join(rng.choice(alphabet) for _ in range(3)) for name in names]
    assert all(NAME.fullmatch(n) for n in names)
    assert all(KEY.fullmatch(key) and key.startswith(name) for name, key in zip(names, keys))
    assert len(set(names)) == len(set(keys)) == 99
    assert names[0] == "user01" and names[-1] == "user99"


def test_bad_names_rejected():
    for bad in ("user7", "user00", "User07", "user07-k3x", "user07k3x", "user100", "user07\n"):
        assert not NAME.fullmatch(bad), bad


def test_bad_keys_rejected():
    for bad in ("user07", "user07-k3x", "user07K3X", "user07k3", "user07k3x!", "user7k3x", "user00abc"):
        assert not KEY.fullmatch(bad), bad


def test_terraform_module_uses_the_contract_rule():
    assert 'format("user%02d", i + 1)' in MODULE
    assert 'primary_key   = "${local.names[count.index]}${random_password.key_suffix[count.index].result}"' in MODULE
    assert "secondary_key" not in MODULE
    block = MODULE[MODULE.index('resource "random_password" "key_suffix"'):MODULE.index("locals {")]
    for setting in ("length  = 3", "lower   = true", "upper   = false", "numeric = true", "special = false"):
        assert setting in block, setting


def test_env_file_contains_contract_values():
    keys = set(re.findall(r"^([A-Z0-9_]+)=", ENV_TEMPLATE, flags=re.M))
    required = {"APIM_BASE_URL", "APIM_SUBSCRIPTION_KEY", "PARTICIPANT_ID", "OPENAI_ENDPOINT", "OPENAI_API_VERSION",
                "CHAT_MODEL", "JUDGE_MODEL", "MCP_URL", "A2A_AGENT_CARD_URL", "FOUNDRY_PROJECT_NAME",
                "FOUNDRY_PROJECT_ENDPOINT", "APPLICATIONINSIGHTS_CONNECTION_STRING"}
    assert required <= keys
    assert "MCP_URL=${apim_base_url}/care-tools/mcp" in ENV_TEMPLATE
    assert "A2A_AGENT_CARD_URL=${apim_base_url}/a2a/care-knowledge/.well-known/agent-card.json" in ENV_TEMPLATE
    assert "FOUNDRY_PROJECT_ENDPOINT=${apim_base_url}/foundry/api/projects/${project_name}" in ENV_TEMPLATE
    assert "IngestionEndpoint=${apim_base_url}/telemetry/" in ENV_TEMPLATE
