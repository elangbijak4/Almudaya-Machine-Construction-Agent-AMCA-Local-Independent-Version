# Vision and Scope

## Product statement

AMCA is a **Specialized Agent Harness, Compositional Formal Verifier, and Agent Constructor**. Its purpose is to act as a model-agnostic orchestrator that can be powered by any cloud AI model (by freely swapping API keys and endpoints), connected to **9Router** (using individual models or 9Router Combo fallback chains), connected to local AI runtimes (**Ollama**, **LM Studio**, **OpenCode**), or powered by a local AI model downloaded to the user's laptop (gated by an automatic hardware specification inspection). It includes a **Native Combo & Token-Limit Fallback Chain Protocol** (with a 9Router-style Combo configuration UI) that automatically fails over across backup models when a model reaches its token limit or quota, can provision specialized **Subworkers** on the fly with their own independent models/Combos and API keys via a Human-in-the-Loop (HITL) interface, and turns a user's natural-language goal into a formally proved, standalone runnable Python project (`kind: MachineSystem`).

## Real implementation mandate (zero mocking of core capabilities)

Every capability in AMCA must be **genuinely realized in executable code**:
- **No Mocked Hardware Inspection**: `hardware.py` queries real OS memory (`GlobalMemoryStatusEx` / `/proc/meminfo`), real disk free space (`shutil.disk_usage`), real CPU cores/architecture, and real GPU/VRAM availability to decide whether a local model is safe to download.
- **No Mocked Agent Harness or Subworker Dispatch**: `harness.py` and `provider.py` perform real HTTP requests for cloud providers (`Gemini`, `xAI (Grok)`, `OpenAI`, `Anthropic`, `Custom OpenAI-Compatible`), real local model endpoint calls/downloads when hardware-verified, and real independent credential routing for Subworkers.
- **No Mocked/Hardcoded Formal Verification**: Formal proof certificates are dynamically computed from graph-theoretic traversal, symbolic Hoare predicate deduction, revision comparison, and `ast.parse()` inspection of generated Python files.
- **No Mocked/Canned Construction**: Project construction writes real, standalone Python packages, real CLI entrypoints, and real `unittest` suites to disk that execute real data transformations when invoked.

## Shared vocabulary

| Term | Meaning |
| --- | --- |
| **AMCA (Specialized Agent Harness)** | The model-agnostic constructor, structural/formal verifier, and subworker orchestrator application (`src/amca/` core + `src/amca_agent/` harness/UI layer). |
| **Primary Agent Binding** | The replaceable AI model configuration powering AMCA itself (Cloud API with session API key, Hardware-Verified Local Model, or Offline Synthesizer), configured in the **Preliminary Setup Interface** and hot-swappable at any time. |
| **Hardware Capability Inspector** | Module (`src/amca_agent/hardware.py`) that inspects the laptop's real RAM, disk space, CPU, and GPU/VRAM before allowing any local model download, refusing downloads when hardware is insufficient. |
| **Subworker / Subagent** | A delegated specialized worker (e.g., `spec_reviewer`, `code_builder`, `test_auditor`) spawned only after **On-The-Fly Human-in-the-Loop (HITL) Approval** and configured with its own independent model and API key. |
| **Machine / agent** | A task-focused computational unit in the target system with a declared role, registered component implementation, typed inputs/outputs, and formal Hoare pre/postcondition predicates $\{P_c\} \; c \; \{Q_c\}$. |
| **Machine system** | One or more machines connected by declared data contracts (`connections`); may be a single machine, linear pipeline, or branching DAG. |
| **Constructor specification (`v1alpha1`)** | Versioned `apiVersion: amca/v1alpha1` (`kind: MachineSystem`) YAML describing intent, acceptance criteria, machines, connections, environment, security policy, construction/worker plan, assumptions, limitations, and unresolved questions. |
| **Multi-stage formal verification** | Mathematical verification across 3 stages: (1) **Spec-Level Proofs**, (2) **Evolution-Level Proofs**, and (3) **Refinement-Level AST Isomorphism Proofs**. |
| **Spec approval (Approval A)** | Explicit user record locking a specific `verified` and formally `PROVED` `v1alpha1` revision and its canonical SHA-256 digest as immutable. |
| **Construction approval (Approval B)** | Explicit user record authorizing the SDLC plan, any HITL-approved Subworkers, and the bounded output directory for project generation. |

