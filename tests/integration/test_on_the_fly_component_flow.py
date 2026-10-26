"""Integration tests for On-The-Fly Code Agent Component Synthesis & Construction (RF-03, RF-04).

Zero-mocking: Tests the entire pipeline from candidate YAML with unregistered components,
detection, Bidirectional Hoare Constraint Propagation, on-the-fly Python code generation,
binding into amca_components, formal verification (Stage 1/2/3), and handover ZIP creation.
"""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from amca.registry import component_ids
from amca.verifier import verify_candidate
from amca_agent import artifacts, cli
from amca_agent.approvals import record_construction_approval, record_spec_approval
from amca_agent.builder import build_constructed_project
from amca_agent.component_synthesizer import (
    detect_unregistered_components_in_yaml,
    synthesize_and_bind_missing_components,
)
from amca_agent.custom_components import clear_all_custom_components
from amca_agent.formal_verifier import verify_formal_spec
from amca_agent.packager import verify_and_package_project
from amca_agent.planner import generate_construction_plan
from amca_agent.system_spec import load_any_spec_to_candidate
from amca_components import COMPONENT_DISPATCH, execute_library_component


class OnTheFlyComponentFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.artifact_root = Path(self.temp.name) / "artifacts"
        self.patch_artifacts = unittest.mock.patch.object(artifacts, "ARTIFACT_ROOT", self.artifact_root)
        self.patch_cli_artifacts = unittest.mock.patch.object(cli, "ARTIFACT_ROOT", self.artifact_root)
        self.patch_artifacts.start()
        self.patch_cli_artifacts.start()
        self.addCleanup(self.patch_artifacts.stop)
        self.addCleanup(self.patch_cli_artifacts.stop)
        clear_all_custom_components(persist=False)

    def tearDown(self) -> None:
        clear_all_custom_components(persist=False)

    def test_on_the_fly_flow_end_to_end_with_stage3_proof_and_zip(self) -> None:
        candidate_yaml = """schema_version: "1.0"
machine_id: "article-html-cleaner-pipeline"
nodes:
  - id: "input"
    component: "input_source"
    config:
      input_key: "article_html"
  - id: "validate"
    component: "validate_text"
    config: {}
  - id: "clean_step"
    component: "html_tag_stripper"
    config: {}
  - id: "char_count"
    component: "analysis_a"
    config: {}
  - id: "word_count"
    component: "analysis_b"
    config: {}
  - id: "aggregate"
    component: "aggregate_results"
    config: {}
  - id: "report"
    component: "generate_report"
    config: {}
edges:
  - {from: "input", out: "text", to: "validate", in: "text"}
  - {from: "validate", out: "text", to: "clean_step", in: "text"}
  - {from: "clean_step", out: "text", to: "char_count", in: "text"}
  - {from: "clean_step", out: "text", to: "word_count", in: "text"}
  - {from: "char_count", out: "finding", to: "aggregate", in: "finding_a"}
  - {from: "word_count", out: "finding", to: "aggregate", in: "finding_b"}
  - {from: "aggregate", out: "summary", to: "report", in: "summary"}
"""
        # 1. Component is not yet registered
        self.assertNotIn("html_tag_stripper", component_ids())

        # 2. Detect unregistered components and verify Bidirectional Hoare Propagation
        plans = detect_unregistered_components_in_yaml(candidate_yaml, "Clean HTML tags from article")
        self.assertEqual(len(plans), 1)
        plan = plans[0]
        self.assertEqual(plan.component_id, "html_tag_stripper")
        self.assertEqual(plan.inferred_input_ports, {"text": "string"})
        self.assertEqual(plan.inferred_output_ports, {"text": "string"})
        self.assertIn("validate_text", plan.upstream_components)
        self.assertIn("analysis_a", plan.downstream_components)
        self.assertIn("analysis_b", plan.downstream_components)

        # 3. Code Agent synthesizes pure Python and binds into amca_components
        bound_records = synthesize_and_bind_missing_components(
            plans,
            problem_statement="Strip HTML tags",
            persist=False,
        )
        self.assertEqual(len(bound_records), 1)
        self.assertEqual(bound_records[0].spec.component_id, "html_tag_stripper")
        self.assertIn("html_tag_stripper", component_ids())
        self.assertIn("html_tag_stripper", COMPONENT_DISPATCH)

        # Verify runtime execution of the synthesized component
        out = execute_library_component(
            "html_tag_stripper",
            {"text": "<p>AMCA <b>constructs</b> clean pipelines.</p>"},
            {},
            {"text": "<p>AMCA <b>constructs</b> clean pipelines.</p>"},
        )
        self.assertNotIn("<p>", out["text"])
        self.assertNotIn("<b>", out["text"])
        self.assertIn("AMCA constructs clean pipelines", out["text"])

        # 4. Verify candidate now passes structural and formal verification (Stage 1 & 2)
        candidate, sys_spec = load_any_spec_to_candidate(candidate_yaml)
        v_rep = verify_candidate(candidate)
        self.assertEqual(v_rep.status, "verified")

        cert = verify_formal_spec(candidate_yaml)
        self.assertEqual(cert.overall_status, "PROVED")
        for obl in cert.obligations:
            self.assertEqual(obl.status, "PROVED")

        # 5. Build constructed project and package ZIP (Stage 3 Refinement Proof)
        with tempfile.TemporaryDirectory() as td:
            out_root = Path(td) / "constructed_projects"
            spec_app = record_spec_approval(
                session_id="test-otf-sess",
                revision=1,
                candidate=candidate,
                verification=v_rep,
                formal_certificate=cert,
                confirmation_token="APPROVE_SPEC",
            )
            plan_obj = generate_construction_plan(candidate, revision=1, sys_spec=sys_spec)
            const_app = record_construction_approval(
                spec_approval=spec_app,
                candidate=candidate,
                formal_certificate=cert,
                confirmation_token="APPROVE_CONSTRUCTION",
            )
            layout = build_constructed_project(
                candidate=candidate,
                yaml_text=candidate_yaml,
                certificate=cert,
                spec_approval=spec_app,
                plan=plan_obj,
                construction_approval=const_app,
                revision=1,
                output_root=out_root,
            )
            pkg = verify_and_package_project(
                layout=layout,
                candidate=candidate,
                certificate=cert,
                spec_approval=spec_app,
                plan=plan_obj,
                construction_approval=const_app,
            )
            self.assertEqual(pkg.refined_certificate.overall_status, "PROVED")
            self.assertTrue(pkg.compile_passed)
            self.assertTrue(pkg.unit_tests_passed)
            self.assertTrue(pkg.sample_execution_passed)
            self.assertTrue(pkg.zip_path.exists())
            self.assertGreater(pkg.zip_path.stat().st_size, 0)

            # Confirm amca_components library snapshot and custom component module are bundled in ZIP
            self.assertIn("src/amca_components/__init__.py", pkg.zip_entries)
            self.assertIn("src/amca_components/contracts.py", pkg.zip_entries)
            self.assertIn("src/amca_components/custom/html_tag_stripper.py", pkg.zip_entries)

    def test_cli_bind_component_and_synthesize_missing_subcommands(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            ext_py = td_path / "custom_cleaner.py"
            ext_py.write_text(
                """
import re

def clean_digits(text: str) -> str:
    \"\"\"Remove all numeric digits from text.\"\"\"
    cleaned = re.sub(r'\\d+', '', text or '').strip()
    return ' '.join(cleaned.split())
""",
                encoding="utf-8",
            )

            # Test bind-component CLI
            out_buf = io.StringIO()
            with redirect_stdout(out_buf), redirect_stderr(out_buf):
                ret = cli.main(["bind-component", str(ext_py), "--id", "clean_digits"])
            self.assertEqual(ret, 0)
            self.assertIn('"status": "bound"', out_buf.getvalue())
            self.assertIn("clean_digits", component_ids())

            # Test synthesize-missing CLI on candidate with missing component
            yaml_path = td_path / "missing.yaml"
            yaml_path.write_text(
                """schema_version: "1.0"
machine_id: "missing-comp-machine"
nodes:
  - id: "input"
    component: "input_source"
    config:
      input_key: "text"
  - id: "validate"
    component: "validate_text"
    config: {}
  - id: "new_node"
    component: "hashtag_extractor"
    config: {}
edges:
  - {from: "input", out: "text", to: "validate", in: "text"}
  - {from: "validate", out: "text", to: "new_node", in: "text"}
""",
                encoding="utf-8",
            )

            # First run without --approve must indicate pending approval
            out_buf2 = io.StringIO()
            with redirect_stdout(out_buf2), redirect_stderr(out_buf2):
                ret2 = cli.main(["synthesize-missing", str(yaml_path)])
            self.assertEqual(ret2, 1)
            self.assertIn('"status": "pending_approval"', out_buf2.getvalue())

            # Second run with --approve synthesizes and verifies
            out_buf3 = io.StringIO()
            with redirect_stdout(out_buf3), redirect_stderr(out_buf3):
                ret3 = cli.main(["synthesize-missing", str(yaml_path), "--approve"])
            self.assertEqual(ret3, 0)
            self.assertIn('"status": "synthesized_and_bound"', out_buf3.getvalue())
            self.assertIn("hashtag_extractor", component_ids())


if __name__ == "__main__":
    unittest.main()
