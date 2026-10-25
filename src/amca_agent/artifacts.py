"""Local persistence helpers for YAML versions, formal proof certificates, approvals, and execution evidence."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_ROOT = ROOT / "artifacts"


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def save_chat(
    session_id: str,
    messages: list[dict[str, str]],
    versions: list[dict[str, Any]],
    *,
    metadata: dict[str, Any] | None = None,
) -> Path:
    """Persist local chat, YAML versions, and non-secret governance metadata. API credentials are never accepted here."""
    safe_id = re.sub(r"[^a-f0-9-]", "", session_id) or "default-session"
    folder = ARTIFACT_ROOT / "agent_sessions" / safe_id
    folder.mkdir(parents=True, exist_ok=True)
    for index, version in enumerate(versions, 1):
        (folder / f"spec-v{index:03}.yaml").write_text(version["yaml"], encoding="utf-8")
        if isinstance(version.get("formal_certificate"), dict):
            _write_json(folder / f"formal-proof-v{index:03}.json", version["formal_certificate"])
    payload: dict[str, Any] = {
        "session_id": safe_id,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "messages": messages,
        "versions": [
            {k: v for k, v in item.items() if k != "yaml"} | {"yaml_file": f"spec-v{i:03}.yaml"}
            for i, item in enumerate(versions, 1)
        ],
    }
    if metadata:
        payload["metadata"] = metadata
    _write_json(folder / "session.json", payload)
    return folder


def list_sessions() -> list[Path]:
    root = ARTIFACT_ROOT / "agent_sessions"
    return sorted(root.glob("*/session.json"), reverse=True) if root.exists() else []


def load_chat(path: Path) -> dict[str, Any]:
    """Load a local chat using only its selected session directory."""
    folder = path.parent.resolve()
    if folder.parent != (ARTIFACT_ROOT / "agent_sessions").resolve():
        raise ValueError("Invalid session path")
    data = json.loads(path.read_text(encoding="utf-8"))
    versions = []
    for item in data.get("versions", []):
        name = item.get("yaml_file", "")
        if not re.fullmatch(r"spec-v\d{3}\.yaml", name):
            continue
        versions.append({**item, "yaml": (folder / name).read_text(encoding="utf-8")})
    data["versions"] = versions
    return data


def save_run(
    spec_yaml: str,
    verification: dict[str, Any],
    candidate: dict[str, Any] | None,
    dot: str | None,
    execution: dict[str, Any] | None,
    status: str,
    *,
    formal_certificate: dict[str, Any] | None = None,
) -> Path:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    folder = ARTIFACT_ROOT / "runs" / run_id
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "machine.yaml").write_text(spec_yaml, encoding="utf-8")
    _write_json(folder / "verification-report.json", verification)
    if formal_certificate is not None:
        _write_json(folder / "formal-proof-certificate.json", formal_certificate)
    if candidate is not None:
        _write_json(folder / "candidate-graph.json", candidate)
    if dot is not None:
        (folder / "machine-dag.dot").write_text(dot, encoding="utf-8")
    if execution is not None:
        _write_json(folder / "execution-record.json", execution)
    _write_json(
        folder / "manifest.json",
        {"run_id": run_id, "status": status, "created_at": datetime.now(timezone.utc).isoformat()},
    )
    return folder