## User journey

1. **Step 0 — Preliminary Harness Setup Interface (GUI & CLI Onboarding)**:
   - Before entering the constructor chat, the user configures AMCA's **Primary Agent Brain**:
     - **Option A — Cloud API Model**: Choose any provider (`Gemini`, `xAI (Grok)`, `OpenAI`, `Anthropic`, or `Custom OpenAI-Compatible`), enter the Model ID/Base URL, and supply the API Key (held strictly in session memory; hot-swappable anytime).
     - **Option B — Local Downloaded Model (Laptop)**: Select a local model profile. AMCA immediately runs the **Hardware Capability Inspector** to check RAM, free disk space, CPU, and GPU/VRAM. If the laptop meets the model's requirements, AMCA enables the download/local binding upon user confirmation; if not, AMCA **refuses the download** and displays the exact hardware deficit.
     - **Option C — Offline Deterministic Mode**: Proceed using AMCA's built-in deterministic synthesizer without an LLM.
2. **Step 1 — Intake & Scope Classification**:
   - GUI (`app.py`) and CLI (`python -m amca_agent.cli`) greet the user with *“Mesin/agent apakah yang Anda ingin buat?”*
   - AMCA classifies the request (`in_scope_machine_engineering`, `ambiguous_needs_clarification`, or `out_of_scope`). Out-of-scope requests receive a clear boundary explanation without invoking YAML generation or construction.
3. **Step 2 — Drafting & Multi-Stage Formal Verification Iteration**:
   - AMCA drafts an `amca/v1alpha1` `MachineSystem` YAML using its currently bound Primary Agent model and explicitly populates `assumptions`, `limitations`, and `unresolvedQuestions`.
   - Every draft revision is checked by the structural verifier (`verify_candidate`) and **Stage 1 & Stage 2 Formal Verification** (`formal_verifier.py`). Structural errors and formal counterexamples are automatically fed back into subsequent revision prompts.
4. **Step 3 — Approval A (Specification & Proof Certificate Approval)**:
   - Once a revision is structurally `verified` and formally `PROVED`, the user reviews the YAML, formal proof certificate, and DAG visualization, then locks that revision via **Approval A (`spec_approval`)**.
5. **Step 4 — Construction Planning & On-The-Fly HITL Subworker Provisioning**:
   - AMCA prepares the Waterfall SDLC plan and evaluates whether specialized **Subworkers** are proposed.
   - **On-The-Fly Subworker HITL Interface**: Whenever AMCA proposes (or the user requests) spawning a Subworker (e.g., an independent *Formal Spec Auditor* or *Test Verification Worker*), an **on-the-fly HITL dialog/prompt** appears:
     - Displays the Subworker's role, task scope, and cost/benefit rationale.
     - Asks for explicit user approval to spawn the Subworker.
     - Prompts the user **on the fly** to select the Subworker's provider/model (Cloud API or hardware-verified Local Model) and **enter a separate API Key dedicated to that Subworker** (kept strictly in session memory). If declined, AMCA executes the task using the Primary Agent alone.
6. **Step 5 — Approval B (Construction Scope Approval)**:
   - User reviews and explicitly approves the final construction plan, active worker bindings, and target workspace (`construction_approval`).
7. **Step 6 — Bounded Construction, Stage 3 Formal Refinement Verification, and Handover**:
   - AMCA (and any approved Subworkers operating within bounded permissions) generates the standalone Python project inside `artifacts/constructed_projects/<machine_id>-rev<N>/`, runs **Stage 3 Formal Refinement Verification** ($G_{\text{code}} \cong G_{\text{yaml}}$) plus actual `compileall` and `unittest` execution, records redacted append-only logs, and packages the reproducible **ZIP handover archive**.
