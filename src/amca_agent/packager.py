"""Post-Construction Verifier, Secret-Redacted Logger, and Handover ZIP Packager."""
from __future__ import annotations

import compileall
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any
import zipfile

from amca.models import CandidateGraph

from .approvals import ConstructionApprovalRecord, SpecApprovalRecord
from .builder import ConstructedProjectLayout
from .formal_verifier import FormalProofCertificate, verify_code_refinement
from .harness import AgentHarnessSession
from .planner import ConstructionPlan


SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_\-]{12,}"),
    re.compile(r"AIza[A-Za-z0-9_\-]{12,}"),
    re.compile(r"AQ\.[A-Za-z0-9_\-]{12,}"),
    re.compile(r"xai-[A-Za-z0-9_\-]{12,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._\-]{12,}"),
)


def redact_secrets(text: str, harness: AgentHarnessSession | None = None) -> str:
    """Redact any active session keys and recognizable credential tokens from logs/artifacts."""
    cleaned = harness.vault.redact_text(text) if harness is not None else text
    for pat in SECRET_PATTERNS:
        cleaned = pat.sub("[REDACTED_SECRET]", cleaned)
    return cleaned


@dataclass(frozen=True)
class HandoverPackageResult:
    machine_id: str
    revision: int
    project_dir: Path
    zip_path: Path
    refined_certificate: FormalProofCertificate
    compile_passed: bool
    unit_tests_passed: bool
    sample_execution_passed: bool
    verification_report: dict[str, Any]
    zip_entries: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "machine_id": self.machine_id,
            "revision": self.revision,
            "project_dir": str(self.project_dir),
            "zip_path": str(self.zip_path),
            "overall_formal_status": self.refined_certificate.overall_status,
            "stage3_status": self.refined_certificate.stage3_refinement_proof.get("status"),
            "compile_passed": self.compile_passed,
            "unit_tests_passed": self.unit_tests_passed,
            "sample_execution_passed": self.sample_execution_passed,
            "verification_report": self.verification_report,
            "zip_entries": list(self.zip_entries),
        }


