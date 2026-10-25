# Requirements Traceability Matrix

**Status:** P5/P6 baseline and CR-001/CR-002 constructor, harness, and 3-stage formal verification mapping completed.  
**Requirement baselines:** [docs/01-requirements-specification.md](01-requirements-specification.md), [docs/11-agent-web-extension-review.md](11-agent-web-extension-review.md), and [docs/12-agent-constructor-requirements.md](12-agent-constructor-requirements.md)

## 1. Core Baseline Requirements (`FR-01`–`FR-10`, `NFR-01`–`NFR-08`)

| Requirement | Design | Implemented source | Current test/evidence | Status |
|---|---|---|---|---|
| FR-01 | `docs/03-data-model-and-yaml-schemas.md` | `src/amca/specification.py`, `src/amca/models.py` | `tests/unit/test_specification.py`; `tests/unit/test_schema.py` | Implemented; P5 full suite passed (68/68; see docs/evidence/p5-unittest-rerun.txt) |
| FR-02 | `docs/03-data-model-and-yaml-schemas.md` | `src/amca/schema.py` | `tests/unit/test_schema.py`; `tests/unit/test_limits.py` | Implemented; P5 full suite passed (68/68; see docs/evidence/p5-unittest-rerun.txt) |
| FR-03 | `docs/02-system-architecture.md` | `src/amca/constructor.py` | `tests/unit/test_constructor.py`; `tests/e2e/test_cli_reference.py` | Implemented; P5 full suite passed (68/68; see docs/evidence/p5-unittest-rerun.txt) |
| FR-04 | `docs/03-data-model-and-yaml-schemas.md` | `src/amca/constructor.py`, `src/amca/models.py` | `tests/unit/test_constructor.py`; `tests/unit/test_verifier.py` | Implemented; P5 full suite passed (68/68; see docs/evidence/p5-unittest-rerun.txt) |
| FR-05 | `docs/04-verification-design.md` | `src/amca/verifier.py`, `src/amca/scheduler.py` | `tests/unit/test_verifier.py`; `tests/unit/test_scheduler.py` | Implemented; P5 full suite passed (68/68; see docs/evidence/p5-unittest-rerun.txt) |
| FR-06 | `docs/03-data-model-and-yaml-schemas.md`, `docs/04-verification-design.md` | `src/amca/registry.py`, `src/amca/verifier.py` | `tests/unit/test_registry.py`; `tests/unit/test_verifier.py` | Implemented; P5 full suite passed (68/68; see docs/evidence/p5-unittest-rerun.txt) |
| FR-07 | `docs/05-runtime-and-execution-design.md` | `src/amca/runtime.py`, `src/amca/registry.py`, `src/amca/scheduler.py` | `tests/integration/test_runtime_admission.py`; `tests/unit/test_scheduler.py` | Implemented; P5 full suite passed (68/68; see docs/evidence/p5-unittest-rerun.txt) |
| FR-08 | `docs/03-data-model-and-yaml-schemas.md`, `docs/04-verification-design.md` | `src/amca/models.py`, `src/amca/reporting.py` | `tests/unit/test_reporting.py`; `tests/integration/test_runtime_admission.py` | Implemented; P5 full suite passed (68/68; see docs/evidence/p5-unittest-rerun.txt) |
| FR-09 | `docs/03-data-model-and-yaml-schemas.md`, `docs/05-runtime-and-execution-design.md` | `src/amca/reporting.py`, `src/amca/canonical.py` | `tests/integration/test_evidence.py` | Implemented; P5 full suite passed (68/68; see docs/evidence/p5-unittest-rerun.txt) |
| FR-10 | `docs/04-verification-design.md`, `docs/05-runtime-and-execution-design.md` | `src/amca/runtime.py`, `src/amca/verifier.py` | `tests/integration/test_runtime_admission.py`; `tests/e2e/test_cli_reference.py` | Implemented; P5 full suite passed (68/68; see docs/evidence/p5-unittest-rerun.txt) |
| NFR-01 | `docs/02-system-architecture.md` | `src/amca/canonical.py`, `src/amca/scheduler.py`, `src/amca/reporting.py` | `tests/integration/test_evidence.py`; `tests/unit/test_canonical.py` | Implemented; P5 full suite passed (68/68; see docs/evidence/p5-unittest-rerun.txt) |
| NFR-02 | `docs/05-runtime-and-execution-design.md` | `src/amca/registry.py`, `src/amca/runtime.py`, `src/amca/specification.py` | `tests/security/test_untrusted_spec.py`; source review | P5 source scan/security tests passed; not a security certification |
| NFR-03 | `docs/04-verification-design.md` | `src/amca/models.py`, `src/amca/reporting.py` | `tests/unit/test_reporting.py`; `tests/unit/test_verifier.py` | Implemented; P5 full suite passed (68/68; see docs/evidence/p5-unittest-rerun.txt) |
| NFR-04 | `docs/06-implementation-plan.md`, `docs/07-test-and-validation-plan.md` | `requirements-dev.txt`, `src/amca/cli.py`, `README.md` | `docs/evidence/p5-static-and-reproducibility.txt`; `docs/evidence/p5-unittest-rerun.txt` | Clean venv reproduction passed with bundled CPython fallback |
| NFR-05 | `docs/02-system-architecture.md`, `docs/06-implementation-plan.md` | `src/amca/*.py` | `compileall`; test suite; code review | P5 compile and full suite passed |
| NFR-06 | `docs/03-data-model-and-yaml-schemas.md`, `docs/05-runtime-and-execution-design.md` | `src/amca/specification.py`, `src/amca/schema.py`, `src/amca/runtime.py` | `tests/unit/test_limits.py`; `tests/integration/test_runtime_admission.py` | Implemented; tested boundaries passed |
| NFR-07 | `docs/02-system-architecture.md`, `docs/06-implementation-plan.md` | `requirements-dev.txt`; `src/amca/*.py` | dependency/source review; `docs/evidence/p5-static-and-reproducibility.txt` | Clean-environment dependency and full-suite checks passed; no external services used |
| NFR-08 | `docs/04-verification-design.md`, `docs/05-runtime-and-execution-design.md` | `src/amca/errors.py`, `src/amca/cli.py`, `src/amca/reporting.py` | `tests/e2e/test_cli_reference.py`; `tests/unit/test_reporting.py` | Implemented; P5 full suite passed (68/68; see docs/evidence/p5-unittest-rerun.txt) |

