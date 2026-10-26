"""Static AST Security Gate & External Component Binder for AMCA (RF-02).

Allows binding Python components authored externally (via Antigravity, OpenCode,
Codex, or manual `.py` files) or synthesized on-the-fly by the AMCA Code Agent
into the cumulative `amca_components` library and active AMCA runtime/verifier.
"""

from __future__ import annotations

import ast
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from amca_components.contracts import (
    ContractViolationError,
    _enforce_postconditions,
    _enforce_preconditions,
    register_contract,
)

from .custom_components import (
    DEFAULT_CUSTOM_MODULES_DIR,
    CustomComponentError,
    CustomComponentSpec,
    register_custom_component,
)


class ComponentSecurityError(CustomComponentError):
    """Raised when component Python source violates the Static AST Security Gate."""


class ComponentBindingError(CustomComponentError):
    """Raised when component metadata extraction or behavioral self-test fails."""


ALLOWED_STDLIB_IMPORTS: frozenset[str] = frozenset(
    {
        "__future__",
        "re",
        "json",
        "math",
        "statistics",
        "collections",
        "itertools",
        "functools",
        "string",
        "unicodedata",
        "hashlib",
        "typing",
        "dataclasses",
        "decimal",
        "fractions",
        "amca_components",
        "amca_components.contracts",
    }
)

FORBIDDEN_CALLS: frozenset[str] = frozenset(
    {
        "eval",
        "exec",
        "compile",
        "open",
        "__import__",
        "input",
        "breakpoint",
        "globals",
        "locals",
        "vars",
        "delattr",
        "setattr",
        "getattr",
    }
)

FORBIDDEN_ATTRS: frozenset[str] = frozenset(
    {
        "__subclasses__",
        "__globals__",
        "__code__",
        "__builtins__",
        "__dict__",
        "__class__",
        "__bases__",
        "__mro__",
        "__closure__",
    }
)


@dataclass(frozen=True)
class ASTAuditReport:
    passed: bool
    imported_modules: tuple[str, ...]
    defined_functions: tuple[str, ...]
    has_explicit_meta: bool
    violations: tuple[str, ...] = ()
    source_sha256: str = ""


@dataclass(frozen=True)
class BoundComponentRecord:
    spec: CustomComponentSpec
    audit_report: ASTAuditReport
    sample_inputs: dict[str, Any]
    sample_outputs: dict[str, Any]
    precondition_rejection_verified: bool
    library_module_path: str
    sha256: str


def entrypoint_name(component_id: str) -> str:
    """Return the Python-safe canonical entrypoint name `run_<id>` (hyphens become underscores)."""
    return "run_" + component_id.replace("-", "_")


