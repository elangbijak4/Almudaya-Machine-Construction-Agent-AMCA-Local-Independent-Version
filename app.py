"""AMCA Local Independent Version Web UI: Specialized Agent Harness, 3-Stage Formal Verifier, and Project Constructor."""
from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path
from typing import Any

import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from amca.errors import AMCAError
from amca.registry import component_ids
from amca.runtime import run
from amca.verifier import verify_candidate
from amca_agent.approvals import record_construction_approval, record_spec_approval
from amca_agent.artifacts import ARTIFACT_ROOT, list_sessions, load_chat, save_chat, save_run
from amca_agent.builder import build_constructed_project
from amca_agent.formal_verifier import verify_formal_spec
from amca_agent.graph import to_dot
from amca_agent.hardware import (
    LOCAL_MODEL_CATALOG,
    evaluate_local_model_eligibility,
    inspect_host_hardware,
    register_approved_local_model,
)
from amca_agent.harness import AgentHarnessSession
from amca_agent.intent import OPENING_GREETING, classify_intent
from amca_agent.packager import verify_and_package_project
from amca_agent.planner import generate_construction_plan
from amca_agent.provider import (
    DEFAULT_MODELS,
    PROVIDER_DEFAULT_URLS,
    ProviderError,
    discover_provider_models,
)
from amca_agent.system_spec import load_any_spec_to_candidate


st.set_page_config(page_title="AMCA Machine & Agent Constructor", page_icon="🧩", layout="wide")
st.title("AMCA · Specialized Agent Harness & Formal Machine Constructor")
st.caption(
    f"**{OPENING_GREETING}** — Susun spesifikasi mesin/agent (YAML v1.0 atau MachineSystem v1alpha1), "
    "buktikan secara matematis dengan 3-Stage Formal Verification, lalu jalankan atau konstruksi paket proyek Python mandiri (.zip)."
)


PROVIDER_OPTIONS = [
    "Gemini",
    "xAI (Grok)",
    "OpenAI",
    "Anthropic",
    "9Router",
    "Ollama",
    "LM Studio",
    "OpenCode",
    "Custom OpenAI-Compatible",
    "Local Model",
    "AMCA Combo",
    "Offline Deterministic",
]


def _init() -> None:
    st.session_state.setdefault("session_id", str(uuid.uuid4()))
    st.session_state.setdefault("harness", AgentHarnessSession(session_id=st.session_state["session_id"]))
    st.session_state.setdefault("messages", [])
    st.session_state.setdefault("versions", [])
    st.session_state.setdefault("problem", "")
    st.session_state.setdefault("machine_yaml", "")
    st.session_state.setdefault("verification", None)
    st.session_state.setdefault("formal_certificate", None)
    st.session_state.setdefault("candidate", None)
    st.session_state.setdefault("dot", None)
    st.session_state.setdefault("validation_error", None)
    st.session_state.setdefault("last_artifact", None)
    st.session_state.setdefault("spec_approval", None)
    st.session_state.setdefault("construction_plan", None)
    st.session_state.setdefault("construction_approval", None)
    st.session_state.setdefault("last_package_result", None)
    st.session_state.setdefault("discovered_models", [])


def _validate(yaml_text: str, previous_yaml: str | None = None) -> tuple[Any | None, Any | None, Any | None, str | None]:
    try:
        candidate, _ = load_any_spec_to_candidate(yaml_text.encode("utf-8"))
        verification = verify_candidate(candidate)
        formal_cert = verify_formal_spec(
            yaml_text.encode("utf-8"),
            previous_spec_or_yaml=previous_yaml.encode("utf-8") if previous_yaml else None,
        )
        return candidate, verification, formal_cert, None
    except (AMCAError, UnicodeEncodeError) as exc:
        return None, None, None, getattr(exc, "message", str(exc))


