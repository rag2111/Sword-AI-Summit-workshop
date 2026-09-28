"""Shared helpers for the offline tests."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

BASE = "https://apim-test.azure-api.net"
KEY = "0123456789abcdef0123456789abcdef"

ENV = {"APIM_BASE_URL": BASE + "/", "APIM_SUBSCRIPTION_KEY": KEY, "PARTICIPANT_ID": "user07"}

REMOTE_CONFIG = {
    "connectionString": f"InstrumentationKey=00000000-0000-0000-0000-000000000000;IngestionEndpoint={BASE}/telemetry/",
    "foundryProjectName": "care-proj",
    "chatModel": "gpt-6-luna",
    "judgeModel": "gpt-6-sol",
}


def make_settings(**env_overrides):
    from care_agent.config import derive_settings

    env = {**ENV, **env_overrides}
    return derive_settings(env, fetch_remote=lambda base, key: dict(REMOTE_CONFIG))
