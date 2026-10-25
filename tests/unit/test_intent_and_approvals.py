"""Unmocked unit tests for Intent Classifier, Two-Stage Approvals, and Cost-Minimizing Planner."""
from __future__ import annotations

import unittest
from pathlib import Path

from amca.verifier import verify_candidate
from amca_agent.approvals import record_construction_approval, record_spec_approval
from amca_agent.formal_verifier import verify_formal_spec
from amca_agent.intent import OPENING_GREETING, classify_intent
from amca_agent.planner import build_construction_plan
from amca_agent.system_spec import load_system_spec

ROOT = Path(__file__).resolve().parents[2]


class IntentAndApprovalsTests(unittest.TestCase):
    def test_intent_classifier_accepts_machine_requests_and_rejects_out_of_scope(self):
        self.assertEqual(OPENING_GREETING, "Mesin/agent apakah yang Anda ingin buat?")
        in_scope = classify_intent("Buat mesin analisis teks untuk menghitung kata dan karakter.")
        self.assertEqual(in_scope.status, "in_scope")
        self.assertTrue(in_scope.allowed)

        out = classify_intent("Tolong berikan resep masakan nasi goreng spesial.")
        self.assertEqual(out.status, "out_of_scope")
        self.assertFalse(out.allowed)
        self.assertIn("luar cakupan AMCA", out.boundary_message or "")

        empty = classify_intent("   ")
        self.assertEqual(empty.status, "needs_clarification")

    def test_two_stage_approvals_enforce_verified_and_proved_status_and_sha256_binding(self):
        spec = load_system_spec(ROOT / "examples" / "valid_machine_system_v1alpha1.yaml")
        candidate = spec.to_candidate_graph()
        verification = verify_candidate(candidate)
        cert = verify_formal_spec(spec)

        with self.assertRaises(PermissionError):
            record_spec_approval(
                session_id="sess-1",
                revision=1,
                candidate=candidate,
                verification=verification,
                formal_certificate=cert,
                confirmation_token="WRONG_TOKEN",
            )

        app_a = record_spec_approval(
            session_id="sess-1",
            revision=1,
            candidate=candidate,
            verification=verification,
            formal_certificate=cert,
            confirmation_token="APPROVE_SPEC",
        )
        self.assertEqual(app_a.specification_sha256, candidate.specification_sha256)
        self.assertEqual(app_a.certificate_sha256, cert.certificate_sha256)

        app_b = record_construction_approval(
            spec_approval=app_a,
            candidate=candidate,
            formal_certificate=cert,
            confirmation_token="APPROVE_CONSTRUCTION",
        )
        self.assertIn("reference-text-analysis-rev001", app_b.destination_dir)

    def test_planner_defaults_to_minimize_cost_and_records_environments(self):
        spec = load_system_spec(ROOT / "examples" / "valid_machine_system_v1alpha1.yaml")
        candidate = spec.to_candidate_graph()
        plan = build_construction_plan(candidate, revision=1, sys_spec=spec)
        self.assertEqual(plan.worker_policy, "minimize-cost")
        self.assertFalse(plan.use_subagents)
        self.assertEqual(len(plan.proposed_subworkers), 0)
        self.assertIn("python", plan.builder_environment)
        self.assertIn("os", plan.target_environment)

        plan_with_sub = build_construction_plan(candidate, revision=1, sys_spec=spec, propose_subworker=True)
        self.assertTrue(plan_with_sub.use_subagents)
        self.assertEqual(len(plan_with_sub.proposed_subworkers), 1)
        self.assertEqual(plan_with_sub.proposed_subworkers[0].subworker_id, "subworker-formal-auditor-01")


if __name__ == "__main__":
    unittest.main()
