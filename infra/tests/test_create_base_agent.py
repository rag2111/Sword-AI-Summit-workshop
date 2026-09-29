"""Base-agent model routing, reasoning compatibility, and failure-cache regression tests."""

import importlib.util
import json
from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest
from azure.ai.projects.models import MCPTool
from azure.core.exceptions import HttpResponseError, ResourceNotFoundError

from _helpers import INFRA

spec = importlib.util.spec_from_file_location("create_base_agent", INFRA / "scripts" / "create_base_agent.py")
agent = importlib.util.module_from_spec(spec)
spec.loader.exec_module(agent)


@pytest.fixture
def setup(monkeypatch, tmp_path):
    monkeypatch.setenv("FOUNDRY_PROJECT_ENDPOINT", "https://example.services.ai.azure.com/api/projects/test")
    monkeypatch.setenv("CHAT_DEPLOYMENT", "gpt-6-luna")
    monkeypatch.setenv("APIM_CONNECTION_NAME", "apim-gateway")
    monkeypatch.setenv("MODEL_ROUTE", "auto")
    monkeypatch.setenv("ENABLE_A2A", "false")
    knowledge_file = tmp_path / "knowledge.json"
    knowledge_file.write_text(json.dumps({"mode": "kb"}))
    monkeypatch.setattr(agent, "INFRA_DIR", tmp_path)
    monkeypatch.setattr(agent, "KNOWLEDGE_FILE", knowledge_file)
    monkeypatch.setattr(agent, "OUT_FILE", tmp_path / "base_agent.json")
    monkeypatch.setattr(agent, "DefaultAzureCredential", Mock())
    project = Mock()
    project.agents.get.return_value.versions.latest.version = "1"
    versions = iter(["2", "3"])

    def create_version(**kwargs):
        version = next(versions)
        project.agents.get.return_value.versions.latest.version = version
        return SimpleNamespace(version=version)

    project.agents.create_version.side_effect = create_version
    monkeypatch.setattr(agent, "AIProjectClient", Mock(return_value=project))
    tool = MCPTool(server_label="care_kb", server_url="https://example.search.windows.net/mcp")
    monkeypatch.setattr(agent, "grounding_tool", Mock(return_value=tool))
    monkeypatch.setattr(agent.time, "sleep", Mock())
    smoke = Mock(return_value=None)
    monkeypatch.setattr(agent, "smoke_invoke", smoke)
    return project, tool, smoke


def save_previous(tool, **extra):
    _, digest = agent.definition_for("gpt-6-luna", tool, model_route="direct")
    previous = {
        "agent_name": agent.AGENT_NAME, "version": "1", "model": "gpt-6-luna",
        "model_route": "direct", "definition_sha256": digest, "grounding": "kb",
        "apim_route_error": "Function tools with reasoning_effort are not supported",
    } | extra
    agent.OUT_FILE.write_text(json.dumps(previous))


def read_result():
    return json.loads(agent.OUT_FILE.read_text())


def test_reasoning_is_scoped_to_apim_and_changes_digest(setup):
    _, tool, _ = setup
    model = "apim-gateway/gpt-6-luna"
    routed, digest = agent.definition_for(model, tool, model_route="apim")
    original, original_digest = agent.definition_for(model, tool, model_route="direct")
    assert routed.as_dict()["reasoning"] == {"effort": "none"}
    assert "reasoning" not in original.as_dict()
    assert routed.as_dict()["tools"] == original.as_dict()["tools"]
    assert routed.instructions == original.instructions == agent.INSTRUCTIONS
    assert digest != original_digest
    assert agent.definition_for(model, tool, model_route="apim")[1] == digest


@pytest.mark.parametrize("cache", [{}, {"apim_definition_sha256": "old-definition"}])
def test_auto_retries_legacy_or_changed_failure_cache(setup, cache):
    project, tool, smoke = setup
    save_previous(tool, **cache)
    agent.main()
    definition = project.agents.create_version.call_args.kwargs["definition"]
    assert definition.model == "apim-gateway/gpt-6-luna"
    assert definition.as_dict()["reasoning"] == {"effort": "none"}
    smoke.assert_called_once_with(project, "2")
    assert read_result()["model_route"] == "apim"
    assert "apim_route_error" not in read_result()
    assert "apim_definition_sha256" not in read_result()


def test_auto_keeps_failure_cache_for_same_definition(setup):
    project, tool, smoke = setup
    _, digest = agent.definition_for("apim-gateway/gpt-6-luna", tool, model_route="apim")
    save_previous(tool, apim_definition_sha256=digest)
    agent.main()
    project.agents.create_version.assert_not_called()
    smoke.assert_called_once_with(project, "1")
    assert read_result()["model_route"] == "direct"


def test_failed_retry_publishes_direct_fallback_as_latest(setup):
    project, tool, smoke = setup
    save_previous(tool)
    smoke.side_effect = ["gateway unavailable", None]
    agent.main()
    assert project.agents.create_version.call_count == 2
    result = read_result()
    assert result["version"] == "3"
    assert project.agents.get.return_value.versions.latest.version == "3"
    assert result["model_route"] == "direct"
    assert result["apim_route_error"] == "gateway unavailable"
    assert result["apim_definition_sha256"] == agent.definition_for(
        "apim-gateway/gpt-6-luna", tool, model_route="apim"
    )[1]