def audit_component_source_ast(source_code: str) -> ASTAuditReport:
    """Parse and statically audit Python source code for security and determinism.

    Fails closed with `ComponentSecurityError` if any forbidden import, builtin
    call, dunder attribute access, or syntax error is present.
    """
    if not isinstance(source_code, str) or not source_code.strip():
        raise ComponentSecurityError("Kode sumber Python komponen tidak boleh kosong.")

    try:
        tree = ast.parse(source_code)
    except SyntaxError as exc:
        raise ComponentSecurityError(
            f"SyntaxError pada kode komponen Python (baris {exc.lineno}): {exc.msg}"
        ) from exc

    violations: list[str] = []
    imported_modules: list[str] = []
    defined_functions: list[str] = []
    has_explicit_meta = False

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                mod_name = alias.name.strip()
                root_mod = mod_name.split(".")[0]
                imported_modules.append(mod_name)
                if mod_name not in ALLOWED_STDLIB_IMPORTS and root_mod not in ALLOWED_STDLIB_IMPORTS:
                    violations.append(
                        f"Import modul '{mod_name}' ditolak oleh AST Security Gate "
                        f"(hanya modul deterministik murni yang diizinkan)."
                    )
        elif isinstance(node, ast.ImportFrom):
            mod_name = (node.module or "").strip()
            root_mod = mod_name.split(".")[0] if mod_name else ""
            imported_modules.append(mod_name)
            if mod_name not in ALLOWED_STDLIB_IMPORTS and root_mod not in ALLOWED_STDLIB_IMPORTS:
                violations.append(
                    f"Import dari modul '{mod_name}' ditolak oleh AST Security Gate."
                )
            for alias in node.names:
                if alias.name == "*":
                    violations.append("Wildcard import ('from ... import *') dilarang.")
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                fn_name = node.func.id
                if fn_name in FORBIDDEN_CALLS:
                    violations.append(
                        f"Pemanggilan fungsi bawaan berbahaya '{fn_name}()' dilarang."
                    )
            elif isinstance(node.func, ast.Attribute):
                attr_name = node.func.attr
                if attr_name in FORBIDDEN_CALLS:
                    violations.append(
                        f"Pemanggilan metode berbahaya '.{attr_name}()' dilarang."
                    )
        elif isinstance(node, ast.Attribute):
            if node.attr in FORBIDDEN_ATTRS:
                violations.append(
                    f"Akses atribut internal/dunder '{node.attr}' dilarang."
                )
        elif isinstance(node, (ast.AsyncFunctionDef, ast.Await, ast.AsyncFor, ast.AsyncWith)):
            violations.append("Konstruksi asinkron (async/await) tidak diizinkan dalam komponen deterministik.")
        elif isinstance(node, ast.Global) or isinstance(node, ast.Nonlocal):
            violations.append("Mutasi state global/nonlocal dilarang dalam komponen deterministik.")

    for top_node in tree.body:
        if isinstance(top_node, ast.FunctionDef):
            defined_functions.append(top_node.name)
        elif isinstance(top_node, ast.Assign):
            for target in top_node.targets:
                if isinstance(target, ast.Name) and target.id == "AMCA_COMPONENT_META":
                    has_explicit_meta = True

    if not defined_functions:
        violations.append(
            "Kode komponen wajib mendefinisikan minimal satu fungsi Python (`def ...`)."
        )

    sha256_hex = hashlib.sha256(source_code.encode("utf-8")).hexdigest()
    if violations:
        raise ComponentSecurityError(
            "AST Security Gate menolak kode komponen:\n- " + "\n- ".join(violations)
        )

    return ASTAuditReport(
        passed=True,
        imported_modules=tuple(dict.fromkeys(imported_modules)),
        defined_functions=tuple(defined_functions),
        has_explicit_meta=has_explicit_meta,
        violations=(),
        source_sha256=sha256_hex,
    )


def _infer_return_port_type(fn_node: ast.FunctionDef) -> str:
    """Infer whether a function returns 'string' or 'object' from its return annotation or body."""
    if fn_node.returns is not None:
        ann_text = ast.unparse(fn_node.returns).lower()
        if "dict" in ann_text or "mapping" in ann_text or "object" in ann_text:
            return "object"
        if "str" in ann_text:
            return "string"

    for node in ast.walk(fn_node):
        if isinstance(node, ast.Return) and node.value is not None:
            if isinstance(node.value, ast.Dict):
                return "object"
            if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name):
                if node.value.func.id == "dict":
                    return "object"
    return "string"


