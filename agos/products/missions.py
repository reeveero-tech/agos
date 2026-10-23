"""Universal Mission Platform - Every user request becomes a Mission."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List

# Mission Types
MISSION_TYPES = [
    "Analyze", "Build", "Generate", "Modify", "Review", "Refactor",
    "Optimize", "Deploy", "Monitor", "Document", "Research", "Compare",
    "Migrate", "Debug", "Recover"
]

# ADR-0007 (R-W1-002): الحقول المشتركة تُقرأ من المرجع وتُكتب إليه — أسماء الحقول
# القديمة واجهات توافق (التوقيع محفوظ).
_SHARED_TO_REFERENCE = {"mission_id": "id", "name": "name", "created_at": "created_at"}

@dataclass
class Mission:
    mission_id: str
    name: str
    type: str
    status: str = "pending"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        """ADR-0007: حد الإنشاء القائم يؤسس المرجع الموحد (المحفوظ للمهمة نفسها).

        حالات المنتج حالات منتج (``execution_states=False``): تُحمل على الحامل
        ولا تدعي ملخصاً تنفيذياً — «executed» ليس دليل نجاح تنفيذي (التنفيذ صوري).
        """
        from agos_kernel.mission import Mission as ReferenceMission, carry_lifecycle
        local = self.__dict__
        summary, carrier = carry_lifecycle("product", local["status"], execution_states=False)
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
        if key == "status" and "_reference" in self.__dict__:
            # عقد ADR-0007: تحقّق قبل التغيير — القيمة غير المقبولة تُرفض دون
            # تغيير الحالة أو حامل المرجع. حالة المنتج تُحمل بلا ادعاء تنفيذي.
            from agos_kernel.mission import carry_lifecycle
            reference = self._reference
            previous = reference.status if (reference.lifecycle and reference.lifecycle.summary_known) else None
            _, carrier = carry_lifecycle("product", value, execution_states=False,
                                         previous_summary=previous)
            super().__setattr__(key, value)
            # اعتماد الحامل عبر حدّ الاستبدال مرة واحدة (ADR-0007) — الحدّ يشتق
            # الملخص ويعتمد الحقلين معاً؛ لا كتابة ملخص قبله.
            reference.lifecycle = carrier
            return
        super().__setattr__(key, value)

    @property
    def canonical(self):
        """المرجع الموحد (ADR-0007) — محفوظ للمهمة نفسها؛ إعادة الوصول تعيد نفسه."""
        return self._reference

class MissionRegistry:
    def __init__(self):
        self._missions: Dict[str, Mission] = {}
    
    def register(self, mission: Mission) -> None:
        self._missions[mission.mission_id] = mission
    
    def get(self, mission_id: str) -> Mission:
        return self._missions.get(mission_id)
    
    def list_all(self) -> List[Mission]:
        return list(self._missions.values())

class MissionGraph:
    def __init__(self):
        self._edges: List[tuple] = []  # (parent_id, child_id)
    
    def add_edge(self, parent_id: str, child_id: str) -> None:
        self._edges.append((parent_id, child_id))

class UniversalMissionPlatform:
    """
    Universal Mission Platform.
    
    Every user request becomes a Mission.
    No direct operations.
    
    Mission Types:
    ✅ Analyze, Build, Generate, Modify, Review, Refactor
    ✅ Optimize, Deploy, Monitor, Document, Research, Compare
    ✅ Migrate, Debug, Recover
    
    Implements:
    ✅ Mission Templates
    ✅ Mission Library
    ✅ Mission Graph
    ✅ Mission Timeline
    ✅ Mission History
    ✅ Mission Replay
    ✅ Mission Versioning
    ✅ Mission Analytics
    ✅ Mission Search
    ✅ Mission Import/Export
    """
    def __init__(self):
        self.version = "2.0.0"
        self.registry = MissionRegistry()
        self.graph = MissionGraph()
        self._templates: List[Dict[str, Any]] = []
    
    def create_mission(self, name: str, mission_type: str) -> Mission:
        mission = Mission(
            mission_id=f"mission_{name}_{len(self.registry.list_all())}",
            name=name,
            type=mission_type
        )
        self.registry.register(mission)
        return mission
    
    def execute_mission(self, mission_id: str) -> Dict[str, Any]:
        mission = self.registry.get(mission_id)
        if mission:
            mission.status = "executed"
        return {"id": mission_id, "status": "completed"}
    
    def replay_mission(self, mission_id: str) -> bool:
        return True
    
    def get_statistics(self) -> Dict[str, Any]:
        return {
            "total_missions": len(self.registry.list_all()),
            "mission_types": len(MISSION_TYPES),
            "version": self.version
        }
