"""Custom Component Authoring, Registration, Catalog & Prompt-Boundary System for AMCA Local Independent Version."""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any

from amca.errors import ComponentFailure, SpecificationError
from amca.models import JsonValue
from amca.registry import (
    BUILTIN_COMPONENT_IDS,
    BUILTIN_COMPONENTS,
    ComponentDefinition,
    clear_custom_component_definitions,
    component_ids,
    get_component,
    is_builtin_component,
    register_component_definition,
    unregister_custom_component_definition,
)
from amca_agent.formal_verifier import HOARE_CONTRACTS, HoareComponentContract
from amca_agent.system_spec import (
    CANONICAL_TO_V1ALPHA1_ALIAS,
    COMPONENT_ALIASES,
    COMPONENT_ROLES,
    IDENTIFIER_RE,
)
from amca_components import (
    clear_custom_library_modules,
    execute_library_component,
    register_library_module,
    unregister_library_module,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CUSTOM_REGISTRY_PATH = ROOT / "artifacts" / "custom_components" / "custom_registry.json"
DEFAULT_CUSTOM_MODULES_DIR = ROOT / "artifacts" / "custom_components" / "modules"


class CustomComponentError(SpecificationError):
    """Raised when a custom, bound, or synthesized component fails validation or security checks."""

    def __init__(self, message: str, path: str = "$.custom_component") -> None:
        super().__init__(message, path=path)

OPERATION_TEMPLATES: dict[str, dict[str, Any]] = {
    "text_transform": {
        "label": "Transformasi & Normalisasi Teks (text -> text)",
        "description": "Memvalidasi dan mentransformasi teks masukan (uppercase, lowercase, titlecase, normalize_spaces, prefix_suffix).",
        "default_inputs": {"text": "string"},
        "default_outputs": {"text": "string"},
        "default_preconditions": {"text": ("is_str",)},
        "default_postconditions": {"text": ("is_str", "non_empty_raw", "non_empty_trimmed", "len_ge_1")},
    },
    "text_metric_object": {
        "label": "Analisis Metrik Teks ke Objek Temuan (text -> finding:object)",
        "description": "Menghitung metrik deterministik (kalimat, baris, angka, kata huruf besar, atau kata kunci) dan menghasilkan objek finding kompatibel Hoare.",
        "default_inputs": {"text": "string"},
        "default_outputs": {"finding": "object"},
        "default_preconditions": {"text": ("is_str", "non_empty_trimmed")},
        "default_postconditions": {
            "finding": (
                "is_obj",
                "has_nonneg_int:character_count",
                "has_nonneg_int:word_count",
                "has_nonneg_int:custom_metric",
            )
        },
    },
    "text_metric_string": {
        "label": "Ringkasan Metrik Teks Langsung (text -> summary:string)",
        "description": "Menghitung metrik teks dan langsung menghasilkan string ringkasan berformat metrik yang siap masuk ke generate_report.",
        "default_inputs": {"text": "string"},
        "default_outputs": {"summary": "string"},
        "default_preconditions": {"text": ("is_str", "non_empty_trimmed")},
        "default_postconditions": {"summary": ("is_str", "formatted_metrics_summary", "non_empty_trimmed")},
    },
    "dual_finding_combiner": {
        "label": "Penggabung Dua Temuan Analisis (finding_a, finding_b -> summary:string)",
        "description": "Menggabungkan dua objek hasil analisis paralel menjadi satu string ringkasan terformat.",
        "default_inputs": {"finding_a": "object", "finding_b": "object"},
        "default_outputs": {"summary": "string"},
        "default_preconditions": {
            "finding_a": ("is_obj", "has_nonneg_int:character_count"),
            "finding_b": ("is_obj", "has_nonneg_int:word_count"),
        },
        "default_postconditions": {"summary": ("is_str", "formatted_metrics_summary", "non_empty_trimmed")},
    },
    "report_packager": {
        "label": "Pengemas Laporan Akhir Kustom (summary -> report:object)",
        "description": "Mengemas string ringkasan menjadi objek laporan akhir dengan label/tag tambahan.",
        "default_inputs": {"summary": "string"},
        "default_outputs": {"report": "object"},
        "default_preconditions": {"summary": ("is_str", "formatted_metrics_summary")},
        "default_postconditions": {"report": ("is_obj", "report_contains_summary")},
    },
    "custom_python": {
        "label": "Modul Kode Python Kustom (On-The-Fly Code Agent / External Bound .py)",
        "description": "Komponen dengan kode Python murni yang telah lulus Static AST Security Gate dan diikat ke amca_components.",
        "default_inputs": {"text": "string"},
        "default_outputs": {"text": "string"},
        "default_preconditions": {"text": ("is_str", "non_empty_trimmed")},
        "default_postconditions": {"text": ("is_str", "non_empty_raw", "non_empty_trimmed", "len_ge_1")},
    },
}


@dataclass(frozen=True)
class CustomComponentSpec:
    component_id: str
    alias: str
    name: str
    role: str
    operation_template: str
    input_ports: dict[str, str]
    output_ports: dict[str, str]
    config_keys: tuple[str, ...]
    default_config: dict[str, Any]
    preconditions: dict[str, tuple[str, ...]]
    postconditions: dict[str, tuple[str, ...]]
    template_params: dict[str, Any]
    prompt_hint: str
    custom_python_source: str = ""
    origin: str = "studio_template"

    def as_dict(self) -> dict[str, Any]:
        return {
            "component_id": self.component_id,
            "alias": self.alias,
            "name": self.name,
            "role": self.role,
            "operation_template": self.operation_template,
            "input_ports": dict(self.input_ports),
            "output_ports": dict(self.output_ports),
            "config_keys": list(self.config_keys),
            "default_config": dict(self.default_config),
            "preconditions": {k: list(v) for k, v in self.preconditions.items()},
            "postconditions": {k: list(v) for k, v in self.postconditions.items()},
            "template_params": dict(self.template_params),
            "prompt_hint": self.prompt_hint,
            "custom_python_source": self.custom_python_source,
            "origin": self.origin,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CustomComponentSpec":
        cid = str(data.get("component_id", "")).strip()
        alias = str(data.get("alias", "") or f"custom.{cid}").strip()
        op_template = str(data.get("operation_template", "text_metric_object")).strip()
        tmpl_meta = OPERATION_TEMPLATES.get(op_template, OPERATION_TEMPLATES["text_metric_object"])
        in_ports = dict(data.get("input_ports") or tmpl_meta["default_inputs"])
        out_ports = dict(data.get("output_ports") or tmpl_meta["default_outputs"])
        cfg_keys = tuple(sorted(str(k) for k in data.get("config_keys", [])))
        def_cfg = dict(data.get("default_config", {}))
        raw_pre = data.get("preconditions")
        if isinstance(raw_pre, dict):
            pre = {str(k): tuple(str(x) for x in v) for k, v in raw_pre.items()}
        else:
            pre = {k: tuple(v) for k, v in tmpl_meta["default_preconditions"].items()}
        raw_post = data.get("postconditions")
        if isinstance(raw_post, dict):
            post = {str(k): tuple(str(x) for x in v) for k, v in raw_post.items()}
        else:
            post = {k: tuple(v) for k, v in tmpl_meta["default_postconditions"].items()}
        params = dict(data.get("template_params", {}))
        name = str(data.get("name", "") or cid.replace("_", " ").title()).strip()
        role = str(data.get("role", "") or tmpl_meta["description"]).strip()
        hint = str(
            data.get("prompt_hint", "")
            or f"Sebutkan komponen `{cid}` (atau alias `{alias}`) di prompt Anda untuk {role.lower()}"
        ).strip()
        py_src = str(data.get("custom_python_source", ""))
        origin = str(data.get("origin", "studio_template" if not py_src else "custom_python"))
        return cls(
            component_id=cid,
            alias=alias,
            name=name,
            role=role,
            operation_template=op_template,
            input_ports=in_ports,
            output_ports=out_ports,
            config_keys=cfg_keys,
            default_config=def_cfg,
            preconditions=pre,
            postconditions=post,
            template_params=params,
            prompt_hint=hint,
            custom_python_source=py_src,
            origin=origin,
        )


_CUSTOM_SPECS: dict[str, CustomComponentSpec] = {}


def render_library_module_for_spec(spec: CustomComponentSpec) -> str:
    """Return the standalone Python library module (`amca_components/custom/<id>.py`) for a CustomComponentSpec."""
    if spec.custom_python_source.strip():
        return spec.custom_python_source.strip() + "\n"

    safe_id = "".join(c if c.isalnum() else "_" for c in spec.component_id)
    func_name = f"run_custom_{safe_id}"
    cid = spec.component_id
    in_port = next(iter(spec.input_ports.keys()), "text")
    out_port = next(iter(spec.output_ports.keys()), "finding")
    default_mode = str(spec.template_params.get("mode", "sentence_count"))
    default_kw = str(spec.template_params.get("keyword", spec.default_config.get("keyword", "amca")))
    default_prefix = str(spec.template_params.get("prefix", spec.default_config.get("prefix", "")))
    default_suffix = str(spec.template_params.get("suffix", spec.default_config.get("suffix", "")))
    default_tag = str(spec.template_params.get("tag", spec.default_config.get("tag", cid)))

    header = f'''"""AMCA Registered Library Component Module: {cid}."""
from __future__ import annotations

import re
from typing import Any

from amca_components.contracts import (
    ContractViolationError,
    _enforce_postconditions,
    _enforce_preconditions,
)

AMCA_COMPONENT_META = {spec.as_dict()!r}
'''

    if spec.operation_template == "text_transform":
        body = f'''
def {func_name}(inputs: dict[str, Any], config: dict[str, Any], raw_inputs: dict[str, Any]) -> dict[str, Any]:
    _enforce_preconditions({cid!r}, inputs)
    raw = str(inputs.get({in_port!r}, "")).strip()
    if not raw:
        raise ContractViolationError("{cid}: input text cannot be empty or whitespace-only")
    mode = str(config.get("mode", {default_mode!r})).lower()
    prefix = str(config.get("prefix", {default_prefix!r}))
    suffix = str(config.get("suffix", {default_suffix!r}))
    if mode == "uppercase":
        transformed = raw.upper()
    elif mode == "lowercase":
        transformed = raw.lower()
    elif mode == "titlecase":
        transformed = raw.title()
    elif mode == "prefix_suffix":
        transformed = f"{{prefix}}{{raw}}{{suffix}}".strip()
    else:
        transformed = " ".join(raw.split())
    outputs = {{{out_port!r}: transformed}}
    _enforce_postconditions({cid!r}, outputs)
    return outputs
'''
        return header + body

    if spec.operation_template in {"text_metric_object", "text_metric_string"}:
        is_str_summary = spec.operation_template == "text_metric_string"
        body = f'''
def {func_name}(inputs: dict[str, Any], config: dict[str, Any], raw_inputs: dict[str, Any]) -> dict[str, Any]:
    _enforce_preconditions({cid!r}, inputs)
    raw = str(inputs.get({in_port!r}, ""))
    if not raw.strip():
        raise ContractViolationError("{cid}: precondition NonEmptyTrimmed({in_port}) violated")
    mode = str(config.get("mode", {default_mode!r})).lower()
    kw = str(config.get("keyword", {default_kw!r})).lower()
    if mode in ("sentence_count", "sentences"):
        m_key, m_val = "sentences", len([s for s in re.split(r"[.!?]+", raw) if s.strip()])
    elif mode in ("line_count", "lines"):
        m_key, m_val = "lines", len([ln for ln in raw.splitlines() if ln.strip()])
    elif mode in ("digit_count", "digits"):
        m_key, m_val = "digits", sum(1 for c in raw if c.isdigit())
    elif mode in ("keyword_count", "keyword"):
        m_key, m_val = "keyword_hits", raw.lower().count(kw or "amca")
    else:
        m_key, m_val = "metric", len(raw.split())
    if {is_str_summary!r}:
        outputs = {{{out_port!r}: f"characters={{len(raw)}}; words={{len(raw.split())}}; {{m_key}}={{m_val}}"}}
    else:
        outputs = {{{out_port!r}: f"{{m_key}}={{m_val}}"}}
    _enforce_postconditions({cid!r}, outputs)
    return outputs
'''
        return header + body

    if spec.operation_template == "dual_finding_combiner":
        ports = list(spec.input_ports.keys())
        p_a = ports[0] if len(ports) >= 1 else "finding_a"
        p_b = ports[1] if len(ports) >= 2 else "finding_b"
        body = f'''
def {func_name}(inputs: dict[str, Any], config: dict[str, Any], raw_inputs: dict[str, Any]) -> dict[str, Any]:
    _enforce_preconditions({cid!r}, inputs)
    outputs = {{{out_port!r}: f"{{inputs[{p_a!r}]}}; {{inputs[{p_b!r}]}}"}}
    _enforce_postconditions({cid!r}, outputs)
    return outputs
'''
        return header + body

    body = f'''
def {func_name}(inputs: dict[str, Any], config: dict[str, Any], raw_inputs: dict[str, Any]) -> dict[str, Any]:
    _enforce_preconditions({cid!r}, inputs)
    tag = str(config.get("tag", {default_tag!r}))
    outputs = {{{out_port!r}: {{"summary": str(inputs[{in_port!r}]), "tag": tag}}}}
    _enforce_postconditions({cid!r}, outputs)
    return outputs
'''
    return header + body


def _compute_text_metric(text: str, mode: str, keyword: str = "amca") -> tuple[str, int]:
    norm_mode = mode.strip().lower()
    if norm_mode in {"sentence_count", "sentences"}:
        parts = [s.strip() for s in re.split(r"[.!?]+", text) if s.strip()]
        return "sentence_count", len(parts)
    if norm_mode in {"line_count", "lines"}:
        lines = [ln for ln in text.splitlines() if ln.strip()]
        return "line_count", len(lines)
    if norm_mode in {"digit_count", "digits"}:
        return "digit_count", sum(1 for c in text if c.isdigit())
    if norm_mode in {"uppercase_word_count", "uppercase_words"}:
        return "uppercase_word_count", sum(1 for w in text.split() if any(c.isupper() for c in w))
    if norm_mode in {"keyword_count", "keyword"}:
        kw = (keyword or "amca").lower()
        return "keyword_count", text.lower().count(kw)
    return "custom_metric", len(text.split())


def _apply_text_transform(text: str, mode: str, prefix: str = "", suffix: str = "") -> str:
    cleaned = text.strip()
    norm_mode = mode.strip().lower()
    if norm_mode == "uppercase":
        out = cleaned.upper()
    elif norm_mode == "lowercase":
        out = cleaned.lower()
    elif norm_mode == "titlecase":
        out = cleaned.title()
    elif norm_mode == "prefix_suffix":
        out = f"{prefix}{cleaned}{suffix}".strip()
    else:
        out = " ".join(cleaned.split())
    return out


def _build_runtime_function(spec: CustomComponentSpec):
    """Build a pure, deterministic runtime function for `amca.registry.ComponentDefinition`."""
    if spec.operation_template == "custom_python" or spec.custom_python_source.strip():
        def _fn_custom_python(config: dict[str, JsonValue], inputs: dict[str, JsonValue]) -> dict[str, JsonValue]:
            try:
                raw_out = execute_library_component(spec.component_id, dict(inputs), dict(config), dict(inputs))
            except Exception as exc:
                raise ComponentFailure(f"{spec.component_id} failed: {exc}") from None
            adapted: dict[str, JsonValue] = {}
            for p_name, p_type in spec.output_ports.items():
                val = raw_out.get(p_name)
                if p_type == "object" and isinstance(val, str):
                    in_text = str(next(iter(inputs.values()), val))
                    adapted[p_name] = {
                        "character_count": len(in_text),
                        "word_count": len(in_text.split()),
                        "custom_metric": 1,
                        "value": val,
                    }
                elif p_type == "string" and isinstance(val, dict):
                    adapted[p_name] = "; ".join(f"{k}={v}" for k, v in sorted(val.items()))
                else:
                    adapted[p_name] = val  # type: ignore[assignment]
            return adapted
        return _fn_custom_python

    in_port = next(iter(spec.input_ports.keys()), "text")
    out_port = next(iter(spec.output_ports.keys()), "finding")
    default_mode = str(spec.template_params.get("mode", "sentence_count"))
    default_kw = str(spec.template_params.get("keyword", spec.default_config.get("keyword", "amca")))
    default_prefix = str(spec.template_params.get("prefix", spec.default_config.get("prefix", "")))
    default_suffix = str(spec.template_params.get("suffix", spec.default_config.get("suffix", "")))
    default_tag = str(spec.template_params.get("tag", spec.default_config.get("tag", spec.component_id)))

    if spec.operation_template == "text_transform":
        def _fn_transform(config: dict[str, JsonValue], inputs: dict[str, JsonValue]) -> dict[str, JsonValue]:
            raw = inputs.get(in_port)
            if type(raw) is not str or not raw.strip():
                raise ComponentFailure(f"{spec.component_id} requires non-empty string on port {in_port!r}")
            mode = str(config.get("mode", default_mode))
            prefix = str(config.get("prefix", default_prefix))
            suffix = str(config.get("suffix", default_suffix))
            transformed = _apply_text_transform(raw, mode=mode, prefix=prefix, suffix=suffix)
            if not transformed:
                raise ComponentFailure(f"{spec.component_id} produced empty text")
            return {out_port: transformed}
        return _fn_transform

    if spec.operation_template == "text_metric_object":
        def _fn_metric_obj(config: dict[str, JsonValue], inputs: dict[str, JsonValue]) -> dict[str, JsonValue]:
            raw = inputs.get(in_port)
            if type(raw) is not str or not raw.strip():
                raise ComponentFailure(f"{spec.component_id} requires non-empty string on port {in_port!r}")
            mode = str(config.get("mode", default_mode))
            kw = str(config.get("keyword", default_kw))
            metric_key, metric_val = _compute_text_metric(raw, mode=mode, keyword=kw)
            return {
                out_port: {
                    "character_count": len(raw),
                    "word_count": len(raw.split()),
                    "custom_metric": metric_val,
                    metric_key: metric_val,
                }
            }
        return _fn_metric_obj

    if spec.operation_template == "text_metric_string":
        def _fn_metric_str(config: dict[str, JsonValue], inputs: dict[str, JsonValue]) -> dict[str, JsonValue]:
            raw = inputs.get(in_port)
            if type(raw) is not str or not raw.strip():
                raise ComponentFailure(f"{spec.component_id} requires non-empty string on port {in_port!r}")
            mode = str(config.get("mode", default_mode))
            kw = str(config.get("keyword", default_kw))
            metric_key, metric_val = _compute_text_metric(raw, mode=mode, keyword=kw)
            return {
                out_port: f"characters={len(raw)}; words={len(raw.split())}; {metric_key}={metric_val}"
            }
        return _fn_metric_str

    if spec.operation_template == "dual_finding_combiner":
        ports = list(spec.input_ports.keys())
        p_a = ports[0] if len(ports) >= 1 else "finding_a"
        p_b = ports[1] if len(ports) >= 2 else "finding_b"

        def _fn_combiner(config: dict[str, JsonValue], inputs: dict[str, JsonValue]) -> dict[str, JsonValue]:
            fa, fb = inputs.get(p_a), inputs.get(p_b)
            if type(fa) is not dict or type(fb) is not dict:
                raise ComponentFailure(f"{spec.component_id} requires object findings on {p_a!r} and {p_b!r}")
            chars = fa.get("character_count", 0)
            words = fb.get("word_count", 0)
            if type(chars) is not int or chars < 0 or type(words) is not int or words < 0:
                raise ComponentFailure("Findings must contain nonnegative integer counts")
            return {out_port: f"characters={chars}; words={words}"}
        return _fn_combiner

    def _fn_report(config: dict[str, JsonValue], inputs: dict[str, JsonValue]) -> dict[str, JsonValue]:
        val = inputs.get(in_port)
        if type(val) is not str or not val.strip():
            raise ComponentFailure(f"{spec.component_id} requires non-empty summary string on {in_port!r}")
        tag = str(config.get("tag", default_tag))
        return {out_port: {"summary": val, "component": spec.component_id, "tag": tag}}

    return _fn_report


def validate_custom_component_spec(spec: CustomComponentSpec) -> None:
    if not IDENTIFIER_RE.match(spec.component_id):
        raise SpecificationError(
            f"component_id {spec.component_id!r} harus sesuai pola ^[a-z][a-z0-9_-]{{0,63}}$",
            path="$.custom_component.component_id",
        )
    if is_builtin_component(spec.component_id):
        raise SpecificationError(
            f"component_id {spec.component_id!r} adalah komponen inti bawaan dan tidak boleh ditimpa.",
            path="$.custom_component.component_id",
        )
    if spec.operation_template not in OPERATION_TEMPLATES:
        raise SpecificationError(
            f"operation_template {spec.operation_template!r} tidak dikenali. Pilihan: {sorted(OPERATION_TEMPLATES)}",
            path="$.custom_component.operation_template",
        )
    if not spec.input_ports or not spec.output_ports:
        raise SpecificationError(
            "Komponen kustom wajib memiliki minimal 1 input port dan 1 output port.",
            path="$.custom_component.ports",
        )
    for p_name, p_type in list(spec.input_ports.items()) + list(spec.output_ports.items()):
        if not IDENTIFIER_RE.match(p_name) or p_type not in {"string", "object"}:
            raise SpecificationError(
                f"Port {p_name!r} ({p_type!r}) tidak valid; nama harus identifier dan tipe 'string' atau 'object'.",
                path="$.custom_component.ports",
            )
    for k in spec.config_keys:
        if not IDENTIFIER_RE.match(k):
            raise SpecificationError(
                f"Config key {k!r} tidak valid; harus sesuai pola identifier.",
                path="$.custom_component.config_keys",
            )


def register_custom_component(
    spec: CustomComponentSpec | dict[str, Any],
    *,
    persist: bool = True,
    overwrite: bool = True,
    registry_path: Path | None = None,
) -> CustomComponentSpec:
    """Validate and register a custom component across AMCA registry, amca_components library, system_spec, and Hoare verifier."""
    parsed = spec if isinstance(spec, CustomComponentSpec) else CustomComponentSpec.from_dict(spec)
    validate_custom_component_spec(parsed)
    if not overwrite and parsed.component_id in _CUSTOM_SPECS:
        raise CustomComponentError(
            f"Komponen kustom {parsed.component_id!r} sudah terdaftar dan overwrite=False."
        )

    module_src = render_library_module_for_spec(parsed)
    disk_dir = ((registry_path.parent / "modules") if registry_path else DEFAULT_CUSTOM_MODULES_DIR) if persist else None
    register_library_module(
        parsed.component_id,
        module_src,
        parsed.as_dict(),
        write_to_disk_dir=disk_dir,
    )

    fn = _build_runtime_function(parsed)
    comp_def = ComponentDefinition(
        component_id=parsed.component_id,
        input_ports=dict(parsed.input_ports),
        output_ports=dict(parsed.output_ports),
        config_keys=frozenset(parsed.config_keys),
        function=fn,
    )
    register_component_definition(comp_def)

    # Register in system_spec alias & role tables
    COMPONENT_ALIASES[parsed.component_id] = parsed.component_id
    if parsed.alias:
        COMPONENT_ALIASES[parsed.alias] = parsed.component_id
    CANONICAL_TO_V1ALPHA1_ALIAS[parsed.component_id] = parsed.alias or f"custom.{parsed.component_id}"
    COMPONENT_ROLES[parsed.component_id] = (parsed.name, parsed.role)

    # Register in Formal Verifier Hoare contract table
    HOARE_CONTRACTS[parsed.component_id] = HoareComponentContract(
        component_id=parsed.component_id,
        preconditions={k: frozenset(v) for k, v in parsed.preconditions.items()},
        postconditions={k: frozenset(v) for k, v in parsed.postconditions.items()},
        pure=True,
    )

    _CUSTOM_SPECS[parsed.component_id] = parsed
    if persist:
        save_custom_components_registry(registry_path)
    return parsed


def unregister_custom_component(
    component_id: str,
    *,
    persist: bool = True,
    registry_path: Path | None = None,
) -> None:
    """Remove a custom component from the active registry and optionally update persisted JSON."""
    if is_builtin_component(component_id):
        raise SpecificationError(f"Tidak dapat menghapus komponen bawaan {component_id!r}.", path="$.custom_component")
    spec = _CUSTOM_SPECS.pop(component_id, None)
    unregister_custom_component_definition(component_id)
    disk_dir = ((registry_path.parent / "modules") if registry_path else DEFAULT_CUSTOM_MODULES_DIR) if persist else None
    unregister_library_module(component_id, disk_dir=disk_dir)
    COMPONENT_ALIASES.pop(component_id, None)
    if spec and spec.alias and spec.alias not in BUILTIN_COMPONENTS:
        COMPONENT_ALIASES.pop(spec.alias, None)
    CANONICAL_TO_V1ALPHA1_ALIAS.pop(component_id, None)
    COMPONENT_ROLES.pop(component_id, None)
    HOARE_CONTRACTS.pop(component_id, None)
    if persist:
        save_custom_components_registry(registry_path)


def clear_all_custom_components(*, persist: bool = False, registry_path: Path | None = None) -> None:
    """Reset the active component registry back to the 6 immutable built-in components."""
    for cid in list(_CUSTOM_SPECS.keys()):
        unregister_custom_component(cid, persist=False)
    _CUSTOM_SPECS.clear()
    clear_custom_component_definitions()
    clear_custom_library_modules()
    if persist:
        save_custom_components_registry(registry_path)


def list_custom_component_specs() -> tuple[CustomComponentSpec, ...]:
    return tuple(_CUSTOM_SPECS[cid] for cid in sorted(_CUSTOM_SPECS))


def get_custom_component_spec(component_id: str) -> CustomComponentSpec | None:
    return _CUSTOM_SPECS.get(component_id)


def save_custom_components_registry(registry_path: Path | None = None) -> Path:
    target = registry_path or DEFAULT_CUSTOM_REGISTRY_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "1.0",
        "custom_components": [spec.as_dict() for spec in list_custom_component_specs()],
    }
    target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


def load_custom_components_registry(registry_path: Path | None = None) -> tuple[CustomComponentSpec, ...]:
    target = registry_path or DEFAULT_CUSTOM_REGISTRY_PATH
    if not target.is_file():
        return ()
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
        items = data.get("custom_components", []) if isinstance(data, dict) else []
        loaded: list[CustomComponentSpec] = []
        for item in items:
            if isinstance(item, dict) and item.get("component_id"):
                cid = str(item["component_id"])
                if not is_builtin_component(cid):
                    loaded.append(register_custom_component(item, persist=False))
        return tuple(loaded)
    except Exception:
        return ()


def draft_custom_component_from_description(
    description: str,
    *,
    component_id: str = "",
    alias: str = "",
) -> CustomComponentSpec:
    """Deterministically draft a complete, Hoare-compliant CustomComponentSpec from a natural language description."""
    desc = description.strip() or "Komponen analisis jumlah kalimat teks"
    lower = desc.lower()

    if not component_id.strip():
        if "kalimat" in lower or "sentence" in lower:
            component_id = "sentence_counter"
        elif "baris" in lower or "line" in lower:
            component_id = "line_counter"
        elif "keyword" in lower or "kata kunci" in lower:
            component_id = "keyword_counter"
        elif "upper" in lower or "kapital" in lower or "huruf besar" in lower:
            component_id = "uppercase_normalizer"
        elif "lower" in lower or "huruf kecil" in lower:
            component_id = "lowercase_normalizer"
        elif "ringkasan" in lower or "summary" in lower:
            component_id = "direct_metric_summarizer"
        elif "laporan" in lower or "report" in lower:
            component_id = "tagged_report_builder"
        else:
            words = [re.sub(r"[^a-z0-9]", "", w) for w in lower.split()]
            words = [w for w in words if w and w[0].isalpha()][:3]
            component_id = "_".join(words) if words else "custom_analyzer"
            if is_builtin_component(component_id):
                component_id = f"custom_{component_id}"

    resolved_alias = alias.strip() or f"custom.{component_id}"

    if any(tok in lower for tok in ("transform", "normal", "upper", "lower", "title", "kapital", "huruf", "bersih")):
        mode = "uppercase" if ("upper" in lower or "kapital" in lower) else ("lowercase" if "lower" in lower else "normalize_spaces")
        return CustomComponentSpec.from_dict(
            {
                "component_id": component_id,
                "alias": resolved_alias,
                "name": component_id.replace("_", " ").title(),
                "role": desc,
                "operation_template": "text_transform",
                "input_ports": {"text": "string"},
                "output_ports": {"text": "string"},
                "config_keys": ["mode"],
                "default_config": {"mode": mode},
                "template_params": {"mode": mode},
                "prompt_hint": f"Gunakan komponen `{component_id}` setelah `input_source` atau `validate_text` untuk menormalisasi teks ({mode}).",
            }
        )

    if any(tok in lower for tok in ("ringkasan langsung", "direct summary", "summary string")):
        mode = "sentence_count" if ("kalimat" in lower or "sentence" in lower) else "word_count"
        return CustomComponentSpec.from_dict(
            {
                "component_id": component_id,
                "alias": resolved_alias,
                "name": component_id.replace("_", " ").title(),
                "role": desc,
                "operation_template": "text_metric_string",
                "input_ports": {"text": "string"},
                "output_ports": {"summary": "string"},
                "config_keys": ["mode"],
                "default_config": {},
                "template_params": {"mode": mode},
                "prompt_hint": f"Gunakan `{component_id}` setelah `validate_text` untuk menghasilkan output `summary` langsung.",
            }
        )

    if any(tok in lower for tok in ("keyword", "kata kunci")):
        return CustomComponentSpec.from_dict(
            {
                "component_id": component_id,
                "alias": resolved_alias,
                "name": component_id.replace("_", " ").title(),
                "role": desc,
                "operation_template": "text_metric_object",
                "input_ports": {"text": "string"},
                "output_ports": {"finding": "object"},
                "config_keys": ["keyword"],
                "default_config": {"keyword": "amca"},
                "template_params": {"mode": "keyword_count", "keyword": "amca"},
                "prompt_hint": f"Gunakan `{component_id}` setelah `validate_text` untuk menghitung kemunculan kata kunci pada teks.",
            }
        )

    mode = "sentence_count"
    if "baris" in lower or "line" in lower:
        mode = "line_count"
    elif "angka" in lower or "digit" in lower:
        mode = "digit_count"

    return CustomComponentSpec.from_dict(
        {
            "component_id": component_id,
            "alias": resolved_alias,
            "name": component_id.replace("_", " ").title(),
            "role": desc,
            "operation_template": "text_metric_object",
            "input_ports": {"text": "string"},
            "output_ports": {"finding": "object"},
            "config_keys": [],
            "default_config": {},
            "template_params": {"mode": mode},
            "prompt_hint": f"Gunakan `{component_id}` setelah `validate_text` sebagai cabang analisis teks ({mode}).",
        }
    )


def get_registered_components_catalog() -> list[dict[str, Any]]:
    """Return a complete, structured catalog of all registered components (built-in + custom) for UI/CLI/Prompt presentation."""
    builtin_hints = {
        "input_source": "Titik masuk wajib. Membaca string dari kunci payload JSON runtime (default `input_key: text`). Dapat berdiri sendiri sebagai Mesin Tunggal (`single_machine`).",
        "validate_text": "Validator wajib sebelum analisis. Memangkas spasi & memastikan teks tidak kosong (`non_empty_trimmed`).",
        "analysis_a": "Menghitung jumlah karakter (`characters=<N>`) dari teks yang telah divalidasi.",
        "analysis_b": "Menghitung jumlah kata (`words=<N>`) dari teks yang telah divalidasi.",
        "aggregate_results": "Menggabungkan temuan `finding_a` (karakter) dan `finding_b` (kata) menjadi string `summary`.",
        "generate_report": "Membungkus string `summary` menjadi objek laporan akhir `report` (`{\"summary\": ...}`).",
    }
    catalog: list[dict[str, Any]] = []
    for cid in component_ids():
        defn = get_component(cid)
        is_builtin = is_builtin_component(cid)
        custom_spec = _CUSTOM_SPECS.get(cid)
        title, role = COMPONENT_ROLES.get(cid, (cid, "Komponen Terdaftar"))
        alias = CANONICAL_TO_V1ALPHA1_ALIAS.get(cid, f"custom.{cid}")
        hoare = HOARE_CONTRACTS.get(cid)
        pre_str = (
            ", ".join(f"{p}: {{{', '.join(sorted(preds))}}}" for p, preds in sorted(hoare.preconditions.items()))
            if hoare and hoare.preconditions
            else "(tanpa prasyarat masuk)"
        )
        post_str = (
            ", ".join(f"{p}: {{{', '.join(sorted(preds))}}}" for p, preds in sorted(hoare.postconditions.items()))
            if hoare and hoare.postconditions
            else "-"
        )
        in_str = ", ".join(f"{k}:{v}" for k, v in defn.input_ports.items()) or "(sumber eksternal)"
        out_str = ", ".join(f"{k}:{v}" for k, v in defn.output_ports.items())
        cfg_str = ", ".join(sorted(defn.config_keys)) if defn.config_keys else "{}"
        hint = custom_spec.prompt_hint if custom_spec else builtin_hints.get(cid, role)
        origin = "builtin" if is_builtin else (custom_spec.origin if custom_spec else "custom")
        catalog.append(
            {
                "component_id": cid,
                "alias": alias,
                "category": "Built-in Inti" if is_builtin else f"Kustom Terdaftar ({origin})",
                "origin": origin,
                "name": title,
                "role": role,
                "input_ports": in_str,
                "output_ports": out_str,
                "config_keys": cfg_str,
                "hoare_preconditions": pre_str,
                "hoare_postconditions": post_str,
                "prompt_hint": hint,
            }
        )
    return catalog


def format_catalog_markdown() -> str:
    """Format all registered components and prompt boundary rules as user-facing Markdown."""
    rows = get_registered_components_catalog()
    builtin_count = sum(1 for r in rows if r["category"] == "Built-in Inti")
    custom_count = sum(1 for r in rows if r["category"] != "Built-in Inti")

    lines = [
        f"### 📋 Katalog Komponen Terdaftar & Panduan Batasan Prompt ({len(rows)} Komponen: {builtin_count} Inti, {custom_count} Kustom)",
        "",
        "Sebelum memasukkan *problem statement* / prompt untuk membangun YAML, perhatikan bahwa **AMCA memelihara Library Komponen Terverifikasi (`amca_components`)**. "
        "Anda dapat merangkai komponen yang sudah terdaftar di tabel bawah ini, mengikat komponen baru dari luar (`.py` hasil Antigravity/OpenCode/Codex), atau mengizinkan Agent AMCA mengenerate komponen baru secara *on-the-fly* saat menyusun YAML:",
        "",
        "| ID Komponen (`v1.0`) | Alias (`amca/v1alpha1`) | Kategori | Port Masuk (`in`) | Port Keluar (`out`) | Config Keys | Kontrak Hoare ($P_c \\rightarrow Q_c$) | Peran & Panduan Prompt |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| `{r['component_id']}` | `{r['alias']}` | {r['category']} | `{r['input_ports']}` | "
            f"`{r['output_ports']}` | `{r['config_keys']}` | **Pre**: `{r['hoare_preconditions']}`<br>**Post**: `{r['hoare_postconditions']}` | "
            f"**{r['name']}**: {r['prompt_hint']} |"
        )

    lines.extend(
        [
            "",
            "#### 🧭 Batasan Prompt (*Prompt Boundaries*) & Ekspansi Library Komponen:",
            "1. **Katalog Komponen & Sintesis *On-The-Fly***: Anda dapat langsung meminta komponen dari tabel di atas, atau meminta kapabilitas baru di dalam prompt Anda. Jika YAML yang disusun Agent memuat komponen baru yang belum terdaftar, AMCA akan meminta persetujuan Anda untuk mengenerate kode Python komponen tersebut secara *on-the-fly* dan menambahkannya ke library `amca_components`.",
            "2. **Batasan Aliran Kontrak Hoare (`FO-HOA-01`)**: Keluaran `input_source` (`text`) **wajib** divalidasi terlebih dahulu oleh `validate_text` (atau komponen transformasi yang menjamin `non_empty_trimmed`) sebelum dihubungkan ke komponen analisis (`analysis_a`, `analysis_b`, atau analisis kustom).",
            "3. **Tiga Topologi Mesin yang Didukung**:",
            "   - **Mesin Tunggal (`single_machine`)**: Contoh prompt: *\"Buat mesin tunggal dengan `machine_id: single_reader` menggunakan `input_source`.\"*",
            "   - **Pipeline Linier (`linear_pipeline`)**: Contoh prompt: *\"Buat pipeline linier `linear_char_pipeline` dari `input_source` -> `validate_text` -> `analysis_a`.\"*",
            "   - **Graf Nonlinier / DAG Paralel (`nonlinear_dag`)**: Contoh prompt: *\"Buat graf DAG paralel `reference_text_analysis` yang memvalidasi teks, menjalankan `analysis_a` dan `analysis_b` secara paralel, menggabungkannya dengan `aggregate_results`, dan membuat laporan `generate_report`.\"*",
        ]
    )
    return "\n".join(lines)
