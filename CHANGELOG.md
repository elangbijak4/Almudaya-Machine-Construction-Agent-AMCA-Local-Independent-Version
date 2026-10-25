# Changelog

## 0.2.0 — 2026-10-25 (AMCA Local Independent Version — CR-002)

- Added **Specialized Agent Harness (`src/amca_agent/harness.py`, `provider.py`)** supporting 12 provider types: Gemini, xAI (Grok), OpenAI, Anthropic, Custom OpenAI-Compatible, **9Router (`nine_router` including 9Router Combos)**, **Ollama**, **LM Studio**, **OpenCode**, **Local Model**, **AMCA Combo (`amca_combo` token-limit fallback chain)**, and **Offline Deterministic**.
- Added **Laptop Hardware Capability Inspection Gate (`src/amca_agent/hardware.py`)** inspecting real host RAM, free disk, CPU cores/arch, and GPU/VRAM (`ELIGIBLE` vs. `REFUSED_INSUFFICIENT_HARDWARE`).
- Added **On-The-Fly Human-in-the-Loop (HITL) Subworker Provisioning** with isolated per-subworker credentials in `SessionCredentialVault`.
- Added **3-Stage Compositional Formal Verification (`src/amca_agent/formal_verifier.py`)** emitting `formal-proof-certificate.json` (Stage 1 Hoare pre/postcondition entailment, Church-Rosser confluence, taint non-interference; Stage 2 revision invariant preservation; Stage 3 Python `ast.parse()` isomorphism $G_{\text{code}} \cong G_{\text{yaml}}$ and runtime guard verification).
- Added **Two-Stage Cryptographic Approvals (`src/amca_agent/approvals.py`)**, **Waterfall Planner (`src/amca_agent/planner.py`)**, **Bounded Project Builder (`src/amca_agent/builder.py`)**, and **Handover ZIP Packager (`src/amca_agent/packager.py`)**.
- Added complete Indonesian user reference books (`help/USER_MANUAL.md`, `help/USER_GUIDE.md`, `help/USER_TUTORIAL.md`) and verification report (`docs/14-agent-constructor-verification-and-handover.md`).

## 0.1.5 — 2026-10-22

- Added executable workflow consistency and phase-gate validator.
- Added per-phase exit-criterion evidence and owner-approval register.
- Added Definition of Done and explicit final release acceptance gate.
- Required a human owner approval before each phase transition.
- Synchronized initial phase statuses across `orchestration.yaml` and `docs/phase-status.md`.
- Kept all phase approvals pending; this scaffold update does not approve P0 or claim implementation/test completion.

## 0.1.0 — Initial scaffold

- Established the AMCA Waterfall document structure, orchestration plan, and initial PoC scope.
# Unreleased

- Added an optional Streamlit web UI for AI-assisted YAML authoring and revision chat, reusing AMCA's verifier and allowlisted runtime.
- Added verified DAG visualization and locally persisted/downloadable YAML, graph, verification, and execution artifacts.
- Added optional Gemini, xAI/Grok, and OpenAI API adapters; API keys are not persisted.