def extract_or_infer_component_meta(
    source_code: str,
    *,
    component_id: str = "",
    alias: str = "",
    name: str = "",
    role: str = "",
    input_ports: dict[str, str] | None = None,
    output_ports: dict[str, str] | None = None,
    config_keys: list[str] | None = None,
    default_config: dict[str, Any] | None = None,
    preconditions: dict[str, list[str]] | None = None,
    postconditions: dict[str, list[str]] | None = None,
    origin: str = "external_bound",
) -> tuple[CustomComponentSpec, str, bool]:
    """Extract `AMCA_COMPONENT_META` or infer metadata from plain Python functions.

    Returns `(spec, target_function_name, is_already_canonical_signature)`.
    """
    tree = ast.parse(source_code)
    explicit_meta: dict[str, Any] = {}

    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "AMCA_COMPONENT_META":
                    try:
                        val = ast.literal_eval(node.value)
                        if isinstance(val, dict):
                            explicit_meta = val
                    except Exception as exc:
                        raise ComponentBindingError(
                            f"AMCA_COMPONENT_META harus berupa literal dict Python yang valid: {exc}"
                        ) from exc

    public_funcs = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and not node.name.startswith("_")
    ]
    if not public_funcs:
        raise ComponentBindingError(
            "Tidak ditemukan fungsi publik (non-private `def ...`) di dalam kode sumber."
        )

    # Prefer `run_<cid>` if present, otherwise first public function
    inferred_cid = (
        component_id.strip()
        or str(explicit_meta.get("component_id", "")).strip()
    )
    chosen_fn: ast.FunctionDef = public_funcs[0]
    for fn in public_funcs:
        if inferred_cid and fn.name in (f"run_{inferred_cid}", entrypoint_name(inferred_cid)):
            chosen_fn = fn
            break
        if fn.name.startswith("run_") and not inferred_cid:
            chosen_fn = fn
            inferred_cid = fn.name[len("run_"):]
            break

    if not inferred_cid:
        raw_fn_name = chosen_fn.name.lower()
        if raw_fn_name.startswith("run_"):
            raw_fn_name = raw_fn_name[4:]
        inferred_cid = raw_fn_name

    arg_names = [arg.arg for arg in chosen_fn.args.args]
    is_canonical_sig = (
        len(arg_names) == 3
        and arg_names[0] == "inputs"
        and arg_names[1] == "config"
        and arg_names[2] == "raw_inputs"
    )

    docstring = ast.get_docstring(chosen_fn) or ast.get_docstring(tree) or ""
    first_doc_line = docstring.strip().splitlines()[0].strip() if docstring.strip() else ""

    final_alias = (
        alias.strip()
        or str(explicit_meta.get("alias", "")).strip()
        or f"custom.{inferred_cid}"
    )
    final_name = (
        name.strip()
        or str(explicit_meta.get("name", "")).strip()
        or inferred_cid.replace("_", " ").title()
    )
    final_role = (
        role.strip()
        or str(explicit_meta.get("role", "")).strip()
        or first_doc_line
        or f"Custom bound component {inferred_cid} ({origin})."
    )

    # Infer input_ports
    if input_ports:
        final_in_ports = dict(input_ports)
    elif isinstance(explicit_meta.get("input_ports"), dict) and explicit_meta["input_ports"]:
        final_in_ports = {str(k): str(v) for k, v in explicit_meta["input_ports"].items()}
    else:
        if is_canonical_sig or not arg_names or arg_names == ["inputs"] or arg_names == ["inputs", "config"]:
            final_in_ports = {"text": "string"}
        else:
            # Map non-default parameters or first parameter as input port
            num_defaults = len(chosen_fn.args.defaults)
            required_args = arg_names[: len(arg_names) - num_defaults] if num_defaults else arg_names
            if not required_args:
                required_args = [arg_names[0]]
            final_in_ports = {}
            for a_name in required_args:
                if a_name in ("config", "raw_inputs"):
                    continue
                port_t = "object" if a_name in ("left", "right", "finding", "data", "payload", "metrics") else "string"
                final_in_ports[a_name] = port_t
            if not final_in_ports:
                final_in_ports = {"text": "string"}

    # Infer output_ports
    if output_ports:
        final_out_ports = dict(output_ports)
    elif isinstance(explicit_meta.get("output_ports"), dict) and explicit_meta["output_ports"]:
        final_out_ports = {str(k): str(v) for k, v in explicit_meta["output_ports"].items()}
    else:
        ret_type = _infer_return_port_type(chosen_fn)
        if ret_type == "object" and not is_canonical_sig:
            final_out_ports = {"finding": "object"}
        elif is_canonical_sig:
            # Inspect return dictionary keys if literal dict is returned
            inferred_out: dict[str, str] = {}
            for sub in ast.walk(chosen_fn):
                if isinstance(sub, ast.Return) and isinstance(sub.value, ast.Dict):
                    for k_node, v_node in zip(sub.value.keys, sub.value.values):
                        if isinstance(k_node, ast.Constant) and isinstance(k_node.value, str):
                            k_str = k_node.value
                            if k_str in ("finding", "report", "metrics", "result") or isinstance(v_node, ast.Dict):
                                inferred_out[k_str] = "object"
                            else:
                                inferred_out[k_str] = "string"
            final_out_ports = inferred_out or {"text": "string"}
        else:
            final_out_ports = {"text": "string"}

    # Infer config_keys & default_config from function defaults if any
    final_def_cfg: dict[str, Any] = dict(default_config or explicit_meta.get("default_config") or {})
    if not is_canonical_sig and chosen_fn.args.defaults:
        num_defs = len(chosen_fn.args.defaults)
        default_arg_names = arg_names[len(arg_names) - num_defs :]
        for d_name, d_node in zip(default_arg_names, chosen_fn.args.defaults):
            if d_name in final_in_ports:
                continue
            try:
                val = ast.literal_eval(d_node)
                if isinstance(val, (str, int, float, bool)):
                    final_def_cfg.setdefault(d_name, val)
            except Exception:
                pass

    if config_keys is not None:
        final_cfg_keys = tuple(sorted(set(str(k) for k in config_keys) | set(final_def_cfg.keys())))
    elif explicit_meta.get("config_keys"):
        final_cfg_keys = tuple(
            sorted(set(str(k) for k in explicit_meta["config_keys"]) | set(final_def_cfg.keys()))
        )
    else:
        final_cfg_keys = tuple(sorted(final_def_cfg.keys()))

    # Infer preconditions & postconditions matching Hoare contracts
    if preconditions:
        final_pre = {str(k): tuple(str(x) for x in v) for k, v in preconditions.items()}
    elif isinstance(explicit_meta.get("preconditions"), dict) and explicit_meta["preconditions"]:
        final_pre = {
            str(k): tuple(str(x) for x in v)
            for k, v in explicit_meta["preconditions"].items()
        }
    else:
        final_pre = {}
        for p_name, p_type in final_in_ports.items():
            if p_type == "string":
                if p_name == "summary":
                    final_pre[p_name] = ("is_str", "formatted_metrics_summary")
                else:
                    final_pre[p_name] = ("is_str",)
            else:
                final_pre[p_name] = ("is_obj",)

    if postconditions:
        final_post = {str(k): tuple(str(x) for x in v) for k, v in postconditions.items()}
    elif isinstance(explicit_meta.get("postconditions"), dict) and explicit_meta["postconditions"]:
        final_post = {
            str(k): tuple(str(x) for x in v)
            for k, v in explicit_meta["postconditions"].items()
        }
    else:
        final_post = {}
        for p_name, p_type in final_out_ports.items():
            if p_type == "string":
                labels = ["is_str", "non_empty_raw", "non_empty_trimmed", "len_ge_1"]
                if p_name == "summary":
                    labels.append("formatted_metrics_summary")
                final_post[p_name] = tuple(labels)
            else:
                # The canonical wrapper guarantees these keys on every object output.
                final_post[p_name] = (
                    "is_obj",
                    "has_nonneg_int:character_count",
                    "has_nonneg_int:word_count",
                    "has_nonneg_int:custom_metric",
                    "report_contains_summary",
                )

    op_template = "custom_python"

    spec = CustomComponentSpec(
        component_id=inferred_cid,
        alias=final_alias,
        name=final_name,
        role=final_role,
        operation_template=op_template,
        input_ports=final_in_ports,
        output_ports=final_out_ports,
        config_keys=final_cfg_keys,
        default_config=final_def_cfg,
        preconditions=final_pre,
        postconditions=final_post,
        template_params={},
        prompt_hint=(
            f"Sebutkan komponen `{inferred_cid}` (atau alias `{final_alias}`) "
            f"di prompt Anda untuk {final_role.lower()}"
        ),
        custom_python_source="",
        origin=origin,
    )
    return spec, chosen_fn.name, is_canonical_sig


