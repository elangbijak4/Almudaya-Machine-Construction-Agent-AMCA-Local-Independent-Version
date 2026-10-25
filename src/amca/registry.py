"""Immutable, project-owned allowlist of trusted built-in components."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .errors import ComponentFailure, SpecificationError
from .models import JsonValue

ComponentFunction = Callable[[dict[str, JsonValue], dict[str, JsonValue]], dict[str, JsonValue]]
REGISTRY_VERSION = "amca-builtin-v1"
EMPTY_CONFIG = frozenset()


@dataclass(frozen=True)
class ComponentDefinition:
    component_id: str
    input_ports: dict[str, str]
    output_ports: dict[str, str]
    config_keys: frozenset[str]
    function: ComponentFunction

    def validate_config(self, config: Any, path: str) -> None:
        if type(config) is not dict:
            raise SpecificationError("Component config must be an object", path=path)
        if self.component_id == "input_source":
            if set(config) != {"input_key"}:
                raise SpecificationError("input_source config requires only input_key", path=path)
            value = config["input_key"]
            if type(value) is not str or not value or not _identifier(value):
                raise SpecificationError("input_key must be a valid identifier", path=f"{path}.input_key")
        elif not self.config_keys:
            if config:
                raise SpecificationError("This component requires an empty config object", path=path)
        else:
            extra = set(config) - set(self.config_keys)
            if extra:
                raise SpecificationError(
                    f"Component {self.component_id!r} does not allow config keys {sorted(extra)}",
                    path=path,
                )
            for k, v in config.items():
                if type(v) not in (str, int, float, bool):
                    raise SpecificationError(
                        f"Config key {k!r} must have a scalar value",
                        path=f"{path}.{k}",
                    )


def _identifier(value: str) -> bool:
    return bool(value) and value[0].islower() and value[0].isascii() and all(
        (char.isascii() and (char.islower() or char.isdigit() or char in "_-") )
        for char in value
    ) and len(value) <= 64


def _input_source(config: dict[str, JsonValue], inputs: dict[str, JsonValue]) -> dict[str, JsonValue]:
    key = config["input_key"]
    if key not in inputs:
        raise ComponentFailure(f"Required external input {key!r} is missing")
    value = inputs[key]
    if type(value) is not str:
        raise ComponentFailure(f"External input {key!r} must be a string")
    return {"text": value}


def _validate_text(config: dict[str, JsonValue], inputs: dict[str, JsonValue]) -> dict[str, JsonValue]:
    text = inputs["text"]
    if type(text) is not str or not text.strip():
        raise ComponentFailure("Text must not be empty or whitespace-only")
    return {"text": text.strip()}


def _analysis_a(config: dict[str, JsonValue], inputs: dict[str, JsonValue]) -> dict[str, JsonValue]:
    text = inputs["text"]
    if type(text) is not str:
        raise ComponentFailure("Analysis A requires text")
    return {"finding": {"character_count": len(text)}}


def _analysis_b(config: dict[str, JsonValue], inputs: dict[str, JsonValue]) -> dict[str, JsonValue]:
    text = inputs["text"]
    if type(text) is not str:
        raise ComponentFailure("Analysis B requires text")
    return {"finding": {"word_count": len(text.split())}}


def _aggregate(config: dict[str, JsonValue], inputs: dict[str, JsonValue]) -> dict[str, JsonValue]:
    finding_a, finding_b = inputs["finding_a"], inputs["finding_b"]
    if type(finding_a) is not dict or type(finding_b) is not dict:
        raise ComponentFailure("Both analysis findings must be objects")
    characters = finding_a.get("character_count")
    words = finding_b.get("word_count")
    if type(characters) is not int or characters < 0 or type(words) is not int or words < 0:
        raise ComponentFailure("Analysis findings must contain nonnegative integer counts")
    return {"summary": f"characters={characters}; words={words}"}


def _generate_report(config: dict[str, JsonValue], inputs: dict[str, JsonValue]) -> dict[str, JsonValue]:
    summary = inputs["summary"]
    if type(summary) is not str:
        raise ComponentFailure("Report generation requires a summary string")
    return {"report": {"summary": summary}}


BUILTIN_COMPONENTS: dict[str, ComponentDefinition] = {
    "input_source": ComponentDefinition("input_source", {}, {"text": "string"}, frozenset({"input_key"}), _input_source),
    "validate_text": ComponentDefinition("validate_text", {"text": "string"}, {"text": "string"}, EMPTY_CONFIG, _validate_text),
    "analysis_a": ComponentDefinition("analysis_a", {"text": "string"}, {"finding": "object"}, EMPTY_CONFIG, _analysis_a),
    "analysis_b": ComponentDefinition("analysis_b", {"text": "string"}, {"finding": "object"}, EMPTY_CONFIG, _analysis_b),
    "aggregate_results": ComponentDefinition("aggregate_results", {"finding_a": "object", "finding_b": "object"}, {"summary": "string"}, EMPTY_CONFIG, _aggregate),
    "generate_report": ComponentDefinition("generate_report", {"summary": "string"}, {"report": "object"}, EMPTY_CONFIG, _generate_report),
}
BUILTIN_COMPONENT_IDS: tuple[str, ...] = tuple(sorted(BUILTIN_COMPONENTS))

_COMPONENTS: dict[str, ComponentDefinition] = dict(BUILTIN_COMPONENTS)


def is_builtin_component(component_id: str) -> bool:
    return component_id in BUILTIN_COMPONENTS


def register_component_definition(definition: ComponentDefinition) -> None:
    if not isinstance(definition, ComponentDefinition):
        raise SpecificationError("definition must be a ComponentDefinition", path="$.registry")
    cid = definition.component_id
    if type(cid) is not str or not _identifier(cid):
        raise SpecificationError(f"Invalid component_id {cid!r}; must match [a-z][a-z0-9_-]{{0,63}}", path="$.registry.component_id")
    if cid in BUILTIN_COMPONENTS:
        raise SpecificationError(f"Cannot overwrite immutable built-in component {cid!r}", path="$.registry.component_id")
    if not definition.output_ports:
        raise SpecificationError(f"Component {cid!r} must declare at least one output port", path="$.registry.output_ports")
    for port_map_name, port_map in (("input_ports", definition.input_ports), ("output_ports", definition.output_ports)):
        for p_name, p_type in port_map.items():
            if type(p_name) is not str or not _identifier(p_name):
                raise SpecificationError(f"Invalid port name {p_name!r} in {port_map_name}", path=f"$.registry.{port_map_name}")
            if p_type not in {"string", "object"}:
                raise SpecificationError(f"Port {p_name!r} type must be 'string' or 'object'", path=f"$.registry.{port_map_name}.{p_name}")
    _COMPONENTS[cid] = definition


def unregister_custom_component_definition(component_id: str) -> None:
    if component_id in BUILTIN_COMPONENTS:
        raise SpecificationError(f"Cannot remove immutable built-in component {component_id!r}", path="$.registry.component_id")
    _COMPONENTS.pop(component_id, None)


def clear_custom_component_definitions() -> None:
    _COMPONENTS.clear()
    _COMPONENTS.update(BUILTIN_COMPONENTS)


def get_component(component_id: str) -> ComponentDefinition:
    try:
        return _COMPONENTS[component_id]
    except (KeyError, TypeError):
        raise SpecificationError(f"Unknown component {component_id!r}", path="$.nodes.component") from None


def component_ids() -> tuple[str, ...]:
    return tuple(sorted(_COMPONENTS))


def custom_component_ids() -> tuple[str, ...]:
    return tuple(sorted(cid for cid in _COMPONENTS if cid not in BUILTIN_COMPONENTS))


def registry_profile() -> str:
    return REGISTRY_VERSION
