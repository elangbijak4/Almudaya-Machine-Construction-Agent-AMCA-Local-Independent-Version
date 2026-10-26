"""Specialized Agent Harness: Multi-Provider Binding, 9Router & Combo Token-Limit Fallback, and On-The-Fly Subworker HITL."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from amca_agent.hardware import (
    HardwareEligibilityReport,
    HostHardwareSnapshot,
    evaluate_local_model_eligibility,
)
from amca_agent.provider import ProviderError, complete_text, generate_yaml, is_offline_provider

SUPPORTED_PROVIDER_TYPES: tuple[str, ...] = (
    "gemini",
    "xai",
    "openai",
    "anthropic",
    "openai_compatible",
    "nine_router",
    "ollama",
    "lm_studio",
    "opencode",
    "local_model",
    "amca_combo",
    "offline_deterministic",
)

FALLBACK_TRIGGER_REASONS: frozenset[str] = frozenset(
    {
        "token_limit_exceeded",
        "output_truncated_length",
        "rate_limit_429",
        "quota_or_credit_exhausted",
        "upstream_unavailable",
    }
)


@dataclass(frozen=True)
class ModelBinding:
    agent_role: str  # e.g. "amca_primary", "subworker:spec_auditor", "combo_tier:1"
    provider_type: str
    model_id: str
    base_url: str | None = None
    credential_source: str = "session_memory_distinct_key"
    hardware_check_id: str | None = None

    def as_sanitized_dict(self) -> dict[str, Any]:
        """Serialize binding metadata WITHOUT any secret API key."""
        return {
            "agent_role": self.agent_role,
            "provider_type": self.provider_type,
            "model_id": self.model_id,
            "base_url": self.base_url,
            "credential_source": self.credential_source,
            "hardware_check_id": self.hardware_check_id,
        }

    as_dict = as_sanitized_dict


@dataclass(frozen=True)
class FallbackTransitionEvent:
    combo_id: str
    agent_role: str
    from_tier: int
    from_provider: str
    from_model: str
    to_tier: int
    to_provider: str
    to_model: str
    trigger_reason: str
    context_compacted: bool
    timestamp: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "event_type": "fallback_transition",
            "timestamp": self.timestamp,
            "agent_role": self.agent_role,
            "combo_id": self.combo_id,
            "from_tier": self.from_tier,
            "from_provider": self.from_provider,
            "from_model": self.from_model,
            "to_tier": self.to_tier,
            "to_provider": self.to_provider,
            "to_model": self.to_model,
            "trigger_reason": self.trigger_reason,
            "context_compacted": self.context_compacted,
        }


@dataclass(frozen=True)
class FallbackComboChain:
    combo_id: str
    tiers: tuple[ModelBinding, ...]

    def as_sanitized_dict(self) -> dict[str, Any]:
        return {
            "combo_id": self.combo_id,
            "tiers": [
                {"tier": idx, **binding.as_sanitized_dict()}
                for idx, binding in enumerate(self.tiers, 1)
            ],
        }

    as_dict = as_sanitized_dict


@dataclass(frozen=True)
class SubworkerProposal:
    subworker_id: str
    role: str
    task_description: str
    rationale: str
    recommended_provider: str = "nine_router"
    recommended_model: str = "free-combo"

    def as_dict(self) -> dict[str, str]:
        return {
            "subworker_id": self.subworker_id,
            "role": self.role,
            "task_description": self.task_description,
            "rationale": self.rationale,
            "recommended_provider": self.recommended_provider,
            "recommended_model": self.recommended_model,
        }


@dataclass(frozen=True)
class SubworkerApprovalRecord:
    session_id: str
    subworker_id: str
    role: str
    task_description: str
    rationale: str
    decision: str  # "APPROVED" | "DECLINED"
    model_binding: ModelBinding | None
    credential_isolated_from_primary: bool
    approved_by: str
    approved_at: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "approval_type": "subworker_hitl_approval",
            "session_id": self.session_id,
            "subworker_id": self.subworker_id,
            "role": self.role,
            "task_description": self.task_description,
            "rationale": self.rationale,
            "decision": self.decision,
            "model_binding": self.model_binding.as_sanitized_dict() if self.model_binding else None,
            "credential_isolated_from_primary": self.credential_isolated_from_primary,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at,
        }


class SessionCredentialVault:
    """Volatile in-memory store isolating API keys between Primary Agent, Combo Tiers, and Subworkers."""

    def __init__(self) -> None:
        self._keys: dict[str, str] = {}

    def set_key(self, role_key: str, api_key: str) -> None:
        self._keys[role_key] = api_key

    def get_key(self, role_key: str) -> str:
        return self._keys.get(role_key, "")

    def is_distinct_from_primary(self, role_key: str) -> bool:
        sub_key = self.get_key(role_key)
        prim_key = self.get_key("amca_primary")
        if not sub_key:
            return True
        return sub_key != prim_key

    def active_secret_values(self) -> list[str]:
        return [v for v in self._keys.values() if v and len(v.strip()) >= 4]

    def redact_text(self, text: str) -> str:
        cleaned = text
        for secret in self.active_secret_values():
            cleaned = cleaned.replace(secret, "[REDACTED_SESSION_KEY]")
        return cleaned


def compact_context_for_token_limit(
    history: list[dict[str, str]],
    *,
    current_yaml: str = "",
    diagnostics: list[str] | None = None,
) -> tuple[list[dict[str, str]], str, list[str]]:
    """Smart Token-Limit Context Compaction: prune verbose older chat turns while preserving canonical YAML & counterexamples."""
    compacted_history = [
        {"role": item["role"], "content": item["content"][:1_200]}
        for item in history[-2:]
    ]
    compacted_yaml = current_yaml[:32_768] if current_yaml else ""
    compacted_diag = [d[:500] for d in (diagnostics or [])[:6]]
    return compacted_history, compacted_yaml, compacted_diag


@dataclass
class AgentHarnessSession:
    session_id: str = field(default_factory=lambda: "session-default")
    vault: SessionCredentialVault = field(default_factory=SessionCredentialVault)
    primary_binding: ModelBinding = field(
        default_factory=lambda: ModelBinding(
            agent_role="amca_primary",
            provider_type="offline_deterministic",
            model_id="builtin-v1",
        )
    )
    combo_chains: dict[str, FallbackComboChain] = field(default_factory=dict)
    subworker_bindings: dict[str, ModelBinding] = field(default_factory=dict)
    subworker_approvals: dict[str, SubworkerApprovalRecord] = field(default_factory=dict)
    pending_subworker_proposals: dict[str, SubworkerProposal] = field(default_factory=dict)
    fallback_events: list[FallbackTransitionEvent] = field(default_factory=list)
    hardware_reports: list[HardwareEligibilityReport] = field(default_factory=list)

    def configure_primary_agent(
        self,
        *,
        provider_type: str,
        model_id: str,
        api_key: str = "",
        base_url: str | None = None,
        hardware: HostHardwareSnapshot | None = None,
    ) -> ModelBinding:
        norm = provider_type.strip().lower()
        hw_check_id = None
        if norm in {"local_model", "local model"}:
            report = evaluate_local_model_eligibility(model_id, hardware=hardware)
            self.hardware_reports.append(report)
            if not report.eligible:
                raise PermissionError(
                    f"Model lokal {model_id!r} ditolak karena spesifikasi laptop tidak mencukupi: {'; '.join(report.reasons)}"
                )
            hw_check_id = report.snapshot.inspection_timestamp

        binding = ModelBinding(
            agent_role="amca_primary",
            provider_type=provider_type,
            model_id=model_id,
            base_url=base_url,
            credential_source="session_memory_primary_key" if api_key else "none",
            hardware_check_id=hw_check_id,
        )
        self.primary_binding = binding
        self.vault.set_key("amca_primary", api_key)
        return binding

    def register_combo_chain(
        self,
        combo_id: str,
        tier_specs: list[dict[str, Any]],
        *,
        set_as_primary: bool = True,
    ) -> FallbackComboChain:
        """Register an ordered 9Router-style Combo fallback chain (Tier 1 -> Tier 2 -> ... -> Tier N)."""
        if not tier_specs:
            raise ValueError("Combo fallback chain requires at least 1 tier.")
        tiers: list[ModelBinding] = []
        for idx, spec in enumerate(tier_specs, 1):
            role = f"combo:{combo_id}:tier:{idx}"
            prov = str(spec["provider_type"])
            mod = str(spec["model_id"])
            burl = spec.get("base_url")
            key = str(spec.get("api_key", ""))
            self.vault.set_key(role, key)
            tiers.append(
                ModelBinding(
                    agent_role=role,
                    provider_type=prov,
                    model_id=mod,
                    base_url=burl,
                    credential_source="session_memory_combo_tier_key" if key else "none",
                )
            )
        chain = FallbackComboChain(combo_id=combo_id, tiers=tuple(tiers))
        self.combo_chains[combo_id] = chain
        if set_as_primary:
            self.primary_binding = ModelBinding(
                agent_role="amca_primary",
                provider_type="amca_combo",
                model_id=combo_id,
            )
        return chain

    def request_subworker_hitl(self, proposal: SubworkerProposal) -> SubworkerProposal:
        """Pause and register an On-The-Fly Subworker proposal requiring Human-in-the-Loop approval."""
        self.pending_subworker_proposals[proposal.subworker_id] = proposal
        return proposal

    def approve_subworker_hitl(
        self,
        subworker_id: str,
        *,
        provider_type: str,
        model_id: str,
        api_key: str = "",
        base_url: str | None = None,
        approved_by: str = "user",
        hardware: HostHardwareSnapshot | None = None,
    ) -> SubworkerApprovalRecord:
        if subworker_id not in self.pending_subworker_proposals:
            raise KeyError(f"Unknown pending subworker proposal: {subworker_id}")
        proposal = self.pending_subworker_proposals.pop(subworker_id)
        norm = provider_type.strip().lower()
        hw_check_id = None
        if norm in {"local_model", "local model"}:
            report = evaluate_local_model_eligibility(model_id, hardware=hardware)
            self.hardware_reports.append(report)
            if not report.eligible:
                raise PermissionError(
                    f"Model lokal untuk Subworker {subworker_id!r} ditolak: {'; '.join(report.reasons)}"
                )
            hw_check_id = report.snapshot.inspection_timestamp

        role_key = f"subworker:{subworker_id}"
        self.vault.set_key(role_key, api_key)
        isolated = self.vault.is_distinct_from_primary(role_key)
        binding = ModelBinding(
            agent_role=role_key,
            provider_type=provider_type,
            model_id=model_id,
            base_url=base_url,
            credential_source="session_memory_distinct_subworker_key" if isolated else "session_memory_shared_key",
            hardware_check_id=hw_check_id,
        )
        self.subworker_bindings[subworker_id] = binding
        record = SubworkerApprovalRecord(
            session_id=self.session_id,
            subworker_id=subworker_id,
            role=proposal.role,
            task_description=proposal.task_description,
            rationale=proposal.rationale,
            decision="APPROVED",
            model_binding=binding,
            credential_isolated_from_primary=isolated,
            approved_by=approved_by,
            approved_at=datetime.now(timezone.utc).isoformat(),
        )
        self.subworker_approvals[subworker_id] = record
        return record

    def decline_subworker_hitl(
        self,
        subworker_id: str,
        *,
        approved_by: str = "user",
    ) -> SubworkerApprovalRecord:
        if subworker_id not in self.pending_subworker_proposals:
            raise KeyError(f"Unknown pending subworker proposal: {subworker_id}")
        proposal = self.pending_subworker_proposals.pop(subworker_id)
        record = SubworkerApprovalRecord(
            session_id=self.session_id,
            subworker_id=subworker_id,
            role=proposal.role,
            task_description=proposal.task_description,
            rationale=proposal.rationale,
            decision="DECLINED",
            model_binding=None,
            credential_isolated_from_primary=True,
            approved_by=approved_by,
            approved_at=datetime.now(timezone.utc).isoformat(),
        )
        self.subworker_approvals[subworker_id] = record
        return record

    def execute_yaml_generation(
        self,
        prompt: str,
        *,
        history: list[dict[str, str]],
        current_yaml: str = "",
        diagnostics: list[str] | None = None,
        subworker_id: str | None = None,
    ) -> str:
        """Execute YAML generation/revision via Primary Agent, Approved Subworker, or Combo Fallback Chain."""
        if subworker_id:
            approval = self.subworker_approvals.get(subworker_id)
            if approval and approval.decision == "APPROVED" and approval.model_binding:
                active_binding = approval.model_binding
                agent_role = f"subworker:{subworker_id}"
            else:
                # Declined or unapproved subworker falls back cleanly to Primary Agent
                active_binding = self.primary_binding
                agent_role = "amca_primary"
        else:
            active_binding = self.primary_binding
            agent_role = "amca_primary"

        if active_binding.provider_type.strip().lower() in {"amca_combo", "combo"}:
            chain = self.combo_chains.get(active_binding.model_id)
            if not chain:
                raise ProviderError(f"Combo fallback chain {active_binding.model_id!r} belum terdaftar.")
            return self._execute_combo_chain(
                chain,
                agent_role=agent_role,
                prompt=prompt,
                history=history,
                current_yaml=current_yaml,
                diagnostics=diagnostics,
            )

        key = self.vault.get_key(active_binding.agent_role)
        return generate_yaml(
            provider=active_binding.provider_type,
            model=active_binding.model_id,
            api_key=key,
            prompt=prompt,
            history=history,
            current_yaml=current_yaml,
            base_url=active_binding.base_url,
            diagnostics=diagnostics,
        )

    def _execute_combo_chain(
        self,
        chain: FallbackComboChain,
        *,
        agent_role: str,
        prompt: str,
        history: list[dict[str, str]],
        current_yaml: str,
        diagnostics: list[str] | None,
    ) -> str:
        active_history = list(history)
        active_yaml = current_yaml
        active_diag = list(diagnostics or [])
        last_error: ProviderError | None = None

        for idx, tier in enumerate(chain.tiers, 1):
            key = self.vault.get_key(tier.agent_role)
            try:
                return generate_yaml(
                    provider=tier.provider_type,
                    model=tier.model_id,
                    api_key=key,
                    prompt=prompt,
                    history=active_history,
                    current_yaml=active_yaml,
                    base_url=tier.base_url,
                    diagnostics=active_diag,
                )
            except ProviderError as exc:
                last_error = exc
                trigger = exc.trigger_reason or "upstream_unavailable"
                compacted = False
                if trigger in {"token_limit_exceeded", "output_truncated_length"}:
                    active_history, active_yaml, active_diag = compact_context_for_token_limit(
                        active_history,
                        current_yaml=active_yaml,
                        diagnostics=active_diag,
                    )
                    compacted = True

                if idx < len(chain.tiers):
                    next_tier = chain.tiers[idx]
                    self.fallback_events.append(
                        FallbackTransitionEvent(
                            combo_id=chain.combo_id,
                            agent_role=agent_role,
                            from_tier=idx,
                            from_provider=tier.provider_type,
                            from_model=tier.model_id,
                            to_tier=idx + 1,
                            to_provider=next_tier.provider_type,
                            to_model=next_tier.model_id,
                            trigger_reason=trigger,
                            context_compacted=compacted,
                            timestamp=datetime.now(timezone.utc).isoformat(),
                        )
                    )
                    continue
                raise

        if last_error is not None:
            raise last_error
        raise ProviderError("Rantai fallback Combo tidak memiliki tier yang berhasil.")

    def has_llm_transport(self) -> bool:
        """Return True when the primary binding (or any Combo tier) points to a real LLM provider."""
        binding = self.primary_binding
        if binding.provider_type.strip().lower() in {"amca_combo", "combo"}:
            chain = self.combo_chains.get(binding.model_id)
            return bool(chain) and any(not is_offline_provider(t.provider_type) for t in chain.tiers)
        return not is_offline_provider(binding.provider_type)

    def execute_text_completion(
        self,
        system_prompt: str,
        user_content: str,
        *,
        agent_role: str = "amca_code_agent",
    ) -> str:
        """Run a raw system+user completion via the Primary binding or its Combo fallback chain.

        Used by the On-The-Fly Code Agent. Applies the same fallback triggers as YAML generation
        and compacts `user_content` on token-limit triggers.
        """
        binding = self.primary_binding
        if binding.provider_type.strip().lower() in {"amca_combo", "combo"}:
            chain = self.combo_chains.get(binding.model_id)
            if not chain:
                raise ProviderError(f"Combo fallback chain {binding.model_id!r} belum terdaftar.")
            tiers: tuple[ModelBinding, ...] = chain.tiers
            combo_id = chain.combo_id
        else:
            tiers = (binding,)
            combo_id = "single"

        active_content = user_content
        last_error: ProviderError | None = None
        for idx, tier in enumerate(tiers, 1):
            try:
                return complete_text(
                    provider=tier.provider_type,
                    model=tier.model_id,
                    api_key=self.vault.get_key(tier.agent_role),
                    system_prompt=system_prompt,
                    user_content=active_content,
                    base_url=tier.base_url,
                )
            except ProviderError as exc:
                last_error = exc
                trigger = exc.trigger_reason or "upstream_unavailable"
                compacted = False
                if trigger in {"token_limit_exceeded", "output_truncated_length"}:
                    active_content = active_content[:4_000]
                    compacted = True
                if idx < len(tiers):
                    next_tier = tiers[idx]
                    self.fallback_events.append(
                        FallbackTransitionEvent(
                            combo_id=combo_id,
                            agent_role=agent_role,
                            from_tier=idx,
                            from_provider=tier.provider_type,
                            from_model=tier.model_id,
                            to_tier=idx + 1,
                            to_provider=next_tier.provider_type,
                            to_model=next_tier.model_id,
                            trigger_reason=trigger,
                            context_compacted=compacted,
                            timestamp=datetime.now(timezone.utc).isoformat(),
                        )
                    )
                    continue
                raise
        if last_error is not None:
            raise last_error
        raise ProviderError("Tidak ada tier model yang tersedia untuk Code Agent.")

    def audit_metadata(self) -> dict[str, Any]:
        """Return non-secret metadata suitable for session.json and construction-log.jsonl."""
        return {
            "session_id": self.session_id,
            "primary_binding": self.primary_binding.as_dict(),
            "combo_chains": {k: v.as_dict() for k, v in self.combo_chains.items()},
            "subworker_approvals": {k: v.as_dict() for k, v in self.subworker_approvals.items()},
            "fallback_events": [e.as_dict() for e in self.fallback_events],
            "hardware_reports": [r.as_dict() for r in self.hardware_reports],
        }