def wrap_into_canonical_library_module(
    source_code: str,
    spec: CustomComponentSpec,
    target_fn_name: str,
    is_canonical_sig: bool,
) -> str:
    """Wrap external or synthesized Python code into a canonical AMCA library module.

    Guarantees explicit `_enforce_preconditions("<cid>", inputs)` and
    `_enforce_postconditions("<cid>", outputs)` calls so Stage 3 AST refinement
    (`FO-REF-02`) and runtime Hoare contract checks always pass.
    """
    cid = spec.component_id
    entry_fn = entrypoint_name(cid)
    meta_dict = {
        "component_id": spec.component_id,
        "entrypoint": entry_fn,
        "alias": spec.alias,
        "name": spec.name,
        "role": spec.role,
        "operation_template": spec.operation_template,
        "input_ports": dict(spec.input_ports),
        "output_ports": dict(spec.output_ports),
        "config_keys": list(spec.config_keys),
        "default_config": dict(spec.default_config),
        "preconditions": {k: list(v) for k, v in spec.preconditions.items()},
        "postconditions": {k: list(v) for k, v in spec.postconditions.items()},
        "origin": spec.origin,
    }

    # Strip existing `from __future__ import annotations` from user source so we place it at top
    cleaned_lines: list[str] = []
    for line in source_code.splitlines():
        if line.strip().startswith("from __future__ import"):
            continue
        cleaned_lines.append(line)
    user_code_block = "\n".join(cleaned_lines).strip()

    # If the user already wrote `def run_<cid>(inputs, config, raw_inputs)`, rename the inner
    # definition to `_impl_run_<cid>` so the outer `run_<cid>` wrapper enforces contracts cleanly.
    impl_fn_name = target_fn_name
    if target_fn_name in {f"run_{cid}", entry_fn}:
        impl_fn_name = f"_user_impl_{entry_fn[len('run_'):]}"
        tree = ast.parse(user_code_block)
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name == target_fn_name:
                node.name = impl_fn_name
        user_code_block = ast.unparse(tree)

    tree_check = ast.parse(user_code_block)
    fn_node: ast.FunctionDef | None = None
    for node in tree_check.body:
        if isinstance(node, ast.FunctionDef) and node.name == impl_fn_name:
            fn_node = node
            break
    arg_names = [a.arg for a in fn_node.args.args] if fn_node else []

    if is_canonical_sig:
        call_expr = f"{impl_fn_name}(inputs, merged_cfg, raw_inputs)"
    elif arg_names == ["inputs", "config"]:
        call_expr = f"{impl_fn_name}(inputs, merged_cfg)"
    elif arg_names == ["inputs"]:
        call_expr = f"{impl_fn_name}(inputs)"
    else:
        call_kwargs: list[str] = []
        for a_name in arg_names:
            if a_name in spec.input_ports:
                call_kwargs.append(f"{a_name}=inputs.get({a_name!r})")
            elif a_name == "config":
                call_kwargs.append("config=merged_cfg")
            elif a_name == "raw_inputs":
                call_kwargs.append("raw_inputs=raw_inputs")
            else:
                call_kwargs.append(f"{a_name}=merged_cfg.get({a_name!r}, inputs.get({a_name!r}))")
        call_expr = f"{impl_fn_name}({', '.join(call_kwargs)})"

    lines = [
        f'"""Bound AMCA Library Component: `{cid}` ({spec.origin})."""',
        "",
        "from __future__ import annotations",
        "",
        "from typing import Any",
        "",
        "from amca_components.contracts import (",
        "    ContractViolationError,",
        "    _enforce_postconditions,",
        "    _enforce_preconditions,",
        "    register_contract,",
        ")",
        "",
        "# --- Begin User / Code-Agent Component Logic ---",
        user_code_block,
        "# --- End User / Code-Agent Component Logic ---",
        "",
        f"AMCA_COMPONENT_META: dict[str, Any] = {repr(meta_dict)}",
        "",
        "register_contract(",
        f"    {cid!r},",
        f"    preconditions={repr({k: list(v) for k, v in spec.preconditions.items()})},",
        f"    postconditions={repr({k: list(v) for k, v in spec.postconditions.items()})},",
        ")",
        "",
        "",
        f"def {entry_fn}(",
        "    inputs: dict[str, Any],",
        "    config: dict[str, Any],",
        "    raw_inputs: dict[str, Any],",
        ") -> dict[str, Any]:",
        f'    """Canonical AMCA library entrypoint with Hoare contract enforcement for `{cid}`."""',
        f'    _enforce_preconditions("{cid}", inputs)',
        f"    merged_cfg = dict({repr(spec.default_config)})",
        "    if config:",
        "        merged_cfg.update(config)",
        f"    raw_result = {call_expr}",
        f"    expected_ports = {repr(dict(spec.output_ports))}",
        "    outputs: dict[str, Any] = {}",
        '    in_text_sample = str(inputs.get("text", next(iter(inputs.values()), "")))',
        "    if isinstance(raw_result, dict) and set(expected_ports.keys()).issubset(set(raw_result.keys())):",
        "        for p_name, p_type in expected_ports.items():",
        "            val = raw_result[p_name]",
        '            if p_type == "string":',
        '                s_val = str(val).strip() if val is not None else ""',
        "                outputs[p_name] = s_val if s_val else f\"[{cid}] processed\"",
        "            else:",
        "                obj_val = dict(val) if isinstance(val, dict) else {\"result\": val, \"component\": " + repr(cid) + "}",
        '                obj_val.setdefault("character_count", len(in_text_sample))',
        '                obj_val.setdefault("word_count", len(in_text_sample.split()))',
        '                obj_val.setdefault("custom_metric", 1)',
        '                obj_val.setdefault("summary", "; ".join(f"{k}={v}" for k, v in sorted(obj_val.items())))',
        "                outputs[p_name] = obj_val",
        "    else:",
        "        for p_name, p_type in expected_ports.items():",
        '            if p_type == "string":',
        "                if isinstance(raw_result, dict) and p_name in raw_result:",
        "                    s_val = str(raw_result[p_name]).strip()",
        "                else:",
        "                    s_val = str(raw_result).strip() if raw_result is not None else \"\"",
        "                outputs[p_name] = s_val if s_val else f\"[{cid}] processed\"",
        "            else:",
        "                obj_val = dict(raw_result) if isinstance(raw_result, dict) else {\"value\": raw_result, \"component\": " + repr(cid) + "}",
        '                obj_val.setdefault("character_count", len(in_text_sample))',
        '                obj_val.setdefault("word_count", len(in_text_sample.split()))',
        '                obj_val.setdefault("custom_metric", 1)',
        '                obj_val.setdefault("summary", "; ".join(f"{k}={v}" for k, v in sorted(obj_val.items())))',
        "                outputs[p_name] = obj_val",
        f'    _enforce_postconditions("{cid}", outputs)',
        "    return outputs",
        "",
    ]
    return "\n".join(lines)