def _record_version(source: str) -> None:
    text = st.session_state.machine_yaml
    prev_yaml = st.session_state.versions[-1]["yaml"] if st.session_state.versions else None
    candidate, verification, formal_cert, error = _validate(text, previous_yaml=prev_yaml)
    st.session_state.candidate = candidate
    st.session_state.verification = verification
    st.session_state.formal_certificate = formal_cert
    st.session_state.validation_error = error
    st.session_state.spec_approval = None
    st.session_state.construction_approval = None
    st.session_state.dot = to_dot(candidate) if candidate is not None and verification.status == "verified" else None
    formal_dict = formal_cert.as_dict() if formal_cert else None
    st.session_state.versions.append(
        {
            "yaml": text,
            "source": source,
            "validation_status": verification.status if verification else "rejected",
            "formal_status": formal_cert.overall_status if formal_cert else "REFUTED",
            "formal_certificate": formal_dict,
            "error": error
            or (
                "; ".join(r.message for r in verification.reasons)
                if verification and verification.status != "verified"
                else None
            ),
        }
    )
    record = (
        verification.as_dict()
        if verification
        else {
            "report_version": "1.0",
            "status": "rejected",
            "candidate_sha256": None,
            "profile_id": "not_constructed",
            "checks": [],
            "reasons": [{"message": error}],
            "assumptions": [],
        }
    )
    folder = save_run(
        text,
        record,
        candidate.as_dict() if candidate else None,
        st.session_state.dot,
        None,
        verification.status if verification else "rejected",
        formal_certificate=formal_dict,
    )
    st.session_state.last_artifact = str(folder)
    save_chat(
        st.session_state.session_id,
        st.session_state.messages,
        st.session_state.versions,
        metadata=st.session_state.harness.audit_metadata(),
    )


_init()
harness: AgentHarnessSession = st.session_state.harness

