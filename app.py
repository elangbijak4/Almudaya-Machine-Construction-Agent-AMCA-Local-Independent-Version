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
from amca_agent.component_binder import bind_component_from_python_source, bind_external_component_file
from amca_agent.component_synthesizer import (
    detect_unregistered_components_in_yaml,
    synthesize_and_bind_missing_components,
)
from amca_agent.custom_components import (
    OPERATION_TEMPLATES,
    draft_custom_component_from_description,
    format_catalog_markdown,
    get_registered_components_catalog,
    list_custom_component_specs,
    load_custom_components_registry,
    register_custom_component,
    unregister_custom_component,
)
from amca_agent.diagnostics import (
    DiagnosticReport,
    ErrorOrigin,
    diagnose_exception,
    format_diagnostic_report_for_markdown,
)
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
    inspect_provider_runtime_status,
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
    load_custom_components_registry(ARTIFACT_ROOT / "custom_components" / "custom_registry.json")
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
    st.session_state.setdefault("active_error_dialog", None)
    st.session_state.setdefault("last_error_report", None)


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


if hasattr(st, "dialog"):
    @st.dialog("🔍 Pemberitahuan Diagnostik Kesalahan", width="large")
    def _show_error_fly_window(report: DiagnosticReport) -> None:
        origin_color = {
            ErrorOrigin.EXTERNAL_SERVICE: "#E65100",  # Amber / Orange
            ErrorOrigin.USER_INPUT_FLOW: "#0277BD",   # Ocean Blue
            ErrorOrigin.CORE_SYSTEM: "#C62828",       # Crimson Red
        }.get(report.origin, "#37474F")

        st.markdown(
            f"<div style='background-color: {origin_color}; color: white; padding: 6px 14px; "
            f"border-radius: 6px; font-weight: bold; display: inline-block; margin-bottom: 12px; font-size: 0.95rem;'>"
            f"{report.origin_icon} {report.origin_label}"
            f"</div>",
            unsafe_allow_html=True,
        )
        st.subheader(report.headline)
        st.write(report.explanation)

        st.markdown("#### 💡 Langkah Penyelesaian yang Disarankan:")
        for idx, step in enumerate(report.remediation_steps, 1):
            st.markdown(f"**{idx}.** {step}")

        with st.expander("🔍 Rincian Diagnostik Teknis (Klik untuk memperluas)", expanded=False):
            if report.context:
                st.markdown(f"**Konteks Operasi**: `{report.context}`")
            if report.raw_message:
                st.markdown(f"**Pesan Mentah Sistem**:\n```\n{report.raw_message}\n```")
            if report.technical_details:
                st.markdown("**Detail Teknis Tambahan**:")
                st.json(report.technical_details)

        col_c1, col_c2 = st.columns([4, 1])
        with col_c2:
            if st.button("Tutup Jendela", key="btn_close_error_modal", type="primary"):
                st.session_state.active_error_dialog = None
                st.rerun()
else:
    def _show_error_fly_window(report: DiagnosticReport) -> None:
        st.error(f"{report.origin_icon} [{report.origin_label}] {report.headline}: {report.explanation}")


_init()
harness: AgentHarnessSession = st.session_state.harness

if st.session_state.get("active_error_dialog") is not None:
    _show_error_fly_window(st.session_state["active_error_dialog"])

