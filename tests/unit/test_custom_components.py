"""Unit and end-to-end tests for Custom Component Authoring, Registration, Catalog Presentation, and ZIP Construction."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from amca.errors import SpecificationError
from amca.registry import BUILTIN_COMPONENT_IDS, component_ids
from amca.runtime import run
from amca.verifier import verify_candidate
from amca_agent.approvals import record_construction_approval, record_spec_approval
from amca_agent.builder import build_constructed_project
from amca_agent.cli import main as cli_main
from amca_agent.custom_components import (
    clear_all_custom_components,
    draft_custom_component_from_description,
    format_catalog_markdown,
    get_registered_components_catalog,
    load_custom_components_registry,
    register_custom_component,
    unregister_custom_component,
)
from amca_agent.formal_verifier import verify_formal_spec
from amca_agent.harness import AgentHarnessSession
from amca_agent.packager import verify_and_package_project
from amca_agent.planner import generate_construction_plan
from amca_agent.provider import build_dynamic_system_prompt, synthesize_deterministic_yaml
from amca_agent.system_spec import load_any_spec_to_candidate


class CustomComponentSystemTests(unittest.TestCase):
    def setUp(self) -> None:
        clear_all_custom_components(persist=False)

    def tearDown(self) -> None:
        clear_all_custom_components(persist=False)

    def test_builtin_components_cannot_be_overwritten_or_deleted(self) -> None:
        self.assertEqual(component_ids(), BUILTIN_COMPONENT_IDS)
        with self.assertRaises(SpecificationError):
            register_custom_component(
                {
                    "component_id": "input_source",
                    "operation_template": "text_transform",
                },
                persist=False,
            )
        with self.assertRaises(SpecificationError):
            unregister_custom_component("validate_text", persist=False)

    def test_catalog_presents_all_registered_components_and_prompt_boundaries(self) -> None:
        register_custom_component(
            {
                "component_id": "sentence_counter",
                "alias": "custom.sentence_counter",
                "name": "Sentence Counter",
                "role": "Count sentences in validated text.",
                "operation_template": "text_metric_object",
                "template_params": {"mode": "sentence_count"},
            },
            persist=False,
        )
        catalog = get_registered_components_catalog()
        self.assertEqual(len(catalog), 7)
        cids = [item["component_id"] for item in catalog]
        self.assertIn("sentence_counter", cids)

        md = format_catalog_markdown()
        self.assertIn("Katalog Komponen Terdaftar & Panduan Batasan Prompt", md)
        self.assertIn("`sentence_counter`", md)
        self.assertIn("`custom.sentence_counter`", md)
        self.assertIn("Batasan Prompt (*Prompt Boundaries*)", md)

        sys_prompt = build_dynamic_system_prompt()
        self.assertIn("sentence_counter", sys_prompt)
        self.assertIn("custom.sentence_counter", sys_prompt)

    def test_custom_component_end_to_end_yaml_formal_proof_runtime_and_zip_construction(self) -> None:
        with tempfile.TemporaryDirectory(prefix="amca-custom-comp-") as tmp:
            tmp_path = Path(tmp)
            reg_file = tmp_path / "custom_registry.json"

            drafted = draft_custom_component_from_description(
                "Komponen penghitung jumlah kalimat dari teks tervalidasi",
                component_id="sentence_counter",
            )
            register_custom_component(drafted, persist=True, registry_path=reg_file)
            self.assertTrue(reg_file.is_file())

            # Reload from persistence to verify round-trip
            clear_all_custom_components(persist=False)
            loaded = load_custom_components_registry(reg_file)
            self.assertEqual(len(loaded), 1)
            self.assertEqual(loaded[0].component_id, "sentence_counter")

            # Synthesize YAML from prompt mentioning sentence_counter
            yaml_text = synthesize_deterministic_yaml(
                "Buat pipeline machine_id: custom_sentence_machine menggunakan sentence_counter setelah validate_text."
            )
            self.assertIn("sentence_counter", yaml_text)

            candidate, _ = load_any_spec_to_candidate(yaml_text.encode("utf-8"))
            verification = verify_candidate(candidate)
            self.assertEqual(verification.status, "verified")

            formal_cert = verify_formal_spec(yaml_text.encode("utf-8"))
            self.assertEqual(formal_cert.overall_status, "PROVED")

            # Execute in AMCA runtime
            exec_record = run(candidate, verification, {"text": "AMCA builds a graph. Second sentence!"})
            self.assertEqual(exec_record["run_status"], "succeeded")

            # Construct standalone Python project & Handover ZIP and prove Stage 3 AST Isomorphism
            harness = AgentHarnessSession(session_id="test-custom-comp-session")
            spec_app = record_spec_approval(
                session_id="test-custom-comp-session",
                revision=1,
                candidate=candidate,
                verification=verification,
                formal_certificate=formal_cert,
                confirmation_token="APPROVE_SPEC",
            )
            plan = generate_construction_plan(candidate, harness=harness)
            const_app = record_construction_approval(
                spec_approval=spec_app,
                candidate=candidate,
                formal_certificate=formal_cert,
                confirmation_token="APPROVE_CONSTRUCTION",
                worker_policy=plan.worker_policy,
                use_subagents=plan.use_subagents,
                projects_root=tmp_path / "projects",
            )
            layout = build_constructed_project(
                candidate=candidate,
                yaml_text=yaml_text,
                certificate=formal_cert,
                spec_approval=spec_app,
                plan=plan,
                construction_approval=const_app,
                revision=1,
                output_root=tmp_path / "projects",
            )
            pkg = verify_and_package_project(
                layout=layout,
                candidate=candidate,
                certificate=formal_cert,
                spec_approval=spec_app,
                plan=plan,
                construction_approval=const_app,
                harness=harness,
            )
            self.assertEqual(pkg.refined_certificate.overall_status, "PROVED")
            self.assertEqual(pkg.refined_certificate.stage3_refinement_proof["status"], "PROVED")
            self.assertTrue(pkg.compile_passed)
            self.assertTrue(pkg.unit_tests_passed)
            self.assertTrue(pkg.zip_path.is_file())
            with zipfile.ZipFile(pkg.zip_path, "r") as zf:
                self.assertIn("src/constructed_machine/components.py", zf.namelist())
                comp_src = zf.read("src/constructed_machine/components.py").decode("utf-8")
                self.assertIn("run_custom_sentence_counter", comp_src)

    def test_cli_components_and_register_subcommands(self) -> None:
        with tempfile.TemporaryDirectory(prefix="amca-cli-comp-") as tmp:
            out_json = Path(tmp) / "catalog.json"
            rc = cli_main(["components", "--json", "--output", str(out_json)])
            self.assertEqual(rc, 0)
            data = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertGreaterEqual(len(data["components"]), 6)


if __name__ == "__main__":
    unittest.main()