with st.sidebar:
    st.header("Pengaturan Agent Harness")
    provider = st.selectbox("Provider model", PROVIDER_OPTIONS)
    default_model_val = DEFAULT_MODELS.get(provider, "gemini-3.8-flash")
    base_url_default = PROVIDER_DEFAULT_URLS.get(provider, "")
    base_url: str | None = None

    if provider in {"9Router", "Ollama", "LM Studio", "OpenCode", "Custom OpenAI-Compatible"}:
        base_url = st.text_input("Endpoint Base URL", value=base_url_default, key=f"url_{provider}")
        if st.button("Pindai Model / Combo Lokal"):
            try:
                st.session_state.discovered_models = discover_provider_models(provider, base_url=base_url)
                st.success(f"Ditemukan {len(st.session_state.discovered_models)} model/Combo.")
            except ProviderError as exc:
                st.warning(str(exc))
        if st.session_state.discovered_models:
            st.caption("Model terdeteksi: " + ", ".join(st.session_state.discovered_models[:8]))

    if provider == "Local Model":
        model = st.selectbox("Katalog Model Lokal Terkurasi", list(LOCAL_MODEL_CATALOG.keys()))
        hw_snap = inspect_host_hardware()
        elig = evaluate_local_model_eligibility(model, hardware=hw_snap)
        st.caption(
            f"Spek Laptop: RAM Tersedia `{hw_snap.ram_available_mb} MB` / Total `{hw_snap.ram_total_mb} MB` · "
            f"Disk Bebas `{hw_snap.disk_free_mb} MB` · CPU `{hw_snap.cpu_logical_cores}` core"
        )
        if elig.eligible:
            st.success(f"Hardware Gate: {elig.decision}")
            if st.button("Daftarkan & Siapkan Model Lokal"):
                _, manifest_path = register_approved_local_model(model, user_approved=True, hardware=hw_snap)
                st.info(f"Manifest model lokal siap: `{manifest_path.name}`")
        else:
            st.error(f"Hardware Gate: {elig.decision} — {'; '.join(elig.reasons)}")
        api_key = ""
    elif provider == "AMCA Combo":
        model = st.text_input("Nama Rantai Combo", value="resilient-local-combo", key="combo_name")
        tier1_spec = st.text_input("Tier 1 (provider:model)", value="9Router:free-combo", key="combo_t1")
        tier2_spec = st.text_input("Tier 2 (provider:model)", value="Ollama:qwen2.5-coder:7b", key="combo_t2")
        tier3_spec = st.text_input(
            "Tier 3 Fallback Akhir",
            value="Offline Deterministic:builtin-deterministic-v1",
            key="combo_t3",
        )
        api_key = st.text_input("API key Tier 1 (opsional, di memori sesi)", type="password")
        tiers_list = []
        for idx, raw_t in enumerate((tier1_spec, tier2_spec, tier3_spec), 1):
            if ":" in raw_t:
                p_name, m_name = raw_t.split(":", 1)
                tiers_list.append(
                    {
                        "provider_type": p_name.strip(),
                        "model_id": m_name.strip(),
                        "api_key": api_key if idx == 1 else "",
                    }
                )
        if tiers_list:
            harness.register_combo_chain(model, tiers_list, set_as_primary=True)
    else:
        model = st.text_input("Model", value=default_model_val, key=f"model_{provider}")
        api_key = st.text_input("API key (hanya di memori sesi)", type="password")

    if provider not in {"AMCA Combo", "Local Model"}:
        harness.configure_primary_agent(
            provider_type=provider,
            model_id=model,
            api_key=api_key,
            base_url=base_url,
        )

    st.caption("Key tidak ditulis ke artefak. Validasi struktural, verifikasi formal 3-tahap, dan runtime tetap lokal.")
    st.divider()
    st.subheader("Sesi tersimpan di komputer ini")
    sessions = list_sessions()
    if sessions:
        labels = [f"{p.parent.name} · {p.parent}" for p in sessions]
        chosen = st.selectbox(
            "Muat sesi",
            [None, *range(len(sessions))],
            format_func=lambda x: "Sesi saat ini" if x is None else labels[x],
        )
        if st.button("Buka sesi terpilih", disabled=chosen is None):
            data = load_chat(sessions[chosen])
            st.session_state.session_id = data["session_id"]
            st.session_state.messages = data.get("messages", [])
            st.session_state.versions = data.get("versions", [])
            if st.session_state.versions:
                st.session_state.machine_yaml = st.session_state.versions[-1]["yaml"]
                candidate, verification, formal_cert, error = _validate(st.session_state.machine_yaml)
                st.session_state.candidate = candidate
                st.session_state.verification = verification
                st.session_state.formal_certificate = formal_cert
                st.session_state.validation_error = error
                st.session_state.dot = to_dot(candidate) if candidate and verification.status == "verified" else None
            st.rerun()
    st.caption(f"Session ID: `{st.session_state.session_id[:8]}`")