with st.sidebar:
    st.header("Pengaturan Agent Harness")
    provider = st.selectbox("Provider model", PROVIDER_OPTIONS)
    default_model_val = DEFAULT_MODELS.get(provider, "gemini-3.8-flash")
    base_url_default = PROVIDER_DEFAULT_URLS.get(provider, "")
    base_url: str | None = None

    api_key: str = ""
    model: str = default_model_val

    # =========================================================================
    # Kategori 1: 9Router (Local Proxy Gateway & Combos)
    # =========================================================================
    if provider == "9Router":
        base_url = st.text_input("Endpoint 9Router", value=base_url_default or "http://127.0.0.1:20128/v1", key="url_9router")
        st_9r = inspect_provider_runtime_status("9router", base_url=base_url)
        st.markdown(f"**Status Gateway**: {st_9r['status_badge']}")
        if st_9r["guidance"]:
            st.info(st_9r["guidance"])

        if st.button("Pindai Model & Combo 9Router"):
            try:
                st.session_state.discovered_models = discover_provider_models("9router", base_url=base_url)
                st.success(f"Ditemukan {len(st.session_state.discovered_models)} model/Combo.")
            except Exception as exc:
                rep = diagnose_exception(exc, context="Pindai Model & Combo 9Router")
                st.session_state.active_error_dialog = rep
                st.session_state.last_error_report = rep
                st.rerun()

        combos_avail = st_9r.get("combos", [])
        discovered = st.session_state.discovered_models or []
        model_options = []
        if combos_avail:
            model_options.extend(combos_avail)
        if discovered:
            for m in discovered:
                if m not in model_options:
                    model_options.append(m)
        if not model_options:
            model_options = ["free-combo", "premium-coding", "alicode-intl/qwen3.5-plus", "gemini/gemini-2.5-flash"]

        default_idx = 0
        if "free-combo" in model_options:
            default_idx = model_options.index("free-combo")

        model = st.selectbox("Pilih Model / Combo 9Router", model_options, index=default_idx, key="model_9router_select")
        st.caption("🔒 *API key penyedia AI sudah dikelola di 9Router. AMCA otomatis menggunakan Default Key lokal.*")
        with st.expander("⚙️ Pengaturan Lanjutan (Override 9Router Key)", expanded=False):
            api_key = st.text_input("Kunci Akses 9Router (opsional, jika remote)", type="password", key="key_9router_override")

    # =========================================================================
    # Kategori 2: Cloud API Langsung (Google Gemini, OpenAI, Anthropic, xAI Grok, Custom)
    # =========================================================================
    elif provider in {"Google Gemini", "xAI (Grok)", "OpenAI", "Anthropic", "Custom OpenAI-Compatible"}:
        st.caption(f"☁️ *Koneksi langsung ke Cloud API {provider}*")
        if provider == "Custom OpenAI-Compatible":
            base_url = st.text_input("Endpoint Base URL", value=base_url_default or "http://127.0.0.1:8000/v1", key="url_custom")

        if provider == "Google Gemini":
            gemini_recommendations = ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash", "gemini-1.5-pro"]
            model = st.selectbox("Pilih Model Gemini", gemini_recommendations, index=0, key="model_gemini_select")
        else:
            model = st.text_input("Model ID", value=default_model_val, key=f"model_{provider}")

        api_key = st.text_input("API key (hanya di memori sesi RAM)", type="password", key=f"key_{provider}")
        st.caption("🔒 *Kunci hanya disimpan di RAM laptop untuk sesi ini (`SessionCredentialVault`). Tidak pernah ditulis ke disk.*")

    # =========================================================================
    # Kategori 3: Runtime Model Lokal Laptop (Ollama, LM Studio, OpenCode)
    # =========================================================================
    elif provider in {"Ollama", "LM Studio", "OpenCode"}:
        base_url = st.text_input("Endpoint Local Runtime", value=base_url_default, key=f"url_{provider}")
        st_rt = inspect_provider_runtime_status(provider, base_url=base_url)
        st.markdown(f"**Status Runtime**: {st_rt['status_badge']}")
        if st_rt["guidance"]:
            st.info(st_rt["guidance"])

        if st.button(f"Pindai Model {provider}"):
            try:
                st.session_state.discovered_models = discover_provider_models(provider, base_url=base_url)
                st.success(f"Ditemukan {len(st.session_state.discovered_models)} model.")
            except Exception as exc:
                rep = diagnose_exception(exc, context=f"Pindai Model {provider}")
                st.session_state.active_error_dialog = rep
                st.session_state.last_error_report = rep
                st.rerun()

        local_models = st_rt.get("models") or st.session_state.discovered_models or []
        if local_models:
            model = st.selectbox(f"Model {provider} Terpasang", local_models, key=f"model_select_{provider}")
        else:
            model = st.text_input("Model ID", value=default_model_val, key=f"model_{provider}")

        st.caption("💻 *Runtime lokal berjalan di laptop tanpa perlu API key.*")
        with st.expander("⚙️ Pengaturan Lanjutan (Bearer Token Opsional)", expanded=False):
            api_key = st.text_input("Token Akses (opsional)", type="password", key=f"key_{provider}_opt")

    # =========================================================================
    # Kategori 4: Local Model GGUF Mandiri (Dijaga Hardware Gate)
    # =========================================================================
    elif provider == "Local Model":
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

    # =========================================================================
    # Kategori 5: AMCA Combo (Rantai Fallback Native)
    # =========================================================================
    elif provider == "AMCA Combo":
        model = st.text_input("Nama Rantai Combo", value="resilient-local-combo", key="combo_name")
        tier1_spec = st.text_input("Tier 1 (provider:model)", value="9Router:free-combo", key="combo_t1")
        tier2_spec = st.text_input("Tier 2 (provider:model)", value="Ollama:qwen2.5-coder:7b", key="combo_t2")
        tier3_spec = st.text_input(
            "Tier 3 Fallback Akhir",
            value="Offline Deterministic:builtin-deterministic-v1",
            key="combo_t3",
        )
        api_key = st.text_input("API key Tier 1 (opsional, di memori sesi)", type="password", key="key_combo_t1")
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

    # =========================================================================
    # Kategori 6: Offline Deterministic (Mode Air-Gapped)
    # =========================================================================
    elif provider == "Offline Deterministic":
        st.success("🛡️ **Mode Air-Gapped (100% Offline)**")
        st.caption("Menggunakan pembuat spesifikasi berbasis aturan matematika deterministik. Tanpa koneksi jaringan, tanpa API key, tanpa biaya token.")
        model = "builtin-v1"
        api_key = ""

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
    if st.session_state.get("last_error_report") is not None:
        rep = st.session_state["last_error_report"]
        st.divider()
        st.caption(f"Status Diagnostik: {rep.origin_icon} {rep.origin_label}")
        if st.button("🔍 Buka Jendela Diagnostik", key="btn_reopen_diag_sidebar"):
            st.session_state.active_error_dialog = rep
            st.rerun()

