# AMCA Agent Constructor Refactoring Scaffold

Status: **aligned planning scaffold (Specialized Agent Harness + Hardware-Gated Local Models + On-The-Fly Subworker HITL + Multi-Stage Formal Verification + Strict Anti-Mocking)**.

## Repository baseline (audit facts)

- **Core baseline (`src/amca/`)**: Completed Waterfall phases `P0`–`P6` (`approved` in `workflow/gate-records.yaml`, 69/69 tests passing). Implements strict `schema_version: "1.0"` YAML loading, deterministic `CandidateGraph` construction, 10-check structural/interface verification, and sequential allowlisted execution over 6 built-in components.
- **Extension baseline (`src/amca_agent/` & `app.py` — `CR-001`)**: Implements optional Streamlit GUI and interactive CLI (`amca-agent`), basic provider adapters (Gemini, xAI/Grok, OpenAI), Graphviz `.dot` export, and local session/run artifacts (77/77 total tests passing in retest evidence).
- **Version control note**: The workspace currently operates as a local directory without `.git` metadata. Recovery checkpoints and audit trails rely on deterministic artifact snapshots and SHA-256 digests.

## AMCA as a Specialized Agent Harness (Model-Agnostic, Local-Hardware-Aware, & Multi-Key Subworkers)

AMCA is architected as a **Specialized Agent Harness**:
1. **Preliminary Harness Setup Interface (GUI & CLI Onboarding)**:
   - Before starting machine construction, an explicit setup screen/wizard lets the user configure the **Primary AMCA Agent's brain**:
     - **Any Cloud API Model**: Switch freely among `Gemini`, `xAI (Grok)`, `OpenAI`, `Anthropic`, or any **Custom OpenAI-Compatible Endpoint** (OpenRouter, DeepSeek, Groq, vLLM, etc.) by entering/swapping the API Key, Base URL, and Model ID in session memory.
     - **Local Downloaded Models with Hardware Inspection Gate**: Users can opt to download/use a local AI model on their laptop. Before any download is permitted, AMCA runs a **real-time Hardware Capability Inspector (`src/amca_agent/hardware.py`)** checking actual system RAM (total & available), free disk space, CPU cores, and GPU/VRAM. **If the laptop's specs meet the model's requirements**, the download/local runtime is allowed upon user confirmation; **if the laptop's specs are insufficient, the download is strictly refused (`REFUSED_INSUFFICIENT_HARDWARE`)** with a clear diagnostic report.
     - **Hot-Swapping**: The user can swap the Primary Agent's model and API Key at any time during a session.
2. **On-The-Fly Human-in-the-Loop (HITL) Interface for Subworkers with Independent API Keys**:
   - Whenever AMCA proposes spawning a **Subworker / Subagent** (e.g., for specification critique, scaffold generation, or test auditing), an **on-the-fly HITL provisioning interface** immediately appears in the GUI or CLI.
   - The user can approve or decline the Subworker. If approved, the user configures the Subworker's own model and **inputs a dedicated API Key for that Subworker on the fly** (which can come from a completely different AI provider/account than the Primary AMCA Agent, or use a hardware-verified local model).

## Strict Anti-Mocking & Real Implementation Mandate

> **MANDATORY RULE ACROSS ALL TASKS:**  
> The AI agent executing this refactoring is **strictly forbidden** from completing any feature, module, hardware inspector, formal verifier check, subworker harness, builder step, or test requirement by creating mocks, stubs, dummy returns, `TODO`/`pass` placeholders, or hardcoded responses.
> - **100% Real Production Logic**: Every module (`hardware.py`, `harness.py`, `intent.py`, `system_spec.py`, `formal_verifier.py`, `approvals.py`, `planner.py`, `builder.py`, `packager.py`, `provider.py`, `cli.py`, `app.py`) must execute real OS hardware queries, real HTTP/local-model dispatch, real symbolic deduction, real `ast.parse()` code inspection, real file generation on disk, real test execution on the generated project, and real ZIP archive creation.
> - **No Mocking the System Under Test (SUT)**: Tests must run against the real implementation and real filesystem artifacts, including mutation tests.

## Read in this order

1. [`MASTER_PROMPT.md`](MASTER_PROMPT.md) — operating rules, agent-harness & subworker HITL rules, hardware gate rules, strict anti-mocking mandate, and task protocol.
2. [`VISION_AND_SCOPE.md`](VISION_AND_SCOPE.md) — product intent, specialized agent harness vocabulary, preliminary & on-the-fly UI flows, multi-stage formal verification, and approval gates.
3. [`SPECIFICATION_MODEL.md`](SPECIFICATION_MODEL.md) — `amca/v1alpha1` (`MachineSystem`) YAML contract, harness & subworker records, hardware inspection records, Hoare contracts, and `formal-proof-certificate.json`.
4. [`TARGET_ARCHITECTURE.md`](TARGET_ARCHITECTURE.md) — module architecture (`hardware.py`, `harness.py`, `formal_verifier.py`, etc.), control flows, and trust boundaries.
5. [`EXECUTION_PLAN.md`](EXECUTION_PLAN.md) — ordered task prompts (`Task 0` through `Task 7`), deliverables, and human approval gates.
6. [`ACCEPTANCE_CRITERIA.md`](ACCEPTANCE_CRITERIA.md) — measurable acceptance criteria (`AC-01`–`AC-21`) and quantitative safety/hardware thresholds.
7. [`DECISIONS_AND_OPEN_QUESTIONS.md`](DECISIONS_AND_OPEN_QUESTIONS.md) — architectural decisions (`D-01`–`D-18`) and concrete baseline resolutions.

## Proposed end-state flow

**Preliminary Harness Setup (Select Cloud API Key or Hardware-Verified Local Model)** → Greeting (*“Mesin/agent apakah yang Anda ingin buat?”*) → Scope & intent classification → Draft `amca/v1alpha1` YAML → Structural verification + **Stage 1 & 2 Formal Verification** → **Approval A (Spec + Formal Proof Certificate)** → SDLC & Subworker proposal → **On-The-Fly HITL Subworker Approval & Separate API Key Input (if Subworker used)** → **Approval B (Construction Scope)** → Bounded project generation in `artifacts/constructed_projects/` → **Stage 3 Formal Refinement (AST/Graph Isomorphism)** + actual test execution → Reviewable artifacts and sanitized **ZIP handover**.
