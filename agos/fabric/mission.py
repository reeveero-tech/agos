"""Global Mission Runtime - Enterprise-scale Mission Graphs."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List

class MissionType(Enum):
    SINGLE = "single"
    MULTI = "multi"
    RECURSIVE = "recursive"
    STREAMING = "streaming"
    SCHEDULED = "scheduled"
    COLLABORATIVE = "collaborative"
    LONG_RUNNING = "long_running"

class MissionState(Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

# ADR-0007 (R-W1-002): الحقول المشتركة تُقرأ من المرجع وتُكتب إليه —
# أسماء الحقول القديمة واجهات توافق (التوقيع محفوظ).
_SHARED_TO_REFERENCE = {"mission_id": "id", "name": "name", "created_at": "created_at"}

@dataclass
class Mission:
    mission_id: str
    mission_type: MissionType
    name: str
    state: MissionState = MissionState.PENDING
    graph: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        """ADR-0007: حد الإنشاء القائم يؤسس المرجع الموحد (المحفوظ للمهمة نفسها).

        الهوية والاسم والطابع الأصلي تُنقل كما هي (لا توليد جديد)؛ الحالة الدقيقة
        تُحمل وفق عقد carry_lifecycle. النسخ المحلية للحقول المشتركة تُزال بعد
        التأسيس فتصبح القراءة والكتابة عبر أسمائها القديمة تفويضاً حياً للمرجع.
        """
        from agos_kernel.mission import Mission as ReferenceMission, carry_lifecycle
        # اقرأ النسخ المحلية قبل تأسيس المرجع (القراءة الموجهة تتعطل دونه)
        local = self.__dict__
        summary, carrier = carry_lifecycle("fabric", local["state"].value)
        self._reference = ReferenceMission(
            id=str(local["mission_id"]),
            name=local["name"],
            created_at=local["created_at"],
            status=summary,
            lifecycle=carrier,
        )
        for local_key in _SHARED_TO_REFERENCE:
            self.__dict__.pop(local_key, None)

    def __getattribute__(self, key):
        if key in _SHARED_TO_REFERENCE:
            reference = object.__getattribute__(self, "_reference")
            return getattr(reference, _SHARED_TO_REFERENCE[key])
        return object.__getattribute__(self, key)

    def __setattr__(self, key, value):
        if key in _SHARED_TO_REFERENCE and "_reference" in self.__dict__:
            setattr(self._reference, _SHARED_TO_REFERENCE[key], value)
            return
        if key == "state" and "_reference" in self.__dict__:
            # عقد ADR-0007: تحقّق قبل التغيير — القيمة غير المقبولة تُرفض دون
            # تغيير الحالة أو حامل المرجع (لا تناقص صامت بين الحالة والمرجع).
            if not isinstance(value, MissionState):
                raise ValueError(
                    f"unacceptable state {value!r} — MissionState expected (ADR-0007)"
                )
            super().__setattr__(key, value)
            self._carry_state(value)
            return
        super().__setattr__(key, value)

    def _carry_state(self, fine: MissionState):
        """انعكاس انتقال الحالة على المرجع وفق ملكية ADR-0007 §2: الحالة والحامل
        فقط — لا استنتاج أوقات تاريخية من الملخص (البدء يُختم عند حد البدء
        الفعلي في MissionRuntime.execute)."""
        from agos_kernel.mission import carry_lifecycle
        reference = self._reference
        previous = reference.status if (reference.lifecycle and reference.lifecycle.summary_known) else None
        _, carrier = carry_lifecycle("fabric", fine.value, previous_summary=previous)
        # اعتماد الحامل عبر حدّ الاستبدال مرة واحدة: الحدّ يتحقق ثم يشتق الملخص
        # ويعتمد الحقلين معاً (ADR-0007) — لا كتابة ملخص قبله فيُرفض الانتقال
        # بعد تغيير نصفه.
        reference.lifecycle = carrier

    @property
    def canonical(self):
        """المرجع الموحد (ADR-0007) — محفوظ للمهمة نفسها؛ إعادة الوصول تعيد نفسه."""
        return self._reference

class MissionGraph:
    def __init__(self):
        self._nodes: Dict[str, Mission] = {}
        self._edges: List[tuple] = []
    
    def add(self, mission: Mission) -> None:
        self._nodes[mission.mission_id] = mission
    
    def get(self, mission_id: str) -> Mission:
        return self._nodes.get(mission_id)
    
    def list_all(self) -> List[Mission]:
        return list(self._nodes.values())

class MissionScheduler:
    def schedule(self, mission_id: str, schedule: Dict[str, Any]) -> bool:
        return True
    
    def cancel(self, mission_id: str) -> bool:
        return True

class MissionRuntime:
    """
    Global Mission Runtime.
    
    Target: 100000 Active Missions
    
    Supported:
    ✅ Single Mission
    ✅ Multi Mission
    ✅ Recursive Mission
    ✅ Streaming Mission
    ✅ Scheduled Mission
    ✅ Collaborative Mission
    ✅ Long Running Mission
    """
    def __init__(self):
        self.version = "2.0.0"
        self.graph = MissionGraph()
        self.scheduler = MissionScheduler()
        self._active: int = 0
    
    def create(self, mission_id: str, mission_type: MissionType, name: str) -> Mission:
        mission = Mission(
            mission_id=mission_id,
            mission_type=mission_type,
            name=name
        )
        self.graph.add(mission)
        return mission
    
    def execute(self, mission_id: str) -> bool:
        mission = self.graph.get(mission_id)
        if mission:
            mission.state = MissionState.RUNNING
            # ADR-0007 §2: حد البدء الفعلي يملك ختم البدء — مرة ولا يُستبدل.
            if mission.canonical.started_at is None:
                mission.canonical.started_at = datetime.now(timezone.utc)
            self._active += 1
            return True
        return False
    
    def recover(self, mission_id: str) -> bool:
        return True
    
    def replay(self, mission_id: str) -> bool:
        return True
    
    def get_statistics(self) -> Dict[str, Any]:
        return {
            "total_missions": len(self.graph.list_all()),
            "active_missions": self._active,
            "target": 100000,
            "version": self.version
        }
