"""CLI for the AMCA Specialized Agent Harness, Formal Verifier, and Bounded Project Constructor."""
from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any

from amca.errors import AMCAError
from amca.runtime import run
from amca.verifier import verify_candidate
from amca_agent.approvals import (
    record_construction_approval,
    record_spec_approval,
)
from amca_agent.artifacts import ARTIFACT_ROOT, ROOT, list_sessions, load_chat, save_chat, save_run
from amca_agent.builder import DEFAULT_CONSTRUCTED_PROJECTS_DIR, build_constructed_project
from amca_agent.formal_verifier import verify_specification_formal
from amca_agent.graph import to_dot
from amca_agent.hardware import (
    CURATED_LOCAL_MODELS,
    evaluate_local_model_eligibility,
    inspect_host_hardware,
)
from amca_agent.harness import AgentHarnessSession, SubworkerProposal
from amca_agent.intent import classify_intent
from amca_agent.packager import verify_and_package_project
from amca_agent.planner import generate_construction_plan
from amca_agent.provider import (
    DEFAULT_MODELS,
    ProviderError,
    discover_provider_models,
    generate_yaml,
)
from amca_agent.system_spec import load_any_spec_to_candidate


def _check(text: str, previous_yaml: str | None = None):
    candidate, _ = load_any_spec_to_candidate(text.encode("utf-8"))
    verification = verify_candidate(candidate)
    formal_cert = verify_specification_formal(
        text.encode("utf-8"),
        previous_spec_or_yaml=previous_yaml.encode("utf-8") if previous_yaml else None,
    )
    return candidate, verification, formal_cert


def _json(value: Any, output: str | None = None) -> None:
    rendered = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if output:
        Path(output).write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)


def _yaml(value: str, output: str | None = None) -> None:
    if output:
        Path(output).write_text(value.rstrip() + "\n", encoding="utf-8")
    else:
        print(value)


def _examples() -> list[Path]:
    return sorted((ROOT / "examples").glob("*.yaml"))


def _example(name: str) -> Path:
    matches = [p for p in _examples() if p.name == name or p.stem == name]
    if len(matches) != 1:
        raise ValueError(f"Contoh tidak ditemukan atau ambigu: {name}")
    return matches[0]


def _rejected(message: str) -> dict[str, Any]:
    return {
        "report_version": "1.0",
        "status": "rejected",
        "candidate_sha256": None,
        "profile_id": "not_constructed",
        "checks": [],
        "reasons": [{"message": message}],
        "assumptions": [],
    }


def _record(
    session_id: str,
    messages: list[dict[str, str]],
    versions: list[dict[str, Any]],
    source: str,
) -> tuple[Any, Any, Any, str | None]:
    text = versions[-1]["yaml"]
    prev_yaml = versions[-2]["yaml"] if len(versions) >= 2 else None
    try:
        candidate, verification, formal_cert = _check(text, previous_yaml=prev_yaml)
        error = None
        dot = to_dot(candidate) if verification.status == "verified" else None
        record = verification.as_dict()
        status = verification.status
        formal_dict = formal_cert.as_dict()
        formal_status = formal_cert.overall_status
    except AMCAError as exc:
        candidate = verification = formal_cert = dot = None
        error = getattr(exc, "message", str(exc))
        record, status = _rejected(error), "rejected"
        formal_dict = None
        formal_status = "REFUTED"
    versions[-1].update(
        {
            "source": source,
            "validation_status": status,
            "formal_status": formal_status,
            "formal_certificate": formal_dict,
            "error": error,
        }
    )
    save_run(
        text,
        record,
        candidate.as_dict() if candidate else None,
        dot,
        None,
        status,
        formal_certificate=formal_dict,
    )
    save_chat(session_id, messages, versions)
    return candidate, verification, formal_cert, error