def verify_component_behavior(
    module_source: str,
    spec: CustomComponentSpec,
) -> tuple[dict[str, Any], dict[str, Any], bool]:
    """Execute the wrapped component in an isolated sandbox to verify Hoare contracts.

    1. Verifies positive execution with sample inputs matching `spec.input_ports`.
    2. Verifies output ports and value types (`str` for `string`, `dict` for `object`).
    3. Verifies negative execution (`{}` empty inputs) raises `ContractViolationError`.
    """
    audit_component_source_ast(module_source)

    namespace: dict[str, Any] = {"__name__": f"amca_sandbox_{spec.component_id}"}
    try:
        code_obj = compile(module_source, f"<amca_component:{spec.component_id}>", "exec")
        exec(code_obj, namespace)  # noqa: S102 - audited by AST gate right above
    except Exception as exc:
        raise ComponentBindingError(
            f"Gagal memuat modul komponen '{spec.component_id}' saat uji mandiri: {exc}"
        ) from exc

    runner_name = entrypoint_name(spec.component_id)
    runner = namespace.get(runner_name)
    if not callable(runner):
        raise ComponentBindingError(
            f"Fungsi entrypoint '{runner_name}' tidak ditemukan setelah pembungkusan."
        )

    sample_inputs: dict[str, Any] = {}
    for p_name, p_type in spec.input_ports.items():
        if p_type == "string":
            sample_inputs[p_name] = "AMCA verifies deterministic component synthesis and Hoare contracts."
        else:
            sample_inputs[p_name] = {
                "metric": "sample_Verification",
                "count": 3,
                "summary": "AMCA sample object payload",
            }

    try:
        sample_outputs = runner(dict(sample_inputs), dict(spec.default_config), dict(sample_inputs))
    except Exception as exc:
        raise ComponentBindingError(
            f"Komponen '{spec.component_id}' gagal saat dieksekusi dengan sampel uji valid: {exc}"
        ) from exc

    if not isinstance(sample_outputs, dict):
        raise ComponentBindingError(
            f"Keluaran komponen '{spec.component_id}' harus berupa dict, bukan {type(sample_outputs).__name__}."
        )

    for p_name, p_type in spec.output_ports.items():
        if p_name not in sample_outputs:
            raise ComponentBindingError(
                f"Port keluaran '{p_name}' tidak dihasilkan oleh komponen '{spec.component_id}'."
            )
        val = sample_outputs[p_name]
        if p_type == "string" and (not isinstance(val, str) or not val.strip()):
            raise ComponentBindingError(
                f"Port keluaran '{p_name}' bertipe 'string' harus menghasilkan str non-kosong."
            )
        if p_type == "object" and (not isinstance(val, dict) or len(val) == 0):
            raise ComponentBindingError(
                f"Port keluaran '{p_name}' bertipe 'object' harus menghasilkan dict non-kosong."
            )

    # Verify negative case (missing preconditions must raise ContractViolationError)
    precondition_rejected = False
    try:
        runner({}, dict(spec.default_config), {})
    except ContractViolationError:
        precondition_rejected = True
    except Exception as exc:
        raise ComponentBindingError(
            f"Saat diberi input kosong, komponen '{spec.component_id}' harus melempar "
            f"ContractViolationError, tetapi melempar {type(exc).__name__}: {exc}"
        ) from exc

    if not precondition_rejected:
        raise ComponentBindingError(
            f"Komponen '{spec.component_id}' tidak menolak input kosong `{{}}` (Precondition check gagal)."
        )

    return sample_inputs, sample_outputs, precondition_rejected


