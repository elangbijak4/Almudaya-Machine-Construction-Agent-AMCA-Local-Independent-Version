"""Provider request/response contract tests; no external API calls are made."""
from __future__ import annotations

import json
import unittest
import urllib.error
from unittest import mock

from amca_agent.provider import ProviderError, generate_yaml, inspect_provider_runtime_status


class _Response:
    def __init__(self, body: dict):
        self.body = json.dumps(body).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, limit: int):
        return self.body


class ProviderAdapterTests(unittest.TestCase):
    def test_gemini_request_uses_header_and_strips_yaml_fence(self):
        response = _Response({"candidates": [{"content": {"parts": [{"text": "```yaml\nschema_version: '1.0'\n```"}]}}]})
        with mock.patch("amca_agent.provider.urllib.request.urlopen", return_value=response) as urlopen:
            result = generate_yaml(provider="Gemini", model="test-model", api_key="secret-value",
                                   prompt="make a machine", history=[], current_yaml="current")
        request = urlopen.call_args.args[0]
        self.assertIn("generativelanguage.googleapis.com", request.full_url)
        self.assertEqual(request.get_header("X-goog-api-key"), "secret-value")
        self.assertEqual(result, "schema_version: '1.0'")
        self.assertNotIn(b"secret-value", request.data)

    def test_openai_compatible_provider_uses_bearer_auth_and_prompt_context(self):
        response = _Response({"choices": [{"message": {"content": "schema_version: '1.0'"}}]})
        with mock.patch("amca_agent.provider.urllib.request.urlopen", return_value=response) as urlopen:
            result = generate_yaml(provider="OpenAI", model="test-model", api_key="secret-value",
                                   prompt="count words", history=[{"role": "user", "content": "prior request"}],
                                   current_yaml="machine_id: old")
        request = urlopen.call_args.args[0]
        payload = json.loads(request.data)
        self.assertEqual(request.full_url, "https://api.openai.com/v1/chat/completions")
        self.assertEqual(request.get_header("Authorization"), "Bearer secret-value")
        self.assertIn("prior request", payload["messages"][1]["content"])
        self.assertIn("machine_id: old", payload["messages"][1]["content"])
        self.assertEqual(result, "schema_version: '1.0'")

    def test_xai_endpoint_and_provider_errors_do_not_expose_credentials(self):
        response = _Response({"choices": [{"message": {"content": "machine_id: test"}}]})
        with mock.patch("amca_agent.provider.urllib.request.urlopen", return_value=response) as urlopen:
            self.assertEqual(generate_yaml(provider="xAI (Grok)", model="grok-test", api_key="secret-value",
                                            prompt="draw", history=[]), "machine_id: test")
        self.assertEqual(urlopen.call_args.args[0].full_url, "https://api.x.ai/v1/chat/completions")

        error = urllib.error.HTTPError("https://api.x.ai", 401, "bad key", {}, None)
        with mock.patch("amca_agent.provider.urllib.request.urlopen", side_effect=error):
            with self.assertRaises(ProviderError) as raised:
                generate_yaml(provider="OpenAI", model="test", api_key="secret-value", prompt="x", history=[])
        self.assertNotIn("secret-value", str(raised.exception))
        self.assertIn("HTTP 401", str(raised.exception))

    def test_inspect_provider_runtime_status_returns_structured_diagnostics(self):
        # 1. 9Router status probe
        res_9r = inspect_provider_runtime_status("9router")
        self.assertIn("reachable", res_9r)
        self.assertIn("status_badge", res_9r)
        self.assertIn("active_accounts", res_9r)
        self.assertIn("combos", res_9r)

        # 2. Ollama status probe
        res_ollama = inspect_provider_runtime_status("ollama")
        self.assertIn("reachable", res_ollama)
        self.assertIn("status_badge", res_ollama)

        # 3. LM Studio probe
        res_lms = inspect_provider_runtime_status("lm_studio")
        self.assertIn("reachable", res_lms)
        self.assertIn("status_badge", res_lms)


if __name__ == "__main__":
    unittest.main()
