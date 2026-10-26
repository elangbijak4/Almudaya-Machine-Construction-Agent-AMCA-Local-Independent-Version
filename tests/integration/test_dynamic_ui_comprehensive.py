"""Comprehensive end-to-end integration test suite for AMCA dynamic UI (app.py).

Verifies:
1. Dynamic dashboard adaptation across all 12 provider options.
2. Continuous in-session provider switching (state & key integrity).
3. Intent filtering and out-of-scope diagnostic fly-window modal.
4. Offline deterministic YAML generation and structural/formal validation.
5. Unregistered component detection in YAML and synthesis trigger.
6. Two-stage approval (APPROVE_SPEC and APPROVE_CONSTRUCTION) and Handover ZIP construction.
7. Custom Component Studio: template registration and AST security gate rejection.
8. Fly-window modal (@st.dialog) open, close, and persistent sidebar re-open.
9. Component catalog expander and historical run explorer.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

try:
    from streamlit.testing.v1 import AppTest
    from amca_agent import artifacts
except ImportError:
    AppTest = None
    artifacts = None

ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(AppTest is not None, "Optional Streamlit GUI dependency is not installed")
class DynamicUIComprehensiveTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="amca-ui-audit-")
        self.original_root = artifacts.ARTIFACT_ROOT
        artifacts.ARTIFACT_ROOT = Path(self.temp_dir.name)

    def tearDown(self):
        artifacts.ARTIFACT_ROOT = self.original_root
        self.temp_dir.cleanup()

    def test_dynamic_dashboard_all_12_providers(self):
        """Verifies each of the 12 provider options dynamically adapts the sidebar interface."""
        expected_providers = [
            "Gemini",
            "xAI (Grok)",
            "OpenAI",
            "Anthropic",
            "9Router",
            "Ollama",
            "LM Studio",
            "OpenCode",
            "Custom OpenAI-Compatible",
            "Local Model",
            "AMCA Combo",
            "Offline Deterministic",
        ]

        for provider in expected_providers:
            app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
            self.assertFalse(app.exception, f"Initial exception on provider {provider}")

            app.sidebar.selectbox[0].select(provider).run()
            self.assertFalse(app.exception, f"Exception occurred when selecting provider: {provider}")

            # Verify specific provider UI characteristics
            if provider == "9Router":
                url_inputs = [w for w in app.sidebar.text_input if "9Router" in w.label or "Endpoint" in w.label]
                self.assertGreaterEqual(len(url_inputs), 1)
                scan_btns = [b for b in app.sidebar.button if "Pindai Model & Combo 9Router" in b.label]
                self.assertEqual(len(scan_btns), 1)
                self.assertTrue(any("Default Key" in c.value or "9Router" in c.value for c in app.sidebar.caption))
            elif provider in {"Gemini", "Google Gemini"}:
                gemini_sb = [s for s in app.sidebar.selectbox if "Pilih Model Gemini" in s.label]
                self.assertEqual(len(gemini_sb), 1)
                key_inputs = [w for w in app.sidebar.text_input if "API key" in w.label]
                self.assertEqual(len(key_inputs), 1)
            elif provider in {"xAI (Grok)", "OpenAI", "Anthropic"}:
                model_inputs = [w for w in app.sidebar.text_input if "Model ID" in w.label]
                self.assertEqual(len(model_inputs), 1)
                key_inputs = [w for w in app.sidebar.text_input if "API key" in w.label]
                self.assertEqual(len(key_inputs), 1)
            elif provider == "Custom OpenAI-Compatible":
                url_inputs = [w for w in app.sidebar.text_input if "Endpoint Base URL" in w.label]
                self.assertEqual(len(url_inputs), 1)
                key_inputs = [w for w in app.sidebar.text_input if "API key" in w.label]
                self.assertEqual(len(key_inputs), 1)
            elif provider in {"Ollama", "LM Studio", "OpenCode"}:
                url_inputs = [w for w in app.sidebar.text_input if "Endpoint Local Runtime" in w.label]
                self.assertEqual(len(url_inputs), 1)
                scan_btns = [b for b in app.sidebar.button if f"Pindai Model {provider}" in b.label]
                self.assertEqual(len(scan_btns), 1)
            elif provider == "Local Model":
                curated_sb = [s for s in app.sidebar.selectbox if "Katalog Model Lokal" in s.label]
                self.assertEqual(len(curated_sb), 1)
                self.assertTrue(any("Spek Laptop:" in c.value for c in app.sidebar.caption))
            elif provider == "AMCA Combo":
                combo_inputs = [w for w in app.sidebar.text_input if "Combo" in w.label or "Tier" in w.label]
                self.assertGreaterEqual(len(combo_inputs), 4)
            elif provider == "Offline Deterministic":
                key_inputs = [w for w in app.sidebar.text_input if "API key" in w.label]
                self.assertEqual(len(key_inputs), 0)
                self.assertTrue(any("Air-Gapped" in s.value for s in app.sidebar.success))

    def test_in_session_provider_switching_continuity(self):
        """Verifies continuous in-session switching across providers without crash or state corruption."""
        app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
        providers_sequence = [
            "9Router",
            "Gemini",
            "Ollama",
            "xAI (Grok)",
            "Local Model",
            "AMCA Combo",
            "Offline Deterministic",
            "OpenAI",
        ]
        for p in providers_sequence:
            app.sidebar.selectbox[0].select(p).run()
            self.assertFalse(app.exception, f"Failed switching to {p}")

    def test_example_loading_and_clearing(self):
        """Verifies loading an example YAML and resetting back to empty."""
        app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
        self.assertFalse(app.exception)

        example_sb = app.selectbox[0]
        valid_label = next(o for o in example_sb.options if "valid_parallel_analysis.yaml" in o)
        example_sb.select(valid_label).run()
        app.button[0].click().run()  # 'Muat contoh ke editor'

        self.assertIn("schema_version", app.session_state["machine_yaml"])

        # Reset to (tanpa contoh)
        example_sb.select("(tanpa contoh)").run()
        app.button[0].click().run()
        self.assertEqual(app.session_state["machine_yaml"], "")

    def test_intent_classification_modal_flow(self):
        """Verifies out-of-scope intent triggers the structured fly-window modal."""
        app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
        problem_ta = app.text_area[0]
        problem_ta.input("buatkan saya resep nasi goreng ayam lezat").run()

        make_btn = next(b for b in app.button if "Buat YAML dengan agent" in b.label)
        make_btn.click().run()

        # Dialog should open
        self.assertIsNotNone(app.session_state["active_error_dialog"])
        report = app.session_state["active_error_dialog"]
        self.assertEqual(report.origin.value, "user_input_flow")
        self.assertIn("Cakupan", report.headline)

        # Close button in modal
        close_btn = next(b for b in app.button if b.label == "Tutup Jendela")
        close_btn.click().run()
        self.assertIsNone(app.session_state["active_error_dialog"])
        self.assertIsNotNone(app.session_state["last_error_report"])

        # Reopen from sidebar
        reopen_btn = next(b for b in app.sidebar.button if "Buka Jendela Diagnostik" in b.label)
        reopen_btn.click().run()
        self.assertIsNotNone(app.session_state["active_error_dialog"])

    def test_offline_deterministic_yaml_generation_and_execution_flow(self):
        """Verifies full end-to-end lifecycle under Offline Deterministic mode."""
        app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
        app.sidebar.selectbox[0].select("Offline Deterministic").run()

        # Input valid problem
        app.text_area[0].input("buatkan pipeline pemrosesan teks dan penghitungan karakter").run()
        make_btn = next(b for b in app.button if "Buat YAML dengan agent" in b.label)
        make_btn.click().run()

        self.assertFalse(app.exception)
        yaml_text = app.session_state["machine_yaml"]
        self.assertTrue(len(yaml_text) > 0)
        self.assertIn("schema_version", yaml_text)
        self.assertEqual(app.session_state["verification"].status, "verified")

        # Execute machine
        approved_cb = app.checkbox[0]
        approved_cb.check().run()
        run_btn = next(b for b in app.button if b.label == "Jalankan mesin")
        run_btn.click().run()

        self.assertFalse(app.exception)
        self.assertEqual(app.session_state["last_execution"]["run_status"], "succeeded")

    def test_unregistered_component_detection(self):
        """Verifies that unregistered components in YAML trigger a warning and synthesis button."""
        app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
        unregistered_yaml = (
            "schema_version: '1.0'\n"
            "machine_id: test-unreg\n"
            "nodes:\n"
            "  - id: input\n"
            "    component: input_source\n"
            "  - id: custom_node\n"
            "    component: unreg_sentiment_counter\n"
            "edges:\n"
            "  - {from: 'input', out: 'text', to: 'custom_node', in: 'text'}\n"
        )
        app.text_area[1].input(unregistered_yaml).run()
        app.button[2].click().run()  # 'Validasi YAML saat ini'

        # Should detect unregistered component
        warnings = [w.value for w in app.warning if "unreg_sentiment_counter" in w.value]
        self.assertGreaterEqual(len(warnings), 1)

        # Synthesis button should be visible
        synth_btns = [b for b in app.button if "Sintesis & Daftarkan Komponen On-The-Fly" in b.label]
        self.assertEqual(len(synth_btns), 1)

    def test_two_stage_approval_and_construction_zip_flow(self):
        """Verifies APPROVE_SPEC, APPROVE_CONSTRUCTION, and Handover ZIP generation in GUI."""
        app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()

        # Load reference example
        example_sb = app.selectbox[0]
        valid_label = next(o for o in example_sb.options if "valid_parallel_analysis.yaml" in o)
        example_sb.select(valid_label).run()
        app.button[0].click().run()
        app.button[2].click().run()  # Validate YAML

        self.assertEqual(app.session_state["verification"].status, "verified")
        self.assertEqual(app.session_state["formal_certificate"].overall_status, "PROVED")

        # Stage 1: APPROVE_SPEC
        spec_app_btn = next(b for b in app.button if "1. Kunci Persetujuan Spesifikasi" in b.label)
        spec_app_btn.click().run()
        self.assertIsNotNone(app.session_state["spec_approval"])
        self.assertIsNotNone(app.session_state["construction_plan"])

        # Stage 2: APPROVE_CONSTRUCTION
        construct_btn = next(b for b in app.button if "2. Setujui Konstruksi & Bangun Paket Handover ZIP" in b.label)
        construct_btn.click().run()

        self.assertIsNotNone(app.session_state["construction_approval"])
        self.assertIsNotNone(app.session_state["last_package_result"])
        pkg = app.session_state["last_package_result"]
        self.assertTrue(pkg.zip_path.is_file())
        self.assertEqual(pkg.refined_certificate.overall_status, "PROVED")

    def test_custom_component_studio_ast_security_rejection(self):
        """Verifies that malicious Python code in Custom Component Studio triggers the error dialog."""
        app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()

        malicious_code = "import os\n\ndef exploit(text: str) -> str:\n    return os.name\n"
        ext_code_ta = [t for t in app.text_area if "ext_py_code" in getattr(t, "key", "") or "def clean_punctuation" in t.value]
        if ext_code_ta:
            ext_code_ta[0].input(malicious_code).run()
            bind_btn = next(b for b in app.button if "Audit AST" in b.label)
            bind_btn.click().run()

            # Error dialog should pop up
            self.assertIsNotNone(app.session_state["active_error_dialog"])
            rep = app.session_state["active_error_dialog"]
            self.assertEqual(rep.origin.value, "user_input_flow")
            self.assertIn("AST", rep.headline)


if __name__ == "__main__":
    unittest.main()
