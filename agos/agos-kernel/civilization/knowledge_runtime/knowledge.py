"""
Universal Knowledge Runtime
PHASE-02: EXECUTION-000014 - Universal Knowledge Runtime
Knowledge becomes a first-class production asset.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum
import uuid


class KnowledgeType(Enum):
    FACT = "fact"
    RULE = "rule"
    PATTERN = "pattern"
    RELATIONSHIP = "relationship"
    METADATA = "metadata"


@dataclass
class KnowledgeObject:
    ko_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    knowledge_type: KnowledgeType = KnowledgeType.FACT
    content: str = ""
    source: str = ""
    # R-W1-005 (ADR-0002): None = ثقة مجهولة لا تُختلق قيمة (الافتراضي 1.0 باقٍ
    # لتوافق المنشئات القديمة التي تمرر رقماً صريحاً)
    confidence: Optional[float] = 1.0
    version: str = "1.0.0"
    relationships: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    # R-W1-005 (ADR-0002): حقول إضافية بقيم افتراضية — المنشئات القديمة لا تنكسر
    evidence: List[Dict[str, Any]] = field(default_factory=list)  # [{source, content, ...}]
    lineage: Optional[List[str]] = None   # None = مجهول، [] = جذر معلن، وقائمة = مشتقة (ADR-0002)
    created_at: Optional[datetime] = None  # زمن إنشاء الأصل إن عُلم — لا يُختلق (ADR-0002)
    
    def to_dict(self) -> Dict:
        return {
            'ko_id': self.ko_id,
            'knowledge_type': self.knowledge_type.value if isinstance(self.knowledge_type, KnowledgeType) else self.knowledge_type,
            'content': self.content,
            'source': self.source,
            'confidence': self.confidence,
            'version': self.version,
            'relationships': self.relationships,
            'metadata': self.metadata,
            'evidence': self.evidence,
            'lineage': self.lineage,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'article13': self.article13,
        }
    
    @property
    def article13(self) -> Dict[str, Any]:
        """حالة المادة 13 — تُحسب عند الطلب فلا تبيت أبداً بعد تعديل الكائن (ADR-0002)."""
        from agos_kernel.knowledge.article13 import article13_status
        return article13_status(self.to_canonical())
    
    def to_canonical(self):
        """حوّل إلى كائن المعرفة المعتمد `agos_kernel.knowledge.models.Knowledge` — بلا فقد صامت.
        
        دلالات ADR-0002:
        - `relationships` تبقى علاقات (`related_to`) ولا تصبح نسباً أبداً.
        - الزمن: زمن إنشاء الأصل إن عُلم (`created_at`) يُحفظ؛ والمجهول يبقى
          `None` (نقص معلن) — لا يُختلق وقت التحويل زمناً للأصل.
        - الثقة المجهولة (`None`) تمر كما هي — لا تُختلق قيمة.
        - المصادر المتعددة تُحفظ في `metadata.sources` (لا تُختزل إلى الأولي).
        - بيانات المجال غير المشتركة (metadata الأصلي) تُحفظ في `domain_extras`.
        """
        from agos_kernel.knowledge.models import (
            Knowledge as CanonicalKnowledge, KnowledgeMetadata,
        )
        
        ktype = self.knowledge_type.value if isinstance(self.knowledge_type, KnowledgeType) else str(self.knowledge_type)
        # امتداد التوافق يحفظ ما لا تمثله هذه الأسرة (النوع غير المشترك، المحتوى
        # المنظم، العنوان والوصف) — لكنه لا يلغي تحديثاً لحقل علبي (ADR-0002):
        # - النوع: لا يُستعمل إلا إذا بقي نوع الأسرة الحالي متطابقاً مع ما حُفظ
        #   وقت التحويل (family_type)؛ فإن عُدّل النوع العلبي ساد التحديث الحي.
        # - المحتوى: raw يتبع حقل الأسرة الحي دائماً؛ والجزء المنظم المحفوظ يبقى.
        cm = self.metadata.get("canonical_metadata", {}) if isinstance(self.metadata, dict) else {}
        # قاعدة تمييز التعديل عن إعادة التحويل (ADR-0002): يُحفظ إسقاط الحقل
        # العلبي (content) والملخص وقت الحفظ؛ فإن بقيا دون تغيير استُعيد المحتوى
        # والملخص حرفياً، وإن تغيّر الحقل العلبي طُبقت قاعدة التحديث الحي.
        stored_projection = cm.get("content_projection")
        stored_summary = cm.get("summary")
        unchanged = (stored_projection is not None and stored_projection == self.content)
        canonical_content = cm.get("content")
        canonical_title = cm.get("title")
        canonical_description = cm.get("description")
        canonical_type = cm.get("canonical_type")
        stored_family_type = cm.get("family_type")
        current_family_type = self.knowledge_type.value if isinstance(self.knowledge_type, KnowledgeType) else str(self.knowledge_type)
        extension_type_in_sync = (
            canonical_type is not None and stored_family_type == current_family_type
        )
        # المصادر: الأولي + القائمة الكاملة إن وُجدت في metadata الأصلي — بلا اختزال
        legacy_sources = []
        if isinstance(self.metadata, dict):
            legacy_sources = list(self.metadata.get("canonical_metadata", {}).get("sources", []))
        sources = [self.source] if self.source else []
        for src in legacy_sources:
            if src not in sources:
                sources.append(src)
        metadata = KnowledgeMetadata(
            title=canonical_title or (self.content[:60] or self.ko_id),  # الأصلي إن حُفظ، وإلا مشتق من المحتوى الفعلي
            sources=sources,
            version=self.version,
        )
        if canonical_description:
            metadata.description = canonical_description
        canonical_evidence = [
            _evidence_dict_to_canonical(ev, self.ko_id, i)
            for i, ev in enumerate(self.evidence)
        ]
        # النوع الأصلي إن حُفظ صراحة (امتداد توافق — لا إسقاط إلى أقرب معنى):
        # يستعمل مباشرة بلا مرور بجدول الأنواع الحضارية (الذي يختزل إلى أقرب معنى)
        restored_canonical_type = None
        if extension_type_in_sync:
            from agos_kernel.knowledge.models import KnowledgeType as CanonicalType
            try:
                restored_canonical_type = CanonicalType(canonical_type)
            except ValueError:
                restored_canonical_type = None
        type_map = _canonical_type_map()
        # domain_extras: بيانات المجال غير المشتركة تُحفظ كما هي (بلا فقد)
        extras = {k: v for k, v in self.metadata.items() if k != "canonical_metadata"} \
            if isinstance(self.metadata, dict) else {}
        canonical = CanonicalKnowledge(
            id=self.ko_id,
            knowledge_type=restored_canonical_type or type_map.get(ktype, type_map["fact"]),
            metadata=metadata,
            summary=stored_summary if unchanged else self.content,
            content=(dict(canonical_content) if unchanged
                    else _merged_content(canonical_content, self.content)),
            related_to=list(self.relationships),   # العلاقات تبقى علاقات
            evidence=canonical_evidence,
            source=self.source,
            confidence=self.confidence,           # المجهولة تمر كما هي
            lineage=self.lineage,                 # النسب الصريح إن وُجد؛ وإلا مجهول معلن
            origin="imported",
            created_at=self.created_at,           # زمن الأصل إن عُلم؛ وإلا None معلن
            imported_at=datetime.now(),
            domain_extras=extras,
        )
        return canonical
    
    @property
    def canonical(self):
        """التمثيل المعتمد مشتق عند الطلب — لا يمكن للنموذجين التباعد (ADR-0002)."""
        return self.to_canonical()
    
    @classmethod
    def from_canonical(cls, canonical) -> "KnowledgeObject":
        """أنشئ كائن هذه الأسرة من الكائن المعتمد — عودة كاملة بلا فقد صامت.
        
        الثقة المجهولة والزمن المجهول والنسب المجهول تمر كما هي (`None`) —
        حقول هذه الأسرة اختيارية الآن (ADR-0002: لا اختلاق قيم).
        """
        ko = cls(
            ko_id=canonical.id,
            knowledge_type=_civilization_type(canonical.knowledge_type),
            content=canonical.summary or str(canonical.content.get("raw", "")),
            source=canonical.source,
            confidence=canonical.confidence,       # المجهولة تمر كما هي
            version=canonical.metadata.version,
            relationships=list(canonical.related_to or []),
            metadata={
                "canonical_metadata": {
                    "title": canonical.metadata.title,
                    "description": canonical.metadata.description,
                    "sources": list(canonical.metadata.sources),   # المصادر المتعددة تعود كاملة
                    # امتداد توافق صريح: ما لا تمثله هذه الأسرة يُحفظ كما هو (لا يُسقط)
                    "content": dict(canonical.content),            # المحتوى المنظم كاملاً
                    "content_projection": (canonical.summary or str(canonical.content.get("raw", ""))),  # إسقاط الحقل العلبي وقت الحفظ
                    "summary": canonical.summary,                   # الملخص الأصلي (للاستعادة الحرفية)
                    "canonical_type": canonical.knowledge_type.value,  # النوع الأصلي الدقيق
                    "family_type": _civilization_type(canonical.knowledge_type).value,  # نوع الأسرة وقت الحفظ (فحص التزامن)
                },
                **(canonical.domain_extras or {}),   # بيانات المجال تعود كما هي
            },
            evidence=[_evidence_canonical_to_dict(ev) for ev in canonical.evidence],
            lineage=list(canonical.lineage) if canonical.lineage is not None else None,
            created_at=canonical.created_at,       # زمن الأصل يعود كما هو (None إن كان مجهولاً)
        )
        return ko


# مطابقة قيم أنواع المعرفة بين الأسرة الحضارية والنموذج المعتمد
# (بناء مؤجل: لا تُحمّل النواة عند استيراد الوحدة، بل عند أول تحويل فعلي)
_CANONICAL_TYPE_MAP = None


def _canonical_type_map():
    global _CANONICAL_TYPE_MAP
    if _CANONICAL_TYPE_MAP is None:
        from agos_kernel.knowledge.models import KnowledgeType as CanonicalType
        mapping = {
            "fact": CanonicalType.FACT,
            "rule": CanonicalType.RULE,
            "pattern": CanonicalType.PATTERN,
            "relationship": CanonicalType.RELATIONSHIP,
        }
        mapping["metadata"] = CanonicalType.CONCEPT   # أقرب دلالة معتمدة
        _CANONICAL_TYPE_MAP = mapping
    return _CANONICAL_TYPE_MAP


def _merged_content(canonical_content, live_content: str) -> Dict[str, Any]:
    """دمج المحتوى: `raw` يتبع حقل الأسرة الحي دائماً (لا ظلاً قديماً)،
    والجزء المنظم المحفوظ (ما لا تمثله الأسرة) يبقى كما هو."""
    if not canonical_content:
        return {"raw": live_content}
    merged = dict(canonical_content)
    merged["raw"] = live_content
    return merged


def _civilization_type(canonical_type) -> KnowledgeType:
    """أعد نوع المعرفة الحضاري المقابل للنوع المعتمد (بلا فقد الدلالة)."""
    value = getattr(canonical_type, "value", str(canonical_type))
    return _civilization_type_map().get(value, KnowledgeType.METADATA)


_CIVILIZATION_TYPE_MAP = None


def _civilization_type_map():
    global _CIVILIZATION_TYPE_MAP
    if _CIVILIZATION_TYPE_MAP is None:
        mapping = {t.value: t for t in KnowledgeType}
        # الأنواع المعتمدة التي لا مقابل حضرياً لها → أقرب دلالة (معلنة في ADR)
        extra = {
            "evidence": KnowledgeType.METADATA, "anti_pattern": KnowledgeType.PATTERN,
            "architecture": KnowledgeType.METADATA, "concept": KnowledgeType.METADATA,
            "policy": KnowledgeType.RULE, "benchmark": KnowledgeType.METADATA,
            "standard": KnowledgeType.RULE, "ontology": KnowledgeType.METADATA,
            "playbook": KnowledgeType.PATTERN, "runbook": KnowledgeType.PATTERN,
            "best_practice": KnowledgeType.PATTERN, "lesson": KnowledgeType.PATTERN,
            "decision": KnowledgeType.RULE,
        }
        mapping.update(extra)
        _CIVILIZATION_TYPE_MAP = mapping
    return _CIVILIZATION_TYPE_MAP


def _evidence_dict_to_canonical(ev: Dict[str, Any], ko_id: str, index: int):
    """دليل حضاري (قاموس) → دليل معتمد كامل الحقول — عبر المساعدات الموحدة
    داخل حزمة المعرفة المعتمدة (`knowledge.convert`) — لا نسخ متضاربة."""
    from agos_kernel.knowledge.convert import evidence_dict_to_canonical
    return evidence_dict_to_canonical(ev, ko_id, index)


def _evidence_canonical_to_dict(ev) -> Dict[str, Any]:
    """دليل معتمد → قاموس حضري كامل الحقول المعلنة — عبر المساعدات الموحدة."""
    from agos_kernel.knowledge.convert import evidence_canonical_to_dict
    return evidence_canonical_to_dict(ev)


class KnowledgeRegistry:
    def __init__(self):
        self.knowledge: Dict[str, KnowledgeObject] = {}
        self.by_type: Dict[str, List[str]] = {}
        # R-W1-005 (ADR-0002): سجل تدقيق المادة 13 — يُختم تلقائياً عند التسجيل
        self.article13_audit: Dict[str, Dict[str, Any]] = {}
    
    def register(self, ko: KnowledgeObject) -> None:
        # R-W1-005 (ADR-0002): حد الاعتماد إلزامي — التسجيل نفسه يختم التدقيق
        # (لا يتذكر المستهلك استدعاء الفحص). الناقص يُقبل بوصفه ناقصاً معلناً.
        self.article13_audit[ko.ko_id] = ko.article13
        self.knowledge[ko.ko_id] = ko
        ktype = ko.knowledge_type.value if isinstance(ko.knowledge_type, KnowledgeType) else ko.knowledge_type
        if ktype not in self.by_type:
            self.by_type[ktype] = []
        self.by_type[ktype].append(ko.ko_id)
    
    def get(self, ko_id: str) -> Optional[KnowledgeObject]:
        return self.knowledge.get(ko_id)
    
    def search(self, query: str) -> List[KnowledgeObject]:
        return [k for k in self.knowledge.values() if query.lower() in k.content.lower()]
    
    def get_canonical(self, ko_id: str):
        """R-W1-005 (ADR-0002): قراءة بالكائن المعتمد — تمثيل معتمد لما هو مسجل فعلاً."""
        ko = self.get(ko_id)
        return ko.to_canonical() if ko is not None else None
    
    def article13_report(self) -> Dict[str, Any]:
        """R-W1-005: تقرير المادة 13 على كل المسجل — تحقق حي وقت التقرير."""
        from agos_kernel.knowledge.article13 import article13_status
        statuses = [article13_status(ko.to_canonical()) for ko in self.knowledge.values()]
        return {
            "total": len(self.knowledge),
            "constitutionally_complete": sum(1 for s in statuses if s["valid"]),
            "incomplete": sum(1 for s in statuses if not s["valid"]),
            "by_requirement": {
                req: sum(1 for s in statuses for v in s["violations"]
                         if v["requirement"] == req)
                for req in ("Source", "Evidence", "Confidence", "Version",
                            "Timestamp", "Lineage")
            },
        }


class KnowledgeRuntime:
    VERSION = "1.0"
    
    def __init__(self):
        self.registry = KnowledgeRegistry()
    
    def create_knowledge(self, ktype: KnowledgeType, content: str, source: str = "",
                         confidence: float = 1.0, version: str = "1.0.0",
                         evidence: Optional[List[Dict[str, Any]]] = None,
                         lineage: Optional[List[str]] = None,
                         ) -> KnowledgeObject:
        """R-W1-005: معاملات المادة 13 اختيارية — النداءات القديمة تعمل كما كانت."""
        # زمن الإنشاء يُختم مرة واحدة عند الإنشاء — زمن حقيقي لا وقت تحويل (ADR-0002)
        ko = KnowledgeObject(knowledge_type=ktype, content=content, source=source,
                             confidence=confidence, version=version,
                             evidence=evidence or [], lineage=lineage,
                             created_at=datetime.now())
        self.registry.register(ko)
        return ko
    
    def relate(self, ko_id1: str, ko_id2: str) -> None:
        ko1 = self.registry.get(ko_id1)
        ko2 = self.registry.get(ko_id2)
        if ko1 and ko2:
            ko1.relationships.append(ko_id2)
            ko2.relationships.append(ko_id1)
    
    def get_knowledge_report(self) -> Dict:
        return {
            'total_knowledge': len(self.registry.knowledge),
            'by_type': {t: len(ids) for t, ids in self.registry.by_type.items()}
        }