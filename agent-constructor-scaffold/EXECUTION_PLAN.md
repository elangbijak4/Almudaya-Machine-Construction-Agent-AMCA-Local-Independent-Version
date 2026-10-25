# Execution Plan and Approval Gates

Execute these tasks sequentially. Do not cross a task gate without explicit human approval (`APPROVE TASK <N>`). Every task must preserve the existing 77 tests and keep `python tools/validate_workflow.py --check-scaffold` and `--phase P0..P6` passing.

## Strict Anti-Mocking Rule for All Tasks

- **No Mocks or Stubs as Implementation**: Never complete a task by writing mock classes, dummy functions, `TODO`/`pass` stubs, or hardcoded return dictionaries in `src/` or `app.py`. Every feature—including OS hardware inspection, multi-provider & local-model agent harness routing, on-the-fly Subworker HITL provisioning, 3-stage formal verification, project generation, test execution, and ZIP archiving—must be genuinely realized.
- **No Mocking the System Under Test (SUT)**: Tests must execute the real implementation end-to-end and include mutation/non-reference cases proving that outputs are dynamically computed. Only outbound HTTP socket calls (`urllib.request.urlopen`) to remote LLM/download servers may be stubbed during offline test runs.

## Governance reconciliation rule

- The baseline Waterfall phases `P0`–`P6` in `orchestration.yaml` and `workflow/gate-records.yaml` remain `approved` as the historical foundation.
- This refactoring is recorded in `docs/change-control.md` as **CR-002 (Specialized Agent Harness, Multi-Stage Formal Verification, & Agent Constructor Refactoring)**, which formally absorbs and completes the pending `CR-001` (`P4-EXT`) scope and maps all requirements (`FR-01`–`FR-10`, `NFR-01`–`NFR-08`, `CR-UI-01`–`CR-UI-09`, and `AC-01`–`AC-21`) in `docs/traceability-matrix.md`.

---

## Task 0 — Repository discovery, audit reconciliation, and plan alignment

**Prompt:** Inspect the repository, baseline code (`src/amca/`, `src/amca_agent/`, `app.py`), tests (`tests/`), and workflow records (`orchestration.yaml`, `workflow/gate-records.yaml`, `docs/`). Reconcile all documents in `agent-constructor-scaffold/` with the audit findings, the **Specialized Agent Harness** design (Preliminary Setup UI, Hardware-Gated Local Models, On-The-Fly Subworker HITL with independent API keys), the **Multi-Stage Formal Verification** design (`formal_verifier.py` + `formal-proof-certificate.json`), and the **Strict Anti-Mocking Mandate**. Modify no application source code during Task 0.

**Deliverables:**
- Revised and aligned documents in `agent-constructor-scaffold/` (`README.md`, `MASTER_PROMPT.md`, `VISION_AND_SCOPE.md`, `SPECIFICATION_MODEL.md`, `TARGET_ARCHITECTURE.md`, `EXECUTION_PLAN.md`, `ACCEPTANCE_CRITERIA.md`, `DECISIONS_AND_OPEN_QUESTIONS.md`).

**Gate:** Human reviews the revised plan in `agent-constructor-scaffold/` and replies **`APPROVE TASK 0`**.

---

## Task 1 — Product/safety/harness/formal-verification requirements and traceability reconciliation

**Prompt:** Record **CR-002** in `docs/change-control.md` (formally reconciling `CR-001` and the Specialized Agent Harness + Hardware Gate + Subworker HITL + Multi-Stage Formal Verification + Anti-Mocking scope). Document all requirements and acceptance criteria (`AC-01`–`AC-21`) in `docs/12-agent-constructor-requirements.md`, and update `docs/traceability-matrix.md` so all baseline (`FR`/`NFR`), UI extension (`CR-UI`), and constructor/harness/formal (`AC`) requirements are mapped to design, source modules, and planned tests without breaking `tools/validate_workflow.py`.

**Deliverables:**
- `docs/change-control.md` (updated with `CR-002` and `CR-001` reconciliation)
- `docs/12-agent-constructor-requirements.md`
- `docs/traceability-matrix.md` (synchronized with `P6` baseline + `CR-UI-01..09` + `AC-01..21`)
- Verification that `tools/validate_workflow.py --check-scaffold` and `--phase P0..P6` pass.