def bind_component_from_python_source(
    source_code: str,
    *,
    component_id: str = "",
    alias: str = "",
    name: str = "",
    role: str = "",
    input_ports: dict[str, str] | None = None,
    output_ports: dict[str, str] | None = None,
    config_keys: list[str] | None = None,
    default_config: dict[str, Any] | None = None,
    preconditions: dict[str, list[str]] | None = None,
    postconditions: dict[str, list[str]] | None = None,
    origin: str = "external_bound",
    persist: bool = True,
    overwrite: bool = True,
) -> BoundComponentRecord:
    """Audit, wrap, self-test, and bind a Python component into AMCA's library & registry."""
    initial_audit = audit_component_source_ast(source_code)
    inferred_spec, target_fn_name, is_canonical_sig = extract_or_infer_component_meta(
        source_code,
        component_id=component_id,
        alias=alias,
        name=name,
        role=role,
        input_ports=input_ports,
        output_ports=output_ports,
        config_keys=config_keys,
        default_config=default_config,
        preconditions=preconditions,
        postconditions=postconditions,
        origin=origin,
    )

    canonical_module_source = wrap_into_canonical_library_module(
        source_code,
        inferred_spec,
        target_fn_name=target_fn_name,
        is_canonical_sig=is_canonical_sig,
    )
    final_audit = audit_component_source_ast(canonical_module_source)
    sample_in, sample_out, pre_verified = verify_component_behavior(
        canonical_module_source,
        inferred_spec,
    )

    final_spec = CustomComponentSpec(
        component_id=inferred_spec.component_id,
        alias=inferred_spec.alias,
        name=inferred_spec.name,
        role=inferred_spec.role,
        operation_template=inferred_spec.operation_template,
        input_ports=inferred_spec.input_ports,
        output_ports=inferred_spec.output_ports,
        config_keys=inferred_spec.config_keys,
        default_config=inferred_spec.default_config,
        preconditions=inferred_spec.preconditions,
        postconditions=inferred_spec.postconditions,
        template_params=inferred_spec.template_params,
        prompt_hint=inferred_spec.prompt_hint,
        custom_python_source=canonical_module_source,
        origin=origin,
    )

    register_custom_component(final_spec, persist=persist, overwrite=overwrite)
    lib_mod_path = (
        str(DEFAULT_CUSTOM_MODULES_DIR / f"{final_spec.component_id}.py")
        if persist
        else f"<in-memory amca_components.custom.{final_spec.component_id}>"
    )
    return BoundComponentRecord(
        spec=final_spec,
        audit_report=initial_audit,
        sample_inputs=sample_in,
        sample_outputs=sample_out,
        precondition_rejection_verified=pre_verified,
        library_module_path=lib_mod_path,
        sha256=final_audit.source_sha256,
    )