def _provider_args(args) -> tuple[str, str, str]:
    provider = getattr(args, "provider", "Gemini") or "Gemini"
    model = getattr(args, "model", None) or DEFAULT_MODELS.get(provider, "gemini-3.8-flash")
    if provider.strip().lower() in {"offline deterministic", "offline_deterministic", "ollama", "lm_studio", "lm studio", "opencode", "local_model", "local model"}:
        return provider, model, os.environ.get("AMCA_API_KEY", "")
    key = os.environ.get("AMCA_API_KEY", "")
    if not key:
        key = getpass.getpass(f"API key {provider} (tidak disimpan): ")
    return provider, model, key


def _generate(args, history: list[dict[str, str]], current: str, diagnostics: list[str] | None = None) -> str:
    provider, model, key = _provider_args(args)
    base_url = getattr(args, "base_url", None)
    return generate_yaml(
        provider=provider,
        model=model,
        api_key=key,
        prompt=args.problem,
        history=history,
        current_yaml=current,
        base_url=base_url,
        diagnostics=diagnostics,
    )


def _extract_diagnostics(versions: list[dict[str, Any]]) -> list[str]:
    if not versions:
        return []
    last = versions[-1]
    diags: list[str] = []
    if last.get("error"):
        diags.append(f"Validation error: {last['error']}")
    cert = last.get("formal_certificate")
    if isinstance(cert, dict):
        for cex in cert.get("counterexamples", []):
            if isinstance(cex, dict) and cex.get("message"):
                diags.append(f"[{cex.get('obligation_id')}] {cex.get('message')}")
    return diags


