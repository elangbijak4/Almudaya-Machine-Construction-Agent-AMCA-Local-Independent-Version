# Target Architecture

## 1. Module architecture & real algorithmic responsibilities

To preserve `src/amca/` (`P0`–`P6` core) while evolving `src/amca_agent/` and `app.py` into a **Specialized Agent Harness**, every module below must be implemented with **100% real, unmocked production logic**:

### Layer A — Authoritative Core (`src/amca/` — preserved intact)
- `src/amca/specification.py` & `src/amca/schema.py` — Strict UTF-8/YAML parsing (`_StrictSafeLoader`, max 64 KiB) and `schema_version: "1.0"` validation.
- `src/amca/registry.py` — Immutable component allowlist (`input_source`, `validate_text`, `analysis_a`, `analysis_b`, `aggregate_results`, `generate_report`).
- `src/amca/constructor.py` — Deterministic `CandidateGraph` normalization and SHA-256 digesting.
- `src/amca/verifier.py` — Independent 10-check structural/interface/acyclicity verifier (`verify_candidate`).
- `src/amca/scheduler.py` & `src/amca/runtime.py` — Lexicographic topological scheduler and fail-closed in-process execution engine.
- `src/amca/cli.py` — Baseline CLI (`validate`, `verify`, `run`, `report`).

### Layer B — Specialized Agent Harness, Hardware Inspector, Formal Verifier, & Constructor (`src/amca_agent/` & `app.py`)
1. **Laptop Hardware Capability Inspector & Local Model Gate (`src/amca_agent/hardware.py`)**
   - Queries the laptop's real hardware specifications using standard OS/Python interfaces (`ctypes` `GlobalMemoryStatusEx` on Windows / `/proc/meminfo` on Linux / `vm_stat` on macOS for total and available RAM; `shutil.disk_usage` for free disk space; `os.cpu_count()` & `platform` for CPU cores/architecture; optional GPU/VRAM detection).
   - Evaluates a catalog of local downloadable models (GGUF / Ollama profiles) with declared minimum RAM, free disk, and optional GPU requirements.
   - **Fail-Closed Hardware Gate (`evaluate_local_model_eligibility`)**:
     - Returns `ELIGIBLE` only when available RAM, free disk space, and hardware capabilities meet or exceed the model's thresholds, unlocking local model download/execution upon user approval.
     - Returns `REFUSED_INSUFFICIENT_HARDWARE` and **strictly blocks downloading** whenever the laptop's specifications are insufficient, reporting the exact deficit (e.g., required vs available MB of RAM/disk).
