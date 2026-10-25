"""Waterfall SDLC & Cost-Minimizing Worker Planner for the AMCA Agent Constructor."""
from __future__ import annotations

import platform
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from amca.models import CandidateGraph
from amca_agent.approvals import resolve_bounded_construction_dir
from amca_agent.harness import SubworkerProposal
from amca_agent.system_spec import MachineSystemSpec


@dataclass(frozen=True)
class WaterfallPhasePlan:
    phase_id: str
    title: str
    deliverables: tuple[str, ...]
    assigned_worker: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "phase_id": self.phase_id,
            "title": self.title,
            "deliverables": list(self.deliverables),
            "assigned_worker": self.assigned_worker,
        }


@dataclass(frozen=True)
class ConstructionPlan:
    machine_id: str
    revision: int
    specification_sha256: str
    sdlc_method: str
    languages: tuple[str, ...]
    builder_environment: dict[str, str]
    target_environment: dict[str, str]
    worker_policy: str
    use_subagents: bool
    worker_rationale: str
    proposed_subworkers: tuple[SubworkerProposal, ...]
    destination_dir: str
    phases: tuple[WaterfallPhasePlan, ...]

    @property
    def plan_id(self) -> str:
        return f"plan-{self.machine_id}-rev{self.revision:03d}-{self.specification_sha256[:8]}"

    @property
    def optimization_profile(self) -> str:
        return self.worker_policy

    @property
    def subworkers(self) -> tuple[SubworkerProposal, ...]:
        return self.proposed_subworkers

    def as_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "machine_id": self.machine_id,
            "revision": self.revision,
            "specification_sha256": self.specification_sha256,
            "sdlc_method": self.sdlc_method,
            "optimization_profile": self.optimization_profile,
            "languages": list(self.languages),
            "builder_environment": self.builder_environment,
            "target_environment": self.target_environment,
            "worker_policy": self.worker_policy,
            "use_subagents": self.use_subagents,
            "worker_rationale": self.worker_rationale,
            "proposed_subworkers": [p.as_dict() for p in self.proposed_subworkers],
            "destination_dir": self.destination_dir,
            "phases": [ph.as_dict() for ph in self.phases],
        }


def _topological_sort(candidate: CandidateGraph) -> list[str]:
    """Deterministic lexicographical Kahn's topological sort of candidate DAG nodes."""
    in_degree = {n.id: 0 for n in candidate.nodes}
    adj: dict[str, list[str]] = {n.id: [] for n in candidate.nodes}
    for edge in candidate.edges:
        if edge.source in adj and edge.target in in_degree:
            adj[edge.source].append(edge.target)
            in_degree[edge.target] += 1
    ready = sorted(nid for nid, deg in in_degree.items() if deg == 0)
    order: list[str] = []
    while ready:
        curr = ready.pop(0)
        order.append(curr)
        for nxt in sorted(adj.get(curr, [])):
            in_degree[nxt] -= 1
            if in_degree[nxt] == 0 and nxt not in ready and nxt not in order:
                ready.append(nxt)
                ready.sort()
    return order


def capture_builder_environment() -> dict[str, str]:
    return {
        "os": platform.system() or "unspecified",
        "os_release": platform.release() or "unspecified",
        "arch": platform.machine() or "unspecified",
        "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
    }