## 2. CR-001 & CR-002 Extension Requirements (`CR-UI-01`–`CR-UI-09`, `AC-01`–`AC-23`)

| Requirement | Design | Implemented source | Current test/evidence | Status |
|---|---|---|---|---|
| CR-UI-01..09 | `docs/11-agent-web-extension-review.md` | `app.py`, `src/amca_agent/provider.py`, `src/amca_agent/graph.py`, `src/amca_agent/artifacts.py`, `src/amca_agent/cli.py` | `tests/unit/test_agent_provider.py`, `tests/integration/test_agent_cli.py`, `tests/integration/test_streamlit_app.py` | Implemented and verified |
| AC-01, AC-02 | `docs/13-agent-constructor-architecture.md` | `src/amca_agent/intent.py`, `src/amca_agent/cli.py`, `app.py` | `tests/unit/test_intent_and_approvals.py`, `tests/integration/test_conversation_and_spec_approval.py` | Implemented and verified |
| AC-03, AC-05, AC-07 | `docs/13-agent-constructor-architecture.md`, `schemas/machine-system-v1alpha1.schema.yaml` | `src/amca_agent/system_spec.py` | `tests/unit/test_system_spec.py` | Implemented and verified |
| AC-04, AC-16 | `docs/13-agent-constructor-architecture.md` | `src/amca_agent/provider.py`, `src/amca_agent/artifacts.py`, `src/amca_agent/cli.py`, `app.py` | `tests/integration/test_conversation_and_spec_approval.py`, `tests/integration/test_streamlit_app.py` | Implemented and verified |
| AC-06, AC-09 | `docs/13-agent-constructor-architecture.md` | `src/amca_agent/approvals.py`, `src/amca_agent/planner.py` | `tests/unit/test_intent_and_approvals.py` | Implemented and verified |
| AC-08, AC-10..14 | `docs/13-agent-constructor-architecture.md` | `src/amca_agent/builder.py`, `src/amca_agent/packager.py` | `tests/integration/test_builder_scaffold.py`, `tests/integration/test_construction_and_zip.py` | Implemented and verified |
| AC-15, AC-18 | `docs/13-agent-constructor-architecture.md` | `src/amca/*`, `src/amca_agent/*` | Full test suite + AST/mutation checks in `tests/unit/test_formal_verifier.py` | Implemented and verified |
| AC-17 | `docs/13-agent-constructor-architecture.md`, `schemas/formal-proof-certificate.schema.yaml` | `src/amca_agent/formal_verifier.py` | `tests/unit/test_formal_verifier.py`, `tests/integration/test_construction_and_zip.py` | Implemented and verified |
| AC-19, AC-20, AC-21, AC-22 | `docs/13-agent-constructor-architecture.md` | `src/amca_agent/hardware.py`, `src/amca_agent/harness.py`, `src/amca_agent/provider.py` | `tests/unit/test_hardware_and_harness.py` | Implemented and verified |
| AC-23 | `docs/14-agent-constructor-verification-and-handover.md` | `help/USER_MANUAL.md`, `help/USER_GUIDE.md`, `help/USER_TUTORIAL.md` | `tests/integration/test_construction_and_zip.py`, `docs/14-agent-constructor-verification-and-handover.md` | Implemented and verified |

P5 verification evidence is in `docs/09-verification-report.md` and `docs/evidence/`. CR-002 verification and handover evidence is in `docs/14-agent-constructor-verification-and-handover.md`.
