"""Local Streamlit UI smoke test; Streamlit is an optional application dependency."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

try:
    from streamlit.testing.v1 import AppTest
    from amca_agent import artifacts
except ImportError:  # Base CLI installs do not include the optional GUI dependency.
    AppTest = None
    artifacts = None

ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(AppTest is not None, "Optional Streamlit GUI dependency is not installed")
class StreamlitAppTests(unittest.TestCase):
    def test_reference_machine_can_be_loaded_verified_and_run_from_gui(self):
        with tempfile.TemporaryDirectory(prefix="amca-streamlit-test-") as temp:
            original_root = artifacts.ARTIFACT_ROOT
            artifacts.ARTIFACT_ROOT = Path(temp)
            try:
                app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
                self.assertFalse(app.exception, [item.message for item in app.exception])

                label = next(value for value in app.selectbox[0].options if "valid_parallel_analysis.yaml" in value)
                app.selectbox[0].select(label).run()
                app.button[0].click().run()
                self.assertIn("schema_version", app.session_state["machine_yaml"])

                app.button[2].click().run()
                self.assertFalse(app.exception, [item.message for item in app.exception])
                self.assertEqual(app.session_state["verification"].status, "verified")
                self.assertTrue(any("VERIFIED" in item.value for item in app.success))

                app.checkbox[0].check().run()
                next(button for button in app.button if button.label == "Jalankan mesin").click().run()
                self.assertFalse(app.exception, [item.message for item in app.exception])
                self.assertEqual(app.session_state["last_execution"]["run_status"], "succeeded")
                summaries = [record["output_summary"].get("safe_summary", {})
                             for record in app.session_state["last_execution"]["node_records"]]
                self.assertIn({"summary": "characters=20; words=4"}, summaries)
            finally:
                artifacts.ARTIFACT_ROOT = original_root

    def test_diagnostic_fly_window_and_reopen_workflow(self):
        with tempfile.TemporaryDirectory(prefix="amca-streamlit-diag-test-") as temp:
            original_root = artifacts.ARTIFACT_ROOT
            artifacts.ARTIFACT_ROOT = Path(temp)
            try:
                app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
                self.assertFalse(app.exception, [item.message for item in app.exception])
                self.assertIsNone(app.session_state["active_error_dialog"])
                self.assertIsNone(app.session_state["last_error_report"])

                # Input invalid YAML to trigger validation diagnostics
                app.text_area[1].input("invalid_yaml: [broken flow sequence").run()
                app.button[2].click().run()

                diag_btns = [b for b in app.button if "Diagnosa Masalah Validasi" in b.label]
                self.assertEqual(len(diag_btns), 1)

                # Click diagnosis button to open fly-window dialog
                diag_btns[0].click().run()
                self.assertIsNotNone(app.session_state["active_error_dialog"])
                report = app.session_state["active_error_dialog"]
                self.assertEqual(report.origin.value, "user_input_flow")
                self.assertIn("YAML", report.headline)

                # Close dialog via Tutup Jendela button
                close_btns = [b for b in app.button if b.label == "Tutup Jendela"]
                self.assertEqual(len(close_btns), 1)
                close_btns[0].click().run()
                self.assertIsNone(app.session_state["active_error_dialog"])
                self.assertIsNotNone(app.session_state["last_error_report"])

                # Re-open dialog via persistent sidebar button
                reopen_btns = [b for b in app.sidebar.button if "Buka Jendela Diagnostik" in b.label]
                self.assertEqual(len(reopen_btns), 1)
                reopen_btns[0].click().run()
                self.assertIsNotNone(app.session_state["active_error_dialog"])
                self.assertEqual(app.session_state["active_error_dialog"].headline, report.headline)
            finally:
                artifacts.ARTIFACT_ROOT = original_root


if __name__ == "__main__":
    unittest.main()
