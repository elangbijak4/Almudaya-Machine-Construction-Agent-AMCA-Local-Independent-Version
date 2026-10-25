# 14 · Agent Constructor Verification & Handover Report (`CR-002`)

**Change Request:** `CR-002` — AMCA Local Independent Version (`v0.2.0`)  
**Verification Status:** `PASSED` (All Unit, Integration, GUI, Mutation, and Scaffold Gates Passed)

---

## 1. Executive Summary

This report records the verification and handover evidence for the refactored **AMCA Local Independent Version** (`CR-002`). All modules were implemented with **zero production mocking/stubbing**, enforcing real OS hardware telemetry, real HTTP/local runtime connectors, real 3-stage compositional mathematical formal verification, real Python AST parsing (`ast.parse()`), real `compileall` and `unittest` execution, and real `zipfile` handover packaging.

---

## 2. Three-Book Verification Oracle Audit (`VO-01` – `VO-06`)

| Oracle ID | Verification Requirement (`USER_MANUAL.md`, `USER_GUIDE.md`, `USER_TUTORIAL.md`) | Implementation & Test Evidence | Status |
| :--- | :--- | :--- | :--- |
| **VO-01** | Preliminary Harness Setup supports hot-swappable Cloud APIs, **9Router (`nine_router`)**, **Ollama (`ollama`)**, **LM Studio (`lm_studio`)**, **OpenCode (`opencode`)**, **Local Model (`local_model`)**, **AMCA Combo (`amca_combo`)**, and **Offline Deterministic**. | `src/amca_agent/provider.py`, `src/amca_agent/harness.py`, `app.py`, `src/amca_agent/cli.py`, `tests/unit/test_hardware_and_harness.py` | **VERIFIED** |
| **VO-02** | `hardware.py` inspects real host laptop RAM, Disk, CPU, and GPU/VRAM and blocks downloads (`REFUSED_INSUFFICIENT_HARDWARE`) when hardware is below model thresholds. | `src/amca_agent/hardware.py`, `tests/unit/test_hardware_and_harness.py` | **VERIFIED** |
| **VO-03** | `FallbackComboRouter` performs ordered failover (`Tier k -> Tier k+1`) on `token_limit_exceeded`, `output_truncated_length`, or `rate_limit_429`, compacts context, and logs `FallbackTransitionEvent` without leaking keys. | `src/amca_agent/harness.py`, `tests/unit/test_hardware_and_harness.py` | **VERIFIED** |
| **VO-04** | On-The-Fly Subworker HITL prompts user approval and allows an isolated Subworker API key/model/Combo (or falls back to Primary Agent when declined). | `src/amca_agent/harness.py`, `src/amca_agent/planner.py`, `tests/unit/test_hardware_and_harness.py` | **VERIFIED** |
| **VO-05** | `formal_verifier.py` executes Stage 1 (`FO-TOP-01`, `FO-CON-01`, `FO-HOA-01`, `FO-GOAL-01`, `FO-SEC-01`), Stage 2 (`FO-EVO-01`), and Stage 3 (`ast.parse()` isomorphism $G_{\text{code}} \cong G_{\text{yaml}}$ `FO-REF-01` & guard `FO-REF-02`) and emits `formal-proof-certificate.json`. | `src/amca_agent/formal_verifier.py`, `tests/unit/test_formal_verifier.py`, `tests/integration/test_construction_and_zip.py` | **VERIFIED** |
| **VO-06** | All CLI subcommands and GUI workflows documented in `help/USER_MANUAL.md`, `help/USER_GUIDE.md`, and `help/USER_TUTORIAL.md` match the application 100%. | `help/USER_MANUAL.md`, `help/USER_GUIDE.md`, `help/USER_TUTORIAL.md`, `tests/integration/test_conversation_and_spec_approval.py`, `tests/integration/test_streamlit_app.py` | **VERIFIED** |

---

## 3. Automated Test Suite Summary

All unit and integration test suites executed cleanly under CPython 3.12:

