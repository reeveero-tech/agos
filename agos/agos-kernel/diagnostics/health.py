"""Kernel health service (R-F-008).

Produces a :class:`KernelHealthReport` from the kernel's *real* registries — every check
inspects actual state; nothing reports health it did not verify (R-Q-008):

* ``capabilities_loaded``  — at least one capability is registered
* ``providers_loaded``     — at least one provider is registered
* ``contracts``            — every capability/provider passes ``ContractEngine``
* ``skill_coverage``       — every skill a capability declares is supported by some
  provider; skills a capability still performs inline are reported (DEGRADED), not hidden

Status: any failed *critical* check → UNHEALTHY; otherwise any failed check → DEGRADED;
otherwise HEALTHY. ``HealthStatus``/``HealthCheck`` are the existing types from
``observability`` (one vocabulary, no duplicate).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

from observability import HealthCheck, HealthStatus

__all__ = ["KernelHealthService", "KernelHealthReport", "HealthStatus", "HealthCheck"]

CRITICAL_CHECKS = ("capabilities_loaded", "providers_loaded", "contracts")


@dataclass
class KernelHealthReport:
    """Outcome of one health evaluation."""

    status: HealthStatus
    checks: List[HealthCheck] = field(default_factory=list)
    capabilities: List[str] = field(default_factory=list)
    providers: List[str] = field(default_factory=list)
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def healthy(self) -> bool:
        return self.status == HealthStatus.HEALTHY

    def failed_checks(self) -> List[HealthCheck]:
        return [c for c in self.checks if c.status != HealthStatus.HEALTHY]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "generated_at": self.generated_at.isoformat(),
            "capabilities": list(self.capabilities),
            "providers": list(self.providers),
            "checks": [{"name": c.name, "status": c.status.value, "message": c.message,
                        "details": c.details} for c in self.checks],
        }


def _components(registry: Any) -> List[Any]:
    if registry is None:
        return []
    if hasattr(registry, "list_all"):
        return list(registry.list_all())
    if isinstance(registry, Iterable):
        return list(registry)
    return []


class KernelHealthService:
    """Evaluates kernel health from its registries."""

    def __init__(self, contract_engine: Optional[Any] = None):
        self._contract_engine = contract_engine

    def _engine(self):
        if self._contract_engine is None:
            from contract_engine import ContractEngine
            self._contract_engine = ContractEngine()
        return self._contract_engine

    def generate_report(self, capability_registry: Any, skill_registry: Any = None,
                        provider_registry: Any = None) -> KernelHealthReport:
        """Evaluate health.

        ``skill_registry`` is the source of declared skills: any registry/iterable whose
        items expose ``.skills`` (the capability registry itself is the usual source —
        the historical call is ``generate_report(caps, caps, providers)``). When omitted,
        the capability registry is used.
        """
        from contract_engine import ContractType

        capabilities = _components(capability_registry)
        providers = _components(provider_registry)
        skill_sources = _components(skill_registry) if skill_registry is not None else capabilities
        checks: List[HealthCheck] = []

        def check(name: str, ok: bool, message: str, **details: Any) -> None:
            checks.append(HealthCheck(name=name,
                                      status=HealthStatus.HEALTHY if ok else HealthStatus.UNHEALTHY,
                                      message=message, details=details))

        check("capabilities_loaded", bool(capabilities), f"{len(capabilities)} capabilities registered",
              count=len(capabilities))
        check("providers_loaded", bool(providers), f"{len(providers)} providers registered",
              count=len(providers))

        engine = self._engine()
        invalid: Dict[str, List[str]] = {}
        for contract_type, items in ((ContractType.CAPABILITY, capabilities),
                                     (ContractType.PROVIDER, providers)):
            for item in items:
                verdict = engine.validate(contract_type, item)
                if not verdict.is_valid:
                    invalid[f"{contract_type.value}:{verdict.contract_id}"] = [e.message for e in verdict.errors]
        check("contracts", not invalid,
              "all contracts valid" if not invalid else f"{len(invalid)} invalid contracts", invalid=invalid)

        uncovered: Dict[str, List[str]] = {}
        for source in skill_sources:
            missing = [s for s in getattr(source, "skills", []) or []
                       if not any(p.supports_skill(s) for p in providers)]
            if missing:
                uncovered[getattr(source, "name", repr(source))] = missing
        check("skill_coverage", not uncovered,
              "every declared skill has a provider" if not uncovered
              else "skills without a provider (performed inline by their capability)",
              uncovered=uncovered)

        failed = [c.name for c in checks if c.status != HealthStatus.HEALTHY]
        if any(name in CRITICAL_CHECKS for name in failed):
            status = HealthStatus.UNHEALTHY
        elif failed:
            status = HealthStatus.DEGRADED
            for c in checks:  # non-critical failures are degradations, not outages
                if c.name in failed:
                    c.status = HealthStatus.DEGRADED
        else:
            status = HealthStatus.HEALTHY

        return KernelHealthReport(status=status, checks=checks,
                                  capabilities=[getattr(c, "name", "") for c in capabilities],
                                  providers=[getattr(p, "name", "") for p in providers])
