"""AGOS runtime entry point — the single boot path (R-W3-001, ADR-0001 §5).

    import agos_runtime
    kernel = agos_runtime.boot()
    result = kernel.analyze("https://github.com/owner/repo", branch="main")

``boot()`` runs ``Bootstrapper.bootstrap()`` (container → discovery → registries →
contract validation → event engine/bus → mission engine) and returns a
:class:`KernelRuntime` handle. Every mission then runs through
``MissionEngine → ExecutionPipeline → CapabilityResolver → ProviderResolver``, which
publishes its events on the kernel ``EventBus`` (Constitution, Articles 6 and 15).

This module adds no second implementation: it only composes the existing kernel parts.
"""
from __future__ import annotations

import contextlib
import io
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from bootstrapper import Bootstrapper, BootstrapResult

__all__ = ["boot", "KernelRuntime", "BootError", "REPOSITORY_ANALYSIS"]

#: Name of the kernel's repository-analysis capability (``capabilities.RepositoryAnalysisCapability``).
REPOSITORY_ANALYSIS = "RepositoryAnalysis"


class BootError(RuntimeError):
    """Raised by :meth:`KernelRuntime.require_ready` when the kernel failed to boot."""


@dataclass
class KernelRuntime:
    """Handle on a booted kernel. Thin: every attribute is the Bootstrapper's own object."""

    bootstrapper: Bootstrapper
    result: BootstrapResult
    boot_log: str = ""
    missions: List[Any] = field(default_factory=list)

    # -- state -----------------------------------------------------------------
    @property
    def ready(self) -> bool:
        return bool(self.result.success)

    @property
    def errors(self) -> List[str]:
        return list(self.result.errors)

    @property
    def warnings(self) -> List[str]:
        return list(self.result.warnings)

    def require_ready(self) -> "KernelRuntime":
        if not self.ready:
            raise BootError("; ".join(self.result.errors) or "kernel did not boot")
        return self

    # -- components (same objects the Bootstrapper built) ----------------------
    @property
    def container(self):
        return self.bootstrapper.container

    @property
    def capability_registry(self):
        return self.bootstrapper._capability_registry

    @property
    def provider_registry(self):
        return self.bootstrapper._provider_registry

    @property
    def contract_engine(self):
        return self.bootstrapper.contract_engine

    @property
    def event_engine(self):
        return self.bootstrapper.event_engine

    @property
    def event_bus(self):
        return self.bootstrapper.event_bus

    @property
    def mission_engine(self):
        return self.bootstrapper.mission_engine

    # -- missions ---------------------------------------------------------------
    def run(self, mission: Any):
        """Run a mission (``Mission`` or dict) through the mission engine."""
        self.require_ready()
        outcome = self.mission_engine.run(mission)
        self.missions.append(outcome)
        return outcome

    def analyze(self, url: str, branch: str = "main"):
        """Run the repository-analysis mission; ``result.result`` is a ``RepositoryDNA``."""
        return self.run({
            "name": f"Analyze {url}",
            "description": "Analyze a repository and generate its DNA",
            "capability": REPOSITORY_ANALYSIS,
            "parameters": {"url": url, "branch": branch},
        })

    def summary(self) -> Dict[str, Any]:
        return {
            "ready": self.ready,
            "kernel_version": self.result.kernel_version,
            "capabilities": list(self.result.loaded_capabilities),
            "providers": list(self.result.loaded_providers),
            "errors": self.errors,
            "warnings": self.warnings,
            "duration_ms": self.result.duration_ms,
        }


def boot(base_path: Optional[str] = None, verbose: bool = False) -> KernelRuntime:
    """Boot the kernel through the Bootstrapper and return its handle.

    ``verbose=False`` captures the Bootstrapper's console banner in ``boot_log``
    instead of printing it (nothing is discarded).
    """
    bootstrapper = Bootstrapper(base_path)
    if verbose:
        result = bootstrapper.bootstrap()
        return KernelRuntime(bootstrapper=bootstrapper, result=result)
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        result = bootstrapper.bootstrap()
    return KernelRuntime(bootstrapper=bootstrapper, result=result, boot_log=buffer.getvalue())
