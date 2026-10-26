"""Runtime Hoare Precondition and Postcondition Guards for the AMCA Component Library."""
from __future__ import annotations

from typing import Any


class ContractViolationError(ValueError):
    """Raised when a runtime Hoare precondition or postcondition is violated."""


COMPONENT_CONTRACTS: dict[str, dict[str, dict[str, tuple[str, ...]]]] = {}


def register_contract(
    component_id: str,
    *,
    preconditions: dict[str, list[str] | tuple[str, ...]] | None = None,
    postconditions: dict[str, list[str] | tuple[str, ...]] | None = None,
) -> None:
    """Register runtime Hoare precondition and postcondition metadata for a component."""
    COMPONENT_CONTRACTS[component_id] = {
        "preconditions": {str(k): tuple(str(x) for x in v) for k, v in (preconditions or {}).items()},
        "postconditions": {str(k): tuple(str(x) for x in v) for k, v in (postconditions or {}).items()},
    }


def _enforce_preconditions(component_id: str, inputs: dict[str, Any]) -> None:
    if component_id in {"validate_text", "analysis_a", "analysis_b"}:
        val = inputs.get("text")
        if not isinstance(val, str):
            raise ContractViolationError(f"{component_id}: input 'text' must be a string")
        if component_id in {"analysis_a", "analysis_b"} and not val.strip():
            raise ContractViolationError(f"{component_id}: precondition NonEmptyTrimmed(text) violated")
    elif component_id == "aggregate_results":
        for port in ("finding_a", "finding_b"):
            val = inputs.get(port)
            if isinstance(val, str):
                if not val.strip():
                    raise ContractViolationError(f"{component_id}: precondition ValidMetric({port}) violated")
            elif isinstance(val, dict):
                if not val:
                    raise ContractViolationError(f"{component_id}: precondition ValidMetric({port}) violated")
            else:
                raise ContractViolationError(f"{component_id}: precondition ValidMetric({port}) violated")
    elif component_id == "generate_report":
        val = inputs.get("summary")
        if not isinstance(val, str) or not val.strip():
            raise ContractViolationError(f"{component_id}: precondition AggregatedSummary(summary) violated")
    elif component_id != "input_source":
        if not inputs:
            raise ContractViolationError(f"{component_id}: missing required inputs")
        for p_name, p_val in inputs.items():
            if p_val is None:
                raise ContractViolationError(f"{component_id}: input {p_name!r} cannot be None")
            if isinstance(p_val, str) and not p_val.strip():
                raise ContractViolationError(f"{component_id}: precondition NonEmpty({p_name}) violated")


def _enforce_postconditions(component_id: str, outputs: dict[str, Any]) -> None:
    if component_id == "input_source":
        if "text" not in outputs or not isinstance(outputs["text"], str):
            raise ContractViolationError("input_source: postcondition TypeString(text) violated")
    elif component_id == "validate_text":
        val = outputs.get("text")
        if not isinstance(val, str) or not val.strip():
            raise ContractViolationError("validate_text: postcondition NonEmptyTrimmed(text) violated")
    elif component_id in {"analysis_a", "analysis_b"}:
        val = outputs.get("finding")
        if not isinstance(val, str) or "=" not in val:
            raise ContractViolationError(f"{component_id}: postcondition metric format violated")
    elif component_id == "aggregate_results":
        val = outputs.get("summary")
        if not isinstance(val, str) or ";" not in val:
            raise ContractViolationError("aggregate_results: postcondition AggregatedSummary violated")
    elif component_id == "generate_report":
        val = outputs.get("report")
        if not isinstance(val, dict) or "summary" not in val:
            raise ContractViolationError("generate_report: postcondition CompleteReport(report) violated")
    else:
        if not isinstance(outputs, dict) or not outputs:
            raise ContractViolationError(f"{component_id}: postcondition non-empty outputs violated")
        for p_name, p_val in outputs.items():
            if p_val is None:
                raise ContractViolationError(f"{component_id}: output {p_name!r} cannot be None")
            if isinstance(p_val, str) and not p_val.strip():
                raise ContractViolationError(f"{component_id}: postcondition NonEmpty({p_name}) violated")


enforce_preconditions = _enforce_preconditions
enforce_postconditions = _enforce_postconditions
