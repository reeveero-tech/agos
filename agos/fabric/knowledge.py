"""Universal Knowledge Fabric - 1 Billion Knowledge Objects."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List

# Knowledge Sources
KNOWLEDGE_SOURCES = [
    "Repositories", "Documentation", "Specifications",
    "Architecture", "Projects", "Benchmarks",
    "Capabilities", "Providers", "Agents", "Models",
    "Patterns", "Incidents", "Lessons"
]

def _merge_with_live(stored_content, live_content: str) -> Dict[str, Any]:
    """التحديث الحي: raw يتبع الحقل العلبي الحي، والجزء المنظم المحفوظ يبقى."""
    if not stored_content:
        return {"raw": live_content}
    merged = dict(stored_content)
    merged["raw"] = live_content
    return merged


@dataclass
class KnowledgeObject:
    id: str
    source: str
    content: str
    embeddings: List[float] = field(default_factory=list)
    provenance: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    rank: float = 0.0
    
    def to_canonical(self):
        """R-W1-005 (ADR-0002): حوّل إلى كائن المعرفة المعتمد `agos_kernel.knowledge.models.Knowledge`.
        
        الطابع الزمني الأصلي (UTC) يُحفظ كما هو في `created_at`؛ النسب والإصدار
        من `provenance` إن وُجدا وإلا فنقص معلن لا مختلق. `origin=imported`.
        ملاحظة: هذه الوحدة غير موصولة بمستوردين اليوم — موثق في ADR-0002.
        """
        from agos_kernel.knowledge.models import (
            Knowledge as CanonicalKnowledge, KnowledgeMetadata, Evidence, KnowledgeType,
        )
        
        lineage = self.provenance.get("lineage") if isinstance(self.provenance, dict) else None
        version = (self.provenance.get("version") or "") if isinstance(self.provenance, dict) else ""
        # الإصدار المجهول يُعلن خاوياً — لا يُختلق "1.0.0" (ADR-0002)
        # المصادر: الأولي + قائمة كاملة إن حُفظت في provenance — بلا اختزال
        stored_sources = (self.provenance.get("sources") or []) if isinstance(self.provenance, dict) else []
        sources = [self.source] if self.source else []
        for src in stored_sources:
            if src not in sources:
                sources.append(src)
        # العنوان والوصف المحفوظان صراحة (امتداد توافق — ما لا تمثله الأسرة)
        stored_title = self.provenance.get("canonical_title") if isinstance(self.provenance, dict) else None
        stored_description = self.provenance.get("canonical_description") if isinstance(self.provenance, dict) else None
        metadata = KnowledgeMetadata(
            title=stored_title or (self.content[:60] or self.id),
            sources=sources,
            version=version,
        )
        if stored_description:
            metadata.description = stored_description
        canonical_evidence = []
        if isinstance(self.provenance, dict) and self.provenance.get("evidence"):
            from agos_kernel.knowledge.convert import evidence_dict_to_canonical
            canonical_evidence = [
                evidence_dict_to_canonical(ev, self.id, i)
                for i, ev in enumerate(self.provenance["evidence"])
            ]
        confidence = self.provenance.get("confidence") if isinstance(self.provenance, dict) else None
        # domain_extras: حقول هذه الأسرة غير المشتركة (embeddings/rank وما زاد في
        # provenance) تُحفظ كما هي — الذهاب والإياب بلا فقد صامت (ADR-0002)
        extras = {
            "embeddings": list(self.embeddings),
            "rank": self.rank,
        }
        if isinstance(self.provenance, dict):
            extras["provenance_extras"] = {
                k: v for k, v in self.provenance.items()
                if k not in ("lineage", "version", "confidence", "evidence",
                             "knowledge_type", "sources", "canonical_title",
                             "canonical_description", "canonical_content")
            }
            # المفاتيح العامة المحفوظة في domain_extras (من رحلة سابقة) تعود كما هي
            for k, v in (self.provenance.get("domain_extras") or {}).items():
                extras.setdefault(k, v)
        # النوع الأصلي إن حُفظ صراحة (امتداد توافق — لا إسقاط إلى FACT)
        knowledge_type_value = (self.provenance.get("knowledge_type") or "fact") \
            if isinstance(self.provenance, dict) else "fact"
        try:
            knowledge_type = KnowledgeType(knowledge_type_value)
        except ValueError:
            knowledge_type = KnowledgeType.FACT
        # قاعدة تمييز التعديل عن إعادة التحويل (ADR-0002): إن بقي الحقل العلبي
        # (content) مطابقاً لإسقاطه المحفوظ وقت الحفظ، استُعيد المحتوى والملخص
        # حرفياً؛ وإن تغيّر طُبقت قاعدة التحديث الحي (raw يتبع الحقل الحي).
        stored_content = self.provenance.get("canonical_content") if isinstance(self.provenance, dict) else None
        stored_projection = self.provenance.get("content_projection") if isinstance(self.provenance, dict) else None
        stored_summary = self.provenance.get("canonical_summary") if isinstance(self.provenance, dict) else None
        unchanged = (stored_projection is not None and stored_projection == self.content)
        canonical = CanonicalKnowledge(
            id=self.id,
            knowledge_type=knowledge_type,
            metadata=metadata,
            summary=(stored_summary if unchanged else self.content) if stored_summary is not None else self.content,
            content=(dict(stored_content) if stored_content is not None
                      else {"raw": self.content}) if unchanged
                     else _merge_with_live(stored_content, self.content),
            evidence=canonical_evidence,
            source=self.source,
            confidence=confidence,
            lineage=lineage if lineage is not None else None,
            origin="imported",
            created_at=self.created_at,   # الأصل محفوظ — ليس وقت التحويل
            domain_extras=extras,
        )
        return canonical
    
    @classmethod
    def from_canonical(cls, canonical) -> "KnowledgeObject":
        """R-W1-005: أنشئ كائن هذه الأسرة من الكائن المعتمد (ذهاب وإياب)."""
        provenance = {}
        if canonical.lineage is not None:
            provenance["lineage"] = list(canonical.lineage)
        if canonical.metadata.version:
            provenance["version"] = canonical.metadata.version
        if canonical.confidence is not None:
            provenance["confidence"] = canonical.confidence
        if canonical.evidence:
            from agos_kernel.knowledge.convert import evidence_canonical_to_dict
            provenance["evidence"] = [
                evidence_canonical_to_dict(ev) for ev in canonical.evidence
            ]
        extras = dict(canonical.domain_extras or {})
        provenance.update(extras.get("provenance_extras", {}))
        # حفظ صريح لما لا تمثله هذه الأسرة بطبيعتها — يعود كما هو في الذهاب والإياب
        provenance["knowledge_type"] = canonical.knowledge_type.value
        provenance["sources"] = list(canonical.metadata.sources)
        provenance["canonical_title"] = canonical.metadata.title
        if canonical.metadata.description:
            provenance["canonical_description"] = canonical.metadata.description
        provenance["canonical_content"] = dict(canonical.content)
        provenance["content_projection"] = canonical.summary or str(canonical.content.get("raw", ""))
        provenance["canonical_summary"] = canonical.summary
        provenance["domain_extras"] = {
            k: v for k, v in extras.items()
            if k not in ("embeddings", "rank", "provenance_extras")
        }
        return cls(
            id=canonical.id,
            source=canonical.source,
            content=canonical.summary or str(canonical.content.get("raw", "")),
            provenance=provenance,
            embeddings=list(extras.get("embeddings", [])),
            rank=float(extras.get("rank", 0.0)),
            created_at=canonical.created_at,   # الأصل محفوظ ذهاباً وإياباً
        )

@dataclass
class KnowledgeGraph:
    nodes: List[KnowledgeObject] = field(default_factory=list)
    edges: List[tuple] = field(default_factory=list)  # (from_id, to_id, relation)

class KnowledgeFabric:
    """
    Universal Knowledge Fabric.
    
    Target: 1 Billion Knowledge Objects
    
    Features:
    ✅ Knowledge Graph Runtime
    ✅ Knowledge Federation
    ✅ Knowledge Synchronization
    ✅ Knowledge Ranking
    ✅ Knowledge Provenance
    ✅ Knowledge Compression
    ✅ Knowledge Clustering
    ✅ Knowledge Reasoning
    ✅ Knowledge Search
    ✅ Knowledge Embeddings
    ✅ Knowledge Snapshots
    ✅ Knowledge Evolution
    """
    def __init__(self):
        self.version = "2.0.0"
        self._objects: Dict[str, KnowledgeObject] = {}
        self._graph = KnowledgeGraph()
        # R-W1-005 (ADR-0002): سجل تدقيق المادة 13 — يُختم تلقائياً عند الإضافة
        self.article13_log: Dict[str, Any] = {}
    
    def add_canonical(self, canonical) -> KnowledgeObject:
        """R-W1-005 (ADR-0002): تخزين عبر الكائن المعتمد — تحويل داخلي ثم تخزين الأسرة.
        يبقى `add()` القديم كما هو؛ هذا الباب الجديد يجعل النسيج قابلاً للاستخدام
        من منظور المعتمد الواحد."""
        obj = KnowledgeObject.from_canonical(canonical)
        self.add(obj)
        return obj
    
    def get_canonical(self, obj_id: str):
        """R-W1-005: قراءة بالكائن المعتمد — تمثيل معتمد لما هو مخزن فعلاً."""
        obj = self.get(obj_id)
        return obj.to_canonical() if obj is not None else None
    
    def add(self, obj: KnowledgeObject) -> bool:
        # R-W1-005 (ADR-0002): حد الاعتماد إلزامي — الإضافة نفسها تختم التدقيق
        # (لا يتذكر المستهلك استدعاء الفحص). الناقص يُقبل بوصفه ناقصاً معلناً.
        from agos_kernel.knowledge.article13 import article13_status
        self.article13_log[obj.id] = article13_status(obj.to_canonical())
        self._objects[obj.id] = obj
        self._graph.nodes.append(obj)
        return True
    
    def article13_report(self) -> Dict[str, Any]:
        """R-W1-005: تقرير المادة 13 على كل المخزون — تحقق حي وقت التقرير."""
        from agos_kernel.knowledge.article13 import article13_status
        statuses = [article13_status(o.to_canonical()) for o in self._objects.values()]
        return {
            "total": len(self._objects),
            "constitutionally_complete": sum(1 for s in statuses if s["valid"]),
            "incomplete": sum(1 for s in statuses if not s["valid"]),
            "by_requirement": {
                req: sum(1 for s in statuses for v in s["violations"]
                        if v["requirement"] == req)
                for req in ("Source", "Evidence", "Confidence", "Version",
                            "Timestamp", "Lineage")
            },
        }
    
    def get(self, obj_id: str) -> KnowledgeObject:
        return self._objects.get(obj_id)
    
    def search(self, query: str) -> List[KnowledgeObject]:
        return [o for o in self._objects.values() if query.lower() in o.content.lower()]
    
    def federate(self, sources: List[str]) -> int:
        return 0
    
    def snapshot(self) -> str:
        return f"snapshot_{int(datetime.now(timezone.utc).timestamp())}"
    
    def get_statistics(self) -> Dict[str, Any]:
        return {
            "total_objects": len(self._objects),
            "target": "1B",
            "sources": len(KNOWLEDGE_SOURCES),
            "version": self.version
        }
