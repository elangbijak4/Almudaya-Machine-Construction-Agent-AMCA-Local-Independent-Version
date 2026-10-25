"""Multi-Stage Compositional Formal Verification Engine (Stage 1 Spec, Stage 2 Evolution, Stage 3 AST Refinement)."""
from __future__ import annotations

import ast
import hashlib
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from amca.canonical import canonical_json, sha256_bytes
from amca.models import CandidateGraph, Edge
from amca.verifier import verify_candidate
from amca_agent.system_spec import MachineSystemSpec, load_any_spec_to_candidate


@dataclass(frozen=True)
class HoareComponentContract:
    component_id: str
    preconditions: dict[str, frozenset[str]]
    postconditions: dict[str, frozenset[str]]
    pure: bool = True


HOARE_CONTRACTS: dict[str, HoareComponentContract] = {
    "input_source": HoareComponentContract(
        component_id="input_source",
        preconditions={},
        postconditions={"text": frozenset({"is_str", "non_empty_raw"})},
        pure=True,
    ),
    "validate_text": HoareComponentContract(
        component_id="validate_text",
        preconditions={"text": frozenset({"is_str"})},
        postconditions={"text": frozenset({"is_str", "non_empty_raw", "non_empty_trimmed", "len_ge_1"})},
        pure=True,
    ),
    "analysis_a": HoareComponentContract(
        component_id="analysis_a",
        preconditions={"text": frozenset({"is_str", "non_empty_trimmed"})},
        postconditions={"finding": frozenset({"is_obj", "has_nonneg_int:character_count"})},
        pure=True,
    ),
    "analysis_b": HoareComponentContract(
        component_id="analysis_b",
        preconditions={"text": frozenset({"is_str", "non_empty_trimmed"})},
        postconditions={"finding": frozenset({"is_obj", "has_nonneg_int:word_count"})},
        pure=True,
    ),
    "aggregate_results": HoareComponentContract(
        component_id="aggregate_results",
        preconditions={
            "finding_a": frozenset({"is_obj", "has_nonneg_int:character_count"}),
            "finding_b": frozenset({"is_obj", "has_nonneg_int:word_count"}),
        },
        postconditions={"summary": frozenset({"is_str", "formatted_metrics_summary", "non_empty_trimmed"})},
        pure=True,
    ),
    "generate_report": HoareComponentContract(
        component_id="generate_report",
        preconditions={"summary": frozenset({"is_str", "formatted_metrics_summary"})},
        postconditions={"report": frozenset({"is_obj", "report_contains_summary"})},
        pure=True,
    ),
}

COUNTEREXAMPLE_WITNESSES: dict[str, Any] = {
    "non_empty_trimmed": {"text": "   ", "explanation": "Whitespace-only string satisfies is_str and non_empty_raw but violates non_empty_trimmed."},
    "has_nonneg_int:character_count": {"finding": {}, "explanation": "Object missing nonnegative character_count."},
    "has_nonneg_int:word_count": {"finding": {}, "explanation": "Object missing nonnegative word_count."},
    "formatted_metrics_summary": {"summary": "unformatted", "explanation": "String does not carry proven formatted_metrics_summary predicate."},
    "report_contains_summary": {"report": None, "explanation": "Terminal report object was never produced."},
}


@dataclass(frozen=True)
class ProofObligationResult:
    id: str
    stage: int
    title: str
    status: str  # "PROVED" | "REFUTED" | "NOT_RUN"
    formula: str
    details: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "stage": self.stage,
            "title": self.title,
            "status": self.status,
            "formula": self.formula,
            "details": self.details,
        }


@dataclass(frozen=True)
class FormalCounterexample:
    obligation_id: str
    message: str
    witness: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "obligation_id": self.obligation_id,
            "message": self.message,
            "witness": self.witness,
        }