def _chat(args) -> int:
    harness = AgentHarnessSession()
    spec_approval = None
    construction_plan = None
    construction_approval = None
    candidate = None
    verification = None
    formal_cert = None

    if args.session:
        path = ARTIFACT_ROOT / "agent_sessions" / args.session / "session.json"
        data = load_chat(path)
        session_id, messages, versions = data["session_id"], data.get("messages", []), data.get("versions", [])
        current = versions[-1]["yaml"] if versions else ""
        if current:
            try:
                candidate, verification, formal_cert = _check(current)
            except AMCAError:
                pass
        print(f"Sesi {session_id} dimuat; YAML versi {len(versions)}.")
    else:
        session_id, messages, versions, current = str(uuid.uuid4()), [], [], ""
        if args.example:
            current = _example(args.example).read_text(encoding="utf-8")
            print(f"Contoh dimuat: {args.example}")
        if not args.problem:
            print("Mesin/agent apakah yang Anda ingin buat?")
            args.problem = input("Problem statement: ").strip()
        if not args.problem:
            raise ValueError("Problem statement tidak boleh kosong.")
        intent_res = classify_intent(args.problem)
        if not intent_res.accepted:
            raise ValueError(intent_res.reason)
        messages.append({"role": "user", "content": args.problem})
        current = _generate(args, messages[:-1], current)
        messages.append({"role": "assistant", "content": "YAML kandidat dibuat."})
        versions.append({"yaml": current})
        candidate, verification, formal_cert, error = _record(session_id, messages, versions, "agent")
        print(
            f"Validasi: {verification.status if verification else 'rejected'}"
            + (f" | Formal: {formal_cert.overall_status}" if formal_cert else "")
            + (f" — {error}" if error else "")
        )
        _yaml(current)

    print(
        "Perintah sesi: revisi <permintaan>, show, load <yaml>, versions, restore <nomor>, "
        "validate, proof, hardware, approve-spec, plan, approve-construction, construct, graph [FILE.dot], run <input.json>, quit"
    )
    while True:
        try:
            line = input("amca> ").strip()
        except EOFError:
            line = "quit"
        if line in {"quit", "exit", "q"}:
            save_chat(session_id, messages, versions, metadata=harness.audit_metadata())
            print(f"Sesi disimpan: artifacts/agent_sessions/{session_id}/session.json")
            return 0
        if line == "show":
            print(current or "(belum ada YAML)")
        elif line == "versions":
            for index, version in enumerate(versions, 1):
                print(
                    f"v{index}: {version.get('source', 'unknown')} · "
                    f"{version.get('validation_status', 'unchecked')} · "
                    f"formal={version.get('formal_status', 'UNCHECKED')}"
                    + (f" · {version['error']}" if version.get("error") else "")
                )
        elif line.startswith("restore "):
            try:
                index = int(line.split(maxsplit=1)[1])
                if not 1 <= index <= len(versions):
                    raise ValueError("Nomor versi tidak tersedia.")
                current = versions[index - 1]["yaml"]
                versions.append({"yaml": current})
                candidate, verification, formal_cert, error = _record(session_id, messages, versions, "restore")
                spec_approval = None
                construction_approval = None
                print(
                    f"Versi v{index} dipulihkan sebagai versi baru. Validasi: {verification.status if verification else 'rejected'}"
                    + (f" — {error}" if error else "")
                )
            except (ValueError, IndexError) as exc:
                print(f"Tidak dapat memulihkan versi: {exc}", file=sys.stderr)
        elif line.startswith("load "):
            try:
                current = Path(line.split(maxsplit=1)[1]).read_text(encoding="utf-8")
                versions.append({"yaml": current})
                candidate, verification, formal_cert, error = _record(session_id, messages, versions, "manual_edit")
                spec_approval = None
                construction_approval = None
                print(
                    f"YAML dimuat sebagai versi v{len(versions)}. Validasi: {verification.status if verification else 'rejected'}"
                    + (f" — {error}" if error else "")
                )
            except (OSError, AMCAError) as exc:
                print(f"YAML tidak dapat dimuat: {getattr(exc, 'message', str(exc))}", file=sys.stderr)
        elif line == "validate":
            try:
                candidate, verification, formal_cert = _check(current)
                print(json.dumps(verification.as_dict(), ensure_ascii=False, indent=2))
            except AMCAError as exc:
                candidate, verification, formal_cert = None, None, None
                print(f"REJECTED: {getattr(exc, 'message', str(exc))}", file=sys.stderr)
        elif line == "proof":
            try:
                candidate, verification, formal_cert = _check(current)
                print(json.dumps(formal_cert.as_dict(), ensure_ascii=False, indent=2))
            except AMCAError as exc:
                print(f"Formal verification gagal: {getattr(exc, 'message', str(exc))}", file=sys.stderr)
        elif line.startswith("hardware"):
            parts = line.split(maxsplit=1)
            model_id = parts[1].strip() if len(parts) > 1 else next(iter(CURATED_LOCAL_MODELS))
            report = evaluate_local_model_eligibility(model_id)
            print(json.dumps(report.as_dict(), ensure_ascii=False, indent=2))
        elif line.startswith("revisi ") or line.startswith("revise "):
            prompt = line.split(" ", 1)[1].strip()
            if not prompt:
                print("Isi permintaan revisi setelah perintah revisi.", file=sys.stderr)
                continue
            messages.append({"role": "user", "content": prompt})
            args.problem = prompt
            diags = _extract_diagnostics(versions)
            try:
                try:
                    current = _generate(args, messages[:-1], current, diagnostics=diags)
                except TypeError:
                    # Fallback if _generate is mocked with a 3-arg signature in legacy unit tests
                    current = _generate(args, messages[:-1], current)
                messages.append({"role": "assistant", "content": f"YAML versi {len(versions)+1} dibuat."})
                versions.append({"yaml": current})
                candidate, verification, formal_cert, error = _record(session_id, messages, versions, "revision")
                spec_approval = None
                construction_approval = None
                print(
                    f"Validasi: {verification.status if verification else 'rejected'}"
                    + (f" — {error}" if error else "")
                )
                _yaml(current)
            except ProviderError as exc:
                messages.pop()
                print(str(exc), file=sys.stderr)
        elif line == "approve-spec":
            try:
                candidate, verification, formal_cert = _check(current)
                print(
                    f"Kandidat: {candidate.candidate_sha256} | Formal: {formal_cert.overall_status}. "
                    "Ketik APPROVE_SPEC untuk menyetujui spesifikasi:"
                )
                token = input("Persetujuan Spesifikasi: ").strip()
                spec_approval = record_spec_approval(
                    session_id=session_id,
                    revision=len(versions),
                    candidate=candidate,
                    verification=verification,
                    formal_certificate=formal_cert,
                    confirmation_token=token,
                )
                print(f"Spesifikasi disetujui: {spec_approval.approval_id}")
            except Exception as exc:
                print(f"Persetujuan spesifikasi ditolak: {exc}", file=sys.stderr)
        elif line.startswith("plan"):
            parts = line.split(maxsplit=1)
            profile = parts[1].strip() if len(parts) > 1 else "minimize_cost"
            try:
                candidate, verification, formal_cert = _check(current)
                construction_plan = generate_construction_plan(
                    candidate,
                    optimization_profile=profile,
                    harness=harness,
                )
                print(json.dumps(construction_plan.as_dict(), ensure_ascii=False, indent=2))
                for sw in construction_plan.subworkers:
                    harness.request_subworker_hitl(sw)
                    print(f"[HITL Subworker] Izinkan subworker {sw.subworker_id} ({sw.role})? Ketik APPROVE atau DECLINE:")
                    ans = input("Subworker HITL: ").strip().upper()
                    if ans == "APPROVE":
                        harness.approve_subworker_hitl(
                            sw.subworker_id,
                            provider_type=sw.recommended_provider,
                            model_id=sw.recommended_model,
                        )
                    else:
                        harness.decline_subworker_hitl(sw.subworker_id)
            except Exception as exc:
                print(f"Gagal menyusun rencana konstruksi: {exc}", file=sys.stderr)
        elif line == "approve-construction":
            try:
                if spec_approval is None:
                    raise PermissionError("Jalankan approve-spec terlebih dahulu.")
                candidate, verification, formal_cert = _check(current)
                if construction_plan is None:
                    construction_plan = generate_construction_plan(candidate, harness=harness)
                print("Ketik APPROVE_CONSTRUCTION untuk mengizinkan pembuatan kode & paket ZIP:")
                token = input("Persetujuan Konstruksi: ").strip()
                construction_approval = record_construction_approval(
                    spec_approval=spec_approval,
                    candidate=candidate,
                    formal_certificate=formal_cert,
                    confirmation_token=token,
                    worker_policy=construction_plan.worker_policy,
                    use_subagents=construction_plan.use_subagents,
                )
                print(f"Konstruksi disetujui: {construction_approval.approval_id}")
            except Exception as exc:
                print(f"Persetujuan konstruksi ditolak: {exc}", file=sys.stderr)
        elif line == "construct":
            try:
                if spec_approval is None or construction_approval is None or construction_plan is None:
                    raise PermissionError("Wajib menyelesaikan approve-spec, plan, dan approve-construction terlebih dahulu.")
                candidate, verification, formal_cert = _check(current)
                layout = build_constructed_project(
                    candidate=candidate,
                    yaml_text=current,
                    certificate=formal_cert,
                    spec_approval=spec_approval,
                    plan=construction_plan,
                    construction_approval=construction_approval,
                    revision=len(versions),
                    output_root=ARTIFACT_ROOT / "constructed_projects",
                )
                pkg = verify_and_package_project(
                    layout=layout,
                    candidate=candidate,
                    certificate=formal_cert,
                    spec_approval=spec_approval,
                    plan=construction_plan,
                    construction_approval=construction_approval,
                    harness=harness,
                )
                print(json.dumps(pkg.as_dict(), ensure_ascii=False, indent=2))
            except Exception as exc:
                print(f"Konstruksi proyek gagal: {exc}", file=sys.stderr)
        elif line.startswith("graph"):
            parts = line.split(maxsplit=1)
            target = Path(parts[1]) if len(parts) > 1 else ARTIFACT_ROOT / "machine-dag.dot"
            try:
                candidate, verification, _ = _check(current)
                if verification.status != "verified":
                    raise ValueError("Graf hanya dibuat untuk spesifikasi berstatus verified.")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(to_dot(candidate) + "\n", encoding="utf-8")
                print(f"DAG tersimpan: {target}")
            except (AMCAError, ValueError, OSError) as exc:
                print(f"Tidak dapat membuat DAG: {getattr(exc, 'message', str(exc))}", file=sys.stderr)
        elif line.startswith("run "):
            input_path = Path(line.split(maxsplit=1)[1])
            try:
                candidate, verification, formal_cert = _check(current)
                if verification.status != "verified":
                    raise ValueError("Spesifikasi harus lolos verifikasi sebelum runtime.")
                raw = json.loads(input_path.read_text(encoding="utf-8"))
                if type(raw) is not dict:
                    raise ValueError("Input runtime harus berupa objek JSON.")
                print("Mesin siap dieksekusi. Ketik RUN untuk menyetujui; selain itu dibatalkan.")
                if input("Persetujuan: ").strip() != "RUN":
                    print("Eksekusi dibatalkan.")
                    continue
                execution = run(candidate, verification, raw)
                folder = save_run(
                    current,
                    verification.as_dict(),
                    candidate.as_dict(),
                    to_dot(candidate),
                    execution,
                    execution["run_status"],
                    formal_certificate=formal_cert.as_dict() if formal_cert else None,
                )
                print(json.dumps(execution, ensure_ascii=False, indent=2))
                print(f"Artefak: {folder}")
            except (AMCAError, OSError, ValueError, json.JSONDecodeError) as exc:
                print(f"Eksekusi ditolak/gagal: {getattr(exc, 'message', str(exc))}", file=sys.stderr)
        elif line:
            print(
                "Perintah tidak dikenal. Ketik show, load, versions, restore, validate, proof, hardware, "
                "revisi, approve-spec, plan, approve-construction, construct, graph, run, atau quit."
            )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="amca-agent",
        description="Author YAML, run 3-stage formal verification, inspect DAGs, and construct bounded AMCA projects locally.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("examples", help="list example YAML specifications")
    example = sub.add_parser("example", help="copy an example YAML")
    example.add_argument("name")
    example.add_argument("--output")
    validate = sub.add_parser("validate", help="validate and verify YAML without running")
    validate.add_argument("spec")
    validate.add_argument("--output")
    formal_cmd = sub.add_parser("formal-verify", help="run Stage 1/2 formal mathematical verification on YAML")
    formal_cmd.add_argument("spec")
    formal_cmd.add_argument("--previous", help="optional previous revision YAML for Stage 2 evolution proof")
    formal_cmd.add_argument("--output")
    hw_cmd = sub.add_parser("hardware-check", help="inspect host laptop RAM/disk/CPU/GPU and local model eligibility")
    hw_cmd.add_argument("--model", default="qwen2.5-coder-1.5b-instruct-q4_k_m.gguf")
    hw_cmd.add_argument("--output")
    disc_cmd = sub.add_parser("discover-models", help="discover models/Combos from 9Router, Ollama, LM Studio, or OpenCode")
    disc_cmd.add_argument("--provider", required=True)
    disc_cmd.add_argument("--base-url")
    disc_cmd.add_argument("--api-key", default="")
    disc_cmd.add_argument("--output")
    combo_cmd = sub.add_parser("combo-config", help="create and validate a multi-tier AMCA Combo fallback chain")
    combo_cmd.add_argument("--name", required=True)
    combo_cmd.add_argument("--tiers", required=True, help="comma-separated provider:model pairs, e.g. gemini:gemini-2.5-pro,nine_router:free-combo,offline_deterministic:builtin-v1")
    combo_cmd.add_argument("--output")
    construct_cmd = sub.add_parser("construct", help="verify, approve, build, run Stage 3 AST proof, test, and package handover ZIP")
    construct_cmd.add_argument("spec")
    construct_cmd.add_argument("--profile", default="minimize_cost", choices=["minimize_cost", "balanced", "maximize_capability"])
    construct_cmd.add_argument("--revision", type=int, default=1)
    construct_cmd.add_argument("--approve-spec", action="store_true", help="confirm Stage 1 spec approval (APPROVE_SPEC)")
    construct_cmd.add_argument("--approve-construction", action="store_true", help="confirm Stage 2 construction approval (APPROVE_CONSTRUCTION)")
    construct_cmd.add_argument("--output-dir")
    construct_cmd.add_argument("--output")
    graph = sub.add_parser("graph", help="write Graphviz DOT for a verified YAML")
    graph.add_argument("spec")
    graph.add_argument("--output", required=True)
    execute = sub.add_parser("run", help="verify and run YAML with JSON input")
    execute.add_argument("spec")
    execute.add_argument("--inputs", required=True)
    execute.add_argument("--output")
    sessions = sub.add_parser("sessions", help="list saved authoring sessions")
    artifacts = sub.add_parser("artifacts", help="list saved run artifact folders")
    artifacts.add_argument("--show", help="show files in a run folder by run ID")
    show = sub.add_parser("show", help="print a saved artifact file")
    show.add_argument("path")
    chat = sub.add_parser("chat", help="interactive author/revise/validate/formal-verify/construct workflow")
    chat.add_argument("--problem")
    chat.add_argument("--example")
    chat.add_argument("--session")
    chat.add_argument("--provider", choices=list(DEFAULT_MODELS.keys()), default="Gemini")
    chat.add_argument("--model")
    chat.add_argument("--base-url")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "examples":
            for path in _examples():
                print(path.name)
        elif args.command == "example":
            _yaml(_example(args.name).read_text(encoding="utf-8"), args.output)
        elif args.command == "validate":
            candidate, verification, formal_cert = _check(Path(args.spec).read_text(encoding="utf-8"))
            _json(
                {
                    "status": verification.status,
                    "formal_status": formal_cert.overall_status,
                    "machine_id": candidate.machine_id,
                    "candidate": candidate.as_dict(),
                    "verification": verification.as_dict(),
                    "formal_certificate": formal_cert.as_dict(),
                },
                args.output,
            )
            return 0 if verification.status == "verified" else 1
        elif args.command == "formal-verify":
            spec_text = Path(args.spec).read_text(encoding="utf-8")
            prev_text = Path(args.previous).read_text(encoding="utf-8") if args.previous else None
            cert = verify_specification_formal(
                spec_text.encode("utf-8"),
                previous_spec_or_yaml=prev_text.encode("utf-8") if prev_text else None,
            )
            _json(cert.as_dict(), args.output)
            return 0 if cert.overall_status == "PROVED" else 1
        elif args.command == "hardware-check":
            hw = inspect_host_hardware()
            elig = evaluate_local_model_eligibility(args.model, hardware=hw)
            _json(elig.as_dict(), args.output)
            return 0 if elig.eligible else 1
        elif args.command == "discover-models":
            models = discover_provider_models(
                args.provider,
                base_url=args.base_url,
                api_key=args.api_key or os.environ.get("AMCA_API_KEY", ""),
            )
            _json({"provider": args.provider, "models": models}, args.output)
            return 0
        elif args.command == "combo-config":
            harness = AgentHarnessSession()
            tiers_raw = []
            for item in args.tiers.split(","):
                item = item.strip()
                if not item or ":" not in item:
                    raise ValueError(f"Format tier tidak valid: {item!r}. Gunakan provider:model")
                prov, mod = item.split(":", 1)
                tiers_raw.append({"provider_type": prov.strip(), "model_id": mod.strip()})
            chain = harness.register_combo_chain(args.name, tiers_raw)
            _json(chain.as_dict(), args.output)
            return 0
        elif args.command == "construct":
            if not args.approve_spec or not args.approve_construction:
                raise ValueError(
                    "Konstruksi proyek membutuhkan persetujuan dua tahap eksplisit: "
                    "sertakan --approve-spec dan --approve-construction."
                )
            spec_text = Path(args.spec).read_text(encoding="utf-8")
            candidate, verification, formal_cert = _check(spec_text)
            session_id = str(uuid.uuid4())
            harness = AgentHarnessSession(session_id=session_id)
            spec_app = record_spec_approval(
                session_id=session_id,
                revision=args.revision,
                candidate=candidate,
                verification=verification,
                formal_certificate=formal_cert,
                confirmation_token="APPROVE_SPEC",
            )
            plan = generate_construction_plan(
                candidate,
                optimization_profile=args.profile,
                revision=args.revision,
                harness=harness,
            )
            const_app = record_construction_approval(
                spec_approval=spec_app,
                candidate=candidate,
                formal_certificate=formal_cert,
                confirmation_token="APPROVE_CONSTRUCTION",
                worker_policy=plan.worker_policy,
                use_subagents=plan.use_subagents,
            )
            out_root = Path(args.output_dir) if args.output_dir else (ARTIFACT_ROOT / "constructed_projects")
            layout = build_constructed_project(
                candidate=candidate,
                yaml_text=spec_text,
                certificate=formal_cert,
                spec_approval=spec_app,
                plan=plan,
                construction_approval=const_app,
                revision=args.revision,
                output_root=out_root,
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
            _json(pkg.as_dict(), args.output)
            return 0
        elif args.command == "graph":
            candidate, verification, _ = _check(Path(args.spec).read_text(encoding="utf-8"))
            if verification.status != "verified":
                raise ValueError("Spesifikasi tidak berstatus verified.")
            Path(args.output).write_text(to_dot(candidate) + "\n", encoding="utf-8")
            print(args.output)
        elif args.command == "run":
            spec_text = Path(args.spec).read_text(encoding="utf-8")
            candidate, verification, formal_cert = _check(spec_text)
            if verification.status != "verified":
                raise ValueError("Spesifikasi tidak berstatus verified.")
            inputs = json.loads(Path(args.inputs).read_text(encoding="utf-8"))
            if type(inputs) is not dict:
                raise ValueError("Input runtime harus berupa objek JSON.")
            record = run(candidate, verification, inputs)
            _json(record, args.output)
            folder = save_run(
                spec_text,
                verification.as_dict(),
                candidate.as_dict(),
                to_dot(candidate),
                record,
                record["run_status"],
                formal_certificate=formal_cert.as_dict(),
            )
            print(f"Artefak: {folder}", file=sys.stderr)
            return 0 if record["run_status"] == "succeeded" else 1
        elif args.command == "sessions":
            for path in list_sessions():
                print(f"{path.parent.name}\t{path}")
        elif args.command == "artifacts":
            root = ARTIFACT_ROOT / "runs"
            if args.show:
                target = root / args.show
                for file in sorted(target.glob("*")):
                    if file.is_file():
                        print(file)
            elif root.exists():
                for folder in sorted((p for p in root.iterdir() if p.is_dir()), reverse=True):
                    print(folder.name)
        elif args.command == "show":
            target = Path(args.path)
            if target.suffix == ".json":
                print(json.dumps(json.loads(target.read_text(encoding="utf-8")), ensure_ascii=False, indent=2))
            else:
                print(target.read_text(encoding="utf-8"))
        elif args.command == "chat":
            return _chat(args)
    except (AMCAError, ProviderError, PermissionError, RuntimeError, OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        print(f"amca-agent: {getattr(exc, 'message', str(exc))}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
