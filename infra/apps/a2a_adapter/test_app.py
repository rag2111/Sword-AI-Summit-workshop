"""Offline startup regression tests using the adapter's pinned SDK dependencies.

Run from this directory: uv run --no-sync python -m unittest test_app
"""

import os
import unittest
from unittest.mock import patch

import httpx

with patch.dict(os.environ, {
    "FOUNDRY_PROJECT_ENDPOINT": "https://example.services.ai.azure.com/api/projects/test",
    "PUBLIC_A2A_URL": "https://example.azure-api.net/a2a/care-knowledge",
    "BACKEND_SHARED_SECRET": "test-only-secret",
}):
    import app


class StartupTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        with patch.object(app, "ManagedIdentityCredential", autospec=True) as credential:
            self.application = await app.build_app()
            credential.return_value.get_token.assert_not_called()
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.application), base_url="https://adapter.test"
        )

    async def asyncTearDown(self):
        await self.client.aclose()

    async def test_health_is_available_without_authentication(self):
        response = await self.client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    async def test_agent_card_has_public_metadata_at_startup(self):
        response = await self.client.get(
            "/.well-known/agent-card.json", headers={"x-backend-secret": app.SHARED_SECRET}
        )
        self.assertEqual(response.status_code, 200)
        card = response.json()
        self.assertEqual(card["name"], "Care Knowledge Agent")
        self.assertIn("Training use only; not a medical device", card["description"])
        self.assertEqual(card["supportedInterfaces"][0]["url"], app.PUBLIC_A2A_URL)
        self.assertEqual(card["skills"][0]["id"], "care-policy-qa")
        self.assertFalse(card["capabilities"]["streaming"])

    async def test_agent_card_still_requires_the_gateway_secret(self):
        for headers in ({}, {"x-backend-secret": "wrong"}):
            with self.subTest(headers=headers):
                response = await self.client.get("/.well-known/agent-card.json", headers=headers)
                self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