example_files = sorted((ROOT / "examples").glob("*.yaml"))
example_map = {f"{p.stem} — {p.name}": p for p in example_files}
left, right = st.columns([1, 1])
with left:
    st.subheader("1 · Problem statement")
    catalog_rows = get_registered_components_catalog()
    st.info(
        f"**Komponen Terdaftar Saat Ini ({len(catalog_rows)})**: "
        + ", ".join(f"`{r['component_id']}`" for r in catalog_rows)
        + " — Prompt Anda hanya dapat merangkai komponen terdaftar di bawah ini (atau buat komponen baru di Bagian 8)."
    )
    with st.expander("📋 Katalog Komponen Terdaftar & Panduan Batasan Prompt (Klik untuk rincian Port & Kontrak Hoare)", expanded=False):
        st.markdown(format_catalog_markdown())
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
            rep = diagnose_exception(
                f"out-of-scope: {intent_check.boundary_message or intent_check.reason}",
                context="Klasifikasi Intent Permintaan Mesin",
            )
            st.session_state.active_error_dialog = rep
            st.session_state.last_error_report = rep
            st.rerun()
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
            except Exception as exc:
                if st.session_state.messages:
                    st.session_state.messages.pop()
                rep = diagnose_exception(exc, context="Buat YAML dengan Agent")
                st.session_state.active_error_dialog = rep
                st.session_state.last_error_report = rep
                st.rerun()
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
        except Exception as exc:
            if st.session_state.messages:
                st.session_state.messages.pop()
            rep = diagnose_exception(exc, context="Revisi YAML lewat Chat")
            st.session_state.active_error_dialog = rep
            st.session_state.last_error_report = rep
            st.rerun()

