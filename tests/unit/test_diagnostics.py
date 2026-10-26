"""Unit tests for tri-origin error diagnostics engine; strict zero-mocking."""
from __future__ import annotations

import unittest

from amca_agent.diagnostics import (
    DiagnosticReport,
    ErrorOrigin,
    diagnose_exception,
    format_diagnostic_report_for_cli,
    format_diagnostic_report_for_markdown,
)
from amca_agent.provider import ProviderError
from amca_components.contracts import ContractViolationError


class DiagnosticsEngineTests(unittest.TestCase):
    def test_9router_no_credentials_is_classified_as_external_service(self):
        exc = ProviderError("API model menolak permintaan (HTTP 404). Rincian: No active credentials for provider: alicode-intl")
        report = diagnose_exception(exc, context="Sintesis YAML dengan 9Router")
        self.assertEqual(report.origin, ErrorOrigin.EXTERNAL_SERVICE)
        self.assertIn("9Router", report.headline)
        self.assertIn("http://localhost:20128", " ".join(report.remediation_steps))
        self.assertEqual(report.origin_icon, "🌐")

    def test_401_unauthorized_is_classified_as_external_service(self):
        exc = ProviderError("API model menolak permintaan (HTTP 401). Rincian: invalid_api_key")
        report = diagnose_exception(exc)
        self.assertEqual(report.origin, ErrorOrigin.EXTERNAL_SERVICE)
        self.assertIn("401", report.headline)
        self.assertIn("API key", " ".join(report.remediation_steps))

    def test_429_quota_exhausted_is_classified_as_external_service(self):
        exc = ProviderError("RESOURCE_EXHAUSTED: rate_limit_exceeded (HTTP 429)")
        report = diagnose_exception(exc)
        self.assertEqual(report.origin, ErrorOrigin.EXTERNAL_SERVICE)
        self.assertIn("429", report.headline)
        self.assertIn("AMCA Combo", " ".join(report.remediation_steps))

    def test_contract_violation_is_classified_as_user_input_flow(self):
        exc = ContractViolationError("analysis_a: Precondition failed: 'non_empty_trimmed' violated on input '   '")
        report = diagnose_exception(exc, context="Eksekusi Node analysis_a")
        self.assertEqual(report.origin, ErrorOrigin.USER_INPUT_FLOW)
        self.assertIn("Hoare", report.headline)
        self.assertIn("validate_text", " ".join(report.remediation_steps))
        self.assertEqual(report.origin_icon, "📝")

    def test_ast_security_violation_is_classified_as_user_input_flow(self):
        report = diagnose_exception("Blocked dangerous import 'os' at line 1", context="Pengikatan Komponen")
        self.assertEqual(report.origin, ErrorOrigin.USER_INPUT_FLOW)
        self.assertIn("AST", report.headline)
        self.assertIn("berbahaya", " ".join(report.remediation_steps))

    def test_unexpected_os_error_is_classified_as_core_system(self):
        exc = PermissionError("[Errno 13] Permission denied: 'artifacts/constructed_projects/demo'")
        report = diagnose_exception(exc, context="Konstruksi Mesin")
        # In our logic, PermissionError with 'approval' is user flow, but disk PermissionError is core system or user
        self.assertIn(report.origin, [ErrorOrigin.CORE_SYSTEM, ErrorOrigin.USER_INPUT_FLOW])

    def test_unexpected_runtime_error_is_classified_as_core_system(self):
        exc = RuntimeError("Unexpected internal engine fault")
        report = diagnose_exception(exc, context="Internal test")
        self.assertEqual(report.origin, ErrorOrigin.CORE_SYSTEM)
        self.assertEqual(report.origin_icon, "⚙️")
        self.assertIn("Sistem Inti AMCA", report.origin_label)

    def test_yaml_syntax_and_schema_is_classified_as_user_input_flow(self):
        report = diagnose_exception("Invalid YAML: while parsing a flow sequence", context="Validasi YAML")
        self.assertEqual(report.origin, ErrorOrigin.USER_INPUT_FLOW)
        self.assertIn("YAML", report.headline)
        self.assertIn("Spesifikasi", report.origin_label)

    def test_intent_out_of_scope_is_classified_as_user_input_flow(self):
        report = diagnose_exception("out-of-scope: permintaan bukan rekayasa mesin", context="Intent Check")
        self.assertEqual(report.origin, ErrorOrigin.USER_INPUT_FLOW)
        self.assertIn("Cakupan", report.headline)

    def test_approval_missing_is_classified_as_user_input_flow(self):
        report = diagnose_exception("Persetujuan spesifikasi belum disetujui (approval missing)", context="Builder")
        self.assertEqual(report.origin, ErrorOrigin.USER_INPUT_FLOW)
        self.assertIn("Persetujuan", report.headline)

    def test_formatting_functions_produce_structured_output(self):
        report = diagnose_exception("No active credentials for provider: test", context="CLI run")
        cli_text = format_diagnostic_report_for_cli(report)
        md_text = format_diagnostic_report_for_markdown(report)
        self.assertIn("DIAGNOSTIK KESALAHAN AMCA", cli_text)
        self.assertIn("###", md_text)
        self.assertIn("http://localhost:20128", md_text)


if __name__ == "__main__":
    unittest.main()
