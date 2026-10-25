"""Two-stage cryptographic approval service (Approval A spec_approval & Approval B construction_approval)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from amca.models import CandidateGraph, VerificationReport
from amca_agent.formal_verifier import FormalProofCertificate

ROOT = Path(__file__).resolve().parents[2]
CONSTRUCTED_PROJECTS_ROOT = (ROOT / "artifacts" / "constructed_projects").resolve()


@dataclass(frozen=True)
class SpecApprovalRecord:
    session_id: str
    machine_id: str
    revision: int
    specification_sha256: str
    candidate_sha256: str
    certificate_sha256: str
    confirmation_token: str
    approved_by: str
    approved_at: str

    @property
    def approval_id(self) -> str:
        return f"spec-approval-{self.machine_id}-rev{self.revision:03d}-{self.specification_sha256[:8]}"

    def as_dict(self) -> dict[str, Any]:
        return {
            "approval_id": self.approval_id,
            "approval_type": "spec_approval",
            "session_id": self.session_id,
            "machine_id": self.machine_id,
            "revision": self.revision,
            "specification_sha256": self.specification_sha256,
            "candidate_sha256": self.candidate_sha256,
            "certificate_sha256": self.certificate_sha256,
            "confirmation_token": self.confirmation_token,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at,
        }


@dataclass(frozen=True)
class ConstructionApprovalRecord:
    session_id: str
    machine_id: str
    revision: int
    specification_sha256: str
    certificate_sha256: str
    destination_dir: str
    sdlc_method: str
    worker_policy: str
    use_subagents: bool
    confirmation_token: str
    approved_by: str
    approved_at: str

    @property
    def approval_id(self) -> str:
        return f"construction-approval-{self.machine_id}-rev{self.revision:03d}-{self.specification_sha256[:8]}"

    def as_dict(self) -> dict[str, Any]:
        return {
            "approval_id": self.approval_id,
            "approval_type": "construction_approval",
            "session_id": self.session_id,
            "machine_id": self.machine_id,
            "revision": self.revision,
            "specification_sha256": self.specification_sha256,
            "certificate_sha256": self.certificate_sha256,
            "destination_dir": self.destination_dir,
            "sdlc_method": self.sdlc_method,
            "worker_policy": self.worker_policy,
            "use_subagents": self.use_subagents,
            "confirmation_token": self.confirmation_token,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at,
        }


def resolve_bounded_construction_dir(
    machine_id: str,
    revision: int,
    *,
    projects_root: Path | None = None,
) -> Path:
    """Resolve and verify that the construction directory stays strictly inside artifacts/constructed_projects/."""
    base_root = (projects_root or CONSTRUCTED_PROJECTS_ROOT).resolve()
    safe_name = f"{machine_id}-rev{revision:03d}"
    if "/" in safe_name or "\\" in safe_name or ".." in safe_name:
        raise ValueError(f"Invalid construction directory name: {safe_name!r}")
    target = (base_root / safe_name).resolve()
    if base_root not in target.parents:
        raise ValueError("Construction destination escapes allowed constructed_projects root.")
    return target


def record_spec_approval(
    *,
    session_id: str,
    revision: int,
    candidate: CandidateGraph,
    verification: VerificationReport,
    formal_certificate: FormalProofCertificate,
    confirmation_token: str,
    approved_by: str = "user",
) -> SpecApprovalRecord:
    """Enforce Approval A: requires structural 'verified', Stage 1 'PROVED', and token 'APPROVE_SPEC'."""
    if confirmation_token != "APPROVE_SPEC":
        raise PermissionError("Approval A requires exact confirmation token 'APPROVE_SPEC'.")
    if verification.status != "verified":
        raise PermissionError("Approval A denied: specification is not structurally 'verified'.")
    if formal_certificate.stage1_spec_proof.get("status") != "PROVED":
        raise PermissionError("Approval A denied: Stage 1 Formal Verification status is not 'PROVED'.")
    if formal_certificate.specification_sha256 != candidate.specification_sha256:
        raise PermissionError("Approval A denied: formal certificate SHA-256 does not match candidate specification.")

    return SpecApprovalRecord(
        session_id=session_id,
        machine_id=candidate.machine_id,
        revision=revision,
        specification_sha256=candidate.specification_sha256,
        candidate_sha256=candidate.candidate_sha256,
        certificate_sha256=formal_certificate.certificate_sha256,
        confirmation_token=confirmation_token,
        approved_by=approved_by,
        approved_at=datetime.now(timezone.utc).isoformat(),
    )


def record_construction_approval(
    *,
    spec_approval: SpecApprovalRecord,
    candidate: CandidateGraph,
    formal_certificate: FormalProofCertificate,
    confirmation_token: str,
    sdlc_method: str = "waterfall",
    worker_policy: str = "minimize-cost",
    use_subagents: bool = False,
    approved_by: str = "user",
    projects_root: Path | None = None,
) -> ConstructionApprovalRecord:
    """Enforce Approval B: binds to valid Approval A, checks digests, and confines destination directory."""
    if confirmation_token != "APPROVE_CONSTRUCTION":
        raise PermissionError("Approval B requires exact confirmation token 'APPROVE_CONSTRUCTION'.")
    if spec_approval.specification_sha256 != candidate.specification_sha256:
        raise PermissionError("Approval B denied: current YAML SHA-256 differs from locked Approval A digest.")
    if spec_approval.certificate_sha256 != formal_certificate.certificate_sha256:
        raise PermissionError("Approval B denied: formal certificate digest differs from locked Approval A digest.")
    if sdlc_method != "waterfall":
        raise ValueError("Only 'waterfall' SDLC method is supported.")

    dest = resolve_bounded_construction_dir(
        candidate.machine_id,
        spec_approval.revision,
        projects_root=projects_root,
    )
    return ConstructionApprovalRecord(
        session_id=spec_approval.session_id,
        machine_id=candidate.machine_id,
        revision=spec_approval.revision,
        specification_sha256=spec_approval.specification_sha256,
        certificate_sha256=spec_approval.certificate_sha256,
        destination_dir=str(dest),
        sdlc_method=sdlc_method,
        worker_policy=worker_policy,
        use_subagents=use_subagents,
        confirmation_token=confirmation_token,
        approved_by=approved_by,
        approved_at=datetime.now(timezone.utc).isoformat(),
    )


def validate_approvals_for_construction(
    spec_approval: SpecApprovalRecord | None,
    construction_approval: ConstructionApprovalRecord | None,
    *,
    candidate: CandidateGraph,
    certificate: FormalProofCertificate,
) -> None:
    """Verify both Stage 1 and Stage 2 approvals match the current candidate and formal certificate SHA-256."""
    if spec_approval is None:
        raise PermissionError("Construction blocked: Stage 1 spec_approval is missing.")
    if construction_approval is None:
        raise PermissionError("Construction blocked: Stage 2 construction_approval is missing.")
    if spec_approval.confirmation_token != "APPROVE_SPEC":
        raise PermissionError("Construction blocked: invalid spec_approval token.")
    if construction_approval.confirmation_token != "APPROVE_CONSTRUCTION":
        raise PermissionError("Construction blocked: invalid construction_approval token.")
    if (
        spec_approval.specification_sha256 != candidate.specification_sha256
        or construction_approval.specification_sha256 != candidate.specification_sha256
    ):
        raise PermissionError("Construction blocked: specification SHA-256 changed after approval.")
    if (
        spec_approval.certificate_sha256 != certificate.certificate_sha256
        or construction_approval.certificate_sha256 != certificate.certificate_sha256
    ):
        raise PermissionError("Construction blocked: formal proof certificate SHA-256 changed after approval.")