with right:
    st.subheader("3 · Tinjau, validasi struktural, & verifikasi formal")
    st.caption("YAML hasil agent adalah kandidat. Ia diverifikasi secara struktural dan matematis sebelum dijalankan.")
    st.text_area("Spesifikasi mesin YAML", key="machine_yaml", height=340)
    if st.button("Validasi YAML saat ini"):
        _record_version("manual_edit")
    unregistered_plans = detect_unregistered_components_in_yaml(
        st.session_state.machine_yaml,
        st.session_state.get("problem", ""),
    )
    if unregistered_plans:
        st.warning(
            f"⚠️ Terdeteksi {len(unregistered_plans)} komponen pada YAML yang belum terdaftar di Library AMCA:\n"
            + "\n".join(
                f"- `{p.component_id}`: in={p.inferred_input_ports}, out={p.inferred_output_ports} ({p.role_description})"
                for p in unregistered_plans
            )
        )
        if st.button("⚡ Sintesis & Daftarkan Komponen On-The-Fly (Code Agent)", key="btn_synthesize_otf"):
            try:
                bound = synthesize_and_bind_missing_components(
                    unregistered_plans,
                    problem_statement=st.session_state.get("problem", ""),
                    harness=harness,
                    persist=True,
                )
                st.success(
                    f"Berhasil mensintesis & mendaftarkan {len(bound)} komponen baru ke library `amca_components`: "
                    + ", ".join(f"`{b.spec.component_id}`" for b in bound)
                )
                _record_version("synthesis")
                st.rerun()
            except Exception as exc:
                rep = diagnose_exception(exc, context="Sintesis Komponen On-The-Fly")
                st.session_state.active_error_dialog = rep
                st.session_state.last_error_report = rep
                st.rerun()
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
    has_valid_failure = bool(
        st.session_state.validation_error
        or (st.session_state.verification and st.session_state.verification.status != "verified")
    )
    if has_valid_failure:
        v_err_msg = st.session_state.validation_error or "; ".join(r.message for r in st.session_state.verification.reasons)
        if st.button("🔍 Diagnosa Masalah Validasi (Buka Jendela Diagnostik)", key="btn_diag_val_fail"):
            rep = diagnose_exception(v_err_msg, context="Validasi Spesifikasi YAML")
            st.session_state.active_error_dialog = rep
            st.session_state.last_error_report = rep
            st.rerun()
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
        except (AMCAError, ValueError, json.JSONDecodeError, Exception) as exc:
            rep = diagnose_exception(exc, context="Eksekusi Runtime Mesin")
            st.session_state.active_error_dialog = rep
            st.session_state.last_error_report = rep
            st.rerun()

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
                    rep = diagnose_exception(exc, context="Konstruksi & Packaging Proyek Mandiri")
                    st.session_state.active_error_dialog = rep
                    st.session_state.last_error_report = rep
                    st.rerun()

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