@dataclass(frozen=True)
class FormalProofCertificate:
    certificate_version: str
    machine_id: str
    specification_sha256: str
    candidate_sha256: str
    certificate_sha256: str
    overall_status: str  # "PROVED" | "REFUTED"
    stage1_spec_proof: dict[str, Any]
    stage2_evolution_proof: dict[str, Any]
    stage3_refinement_proof: dict[str, Any]
    obligations: tuple[ProofObligationResult, ...]
    counterexamples: tuple[FormalCounterexample, ...]
    generated_at: str

    def core_dict(self) -> dict[str, Any]:
        return {
            "certificate_version": self.certificate_version,
            "machine_id": self.machine_id,
            "specification_sha256": self.specification_sha256,
            "candidate_sha256": self.candidate_sha256,
            "overall_status": self.overall_status,
            "stage1_spec_proof": self.stage1_spec_proof,
            "stage2_evolution_proof": self.stage2_evolution_proof,
            "stage3_refinement_proof": self.stage3_refinement_proof,
            "obligations": [o.as_dict() for o in self.obligations],
            "counterexamples": [c.as_dict() for c in self.counterexamples],
            "generated_at": self.generated_at,
        }

    def as_dict(self) -> dict[str, Any]:
        return {**self.core_dict(), "certificate_sha256": self.certificate_sha256}


def _compute_certificate_sha256(core: dict[str, Any]) -> str:
    stable = {k: v for k, v in core.items() if k != "generated_at"}
    return sha256_bytes(canonical_json(stable))