def test_auto_fallback_creates_direct_definition_without_reasoning(setup):
    project, _, smoke = setup
    smoke.side_effect = ["gateway unavailable", None]
    agent.main()
    definitions = [call.kwargs["definition"].as_dict() for call in project.agents.create_version.call_args_list]
    assert definitions[0]["reasoning"] == {"effort": "none"}
    assert definitions[1]["model"] == "gpt-6-luna"
    assert "reasoning" not in definitions[1]
    assert read_result()["model_route"] == "direct"
    assert read_result()["apim_route_error"] == "gateway unavailable"


@pytest.mark.parametrize("route,errors", [
    ("apim", ["gateway unavailable"]),
    ("direct", ["direct unavailable"]),
    ("auto", ["gateway unavailable", "direct unavailable"]),
])
def test_failed_smoke_without_successful_fallback_is_fatal(setup, monkeypatch, route, errors):
    _, _, smoke = setup
    monkeypatch.setenv("MODEL_ROUTE", route)
    smoke.side_effect = errors
    with pytest.raises(SystemExit, match="Test invocation failed"):
        agent.main()
    assert not agent.OUT_FILE.exists()


def test_strict_apim_retries_matching_cache(setup, monkeypatch):
    project, tool, smoke = setup
    _, digest = agent.definition_for("apim-gateway/gpt-6-luna", tool, model_route="apim")
    save_previous(tool, apim_definition_sha256=digest)
    monkeypatch.setenv("MODEL_ROUTE", "apim")
    agent.main()
    smoke.assert_called_once_with(project, "2")
    assert read_result()["model_route"] == "apim"


def test_direct_route_does_not_disable_reasoning(setup, monkeypatch):
    project, _, _ = setup
    monkeypatch.setenv("MODEL_ROUTE", "direct")
    agent.main()
    definition = project.agents.create_version.call_args.kwargs["definition"].as_dict()
    assert definition["model"] == "gpt-6-luna"
    assert "reasoning" not in definition


def test_strict_apim_requires_connection(setup, monkeypatch):
    project, _, _ = setup
    monkeypatch.setenv("MODEL_ROUTE", "apim")
    monkeypatch.delenv("APIM_CONNECTION_NAME")
    with pytest.raises(SystemExit, match="requires APIM_CONNECTION_NAME"):
        agent.main()
    project.agents.create_version.assert_not_called()


def test_successful_unchanged_apim_definition_reuses_version(setup):
    project, _, smoke = setup
    agent.main()
    project.agents.create_version.reset_mock()
    smoke.reset_mock()
    agent.main()
    project.agents.create_version.assert_not_called()
    smoke.assert_called_once_with(project, "2")
    assert read_result()["model_route"] == "apim"


def test_smoke_targets_exact_version():
    project = Mock()
    client = project.get_openai_client.return_value
    client.responses.create.return_value.output_text = "Post-discharge follow-up SLA (FU-001 §FU-3)."
    assert agent.smoke_invoke(project, "7") is None
    assert client.responses.create.call_args.kwargs["extra_body"]["agent_reference"] == {
        "name": agent.AGENT_NAME, "version": "7", "type": "agent_reference",
    }


def test_smoke_reports_empty_response_and_api_errors():
    project = Mock()
    client = project.get_openai_client.return_value
    client.responses.create.return_value.output_text = ""
    assert agent.smoke_invoke(project, "7") == "empty response"
    client.responses.create.side_effect = RuntimeError("tools/reasoning rejected")
    assert agent.smoke_invoke(project, "7") == "tools/reasoning rejected"


def test_smoke_rejects_uncited_policy_answer():
    project = Mock()
    project.get_openai_client.return_value.responses.create.return_value.output_text = "Follow up in two days."
    assert agent.smoke_invoke(project, "7") == "missing follow-up policy citation (FU-001 + section)"


def test_cached_fallback_is_republished_when_latest_is_broken(setup):
    project, tool, smoke = setup
    _, digest = agent.definition_for("apim-gateway/gpt-6-luna", tool, model_route="apim")
    save_previous(tool, apim_definition_sha256=digest)
    project.agents.get.return_value.versions.latest.version = "broken"
    agent.main()
    assert read_result()["version"] == "2"
    assert read_result()["model_route"] == "direct"
    smoke.assert_called_once_with(project, "2")


def test_reused_version_is_revalidated(setup):
    project, _, smoke = setup
    agent.main()
    smoke.return_value = "missing citation"
    with pytest.raises(SystemExit, match="Test invocation failed"):
        agent.main()


def test_latest_lookup_handles_missing_agent_but_propagates_other_errors():
    project = Mock()
    project.agents.get.side_effect = ResourceNotFoundError("missing")
    assert not agent.version_is_latest(project, "1")
    project.agents.get.side_effect = RuntimeError("access denied")
    with pytest.raises(RuntimeError, match="access denied"):
        agent.version_is_latest(project, "1")


