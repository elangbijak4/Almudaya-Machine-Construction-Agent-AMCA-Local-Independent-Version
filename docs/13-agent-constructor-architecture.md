# CR-002 System Architecture — Specialized Agent Harness, 3-Stage Formal Verifier, & Agent Constructor

**Status:** Approved & Implemented under **CR-002** (2026-10-25)  
**Edition:** Local Independent Version (`src/amca/` + `src/amca_agent/` + `app.py`)

---

## 1. Layered Architecture Overview

AMCA Local Independent Version is structured in two cleanly separated layers:
1. **Layer A — Authoritative Core (`src/amca/`)**: Preserves the `P0`–`P6` baseline (`specification.py`, `schema.py`, `registry.py`, `constructor.py`, `verifier.py`, `scheduler.py`, `runtime.py`, `cli.py`).
2. **Layer B — Specialized Agent Harness, 3-Stage Formal Verifier, & Constructor (`src/amca_agent/` & `app.py`)**:
   - `hardware.py`: Real OS hardware inspection (`GlobalMemoryStatusEx` / `/proc/meminfo`, `shutil.disk_usage`, CPU cores/arch, GPU/VRAM) and fail-closed Local Model Download Gate (`ELIGIBLE` vs `REFUSED_INSUFFICIENT_HARDWARE`).
   - `provider.py` & `harness.py`: Model-agnostic Agent Harness supporting 12 provider types (`Gemini`, `xAI (Grok)`, `OpenAI`, `Anthropic`, `Custom OpenAI-Compatible`, `9Router` including 9Router Combos, `Ollama`, `LM Studio`, `OpenCode`, `Local Model`, `AMCA Combo`, and `Offline Deterministic`), live model auto-discovery, `SessionCredentialVault` (volatile in-memory API key isolation for Primary Agent, Combo Tiers, and Subworkers), `FallbackComboRouter` (automatic context compaction and multi-tier failover on token-limit/quota exhaustion), and On-The-Fly Subworker HITL state management.
   - `intent.py`: Opening greeting (*“Mesin/agent apakah yang Anda ingin buat?”*) and scope classification (`in_scope`, `needs_clarification`, `out_of_scope`).
   - `system_spec.py`: Parser, validator, component alias resolver, and bidirectional adapter for `apiVersion: amca/v1alpha1` (`kind: MachineSystem`) and `schema_version: "1.0"`.
   - `formal_verifier.py`: 3-Stage Compositional Formal Verification Engine:
     - **Stage 1 (`verify_formal_spec`)**: `FO-TOP-01` (Reachability), `FO-CON-01` (Church-Rosser Confluence), `FO-HOA-01` (Hoare Pre/Postcondition Entailment $\{P_c\}\;c\;\{Q_c\}$), `FO-GOAL-01` (Goal Entailment), `FO-SEC-01` (Taint Non-Interference).
     - **Stage 2 (`verify_revision_invariants`)**: `FO-EVO-01` (Invariant preservation across revisions).
     - **Stage 3 (`verify_code_refinement`)**: `FO-REF-01` (AST Graph Isomorphism $G_{\text{code}} \cong G_{\text{yaml}}$ via `ast.parse()`) and `FO-REF-02` (Runtime contract guard presence).
   - `approvals.py` & `planner.py`: Two-stage cryptographic approval records (`spec_approval`, `subworker_hitl_approval`, `construction_approval`) and Waterfall SDLC + cost-minimizing worker planner.
   - `builder.py` & `packager.py`: Bounded standalone Python project generator (`artifacts/constructed_projects/<machine_id>-rev<NNN>/`), Stage 3 AST verifier, real `compileall` and `unittest` runner, redacted `construction-log.jsonl` writer, and reproducible `<machine_id>-rev<NNN>-handover.zip` packager.