**Gate:** Human approves requirements and traceability (`APPROVE TASK 1`).

---

## Task 2 — `amca/v1alpha1` specification schema, unified component aliases, and Stage 1 & 2 Formal Verifier (100% real algorithmic implementation)

**Prompt:**
1. Implement `src/amca_agent/system_spec.py` and `schemas/machine-system-v1alpha1.schema.yaml` to support `apiVersion: amca/v1alpha1` (`kind: MachineSystem`) while keeping `src/amca/schema.py` (`schema_version: "1.0"`) intact. Support component aliases (`text.input`, `text.validate`, `text.char_count`, `text.word_count`, `text.summarize`, `report.assemble` alongside canonical v1.0 IDs), `secretRef` validation (`^[A-Z][A-Z0-9_]{1,63}$`), explicit `assumptions`/`limitations`/`unresolvedQuestions`, conversion to `CandidateGraph` for `verify_candidate`, and bidirectional conversion/import from `schema_version: "1.0"`.
2. Implement `src/amca_agent/formal_verifier.py` (Stages 1 & 2) and `schemas/formal-proof-certificate.schema.yaml` using **real graph and symbolic predicate algorithms (zero hardcoded certificates)**:
   - **Stage 1 (`verify_formal_spec`)**: Computes forward/backward BFS reachability (`FO-TOP-01`), port in-degree & purity confluence (`FO-CON-01`), symbolic Hoare predicate set entailment $Q_u(\text{out}) \supseteq P_v(\text{in})$ across every edge (`FO-HOA-01`), acceptance goal entailment (`FO-GOAL-01`), and security/taint non-interference (`FO-SEC-01`). Emits concrete computed counterexamples when any proof obligation is `REFUTED`.
   - **Stage 2 (`verify_revision_invariants`)**: Dynamically compares two parsed revisions (`rev-N` vs `rev-(N+1)`) and proves whether security invariants and external I/O contracts are preserved.
3. Add `examples/valid_machine_system_v1alpha1.yaml` and unmocked unit + mutation tests in `tests/unit/test_system_spec.py` and `tests/unit/test_formal_verifier.py`.

**Deliverables:**
- `schemas/machine-system-v1alpha1.schema.yaml`
- `schemas/formal-proof-certificate.schema.yaml`
- `src/amca_agent/system_spec.py`
- `src/amca_agent/formal_verifier.py`
- `examples/valid_machine_system_v1alpha1.yaml`
- `tests/unit/test_system_spec.py`
- `tests/unit/test_formal_verifier.py`

**Gate:** Human approves schema, formal verifier (Stages 1 & 2), and unmocked unit/mutation test evidence (`APPROVE TASK 2`).

---

## Task 3 — Specialized Agent Harness, Hardware Inspector Gate, Intent Classifier, and Approval/Planner Models

**Prompt:** Document the constructor architecture, specialized agent harness, hardware inspection gate, threat boundaries, and 3-stage formal verification calculus in `docs/13-agent-constructor-architecture.md`. Implement:
1. `src/amca_agent/hardware.py`: Real OS hardware inspection (RAM total/available, disk free space, CPU cores/arch, GPU/VRAM) and the fail-closed local model gate (`evaluate_local_model_eligibility`) that permits downloads when specs are sufficient (`ELIGIBLE`) and strictly refuses downloads when specs are insufficient (`REFUSED_INSUFFICIENT_HARDWARE`).
2. `src/amca_agent/harness.py` & upgraded `src/amca_agent/provider.py`: Multi-provider Agent Harness across Cloud APIs (`Gemini`, `xAI (Grok)`, `OpenAI`, `Anthropic`, `Custom OpenAI-Compatible`), **9Router Bridge (`nine_router` at `http://127.0.0.1:20128/v1` supporting individual models and 9Router Combos)**, **Local AI Runtimes (`Ollama`, `LM Studio`, `OpenCode` with live model auto-discovery)**, `Local Model`, and `Offline Deterministic`; **AMCA's Native Combo & Token-Limit Fallback Chain Router (`FallbackComboRouter`)** that automatically compacts context, logs `FallbackTransitionEvent`, and fails over across `Tier 1 -> Tier 2 -> ... -> Tier N` upon token-limit overflow (`context_length_exceeded`, `finish_reason == "length"`, TPM/TPD limit) or `HTTP 429` quota exhaustion; `SessionCredentialVault` holding independent in-memory API keys for Primary Agent, Combo tiers, and Subworkers; and on-the-fly Subworker HITL state management (`request_subworker_hitl`, `approve_subworker_hitl`, `decline_subworker_hitl`).
3. `src/amca_agent/intent.py`, `src/amca_agent/approvals.py` (Approval A `spec_approval`, `subworker_hitl_approval`, and Approval B `construction_approval`), and `src/amca_agent/planner.py`.
Add unmocked unit tests in `tests/unit/test_hardware_and_harness.py` and `tests/unit/test_intent_and_approvals.py`.

