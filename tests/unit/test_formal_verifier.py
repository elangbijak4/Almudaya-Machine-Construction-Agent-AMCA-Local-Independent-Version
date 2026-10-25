"""Unmocked unit & mutation tests for the 3-Stage Compositional Formal Verification Engine."""
from __future__ import annotations

import copy
import unittest
from pathlib import Path

from amca.verifier import verify_candidate
from amca_agent.formal_verifier import verify_formal_spec, verify_revision_invariants
from amca_agent.system_spec import load_system_spec, validate_system_spec_mapping

ROOT = Path(__file__).resolve().parents[2]


class FormalVerifierTests(unittest.TestCase):
    def setUp(self):
        self.valid_spec = load_system_spec(ROOT / "examples" / "valid_machine_system_v1alpha1.yaml")

    def test_stage1_proves_valid_reference_system(self):
        cert = verify_formal_spec(self.valid_spec)
        self.assertEqual(cert.overall_status, "PROVED")
        self.assertEqual(cert.stage1_spec_proof["status"], "PROVED")
        self.assertEqual(cert.stage1_spec_proof["checks_passed"], 5)
        self.assertEqual(len(cert.counterexamples), 0)
        by_id = {o.id: o.status for o in cert.obligations}
        self.assertEqual(by_id["FO-TOP-01"], "PROVED")
        self.assertEqual(by_id["FO-CON-01"], "PROVED")
        self.assertEqual(by_id["FO-HOA-01"], "PROVED")
        self.assertEqual(by_id["FO-GOAL-01"], "PROVED")
        self.assertEqual(by_id["FO-SEC-01"], "PROVED")

    def test_hoare_entailment_refutes_bypassing_validate_text_even_when_port_types_match(self):
        """Crucial researcher test: input_source.text -> analysis_a.text matches port type 'string',
        but violates Hoare precondition 'non_empty_trimmed' because validate_text was bypassed."""
        d = copy.deepcopy(self.valid_spec.as_dict())
        # Remove validate machine and wire input directly to analysis_a and analysis_b
        d["machines"] = [m for m in d["machines"] if m["id"] != "validate"]
        d["connections"] = [
            {"from": {"machine": "input", "output": "text"}, "to": {"machine": "analysis_a", "input": "text"}},
            {"from": {"machine": "input", "output": "text"}, "to": {"machine": "analysis_b", "input": "text"}},
            {"from": {"machine": "analysis_a", "output": "finding"}, "to": {"machine": "aggregate", "input": "finding_a"}},
            {"from": {"machine": "analysis_b", "output": "finding"}, "to": {"machine": "aggregate", "input": "finding_b"}},
            {"from": {"machine": "aggregate", "output": "summary"}, "to": {"machine": "report", "input": "summary"}},
        ]
        bypassed_spec = validate_system_spec_mapping(d)
        # Structural verifier sees valid port types (string -> string)
        self.assertEqual(verify_candidate(bypassed_spec.to_candidate_graph()).status, "verified")

        # Formal verifier Stage 1 MUST refute FO-HOA-01 and emit concrete counterexample witness
        cert = verify_formal_spec(bypassed_spec)
        self.assertEqual(cert.overall_status, "REFUTED")
        by_id = {o.id: o.status for o in cert.obligations}
        self.assertEqual(by_id["FO-HOA-01"], "REFUTED")
        self.assertTrue(any(c.obligation_id == "FO-HOA-01" for c in cert.counterexamples))
        hoa_cex = next(c for c in cert.counterexamples if c.obligation_id == "FO-HOA-01")
        self.assertIn("non_empty_trimmed", hoa_cex.witness["missing_predicates"])
        self.assertEqual(hoa_cex.witness["counterexample_witness"]["text"], "   ")

    def test_taint_non_interference_refutes_secret_ref_reaching_sink(self):
        d = copy.deepcopy(self.valid_spec.as_dict())
        d["machines"][0]["services"] = [{"name": "ext", "kind": "api", "secretRef": "AMCA_SECRET_TOKEN"}]
        tainted_spec = validate_system_spec_mapping(d)
        cert = verify_formal_spec(tainted_spec)
        self.assertEqual(cert.overall_status, "REFUTED")
        by_id = {o.id: o.status for o in cert.obligations}
        self.assertEqual(by_id["FO-SEC-01"], "REFUTED")

    def test_stage2_evolution_detects_dropped_formal_goals(self):
        d2 = copy.deepcopy(self.valid_spec.as_dict())
        d2["metadata"]["revision"] = 2
        d2["intent"]["acceptanceCriteria"] = [d2["intent"]["acceptanceCriteria"][0]]  # Drop AC-SYS-2
        rev2_spec = validate_system_spec_mapping(d2)

        obligation, cex = verify_revision_invariants(self.valid_spec, rev2_spec)
        self.assertEqual(obligation.status, "REFUTED")
        self.assertIsNotNone(cex)
        self.assertIn("report_contains_summary", cex.witness["dropped_goals"])


if __name__ == "__main__":
    unittest.main()