def append_construction_log(
    log_path: Path,
    event_type: str,
    payload: dict[str, Any],
    *,
    harness: AgentHarnessSession | None = None,
) -> None:
    """Append a single secret-redacted JSONL entry to construction-log.jsonl."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "payload": payload,
    }
    raw_line = json.dumps(entry, sort_keys=True)
    safe_line = redact_secrets(raw_line, harness=harness)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(safe_line + "\n")


def verify_and_package_project(
    *,
    layout: ConstructedProjectLayout,
    candidate: CandidateGraph,
    certificate: FormalProofCertificate,
    spec_approval: SpecApprovalRecord,
    plan: ConstructionPlan,
    construction_approval: ConstructionApprovalRecord,
    harness: AgentHarnessSession | None = None,
    require_stage3_proved: bool = True,
) -> HandoverPackageResult:
    """Run Stage 3 AST refinement proof, compileall, unit tests, sample run, and package Handover ZIP."""
    project_dir = layout.project_dir
    log_path = project_dir / "construction-log.jsonl"

    append_construction_log(
        log_path,
        "construction_started",
        {
            "machine_id": layout.machine_id,
            "revision": layout.revision,
            "candidate_sha256": layout.candidate_sha256,
            "plan_id": layout.plan_id,
            "harness_audit": harness.audit_metadata() if harness else {"mode": "standalone"},
        },
        harness=harness,
    )

    # 1. Stage 3 Formal Code Refinement Proof (AST Isomorphism & Runtime Hoare Guards)
    refined_cert = verify_code_refinement(certificate, candidate, project_dir)
    cert_path = project_dir / "formal-proof-certificate.json"
    cert_path.write_text(
        json.dumps(refined_cert.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    append_construction_log(
        log_path,
        "stage3_formal_refinement_completed",
        {
            "overall_status": refined_cert.overall_status,
            "stage3_status": refined_cert.stage3_refinement_proof.get("status"),
            "certificate_sha256": refined_cert.certificate_sha256,
        },
        harness=harness,
    )
    if require_stage3_proved and refined_cert.overall_status != "PROVED":
        raise RuntimeError(
            f"Stage 3 Formal Refinement Verification REFUTED: "
            f"{[c.as_dict() for c in refined_cert.counterexamples]}"
        )

    # 2. Bytecode compilation check
    compile_ok = bool(compileall.compile_dir(str(project_dir / "src"), quiet=1))
    append_construction_log(
        log_path,
        "bytecode_compilation_checked",
        {"compile_passed": compile_ok},
        harness=harness,
    )
    if not compile_ok:
        raise RuntimeError("Generated Python package failed compileall bytecode check.")

    # 3. Execute generated unittest suite
    env = dict(os.environ)
    env["PYTHONPATH"] = str(project_dir / "src")
    test_proc = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-v"],
        cwd=str(project_dir),
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    tests_ok = test_proc.returncode == 0
    append_construction_log(
        log_path,
        "generated_unit_tests_executed",
        {
            "returncode": test_proc.returncode,
            "unit_tests_passed": tests_ok,
            "stderr_tail": (test_proc.stderr or "")[-600:],
        },
        harness=harness,
    )
    if not tests_ok:
        raise RuntimeError(f"Generated unit tests failed:\n{test_proc.stdout}\n{test_proc.stderr}")

    # 4. Execute sample CLI run
    cli_proc = subprocess.run(
        [sys.executable, "-m", "constructed_machine.cli", "--text", "AMCA builds a graph."],
        cwd=str(project_dir),
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    sample_ok = cli_proc.returncode == 0
    sample_output_json: dict[str, Any] = {}
    if sample_ok:
        try:
            sample_output_json = json.loads(cli_proc.stdout)
            sample_ok = (
                sample_output_json.get("final_output", {}).get("report", {}).get("summary")
                == "characters=20; words=4"
            )
        except Exception:
            sample_ok = False

    append_construction_log(
        log_path,
        "sample_execution_verified",
        {
            "sample_execution_passed": sample_ok,
            "final_output": sample_output_json.get("final_output"),
        },
        harness=harness,
    )
    if not sample_ok:
        raise RuntimeError(f"Sample CLI execution failed verification: {cli_proc.stdout} {cli_proc.stderr}")

    # 5. Write governance & verification artifacts into project_dir
    (project_dir / "spec-approval.json").write_text(
        redact_secrets(json.dumps(spec_approval.as_dict(), indent=2, sort_keys=True), harness=harness) + "\n",
        encoding="utf-8",
    )
    (project_dir / "construction-plan.json").write_text(
        redact_secrets(json.dumps(plan.as_dict(), indent=2, sort_keys=True), harness=harness) + "\n",
        encoding="utf-8",
    )
    (project_dir / "construction-approval.json").write_text(
        redact_secrets(json.dumps(construction_approval.as_dict(), indent=2, sort_keys=True), harness=harness) + "\n",
        encoding="utf-8",
    )

    verification_report = {
        "machine_id": layout.machine_id,
        "revision": layout.revision,
        "candidate_sha256": layout.candidate_sha256,
        "certificate_sha256": refined_cert.certificate_sha256,
        "formal_overall_status": refined_cert.overall_status,
        "stage1_status": refined_cert.stage1_spec_proof.get("status"),
        "stage2_status": refined_cert.stage2_evolution_proof.get("status"),
        "stage3_status": refined_cert.stage3_refinement_proof.get("status"),
        "compile_passed": compile_ok,
        "unit_tests_passed": tests_ok,
        "sample_execution_passed": sample_ok,
        "sample_final_output": sample_output_json.get("final_output"),
        "verified_at": datetime.now(timezone.utc).isoformat(),
    }
    (project_dir / "verification-report.json").write_text(
        redact_secrets(json.dumps(verification_report, indent=2, sort_keys=True), harness=harness) + "\n",
        encoding="utf-8",
    )
    append_construction_log(
        log_path,
        "packaging_handover_zip",
        {"status": "ready"},
        harness=harness,
    )

    # 6. Create <machine_id>-rev<NNN>-handover.zip
    zip_path = project_dir.parent / f"{project_dir.name}-handover.zip"
    zip_entries: list[str] = []
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file_path in sorted(project_dir.rglob("*")):
            if file_path.is_file() and "__pycache__" not in file_path.parts and not file_path.name.endswith(".pyc"):
                arcname = str(file_path.relative_to(project_dir)).replace("\\", "/")
                zf.write(file_path, arcname=arcname)
                zip_entries.append(arcname)

    with zipfile.ZipFile(zip_path, "r") as zf_check:
        bad_file = zf_check.testzip()
        if bad_file is not None:
            raise RuntimeError(f"Corrupt entry in generated handover ZIP: {bad_file}")

    return HandoverPackageResult(
        machine_id=layout.machine_id,
        revision=layout.revision,
        project_dir=project_dir,
        zip_path=zip_path,
        refined_certificate=refined_cert,
        compile_passed=compile_ok,
        unit_tests_passed=tests_ok,
        sample_execution_passed=sample_ok,
        verification_report=verification_report,
        zip_entries=tuple(zip_entries),
    )
