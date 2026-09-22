"""AgentRouter provider + provider-switching tests (no live network).

Reuses the DeepSeek test's transport mock so the REAL request/parse path runs
against canned OpenAI-shaped responses. Verifies the AgentRouter wire contract
(base URL, model, key header), usage capture, cost estimation from configurable
pricing, friendly error mapping, and that switching the active provider in
``Services`` picks the right implementation without touching stored data.
"""
import unittest

from tests.conftest_helpers import _TMP  # noqa: F401  (sets SQUAD_AI_HOME)
from tests.test_deepseek_provider import _Patched, _canned, REQ
from app.providers.agentrouter_provider import AgentRouterProvider
from app.providers.deepseek_provider import DeepSeekProvider
from app.services import Services
from app.utils.config import CONFIG


class TestAgentRouterRequest(unittest.TestCase):
    def test_uses_configured_base_url_and_model(self):
        prov = AgentRouterProvider(api_key="ar-test-key")
        with _Patched(_canned('{"answer":"Retired","option_index":2,'
                              '"confidence":0.9}')) as p:
            r = prov.answer(REQ)
        self.assertTrue(r.success)
        self.assertEqual(r.answer, "Retired")
        self.assertEqual(r.selected_option_index, 2)
        # Key is sent, and the request hits the AgentRouter base URL + model.
        self.assertEqual(p.captured["headers"].get("Authorization"),
                         "Bearer ar-test-key")
        self.assertTrue(p.captured["url"].startswith(
            CONFIG.agentrouter.base_url.rstrip("/")))
        self.assertEqual(p.captured["body"]["model"], CONFIG.agentrouter.model)

    def test_default_model_is_deepseek_v4_flash(self):
        self.assertEqual(AgentRouterProvider("k").model, "deepseek-v4-flash")

    def test_missing_key_fails_gracefully(self):
        r = AgentRouterProvider(api_key=None).answer(REQ)
        self.assertFalse(r.success)
        self.assertIn("key", r.error.lower())

    def test_http_401_maps_to_friendly_auth_error(self):
        prov = AgentRouterProvider(api_key="ar-test-key")
        with _Patched({"error": {"message": "invalid key"}}, status=401):
            ok, msg = prov.test_connection()
        self.assertFalse(ok)
        self.assertIn("authentication", msg.lower())


class TestAgentRouterCost(unittest.TestCase):
    def test_cost_uses_configurable_pricing(self):
        # Pricing defaults to 0 (estimate unknown) -> cost 0…
        prov = AgentRouterProvider(api_key="k")
        self.assertEqual(prov.estimate_cost(1000, 100), 0.0)
        # …until the user configures prices, then it estimates.
        CONFIG.agentrouter.price_input_per_m = 0.5
        CONFIG.agentrouter.price_output_per_m = 1.5
        try:
            cost = prov.estimate_cost(1000, 100)
            self.assertGreater(cost, 0)
        finally:
            CONFIG.agentrouter.price_input_per_m = 0.0
            CONFIG.agentrouter.price_output_per_m = 0.0


class TestProviderSwitching(unittest.TestCase):
    def test_active_provider_selects_implementation(self):
        svc = Services()
        try:
            svc.credentials.set_key("deepseek", "sk-deep")
            svc.credentials.set_key("agentrouter", "ar-key")

            CONFIG.active_provider = "deepseek"
            self.assertIsInstance(svc.build_provider(), DeepSeekProvider)

            CONFIG.active_provider = "agentrouter"
            self.assertIsInstance(svc.build_provider(), AgentRouterProvider)

            # Switching back still works and each key is independent.
            CONFIG.active_provider = "deepseek"
            self.assertIsInstance(svc.build_provider(), DeepSeekProvider)
        finally:
            svc.credentials.delete_key("deepseek")
            svc.credentials.delete_key("agentrouter")
            CONFIG.active_provider = "deepseek"
            svc.close()

    def test_no_key_returns_none(self):
        svc = Services()
        try:
            svc.credentials.delete_key("agentrouter")
            CONFIG.active_provider = "agentrouter"
            self.assertIsNone(svc.build_provider())
        finally:
            CONFIG.active_provider = "deepseek"
            svc.close()


if __name__ == "__main__":
    unittest.main()