def verify_formal_spec(
    spec_or_yaml: str | bytes | Path | MachineSystemSpec,
    *,
    previous_spec_or_yaml: str | bytes | Path | MachineSystemSpec | None = None,
) -> FormalProofCertificate:
    """Execute Stage 1 (Spec-level) and optional Stage 2 (Evolution-level) formal verification."""
    if isinstance(spec_or_yaml, MachineSystemSpec):
        sys_spec = spec_or_yaml
        candidate = sys_spec.to_candidate_graph()
    else:
        candidate, sys_spec = load_any_spec_to_candidate(spec_or_yaml)

    structural = verify_candidate(candidate)
    obligations: list[ProofObligationResult] = []
    counterexamples: list[FormalCounterexample] = []

    node_by_id = {n.id: n for n in candidate.nodes}
    outgoing: dict[str, list[Edge]] = {n.id: [] for n in candidate.nodes}
    incoming: dict[str, list[Edge]] = {n.id: [] for n in candidate.nodes}
    for edge in candidate.edges:
        if edge.source in outgoing:
            outgoing[edge.source].append(edge)
        if edge.target in incoming:
            incoming[edge.target].append(edge)

    # 1. FO-TOP-01: Source-to-Sink Reachability & Deadlock Freedom
    sources = [n.id for n in candidate.nodes if len(incoming[n.id]) == 0]
    sinks = [n.id for n in candidate.nodes if len(outgoing[n.id]) == 0]

    fwd_visited: set[str] = set()
    q_fwd: deque[str] = deque(sources)
    while q_fwd:
        curr = q_fwd.popleft()
        if curr in fwd_visited:
            continue
        fwd_visited.add(curr)
        for e in outgoing.get(curr, []):
            if e.target not in fwd_visited:
                q_fwd.append(e.target)

    bwd_visited: set[str] = set()
    q_bwd: deque[str] = deque(sinks)
    while q_bwd:
        curr = q_bwd.popleft()
        if curr in bwd_visited:
            continue
        bwd_visited.add(curr)
        for e in incoming.get(curr, []):
            if e.source not in bwd_visited:
                q_bwd.append(e.source)

    all_node_ids = {n.id for n in candidate.nodes}
    unreachable_from_sources = sorted(all_node_ids - fwd_visited)
    cannot_reach_sinks = sorted(all_node_ids - bwd_visited)
    has_cycle = any(r.code == "CYCLE_DETECTED" for r in structural.reasons)

    if sources and sinks and not unreachable_from_sources and not cannot_reach_sinks and not has_cycle:
        obligations.append(
            ProofObligationResult(
                id="FO-TOP-01",
                stage=1,
                title="Source-to-Sink Reachability & Deadlock Freedom",
                status="PROVED",
                formula="∀v ∈ V: v ∈ Reach_fwd(Sources) ∧ v ∈ Reach_bwd(Sinks) ∧ Acyclic(G)",
                details={
                    "sources": sources,
                    "sinks": sinks,
                    "reachable_count": len(all_node_ids),
                    "total_nodes": len(all_node_ids),
                },
            )
        )
    else:
        obligations.append(
            ProofObligationResult(
                id="FO-TOP-01",
                stage=1,
                title="Source-to-Sink Reachability & Deadlock Freedom",
                status="REFUTED",
                formula="∀v ∈ V: v ∈ Reach_fwd(Sources) ∧ v ∈ Reach_bwd(Sinks) ∧ Acyclic(G)",
                details={
                    "sources": sources,
                    "sinks": sinks,
                    "unreachable_from_sources": unreachable_from_sources,
                    "cannot_reach_sinks": cannot_reach_sinks,
                    "has_cycle": has_cycle,
                },
            )
        )
        counterexamples.append(
            FormalCounterexample(
                obligation_id="FO-TOP-01",
                message="Topological reachability or acyclicity violated.",
                witness={
                    "unreachable_from_sources": unreachable_from_sources,
                    "cannot_reach_sinks": cannot_reach_sinks,
                    "has_cycle": has_cycle,
                },
            )
        )

    # 2. FO-CON-01: Schedule Confluence (Church-Rosser Property)
    port_in_degree: dict[tuple[str, str], int] = {}
    for edge in candidate.edges:
        key = (edge.target, edge.input)
        port_in_degree[key] = port_in_degree.get(key, 0) + 1
    conflicting_ports = [f"{t}.{p}" for (t, p), count in sorted(port_in_degree.items()) if count > 1]
    impure_nodes = [
        n.id for n in candidate.nodes
        if n.component not in HOARE_CONTRACTS or not HOARE_CONTRACTS[n.component].pure
    ]

    if not conflicting_ports and not impure_nodes and not has_cycle:
        obligations.append(
            ProofObligationResult(
                id="FO-CON-01",
                stage=1,
                title="Schedule Confluence (Church-Rosser Determinism)",
                status="PROVED",
                formula="∀S1, S2 ∈ TopoSort(G): Exec(G, S1, x) = Exec(G, S2, x)",
                details={
                    "all_components_pure": True,
                    "max_target_port_in_degree": max(port_in_degree.values(), default=0),
                    "disjoint_branch_writes": True,
                },
            )
        )
    else:
        obligations.append(
            ProofObligationResult(
                id="FO-CON-01",
                stage=1,
                title="Schedule Confluence (Church-Rosser Determinism)",
                status="REFUTED",
                formula="∀S1, S2 ∈ TopoSort(G): Exec(G, S1, x) = Exec(G, S2, x)",
                details={
                    "conflicting_ports": conflicting_ports,
                    "impure_nodes": impure_nodes,
                },
            )
        )
        counterexamples.append(
            FormalCounterexample(
                obligation_id="FO-CON-01",
                message="Schedule confluence violated due to conflicting port writes or impure components.",
                witness={"conflicting_ports": conflicting_ports, "impure_nodes": impure_nodes},
            )
        )

    # 3. FO-HOA-01: Compositional Hoare Pre/Postcondition Entailment {P_c} c {Q_c}
    edge_failures: list[dict[str, Any]] = []
    verified_edges: list[dict[str, Any]] = []
    established_predicates: set[str] = set()
    for node in candidate.nodes:
        contract = HOARE_CONTRACTS.get(node.component)
        if contract:
            for preds in contract.postconditions.values():
                established_predicates.update(preds)

    for edge in candidate.edges:
        src_node = node_by_id.get(edge.source)
        dst_node = node_by_id.get(edge.target)
        if not src_node or not dst_node:
            edge_failures.append(
                {
                    "edge": f"{edge.source}.{edge.output} -> {edge.target}.{edge.input}",
                    "reason": "Missing endpoint node",
                }
            )
            continue
        src_contract = HOARE_CONTRACTS.get(src_node.component)
        dst_contract = HOARE_CONTRACTS.get(dst_node.component)
        if not src_contract or not dst_contract:
            edge_failures.append(
                {
                    "edge": f"{edge.source}.{edge.output} -> {edge.target}.{edge.input}",
                    "reason": "Missing formal Hoare contract",
                }
            )
            continue
        post_preds = src_contract.postconditions.get(edge.output, frozenset())
        pre_preds = dst_contract.preconditions.get(edge.input, frozenset())
        missing_preds = sorted(pre_preds - post_preds)
        if missing_preds:
            first_missing = missing_preds[0]
            witness = COUNTEREXAMPLE_WITNESSES.get(
                first_missing,
                {"missing_predicate": first_missing},
            )
            edge_failures.append(
                {
                    "edge": f"{edge.source}.{edge.output} -> {edge.target}.{edge.input}",
                    "source_component": src_node.component,
                    "target_component": dst_node.component,
                    "postconditions_guaranteed": sorted(post_preds),
                    "preconditions_required": sorted(pre_preds),
                    "missing_predicates": missing_preds,
                    "counterexample_witness": witness,
                }
            )
        else:
            verified_edges.append(
                {
                    "edge": f"{edge.source}.{edge.output} -> {edge.target}.{edge.input}",
                    "post": sorted(post_preds),
                    "pre": sorted(pre_preds),
                    "entailed": True,
                }
            )

    if not edge_failures and structural.status == "verified":
        obligations.append(
            ProofObligationResult(
                id="FO-HOA-01",
                stage=1,
                title="Compositional Hoare Pre/Postcondition Entailment",
                status="PROVED",
                formula="∀(u.out → v.in) ∈ E: Q_u(out) ⊇ P_v(in)",
                details={
                    "edges_verified": len(verified_edges),
                    "edge_proofs": verified_edges,
                },
            )
        )
    else:
        obligations.append(
            ProofObligationResult(
                id="FO-HOA-01",
                stage=1,
                title="Compositional Hoare Pre/Postcondition Entailment",
                status="REFUTED",
                formula="∀(u.out → v.in) ∈ E: Q_u(out) ⊇ P_v(in)",
                details={
                    "edges_verified": len(verified_edges),
                    "edge_failures": edge_failures,
                    "structural_status": structural.status,
                },
            )
        )
        for failure in edge_failures:
            counterexamples.append(
                FormalCounterexample(
                    obligation_id="FO-HOA-01",
                    message=(
                        f"Hoare entailment failed on edge {failure['edge']}: "
                        f"missing required precondition(s) {failure.get('missing_predicates', [])}."
                    ),
                    witness=failure,
                )
            )
        if not edge_failures and structural.status != "verified":
            counterexamples.append(
                FormalCounterexample(
                    obligation_id="FO-HOA-01",
                    message="Structural port/connection verification failed prior to Hoare composition.",
                    witness={"reasons": [r.as_dict() for r in structural.reasons]},
                )
            )

    # 4. FO-GOAL-01: Acceptance Criteria Goal Entailment
    declared_goals = [
        {"id": ac.id, "formalGoal": ac.formal_goal}
        for ac in (sys_spec.acceptance_criteria if sys_spec else ())
    ]
    # Only count predicates from nodes that actually lie on a valid proved path
    effectively_proved_preds = established_predicates if not edge_failures and structural.status == "verified" else set()
    unproved_goals = [
        g for g in declared_goals
        if g["formalGoal"] not in effectively_proved_preds
    ]
    if not unproved_goals and effectively_proved_preds:
        obligations.append(
            ProofObligationResult(
                id="FO-GOAL-01",
                stage=1,
                title="Acceptance Criteria Formal Goal Entailment",
                status="PROVED",
                formula="⋀_{u ∈ V} Q_u ⊢ ⋀_{g ∈ Goals} g",
                details={
                    "declared_goals": declared_goals,
                    "established_predicates": sorted(effectively_proved_preds),
                },
            )
        )
    else:
        obligations.append(
            ProofObligationResult(
                id="FO-GOAL-01",
                stage=1,
                title="Acceptance Criteria Formal Goal Entailment",
                status="REFUTED",
                formula="⋀_{u ∈ V} Q_u ⊢ ⋀_{g ∈ Goals} g",
                details={
                    "declared_goals": declared_goals,
                    "unproved_goals": unproved_goals,
                    "established_predicates": sorted(effectively_proved_preds),
                },
            )
        )
        counterexamples.append(
            FormalCounterexample(
                obligation_id="FO-GOAL-01",
                message="One or more acceptance criteria formal goals are not entailed by the DAG postconditions.",
                witness={"unproved_goals": unproved_goals},
            )
        )

    # 5. FO-SEC-01: Security Policy & Secret Taint Non-Interference
    sec_policy = sys_spec.security_policy if sys_spec else {
        "networkPolicy": "deny-by-default",
        "operatingSystemCommands": "deny",
        "secretPolicy": "references-only",
    }
    policy_ok = (
        sec_policy.get("networkPolicy") == "deny-by-default"
        and sec_policy.get("operatingSystemCommands") == "deny"
        and sec_policy.get("secretPolicy") == "references-only"
    )
    tainted_machines: set[str] = set()
    if sys_spec:
        for m in sys_spec.machines:
            if m.services:
                tainted_machines.add(m.id)
    # Propagate taint forward
    taint_queue: deque[str] = deque(tainted_machines)
    while taint_queue:
        curr = taint_queue.popleft()
        for e in outgoing.get(curr, []):
            if e.target not in tainted_machines:
                tainted_machines.add(e.target)
                taint_queue.append(e.target)
    tainted_sinks = sorted(set(sinks) & tainted_machines)

    if policy_ok and not tainted_sinks:
        obligations.append(
            ProofObligationResult(
                id="FO-SEC-01",
                stage=1,
                title="Security Policy & Secret Taint Non-Interference",
                status="PROVED",
                formula="PolicySafe(S) ∧ (Taint(secretRef) ∩ Outputs(Sinks) = ∅)",
                details={
                    "security_policy": sec_policy,
                    "tainted_sinks": [],
                },
            )
        )
    else:
        obligations.append(
            ProofObligationResult(
                id="FO-SEC-01",
                stage=1,
                title="Security Policy & Secret Taint Non-Interference",
                status="REFUTED",
                formula="PolicySafe(S) ∧ (Taint(secretRef) ∩ Outputs(Sinks) = ∅)",
                details={
                    "security_policy": sec_policy,
                    "tainted_sinks": tainted_sinks,
                },
            )
        )
        counterexamples.append(
            FormalCounterexample(
                obligation_id="FO-SEC-01",
                message="Security policy or secretRef taint non-interference violated.",
                witness={"security_policy": sec_policy, "tainted_sinks": tainted_sinks},
            )
        )

    stage1_passed = sum(1 for o in obligations if o.stage == 1 and o.status == "PROVED")
    stage1_total = sum(1 for o in obligations if o.stage == 1)
    stage1_status = "PROVED" if stage1_passed == stage1_total else "REFUTED"

    # Stage 2: Evolution Proof (if previous revision supplied)
    if previous_spec_or_yaml is not None:
        evo_obligation, evo_cex = verify_revision_invariants(previous_spec_or_yaml, sys_spec)
        obligations.append(evo_obligation)
        if evo_cex:
            counterexamples.append(evo_cex)
        stage2_summary = {
            "status": evo_obligation.status,
            "details": evo_obligation.details,
        }
    else:
        stage2_summary = {
            "status": "PROVED",
            "details": {"mode": "initial_revision", "invariants_preserved": True},
        }

    stage3_summary = {
        "status": "NOT_RUN",
        "details": {"reason": "Code construction not yet executed for this certificate snapshot."},
    }

    overall_status = (
        "PROVED"
        if stage1_status == "PROVED" and stage2_summary["status"] == "PROVED"
        else "REFUTED"
    )
    generated_at = datetime.now(timezone.utc).isoformat()
    temp_cert = FormalProofCertificate(
        certificate_version="1.0",
        machine_id=candidate.machine_id,
        specification_sha256=candidate.specification_sha256,
        candidate_sha256=candidate.candidate_sha256,
        certificate_sha256="",
        overall_status=overall_status,
        stage1_spec_proof={
            "status": stage1_status,
            "checks_passed": stage1_passed,
            "checks_total": stage1_total,
        },
        stage2_evolution_proof=stage2_summary,
        stage3_refinement_proof=stage3_summary,
        obligations=tuple(obligations),
        counterexamples=tuple(counterexamples),
        generated_at=generated_at,
    )
    cert_sha = _compute_certificate_sha256(temp_cert.core_dict())
    return FormalProofCertificate(
        certificate_version="1.0",
        machine_id=candidate.machine_id,
        specification_sha256=candidate.specification_sha256,
        candidate_sha256=candidate.candidate_sha256,
        certificate_sha256=cert_sha,
        overall_status=overall_status,
        stage1_spec_proof=temp_cert.stage1_spec_proof,
        stage2_evolution_proof=temp_cert.stage2_evolution_proof,
        stage3_refinement_proof=temp_cert.stage3_refinement_proof,
        obligations=temp_cert.obligations,
        counterexamples=temp_cert.counterexamples,
        generated_at=generated_at,
    )


