"""Built-in Core Components of the AMCA Component Library."""
from __future__ import annotations

from typing import Any

from .contracts import (
    ContractViolationError,
    _enforce_postconditions,
    _enforce_preconditions,
)


def run_input_source(inputs: dict[str, Any], config: dict[str, Any], raw_inputs: dict[str, Any]) -> dict[str, Any]:
    _enforce_preconditions("input_source", inputs)
    key = str(config.get("input_key", "text"))
    if key not in raw_inputs:
        raise ContractViolationError(f"Missing required input key: {key!r}")
    val = raw_inputs[key]
    if not isinstance(val, str):
        raise ContractViolationError(f"Input {key!r} must be a string")
    outputs = {"text": val}
    _enforce_postconditions("input_source", outputs)
    return outputs


def run_validate_text(inputs: dict[str, Any], config: dict[str, Any], raw_inputs: dict[str, Any]) -> dict[str, Any]:
    _enforce_preconditions("validate_text", inputs)
    cleaned = str(inputs["text"]).strip()
    if not cleaned:
        raise ContractViolationError("Input text cannot be empty or whitespace-only.")
    outputs = {"text": cleaned}
    _enforce_postconditions("validate_text", outputs)
    return outputs


def run_analysis_a(inputs: dict[str, Any], config: dict[str, Any], raw_inputs: dict[str, Any]) -> dict[str, Any]:
    _enforce_preconditions("analysis_a", inputs)
    text = str(inputs["text"])
    outputs = {"finding": f"characters={len(text)}"}
    _enforce_postconditions("analysis_a", outputs)
    return outputs


def run_analysis_b(inputs: dict[str, Any], config: dict[str, Any], raw_inputs: dict[str, Any]) -> dict[str, Any]:
    _enforce_preconditions("analysis_b", inputs)
    text = str(inputs["text"])
    outputs = {"finding": f"words={len(text.split())}"}
    _enforce_postconditions("analysis_b", outputs)
    return outputs


def run_aggregate_results(inputs: dict[str, Any], config: dict[str, Any], raw_inputs: dict[str, Any]) -> dict[str, Any]:
    _enforce_preconditions("aggregate_results", inputs)
    fa = inputs["finding_a"]
    fb = inputs["finding_b"]
    if isinstance(fa, dict):
        fa = f"characters={fa.get('character_count', 0)}"
    if isinstance(fb, dict):
        fb = f"words={fb.get('word_count', 0)}"
    summary = f"{fa}; {fb}"
    outputs = {"summary": summary}
    _enforce_postconditions("aggregate_results", outputs)
    return outputs


def run_generate_report(inputs: dict[str, Any], config: dict[str, Any], raw_inputs: dict[str, Any]) -> dict[str, Any]:
    _enforce_preconditions("generate_report", inputs)
    outputs = {"report": {"summary": str(inputs["summary"])}}
    _enforce_postconditions("generate_report", outputs)
    return outputs


BUILTIN_DISPATCH = {
    "input_source": run_input_source,
    "validate_text": run_validate_text,
    "analysis_a": run_analysis_a,
    "analysis_b": run_analysis_b,
    "aggregate_results": run_aggregate_results,
    "generate_report": run_generate_report,
}
