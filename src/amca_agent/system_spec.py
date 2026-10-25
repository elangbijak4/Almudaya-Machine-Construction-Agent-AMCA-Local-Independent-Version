"""Parser, validator, and bidirectional adapter for amca/v1alpha1 (MachineSystem) and v1.0."""
from __future__ import annotations

import platform
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from yaml.tokens import AliasToken, AnchorToken

from amca.canonical import canonical_json
from amca.constructor import construct
from amca.errors import InputError, SpecificationError
from amca.models import CandidateGraph, Edge, MachineSpec, NodeSpec
from amca.registry import get_component
from amca.specification import MAX_SPEC_BYTES, _StrictSafeLoader, load_spec

IDENTIFIER_RE = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
SECRET_REF_RE = re.compile(r"^[A-Z][A-Z0-9_]{1,63}$")
MAX_CONFIG_BYTES = 16_384

COMPONENT_ALIASES: dict[str, str] = {
    "input_source": "input_source",
    "validate_text": "validate_text",
    "analysis_a": "analysis_a",
    "analysis_b": "analysis_b",
    "aggregate_results": "aggregate_results",
    "generate_report": "generate_report",
    "text.input": "input_source",
    "text.validate": "validate_text",
    "text.char_count": "analysis_a",
    "text.word_count": "analysis_b",
    "text.summarize": "aggregate_results",
    "report.assemble": "generate_report",
}

CANONICAL_TO_V1ALPHA1_ALIAS: dict[str, str] = {
    "input_source": "text.input",
    "validate_text": "text.validate",
    "analysis_a": "text.char_count",
    "analysis_b": "text.word_count",
    "aggregate_results": "text.summarize",
    "generate_report": "report.assemble",
}

COMPONENT_ROLES: dict[str, tuple[str, str]] = {
    "input_source": ("Input Reader", "Read raw text from runtime JSON payload."),
    "validate_text": ("Text Validator", "Ensure text is non-empty and normalized."),
    "analysis_a": ("Character Analyzer", "Count characters in validated text."),
    "analysis_b": ("Word Analyzer", "Count words in validated text."),
    "aggregate_results": ("Findings Summarizer", "Combine character and word counts into summary string."),
    "generate_report": ("Report Assembler", "Package summary string into report object."),
}


@dataclass(frozen=True)
class ServiceDeclaration:
    name: str
    kind: str
    secret_ref: str

    def as_dict(self) -> dict[str, str]:
        return {"name": self.name, "kind": self.kind, "secretRef": self.secret_ref}


@dataclass(frozen=True)
class AcceptanceCriterionSpec:
    id: str
    statement: str
    formal_goal: str

    def as_dict(self) -> dict[str, str]:
        return {"id": self.id, "statement": self.statement, "formalGoal": self.formal_goal}


@dataclass(frozen=True)
class MachineUnitSpec:
    id: str
    name: str
    role: str
    component_alias: str
    canonical_component: str
    config: dict[str, Any]
    inputs: tuple[dict[str, Any], ...]
    outputs: tuple[dict[str, Any], ...]
    services: tuple[ServiceDeclaration, ...]