example_files = sorted((ROOT / "examples").glob("*.yaml"))
example_map = {f"{p.stem} — {p.name}": p for p in example_files}
left, right = st.columns([1, 1])
with left:
    st.subheader("1 · Problem statement")
    selected_example = st.selectbox("Contoh YAML sebagai titik awal", ["(tanpa contoh)", *example_map])
    if st.button("Muat contoh ke editor"):
        if selected_example == "(tanpa contoh)":
            st.session_state.machine_yaml = ""
        else:
            st.session_state.machine_yaml = example_map[selected_example].read_text(encoding="utf-8")
        st.session_state.verification = None
        st.session_state.formal_certificate = None
        st.session_state.candidate = None
        st.session_state.dot = None
        st.rerun()
    st.text_area(
        "Jelaskan mesin yang ingin dibuat",
        key="problem",
        height=130,
        placeholder="Contoh: Buat pipeline untuk memeriksa teks, menghitung karakter dan kata, lalu merangkum hasilnya.",
    )
    if st.button("Buat YAML dengan agent", type="primary", disabled=not st.session_state.problem.strip()):
        request = st.session_state.problem.strip()
        intent_check = classify_intent(request)
        if not intent_check.allowed:
            st.warning(intent_check.boundary_message or intent_check.reason)
        else:
            st.session_state.messages.append({"role": "user", "content": request})
            try:
                current = st.session_state.machine_yaml
                if not current and selected_example != "(tanpa contoh)":
                    current = example_map[selected_example].read_text(encoding="utf-8")
                result = harness.execute_yaml_generation(
                    request,
                    history=st.session_state.messages[:-1],
                    current_yaml=current,
                )
                st.session_state.machine_yaml = result
                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "content": f"YAML versi {len(st.session_state.versions) + 1} dibuat oleh {provider}/{model}.",
                    }
                )
                _record_version("agent")
                st.rerun()
            except (ProviderError, PermissionError) as exc:
                st.error(str(exc))
                st.session_state.messages.pop()
    st.subheader("2 · Revisi lewat chat")
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])
    revision = st.chat_input("Minta perubahan pada YAML…", key="revision_input", submit_mode="disable")
    if revision:
        request = revision.strip()
        st.session_state.messages.append({"role": "user", "content": request})
        diags: list[str] = []
        if st.session_state.validation_error:
            diags.append(st.session_state.validation_error)
        if st.session_state.formal_certificate and st.session_state.formal_certificate.counterexamples:
            diags.extend(c.message for c in st.session_state.formal_certificate.counterexamples)
        try:
            with st.status("Meminta revisi dan memvalidasi YAML…", expanded=False):
                result = harness.execute_yaml_generation(
                    request,
                    history=st.session_state.messages[:-1],
                    current_yaml=st.session_state.machine_yaml,
                    diagnostics=diags,
                )
                st.session_state.machine_yaml = result
                candidate, verification, formal_cert, error = _validate(result)
                state = verification.status if verification else "rejected"
                f_state = formal_cert.overall_status if formal_cert else "REFUTED"
                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "content": (
                            f"YAML versi {len(st.session_state.versions) + 1} dibuat oleh {provider}/{model}. "
                            f"Hasil pemeriksaan: {state} (Formal: {f_state})."
                        ),
                    }
                )
                _record_version("revision")
            st.rerun()
        except (ProviderError, PermissionError) as exc:
            st.error(str(exc))
            st.session_state.messages.pop()

with right:
    st.subheader("3 · Tinjau, validasi struktural, & verifikasi formal")
    st.caption("YAML hasil agent adalah kandidat. Ia diverifikasi secara struktural dan matematis sebelum dijalankan.")
    st.text_area("Spesifikasi mesin YAML", key="machine_yaml", height=340)
    if st.button("Validasi YAML saat ini"):
        _record_version("manual_edit")
    if st.session_state.verification is not None:
        status = st.session_state.verification.status
        (st.success if status == "verified" else st.error)(f"Validasi AMCA: {status.upper()}")
    elif st.session_state.validation_error:
        st.error(st.session_state.validation_error)
    if st.session_state.formal_certificate is not None:
        f_cert = st.session_state.formal_certificate
        if f_cert.overall_status == "PROVED":
            st.success(f"Formal Verification (Stage 1/2): PROVED · SHA-256 `{f_cert.certificate_sha256[:12]}…`")
        else:
            st.error(f"Formal Verification (Stage 1/2): REFUTED ({len(f_cert.counterexamples)} counterexample)")
        with st.expander("Sertifikat Pembuktian Formal (`formal-proof-certificate.json`)"):
            st.json(f_cert.as_dict())
    if st.session_state.validation_error:
        st.code(st.session_state.validation_error)
    elif st.session_state.verification and st.session_state.verification.reasons:
        for reason in st.session_state.verification.reasons:
            st.warning(f"{reason.code}: {reason.message}")
    if st.session_state.versions:
        labels = [
            f"v{i} · {v['source']} · {v['validation_status']} · formal:{v.get('formal_status', '-')}"
            for i, v in enumerate(st.session_state.versions, 1)
        ]
        version_index = st.selectbox(
            "Versi YAML",
            list(range(len(labels))),
            format_func=lambda i: labels[i],
            key="version_index",
        )
        if st.button("Pulihkan versi terpilih"):
            st.session_state.machine_yaml = st.session_state.versions[version_index]["yaml"]
            st.session_state.verification = None
            st.session_state.formal_certificate = None
            st.rerun()