2. **Specialized Agent Harness, 9Router Bridge, Local Runtime Connectors (`Ollama`, `LM Studio`, `OpenCode`), Native Combo Fallback Router, & Subworker Credential Router (`src/amca_agent/harness.py` & `src/amca_agent/provider.py`)**
   - Implements the **model-agnostic Agent Harness** managing isolated in-memory `ModelBinding` and `FallbackComboChain` instances for:
     - **Primary AMCA Agent (`amca_primary`)**: Configured in the **Preliminary Setup & Combo Configuration Interface** (GUI & CLI onboarding) and hot-swappable at any time across Cloud APIs (`Gemini`, `xAI (Grok)`, `OpenAI`, `Anthropic`, `Custom OpenAI-Compatible Endpoint`), **9Router Bridge (`nine_router` at `http://127.0.0.1:20128/v1`)**, **Local AI Runtimes (`Ollama`, `LM Studio`, `OpenCode`) with live model auto-discovery**, **Native AMCA Combo Fallback Chains (`amca_combo`)**, `Hardware-Verified Local Model`, or `Offline Deterministic Synthesizer`.
     - **9Router & Local Runtime Auto-Discovery Bridges (`9Router`, `Ollama`, `LM Studio`, `OpenCode`)**:
       - **9Router Connector (`nine_router`)**: Probes `http://127.0.0.1:20128/v1/models` (with optional 9Router API key) to discover both individual models and **9Router Combo aliases** (e.g., `premium-coding`, `free-combo`), allowing AMCA to either delegate fallback routing directly to a 9Router Combo or embed 9Router models as tiers inside an AMCA Combo chain.
       - **Ollama Connector (`ollama`)**: Probes `http://127.0.0.1:11434/api/tags` to list installed models, checks `hardware.py` before pulling any new model (`/api/pull`) or activating large models, and dispatches chat completions.
       - **LM Studio Connector (`lm_studio`)**: Probes `http://127.0.0.1:1234/v1/models` to list models available in LM Studio, validates laptop RAM/VRAM eligibility via `hardware.py`, and dispatches via `/v1/chat/completions`.
       - **OpenCode Connector (`opencode`)**: Probes the local OpenCode server (`http://127.0.0.1:4096`) or CLI (`opencode models` / `opencode run --format json`) to list and invoke models already configured in the user's OpenCode environment.
     - **Native AMCA Combo & Token-Limit Fallback Chain Protocol (`FallbackComboRouter`)**:
       - Provides a **9Router-style Combo Configuration UI** in `app.py` and CLI commands in `amca_agent.cli` where users chain ordered model tiers (`Tier 1 -> Tier 2 -> Tier 3 ...`), each with its own provider, model ID, and independent in-memory API key.
       - Automatically intercepts **Token Limit Exceeded** (`context_length_exceeded`, `finish_reason == "length"` truncation, TPM/TPD limit), **Quota / Rate-Limit Exhaustion** (`HTTP 429`, `RESOURCE_EXHAUSTED`, `insufficient_quota`), and **Upstream 5xx/Timeout** errors, compacts the prompt context if triggered by token limits, records a sanitized `FallbackTransitionEvent`, and seamlessly fails over to the next tier in the Combo chain.
     - **Independent Subworkers (`subworker:<id>`)**: When AMCA proposes creating a Subworker, triggers the **On-The-Fly Human-in-the-Loop (HITL) Provisioning Interface** where the user approves/declines the Subworker, selects its provider/model or Combo chain (any Cloud API key, any **9Router** model/Combo, any model inside `Ollama` / `LM Studio` / `OpenCode`, an `amca_combo` fallback chain, or a hardware-verified Local Model), and **inputs a separate API Key/binding dedicated to that Subworker**.
   - Holds all API keys strictly in a volatile in-memory store (`SessionCredentialVault`), never writing any key to YAML, session files, logs, or ZIP archives.
3. **Intake & Intent Classifier (`src/amca_agent/intent.py`)**
   - Greets the user with *“Mesin/agent apakah yang Anda ingin buat?”*
   - Evaluates incoming requests to classify prompts into `in_scope`, `needs_clarification`, or `out_of_scope`. Rejects unrelated requests before any YAML generation or construction.
4. **v1alpha1 System Schema & Adapter (`src/amca_agent/system_spec.py`)**
   - Parses and validates `apiVersion: amca/v1alpha1` (`kind: MachineSystem`), resolves component aliases (`text.input`, `text.validate`, `text.char_count`, `text.word_count`, `text.summarize`, `report.assemble`), and compiles the system into a `CandidateGraph` for `verify_candidate`.
5. **Multi-Stage Formal Verification Engine (`src/amca_agent/formal_verifier.py`)**
   - Executes **genuine mathematical and AST-level proof algorithms** across 3 lifecycle stages and emits **`formal-proof-certificate.json`**:
     - **Stage 1 — Spec-Level Formal Verifier (`verify_formal_spec`)**: Proves source-to-sink reachability (`FO-TOP-01`), schedule confluence (`FO-CON-01`), Hoare pre/postcondition entailment $Q_u \supseteq P_v$ (`FO-HOA-01`), acceptance goal entailment (`FO-GOAL-01`), and security/taint non-interference (`FO-SEC-01`).
     - **Stage 2 — Evolution-Level Invariant Verifier (`verify_revision_invariants`)**: Proves whether security invariants and I/O contracts are preserved across revisions (`rev-N` $\to$ `rev-(N+1)`).
     - **Stage 3 — Refinement-Level AST/Graph Isomorphism Verifier (`verify_code_refinement`)**: Parses generated Python files on disk via `ast.parse()` to prove graph isomorphism ($G_{\text{code}} \cong G_{\text{yaml}}$) and runtime pre/postcondition guard presence.
