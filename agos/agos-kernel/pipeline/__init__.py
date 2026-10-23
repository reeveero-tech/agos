"""Execution Pipeline for running missions."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from context import ExecutionContext
from events import Event, EventBus, EventType
from mission import Mission
from resolvers import CapabilityResolver, ProviderResolver


class ExecutionStatus(Enum):
    """Execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ExecutionStep:
    """A single step in the execution pipeline."""
    step_id: str
    name: str
    status: ExecutionStatus
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Any] = None
    error: Optional[str] = None


@dataclass
class ExecutionResult:
    """Result of an execution pipeline — carries its decision evidence."""
    status: ExecutionStatus
    mission_id: str
    steps: List[ExecutionStep] = field(default_factory=list)
    result: Optional[Any] = None
    error: Optional[str] = None
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    duration_ms: int = 0
    #: عقود الدليل من قراري القدرة والموفّر (R-W1-004) — من المسار الموحد
    decision_records: List[Any] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "mission_id": self.mission_id,
            "steps": [{"step_id": s.step_id, "name": s.name, "status": s.status.value, "error": s.error} for s in self.steps],
            "result": self.result,
            "error": self.error,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_ms": self.duration_ms,
            "decision_records": [r.to_dict() for r in self.decision_records]
        }


class ExecutionPipeline:
    """Executes missions through the full pipeline."""
    
    def __init__(self, event_bus: EventBus, capability_resolver: CapabilityResolver, provider_resolver: ProviderResolver, execution_engine=None):
        self.event_bus = event_bus
        self.capability_resolver = capability_resolver
        self.provider_resolver = provider_resolver
        # ADR-0008 (R-W1-003): النواة المشتركة لاستدعاء العمل — الربط
        # الافتراضي هو المحرك العالمي؛ التواقيع الموضعية القائمة محفوظة (G2).
        if execution_engine is None:
            from agos_kernel.execution.engine import get_engine
            execution_engine = get_engine()
        self.execution_engine = execution_engine
    
    def execute(self, mission: Mission) -> ExecutionResult:
        """Execute a mission through the full pipeline."""
        result = ExecutionResult(status=ExecutionStatus.RUNNING, mission_id=mission.id)
        context = ExecutionContext(mission=mission)
        
        try:
            # Step 1: Resolve Capability
            step = self._create_step("resolve_capability", "Resolve Capability")
            result.steps.append(step)
            
            capability_selection = self.capability_resolver.resolve(mission, context)
            # R-W1-004: يُحفظ أثر القرار فور عودة كل مرحلة — قبل فحص حالتها
            # ففشل الحل لا يسقط الدليل (من اختار، ولماذا رُفض/تعذر)
            result.decision_records = [
                r for r in (getattr(capability_selection, "record", None),)
                if r is not None]
            
            if capability_selection.status.value != "success":
                raise Exception(f"Capability resolution failed: {capability_selection.reason}")
            
            step.status = ExecutionStatus.COMPLETED
            step.completed_at = datetime.now(timezone.utc)
            step.result = capability_selection.capability_name
            
            self.event_bus.publish(Event(
                type=EventType.CAPABILITY_SELECTED,
                mission_id=mission.id,
                data={"capability": capability_selection.capability_name, "reason": capability_selection.reason}
            ))
            
            # Step 2: Resolve Provider
            step = self._create_step("resolve_provider", "Resolve Provider")
            result.steps.append(step)
            
            provider_selection = self.provider_resolver.resolve(capability_selection.capability, mission)
            # R-W1-004: عقدي القرار معاً — حتى لو فشل حل الموفّر بعدها
            result.decision_records = [
                r for r in (getattr(capability_selection, "record", None),
                            getattr(provider_selection, "record", None))
                if r is not None]
            
            if provider_selection.status.value != "success":
                raise Exception(f"Provider resolution failed: {provider_selection.reason}")
            
            step.status = ExecutionStatus.COMPLETED
            step.completed_at = datetime.now(timezone.utc)
            step.result = provider_selection.provider_name
            
            self.event_bus.publish(Event(
                type=EventType.PROVIDER_SELECTED,
                mission_id=mission.id,
                data={"provider": provider_selection.provider_name, "reason": provider_selection.reason}
            ))
            
            # Step 3: Execute Capability
            step = self._create_step("execute_capability", "Execute Capability")
            result.steps.append(step)
            step.started_at = datetime.now(timezone.utc)
            
            self.event_bus.publish(Event(
                type=EventType.EXECUTION_STARTED,
                mission_id=mission.id,
                data={"capability": capability_selection.capability_name}
            ))
            
            capability = capability_selection.capability
            # ADR-0008 (R-W1-003): استدعاء القدرة عبر النواة المشتركة — سياسة
            # الاستدعاء الواحد محفوظة؛ الفشل يعود إلى مسار الاستثناء نفسه
            # (الرسالة والسلوك وأدلة القرار محفوظة حرفياً).
            outcome = self.execution_engine.invoke_sync(
                capability.execute, mission.parameters)
            if outcome.error is not None:
                raise outcome.error
            execution_result = outcome.value
            
            step.status = ExecutionStatus.COMPLETED
            step.completed_at = datetime.now(timezone.utc)
            step.result = execution_result
            
            # Step 4: Complete
            result.result = execution_result
            result.status = ExecutionStatus.COMPLETED
            
            self.event_bus.publish(Event(
                type=EventType.EXECUTION_COMPLETED,
                mission_id=mission.id,
                data={"success": True}
            ))
            
            result.completed_at = datetime.now(timezone.utc)
            result.duration_ms = int((result.completed_at - result.started_at).total_seconds() * 1000)
            
            return result
            
        except Exception as e:
            result.status = ExecutionStatus.FAILED
            result.error = str(e)
            result.completed_at = datetime.now(timezone.utc)
            result.duration_ms = int((result.completed_at - result.started_at).total_seconds() * 1000)
            
            step = self._create_step("error", "Error")
            step.status = ExecutionStatus.FAILED
            step.error = str(e)
            step.completed_at = datetime.now(timezone.utc)
            result.steps.append(step)
            
            self.event_bus.publish(Event(
                type=EventType.EXECUTION_FAILED,
                mission_id=mission.id,
                data={"error": str(e)}
            ))
            
            return result
    
    def _create_step(self, step_id: str, name: str) -> ExecutionStep:
        return ExecutionStep(step_id=step_id, name=name, status=ExecutionStatus.PENDING, started_at=datetime.now(timezone.utc))
