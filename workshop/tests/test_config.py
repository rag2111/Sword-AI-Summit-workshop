import pytest

from tests.helpers import BASE, ENV, KEY, REMOTE_CONFIG, make_settings


def test_derives_every_route_from_three_values():
    s = make_settings()
    assert s.apim_base_url == BASE  # trailing slash stripped
    assert s.openai_endpoint == BASE  # the SDK appends /openai/...
    assert s.mcp_url == f"{BASE}/care-tools/mcp"
    assert s.a2a_agent_card_url == f"{BASE}/a2a/care-knowledge/.well-known/agent-card.json"
    assert s.a2a_base_url == f"{BASE}/a2a/care-knowledge"
    assert s.foundry_project_endpoint == f"{BASE}/foundry/api/projects/care-proj"
    assert s.appinsights_connection_string == REMOTE_CONFIG["connectionString"]
    assert s.chat_model == "gpt-6-luna" and s.judge_model == "gpt-6-sol"
    assert s.openai_api_version == "2024-10-21"
    assert s.chat_api == "chat_completions"
    assert s.telemetry_config_url == f"{BASE}/telemetry/config"


def test_overrides_win_and_skip_remote_fetch():
    from care_agent.config import derive_settings

    calls = []
    env = {
        **ENV,
        "FOUNDRY_PROJECT_ENDPOINT": f"{BASE}/foundry/api/projects/other",
        "APPLICATIONINSIGHTS_CONNECTION_STRING": "InstrumentationKey=x;IngestionEndpoint=https://example/",
        "CHAT_MODEL": "my-chat",
        "OPENAI_API_VERSION": "2025-01-01-preview",
    }
    s = derive_settings(env, fetch_remote=lambda b, k: calls.append(1) or {})
    assert calls == []  # nothing unknown -> no /telemetry/config call
    assert s.foundry_project_endpoint.endswith("/projects/other")
    assert s.chat_model == "my-chat"
    assert s.openai_api_version == "2025-01-01-preview"


def test_project_name_override_builds_endpoint():
    s = make_settings(FOUNDRY_PROJECT_NAME="p2", APPLICATIONINSIGHTS_CONNECTION_STRING="InstrumentationKey=x")
    assert s.foundry_project_endpoint == f"{BASE}/foundry/api/projects/p2"


@pytest.mark.parametrize("missing", ["APIM_BASE_URL", "APIM_SUBSCRIPTION_KEY", "PARTICIPANT_ID"])
def test_missing_values_raise_helpful_error(missing):
    from care_agent.config import ConfigError, derive_settings

    env = dict(ENV)
    env[missing] = "<placeholder>"
    with pytest.raises(ConfigError, match=missing):
        derive_settings(env, fetch_remote=None)


@pytest.mark.parametrize("participant", ["user00", "user00-xxx"])
def test_example_placeholders_are_rejected(participant):
    from care_agent.config import ConfigError, derive_settings

    env = {**ENV, "PARTICIPANT_ID": participant}
    with pytest.raises(ConfigError, match="PARTICIPANT_ID"):
        derive_settings(env, fetch_remote=None)


def test_http_base_url_rejected():
    from care_agent.config import ConfigError, derive_settings

    with pytest.raises(ConfigError, match="https"):
        derive_settings({**ENV, "APIM_BASE_URL": "http://apim.example"}, fetch_remote=None)


def test_base_url_with_route_suffix_is_normalized():
    from care_agent.config import normalize_base_url

    assert normalize_base_url(' "https://x.azure-api.net/openai/" ') == "https://x.azure-api.net"


def test_remote_fetch_failure_is_a_warning_not_a_crash():
    from care_agent.config import derive_settings

    def boom(base, key):
        raise TimeoutError("no network")

    s = derive_settings(ENV, fetch_remote=boom)
    assert s.appinsights_connection_string is None
    assert s.foundry_project_endpoint is None
    assert any("telemetry/config" in w for w in s.warnings)


def test_participant_id_format_warning():
    s = make_settings(PARTICIPANT_ID="presenter")
    assert any("PARTICIPANT_ID" in w for w in s.warnings)


def test_headers_and_redaction():
    s = make_settings()
    assert s.apim_headers() == {"Ocp-Apim-Subscription-Key": KEY, "api-key": KEY}
    assert KEY not in repr(s)
    assert s.redacted_key().startswith(KEY[:4]) and KEY not in s.redacted_key()


@pytest.mark.parametrize("participant", ["user01", "user07", "user99"])
def test_new_participant_ids_and_short_keys(participant):
    key = participant + "k3x"
    s = make_settings(PARTICIPANT_ID=participant, APIM_SUBSCRIPTION_KEY=key)
    assert s.warnings == ()
    assert s.participant_id == participant
    assert s.apim_headers() == {"Ocp-Apim-Subscription-Key": key, "api-key": key}
    assert s.redacted_key() == "****"
    assert key not in repr(s)


@pytest.mark.parametrize("participant", ["user1", "user100", "user07-k3x", "user07k3x"])
def test_old_or_invalid_names_produce_format_warning(participant):
    assert any("PARTICIPANT_ID" in w for w in make_settings(PARTICIPANT_ID=participant).warnings)


def test_env_example_contains_only_three_active_values():
    from tests.helpers import ROOT

    lines = [l for l in (ROOT / ".env.example").read_text().splitlines() if l.strip() and not l.startswith("#")]
    assert [l.split("=")[0] for l in lines] == ["APIM_BASE_URL", "APIM_SUBSCRIPTION_KEY", "PARTICIPANT_ID"]


def test_dotenv_is_git_ignored():
    from tests.helpers import ROOT

    ignored = (ROOT / ".gitignore").read_text().splitlines()
    assert ".env" in ignored and "!.env.example" in ignored
