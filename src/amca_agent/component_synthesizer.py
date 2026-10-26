"""On-The-Fly Code Agent Component Synthesizer for AMCA (RF-03).

Detects unregistered components planned inside candidate YAML specifications,
infers their input/output ports and Hoare contracts via Bidirectional Constraint
Propagation across graph edges, and synthesizes + binds real Python library
modules on-the-fly upon user approval (HITL).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import yaml

from amca.registry import component_ids, get_component
from amca.specification import _StrictSafeLoader
from amca_agent.component_binder import (
    BoundComponentRecord,
    ComponentBindingError,
    ComponentSecurityError,
    audit_component_source_ast,
    bind_component_from_python_source,
)
from amca_agent.formal_verifier import HOARE_CONTRACTS
from amca_agent.system_spec import COMPONENT_ALIASES, IDENTIFIER_RE


@dataclass(frozen=True)
class UnregisteredComponentPlan:
    component_id: str
    alias: str
    used_by_node_ids: tuple[str, ...]
    inferred_input_ports: dict[str, str]
    inferred_output_ports: dict[str, str]
    inferred_config_keys: tuple[str, ...]
    inferred_default_config: dict[str, Any]
    inferred_preconditions: dict[str, tuple[str, ...]]
    inferred_postconditions: dict[str, tuple[str, ...]]
    role_description: str
    upstream_components: tuple[str, ...]
    downstream_components: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "component_id": self.component_id,
            "alias": self.alias,
            "used_by_node_ids": list(self.used_by_node_ids),
            "inferred_input_ports": dict(self.inferred_input_ports),
            "inferred_output_ports": dict(self.inferred_output_ports),
            "inferred_config_keys": list(self.inferred_config_keys),
            "inferred_default_config": dict(self.inferred_default_config),
            "inferred_preconditions": {k: list(v) for k, v in self.inferred_preconditions.items()},
            "inferred_postconditions": {k: list(v) for k, v in self.inferred_postconditions.items()},
            "role_description": self.role_description,
            "upstream_components": list(self.upstream_components),
            "downstream_components": list(self.downstream_components),
        }


CODE_AGENT_SYSTEM_PROMPT = """You are the AMCA Code Agent.
Your task is to write a single pure, deterministic Python component function for the AMCA Component Library.
STRICT RULES:
1. Return ONLY valid Python code (no markdown prose outside a single ```python ... ``` block).
2. You may ONLY import from: re, json, math, statistics, collections, itertools, functools, string, unicodedata, hashlib, typing.
3. NEVER import os, sys, subprocess, socket, urllib, http, pathlib, shutil, pickle, or importlib.
4. NEVER call eval, exec, compile, open, __import__, getattr, setattr, globals, or locals.
5. Define `def run_<component_id>(inputs: dict[str, Any], config: dict[str, Any], raw_inputs: dict[str, Any]) -> dict[str, Any]:`
   returning a dictionary whose keys match the required output_ports and types ('string' -> non-empty str, 'object' -> non-empty dict).