@dataclass(frozen=True)
class MachineSystemSpec:
    api_version: str
    kind: str
    machine_id: str
    name: str
    revision: int
    lifecycle: str
    request: str
    acceptance_criteria: tuple[AcceptanceCriterionSpec, ...]
    machines: tuple[MachineUnitSpec, ...]
    connections: tuple[Edge, ...]
    builder_environment: dict[str, Any]
    target_environment: dict[str, Any]
    security_policy: dict[str, str]
    construction: dict[str, Any]
    assumptions: tuple[str, ...]
    limitations: tuple[str, ...]
    unresolved_questions: tuple[str, ...]

    def to_machine_spec_v1(self) -> MachineSpec:
        nodes = tuple(
            NodeSpec(id=m.id, component=m.canonical_component, config=dict(m.config))
            for m in self.machines
        )
        return MachineSpec(
            schema_version="1.0",
            machine_id=self.machine_id,
            nodes=nodes,
            edges=self.connections,
        )

    def to_candidate_graph(self) -> CandidateGraph:
        return construct(self.to_machine_spec_v1())

    def as_dict(self) -> dict[str, Any]:
        return {
            "apiVersion": self.api_version,
            "kind": self.kind,
            "metadata": {
                "id": self.machine_id,
                "name": self.name,
                "revision": self.revision,
                "lifecycle": self.lifecycle,
            },
            "intent": {
                "request": self.request,
                "acceptanceCriteria": [ac.as_dict() for ac in self.acceptance_criteria],
            },
            "machines": [
                {
                    "id": m.id,
                    "name": m.name,
                    "role": m.role,
                    "implementation": {
                        "language": "python",
                        "component": m.component_alias,
                        "version": "1",
                        "config": dict(m.config),
                    },
                    "inputs": [dict(p) for p in m.inputs],
                    "outputs": [dict(p) for p in m.outputs],
                    "services": [s.as_dict() for s in m.services],
                }
                for m in self.machines
            ],
            "connections": [
                {
                    "from": {"machine": e.source, "output": e.output},
                    "to": {"machine": e.target, "input": e.input},
                }
                for e in self.connections
            ],
            "environment": {
                "builderEnvironment": dict(self.builder_environment),
                "targetEnvironment": dict(self.target_environment),
            },
            "securityPolicy": dict(self.security_policy),
            "construction": dict(self.construction),
            "assumptions": list(self.assumptions),
            "limitations": list(self.limitations),
            "unresolvedQuestions": list(self.unresolved_questions),
        }


def resolve_component_alias(component_name: str, path: str = "$.machines.implementation.component") -> str:
    if type(component_name) is not str or component_name not in COMPONENT_ALIASES:
        raise SpecificationError(f"Unknown or disallowed component {component_name!r}", path=path)
    return COMPONENT_ALIASES[component_name]


def _parse_yaml_mapping(path_or_bytes: str | Path | bytes) -> dict[str, Any]:
    if isinstance(path_or_bytes, bytes):
        raw = path_or_bytes
    elif isinstance(path_or_bytes, str) and ("\n" in path_or_bytes or ":" in path_or_bytes):
        raw = path_or_bytes.encode("utf-8")
    else:
        try:
            raw = Path(path_or_bytes).read_bytes()
        except OSError as exc:
            raise InputError(f"Could not read specification: {exc.strerror or exc.__class__.__name__}") from None
    if len(raw) > MAX_SPEC_BYTES:
        raise SpecificationError("Specification exceeds 65,536 bytes", path="$")
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        raise InputError("Specification must be valid UTF-8", path="$") from None
    try:
        for token in yaml.scan(text, Loader=_StrictSafeLoader):
            if isinstance(token, (AnchorToken, AliasToken)):
                raise SpecificationError("YAML anchors and aliases are not supported", path="$")
        value = yaml.load(text, Loader=_StrictSafeLoader)
    except yaml.YAMLError as exc:
        raise InputError(f"Invalid YAML: {str(exc).splitlines()[0]}", path="$") from None
    if not isinstance(value, dict):
        raise SpecificationError("Specification root must be a mapping", path="$")
    return value