def build_construction_plan(
    candidate: CandidateGraph,
    *,
    revision: int = 1,
    sys_spec: MachineSystemSpec | None = None,
    propose_subworker: bool | None = None,
    projects_root: Path | None = None,
) -> ConstructionPlan:
    """Create a Waterfall SDLC and worker allocation plan (defaults to single-agent minimize-cost)."""
    builder_env = capture_builder_environment()
    target_env = (
        {k: str(v) for k, v in sys_spec.target_environment.items()}
        if sys_spec and sys_spec.target_environment
        else {"os": "any", "python": ">=3.12,<3.13", "container": "unspecified"}
    )
    if "container" not in target_env:
        target_env["container"] = "unspecified"

    if propose_subworker is None:
        if sys_spec and sys_spec.construction.get("workerPlan", {}).get("useSubagents") is True:
            propose_subworker = True
        else:
            propose_subworker = False

    proposals: list[SubworkerProposal] = []
    if propose_subworker:
        proposals.append(
            SubworkerProposal(
                subworker_id="subworker-formal-auditor-01",
                role="independent_test_and_proof_auditor",
                task_description=(
                    f"Audit boundary test cases and Stage 3 AST refinement invariants for {candidate.machine_id} "
                    f"({len(candidate.nodes)} nodes, {len(candidate.edges)} edges)."
                ),
                rationale=(
                    "Provides independent verification of generated unit tests and Hoare runtime guards using a "
                    "separate model/API key approved via Human-in-the-Loop."
                ),
                recommended_provider="nine_router",
                recommended_model="free-combo",
            )
        )
        worker_policy = "independent-verification"
        rationale = (
            "Subworker proposed for independent test/proof auditing. Requires explicit On-The-Fly HITL "
            "approval and separate API key/model binding; falls back to Primary Agent if declined."
        )
    else:
        worker_policy = "minimize-cost"
        rationale = (
            f"Single-agent execution selected (minimize-cost policy): DAG has {len(candidate.nodes)} nodes and "
            f"{len(candidate.edges)} edges, which can be deterministically synthesized and verified in-process "
            "without incurring extra multi-agent coordination or API token overhead."
        )

    dest = resolve_bounded_construction_dir(candidate.machine_id, revision, projects_root=projects_root)
    auditor_worker = "subworker:subworker-formal-auditor-01" if propose_subworker else "amca_primary"

    phases = (
        WaterfallPhasePlan(
            phase_id="WF-1",
            title="Requirements & Formal Specification Lock",
            deliverables=("machine.yaml", "formal-proof-certificate.json"),
            assigned_worker="amca_primary",
        ),
        WaterfallPhasePlan(
            phase_id="WF-2",
            title="Architecture & Topological DAG Design",
            deliverables=("machine-dag.dot", "manifest.json"),
            assigned_worker="amca_primary",
        ),
        WaterfallPhasePlan(
            phase_id="WF-3",
            title="Standalone Python Package & Runtime Contract Guard Synthesis",
            deliverables=("src/components.py", "src/pipeline.py", "src/cli.py"),
            assigned_worker="amca_primary",
        ),
        WaterfallPhasePlan(
            phase_id="WF-4",
            title="Stage 3 AST Isomorphism Proof & Unit Test Verification",
            deliverables=("tests/test_constructed_machine.py", "verification-report.json"),
            assigned_worker=auditor_worker,
        ),
        WaterfallPhasePlan(
            phase_id="WF-5",
            title="Redacted Audit Log & Reproducible Handover ZIP Packaging",
            deliverables=("construction-log.jsonl", f"{candidate.machine_id}-rev{revision:03d}-handover.zip"),
            assigned_worker="amca_primary",
        ),
    )

    return ConstructionPlan(
        machine_id=candidate.machine_id,
        revision=revision,
        specification_sha256=candidate.specification_sha256,
        sdlc_method="waterfall",
        languages=("python",),
        builder_environment=builder_env,
        target_environment=target_env,
        worker_policy=worker_policy,
        use_subagents=propose_subworker,
        worker_rationale=rationale,
        proposed_subworkers=tuple(proposals),
        destination_dir=str(dest),
        phases=phases,
    )


def generate_construction_plan(
    candidate: CandidateGraph,
    *,
    optimization_profile: str = "minimize_cost",
    revision: int = 1,
    sys_spec: MachineSystemSpec | None = None,
    harness: Any = None,
    projects_root: Path | None = None,
) -> ConstructionPlan:
    """Compatibility wrapper supporting optimization_profile ('minimize_cost', 'balanced', 'maximize_capability')."""
    propose = optimization_profile in {"balanced", "maximize_capability", "independent-verification"}
    return build_construction_plan(
        candidate,
        revision=revision,
        sys_spec=sys_spec,
        propose_subworker=propose,
        projects_root=projects_root,
    )