if st.session_state.candidate is not None and st.session_state.verification and st.session_state.verification.status == "verified":
    st.subheader("4 · Graf DAG mesin")
    st.graphviz_chart(st.session_state.dot, width="stretch")
    st.download_button("Unduh graf DAG (.dot)", st.session_state.dot, file_name="machine-dag.dot", mime="text/vnd.graphviz")
    with st.expander("Candidate graph JSON"):
        st.json(st.session_state.candidate.as_dict())

st.subheader("5 · Eksekusi yang disetujui user")
if st.session_state.verification is None or st.session_state.verification.status != "verified":
    st.info("Validasi YAML hingga status `verified` untuk membuka eksekusi.")
else:
    source_nodes = [n for n in st.session_state.candidate.nodes if n.component == "input_source"]
    input_key = source_nodes[0].config["input_key"] if source_nodes else "text"
    input_json = st.text_area(
        "Input runtime (JSON)",
        value=json.dumps({input_key: "AMCA builds a graph."}, ensure_ascii=False),
        height=85,
    )
    approved = st.checkbox("Saya menyetujui eksekusi mesin ini")
    if st.button("Jalankan mesin", type="primary", disabled=not approved):
        try:
            inputs = json.loads(input_json)
            if type(inputs) is not dict:
                raise ValueError("Input runtime harus berupa objek JSON.")
            record = run(st.session_state.candidate, st.session_state.verification, inputs)
            folder = save_run(
                st.session_state.machine_yaml,
                st.session_state.verification.as_dict(),
                st.session_state.candidate.as_dict(),
                st.session_state.dot,
                record,
                record["run_status"],
                formal_certificate=st.session_state.formal_certificate.as_dict()
                if st.session_state.formal_certificate
                else None,
            )
            st.session_state.last_artifact = str(folder)
            st.session_state.last_execution = record
            st.rerun()
        except (AMCAError, ValueError, json.JSONDecodeError) as exc:
            st.error(f"Input JSON tidak valid: {exc}")

if "last_execution" in st.session_state:
    st.subheader("Hasil execution record")
    st.json(st.session_state.last_execution)