def validate_system_spec_mapping(mapping: dict[str, Any]) -> MachineSystemSpec:
    required_root = {
        "apiVersion",
        "kind",
        "metadata",
        "intent",
        "machines",
        "connections",
        "environment",
        "securityPolicy",
        "construction",
        "assumptions",
        "limitations",
        "unresolvedQuestions",
    }
    extra_root = set(mapping) - required_root
    missing_root = required_root - set(mapping)
    if missing_root:
        raise SpecificationError(f"Missing required root keys: {sorted(missing_root)}", path="$")
    if extra_root:
        raise SpecificationError(f"Unexpected root keys: {sorted(extra_root)}", path="$")
    if mapping.get("apiVersion") != "amca/v1alpha1":
        raise SpecificationError("apiVersion must be 'amca/v1alpha1'", path="$.apiVersion")
    if mapping.get("kind") != "MachineSystem":
        raise SpecificationError("kind must be 'MachineSystem'", path="$.kind")

    # Metadata
    meta = mapping["metadata"]
    if type(meta) is not dict or set(meta) != {"id", "name", "revision", "lifecycle"}:
        raise SpecificationError("metadata requires id, name, revision, lifecycle", path="$.metadata")
    machine_id = meta["id"]
    if type(machine_id) is not str or not IDENTIFIER_RE.match(machine_id):
        raise SpecificationError("metadata.id must match ^[a-z][a-z0-9_-]{0,63}$", path="$.metadata.id")
    name = meta["name"]
    if type(name) is not str or not (1 <= len(name.strip()) <= 128):
        raise SpecificationError("metadata.name must be a non-empty string (<=128 chars)", path="$.metadata.name")
    revision = meta["revision"]
    if type(revision) is not int or revision < 1:
        raise SpecificationError("metadata.revision must be an integer >= 1", path="$.metadata.revision")
    lifecycle = meta["lifecycle"]
    if lifecycle not in {"draft", "verified", "approved", "constructed"}:
        raise SpecificationError("metadata.lifecycle is invalid", path="$.metadata.lifecycle")

    # Intent
    intent = mapping["intent"]
    if type(intent) is not dict or set(intent) != {"request", "acceptanceCriteria"}:
        raise SpecificationError("intent requires request and acceptanceCriteria", path="$.intent")
    request_text = intent["request"]
    if type(request_text) is not str or not request_text.strip() or len(request_text) > 8000:
        raise SpecificationError("intent.request must be a non-empty string <= 8000 chars", path="$.intent.request")
    raw_ac = intent["acceptanceCriteria"]
    if type(raw_ac) is not list or not raw_ac:
        raise SpecificationError("intent.acceptanceCriteria must be a non-empty list", path="$.intent.acceptanceCriteria")
    criteria: list[AcceptanceCriterionSpec] = []
    for idx, item in enumerate(raw_ac):
        if type(item) is not dict or set(item) != {"id", "statement", "formalGoal"}:
            raise SpecificationError("acceptanceCriteria item requires id, statement, formalGoal", path=f"$.intent.acceptanceCriteria[{idx}]")
        if not all(type(item[k]) is str and item[k].strip() for k in ("id", "statement", "formalGoal")):
            raise SpecificationError("acceptanceCriteria fields must be non-empty strings", path=f"$.intent.acceptanceCriteria[{idx}]")
        criteria.append(AcceptanceCriterionSpec(id=item["id"], statement=item["statement"], formal_goal=item["formalGoal"]))

    # Security policy (fail-closed)
    sec = mapping["securityPolicy"]
    if type(sec) is not dict or set(sec) != {"networkPolicy", "operatingSystemCommands", "secretPolicy"}:
        raise SpecificationError("securityPolicy requires networkPolicy, operatingSystemCommands, secretPolicy", path="$.securityPolicy")
    if sec.get("networkPolicy") != "deny-by-default":
        raise SpecificationError("securityPolicy.networkPolicy must be 'deny-by-default'", path="$.securityPolicy.networkPolicy")
    if sec.get("operatingSystemCommands") != "deny":
        raise SpecificationError("securityPolicy.operatingSystemCommands must be 'deny'", path="$.securityPolicy.operatingSystemCommands")
    if sec.get("secretPolicy") != "references-only":
        raise SpecificationError("securityPolicy.secretPolicy must be 'references-only'", path="$.securityPolicy.secretPolicy")

    # Environment
    env = mapping["environment"]
    if type(env) is not dict or set(env) != {"builderEnvironment", "targetEnvironment"}:
        raise SpecificationError("environment requires builderEnvironment and targetEnvironment", path="$.environment")
    if type(env["builderEnvironment"]) is not dict or type(env["targetEnvironment"]) is not dict:
        raise SpecificationError("builderEnvironment and targetEnvironment must be objects", path="$.environment")

    # Construction
    con = mapping["construction"]
    if type(con) is not dict or set(con) != {"sdlc", "languages", "workerPlan"}:
        raise SpecificationError("construction requires sdlc, languages, workerPlan", path="$.construction")
    if type(con.get("sdlc")) is not dict or con["sdlc"].get("method") != "waterfall":
        raise SpecificationError("construction.sdlc.method must be 'waterfall'", path="$.construction.sdlc")
    if con.get("languages") != ["python"]:
        raise SpecificationError("construction.languages must be ['python']", path="$.construction.languages")
    wp = con.get("workerPlan")
    if type(wp) is not dict or type(wp.get("policy")) is not str or type(wp.get("useSubagents")) is not bool:
        raise SpecificationError("construction.workerPlan requires policy (str) and useSubagents (bool)", path="$.construction.workerPlan")

    # Machines
    raw_machines = mapping["machines"]
    if type(raw_machines) is not list or not (1 <= len(raw_machines) <= 64):
        raise SpecificationError("machines must be a list of 1 to 64 items", path="$.machines")
    seen_ids: set[str] = set()
    machines: list[MachineUnitSpec] = []
    for idx, m in enumerate(raw_machines):
        m_path = f"$.machines[{idx}]"
        if type(m) is not dict or set(m) != {"id", "name", "role", "implementation", "inputs", "outputs", "services"}:
            raise SpecificationError("machine requires id, name, role, implementation, inputs, outputs, services", path=m_path)
        mid = m["id"]
        if type(mid) is not str or not IDENTIFIER_RE.match(mid):
            raise SpecificationError("machine.id is invalid", path=f"{m_path}.id")
        if mid in seen_ids:
            raise SpecificationError(f"Duplicate machine id {mid!r}", path=f"{m_path}.id")
        seen_ids.add(mid)
        if type(m["name"]) is not str or not m["name"].strip() or type(m["role"]) is not str or not m["role"].strip():
            raise SpecificationError("machine.name and machine.role must be non-empty strings", path=m_path)
        impl = m["implementation"]
        if type(impl) is not dict or set(impl) != {"language", "component", "version", "config"}:
            raise SpecificationError("implementation requires language, component, version, config", path=f"{m_path}.implementation")
        if impl.get("language") != "python" or impl.get("version") != "1":
            raise SpecificationError("implementation requires language='python' and version='1'", path=f"{m_path}.implementation")
        comp_alias = impl["component"]
        canonical_comp = resolve_component_alias(comp_alias, path=f"{m_path}.implementation.component")
        comp_def = get_component(canonical_comp)
        cfg = impl["config"]
        comp_def.validate_config(cfg, f"{m_path}.implementation.config")
        if len(canonical_json(cfg)) > MAX_CONFIG_BYTES:
            raise SpecificationError("Component config exceeds 16,384 bytes", path=f"{m_path}.implementation.config")

        # Validate declared inputs/outputs against component registry contract
        raw_inputs = m["inputs"]
        raw_outputs = m["outputs"]
        if type(raw_inputs) is not list or type(raw_outputs) is not list:
            raise SpecificationError("inputs and outputs must be lists", path=m_path)
        declared_in = {}
        for p in raw_inputs:
            if type(p) is not dict or set(p) != {"name", "type", "required"} or p.get("required") is not True:
                raise SpecificationError("input port requires name, type, and required=true", path=f"{m_path}.inputs")
            declared_in[p["name"]] = p["type"]
        if declared_in != comp_def.input_ports:
            raise SpecificationError(
                f"Machine {mid!r} inputs {declared_in} do not match component {canonical_comp!r} contract {comp_def.input_ports}",
                path=f"{m_path}.inputs",
            )
        declared_out = {}
        for p in raw_outputs:
            if type(p) is not dict or set(p) != {"name", "type"}:
                raise SpecificationError("output port requires name and type", path=f"{m_path}.outputs")
            declared_out[p["name"]] = p["type"]
        if declared_out != comp_def.output_ports:
            raise SpecificationError(
                f"Machine {mid!r} outputs {declared_out} do not match component {canonical_comp!r} contract {comp_def.output_ports}",
                path=f"{m_path}.outputs",
            )

        # Services & secretRef validation
        raw_services = m["services"]
        if type(raw_services) is not list:
            raise SpecificationError("services must be a list", path=f"{m_path}.services")
        services: list[ServiceDeclaration] = []
        for s_idx, s in enumerate(raw_services):
            s_path = f"{m_path}.services[{s_idx}]"
            if type(s) is not dict or set(s) != {"name", "kind", "secretRef"}:
                raise SpecificationError("service requires name, kind, secretRef", path=s_path)
            secret_ref = s["secretRef"]
            if type(secret_ref) is not str or not SECRET_REF_RE.match(secret_ref):
                raise SpecificationError(
                    "secretRef must be an uppercase environment variable name matching ^[A-Z][A-Z0-9_]{1,63}$",
                    path=f"{s_path}.secretRef",
                )
            services.append(ServiceDeclaration(name=str(s["name"]), kind=str(s["kind"]), secret_ref=secret_ref))

        machines.append(
            MachineUnitSpec(
                id=mid,
                name=m["name"],
                role=m["role"],
                component_alias=comp_alias,
                canonical_component=canonical_comp,
                config=dict(cfg),
                inputs=tuple(dict(p) for p in raw_inputs),
                outputs=tuple(dict(p) for p in raw_outputs),
                services=tuple(services),
            )
        )

    # Connections
    raw_connections = mapping["connections"]
    if type(raw_connections) is not list or len(raw_connections) > 128:
        raise SpecificationError("connections must be a list of 0 to 128 items", path="$.connections")
    edges: list[Edge] = []
    for c_idx, conn in enumerate(raw_connections):
        c_path = f"$.connections[{c_idx}]"
        if type(conn) is not dict or set(conn) != {"from", "to"}:
            raise SpecificationError("connection requires 'from' and 'to'", path=c_path)
        src, dst = conn["from"], conn["to"]
        if type(src) is not dict or set(src) != {"machine", "output"} or type(dst) is not dict or set(dst) != {"machine", "input"}:
            raise SpecificationError("connection endpoints require machine and port names", path=c_path)
        if not all(type(v) is str and IDENTIFIER_RE.match(v) for v in (src["machine"], src["output"], dst["machine"], dst["input"])):
            raise SpecificationError("connection identifiers must match ^[a-z][a-z0-9_-]{0,63}$", path=c_path)
        edges.append(Edge(source=src["machine"], output=src["output"], target=dst["machine"], input=dst["input"]))

    # Assumptions, limitations, unresolvedQuestions
    for field_name in ("assumptions", "limitations", "unresolvedQuestions"):
        val = mapping[field_name]
        if type(val) is not list or not all(type(x) is str and x.strip() for x in val):
            raise SpecificationError(f"{field_name} must be a list of non-empty strings", path=f"$.{field_name}")

    return MachineSystemSpec(
        api_version="amca/v1alpha1",
        kind="MachineSystem",
        machine_id=machine_id,
        name=name,
        revision=revision,
        lifecycle=lifecycle,
        request=request_text,
        acceptance_criteria=tuple(criteria),
        machines=tuple(machines),
        connections=tuple(edges),
        builder_environment=dict(env["builderEnvironment"]),
        target_environment=dict(env["targetEnvironment"]),
        security_policy=dict(sec),
        construction=dict(con),
        assumptions=tuple(mapping["assumptions"]),
        limitations=tuple(mapping["limitations"]),
        unresolved_questions=tuple(mapping["unresolvedQuestions"]),
    )


