"""Bounded Project Builder for AMCA Local Independent Version.

Generates a real, runnable Python package in `artifacts/constructed_projects/<machine_id>-rev<NNN>/`
after enforcing Two-Stage Human Approvals (`spec_approval` + `construction_approval`) and
Stage 1/2 Formal Proof Certificate verification. Calls `amca_components` as a reusable component library
and bundles a self-contained snapshot of `amca_components` into the constructed project.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from amca.models import CandidateGraph
from amca_components import (
    COMPONENT_DISPATCH,
    execute_library_component,
    get_library_catalog_snapshot,
)

from .approvals import (
    ConstructionApprovalRecord,
    SpecApprovalRecord,
    validate_approvals_for_construction,
)
from .custom_components import (
    CustomComponentSpec,
    get_custom_component_spec,
    list_custom_component_specs,
    render_library_module_for_spec,
)
from .formal_verifier import FormalProofCertificate
from .graph import to_dot
from .planner import ConstructionPlan, _topological_sort


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONSTRUCTED_PROJECTS_DIR = ROOT / "artifacts" / "constructed_projects"


@dataclass(frozen=True)
class ConstructedProjectLayout:
    machine_id: str
    revision: int
    project_dir: Path
    files_written: tuple[str, ...]
    candidate_sha256: str
    certificate_sha256: str
    plan_id: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "machine_id": self.machine_id,
            "revision": self.revision,
            "project_dir": str(self.project_dir),
            "files_written": list(self.files_written),
            "candidate_sha256": self.candidate_sha256,
            "certificate_sha256": self.certificate_sha256,
            "plan_id": self.plan_id,
        }


def _sanitize_slug(machine_id: str) -> str:
    return "".join(c if (c.isalnum() or c in "-_") else "-" for c in machine_id.strip()) or "machine"


def _detect_input_key(candidate: CandidateGraph) -> str:
    for node in candidate.nodes:
        if node.component == "input_source":
            return str(node.config.get("input_key", "text"))
    return "text"


def classify_topology(candidate: CandidateGraph) -> str:
    """Classify the candidate graph into 'single_machine', 'linear_pipeline', or 'nonlinear_dag'."""
    if len(candidate.nodes) == 1 and len(candidate.edges) == 0:
        return "single_machine"
    out_deg: dict[str, int] = {n.id: 0 for n in candidate.nodes}
    in_deg: dict[str, int] = {n.id: 0 for n in candidate.nodes}
    for edge in candidate.edges:
        out_deg[edge.source] = out_deg.get(edge.source, 0) + 1
        in_deg[edge.target] = in_deg.get(edge.target, 0) + 1
    if max(out_deg.values(), default=0) <= 1 and max(in_deg.values(), default=0) <= 1:
        return "linear_pipeline"
    return "nonlinear_dag"


def _render_components_py(candidate: CandidateGraph | None = None) -> str:
    """Render `src/constructed_machine/components.py` as a library facade over `amca_components`."""
    custom_specs: dict[str, CustomComponentSpec] = {s.component_id: s for s in list_custom_component_specs()}
    if candidate is not None:
        for node in candidate.nodes:
            spec = get_custom_component_spec(node.component)
            if spec is not None:
                custom_specs[spec.component_id] = spec

    alias_lines: list[str] = []
    for cid in sorted(custom_specs):
        safe_id = "".join(c if c.isalnum() else "_" for c in cid)
        alias_lines.append(f"run_custom_{safe_id} = COMPONENT_DISPATCH[{cid!r}]")
    alias_block = ("\n" + "\n".join(alias_lines) + "\n") if alias_lines else ""

    return f'''"""Library facade binding the constructed machine to the AMCA Component Library (`amca_components`)."""
from __future__ import annotations

from amca_components import (
    COMPONENT_DISPATCH,
    ContractViolationError,
    _enforce_postconditions,
    _enforce_preconditions,
    execute_library_component,
    run_aggregate_results,
    run_analysis_a,
    run_analysis_b,
    run_generate_report,
    run_input_source,
    run_validate_text,
)
{alias_block}
__all__ = [
    "COMPONENT_DISPATCH",
    "ContractViolationError",
    "_enforce_postconditions",
    "_enforce_preconditions",
    "execute_library_component",
    "run_aggregate_results",
    "run_analysis_a",
    "run_analysis_b",
    "run_generate_report",
    "run_input_source",
    "run_validate_text",
]
'''


def expected_reference_final_output(candidate: CandidateGraph) -> dict[str, Any]:
    """Compute the deterministic expected final_output of the sink node for reference input 'AMCA builds a graph.'."""
    input_key = _detect_input_key(candidate)
    order = _topological_sort(candidate) or [n.id for n in candidate.nodes]
    node_map = {n.id: n for n in candidate.nodes}
    incoming_by_target: dict[str, list[Any]] = {n.id: [] for n in candidate.nodes}
    for edge in sorted(candidate.edges, key=lambda e: (e.target, e.input, e.source, e.output)):
        incoming_by_target[edge.target].append(edge)

    raw_inputs = {input_key: "AMCA builds a graph."}
    state: dict[str, dict[str, Any]] = {}
    for nid in order:
        node = node_map[nid]
        node_inputs: dict[str, Any] = {}
        for edge in incoming_by_target.get(nid, []):
            node_inputs[edge.input] = state[edge.source][edge.output]
        state[nid] = execute_library_component(node.component, node_inputs, dict(node.config), raw_inputs)
    return state[order[-1]]


def _render_pipeline_py(candidate: CandidateGraph) -> str:
    order = _topological_sort(candidate) or [n.id for n in candidate.nodes]
    topology_class = classify_topology(candidate)
    node_map = {n.id: n for n in candidate.nodes}
    incoming_by_target: dict[str, list[Any]] = {n.id: [] for n in candidate.nodes}
    for edge in sorted(candidate.edges, key=lambda e: (e.target, e.input, e.source, e.output)):
        incoming_by_target[edge.target].append(edge)

    lines = [
        '"""Generated deterministic DAG pipeline refined from approved AMCA YAML specification."""',
        "from __future__ import annotations",
        "",
        "from typing import Any",
        "",
        "from amca_components import COMPONENT_DISPATCH, ContractViolationError, execute_library_component",
        "",
        f"MACHINE_ID = {candidate.machine_id!r}",
        f"TOPOLOGY_CLASS = {topology_class!r}",
        f"SPECIFICATION_SHA256 = {candidate.specification_sha256!r}",
        f"CANDIDATE_SHA256 = {candidate.candidate_sha256!r}",
        f"TOPOLOGICAL_ORDER = {list(order)!r}",
        "",
        "",
        "def wire_edge(",
        "    state: dict[str, dict[str, Any]],",
        "    node_inputs: dict[str, Any],",
        "    *,",
        "    source: str,",
        "    output: str,",
        "    target: str,",
        "    input_port: str,",
        ") -> None:",
        '    """Wire a deterministic directed edge between two DAG nodes."""',
        "    node_inputs[input_port] = state[source][output]",
        "",
        "",
        "def execute_component_node(",
        "    state: dict[str, dict[str, Any]],",
        "    *,",
        "    node_id: str,",
        "    component_id: str,",
        "    node_inputs: dict[str, Any],",
        "    config: dict[str, Any],",
        "    raw_inputs: dict[str, Any],",
        ") -> dict[str, Any]:",
        '    """Execute a single verified component node from the AMCA Component Library (`amca_components`)."""',
        "    out = execute_library_component(component_id, node_inputs, config, raw_inputs)",
        "    state[node_id] = out",
        "    return out",
        "",
        "",
        "def run_machine(raw_inputs: dict[str, Any]) -> dict[str, Any]:",
        '    """Execute the constructed machine in deterministic topological order."""',
        "    state: dict[str, dict[str, Any]] = {}",
    ]

    for nid in order:
        node = node_map[nid]
        lines.append(f"    # Node: {nid} ({node.component})")
        lines.append(f"    inputs_{nid}: dict[str, Any] = {{}}")
        for edge in incoming_by_target.get(nid, []):
            lines.append(
                f"    wire_edge(state, inputs_{nid}, "
                f"source={edge.source!r}, output={edge.output!r}, "
                f"target={edge.target!r}, input_port={edge.input!r})"
            )
        lines.append(
            f"    execute_component_node(state, "
            f"node_id={nid!r}, component_id={node.component!r}, "
            f"node_inputs=inputs_{nid}, config={dict(node.config)!r}, raw_inputs=raw_inputs)"
        )
        lines.append("")

    sink_id = order[-1]
    lines.extend(
        [
            "    return {",
            '        "machine_id": MACHINE_ID,',
            '        "specification_sha256": SPECIFICATION_SHA256,',
            '        "candidate_sha256": CANDIDATE_SHA256,',
            '        "execution_order": list(TOPOLOGICAL_ORDER),',
            '        "node_outputs": state,',
            f'        "final_output": state[{sink_id!r}],',
            "    }",
            "",
        ]
    )
    return "\n".join(lines)


def _render_cli_py(input_key: str) -> str:
    return f'''"""Command-line entrypoint for the constructed AMCA machine."""
from __future__ import annotations

import argparse
import json
import sys

from .pipeline import run_machine


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run constructed AMCA machine.")
    parser.add_argument("--input-json", help="JSON object payload for machine inputs.")
    parser.add_argument("--text", help="Direct string value for primary input key '{input_key}'.")
    args = parser.parse_args(argv)

    if args.input_json:
        payload = json.loads(args.input_json)
    elif args.text is not None:
        payload = {{{input_key!r}: args.text}}
    else:
        payload = {{{input_key!r}: "AMCA builds a graph."}}

    result = run_machine(payload)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''


def _render_tests_py(candidate: CandidateGraph, input_key: str) -> str:
    expected_out = expected_reference_final_output(candidate)
    has_validation_or_analysis = any(n.component != "input_source" for n in candidate.nodes)
    invalid_payload_expr = f"{{{input_key!r}: '   '}}" if has_validation_or_analysis else "{}"
    return f'''"""Automated unit & contract verification suite for constructed machine {candidate.machine_id!r}."""
from __future__ import annotations

from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from amca_components import ContractViolationError
from constructed_machine.pipeline import MACHINE_ID, TOPOLOGICAL_ORDER, TOPOLOGY_CLASS, run_machine


class ConstructedMachineTests(unittest.TestCase):
    def test_reference_input_produces_deterministic_output(self) -> None:
        result = run_machine({{{input_key!r}: "AMCA builds a graph."}})
        self.assertEqual(result["machine_id"], {candidate.machine_id!r})
        self.assertEqual(result["final_output"], {expected_out!r})
        self.assertEqual(result["execution_order"], TOPOLOGICAL_ORDER)
        self.assertIn(TOPOLOGY_CLASS, ("single_machine", "linear_pipeline", "nonlinear_dag"))

    def test_invalid_input_rejected_by_hoare_guard(self) -> None:
        with self.assertRaises(ContractViolationError):
            run_machine({invalid_payload_expr})


if __name__ == "__main__":
    unittest.main()
'''


def build_constructed_project(
    *,
    candidate: CandidateGraph,
    yaml_text: str,
    certificate: FormalProofCertificate,
    spec_approval: SpecApprovalRecord,
    plan: ConstructionPlan,
    construction_approval: ConstructionApprovalRecord,
    revision: int = 1,
    output_root: Path | None = None,
) -> ConstructedProjectLayout:
    """Construct the standalone Python project after verifying approvals and formal certificate bindings."""
    validate_approvals_for_construction(
        spec_approval,
        construction_approval,
        candidate=candidate,
        certificate=certificate,
    )
    if certificate.stage1_spec_proof.get("status") != "PROVED":
        raise PermissionError("Stage 1 Formal Proof Certificate must be PROVED before project construction.")
    if certificate.stage2_evolution_proof.get("status") != "PROVED":
        raise PermissionError("Stage 2 Evolution Proof must be PROVED before project construction.")

    base_root = output_root or DEFAULT_CONSTRUCTED_PROJECTS_DIR
    slug = _sanitize_slug(candidate.machine_id)
    project_dir = base_root / f"{slug}-rev{revision:03d}"
    src_pkg_dir = project_dir / "src" / "constructed_machine"
    tests_dir = project_dir / "tests"
    src_pkg_dir.mkdir(parents=True, exist_ok=True)
    tests_dir.mkdir(parents=True, exist_ok=True)

    input_key = _detect_input_key(candidate)
    files_written: list[str] = []

    def _write(rel_path: str, content: str) -> None:
        target = project_dir / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        files_written.append(rel_path)

    _write("machine.yaml", yaml_text.strip() + "\n")
    _write("machine-dag.dot", to_dot(candidate) + "\n")
    _write(
        "formal-proof-certificate.json",
        json.dumps(certificate.as_dict(), indent=2, sort_keys=True) + "\n",
    )

    # Bundle the AMCA Component Library (`amca_components`) into `src/amca_components/`
    lib_src_dir = ROOT / "src" / "amca_components"
    _write("src/amca_components/__init__.py", (lib_src_dir / "__init__.py").read_text(encoding="utf-8"))
    _write("src/amca_components/contracts.py", (lib_src_dir / "contracts.py").read_text(encoding="utf-8"))
    _write("src/amca_components/builtin.py", (lib_src_dir / "builtin.py").read_text(encoding="utf-8"))
    _write(
        "src/amca_components/catalog.json",
        json.dumps(get_library_catalog_snapshot(), indent=2, sort_keys=True) + "\n",
    )
    _write("src/amca_components/custom/__init__.py", (lib_src_dir / "custom" / "__init__.py").read_text(encoding="utf-8"))

    custom_specs: dict[str, CustomComponentSpec] = {s.component_id: s for s in list_custom_component_specs()}
    for node in candidate.nodes:
        spec = get_custom_component_spec(node.component)
        if spec is not None:
            custom_specs[spec.component_id] = spec
    for cid in sorted(custom_specs):
        _write(f"src/amca_components/custom/{cid}.py", render_library_module_for_spec(custom_specs[cid]))

    init_code = (
        '"""Constructed AMCA machine package."""\n'
        "from .pipeline import MACHINE_ID, CANDIDATE_SHA256, SPECIFICATION_SHA256, run_machine\n\n"
        '__all__ = ["MACHINE_ID", "CANDIDATE_SHA256", "SPECIFICATION_SHA256", "run_machine"]\n'
    )
    _write("src/constructed_machine/__init__.py", init_code)
    _write("src/constructed_machine/components.py", _render_components_py(candidate))
    _write("src/constructed_machine/pipeline.py", _render_pipeline_py(candidate))
    _write("src/constructed_machine/cli.py", _render_cli_py(input_key))
    _write("tests/test_constructed_machine.py", _render_tests_py(candidate, input_key))

    readme_content = f"""# Constructed Machine: `{candidate.machine_id}` (Revision {revision:03d})

