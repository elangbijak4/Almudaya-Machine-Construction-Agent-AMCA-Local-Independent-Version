# Proposed Machine Specification Model, Agent Harness, & Formal Contracts

Status: **reconciled specification, harness/hardware, and formal proof contracts**. This model bridges the existing `schema_version: "1.0"` runtime contract with the new `apiVersion: amca/v1alpha1` (`kind: MachineSystem`) constructor contract, the **Specialized Agent Harness & Hardware Inspection contracts**, and the mathematical contract calculus for `formal_verifier.py`.

> **Anti-Mocking Rule for All Contracts:**  
> `hardware.py`, `harness.py`, `system_spec.py`, and `formal_verifier.py` must compute every hardware check, provider dispatch, validation result, Hoare entailment check, reachability path, confluence proof, revision invariant comparison, and AST isomorphism check dynamically from real OS metrics, data structures, and files on disk.

## 1. Specialized Agent Harness & Hardware Inspection Contracts

### 1.1 Model Binding & Multi-Provider Harness (`ModelBinding`)
Both the **Primary AMCA Agent** (configured in the Preliminary Setup UI) and any **Subworker** (configured in the On-The-Fly HITL UI) use a unified `ModelBinding` structure whose API key is held **only in session memory** and never serialized to disk:

- **Supported Provider Types (`provider_type`)**:
  1. `gemini` — Google Gemini REST API (`generateContent`)
  2. `xai` — xAI Grok REST API (`/v1/chat/completions`)
  3. `openai` — OpenAI REST API (`/v1/chat/completions`)
  4. `anthropic` — Anthropic Messages API (`/v1/messages`)
  5. `openai_compatible` — Any custom OpenAI-compatible endpoint (`base_url`, `model_id`, `api_key` in memory)
  6. `nine_router` (`9router`) — Local or remote **9Router** proxy (`http://127.0.0.1:20128/v1` by default); auto-discovers both individual routed models and **9Router Combo aliases** (e.g., `premium-coding`, `free-combo`) via `GET /v1/models` and delegates requests or fallback chains through 9Router's `/v1/chat/completions` endpoint
  7. `ollama` — Local Ollama runtime (`http://127.0.0.1:11434` by default); auto-discovers installed models via `GET /api/tags`, gates any new `POST /api/pull` download or heavy model load through `HardwareEligibilityReport` (`hardware.py`), and executes via `/api/chat` or `/v1/chat/completions`
  8. `lm_studio` — Local LM Studio server (`http://127.0.0.1:1234/v1` by default); auto-discovers loaded/available GGUF models via `GET /v1/models`, verifies available RAM/VRAM via `hardware.py`, and executes via `/v1/chat/completions`
  9. `opencode` — Local OpenCode runtime/bridge (`http://127.0.0.1:4096` HTTP server or `opencode models` / `opencode run --format json` CLI bridge); auto-discovers models configured inside the user's OpenCode installation and routes Primary Agent or Subworker prompts through OpenCode
  10. `local_model` — Direct local GGUF/model file download on laptop (requires passing `HardwareEligibilityReport` with `status == "ELIGIBLE"` and explicit download/load approval)
  11. `amca_combo` — Native AMCA **Combo Fallback Chain** (9Router-style ordered `Tier 1 -> Tier 2 -> ... -> Tier N` list of `ModelBinding` items with automatic failover on token-limit overflow, `finish_reason == "length"`, `HTTP 429` rate limit, or quota exhaustion)
  12. `offline_deterministic` — Built-in rule/registry synthesizer requiring no API key or model download

