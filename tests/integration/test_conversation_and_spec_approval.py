"""Integration tests for conversational greeting, intent scope boundary, formal proof CLI, and Stage 1 spec approval."""
from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from amca_agent import artifacts, cli

ROOT = Path(__file__).resolve().parents[2]
VALID_V1 = (ROOT / "examples" / "valid_parallel_analysis.yaml").read_text(encoding="utf-8")
VALID_V1ALPHA1 = (ROOT / "examples" / "valid_machine_system_v1alpha1.yaml").read_text(encoding="utf-8")


class ConversationAndSpecApprovalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.artifact_root = Path(self.temp.name) / "artifacts"
        self.patch_artifacts = mock.patch.object(artifacts, "ARTIFACT_ROOT", self.artifact_root)
        self.patch_cli_artifacts = mock.patch.object(cli, "ARTIFACT_ROOT", self.artifact_root)
        self.patch_artifacts.start()
        self.patch_cli_artifacts.start()
        self.addCleanup(self.patch_artifacts.stop)
        self.addCleanup(self.patch_cli_artifacts.stop)

    def invoke(self, *args: str) -> tuple[int, str]:
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            code = cli.main(list(args))
        return code, output.getvalue()

    def test_opening_greeting_and_out_of_scope_rejection_in_chat(self) -> None:
        with mock.patch("builtins.input", side_effect=["Tolong buatkan resep masakan nasi goreng"]):
            code, out = self.invoke("chat")
        self.assertEqual(code, 2)
        self.assertIn("Mesin/agent apakah yang Anda ingin buat?", out)
        self.assertIn("luar cakupan", out)

    def test_formal_verify_and_hardware_check_and_combo_subcommands(self) -> None:
        spec_path = Path(self.temp.name) / "sys.yaml"
        spec_path.write_text(VALID_V1ALPHA1, encoding="utf-8")
        cert_out = Path(self.temp.name) / "cert.json"

        code, _ = self.invoke("formal-verify", str(spec_path), "--output", str(cert_out))
        self.assertEqual(code, 0)
        cert_data = json.loads(cert_out.read_text(encoding="utf-8"))
        self.assertEqual(cert_data["overall_status"], "PROVED")
        self.assertEqual(cert_data["stage1_spec_proof"]["status"], "PROVED")

        code_hw, hw_out = self.invoke("hardware-check", "--model", "qwen2.5-coder-1.5b-instruct-q4_k_m.gguf")
        self.assertIn(code_hw, (0, 1))
        hw_data = json.loads(hw_out)
        self.assertIn("ram_total_mb", hw_data)
        self.assertGreater(hw_data["ram_total_mb"], 0)

        code_combo, combo_out = self.invoke(
            "combo-config",
            "--name",
            "research-combo",
            "--tiers",
            "nine_router:free-combo,ollama:qwen2.5-coder:7b,offline_deterministic:builtin-v1",
        )
        self.assertEqual(code_combo, 0)
        combo_data = json.loads(combo_out)
        self.assertEqual(combo_data["combo_id"], "research-combo")
        self.assertEqual(len(combo_data["tiers"]), 3)

    def test_chat_proof_and_approve_spec_workflow(self) -> None:
        inputs = [
            "Buat sistem analisis teks paralel",
            "proof",
            "approve-spec",
            "WRONG_TOKEN",
            "approve-spec",
            "APPROVE_SPEC",
            "quit",
        ]
        with mock.patch.object(cli, "_generate", return_value=VALID_V1), mock.patch("builtins.input", side_effect=inputs):
            code, out = self.invoke("chat")
        self.assertEqual(code, 0)
        self.assertIn("Mesin/agent apakah yang Anda ingin buat?", out)
        self.assertIn("Persetujuan spesifikasi ditolak", out)
        self.assertIn("Spesifikasi disetujui: spec-approval-", out)


if __name__ == "__main__":
    unittest.main()