Generated by **AMCA Local Independent Version** Bounded Project Builder using the **AMCA Component Library (`amca_components`)**.

- **Machine ID**: `{candidate.machine_id}`
- **Specification SHA-256**: `{candidate.specification_sha256}`
- **Candidate Graph SHA-256**: `{candidate.candidate_sha256}`
- **Formal Proof Certificate SHA-256**: `{certificate.certificate_sha256}`
- **Construction Plan ID**: `{plan.plan_id}` (`{plan.optimization_profile}`)

## Running the Machine Locally

```powershell
$env:PYTHONPATH = "src"
python -m constructed_machine.cli --text "AMCA builds a graph."
```

## Running the Generated Unit Tests

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -p "test_*.py" -v
```
"""
    _write("README.md", readme_content)

    manifest_data = {
        "schema_version": "1.0",
        "machine_id": candidate.machine_id,
        "revision": revision,
        "specification_sha256": candidate.specification_sha256,
        "candidate_sha256": candidate.candidate_sha256,
        "certificate_sha256": certificate.certificate_sha256,
        "spec_approval_id": spec_approval.approval_id,
        "construction_approval_id": construction_approval.approval_id,
        "plan_id": plan.plan_id,
        "optimization_profile": plan.optimization_profile,
        "files": list(files_written) + ["manifest.json"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    _write("manifest.json", json.dumps(manifest_data, indent=2, sort_keys=True) + "\n")

    return ConstructedProjectLayout(
        machine_id=candidate.machine_id,
        revision=revision,
        project_dir=project_dir,
        files_written=tuple(files_written),
        candidate_sha256=candidate.candidate_sha256,
        certificate_sha256=certificate.certificate_sha256,
        plan_id=plan.plan_id,
    )