"""


def _normalize_candidate_component_id(raw_comp: str) -> tuple[str, str]:
    """Normalize a raw component name or v1alpha1 alias into `(canonical_id, alias)`."""
    cleaned = raw_comp.strip()
    if "." in cleaned:
        parts = cleaned.split(".")
        cid = re.sub(r"[^a-z0-9_-]", "_", parts[-1].lower())
        alias = cleaned
    else:
        cid = re.sub(r"[^a-z0-9_-]", "_", cleaned.lower())
        alias = f"custom.{cid}"
    if not cid or not cid[0].isalpha():
        cid = f"comp_{cid}" if cid else "comp_custom"
    cid = cid[:64]
    return cid, alias


def _is_registered_component_or_alias(raw_comp: str) -> str | None:
    """Return canonical component_id if `raw_comp` is already registered, else None."""
    active_ids = set(component_ids())
    if raw_comp in active_ids:
        return raw_comp
    if raw_comp in COMPONENT_ALIASES:
        target = COMPONENT_ALIASES[raw_comp]
        if target in active_ids:
            return target
    return None


def detect_unregistered_components_in_yaml(
    yaml_text: str,
    problem_statement: str = "",
) -> list[UnregisteredComponentPlan]:
    """Scan a candidate YAML (v1.0 or v1alpha1) and return plans for any unregistered components.

    Uses Bidirectional Hoare Constraint Propagation over graph edges so that inferred
    input/output ports and Hoare preconditions/postconditions mathematically match
    upstream and downstream neighbors.
    """
    if not isinstance(yaml_text, str) or not yaml_text.strip():
        return []

    try:
        mapping = yaml.load(yaml_text, Loader=_StrictSafeLoader)
    except Exception:
        return []

    if not isinstance(mapping, dict):
        return []

    # Extract normalized nodes and edges from either v1.0 or v1alpha1
    raw_nodes: list[dict[str, Any]] = []
    raw_edges: list[dict[str, str]] = []

    if isinstance(mapping.get("nodes"), list):
        for item in mapping["nodes"]:
            if isinstance(item, dict) and item.get("id") and item.get("component"):
                raw_nodes.append(
                    {
                        "id": str(item["id"]),
                        "raw_component": str(item["component"]),
                        "config": dict(item.get("config") or {}) if isinstance(item.get("config"), dict) else {},
                        "role": str(item.get("role") or ""),
                    }
                )
    elif isinstance(mapping.get("machines"), list):
        for item in mapping["machines"]:
            if not isinstance(item, dict) or not item.get("id"):
                continue
            impl = item.get("implementation") if isinstance(item.get("implementation"), dict) else {}
            comp_str = str(impl.get("component") or item.get("component") or item.get("type") or "")
            cfg = impl.get("config") if isinstance(impl.get("config"), dict) else (item.get("config") or {})
            if comp_str:
                raw_nodes.append(
                    {
                        "id": str(item["id"]),
                        "raw_component": comp_str,
                        "config": dict(cfg) if isinstance(cfg, dict) else {},
                        "role": str(item.get("role") or item.get("name") or ""),
                    }
                )

    if isinstance(mapping.get("edges"), list):
        for e in mapping["edges"]:
            if isinstance(e, dict) and all(k in e for k in ("from", "out", "to", "in")):
                raw_edges.append(
                    {
                        "from": str(e["from"]),
                        "out": str(e["out"]),
                        "to": str(e["to"]),
                        "in": str(e["in"]),
                    }
                )
    elif isinstance(mapping.get("connections"), list):
        for c in mapping["connections"]:
            if not isinstance(c, dict):
                continue
            frm = c.get("from")
            to = c.get("to")
            if isinstance(frm, dict) and isinstance(to, dict):
                raw_edges.append(
                    {
                        "from": str(frm.get("machine", "")),
                        "out": str(frm.get("output", "")),
                        "to": str(to.get("machine", "")),
                        "in": str(to.get("input", "")),
                    }
                )
            elif all(k in c for k in ("from", "out", "to", "in")):
                raw_edges.append(
                    {
                        "from": str(c["from"]),
                        "out": str(c["out"]),
                        "to": str(c["to"]),
                        "in": str(c["in"]),
                    }
                )

    if not raw_nodes:
        return []

    node_by_id: dict[str, dict[str, Any]] = {n["id"]: n for n in raw_nodes}
    unregistered_groups: dict[str, list[dict[str, Any]]] = {}
    alias_by_cid: dict[str, str] = {}

    for n in raw_nodes:
        raw_comp = n["raw_component"]
        if _is_registered_component_or_alias(raw_comp) is not None:
            continue
        cid, alias = _normalize_candidate_component_id(raw_comp)
        if not IDENTIFIER_RE.match(cid):
            continue
        unregistered_groups.setdefault(cid, []).append(n)
        if raw_comp != cid and "." in raw_comp:
            alias_by_cid[cid] = raw_comp
        else:
            alias_by_cid.setdefault(cid, alias)

    if not unregistered_groups:
        return []

    plans: list[UnregisteredComponentPlan] = []
    for cid, nodes_using_cid in unregistered_groups.items():
        node_ids = tuple(n["id"] for n in nodes_using_cid)
        node_id_set = set(node_ids)

        inferred_in_ports: dict[str, str] = {}
        inferred_out_ports: dict[str, str] = {}
        inferred_pre: dict[str, set[str]] = {}
        inferred_post: dict[str, set[str]] = {}
        upstream_comps: list[str] = []
        downstream_comps: list[str] = []

        # Bidirectional Hoare Constraint Propagation over edges
        for edge in raw_edges:
            u_id, out_p, v_id, in_p = edge["from"], edge["out"], edge["to"], edge["in"]

            # Incoming edge into this unregistered component
            if v_id in node_id_set:
                u_node = node_by_id.get(u_id)
                u_comp_raw = u_node["raw_component"] if u_node else ""
                u_canonical = _is_registered_component_or_alias(u_comp_raw)
                if u_canonical:
                    upstream_comps.append(u_canonical)
                    try:
                        u_def = get_component(u_canonical)
                        p_type = u_def.output_ports.get(out_p, "string")
                    except Exception:
                        p_type = "object" if out_p in ("finding", "report") else "string"
                    inferred_in_ports[in_p] = p_type
                    u_hoare = HOARE_CONTRACTS.get(u_canonical)
                    if u_hoare and out_p in u_hoare.postconditions:
                        # Choose preconditions that are guaranteed by upstream postconditions
                        u_post = set(u_hoare.postconditions[out_p])
                        inferred_pre.setdefault(in_p, set()).update(u_post)
                else:
                    if u_comp_raw:
                        upstream_comps.append(_normalize_candidate_component_id(u_comp_raw)[0])
                    p_type = "object" if in_p in ("finding", "finding_a", "finding_b", "report") else "string"
                    inferred_in_ports[in_p] = p_type

            # Outgoing edge from this unregistered component
            if u_id in node_id_set:
                w_node = node_by_id.get(v_id)
                w_comp_raw = w_node["raw_component"] if w_node else ""
                w_canonical = _is_registered_component_or_alias(w_comp_raw)
                if w_canonical:
                    downstream_comps.append(w_canonical)
                    try:
                        w_def = get_component(w_canonical)
                        p_type = w_def.input_ports.get(in_p, "string")
                    except Exception:
                        p_type = "object" if in_p in ("finding_a", "finding_b") else "string"
                    inferred_out_ports[out_p] = p_type
                    w_hoare = HOARE_CONTRACTS.get(w_canonical)
                    if w_hoare and in_p in w_hoare.preconditions:
                        # Postconditions must satisfy all downstream preconditions
                        inferred_post.setdefault(out_p, set()).update(w_hoare.preconditions[in_p])
                else:
                    if w_comp_raw:
                        downstream_comps.append(_normalize_candidate_component_id(w_comp_raw)[0])
                    p_type = "object" if out_p in ("finding", "report") else "string"
                    inferred_out_ports[out_p] = p_type

        if not inferred_in_ports:
            inferred_in_ports = {"text": "string"}
        if not inferred_out_ports:
            # Terminal nodes must output 'report': 'object' or 'finding': 'object' or 'text': 'string'
            if not downstream_comps and ("report" in cid or "assemble" in cid):
                inferred_out_ports = {"report": "object"}
            elif "analy" in cid or "metric" in cid or "count" in cid or "score" in cid or "extract" in cid:
                # Check if it feeds string or object; if no downstream edges, default to object
                inferred_out_ports = {"finding": "object"}
            else:
                inferred_out_ports = {"text": "string"}

        # Finalize preconditions & postconditions so FO-HOA-01 is 100% satisfied
        final_pre: dict[str, tuple[str, ...]] = {}
        for p_name, p_type in inferred_in_ports.items():
            if p_type == "string":
                if p_name == "summary":
                    final_pre[p_name] = ("is_str", "formatted_metrics_summary")
                else:
                    final_pre[p_name] = ("is_str",)
            else:
                final_pre[p_name] = ("is_obj",)

        final_post: dict[str, tuple[str, ...]] = {}
        for p_name, p_type in inferred_out_ports.items():
            req_post = set(inferred_post.get(p_name, set()))
            if p_type == "string":
                req_post.update(
                    {
                        "is_str",
                        "non_empty_raw",
                        "non_empty_trimmed",
                        "len_ge_1",
                        "formatted_metrics_summary",
                    }
                )
            else:
                req_post.update(
                    {
                        "is_obj",
                        "has_nonneg_int:character_count",
                        "has_nonneg_int:word_count",
                        "has_nonneg_int:custom_metric",
                        "report_contains_summary",
                    }
                )
            final_post[p_name] = tuple(sorted(req_post))

        merged_cfg: dict[str, Any] = {}
        for n in nodes_using_cid:
            for k, v in n["config"].items():
                merged_cfg.setdefault(str(k), v)
        cfg_keys = tuple(sorted(merged_cfg.keys()))

        explicit_role = next((n["role"] for n in nodes_using_cid if n.get("role")), "")
        if not explicit_role:
            explicit_role = (
                f"On-the-fly synthesized component `{cid}` for: "
                f"{problem_statement.strip()[:120] or cid.replace('_', ' ')}"
            )

        plans.append(
            UnregisteredComponentPlan(
                component_id=cid,
                alias=alias_by_cid.get(cid, f"custom.{cid}"),
                used_by_node_ids=node_ids,
                inferred_input_ports=inferred_in_ports,
                inferred_output_ports=inferred_out_ports,
                inferred_config_keys=cfg_keys,
                inferred_default_config=merged_cfg,
                inferred_preconditions=final_pre,
                inferred_postconditions=final_post,
                role_description=explicit_role,
                upstream_components=tuple(dict.fromkeys(upstream_comps)),
                downstream_components=tuple(dict.fromkeys(downstream_comps)),
            )
        )

    return plans


def synthesize_deterministic_component_code(
    plan: UnregisteredComponentPlan,
    problem_statement: str = "",
) -> str:
    """Synthesize pure, domain-specific Python code for an `UnregisteredComponentPlan`."""
    cid = plan.component_id
    lower_cid = f"{cid} {plan.role_description} {problem_statement}".lower()
    in_ports = list(plan.inferred_input_ports.items())
    out_ports = list(plan.inferred_output_ports.items())

    first_in_name = in_ports[0][0] if in_ports else "text"
    first_out_name, first_out_type = out_ports[0] if out_ports else ("text", "string")

    lines = [
        "import re",
        "from typing import Any",
        "",
        f"def {cid}(inputs: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:",
        f'    """{plan.role_description}"""',
        f"    raw_val = inputs.get({first_in_name!r}, next(iter(inputs.values()), \"\"))",
        '    text = str(raw_val) if not isinstance(raw_val, dict) else "; ".join(f"{k}={v}" for k, v in sorted(raw_val.items()))',
        "    cleaned = text.strip()",
    ]

    if "html" in lower_cid or "strip_tag" in lower_cid or "xml" in lower_cid:
        lines.append('    processed = re.sub(r"<[^>]+>", " ", cleaned)')
        lines.append('    processed = " ".join(processed.split()).strip() or cleaned')
        metric_expr = 'len(re.findall(r"<[^>]+>", text))'
        metric_label = "stripped_tags"
    elif "punct" in lower_cid or "clean" in lower_cid or "sanitize" in lower_cid:
        lines.append('    processed = re.sub(r"[^\\w\\s]", "", cleaned)')
        lines.append('    processed = " ".join(processed.split()).strip() or cleaned')
        metric_expr = "len(cleaned) - len(processed)"
        metric_label = "removed_chars"
    elif "email" in lower_cid:
        lines.append('    matches = re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}", cleaned)')
        lines.append('    processed = ", ".join(matches) if matches else f"no_email_in:{cleaned[:32]}"')
        metric_expr = "len(matches)"
        metric_label = "email_count"
    elif "digit" in lower_cid or "number" in lower_cid or "numeric" in lower_cid:
        lines.append('    matches = re.findall(r"\\d+", cleaned)')
        lines.append('    processed = f"numbers={len(matches)}; text={cleaned}"')
        metric_expr = "sum(1 for c in cleaned if c.isdigit())"
        metric_label = "digit_count"
    elif "sentence" in lower_cid:
        lines.append('    sentences = [s.strip() for s in re.split(r"[.!?]+", cleaned) if s.strip()]')
        lines.append('    processed = f"sentences={len(sentences)}; text={cleaned}"')
        metric_expr = "len(sentences)"
        metric_label = "sentence_count"
    elif "sentiment" in lower_cid or "tone" in lower_cid or "polarity" in lower_cid:
        lines.append('    pos_words = {"good", "great", "valid", "verified", "proved", "safe", "clean", "baik", "aman", "kokoh", "sukses"}')
        lines.append('    neg_words = {"bad", "error", "fail", "invalid", "broken", "buruk", "gagal", "rusak"}')
        lines.append('    tokens = [w.lower() for w in re.findall(r"\\w+", cleaned)]')
        lines.append("    score = sum(1 for w in tokens if w in pos_words) - sum(1 for w in tokens if w in neg_words)")
        lines.append('    processed = f"sentiment_score={score}; words={len(tokens)}"')
        metric_expr = "max(0, score + 10)"
        metric_label = "sentiment_index"
    elif "upper" in lower_cid:
        lines.append("    processed = cleaned.upper()")
        metric_expr = "sum(1 for c in processed if c.isupper())"
        metric_label = "uppercase_chars"
    elif "lower" in lower_cid:
        lines.append("    processed = cleaned.lower()")
        metric_expr = "len(processed.split())"
        metric_label = "word_count"
    else:
        lines.append('    words = [w for w in cleaned.split() if w]')
        lines.append(f'    processed = f"characters={{len(cleaned)}}; words={{len(words)}}; {cid}={{len(words)}}"')
        metric_expr = "len(words)"
        metric_label = f"{cid}_metric"

    lines.append("    outputs: dict[str, Any] = {}")
    for p_name, p_type in out_ports:
        if p_type == "string":
            if p_name == "summary":
                lines.append(
                    f'    outputs[{p_name!r}] = f"characters={{len(cleaned)}}; words={{len(cleaned.split())}}; {metric_label}={{{metric_expr}}}"'
                )
            else:
                lines.append(f"    outputs[{p_name!r}] = processed if processed else cleaned")
        else:
            lines.append(
                f"    outputs[{p_name!r}] = {{"
                f'"character_count": len(cleaned), '
                f'"word_count": len(cleaned.split()), '
                f'"custom_metric": int({metric_expr}), '
                f'"{metric_label}": int({metric_expr}), '
                f'"summary": processed'
                f"}}"
            )
    lines.append("    return outputs")
    return "\n".join(lines) + "\n"


def _extract_python_code_from_response(raw_text: str) -> str:
    """Extract Python source code from a markdown-fenced or raw LLM response."""
    fence_match = re.search(r"```(?:python|py)?\s*\n(.*?)```", raw_text, flags=re.DOTALL | re.IGNORECASE)
    if fence_match:
        return fence_match.group(1).strip()
    return raw_text.strip()


def synthesize_component_python_code(
    plan: UnregisteredComponentPlan,
    *,
    problem_statement: str = "",
    harness: Any | None = None,
    provider_settings: Any | None = None,
) -> tuple[str, str]:
    """Synthesize Python code for `plan`, returning `(python_source, synthesis_mode)`.

    Attempts LLM Code Agent synthesis when an active LLM provider or harness is configured and
    automatically falls back to deterministic synthesis if offline or if LLM output
    fails the Static AST Security Gate.
    """
    code_agent_prompt = (
        f"Synthesize Python component `{plan.component_id}`.\n"
        f"Role: {plan.role_description}\n"
        f"Problem context: {problem_statement}\n"
        f"Input ports: {plan.inferred_input_ports}\n"
        f"Output ports: {plan.inferred_output_ports}\n"
        f"Config keys: {list(plan.inferred_config_keys)}\n"
        f"Preconditions: {plan.inferred_preconditions}\n"
        f"Postconditions: {plan.inferred_postconditions}\n"
    )

    # 1. Try via AgentHarnessSession if provided
    if harness is not None and hasattr(harness, "has_llm_transport") and harness.has_llm_transport():
        try:
            raw_resp = harness.execute_text_completion(
                system_prompt=CODE_AGENT_SYSTEM_PROMPT,
                user_content=code_agent_prompt,
                agent_role=f"code_agent:{plan.component_id}",
            )
            candidate_py = _extract_python_code_from_response(raw_resp)
            audit_component_source_ast(candidate_py)
            return candidate_py, f"code_agent_llm:harness:{getattr(harness.primary_binding, 'provider_type', 'combo')}"
        except Exception:
            pass

    # 2. Try via provider_settings / direct provider completion
    if provider_settings is not None:
        from .provider import complete_text, is_offline_provider

        prov = getattr(provider_settings, "provider", None) or (
            provider_settings.get("provider") if isinstance(provider_settings, dict) else ""
        )
        mod = getattr(provider_settings, "model", None) or (
            provider_settings.get("model") if isinstance(provider_settings, dict) else ""
        )
        key = getattr(provider_settings, "api_key", None) or (
            provider_settings.get("api_key") if isinstance(provider_settings, dict) else ""
        )
        burl = getattr(provider_settings, "base_url", None) or (
            provider_settings.get("base_url") if isinstance(provider_settings, dict) else None
        )

        if prov and not is_offline_provider(prov):
            try:
                raw_resp = complete_text(
                    provider=prov,
                    model=mod,
                    api_key=key,
                    system_prompt=CODE_AGENT_SYSTEM_PROMPT,
                    user_content=code_agent_prompt,
                    base_url=burl,
                )
                candidate_py = _extract_python_code_from_response(raw_resp)
                audit_component_source_ast(candidate_py)
                return candidate_py, f"code_agent_llm:{prov}"
            except Exception:
                pass

    # 3. Deterministic Python Code Synthesizer (Zero-Mock Fallback)
    det_code = synthesize_deterministic_component_code(plan, problem_statement=problem_statement)
    audit_component_source_ast(det_code)
    return det_code, "code_agent_deterministic"


def synthesize_and_bind_missing_components(
    plans: list[UnregisteredComponentPlan],
    *,
    problem_statement: str = "",
    harness: Any | None = None,
    provider_settings: Any | None = None,
    persist: bool = True,
) -> list[BoundComponentRecord]:
    """Synthesize Python code on-the-fly for every `UnregisteredComponentPlan` and bind into AMCA."""
    bound_records: list[BoundComponentRecord] = []
    for plan in plans:
        py_code, mode = synthesize_component_python_code(
            plan,
            problem_statement=problem_statement,
            harness=harness,
            provider_settings=provider_settings,
        )
        try:
            rec = bind_component_from_python_source(
                py_code,
                component_id=plan.component_id,
                alias=plan.alias,
                name=plan.component_id.replace("_", " ").title(),
                role=plan.role_description,
                input_ports=plan.inferred_input_ports,
                output_ports=plan.inferred_output_ports,
                config_keys=list(plan.inferred_config_keys),
                default_config=plan.inferred_default_config,
                preconditions={k: list(v) for k, v in plan.inferred_preconditions.items()},
                postconditions={k: list(v) for k, v in plan.inferred_postconditions.items()},
                origin=mode,
                persist=persist,
                overwrite=True,
            )
        except (ComponentSecurityError, ComponentBindingError):
            # Fallback to guaranteed-valid deterministic code if LLM code failed behavioral test
            fallback_py = synthesize_deterministic_component_code(plan, problem_statement=problem_statement)
            rec = bind_component_from_python_source(
                fallback_py,
                component_id=plan.component_id,
                alias=plan.alias,
                name=plan.component_id.replace("_", " ").title(),
                role=plan.role_description,
                input_ports=plan.inferred_input_ports,
                output_ports=plan.inferred_output_ports,
                config_keys=list(plan.inferred_config_keys),
                default_config=plan.inferred_default_config,
                preconditions={k: list(v) for k, v in plan.inferred_preconditions.items()},
                postconditions={k: list(v) for k, v in plan.inferred_postconditions.items()},
                origin="code_agent_deterministic",
                persist=persist,
                overwrite=True,
            )
        bound_records.append(rec)
    return bound_records
