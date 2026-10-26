"""AMCA Cumulative Registered Component Library (`amca_components`).

Provides a reusable, formally guarded Python component library called directly by constructed
machine scripts (`from amca_components import COMPONENT_DISPATCH, ContractViolationError, execute_library_component`).
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any, Callable

from .builtin import (
    BUILTIN_DISPATCH,
    run_aggregate_results,
    run_analysis_a,
    run_analysis_b,
    run_generate_report,
    run_input_source,
    run_validate_text,
)
from .contracts import (
    COMPONENT_CONTRACTS,
    ContractViolationError,
    _enforce_postconditions,
    _enforce_preconditions,
    enforce_postconditions,
    enforce_preconditions,
    register_contract,
)

PACKAGE_DIR = Path(__file__).resolve().parent
CUSTOM_MODULES_DIR = PACKAGE_DIR / "custom"
CATALOG_JSON_PATH = PACKAGE_DIR / "catalog.json"

ComponentCallable = Callable[[dict[str, Any], dict[str, Any], dict[str, Any]], dict[str, Any]]

COMPONENT_DISPATCH: dict[str, ComponentCallable] = dict(BUILTIN_DISPATCH)
CUSTOM_MODULE_SOURCES: dict[str, str] = {}
CUSTOM_MODULE_META: dict[str, dict[str, Any]] = {}


def _load_module_from_source(component_id: str, source_code: str) -> tuple[ComponentCallable, dict[str, Any]]:
    ns: dict[str, Any] = {
        "__name__": f"amca_components.custom.{component_id}",
        "ContractViolationError": ContractViolationError,
        "_enforce_preconditions": _enforce_preconditions,
        "_enforce_postconditions": _enforce_postconditions,
        "enforce_preconditions": enforce_preconditions,
        "enforce_postconditions": enforce_postconditions,
        "register_contract": register_contract,
    }
    exec(compile(source_code, f"<amca_components.custom.{component_id}>", "exec"), ns)
    meta = dict(ns.get("AMCA_COMPONENT_META", {}))
    fn_name = meta.get("entrypoint") or f"run_custom_{component_id}"
    fn = ns.get(fn_name) or ns.get(f"run_{component_id}") or ns.get("COMPONENT_ENTRYPOINT")
    if not callable(fn):
        for k, v in ns.items():
            if k.startswith("run_") and callable(v):
                fn = v
                break
    if not callable(fn):
        raise ValueError(f"Custom library module {component_id!r} does not define a callable run_<id> entrypoint.")
    return fn, meta


def load_bundled_custom_modules(custom_dir: Path | None = None) -> None:
    """Scan `amca_components/custom/*.py` and register all bundled custom component modules."""
    target_dir = custom_dir or CUSTOM_MODULES_DIR
    if not target_dir.is_dir():
        return
    for py_path in sorted(target_dir.glob("*.py")):
        if py_path.name == "__init__.py":
            continue
        cid = py_path.stem
        try:
            src = py_path.read_text(encoding="utf-8")
            fn, meta = _load_module_from_source(cid, src)
            resolved_id = str(meta.get("component_id", cid))
            COMPONENT_DISPATCH[resolved_id] = fn
            CUSTOM_MODULE_SOURCES[resolved_id] = src
            CUSTOM_MODULE_META[resolved_id] = meta
        except Exception:
            continue


def register_library_module(
    component_id: str,
    source_code: str,
    meta: dict[str, Any] | None = None,
    *,
    write_to_disk_dir: Path | None = None,
) -> ComponentCallable:
    """Register a verified Python component module into `amca_components` in-memory and optionally on disk."""
    fn, parsed_meta = _load_module_from_source(component_id, source_code)
    merged_meta = {**parsed_meta, **(meta or {}), "component_id": component_id}
    merged_meta["module_sha256"] = hashlib.sha256(source_code.encode("utf-8")).hexdigest()
    COMPONENT_DISPATCH[component_id] = fn
    CUSTOM_MODULE_SOURCES[component_id] = source_code
    CUSTOM_MODULE_META[component_id] = merged_meta
    if write_to_disk_dir is not None:
        write_to_disk_dir.mkdir(parents=True, exist_ok=True)
        (write_to_disk_dir / f"{component_id}.py").write_text(source_code, encoding="utf-8")
    return fn


def unregister_library_module(component_id: str, *, disk_dir: Path | None = None) -> None:
    if component_id in BUILTIN_DISPATCH:
        return
    COMPONENT_DISPATCH.pop(component_id, None)
    CUSTOM_MODULE_SOURCES.pop(component_id, None)
    CUSTOM_MODULE_META.pop(component_id, None)
    if disk_dir is not None:
        mod_file = disk_dir / f"{component_id}.py"
        if mod_file.is_file():
            mod_file.unlink()


def clear_custom_library_modules() -> None:
    COMPONENT_DISPATCH.clear()
    COMPONENT_DISPATCH.update(BUILTIN_DISPATCH)
    CUSTOM_MODULE_SOURCES.clear()
    CUSTOM_MODULE_META.clear()


def execute_library_component(
    component_id: str,
    inputs: dict[str, Any],
    config: dict[str, Any],
    raw_inputs: dict[str, Any],
) -> dict[str, Any]:
    """Execute any registered built-in or custom component from the AMCA Component Library."""
    if component_id not in COMPONENT_DISPATCH:
        raise KeyError(f"Component {component_id!r} is not registered in amca_components.COMPONENT_DISPATCH")
    return COMPONENT_DISPATCH[component_id](inputs, config, raw_inputs)


def get_library_catalog_snapshot() -> dict[str, Any]:
    return {
        "library_version": "0.3.0",
        "builtin_components": sorted(BUILTIN_DISPATCH.keys()),
        "custom_components": {
            cid: {
                **CUSTOM_MODULE_META.get(cid, {"component_id": cid}),
                "module_sha256": hashlib.sha256(CUSTOM_MODULE_SOURCES[cid].encode("utf-8")).hexdigest(),
            }
            for cid in sorted(CUSTOM_MODULE_SOURCES)
        },
    }


load_bundled_custom_modules()

__all__ = [
    "BUILTIN_DISPATCH",
    "COMPONENT_DISPATCH",
    "CUSTOM_MODULE_META",
    "CUSTOM_MODULE_SOURCES",
    "ContractViolationError",
    "_enforce_postconditions",
    "_enforce_preconditions",
    "clear_custom_library_modules",
    "enforce_postconditions",
    "enforce_preconditions",
    "execute_library_component",
    "get_library_catalog_snapshot",
    "load_bundled_custom_modules",
    "register_library_module",
    "run_aggregate_results",
    "run_analysis_a",
    "run_analysis_b",
    "run_generate_report",
    "run_input_source",
    "run_validate_text",
    "unregister_library_module",
]
