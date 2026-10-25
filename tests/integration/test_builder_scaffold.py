"""Integration tests for the Bounded Project Builder scaffold and two-stage approval enforcement."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from amca.verifier import verify_candidate
from amca_agent.approvals import record_construction_approval, record_spec_approval
from amca_agent.builder import build_constructed_project
from amca_agent.formal_verifier import verify_formal_spec
from amca_agent.planner import generate_construction_plan
from amca_agent.system_spec import load_any_spec_to_candidate

ROOT = Path(__file__).resolve().parents[2]
VALID_YAML = (ROOT / "examples" / "valid_machine_system_v1alpha1.yaml").read_text(encoding="utf-8")


class BuilderScaffoldTests(unittest.TestCase):
    def test_builder_requires_matching_two_stage_approvals_and_generates_runnable_layout(self) -> None:
        candidate, sys_spec = load_any_spec_to_candidate(VALID_YAML.encode("utf-8"))
        verification = verify_candidate(candidate)
        cert = verify_formal_spec(VALID_YAML.encode("utf-8"))

        spec_app = record_spec_approval(
            session_id="sess-builder-test",
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

            # Missing construction approval must fail closed
            with self.assertRaises(PermissionError):
                build_constructed_project(
                    candidate=candidate,
                    yaml_text=VALID_YAML,
                    certificate=cert,
                    spec_approval=spec_app,
                    plan=plan,
                    construction_approval=None,  # type: ignore[arg-type]
                    revision=1,
                    output_root=out_root,
                )

            # Mutated specification digest after approval must fail closed
            modified_yaml = VALID_YAML.replace("id: reference-text-analysis", "id: modified-text-analysis")
            mod_candidate, _ = load_any_spec_to_candidate(modified_yaml.encode("utf-8"))
            with self.assertRaises(PermissionError):
                build_constructed_project(
                    candidate=mod_candidate,
                    yaml_text=modified_yaml,
                    certificate=cert,
                    spec_approval=spec_app,
                    plan=plan,
                    construction_approval=const_app,
                    revision=1,
                    output_root=out_root,
                )

            # Valid approvals generate full bounded layout
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
            self.assertTrue((layout.project_dir / "machine.yaml").is_file())
            self.assertTrue((layout.project_dir / "machine-dag.dot").is_file())
            self.assertTrue((layout.project_dir / "formal-proof-certificate.json").is_file())
            self.assertTrue((layout.project_dir / "manifest.json").is_file())
            self.assertTrue((layout.project_dir / "README.md").is_file())
            self.assertTrue((layout.project_dir / "src" / "constructed_machine" / "components.py").is_file())
            self.assertTrue((layout.project_dir / "src" / "constructed_machine" / "pipeline.py").is_file())
            self.assertTrue((layout.project_dir / "src" / "constructed_machine" / "cli.py").is_file())
            self.assertTrue((layout.project_dir / "tests" / "test_constructed_machine.py").is_file())


if __name__ == "__main__":
    unittest.main()