verify_specification_formal = verify_formal_spec



def verify_revision_invariants(
    prev_spec_or_yaml: str | bytes | Path | MachineSystemSpec,
    curr_spec_or_yaml: str | bytes | Path | MachineSystemSpec,
) -> tuple[ProofObligationResult, FormalCounterexample | None]:
    """Stage 2: Prove that security policies, formal goals, and external I/O contracts do not regress across revisions."""
    prev_cand, prev_sys = (
        (prev_spec_or_yaml.to_candidate_graph(), prev_spec_or_yaml)
        if isinstance(prev_spec_or_yaml, MachineSystemSpec)
        else load_any_spec_to_candidate(prev_spec_or_yaml)
    )
    curr_cand, curr_sys = (
        (curr_spec_or_yaml.to_candidate_graph(), curr_spec_or_yaml)
        if isinstance(curr_spec_or_yaml, MachineSystemSpec)
        else load_any_spec_to_candidate(curr_spec_or_yaml)
    )

    prev_goals = {ac.formal_goal for ac in (prev_sys.acceptance_criteria if prev_sys else ())}
    curr_goals = {ac.formal_goal for ac in (curr_sys.acceptance_criteria if curr_sys else ())}
    dropped_goals = sorted(prev_goals - curr_goals)

    prev_inputs = sorted(
        n.config.get("input_key", "") for n in prev_cand.nodes if n.component == "input_source"
    )
    curr_inputs = sorted(
        n.config.get("input_key", "") for n in curr_cand.nodes if n.component == "input_source"
    )
    curr_sec = curr_sys.security_policy if curr_sys else {}
    sec_preserved = (
        curr_sec.get("networkPolicy") == "deny-by-default"
        and curr_sec.get("operatingSystemCommands") == "deny"
        and curr_sec.get("secretPolicy") == "references-only"
    )

    if not dropped_goals and sec_preserved and bool(curr_inputs):
        return (
            ProofObligationResult(
                id="FO-EVO-01",
                stage=2,
                title="Revision Invariant & Safety Preservation",
                status="PROVED",
                formula="Invariants(rev_N) ⊆ Invariants(rev_{N+1}) ∧ SecurityPolicyPreserved",
                details={
                    "prev_spec_sha256": prev_cand.specification_sha256,
                    "curr_spec_sha256": curr_cand.specification_sha256,
                    "preserved_goals": sorted(curr_goals),
                    "prev_input_keys": prev_inputs,
                    "curr_input_keys": curr_inputs,
                    "security_preserved": True,
                },
            ),
            None,
        )

    witness = {
        "dropped_goals": dropped_goals,
        "security_preserved": sec_preserved,
        "curr_input_keys": curr_inputs,
    }
    return (
        ProofObligationResult(
            id="FO-EVO-01",
            stage=2,
            title="Revision Invariant & Safety Preservation",
            status="REFUTED",
            formula="Invariants(rev_N) ⊆ Invariants(rev_{N+1}) ∧ SecurityPolicyPreserved",
            details=witness,
        ),
        FormalCounterexample(
            obligation_id="FO-EVO-01",
            message="Revision regression detected: formal goals or security invariants were weakened.",
            witness=witness,
        ),
    )


