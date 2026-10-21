"""``AGOSKernel`` — the kernel facade (R-F-008).

A thin, stateful facade over the single boot path (``agos_runtime.boot()`` →
``Bootstrapper``, R-W3-001). It adds a lifecycle (``start``/``shutdown``) and a
:class:`MissionManager` that keeps the caller's ``Mission`` object in sync with the
outcome; it does not re-implement booting, resolution or execution.

    kernel = AGOSKernel().start()
    result = kernel.mission_manager.execute(Mission(name="A", capability="RepositoryAnalysis",
                                                    parameters={"url": "...", "branch": "main"}))
    result.is_success, result.data, result.error
    kernel.health().status
    kernel.shutdown()
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, List, Optional

from shared import Result, ResultStatus

__all__ = ["AGOSKernel", "KernelState", "MissionManager", "MissionResult", "KernelNotRunning"]


class KernelState(Enum):
    CREATED = "created"
    RUNNING = "running"
    FAILED = "failed"
    STOPPED = "stopped"


class KernelNotRunning(RuntimeError):
    """Raised when a running kernel is required."""


@dataclass
class MissionResult(Result):
    """``shared.Result`` of a mission, plus its id and the engine's full record."""

    mission_id: str = ""
    execution: Optional[Any] = None  # mission_engine.MissionExecutionResult


class MissionManager:
    """Executes missions on a running kernel and records their outcomes."""

    def __init__(self, kernel: "AGOSKernel"):
        self._kernel = kernel
        self.history: List[MissionResult] = []

    def execute(self, mission: Any) -> MissionResult:
        """Run ``mission`` (a ``mission.Mission`` or a dict) through the mission engine.

        Never raises for a failing mission: failures come back as ``FAILURE`` results and,
        for ``Mission`` objects, ``status``/``error``/timestamps are updated in place.
        """
        from mission import MissionStatus

        is_obj = hasattr(mission, "status") and hasattr(mission, "parameters")
        if is_obj:
            mission.status = MissionStatus.RUNNING
            mission.started_at = datetime.utcnow()
        mission_id = getattr(mission, "id", None) or (mission.get("id", "") if isinstance(mission, dict) else "")

        if self._kernel.state != KernelState.RUNNING:
            outcome = MissionResult(status=ResultStatus.FAILURE, mission_id=mission_id,
                                    error=f"kernel is not running (state: {self._kernel.state.value})")
        else:
            try:
                record = self._kernel.runtime.run(mission)
            except Exception as exc:  # engine contract: report, do not crash the caller
                outcome = MissionResult(status=ResultStatus.FAILURE, mission_id=mission_id, error=str(exc))
            else:
                ok = record.state.value == "completed"
                outcome = MissionResult(status=ResultStatus.SUCCESS if ok else ResultStatus.FAILURE,
                                        data=record.result if ok else None, error=record.error,
                                        mission_id=record.mission_id, execution=record)

        if is_obj:
            mission.completed_at = datetime.utcnow()
            mission.status = MissionStatus.COMPLETED if outcome.is_success else MissionStatus.FAILED
            mission.result = outcome.data
            mission.error = outcome.error
        self.history.append(outcome)
        return outcome


class AGOSKernel:
    """Kernel lifecycle facade over ``agos_runtime``."""

    def __init__(self, base_path: Optional[str] = None, verbose: bool = False):
        self.base_path = base_path
        self.verbose = verbose
        self.state = KernelState.CREATED
        self.runtime = None  # agos_runtime.KernelRuntime once started
        self.started_at: Optional[datetime] = None
        self.stopped_at: Optional[datetime] = None
        self.mission_manager = MissionManager(self)

    # -- lifecycle -------------------------------------------------------------
    def start(self) -> "AGOSKernel":
        """Boot through ``agos_runtime.boot()``; raises ``agos_runtime.BootError`` on failure."""
        import agos_runtime

        if self.state == KernelState.RUNNING:
            return self
        self.runtime = agos_runtime.boot(self.base_path, verbose=self.verbose)
        if not self.runtime.ready:
            self.state = KernelState.FAILED
            self.runtime.require_ready()  # raises BootError with the boot errors
        self.state = KernelState.RUNNING
        self.started_at = datetime.utcnow()
        self.stopped_at = None
        return self

    def shutdown(self) -> None:
        """Stop accepting missions. Idempotent; registries stay readable for inspection."""
        if self.state == KernelState.RUNNING:
            self.state = KernelState.STOPPED
            self.stopped_at = datetime.utcnow()

    def __enter__(self) -> "AGOSKernel":
        return self.start()

    def __exit__(self, *exc: Any) -> None:
        self.shutdown()

    # -- state -----------------------------------------------------------------
    @property
    def running(self) -> bool:
        return self.state == KernelState.RUNNING

    def _component(self, name: str):
        return getattr(self.runtime, name) if self.runtime is not None else None

    @property
    def capability_registry(self):
        return self._component("capability_registry")

    @property
    def provider_registry(self):
        return self._component("provider_registry")

    @property
    def contract_engine(self):
        return self._component("contract_engine")

    @property
    def event_bus(self):
        return self._component("event_bus")

    @property
    def mission_engine(self):
        return self._component("mission_engine")

    def health(self):
        """``diagnostics.KernelHealthReport`` for the current registries."""
        from diagnostics import KernelHealthService

        if self.runtime is None:
            raise KernelNotRunning("kernel has not been started")
        return KernelHealthService(self.contract_engine).generate_report(
            self.capability_registry, self.capability_registry, self.provider_registry)