6. **Immutable Revision & Multi-Gate Approval Service (`src/amca_agent/approvals.py`)**
   - Manages monotonic YAML revisions and persisted approval records:
     - **Approval A (`spec_approval`)**: Locks a structurally `verified` and formally `PROVED` revision by SHA-256 digest.
     - **Subworker HITL Approval (`subworker_hitl_approval`)**: Records on-the-fly user approval and sanitized model metadata (excluding the API key) whenever a Subworker is provisioned.
     - **Approval B (`construction_approval`)**: Authorizes the SDLC plan, active worker bindings, and destination directory.
7. **Planner, Bounded Builder, & Packager (`src/amca_agent/planner.py`, `builder.py`, `packager.py`)**
   - Generates the standalone runnable Python project in `artifacts/constructed_projects/<machine_id>-rev<NNN>/`, runs Stage 3 AST isomorphism checks + `compileall` + generated `unittest` suite, writes redacted `construction-log.jsonl`, and packages `<machine_id>-rev<NNN>-handover.zip`.

## 2. Control flow

```mermaid
flowchart TD
  S0["Step 0: Preliminary Harness Setup UI<br/>(Select Cloud API Key / Custom Endpoint / Local Model)"] --> S0B{"Local Model Selected?"}
  S0B -->|Yes| HW["Hardware Capability Inspector (hardware.py)<br/>Check RAM, Free Disk, CPU, GPU/VRAM"]
  HW -->|Insufficient Specs| HWR["REFUSED: Block Download & Show Hardware Deficit"]
  HWR --> S0
  HW -->|Specs Eligible + User Approves| S1["Bind Local Model to Primary Agent"]
  S0B -->|Cloud API Key / Offline| S1B["Bind Cloud API Key (In-Memory) / Offline Mode"]
  S1 --> A["Step 1: 'Mesin/agent apakah yang Anda ingin buat?'"]
  S1B --> A
  A --> B["Intent & Scope Classifier (intent.py)"]
  B -->|Out of scope| C["Explain AMCA machine-engineering scope; stop"]
  B -->|In scope| E["Draft / Revise amca/v1alpha1 YAML via Primary Agent Harness"]
  E --> F["1. Structural Verifier (verifier.py)<br/>2. Stage 1 & 2 Formal Verifier (formal_verifier.py)"]
  F -->|Rejected or REFUTED| G["Attach structural reasons + formal counterexamples; revise"]
  G --> E
  F -->|Verified + PROVED| H["Display YAML, Formal Proof Certificate, and DAG"]
  H --> I{"Approval A: User approves Spec + Formal Proof Certificate?"}
  I -->|No / Revise| E
  I -->|Yes (spec_approval)| K["Generate Waterfall SDLC & Worker Plan (planner.py)"]
  K --> SW{"Subworker Proposed / Requested?"}
  SW -->|Yes| HITL["On-The-Fly Subworker HITL UI:<br/>User Approves Subworker & Inputs Separate Subworker Model + API Key"]
  HITL -->|Approved with Separate Key/Model| L
  HITL -->|Declined: Fallback to Primary Agent| L
  SW -->|No (Primary Agent Only)| L{"Approval B: User approves Construction Plan & Destination?"}
  L -->|Yes (construction_approval)| M["Generate Runnable Project in artifacts/constructed_projects/ (builder.py)"]
  M --> N["Run Stage 3 AST Isomorphism (G_code ≅ G_yaml) + compileall + Generated Project unittest"]
  N --> O["Write Redacted Audit Log & Package Real Handover ZIP (packager.py)"]
```

## 3. Strict testing & anti-mocking boundaries

- **Zero Mocking of Internal Services**: No test in `tests/` may mock `hardware`, `harness`, `load_spec`, `validate_system_spec`, `verify_candidate`, `verify_formal_spec`, `verify_revision_invariants`, `verify_code_refinement`, `approvals`, `planner`, `builder`, or `packager`.
- **Hardware Gate & Multi-Key Verification**: Tests must verify real OS hardware inspection, verify that models exceeding available RAM/disk are deterministically refused (`REFUSED_INSUFFICIENT_HARDWARE`), and verify that Primary Agent and Subworker API keys are routed independently in memory and never written to disk or ZIP archives.