**Deliverables:**
- `docs/13-agent-constructor-architecture.md`
- `src/amca_agent/hardware.py`
- `src/amca_agent/harness.py`
- `src/amca_agent/provider.py`
- `src/amca_agent/intent.py`
- `src/amca_agent/approvals.py`
- `src/amca_agent/planner.py`
- `tests/unit/test_hardware_and_harness.py`
- `tests/unit/test_intent_and_approvals.py`

**Gate:** Human approves architecture, hardware gate, multi-key agent harness, and core domain services (`APPROVE TASK 3`).

---

## Task 4 — Preliminary Harness Setup UI, Specification Conversation MVP, & Formal Counterexample Loop (GUI + CLI parity)

**Prompt:** Upgrade `src/amca_agent/cli.py` and `app.py` to support:
1. **Preliminary Harness Setup & 9Router-Style Combo Configuration Interface (Onboarding Step 0)**: Allows configuring and hot-swapping the Primary AMCA Agent across any Cloud API provider/custom endpoint (with in-memory API Key), **9Router** (individual models or 9Router Combos), **Ollama / LM Studio / OpenCode** (with live model auto-discovery), **AMCA's Native Combo Fallback Chain Builder (`Tier 1 -> Tier 2 -> Tier N`)**, a Local Downloaded Model (running `hardware.py` inspection first, displaying real laptop RAM/disk/CPU/GPU metrics, and refusing download if insufficient), or Offline Deterministic Mode.
2. Opening prompt *“Mesin/agent apakah yang Anda ingin buat?”* and scope classification (rejecting out-of-scope requests cleanly).
3. Drafting `amca/v1alpha1` YAML with explicit `assumptions`, `limitations`, and `unresolvedQuestions`, plus the **Diagnostic & Formal Counterexample Feedback Loop** (passing structural reasons and Stage 1 formal counterexamples into revision prompts).
4. Immutable revision history, Stage 2 revision invariant comparison display, Formal Proof Certificate viewer/download, DAG display/export, and explicit **Approval A (`spec_approval`)** in both GUI and CLI.
Add integration tests in `tests/integration/test_conversation_and_spec_approval.py`.

**Deliverables:**
- Updated `src/amca_agent/artifacts.py`, `src/amca_agent/cli.py`, `app.py`
- `tests/integration/test_conversation_and_spec_approval.py`

**Gate:** Human approves Preliminary Harness Setup UI, GUI/CLI conversation flow, formal proof display, and Approval A (`APPROVE TASK 4`).

---

## Task 5 — On-The-Fly Subworker HITL UI, Construction Planning, Approval B, and Runnable Project Scaffold

