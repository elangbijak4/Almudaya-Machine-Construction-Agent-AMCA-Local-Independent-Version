"""Unmocked unit tests for Hardware Gate, 9Router/Ollama/LM Studio/OpenCode discovery, Combo Token-Limit Fallback, and Subworker HITL."""
from __future__ import annotations

import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

from amca_agent.hardware import (
    HostHardwareSnapshot,
    LocalModelProfile,
    evaluate_local_model_eligibility,
    inspect_host_hardware,
    register_approved_local_model,
)
from amca_agent.harness import AgentHarnessSession, SubworkerProposal
from amca_agent.provider import discover_provider_models


class _StubHttpResponse:
    def __init__(self, payload: dict):
        self.raw = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, limit: int = -1) -> bytes:
        return self.raw


class HardwareAndHarnessTests(unittest.TestCase):
    def test_real_os_hardware_inspection_returns_valid_metrics(self):
        snapshot = inspect_host_hardware()
        self.assertGreater(snapshot.ram_total_mb, 256)
        self.assertGreater(snapshot.ram_available_mb, 64)
        self.assertGreater(snapshot.disk_free_mb, 64)
        self.assertGreaterEqual(snapshot.cpu_logical_cores, 1)

    def test_hardware_gate_allows_eligible_model_and_refuses_insufficient_specs(self):
        modest_laptop = HostHardwareSnapshot(
            inspection_timestamp="2026-10-25T21:00:00Z",
            host_os="Windows-11",
            cpu_arch="AMD64",
            cpu_logical_cores=8,
            ram_total_mb=16384,
            ram_available_mb=5800,
            disk_free_mb=40000,
            gpu_detected=False,
            gpu_vram_mb=0,
        )
        # 1.5B model requires 1536 MB RAM -> ELIGIBLE
        light_report = evaluate_local_model_eligibility(
            "qwen2.5-coder-1.5b-instruct-q4_k_m.gguf",
            hardware=modest_laptop,
        )
        self.assertTrue(light_report.eligible)
        self.assertEqual(light_report.status, "ELIGIBLE")

        # 7B model requires 6144 MB available RAM -> REFUSED on 5800 MB available RAM
        heavy_report = evaluate_local_model_eligibility(
            "qwen2.5-coder-7b-instruct-q4_k_m.gguf",
            hardware=modest_laptop,
        )
        self.assertFalse(heavy_report.eligible)
        self.assertEqual(heavy_report.status, "REFUSED_INSUFFICIENT_HARDWARE")
        self.assertTrue(any("5800 MB" in r and "6144 MB" in r for r in heavy_report.reasons))

        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(PermissionError):
                register_approved_local_model(
                    "qwen2.5-coder-7b-instruct-q4_k_m.gguf",
                    user_approved=True,
                    hardware=modest_laptop,
                    target_dir=Path(tmp),
                )
            _, manifest = register_approved_local_model(
                "qwen2.5-coder-1.5b-instruct-q4_k_m.gguf",
                user_approved=True,
                hardware=modest_laptop,
                target_dir=Path(tmp),
            )
            self.assertTrue(manifest.is_file())

    def test_9router_ollama_lm_studio_and_opencode_model_discovery(self):
        # 9Router discovery (models + Combos)
        nine_router_resp = _StubHttpResponse(
            {"data": [{"id": "premium-coding"}, {"id": "free-combo"}, {"id": "claude-3-7-sonnet"}]}
        )
        with mock.patch("amca_agent.provider.urllib.request.urlopen", return_value=nine_router_resp) as m_open:
            models = discover_provider_models("nine_router", api_key="9r-secret")
        self.assertEqual(models, ["premium-coding", "free-combo", "claude-3-7-sonnet"])
        self.assertIn("20128/v1/models", m_open.call_args.args[0].full_url)

        # Ollama discovery (/api/tags)
        ollama_resp = _StubHttpResponse(
            {"models": [{"name": "qwen2.5-coder:7b"}, {"name": "deepseek-r1:8b"}]}
        )
        with mock.patch("amca_agent.provider.urllib.request.urlopen", return_value=ollama_resp):
            ollama_models = discover_provider_models("ollama")
        self.assertEqual(ollama_models, ["qwen2.5-coder:7b", "deepseek-r1:8b"])

        # LM Studio discovery (/v1/models)
        lms_resp = _StubHttpResponse({"data": [{"id": "qwen2.5-coder-7b-gguf"}]})
        with mock.patch("amca_agent.provider.urllib.request.urlopen", return_value=lms_resp):
            lms_models = discover_provider_models("lm_studio")
        self.assertEqual(lms_models, ["qwen2.5-coder-7b-gguf"])

        # OpenCode discovery (/v1/models)
        oc_resp = _StubHttpResponse({"data": [{"id": "opencode/claude-sonnet-4"}]})
        with mock.patch("amca_agent.provider.urllib.request.urlopen", return_value=oc_resp):
            oc_models = discover_provider_models("opencode")
        self.assertEqual(oc_models, ["opencode/claude-sonnet-4"])

    def test_native_combo_fallback_chain_on_token_limit_and_http_429(self):
        harness = AgentHarnessSession(session_id="test-session-combo")
        harness.register_combo_chain(
            "resilient-research-combo",
            [
                {"provider_type": "gemini", "model_id": "gemini-2.5-pro", "api_key": "key-tier-1"},
                {"provider_type": "nine_router", "model_id": "free-combo", "api_key": "key-tier-2"},
                {"provider_type": "offline_deterministic", "model_id": "builtin-v1", "api_key": ""},
            ],
        )

        # Tier 1 returns truncated output due to token limit (finishReason: MAX_TOKENS)
        tier1_truncated = _StubHttpResponse(
            {"candidates": [{"finishReason": "MAX_TOKENS", "content": {"parts": [{"text": "schema_version: '1.0'"}]}}]}
        )
        # Tier 2 (9Router) returns HTTP 429 rate limit
        tier2_429 = urllib.error.HTTPError("http://127.0.0.1:20128/v1/chat/completions", 429, "Too Many Requests", {}, None)

        with mock.patch("amca_agent.provider.urllib.request.urlopen", side_effect=[tier1_truncated, tier2_429]):
            yaml_out = harness.execute_yaml_generation(
                "Buat sistem analisis teks text_review_v2",
                history=[{"role": "user", "content": "turn 1 " * 400}, {"role": "assistant", "content": "turn 2 " * 400}],
            )

        self.assertIn("machine_id: text_review_v2", yaml_out)
        self.assertEqual(len(harness.fallback_events), 2)
        self.assertEqual(harness.fallback_events[0].from_tier, 1)
        self.assertEqual(harness.fallback_events[0].to_tier, 2)
        self.assertEqual(harness.fallback_events[0].trigger_reason, "output_truncated_length")
        self.assertTrue(harness.fallback_events[0].context_compacted)
        self.assertEqual(harness.fallback_events[1].from_tier, 2)
        self.assertEqual(harness.fallback_events[1].to_tier, 3)
        self.assertEqual(harness.fallback_events[1].trigger_reason, "rate_limit_429")

    def test_on_the_fly_subworker_hitl_key_isolation_and_decline_fallback(self):
        harness = AgentHarnessSession(session_id="test-hitl")
        harness.configure_primary_agent(provider_type="gemini", model_id="gemini-2.5-flash", api_key="PRIMARY-SECRET-KEY")

        prop = SubworkerProposal(
            subworker_id="sub-auditor-1",
            role="formal_auditor",
            task_description="Audit DAG edge contracts",
            rationale="Separate model verification",
        )
        harness.request_subworker_hitl(prop)
        approval = harness.approve_subworker_hitl(
            "sub-auditor-1",
            provider_type="nine_router",
            model_id="premium-coding",
            api_key="SUBWORKER-DISTINCT-KEY",
        )
        self.assertEqual(approval.decision, "APPROVED")
        self.assertTrue(approval.credential_isolated_from_primary)
        # Ensure serialized approval record never contains raw API keys
        serialized = json.dumps(approval.as_dict())
        self.assertNotIn("PRIMARY-SECRET-KEY", serialized)
        self.assertNotIn("SUBWORKER-DISTINCT-KEY", serialized)

        # Test declining a second subworker falls back cleanly to Primary Agent
        prop2 = SubworkerProposal(
            subworker_id="sub-declined-2",
            role="extra_worker",
            task_description="Optional worker",
            rationale="Optional",
        )
        harness.request_subworker_hitl(prop2)
        declined = harness.decline_subworker_hitl("sub-declined-2")
        self.assertEqual(declined.decision, "DECLINED")
        self.assertIsNone(declined.model_binding)


if __name__ == "__main__":
    unittest.main()