Sanitized persisted metadata (stored in session/construction records without credentials):
```json
{
  "agent_role": "amca_primary | subworker:spec_auditor | subworker:test_reviewer",
  "provider_type": "gemini | xai | openai | anthropic | openai_compatible | nine_router | ollama | lm_studio | opencode | local_model | amca_combo | offline_deterministic",
  "model_id": "premium-coding-combo",
  "base_url": "http://127.0.0.1:20128/v1",
  "credential_source": "session_memory_distinct_key",
  "hardware_check_id": null,
  "combo_tiers": [
    {"tier": 1, "provider_type": "gemini", "model_id": "gemini-2.5-pro"},
    {"tier": 2, "provider_type": "nine_router", "model_id": "free-combo"},
    {"tier": 3, "provider_type": "ollama", "model_id": "qwen2.5-coder:7b"},
    {"tier": 4, "provider_type": "offline_deterministic", "model_id": "builtin-v1"}
  ]
}
```

### 1.1b Native AMCA Combo & Token-Limit Fallback Chain Contract (`FallbackComboChain` & `FallbackTransitionEvent`)
Inspired by **9Router Combos**, AMCA allows the user to configure named **Combo Fallback Chains** inside AMCA (or use 9Router's own Combos directly). Whenever a tier encounters a token limit or quota barrier, AMCA executes deterministic failover:

- **Trigger Conditions (`trigger_reason`)**:
  1. `token_limit_exceeded` — Prompt + completion exceeds the model's context window (`context_length_exceeded`, `max_tokens` overflow, or TPM/TPD token rate limit).
  2. `output_truncated_length` — Model response terminates prematurely with `finish_reason == "length"`, producing incomplete YAML/code.
  3. `rate_limit_429` — Provider returns `HTTP 429 Too Many Requests` or `RESOURCE_EXHAUSTED`.
  4. `quota_or_credit_exhausted` — Provider returns `insufficient_quota` or billing/credit limit reached.
  5. `upstream_unavailable` — Provider returns `HTTP 500/502/503/504` or connection timeout.
- **Token-Limit Context Compaction & Handover Procedure**:
  - When `token_limit_exceeded` or `output_truncated_length` occurs on Tier $k$, AMCA constructs a **Compacted Continuity Payload** (retaining the latest verified/draft `amca/v1alpha1` YAML, the latest structural/formal counterexamples, and the active user instruction while pruning verbose older conversational turns) before invoking Tier $k+1$.
- **Sanitized Audit Record (`FallbackTransitionEvent`)**:
```json
{
  "event_type": "fallback_transition",
  "timestamp": "2026-10-25T21:12:00Z",
  "agent_role": "amca_primary",
  "combo_id": "researcher-resilient-combo",
  "from_tier": 1,
  "from_provider": "gemini",
  "from_model": "gemini-2.5-pro",
  "to_tier": 2,
  "to_provider": "nine_router",
  "to_model": "free-combo",
  "trigger_reason": "token_limit_exceeded",
  "context_compacted": true
}
```

### 1.2 Laptop Hardware Inspection & Local Model Gate Contract (`HardwareEligibilityReport`)
Before downloading or activating any `local_model`, `src/amca_agent/hardware.py` queries the host OS in real time and compares against the model catalog profile:

```json
{
  "inspection_timestamp": "2026-10-25T14:40:00Z",
  "host_os": "Windows-11-10.0.22631-SP0",
  "cpu_arch": "AMD64",
  "cpu_logical_cores": 8,
  "ram_total_mb": 16384,
  "ram_available_mb": 6120,
  "disk_free_mb": 45200,
  "gpu_detected": false,
  "gpu_vram_mb": 0,
  "requested_local_model": {
    "model_id": "qwen2.5-coder-7b-instruct-q4_k_m.gguf",
    "download_size_mb": 4680,
    "min_ram_available_mb": 6144,
    "min_disk_free_mb": 7000,
    "requires_gpu": false
  },
  "status": "REFUSED_INSUFFICIENT_HARDWARE",
  "reasons": [
    "Available RAM (6120 MB) is below the model minimum requirement (6144 MB)."
  ]
}
```
- If `status == "REFUSED_INSUFFICIENT_HARDWARE"`, the download button/command is strictly blocked (`fail-closed`).
- If `status == "ELIGIBLE"`, the user may approve downloading the model file into `artifacts/local_models/` (bounded, hash/size-checked) or connecting to a local inference server.

### 1.3 On-The-Fly Subworker HITL Approval Record (`subworker-approval.json`)
When AMCA proposes a Subworker, execution pauses for user approval and on-the-fly API key provisioning:
```json
{
  "approval_type": "subworker_hitl_approval",
  "session_id": "uuid",
  "subworker_id": "subworker-formal-auditor-01",
  "role": "independent_test_and_proof_auditor",
  "task_description": "Audit edge cases and generate adversarial test inputs for constructed DAG.",
  "rationale": "Separates test generation from primary spec authoring using a distinct model.",
  "decision": "APPROVED",
  "model_binding": {
    "provider_type": "openai_compatible",
    "model_id": "deepseek-chat",
    "credential_isolated_from_primary": true
  },
  "approved_by": "user",
  "approved_at": "2026-10-25T14:45:00Z"
}
```

## 2. Unified component registry & Hoare formal contracts ($\{P_c\}\;c\;\{Q_c\}$)

Every `machines[].implementation.component` in `amca/v1alpha1` resolves to a registered component in the AMCA allowlist. Each component carries both **typed port contracts** and **formal Hoare pre/postcondition predicates** used by `formal_verifier.py` to algorithmically evaluate compositional Verification Conditions ($\text{VC}(u \to v): Q_u(\text{out}) \supseteq P_v(\text{in})$):

| Canonical v1.0 ID | v1alpha1 Alias | Input Ports & Formal Preconditions $P_c$ | Output Ports & Formal Postconditions $Q_c$ | Pure / Side-Effect Free |
|---|---|---|---|---|
| `input_source` | `text.input` | **Config**: `input_key` (`id`)<br/>**Pre**: $\text{env\_has\_nonempty\_str}(\text{input\_key})$ | `text: string`<br/>**Post**: $\{\text{is\_str}, \text{non\_empty\_raw}\}$ | Yes |
| `validate_text` | `text.validate` | `text: string`<br/>**Pre**: $\{\text{is\_str}\}$ | `text: string`<br/>**Post**: $\{\text{is\_str}, \text{non\_empty\_trimmed}, \text{len\_ge\_1}\}$ | Yes |
| `analysis_a` | `text.char_count` | `text: string`<br/>**Pre**: $\{\text{is\_str}, \text{non\_empty\_trimmed}\}$ | `finding: object`<br/>**Post**: $\{\text{is\_obj}, \text{has\_nonneg\_int:character\_count}\}$ | Yes |
| `analysis_b` | `text.word_count` | `text: string`<br/>**Pre**: $\{\text{is\_str}, \text{non\_empty\_trimmed}\}$ | `finding: object`<br/>**Post**: $\{\text{is\_obj}, \text{has\_nonneg\_int:word\_count}\}$ | Yes |
| `aggregate_results` | `text.summarize` | `finding_a: object` ($\{\text{is\_obj}, \text{has\_nonneg\_int:character\_count}\}$)<br/>`finding_b: object` ($\{\text{is\_obj}, \text{has\_nonneg\_int:word\_count}\}$) | `summary: string`<br/>**Post**: $\{\text{is\_str}, \text{formatted\_metrics\_summary}\}$ | Yes |
| `generate_report` | `report.assemble` | `summary: string`<br/>**Pre**: $\{\text{is\_str}, \text{formatted\_metrics\_summary}\}$ | `report: object`<br/>**Post**: $\{\text{is\_obj}, \text{report\_contains\_summary}\}$ | Yes |

## 3. Canonical `amca/v1alpha1` (`MachineSystem`) YAML format

```yaml
apiVersion: amca/v1alpha1
kind: MachineSystem
metadata:
  id: reference-text-analysis
  name: Reference Text Analysis System
  revision: 1
  lifecycle: draft
intent:
  request: >-
    Terima teks masukan, validasi agar tidak kosong, hitung jumlah karakter
    dan kata secara terpisah, gabungkan ringkasannya, lalu hasilkan laporan.
  acceptanceCriteria:
    - id: AC-SYS-1
      statement: Teks kosong atau hanya spasi ditolak sebelum analisis.
      formalGoal: non_empty_trimmed
    - id: AC-SYS-2
      statement: Teks valid menghasilkan ringkasan jumlah karakter dan kata serta objek laporan.
      formalGoal: report_contains_summary
machines:
  - id: input
    name: Input Reader
    role: Read raw text from runtime JSON payload.
    implementation:
      language: python
      component: text.input
      version: "1"
      config:
        input_key: text
    inputs: []
    outputs:
      - name: text
        type: string
    services: []
  - id: validate
    name: Text Validator
    role: Ensure text is non-empty and normalized.
    implementation:
      language: python
      component: text.validate
      version: "1"
      config: {}
    inputs:
      - name: text
        type: string
        required: true
    outputs:
      - name: text
        type: string
    services: []
  - id: analysis_a
    name: Character Analyzer
    role: Count characters in validated text.
    implementation:
      language: python
      component: text.char_count
      version: "1"
      config: {}
    inputs:
      - name: text
        type: string
        required: true
    outputs:
      - name: finding
        type: object
    services: []
  - id: analysis_b
    name: Word Analyzer
    role: Count words in validated text.
    implementation:
      language: python
      component: text.word_count
      version: "1"
      config: {}
    inputs:
      - name: text
        type: string
        required: true
    outputs:
      - name: finding
        type: object
    services: []
  - id: aggregate
    name: Result Aggregator
    role: Combine character and word findings into a summary string.
    implementation:
      language: python
      component: text.summarize
      version: "1"
      config: {}
    inputs:
      - name: finding_a
        type: object
        required: true
      - name: finding_b
        type: object
        required: true
    outputs:
      - name: summary
        type: string
    services:
      - provider: llm
        purpose: Optional semantic enrichment (disabled by default in offline runtime)
        required: false
        secretRef: AMCA_LLM_API_KEY
        model: null
  - id: report
    name: Report Builder
    role: Wrap aggregated summary into a final report object.
    implementation:
      language: python
      component: report.assemble
      version: "1"
      config: {}
    inputs:
      - name: summary
        type: string
        required: true
    outputs:
      - name: report
        type: object
    services: []
connections:
  - from: input.text
    to: validate.text
  - from: validate.text
    to: analysis_a.text
  - from: validate.text
    to: analysis_b.text
  - from: analysis_a.finding
    to: aggregate.finding_a
  - from: analysis_b.finding
    to: aggregate.finding_b
  - from: aggregate.summary
    to: report.summary
construction:
  sdlc:
    method: waterfall
    rationale: Stage-gated construction with explicit spec, formal proof, and build approvals.
  workers:
    policy: minimize-cost
    useSubagents: false
    rationale: Single-agent template construction is deterministic and lowest cost; subworkers require on-the-fly HITL approval and dedicated model/key binding.
  languages: [python]
  dependencies:
    - name: PyYAML
      constraint: ">=6.0,<7.0"
      purpose: Safe declarative specification parsing
  builderEnvironment:
    capture: runtime-detected
    values: {}
  targetEnvironment:
    os: any
    python: ">=3.12,<3.13"
    hardware: cpu-standard
security:
  networkPolicy: deny-by-default
  operatingSystemCommands: deny
  secretPolicy: references-only
assumptions:
  - Input payload is supplied as UTF-8 JSON with key 'text'.
limitations:
  - Branch execution (analysis_a, analysis_b) runs sequentially in deterministic topological order, proved confluent by Church-Rosser property.
unresolvedQuestions: []
```