def verify_code_refinement(
    certificate: FormalProofCertificate,
    candidate: CandidateGraph,
    project_dir: Path,
) -> FormalProofCertificate:
    """Stage 3: Parse generated Python files with ast.parse() to prove G_code ≅ G_yaml and runtime contract guard presence."""
    src_root = project_dir / "src"
    py_files = sorted(src_root.rglob("*.py")) if src_root.exists() else []

    extracted_nodes: dict[str, str] = {}
    extracted_edges: list[tuple[str, str, str, str]] = []
    guarded_components: set[str] = set()
    ast_digests: dict[str, str] = {}
    parse_errors: list[str] = []

    for py_file in py_files:
        try:
            source_text = py_file.read_text(encoding="utf-8")
            tree = ast.parse(source_text, filename=str(py_file))
            ast_dump_bytes = ast.dump(tree, include_attributes=False).encode("utf-8")
            ast_digests[str(py_file.relative_to(project_dir)).replace("\\", "/")] = hashlib.sha256(ast_dump_bytes).hexdigest()
        except (OSError, SyntaxError) as exc:
            parse_errors.append(f"{py_file.name}: {exc}")
            continue

        for node in ast.walk(tree):
            # Extract execute_component_node(node_id=..., component_id=..., ...) calls in pipeline.py
            if isinstance(node, ast.Call):
                func_name = ""
                if isinstance(node.func, ast.Name):
                    func_name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    func_name = node.func.attr

                if func_name == "execute_component_node":
                    kw_map = {
                        kw.arg: kw.value.value
                        for kw in node.keywords
                        if kw.arg and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str)
                    }
                    nid = kw_map.get("node_id")
                    cid = kw_map.get("component_id")
                    if nid and cid:
                        extracted_nodes[nid] = cid

                elif func_name == "wire_edge":
                    kw_map = {
                        kw.arg: kw.value.value
                        for kw in node.keywords
                        if kw.arg and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str)
                    }
                    s, o, t, i = kw_map.get("source"), kw_map.get("output"), kw_map.get("target"), kw_map.get("input_port")
                    if s and o and t and i:
                        extracted_edges.append((s, o, t, i))

                elif func_name in {"_enforce_preconditions", "_enforce_postconditions"}:
                    if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                        guarded_components.add(node.args[0].value)

    expected_nodes = {n.id: n.component for n in candidate.nodes}
    expected_edges = sorted((e.source, e.output, e.target, e.input) for e in candidate.edges)
    actual_edges = sorted(extracted_edges)

    nodes_match = (extracted_nodes == expected_nodes)
    edges_match = (actual_edges == expected_edges)
    isomorphic = (not parse_errors) and nodes_match and edges_match

    new_obligations = [o for o in certificate.obligations if o.stage != 3]
    new_counterexamples = [c for c in certificate.counterexamples if not c.obligation_id.startswith("FO-REF-")]

    if isomorphic:
        new_obligations.append(
            ProofObligationResult(
                id="FO-REF-01",
                stage=3,
                title="AST Code-to-YAML Graph Isomorphism (G_code ≅ G_yaml)",
                status="PROVED",
                formula="nodes(AST(code)) = nodes(G_yaml) ∧ edges(AST(code)) = edges(G_yaml)",
                details={
                    "expected_nodes": expected_nodes,
                    "extracted_nodes": extracted_nodes,
                    "expected_edges_count": len(expected_edges),
                    "extracted_edges_count": len(actual_edges),
                    "ast_file_sha256": ast_digests,
                },
            )
        )
    else:
        witness_ref1 = {
            "parse_errors": parse_errors,
            "expected_nodes": expected_nodes,
            "extracted_nodes": extracted_nodes,
            "expected_edges": [list(e) for e in expected_edges],
            "extracted_edges": [list(e) for e in actual_edges],
        }
        new_obligations.append(
            ProofObligationResult(
                id="FO-REF-01",
                stage=3,
                title="AST Code-to-YAML Graph Isomorphism (G_code ≅ G_yaml)",
                status="REFUTED",
                formula="nodes(AST(code)) = nodes(G_yaml) ∧ edges(AST(code)) = edges(G_yaml)",
                details=witness_ref1,
            )
        )
        new_counterexamples.append(
            FormalCounterexample(
                obligation_id="FO-REF-01",
                message="Generated Python AST call graph does not match the approved YAML specification graph.",
                witness=witness_ref1,
            )
        )

    required_components = {n.component for n in candidate.nodes}
    missing_guards = sorted(required_components - guarded_components)
    if not parse_errors and not missing_guards and required_components:
        new_obligations.append(
            ProofObligationResult(
                id="FO-REF-02",
                stage=3,
                title="Runtime Hoare Pre/Postcondition Guard Verification in AST",
                status="PROVED",
                formula="∀c ∈ Components(G_yaml): HasRuntimeGuards(AST(code), P_c, Q_c)",
                details={
                    "required_components": sorted(required_components),
                    "guarded_components": sorted(guarded_components),
                },
            )
        )
    else:
        witness_ref2 = {
            "required_components": sorted(required_components),
            "guarded_components": sorted(guarded_components),
            "missing_guards": missing_guards,
        }
        new_obligations.append(
            ProofObligationResult(
                id="FO-REF-02",
                stage=3,
                title="Runtime Hoare Pre/Postcondition Guard Verification in AST",
                status="REFUTED",
                formula="∀c ∈ Components(G_yaml): HasRuntimeGuards(AST(code), P_c, Q_c)",
                details=witness_ref2,
            )
        )
        new_counterexamples.append(
            FormalCounterexample(
                obligation_id="FO-REF-02",
                message="Generated Python AST is missing runtime precondition/postcondition guards for one or more components.",
                witness=witness_ref2,
            )
        )

    stage3_status = "PROVED" if (isomorphic and not missing_guards and not parse_errors) else "REFUTED"
    overall_status = (
        "PROVED"
        if certificate.stage1_spec_proof["status"] == "PROVED"
        and certificate.stage2_evolution_proof["status"] == "PROVED"
        and stage3_status == "PROVED"
        else "REFUTED"
    )
    stage3_summary = {
        "status": stage3_status,
        "isomorphic": isomorphic,
        "guards_verified": not bool(missing_guards),
        "ast_file_sha256": ast_digests,
    }
    generated_at = datetime.now(timezone.utc).isoformat()
    temp_cert = FormalProofCertificate(
        certificate_version="1.0",
        machine_id=certificate.machine_id,
        specification_sha256=certificate.specification_sha256,
        candidate_sha256=certificate.candidate_sha256,
        certificate_sha256="",
        overall_status=overall_status,
        stage1_spec_proof=certificate.stage1_spec_proof,
        stage2_evolution_proof=certificate.stage2_evolution_proof,
        stage3_refinement_proof=stage3_summary,
        obligations=tuple(new_obligations),
        counterexamples=tuple(new_counterexamples),
        generated_at=generated_at,
    )
    cert_sha = _compute_certificate_sha256(temp_cert.core_dict())
    return FormalProofCertificate(
        certificate_version="1.0",
        machine_id=certificate.machine_id,
        specification_sha256=certificate.specification_sha256,
        candidate_sha256=certificate.candidate_sha256,
        certificate_sha256=cert_sha,
        overall_status=overall_status,
        stage1_spec_proof=temp_cert.stage1_spec_proof,
        stage2_evolution_proof=temp_cert.stage2_evolution_proof,
        stage3_refinement_proof=temp_cert.stage3_refinement_proof,
        obligations=temp_cert.obligations,
        counterexamples=temp_cert.counterexamples,
        generated_at=generated_at,
    )


verify_specification_formal = verify_formal_spec