st.subheader("8 · Pembuat & Pendaftar Komponen Baru (Custom Component Studio)")
st.caption(
    "Tambahkan komponen deterministik baru beserta kontrak Hoare-nya ke dalam Registry AMCA. "
    "Komponen yang didaftarkan di sini langsung tampil pada Katalog Komponen Terdaftar (Bagian 1) dan siap dipakai dalam prompt YAML, verifikasi formal 3-tahap, maupun konstruksi paket kode Python (.zip)."
)
with st.expander("🧩 Buat & Daftarkan Komponen Baru atau Kelola Komponen Kustom", expanded=False):
    tab_template, tab_external = st.tabs([
        "🛠️ Template Operasi Deterministik",
        "🔗 Ikat File Python (.py) dari Luar (Antigravity/OpenCode/Codex)",
    ])
    with tab_template:
        cc_col1, cc_col2 = st.columns([1, 1])
        with cc_col1:
            cc_id = st.text_input("ID Komponen Baru (`^[a-z][a-z0-9_-]{0,63}$`)", value="sentence_counter", key="cc_id")
            cc_alias = st.text_input("Alias `amca/v1alpha1`", value=f"custom.{cc_id.strip() or 'sentence_counter'}", key="cc_alias")
            cc_name = st.text_input("Nama Tampilan", value="Sentence Counter", key="cc_name")
            cc_role = st.text_input(
                "Deskripsi Peran & Fungsi",
                value="Menghitung jumlah kalimat dari teks yang telah divalidasi.",
                key="cc_role",
            )
        with cc_col2:
            cc_template = st.selectbox(
                "Template Operasi Deterministik",
                list(OPERATION_TEMPLATES.keys()),
                format_func=lambda k: f"{k} — {OPERATION_TEMPLATES[k]['label']}",
                key="cc_template",
            )
            cc_mode = st.selectbox(
                "Mode Perhitungan / Transformasi",
                ["sentence_count", "line_count", "digit_count", "keyword_count", "uppercase", "lowercase", "titlecase", "normalize_spaces"],
                key="cc_mode",
            )
            cc_keyword = st.text_input("Kata Kunci Default (opsional, untuk `keyword_count`)", value="", key="cc_keyword")
            cc_hint = st.text_input(
                "Panduan Batasan Prompt untuk User",
                value=f"Sebutkan `{cc_id.strip() or 'sentence_counter'}` setelah `validate_text` pada prompt Anda.",
                key="cc_hint",
            )

        btn_col1, btn_col2 = st.columns([1, 1])
        with btn_col1:
            if st.button("Daftarkan Komponen ke Registry AMCA", key="btn_register_cc"):
                try:
                    cfg_keys: list[str] = []
                    def_cfg: dict[str, Any] = {}
                    params: dict[str, Any] = {"mode": cc_mode}
                    if cc_keyword.strip():
                        cfg_keys.append("keyword")
                        def_cfg["keyword"] = cc_keyword.strip()
                        params["keyword"] = cc_keyword.strip()
                    spec_payload = {
                        "component_id": cc_id.strip(),
                        "alias": cc_alias.strip() or f"custom.{cc_id.strip()}",
                        "name": cc_name.strip() or cc_id.strip().replace("_", " ").title(),
                        "role": cc_role.strip(),
                        "operation_template": cc_template,
                        "config_keys": cfg_keys,
                        "default_config": def_cfg,
                        "template_params": params,
                        "prompt_hint": cc_hint.strip(),
                    }
                    reg_spec = register_custom_component(
                        spec_payload,
                        persist=True,
                        registry_path=ARTIFACT_ROOT / "custom_components" / "custom_registry.json",
                    )
                    st.success(
                        f"Komponen `{reg_spec.component_id}` (`{reg_spec.alias}`) berhasil didaftarkan ke Registry AMCA dan siap digunakan di prompt YAML!"
                    )
                    st.rerun()
                except Exception as exc:
                    rep = diagnose_exception(exc, context="Pendaftaran Komponen Kustom")
                    st.session_state.active_error_dialog = rep
                    st.session_state.last_error_report = rep
                    st.rerun()
        with btn_col2:
            if st.button("Draft Otomatis dari Deskripsi Peran", key="btn_draft_cc"):
                try:
                    drafted = draft_custom_component_from_description(cc_role, component_id=cc_id.strip(), alias=cc_alias.strip())
                    reg_spec = register_custom_component(
                        drafted,
                        persist=True,
                        registry_path=ARTIFACT_ROOT / "custom_components" / "custom_registry.json",
                    )
                    st.success(
                        f"Komponen hasil draft otomatis `{reg_spec.component_id}` (`{reg_spec.operation_template}`) terdaftar!"
                    )
                    st.rerun()
                except Exception as exc:
                    rep = diagnose_exception(exc, context="Draft Otomatis Komponen Kustom")
                    st.session_state.active_error_dialog = rep
                    st.session_state.last_error_report = rep
                    st.rerun()

    with tab_external:
        st.markdown(
            "Ikat fungsi Python murni yang Anda buat di **Antigravity**, **OpenCode**, atau **Codex**. "
            "Kode akan diverifikasi melalui **Static AST Security Gate** (menolak import/panggilan OS berbahaya) "
            "dan diuji di sandbox sebelum didaftarkan ke library `amca_components`."
        )
        ext_py_code = st.text_area(
            "Kode Python Komponen (.py)",
            height=180,
            value=(
                "import re\n\n"
                "def clean_punctuation(text: str) -> str:\n"
                "    \"\"\"Menghapus tanda baca dan menormalkan spasi.\"\"\"\n"
                "    return re.sub(r'[^\\w\\s]', '', text or '').strip()\n"
            ),
            key="ext_py_code",
        )
        ec_col1, ec_col2 = st.columns([1, 1])
        with ec_col1:
            ext_cid = st.text_input("ID Komponen (opsional, auto-infer dari fungsi)", value="", key="ext_cid")
            ext_alias = st.text_input("Alias v1alpha1 (opsional)", value="", key="ext_alias")
        with ec_col2:
            ext_name = st.text_input("Nama Tampilan (opsional)", value="", key="ext_name")
            ext_role = st.text_input("Deskripsi Peran (opsional)", value="", key="ext_role")

        if st.button("Audit AST, Uji Kontrak Hoare & Ikat ke Library AMCA", key="btn_bind_external_py"):
            try:
                bound = bind_component_from_python_source(
                    ext_py_code,
                    component_id=ext_cid.strip(),
                    alias=ext_alias.strip(),
                    name=ext_name.strip(),
                    role=ext_role.strip(),
                    origin="external_gui_bound",
                    persist=True,
                )
                st.success(
                    f"Komponen eksternal `{bound.spec.component_id}` (`{bound.spec.alias}`) lolos AST Gate & "
                    f"berhasil diikat ke library `amca_components`!"
                )
                st.json({
                    "component_id": bound.spec.component_id,
                    "input_ports": bound.spec.input_ports,
                    "output_ports": bound.spec.output_ports,
                    "sample_outputs": bound.sample_outputs,
                    "sha256": bound.sha256,
                })
                st.rerun()
            except Exception as exc:
                rep = diagnose_exception(exc, context="Pengikatan Komponen Python Eksternal")
                st.session_state.active_error_dialog = rep
                st.session_state.last_error_report = rep
                st.rerun()

    custom_list = list_custom_component_specs()
    if custom_list:
        st.markdown(f"**Komponen Kustom Terdaftar Saat Ini ({len(custom_list)}):**")
        for cspec in custom_list:
            row_a, row_b = st.columns([4, 1])
            with row_a:
                st.markdown(
                    f"- **`{cspec.component_id}`** (`{cspec.alias}`) · *{cspec.operation_template}* · "
                    f"In: `{cspec.input_ports}` → Out: `{cspec.output_ports}` · {cspec.role}"
                )
            with row_b:
                if st.button(f"Hapus {cspec.component_id}", key=f"del_cc_{cspec.component_id}"):
                    unregister_custom_component(
                        cspec.component_id,
                        persist=True,
                        registry_path=ARTIFACT_ROOT / "custom_components" / "custom_registry.json",
                    )
                    st.rerun()

st.caption(
    f"Komponen allowlist saat ini: {', '.join(component_ids())}. "
    "Eksekusi lokal, berurutan, dan hanya melalui runtime AMCA."
)
