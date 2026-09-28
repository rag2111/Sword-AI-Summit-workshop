# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = [
#   "httpx==0.28.1",
# ]
# ///
"""Smoke-test every participant-facing APIM route with ONE participant's key.

    uv run scripts/smoke_test.py --env out/participants/user01.env

Only the APIM gateway URL and the subscription key are used (exactly what participants get).
Prints a PASS/FAIL table and exits non-zero if any check fails.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

import httpx

TIMEOUT = httpx.Timeout(120.0, connect=15.0)


def load_env(path: Path) -> dict[str, str]:
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip().strip('"')
    return values


class Smoke:
    def __init__(self, cfg: dict[str, str]) -> None:
        self.cfg = cfg
        self.base = cfg["APIM_BASE_URL"].rstrip("/")
        key = cfg["APIM_SUBSCRIPTION_KEY"]
        # CONTRACT §2: every client sends both headers. traceparent shows up in App Insights.
        self.trace_id = uuid.uuid4().hex
        self.headers = {"Ocp-Apim-Subscription-Key": key, "api-key": key,
                        "traceparent": f"00-{self.trace_id}-{uuid.uuid4().hex[:16]}-01"}
        self.http = httpx.Client(timeout=TIMEOUT, headers=self.headers)
        self.results: list[tuple[str, bool, str]] = []

    def check(self, name: str, fn) -> None:
        start = time.perf_counter()
        try:
            ok, detail = fn()
        except Exception as exc:  # noqa: BLE001 - report every failure in the table
            ok, detail = False, f"{type(exc).__name__}: {str(exc)[:160]}"
        self.results.append((name, ok, f"{detail} ({(time.perf_counter() - start) * 1000:.0f} ms)"))

    # ---- /openai ---------------------------------------------------------------------------
    def model_deployments(self):
        url = f"{self.base}/openai/deployments/{self.cfg['CHAT_MODEL']}/chat/completions"
        r = self.http.post(url, params={"api-version": self.cfg["OPENAI_API_VERSION"]},
                           json={"messages": [{"role": "user", "content": "Reply with the word PONG."}],
                                 "max_completion_tokens": 5})
        return r.status_code == 200, f"HTTP {r.status_code} {r.json()['choices'][0]['message']['content'] if r.status_code == 200 else r.text[:120]}"

    def model_v1(self):
        r = self.http.post(f"{self.base}/openai/v1/chat/completions",
                           json={"model": self.cfg["CHAT_MODEL"], "max_completion_tokens": 5,
                                 "messages": [{"role": "user", "content": "Reply with the word PONG."}]})
        return r.status_code == 200, f"HTTP {r.status_code}"

    # ---- /care-tools/mcp -------------------------------------------------------------------
    def _mcp(self, payload: dict, session: str | None) -> tuple[httpx.Response, dict | None]:
        headers = {"Accept": "application/json, text/event-stream", "MCP-Protocol-Version": "2025-06-18"}
        if session:
            headers["Mcp-Session-Id"] = session
        r = self.http.post(self.cfg["MCP_URL"], json=payload, headers=headers)
        body = None
        if "text/event-stream" in r.headers.get("content-type", ""):
            for line in r.text.splitlines():
                if line.startswith("data:"):
                    body = json.loads(line[5:].strip())
        elif r.content:
            body = r.json()
        return r, body

    def mcp(self):
        r, body = self._mcp({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-06-18", "capabilities": {},
            "clientInfo": {"name": "infra-smoke-test", "version": "1.0"}}}, None)
        if r.status_code != 200 or not body or "result" not in body:
            return False, f"initialize HTTP {r.status_code} {r.text[:120]}"
        session = r.headers.get("mcp-session-id")
        self._mcp({"jsonrpc": "2.0", "method": "notifications/initialized"}, session)
        r, body = self._mcp({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, session)
        tools = sorted(t["name"] for t in (body or {}).get("result", {}).get("tools", []))
        expected = sorted(["search_patient", "get_care_plan", "list_available_slots", "book_follow_up",
                           "create_referral", "check_medication_interactions", "check_prior_auth_requirement"])
        if tools != expected:
            return False, f"tools/list returned {tools}"
        r, body = self._mcp({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                             "params": {"name": "search_patient", "arguments": {"query": "Ellis"}}}, session)
        found = "P-1042" in json.dumps(body or {})
        return found, f"7 tools listed; search_patient('Ellis') {'found P-1042' if found else 'did NOT find P-1042'}"

    # ---- /a2a/care-knowledge ---------------------------------------------------------------
    def a2a_card(self):
        r = self.http.get(self.cfg["A2A_AGENT_CARD_URL"], headers={"A2A-Version": "1.0"})
        if r.status_code != 200:
            return False, f"HTTP {r.status_code} {r.text[:120]}"
        self.card = r.json()
        urls = [i.get("url", "") for i in self.card.get("supportedInterfaces", [])] + [self.card.get("url", "")]
        via_apim = any(u.startswith(self.base) for u in urls if u)
        return True, f"'{self.card.get('name')}' interface via APIM: {via_apim}"

    def a2a_message(self):
        card = getattr(self, "card", {})
        question = "Does Northwind Health Plan require prior authorization for CARD-MRI? Cite the section."
        v1 = {"jsonrpc": "2.0", "id": "1", "method": "SendMessage", "params": {"message": {
            "messageId": uuid.uuid4().hex, "role": "ROLE_USER", "parts": [{"text": question}]}}}
        v03 = {"jsonrpc": "2.0", "id": "1", "method": "message/send", "params": {"message": {
            "kind": "message", "messageId": uuid.uuid4().hex, "role": "user",
            "parts": [{"kind": "text", "text": question}]}}}
        attempts = [(v1, "1.0"), (v03, "0.3")] if "supportedInterfaces" in card else [(v03, "0.3"), (v1, "1.0")]
        detail = ""
        for payload, version in attempts:
            r = self.http.post(self.cfg["A2A_URL"], json=payload, headers={"A2A-Version": version})
            body = r.json() if r.content and "json" in r.headers.get("content-type", "") else {}
            if r.status_code == 200 and "result" in body:
                return True, f"A2A {version} {payload['method']} OK"
            detail += f"[{version}: HTTP {r.status_code} {json.dumps(body.get('error', ''))[:80]}] "
        return False, detail

    # ---- /telemetry ------------------------------------------------------------------------
    def telemetry_config(self):
        r = self.http.get(f"{self.base}/telemetry/config")
        if r.status_code != 200:
            return False, f"HTTP {r.status_code}"
        self.telemetry = r.json()
        ok = f"IngestionEndpoint={self.base}/telemetry/" in self.telemetry.get("connectionString", "")
        return ok, f"project={self.telemetry.get('foundryProjectName')} ingestion via APIM: {ok}"

    def telemetry_track(self):
        cs = getattr(self, "telemetry", {}).get("connectionString") or self.cfg["APPLICATIONINSIGHTS_CONNECTION_STRING"]
        ikey = dict(p.split("=", 1) for p in cs.split(";") if "=" in p)["InstrumentationKey"]
        envelope = [{
            "name": "Microsoft.ApplicationInsights.Event", "time": datetime.now(UTC).isoformat(), "iKey": ikey,
            "tags": {"ai.cloud.role": self.cfg["PARTICIPANT_ID"], "ai.operation.id": self.trace_id},
            "data": {"baseType": "EventData", "baseData": {"ver": 2, "name": "infra-smoke-test",
                                                            "properties": {"participant": self.cfg["PARTICIPANT_ID"]}}},
        }]
        r = self.http.post(f"{self.base}/telemetry/v2.1/track", json=envelope)
        accepted = r.json().get("itemsAccepted") if r.status_code == 200 else None
        return r.status_code == 200 and accepted == 1, f"HTTP {r.status_code} itemsAccepted={accepted}"

    # ---- /foundry --------------------------------------------------------------------------
    def foundry_agents(self):
        r = self.http.get(f"{self.cfg['FOUNDRY_PROJECT_ENDPOINT']}/agents", params={"api-version": "v1"},
                          headers={"Authorization": "Bearer placeholder-apim-discards-this"})
        found = r.status_code == 200 and "care-knowledge-agent" in r.text
        return found, f"HTTP {r.status_code} care-knowledge-agent listed: {found}"

    def foundry_blocked(self):
        r = self.http.delete(f"{self.cfg['FOUNDRY_PROJECT_ENDPOINT']}/agents/care-knowledge-agent",
                             params={"api-version": "v1"})
        return r.status_code == 403, f"DELETE base agent -> HTTP {r.status_code} (403 expected: allowlist works)"

    def run(self) -> int:
        self.check("model /openai/deployments/*", self.model_deployments)
        self.check("model /openai/v1/*", self.model_v1)
        self.check("MCP /care-tools/mcp", self.mcp)
        self.check("A2A agent card", self.a2a_card)
        self.check("A2A message", self.a2a_message)
        self.check("telemetry /config", self.telemetry_config)
        self.check("telemetry /v2.1/track", self.telemetry_track)
        self.check("foundry list agents", self.foundry_agents)
        self.check("foundry allowlist blocks DELETE", self.foundry_blocked)
        width = max(len(n) for n, _, _ in self.results)
        print(f"\nSmoke test for {self.cfg['PARTICIPANT_ID']} against {self.base}  (trace id {self.trace_id})\n")
        for name, ok, detail in self.results:
            print(f"  {'PASS' if ok else 'FAIL'}  {name.ljust(width)}  {detail}")
        failed = sum(not ok for _, ok, _ in self.results)
        print(f"\n{len(self.results) - failed}/{len(self.results)} checks passed.")
        return 1 if failed else 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--env", required=True, type=Path, help="Participant .env file (infra/out/participants/<name>.env)")
    args = parser.parse_args()
    sys.exit(Smoke(load_env(args.env)).run())


if __name__ == "__main__":
    main()