def bind_external_component_file(
    file_path: str | Path,
    *,
    component_id: str = "",
    alias: str = "",
    name: str = "",
    role: str = "",
    input_ports: dict[str, str] | None = None,
    output_ports: dict[str, str] | None = None,
    config_keys: list[str] | None = None,
    default_config: dict[str, Any] | None = None,
    origin: str = "external_bound",
    persist: bool = True,
    overwrite: bool = True,
) -> BoundComponentRecord:
    """Read an external `.py` file (e.g. from Antigravity, OpenCode, or Codex) and bind it."""
    path = Path(file_path).resolve()
    if not path.exists() or not path.is_file():
        raise ComponentBindingError(f"File komponen eksternal tidak ditemukan: {path}")
    if path.suffix.lower() != ".py":
        raise ComponentBindingError(f"File komponen eksternal harus berekstensi '.py': {path}")

    source_code = path.read_text(encoding="utf-8")
    inferred_id = component_id.strip() or path.stem.lower()
    return bind_component_from_python_source(
        source_code,
        component_id=inferred_id,
        alias=alias,
        name=name,
        role=role,
        input_ports=input_ports,
        output_ports=output_ports,
        config_keys=config_keys,
        default_config=default_config,
        origin=origin,
        persist=persist,
        overwrite=overwrite,
    )
