"""Integration & mutation tests for Stage 3 AST code refinement, secret redaction, and Handover ZIP packaging."""
from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from amca.verifier import verify_candidate
from amca_agent import cli
from amca_agent.approvals import record_construction_approval, record_spec_approval
from amca_agent.builder import build_constructed_project
from amca_agent.formal_verifier import verify_code_refinement, verify_formal_spec
from amca_agent.harness import AgentHarnessSession, SubworkerProposal
from amca_agent.packager import verify_and_package_project
from amca_agent.planner import generate_construction_plan
from amca_agent.system_spec import load_any_spec_to_candidate

ROOT = Path(__file__).resolve().parents[2]
VALID_YAML = (ROOT / "examples" / "valid_machine_system_v1alpha1.yaml").read_text(encoding="utf-8")


class ConstructionAndZipTests(unittest.TestCase):
    def test_end_to_end_construction_stage3_proof_zip_and_secret_redaction(self) -> None:
        candidate, sys_spec = load_any_spec_to_candidate(VALID_YAML.encode("utf-8"))
        verification = verify_candidate(candidate)
        cert = verify_formal_spec(VALID_YAML.encode("utf-8"))

        # Configure harness with multiple secret keys (Primary, Combo Tiers, and Subworker)
        harness = AgentHarnessSession(session_id="sess-sec-test")
        primary_secret = "sk-PRIMARY-SUPER-SECRET-TOKEN-999999"
        subworker_secret = "AIza-SUBWORKER-DISTINCT-SECRET-888888"
        combo_secret = "xai-COMBO-TIER-SECRET-777777"

        harness.configure_primary_agent(
            provider_type="openai",
            model_id="gpt-4.1-mini",
            api_key=primary_secret,
        )
        harness.register_combo_chain(
            "combo-sec",
            [
                {"provider_type": "xai", "model_id": "grok-4.7", "api_key": combo_secret},
                {"provider_type": "offline_deterministic", "model_id": "builtin-v1", "api_key": ""},
            ],
            set_as_primary=False,
        )
        prop = SubworkerProposal(
            subworker_id="sub-1",
            role="auditor",
            task_description="Audit tests",
            rationale="Independent verification",
        )
        harness.request_subworker_hitl(prop)
        harness.approve_subworker_hitl(
            "sub-1",
            provider_type="gemini",
            model_id="gemini-3.8-flash",
            api_key=subworker_secret,
        )

        spec_app = record_spec_approval(
            session_id=harness.session_id,
            revision=1,
            candidate=candidate,
            verification=verification,
            formal_certificate=cert,
            confirmation_token="APPROVE_SPEC",
        )
        plan = generate_construction_plan(candidate, revision=1, sys_spec=sys_spec)
        const_app = record_construction_approval(
            spec_approval=spec_app,
            candidate=candidate,
            formal_certificate=cert,
            confirmation_token="APPROVE_CONSTRUCTION",
        )

        with tempfile.TemporaryDirectory() as tmp:
            out_root = Path(tmp) / "constructed_projects"
            layout = build_constructed_project(
                candidate=candidate,
                yaml_text=VALID_YAML,
                certificate=cert,
                spec_approval=spec_app,
                plan=plan,
                construction_approval=const_app,
                revision=1,
                output_root=out_root,
            )
            pkg = verify_and_package_project(
                layout=layout,
                candidate=candidate,
                certificate=cert,
                spec_approval=spec_app,
                plan=plan,
                construction_approval=const_app,
                harness=harness,
            )

            self.assertEqual(pkg.refined_certificate.overall_status, "PROVED")
            self.assertEqual(pkg.refined_certificate.stage3_refinement_proof["status"], "PROVED")
            self.assertTrue(pkg.compile_passed)
            self.assertTrue(pkg.unit_tests_passed)
            self.assertTrue(pkg.sample_execution_passed)
            self.assertTrue(pkg.zip_path.is_file())

            # Inspect ZIP contents and verify zero secret leakage across all packaged files
            with zipfile.ZipFile(pkg.zip_path, "r") as zf:
                names = set(zf.namelist())
                self.assertIn("machine.yaml", names)
                self.assertIn("formal-proof-certificate.json", names)
                self.assertIn("verification-report.json", names)
                self.assertIn("construction-log.jsonl", names)
                self.assertIn("src/constructed_machine/pipeline.py", names)
                self.assertIn("tests/test_constructed_machine.py", names)

                for name in names:
                    text_content = zf.read(name).decode("utf-8", errors="ignore")
                    self.assertNotIn(primary_secret, text_content)
                    self.assertNotIn(subworker_secret, text_content)
                    self.assertNotIn(combo_secret, text_content)

    def test_stage3_ast_mutation_flips_fo_ref_01_to_refuted_and_blocks_packaging(self) -> None:
        candidate, sys_spec = load_any_spec_to_candidate(VALID_YAML.encode("utf-8"))
        verification = verify_candidate(candidate)
        cert = verify_formal_spec(VALID_YAML.encode("utf-8"))

        spec_app = record_spec_approval(
            session_id="sess-mut",
            revision=1,
            candidate=candidate,
            verification=verification,
            formal_certificate=cert,
            confirmation_token="APPROVE_SPEC",
        )
        plan = generate_construction_plan(candidate, revision=1, sys_spec=sys_spec)
        const_app = record_construction_approval(
            spec_approval=spec_app,
            candidate=candidate,
            formal_certificate=cert,
            confirmation_token="APPROVE_CONSTRUCTION",
        )

        with tempfile.TemporaryDirectory() as tmp:
            out_root = Path(tmp) / "constructed_projects"
            layout = build_constructed_project(
                candidate=candidate,
                yaml_text=VALID_YAML,
                certificate=cert,
                spec_approval=spec_app,
                plan=plan,
                construction_approval=const_app,
                revision=1,
                output_root=out_root,
            )

            # Mutate generated pipeline.py by removing an edge wiring call so G_code != G_yaml
            pipeline_file = layout.project_dir / "src" / "constructed_machine" / "pipeline.py"
            orig_code = pipeline_file.read_text(encoding="utf-8")
            mutated_code = orig_code.replace("wire_edge(", "# mutated_out_wire_edge(", 1)
            pipeline_file.write_text(mutated_code, encoding="utf-8")

            mutated_cert = verify_code_refinement(cert, candidate, layout.project_dir)
            self.assertEqual(mutated_cert.overall_status, "REFUTED")
            self.assertEqual(mutated_cert.stage3_refinement_proof["status"], "REFUTED")
            ref1 = next(o for o in mutated_cert.obligations if o.id == "FO-REF-01")
            self.assertEqual(ref1.status, "REFUTED")

            with self.assertRaises(RuntimeError):
                verify_and_package_project(
                    layout=layout,
                    candidate=candidate,
                    certificate=cert,
                    spec_approval=spec_app,
                    plan=plan,
                    construction_approval=const_app,
                )

    def test_cli_construct_subcommand_end_to_end(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            spec_file = Path(tmp) / "spec.yaml"
            spec_file.write_text(VALID_YAML, encoding="utf-8")
            out_dir = Path(tmp) / "projects"
            out_json = Path(tmp) / "result.json"

            buf = io.StringIO()
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                code = cli.main(
                    [
                        "construct",
                        str(spec_file),
                        "--approve-spec",
                        "--approve-construction",
                        "--output-dir",
                        str(out_dir),
                        "--output",
                        str(out_json),
                    ]
                )
            self.assertEqual(code, 0, buf.getvalue())
            res = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertEqual(res["overall_formal_status"], "PROVED")
            self.assertEqual(res["stage3_status"], "PROVED")
            self.assertTrue(Path(res["zip_path"]).is_file())


if __name__ == "__main__":
    unittest.main()
