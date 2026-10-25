"""Unit tests for amca/v1alpha1 (MachineSystem) parser, aliases, and bidirectional v1.0 conversion."""
from __future__ import annotations

import copy
import unittest
from pathlib import Path

from amca.errors import SpecificationError
from amca.specification import load_spec
from amca.verifier import verify_candidate
from amca_agent.system_spec import (
    dump_system_spec_yaml,
    load_any_spec_to_candidate,
    load_system_spec,
    resolve_component_alias,
    v1_to_system_spec,
    validate_system_spec_mapping,
)

ROOT = Path(__file__).resolve().parents[2]


class SystemSpecTests(unittest.TestCase):
    def test_valid_v1alpha1_example_loads_and_verifies(self):
        path = ROOT / "examples" / "valid_machine_system_v1alpha1.yaml"
        spec = load_system_spec(path)
        self.assertEqual(spec.api_version, "amca/v1alpha1")
        self.assertEqual(spec.kind, "MachineSystem")
        self.assertEqual(spec.machine_id, "reference-text-analysis")
        self.assertEqual(len(spec.machines), 6)
        self.assertTrue(len(spec.assumptions) >= 1)
        self.assertTrue(len(spec.limitations) >= 1)

        candidate = spec.to_candidate_graph()
        report = verify_candidate(candidate)
        self.assertEqual(report.status, "verified")

    def test_component_aliases_resolve_correctly(self):
        self.assertEqual(resolve_component_alias("text.input"), "input_source")
        self.assertEqual(resolve_component_alias("text.validate"), "validate_text")
        self.assertEqual(resolve_component_alias("text.char_count"), "analysis_a")
        self.assertEqual(resolve_component_alias("text.word_count"), "analysis_b")
        self.assertEqual(resolve_component_alias("text.summarize"), "aggregate_results")
        self.assertEqual(resolve_component_alias("report.assemble"), "generate_report")
        with self.assertRaises(SpecificationError):
            resolve_component_alias("arbitrary.shell_exec")

    def test_bidirectional_v1_and_v1alpha1_conversion(self):
        v1_spec = load_spec(ROOT / "examples" / "valid_parallel_analysis.yaml")
        sys_spec = v1_to_system_spec(v1_spec)
        yaml_text = dump_system_spec_yaml(sys_spec)
        reloaded_cand, reloaded_sys = load_any_spec_to_candidate(yaml_text)
        self.assertIsNotNone(reloaded_sys)
        self.assertEqual(verify_candidate(reloaded_cand).status, "verified")

    def test_invalid_security_policy_and_secret_ref_fail_closed(self):
        spec = load_system_spec(ROOT / "examples" / "valid_machine_system_v1alpha1.yaml")
        bad_sec = copy.deepcopy(spec.as_dict())
        bad_sec["securityPolicy"]["operatingSystemCommands"] = "allow"
        with self.assertRaises(SpecificationError):
            validate_system_spec_mapping(bad_sec)

        bad_secret = copy.deepcopy(spec.as_dict())
        bad_secret["machines"][0]["services"] = [
            {"name": "llm", "kind": "api", "secretRef": "sk-raw-secret-lowercase-not-allowed"}
        ]
        with self.assertRaises(SpecificationError):
            validate_system_spec_mapping(bad_secret)


if __name__ == "__main__":
    unittest.main()
