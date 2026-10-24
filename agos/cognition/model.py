"""AGOS Universal World Model - Single source of truth for AGOS cognition."""
from dataclasses import dataclass, field
from typing import Any, Dict, List

WORLD_MODEL_ENTITIES = ["Organizations", "Projects", "Repositories", "Users", "Capabilities", "Providers", "Agents", "Models", "Workspaces", "Artifacts", "Executions", "Infrastructure", "Knowledge", "Policies", "Costs", "Risks", "Dependencies", "Goals", "Constraints"]

@dataclass
class Entity:
    entity_id: str
    type: str
    properties: Dict[str, Any] = field(default_factory=dict)

class WorldGraph:
    def __init__(self):
        self._nodes: Dict[str, Entity] = {}
        self._edges: List[tuple] = []
    
    def add_entity(self, entity: Entity) -> None:
        self._nodes[entity.entity_id] = entity
    
    def add_edge(self, from_id: str, to_id: str, relation: str) -> None:
        self._edges.append((from_id, to_id, relation))
    
    def edges(self) -> List[tuple]:
        """الحواف المعلنة (نسخة) — إفصاح عام لعلاقات الرسم يستهلكه محرك
        العلاقات بدل قراءة الحقل الخاص من كائن آخر (عيب ADR-0012 — 0076)."""
        return list(self._edges)
    
    def get_entity(self, entity_id: str) -> Entity:
        return self._nodes.get(entity_id)

class StateEngine:
    """حالة الكيان غير مقيسة — لا حالة تُختلق (ADR-0012، العمل 1 —
    model.py:29)."""

    def get_state(self, entity_id: str) -> Dict[str, Any]:
        return {"status": None,
                "reason": "حالة الكيان غير مقيسة — لا حالة تُختلق"}

class RelationshipEngine:
    """يحل علاقات الكيان من الرسم المقيّد إن رُبط به.

    عيب معاد إنتاجه وثّقه ADR-0012 وصُلح هنا (سجل العمل 0076): كان يقرأ
    ``self._edges`` غير الموجودة عليه فكان **كل استدعاء عام** يرفع
    AttributeError — الآن يقرأ حواف الرسم المقيّد عبر الإفصاح العام
    ``edges()``؛ وبلا رسم مقيّد لا حواف تُبحث فالناتج قائمة فارغة صادقة.
    """

    def __init__(self, graph: "WorldGraph" = None):
        self._graph = graph

    def find_relationships(self, entity_id: str) -> List[tuple]:
        edges = self._graph.edges() if self._graph is not None else []
        return [(e[0], e[1], e[2]) for e in edges
                if e[0] == entity_id or e[1] == entity_id]

class PredictionEngine:
    """التنبؤ غير منفذ — لا تنبؤ ولا ثقة تُختلقان (ADR-0012، العمل 1 —
    model.py:37)."""

    def predict(self, entity_id: str) -> Dict[str, Any]:
        return {"prediction": None, "confidence": None,
                "reason": "التنبؤ غير منفذ — لا تنبؤ يُختلق"}

class UniversalWorldModel:
    """
    Universal World Model.
    
    Target: Single Source of Truth for AGOS cognition
    
    Entities:
    ✅ Organizations, Projects, Repositories, Users, Capabilities
    ✅ Providers, Agents, Models, Workspaces, Artifacts
    ✅ Executions, Infrastructure, Knowledge, Policies, Costs
    ✅ Risks, Dependencies, Goals, Constraints
    """
    def __init__(self):
        self.version = "10.0.0"
        self.graph = WorldGraph()
        self.state = StateEngine()
        self.relationships = RelationshipEngine()
        self.prediction = PredictionEngine()
    
    def add(self, entity_id: str, entity_type: str, properties: Dict[str, Any]) -> Entity:
        entity = Entity(entity_id=entity_id, type=entity_type, properties=properties)
        self.graph.add_entity(entity)
        return entity
    
    def get_statistics(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "entities": WORLD_MODEL_ENTITIES
        }