def load_system_spec(path_or_bytes: str | Path | bytes) -> MachineSystemSpec:
    mapping = _parse_yaml_mapping(path_or_bytes)
    if mapping.get("apiVersion") == "amca/v1alpha1":
        return validate_system_spec_mapping(mapping)
    if mapping.get("schema_version") == "1.0":
        raw_bytes = (
            path_or_bytes
            if isinstance(path_or_bytes, bytes)
            else (
                path_or_bytes.encode("utf-8")
                if isinstance(path_or_bytes, str) and ("\n" in path_or_bytes or ":" in path_or_bytes)
                else Path(path_or_bytes).read_bytes()
            )
        )
        v1_spec = load_spec(raw_bytes)
        return v1_to_system_spec(v1_spec)
    raise SpecificationError("Unsupported specification format: expected apiVersion 'amca/v1alpha1' or schema_version '1.0'", path="$")


def load_any_spec_to_candidate(path_or_bytes: str | Path | bytes) -> tuple[CandidateGraph, MachineSystemSpec | None]:
    """Load either schema_version '1.0' or apiVersion 'amca/v1alpha1' and return (CandidateGraph, MachineSystemSpec)."""
    mapping = _parse_yaml_mapping(path_or_bytes)
    if mapping.get("apiVersion") == "amca/v1alpha1":
        sys_spec = validate_system_spec_mapping(mapping)
        return sys_spec.to_candidate_graph(), sys_spec
    raw_bytes = (
        path_or_bytes
        if isinstance(path_or_bytes, bytes)
        else (
            path_or_bytes.encode("utf-8")
            if isinstance(path_or_bytes, str) and ("\n" in path_or_bytes or ":" in path_or_bytes)
            else Path(path_or_bytes).read_bytes()
        )
    )
    v1_spec = load_spec(raw_bytes)
    return construct(v1_spec), v1_to_system_spec(v1_spec)


