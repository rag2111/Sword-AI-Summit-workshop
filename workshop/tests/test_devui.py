"""DevUI startup must display the local token without exposing the APIM key."""

import asyncio
import secrets
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import pytest

from tests.helpers import KEY, make_settings


@pytest.fixture
def launcher(monkeypatch):
    from care_agent import agent, devui

    serve = Mock()
    sdk = ModuleType("agent_framework.devui")
    sdk.serve = serve
    monkeypatch.setitem(sys.modules, "agent_framework.devui", sdk)
    monkeypatch.setattr(devui, "get_settings", make_settings)
    monkeypatch.setattr(devui, "setup_telemetry", Mock())
    handle = SimpleNamespace(agent=object())
    monkeypatch.setattr(agent, "build_agent", Mock(return_value=handle))
    return devui, serve, handle


@pytest.mark.parametrize("configured", [None, "", "configured-devui-test-token"])
def test_prints_and_uses_same_local_token(launcher, monkeypatch, capsys, configured):
    devui, serve, handle = launcher
    if configured is None:
        monkeypatch.delenv("DEVUI_AUTH_TOKEN", raising=False)
    else:
        monkeypatch.setenv("DEVUI_AUTH_TOKEN", configured)
    generate = Mock(return_value="generated-devui-test-token")
    monkeypatch.setattr(secrets, "token_urlsafe", generate)

    assert devui.main() == 0

    token = configured or generate.return_value
    output = capsys.readouterr().out
    assert f"DevUI access token: {token}" in output
    assert "not your APIM subscription key" in output
    assert KEY not in output
    serve.assert_called_once_with(
        entities=[handle.agent], host="127.0.0.1", port=8080, auto_open=True,
        auth_enabled=True, auth_token=token,
    )
    if configured:
        generate.assert_not_called()
    else:
        generate.assert_called_once_with(32)


def test_displayed_token_authenticates_with_pinned_devui(launcher, monkeypatch, capsys):
    httpx = pytest.importorskip("httpx")
    sdk = pytest.importorskip("agent_framework_devui")
    devui, serve, _ = launcher
    monkeypatch.delenv("DEVUI_AUTH_TOKEN", raising=False)
    assert devui.main() == 0
    output = capsys.readouterr().out
    token = serve.call_args.kwargs["auth_token"]
    assert f"DevUI access token: {token}" in output
    server = sdk.DevServer(host="127.0.0.1", auth_enabled=True, auth_token=token)

    async def check():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=server.get_app()), base_url="http://127.0.0.1"
        ) as client:
            assert (await client.get("/meta")).status_code == 401
            assert (await client.get("/meta", headers={"Authorization": "Bearer wrong"})).status_code == 401
            assert (await client.get("/meta", headers={"Authorization": f"Bearer {token}"})).status_code == 200

    asyncio.run(check())