st.subheader("6 · Konstruksi Proyek Python Mandiri & Paket Handover (.zip)")
if (
    st.session_state.candidate is not None
    and st.session_state.verification is not None
    and st.session_state.verification.status == "verified"
    and st.session_state.formal_certificate is not None
    and st.session_state.formal_certificate.overall_status == "PROVED"
):
    with st.expander("Persetujuan Dua Tahap (`APPROVE_SPEC` & `APPROVE_CONSTRUCTION`), Subworker HITL, dan Builder"):
        rev_num = max(len(st.session_state.versions), 1)
        if st.button("1. Kunci Persetujuan Spesifikasi (APPROVE_SPEC)"):
            st.session_state.spec_approval = record_spec_approval(
                session_id=st.session_state.session_id,
                revision=rev_num,
                candidate=st.session_state.candidate,
                verification=st.session_state.verification,
                formal_certificate=st.session_state.formal_certificate,
                confirmation_token="APPROVE_SPEC",
            )
            st.session_state.construction_plan = generate_construction_plan(
                st.session_state.candidate,
                optimization_profile="minimize_cost",
                revision=rev_num,
                harness=harness,
            )
        if st.session_state.spec_approval is not None:
            st.success(f"Stage 1 Spec Approval terkunci: `{st.session_state.spec_approval.approval_id}`")
            if st.session_state.construction_plan is not None:
                st.json(st.session_state.construction_plan.as_dict())
            if st.button("2. Setujui Konstruksi & Bangun Paket Handover ZIP (APPROVE_CONSTRUCTION)"):
                try:
                    c_app = record_construction_approval(
                        spec_approval=st.session_state.spec_approval,
                        candidate=st.session_state.candidate,
                        formal_certificate=st.session_state.formal_certificate,
                        confirmation_token="APPROVE_CONSTRUCTION",
                        worker_policy=st.session_state.construction_plan.worker_policy,
                        use_subagents=st.session_state.construction_plan.use_subagents,
                        projects_root=ARTIFACT_ROOT / "constructed_projects",
                    )
                    st.session_state.construction_approval = c_app
                    layout = build_constructed_project(
                        candidate=st.session_state.candidate,
                        yaml_text=st.session_state.machine_yaml,
                        certificate=st.session_state.formal_certificate,
                        spec_approval=st.session_state.spec_approval,
                        plan=st.session_state.construction_plan,
                        construction_approval=c_app,
                        revision=rev_num,
                        output_root=ARTIFACT_ROOT / "constructed_projects",
                    )
                    pkg_res = verify_and_package_project(
                        layout=layout,
                        candidate=st.session_state.candidate,
                        certificate=st.session_state.formal_certificate,
                        spec_approval=st.session_state.spec_approval,
                        plan=st.session_state.construction_plan,
                        construction_approval=c_app,
                        harness=harness,
                    )
                    st.session_state.last_package_result = pkg_res
                except Exception as exc:
                    st.error(f"Konstruksi gagal: {exc}")

        if st.session_state.last_package_result is not None:
            pkg = st.session_state.last_package_result
            st.success(
                f"Proyek mandiri berhasil dikonstruksi dan lulus Stage 3 AST Proof (`{pkg.refined_certificate.overall_status}`): `{pkg.zip_path.name}`"
            )
            st.download_button(
                f"Unduh {pkg.zip_path.name}",
                pkg.zip_path.read_bytes(),
                file_name=pkg.zip_path.name,
                mime="application/zip",
                key=f"dl-zip-{pkg.zip_path.name}",
            )
else:
    st.info("Selesaikan validasi struktural (`verified`) dan pembuktian formal Stage 1 (`PROVED`) untuk membuka konstruksi proyek mandiri.")

st.subheader("7 · Artefak tersimpan")
if st.session_state.last_artifact:
    folder = Path(st.session_state.last_artifact)
    st.caption(f"Folder artefak terakhir: `{folder}`")
    for path in sorted(folder.glob("*")):
        if path.is_file():
            mime = "application/json" if path.suffix == ".json" else "text/plain"
            st.download_button(
                f"Unduh {path.name}",
                path.read_bytes(),
                file_name=path.name,
                mime=mime,
                key=f"dl-{path.name}-{folder.name}",
            )

run_root = ARTIFACT_ROOT / "runs"
if run_root.exists():
    runs = sorted((p for p in run_root.iterdir() if p.is_dir()), reverse=True)
    if runs:
        with st.expander("Jelajahi artefak siklus sebelumnya"):
            chosen_run = st.selectbox("Run tersimpan", runs, format_func=lambda p: p.name)
            for path in sorted(chosen_run.glob("*")):
                if path.is_file():
                    st.markdown(f"**{path.name}**")
                    if path.suffix == ".json":
                        try:
                            st.json(json.loads(path.read_text(encoding="utf-8")))
                        except json.JSONDecodeError:
                            st.warning("JSON artefak rusak.")
                    elif path.suffix in {".yaml", ".dot"}:
                        st.code(
                            path.read_text(encoding="utf-8"),
                            language="yaml" if path.suffix == ".yaml" else "dot",
                        )
                    st.download_button(
                        f"Unduh {path.name}",
                        path.read_bytes(),
                        file_name=path.name,
                        mime="application/json" if path.suffix == ".json" else "text/plain",
                        key=f"history-{chosen_run.name}-{path.name}",
                    )

st.caption(
    f"Komponen allowlist saat ini: {', '.join(component_ids())}. "
    "Eksekusi lokal, berurutan, dan hanya melalui runtime AMCA."
)