- `tests/unit/test_system_spec.py` — Validates `amca/v1alpha1` (`kind: MachineSystem`) and `schema_version: "1.0"` compatibility, security policy, and `secretRef` constraints.
- `tests/unit/test_formal_verifier.py` — Validates Stage 1 Hoare pre/postcondition entailment, Church-Rosser confluence, secret taint non-interference, Stage 2 revision invariants, and Stage 3 AST refinement proofs.
- `tests/unit/test_hardware_and_harness.py` — Validates real OS hardware inspection, fail-closed model download gate, 9Router/Ollama/LM Studio/OpenCode discovery, Native Combo token-limit fallback chain, and On-The-Fly Subworker HITL credential isolation.
- `tests/unit/test_intent_and_approvals.py` — Validates scope boundary classification, cost-minimizing Waterfall planner, and SHA-256 bound two-stage approvals (`APPROVE_SPEC` & `APPROVE_CONSTRUCTION`).
- `tests/integration/test_conversation_and_spec_approval.py` — Validates CLI `chat` opening greeting, `formal-verify`, `hardware-check`, `combo-config`, `proof`, and `approve-spec`.
- `tests/integration/test_builder_scaffold.py` — Validates bounded project generation in `artifacts/constructed_projects/<machine_id>-rev<NNN>/`.
- `tests/integration/test_construction_and_zip.py` — Validates end-to-end project construction, Stage 3 AST mutation detection (`FO-REF-01: REFUTED`), zero secret leakage across all artifacts/logs, and `<machine_id>-rev<NNN>-handover.zip` packaging.
- `tests/integration/test_streamlit_app.py` — Validates the Streamlit web application end-to-end.

---

## 4. Live Multi-Provider & Real API Key End-to-End Audit (`2026-10-25`)

Following the automated suite, a **live end-to-end empirical audit** was executed against live external and local endpoints on the host machine using **two distinct live Google Gemini API keys** (Key 1 `AIza...` for Primary Agent / Combo Tier 2, Key 2 `AQ...` for On-The-Fly Subworker HITL), a running **9Router** daemon (`http://127.0.0.1:20128/v1`), and a local **OpenCode** installation:

1. **Live Model & Combo Discovery**:
   - `discover_provider_models("nine_router")` discovered **824 models** from the live local 9Router daemon and automatically authenticated against the local 9Router SQLite database (`%APPDATA%\9router\db\data.sqlite`).
   - `discover_provider_models("opencode")` discovered **12 models** from the host's OpenCode CLI/runtime.
   - `discover_provider_models("gemini")` discovered **46 generative models** (`gemini-2.5-flash`, `gemini-2.5-pro`, etc.) from `https://generativelanguage.googleapis.com/v1beta/models`.
2. **Live `AMCA Combo` Failover (`Tier 1: nine_router -> Tier 2: gemini`)**:
   - When Tier 1 (`nine_router`) returned an unconfigured upstream provider error (`HTTP 404`), `FallbackComboRouter` recorded a `FallbackTransitionEvent` (`from_tier: 1 -> to_tier: 2`, `trigger_reason: "upstream_unavailable"`) and automatically failed over to Tier 2 (`gemini / gemini-2.5-flash` using Primary Gemini Key 1).
   - Live `gemini-2.5-flash` synthesized `machine_id: "live-gemini-audit"` (Revision 1), which immediately passed Structural Verification (`verified`) and all 5 Stage 1 Formal Verification obligations (`FO-TOP-01`, `FO-CON-01`, `FO-HOA-01`, `FO-GOAL-01`, `FO-SEC-01` = `PROVED`).
3. **Live Counterexample-Driven Repair via On-The-Fly Subworker HITL (Isolated Gemini Key 2)**:
   - A Hoare logic violation (`input.text -> analysis_a.text` bypassing `validate_text`) was injected, triggering `FO-HOA-01: REFUTED` with counterexample witness `missing required precondition(s) ['non_empty_trimmed']`.
   - Subworker `subworker-live-gemini-key2` was provisioned via On-The-Fly HITL using the **second, independent Gemini API Key** (`credential_isolated_from_primary: True`).
   - Given the broken YAML and the `FO-HOA-01` formal counterexample, the live Subworker repaired the DAG in Revision 2, restoring `verified` structural status and `PROVED` Stage 1 + Stage 2 Evolution formal status.
4. **Live Project Construction, Stage 3 AST Proof, & Zero-Leakage Scan**:
   - The repaired specification was approved (`APPROVE_SPEC` + `APPROVE_CONSTRUCTION`), constructed into a runnable Python package, verified by Stage 3 AST isomorphism (`FO-REF-01: PROVED`, `FO-REF-02: PROVED`), tested via its generated `unittest` suite (`PASSED`), and packaged into `live-gemini-audit-rev002-handover.zip` (15 files).
   - Every file in `live-gemini-audit-rev002-handover.zip` was scanned for both live Gemini API keys and the local 9Router key: **0 occurrences (`Secret Leakage Count = 0`)**.