def v1_to_system_spec(
    v1_spec: MachineSpec,
    *,
    request: str = "Konstruksi sistem mesin dari spesifikasi AMCA v1.0.",
    revision: int = 1,
    lifecycle: str = "draft",
) -> MachineSystemSpec:
    machines: list[MachineUnitSpec] = []
    for node in v1_spec.nodes:
        comp_def = get_component(node.component)
        title, role = COMPONENT_ROLES.get(node.component, (node.id, f"Execute {node.component}"))
        alias = CANONICAL_TO_V1ALPHA1_ALIAS.get(node.component, node.component)
        inputs = tuple(
            {"name": port_name, "type": port_type, "required": True}
            for port_name, port_type in comp_def.input_ports.items()
        )
        outputs = tuple(
            {"name": port_name, "type": port_type}
            for port_name, port_type in comp_def.output_ports.items()
        )
        machines.append(
            MachineUnitSpec(
                id=node.id,
                name=title,
                role=role,
                component_alias=alias,
                canonical_component=node.component,
                config=dict(node.config),
                inputs=inputs,
                outputs=outputs,
                services=(),
            )
        )

    has_validate = any(n.component == "validate_text" for n in v1_spec.nodes)
    has_report = any(n.component == "generate_report" for n in v1_spec.nodes)
    criteria = []
    if has_validate:
        criteria.append(
            AcceptanceCriterionSpec(
                id="AC-SYS-1",
                statement="Teks kosong atau hanya spasi ditolak sebelum analisis.",
                formal_goal="non_empty_trimmed",
            )
        )
    if has_report:
        criteria.append(
            AcceptanceCriterionSpec(
                id="AC-SYS-2",
                statement="Teks valid menghasilkan ringkasan dan objek laporan akhir.",
                formal_goal="report_contains_summary",
            )
        )
    if not criteria:
        criteria.append(
            AcceptanceCriterionSpec(
                id="AC-SYS-1",
                statement="Mesin menghasilkan keluaran sesuai komponen terdaftar.",
                formal_goal="is_str",
            )
        )

    return MachineSystemSpec(
        api_version="amca/v1alpha1",
        kind="MachineSystem",
        machine_id=v1_spec.machine_id.replace("_", "-"),
        name=f"AMCA System {v1_spec.machine_id}",
        revision=revision,
        lifecycle=lifecycle,
        request=request,
        acceptance_criteria=tuple(criteria),
        machines=tuple(machines),
        connections=v1_spec.edges,
        builder_environment={
            "os": platform.system() or "unspecified",
            "python": ">=3.12,<3.13",
        },
        target_environment={
            "os": "any",
            "python": ">=3.12,<3.13",
        },
        security_policy={
            "networkPolicy": "deny-by-default",
            "operatingSystemCommands": "deny",
            "secretPolicy": "references-only",
        },
        construction={
            "sdlc": {"method": "waterfall"},
            "languages": ["python"],
            "workerPlan": {"policy": "minimize-cost", "useSubagents": False},
        },
        assumptions=("Input JSON runtime selalu berupa objek pemetaan dengan kunci string yang sesuai.",),
        limitations=("Eksekusi cabang DAG dijalankan secara sekuensial deterministik.",),
        unresolved_questions=(),
    )


def dump_system_spec_yaml(spec: MachineSystemSpec) -> str:
    return yaml.safe_dump(spec.as_dict(), sort_keys=False, allow_unicode=True)
