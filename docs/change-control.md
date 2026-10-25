# Change Control

## Approved change records

### CR-001 — Conversational YAML-Authoring Agent & Streamlit Local UI
- **Change ID:** CR-001
- **Date:** 2026-10-22
- **Requester:** Project owner (explicit request in project conversation)
- **Affected phase/document:** Post-P6 scope extension; P1–P4 requirements/design/implementation records and P5–P6 evaluation/handover
- **Current approved baseline:** Local CLI PoC accepts user-authored YAML for the fixed allowlisted DAG runtime; no LLM/API or GUI dependency.
- **Proposed change:** Add a separate optional Streamlit agent UI that generates/revises YAML through a configured model API, supports example selection and chat iteration, validates every candidate with the existing verifier, requires explicit user confirmation to execute, and persists/displays DAG and run artifacts locally.
- **Reason and evidence:** Project owner requested the conversational machine-authoring workflow and a visible DAG/run artifact experience.
- **Impact:** Adds a GUI dependency and optional external model calls; extends data handling to locally persist user chat/YAML; leaves the AMCA runtime allowlist, graph schema, verifier, and execution semantics unchanged.
- **Earlier phases to reopen:** P1 requirements, P2 architecture, P3 contracts/test plan, P4 implementation; P5 verification and P6 handover need an extension review after implementation.
- **Decision:** Approved by explicit project-owner implementation request; 2026-10-22 (formally absorbed and completed under CR-002).
- **Decision maker/date:** Project owner / 2026-10-22.
- **Follow-up actions:** Implemented in `app.py` and `src/amca_agent/`; regression evidence recorded in `docs/evidence/cr-001-retest-2026-10-22.md` and extended to full constructor handover under CR-002.

---

### CR-002 — Specialized Agent Harness, 9Router/Local-Runtime Bridges, Combo Token-Limit Fallback, 3-Stage Formal Verification, & Standalone Agent Constructor (Local Independent Version)
- **Change ID:** CR-002
- **Date:** 2026-10-25
- **Requester:** Project owner (explicit architectural review and implementation authorization)
- **Affected phase/document:** Post-P6 constructor & formal verification extension; `docs/12-agent-constructor-requirements.md`, `docs/13-agent-constructor-architecture.md`, `docs/14-agent-constructor-verification-and-handover.md`, `docs/traceability-matrix.md`, `help/USER_MANUAL.md`, `help/USER_GUIDE.md`, `help/USER_TUTORIAL.md`, `src/amca_agent/*`, `app.py`, `schemas/*`, and `tests/*`.
- **Current approved baseline:** `src/amca/` (`v0.1.0`, `P0`–`P6` approved, 69 tests) + `CR-001` (`src/amca_agent/` & `app.py`, 79 total tests).
- **Proposed change:**
  1. Evolve AMCA Local Independent Version into a **Specialized Agent Harness** supporting hot-swappable Primary Agent and Subworker bindings across Cloud APIs (`Gemini`, `xAI`, `OpenAI`, `Anthropic`, `Custom OpenAI-Compatible`), **9Router Bridge** (`nine_router` at `http://127.0.0.1:20128/v1` including 9Router Combos), **Local AI Runtimes** (`Ollama`, `LM Studio`, `OpenCode` with live model auto-discovery), **Hardware-Gated Local Model Downloads** (`hardware.py`), **Native AMCA Combo & Token-Limit Fallback Chains** (`FallbackComboRouter`), and `Offline Deterministic` synthesis.
  2. Provide an **On-The-Fly Human-in-the-Loop (HITL) Subworker Provisioning Interface** allowing the user to approve/decline proposed Subworkers and supply an independent API key, model, or Combo chain dedicated to each Subworker.
  3. Add support for `apiVersion: amca/v1alpha1` (`kind: MachineSystem`) with unified component aliases and explicit `assumptions`, `limitations`, and `unresolvedQuestions` while preserving `schema_version: "1.0"` backward compatibility.
  4. Implement a **3-Stage Formal Verification Engine** (`src/amca_agent/formal_verifier.py`) emitting `formal-proof-certificate.json`: Stage 1 (Spec-level reachability `FO-TOP-01`, Church-Rosser confluence `FO-CON-01`, Hoare pre/postcondition entailment `FO-HOA-01`, goal entailment `FO-GOAL-01`, and taint non-interference `FO-SEC-01`), Stage 2 (Revision invariant preservation), and Stage 3 (Post-construction Python `ast.parse()` graph isomorphism $G_{\text{code}} \cong G_{\text{yaml}}$ `FO-REF-01` and runtime contract guards `FO-REF-02`).
  5. Implement two-stage approval gates (**Approval A `spec_approval`** and **Approval B `construction_approval`**), bounded standalone Python project construction (`builder.py`), real generated-project test execution, redacted audit logs (`construction-log.jsonl`), and reproducible handover ZIP packaging (`packager.py`).
  6. Enforce the **Strict Anti-Mocking Mandate** and verify 100% consistency against the three reference books (`USER_MANUAL.md`, `USER_GUIDE.md`, `USER_TUTORIAL.md`).
- **Reason and evidence:** Project owner requested a scientifically rigorous, formally verified, model-agnostic Local Independent Agent Constructor with 9Router/Combo fallback resilience and hardware-safe local model support.
- **Impact:** Extends `src/amca_agent/`, `app.py`, `schemas/`, `help/`, `docs/`, and `tests/` while preserving `src/amca/` (`v0.1.0`) and all `P0`–`P6` workflow gates intact.
- **Earlier phases to reopen:** None broken (`P0`–`P6` remain `approved` as foundation; CR-002 adds extension deliverables `docs/12..14` and maps all requirements in `docs/traceability-matrix.md`).
- **Decision:** Approved by explicit project-owner instruction; 2026-10-25.
- **Decision maker/date:** Project owner / 2026-10-25.
- **Follow-up actions:** Implemented and verified across Tasks 1–7.

Use this process when changing scope, requirements, architecture, dependencies, acceptance criteria, or the runtime trust model.

## Rules

1. Do not silently modify approved requirements or architecture.
2. A change affecting an earlier phase reopens that phase and dependent review steps as needed.
3. Update `orchestration.yaml`, `phase-status.md`, and `traceability-matrix.md` after approval.
4. Keep a short rationale and evidence trail.