**Prompt:** Implement `src/amca_agent/builder.py` and integrate the **On-The-Fly Subworker HITL Provisioning Interface** and **Approval B (`construction_approval`)** into `app.py` and `src/amca_agent/cli.py`:
1. When AMCA proposes (or the user triggers) a Subworker during construction planning/execution, display the **On-The-Fly Subworker HITL Modal/Prompt** in GUI and CLI where the user approves or declines the Subworker and **inputs a dedicated Model & API Key for that Subworker** (isolated from the Primary Agent's key, or using a hardware-verified local model).
2. Enforce that project generation can only run when both `spec_approval` (with `PROVED` formal certificate) and `construction_approval` are valid and match the current YAML SHA-256 digest.
3. Generate a **real, standalone, runnable Python project** inside `artifacts/constructed_projects/<machine_id>-rev<NNN>/` with path-confinement checks, executable Python component modules containing explicit runtime pre/postcondition guards corresponding to $\{P_c\}\;c\;\{Q_c\}$, a working runner CLI, a real `unittest` suite, `README.md`, `machine.yaml`, `machine-dag.dot`, and `manifest.json`.
Add unmocked integration tests in `tests/integration/test_builder_scaffold.py` verifying On-The-Fly Subworker HITL key isolation, fallback when declined, and real project generation.

**Deliverables:**
- `src/amca_agent/builder.py`
- Updated `app.py` and `src/amca_agent/cli.py` for On-The-Fly Subworker HITL UI, Construction Plan review, and Approval B
- `tests/integration/test_builder_scaffold.py`

**Gate:** Human approves On-The-Fly Subworker HITL flow, real scaffold generation, and Approval B gate (`APPROVE TASK 5`).

---

## Task 6 — Stage 3 AST Formal Refinement Verification, real test execution, redacted audit logs, and ZIP packaging

**Prompt:** Extend `src/amca_agent/formal_verifier.py` with **Stage 3 (`verify_code_refinement`)** using real `ast.parse()` inspection of the generated Python files on disk to prove graph isomorphism ($G_{\text{code}} \cong G_{\text{yaml}}$) and verify runtime pre/postcondition guard calls in the generated AST (including negative tests where a mutated AST is rejected). Implement `src/amca_agent/packager.py` to:
1. Run Stage 3 Formal Refinement Verification (`FO-REF-01`, `FO-REF-02`), run `compileall`, and actually execute the generated project's `unittest` suite, updating `formal-proof-certificate.json` with real results.
2. Maintain an append-only, secret-redacted construction audit log (`construction-log.jsonl`) ensuring neither Primary Agent API keys nor Subworker API keys ever appear in logs.
3. Package the verified project, final `machine.yaml`, `formal-proof-certificate.json`, `machine-dag.dot`, verification report, user guide, and sanitized logs into a real `<machine_id>-rev<NNN>-handover.zip` archive.
Expose build verification and ZIP download/export in both `app.py` and `src/amca_agent/cli.py`, and add unmocked integration, AST-mutation, and multi-key secret-exclusion tests in `tests/integration/test_construction_and_zip.py`.

**Deliverables:**
- Stage 3 AST refinement checks in `src/amca_agent/formal_verifier.py`
- `src/amca_agent/packager.py`
- Updated `app.py` and `src/amca_agent/cli.py`
- `tests/integration/test_construction_and_zip.py`

**Gate:** Human reviews implementation evidence and approves transition to final verification (`APPROVE TASK 6`).

---

## Task 7 — Full verification, documentation-to-application consistency check against the 3 User Books, and handover

**Prompt:** Run the complete test suite (`unittest`, `AppTest`, hardware gate tests, 9Router & Combo token-limit failover tests, multi-key subworker HITL tests, formal verification & AST mutation tests, security scans, and `tools/validate_workflow.py`) in a clean environment. Perform an explicit **Documentation-to-Application Consistency Audit** against the three reference books (`help/USER-MANUAL.md` / `help/USER_MANUAL.md`, `help/USER-GUIDE.md` / `help/USER_GUIDE.md`, and `help/USER-TUTORIAL.md` / `help/USER_TUTORIAL.md`):
1. Verify that the application implements 100% of the minimum capabilities, commands, UI flows, and verification guarantees specified in those three books.
2. If the application includes additional capabilities, options, or behaviors that are consistent with the minimum baseline in the three books, **update all three books** (`USER-MANUAL.md`/`USER_MANUAL.md`, `USER-GUIDE.md`/`USER_GUIDE.md`, `USER-TUTORIAL.md`/`USER_TUTORIAL.md`) plus `README.md`, `CHANGELOG.md`, and `docs/14-agent-constructor-verification-and-handover.md` so they match the final built system 100%.

**Deliverables:**
- `docs/14-agent-constructor-verification-and-handover.md`
- Updated `README.md`, `CHANGELOG.md`, `docs/traceability-matrix.md`, and `help/*.md`
- Complete test and reproducibility evidence in `docs/evidence/`

**Gate:** Human accepts final refactoring handover (`APPROVE TASK 7`).