def test_latest_lookup_retries_foundry_timeout(monkeypatch):
    project = Mock()
    timeout = HttpResponseError("The operation was timeout.")
    timeout.error = SimpleNamespace(code="Timeout")
    project.agents.get.side_effect = [timeout, SimpleNamespace(
        versions=SimpleNamespace(latest=SimpleNamespace(version="7"))
    )]
    sleep = Mock()
    monkeypatch.setattr(agent.time, "sleep", sleep)

    assert agent.version_is_latest(project, "7")
    assert project.agents.get.call_count == 2
    sleep.assert_called_once_with(agent.AGENT_GET_RETRY_DELAY)


def test_latest_lookup_propagates_exhausted_foundry_timeout(monkeypatch):
    project = Mock()
    timeout = HttpResponseError("The operation was timeout.")
    timeout.error = SimpleNamespace(code="Timeout")
    project.agents.get.side_effect = timeout
    sleep = Mock()
    monkeypatch.setattr(agent.time, "sleep", sleep)

    with pytest.raises(HttpResponseError, match="timeout"):
        agent.version_is_latest(project, "7")
    assert project.agents.get.call_count == agent.AGENT_GET_ATTEMPTS
    assert sleep.call_count == agent.AGENT_GET_ATTEMPTS - 1


@pytest.mark.parametrize("status,code", [
    (500, "InternalServerError"),
    (None, "InternalServerError"),
    (500, None),
    (408, None),
    (429, None),
    (502, None),
    (503, None),
    (504, None),
])
@pytest.mark.parametrize("latest_version,expected", [("7", True), ("8", False)])
def test_latest_lookup_retries_transient_errors(monkeypatch, capsys, status, code, latest_version, expected):
    project = Mock()
    error = HttpResponseError("Unable to get resource information.")
    error.status_code = status
    error.error = SimpleNamespace(code=code)
    project.agents.get.side_effect = [error, SimpleNamespace(
        versions=SimpleNamespace(latest=SimpleNamespace(version=latest_version))
    )]
    sleep = Mock()
    monkeypatch.setattr(agent.time, "sleep", sleep)

    assert agent.version_is_latest(project, "7") is expected
    assert project.agents.get.call_args_list == [call(agent_name=agent.AGENT_NAME)] * 2
    sleep.assert_called_once_with(agent.AGENT_GET_RETRY_DELAY)
    assert f"HTTP {status}, code {code}" in capsys.readouterr().out


@pytest.mark.parametrize("status,code", [
    (400, "BadRequest"),
    (401, "Unauthorized"),
    (403, "Forbidden"),
    (403, "InternalServerError"),
    (501, "NotImplemented"),
    (None, "UnknownError"),
])
def test_latest_lookup_does_not_retry_permanent_errors(monkeypatch, status, code):
    project = Mock()
    error = HttpResponseError("permanent failure")
    error.status_code = status
    error.error = SimpleNamespace(code=code)
    project.agents.get.side_effect = error
    sleep = Mock()
    monkeypatch.setattr(agent.time, "sleep", sleep)

    with pytest.raises(HttpResponseError) as caught:
        agent.version_is_latest(project, "7")
    assert caught.value is error
    project.agents.get.assert_called_once_with(agent_name=agent.AGENT_NAME)
    sleep.assert_not_called()


def test_cached_agent_is_reused_after_internal_server_error(setup, monkeypatch):
    project, tool, smoke = setup
    monkeypatch.setenv("MODEL_ROUTE", "direct")
    save_previous(tool)
    error = HttpResponseError("Unable to get resource information.")
    error.status_code = 500
    error.error = SimpleNamespace(code="InternalServerError")
    project.agents.get.side_effect = [error, SimpleNamespace(
        versions=SimpleNamespace(latest=SimpleNamespace(version="1"))
    )]

    agent.main()

    project.agents.create_version.assert_not_called()
    smoke.assert_called_once_with(project, "1")
    assert read_result()["version"] == "1"


def test_exhausted_internal_server_error_preserves_cached_agent(setup, monkeypatch, capsys):
    project, tool, smoke = setup
    monkeypatch.setenv("MODEL_ROUTE", "direct")
    save_previous(tool)
    previous = agent.OUT_FILE.read_bytes()
    error = HttpResponseError("Unable to get resource information.")
    error.status_code = 500
    error.error = SimpleNamespace(code="InternalServerError")
    project.agents.get.side_effect = error

    with pytest.raises(HttpResponseError) as caught:
        agent.main()

    assert caught.value is error
    assert project.agents.get.call_count == agent.AGENT_GET_ATTEMPTS
    assert agent.time.sleep.call_args_list == [
        call(agent.AGENT_GET_RETRY_DELAY * attempt)
        for attempt in range(1, agent.AGENT_GET_ATTEMPTS)
    ]
    project.agents.create_version.assert_not_called()
    smoke.assert_not_called()
    assert agent.OUT_FILE.read_bytes() == previous
    assert "Retry terraform apply once the service recovers." in capsys.readouterr().out
