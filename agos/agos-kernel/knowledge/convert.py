#!/usr/bin/env python3
"""مساعدات التحويل المشتركة للأدلة — R-W1-005 / ADR-0002.

تُستعمل من كل الأسر (kernel/civilization/fabric) كي لا يتكرر منطق التحويل
فيتضارب. سياسة الصدق:
- زمن جمع الدليل (`collected_at`): القيمة الصحيحة تُحفظ كما هي؛ والمفقود
  يبقى `None` (مجهول معلن) — **لا يُختلق `now()`**؛ والقيمة غير القابلة
  للتحليل تحفظ خاماً في `metadata["collected_at_raw"]` ويعلن الزمن مجهولاً.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from .models import Evidence, EvidenceQuality


def evidence_dict_to_canonical(ev: Dict[str, Any], owner_id: str, index: int) -> Evidence:
    """دليل قاموسي (أي أسرة) → دليل معتمد كامل الحقول — بلا فقد ولا اختلاق."""
    quality = EvidenceQuality.MEDIUM
    if ev.get("quality"):
        try:
            quality = EvidenceQuality(str(ev["quality"]))
        except ValueError:
            quality = EvidenceQuality.MEDIUM
    collected_at = None
    raw_collected = ev.get("collected_at")
    extra_meta: Dict[str, Any] = dict(ev.get("metadata", {}) or {})
    if isinstance(raw_collected, datetime):
        collected_at = raw_collected
    elif raw_collected is not None:
        # قيمة نصية قابلة للتحليل → تُحل؛ وأي قيمة أخرى (نص فاسد/رقم/غيره)
        # تُحفظ خاماً في collected_at_raw ويُعلن الزمن مجهولاً — لا فقد صامت ولا اختلاق
        parsed = None
        if isinstance(raw_collected, str) and raw_collected.strip():
            try:
                parsed = datetime.fromisoformat(raw_collected)
            except ValueError:
                parsed = None
        if parsed is not None:
            collected_at = parsed
        else:
            extra_meta["collected_at_raw"] = raw_collected
    # المصدر: السلاسل فقط تمر كما هي؛ وغير ذلك (None/رقم) يصير خاوياً —
    # نقص يُعلن عند الفحص، لا نصاً مختلقاً مثل "None" يجتاز الفحص
    raw_source = ev.get("source")
    ev_source = raw_source if isinstance(raw_source, str) else ""
    return Evidence(
        id=str(ev.get("id") or f"{owner_id}-ev-{index}"),
        content=str(ev.get("content", "")),
        source=ev_source,
        source_url=str(ev.get("source_url", "") or ""),
        quality=quality,
        collected_at=collected_at,
        verified=bool(ev.get("verified", False)),
        verified_by=str(ev.get("verified_by", "") or ""),
        metadata=extra_meta,
    )


def evidence_canonical_to_dict(ev: Evidence) -> Dict[str, Any]:
    """دليل معتمد → قاموس كامل الحقول المعلنة — بلا فقد صامت."""
    out: Dict[str, Any] = {
        "id": ev.id,
        "content": ev.content,
        "source": ev.source,
        "source_url": ev.source_url,
        "quality": ev.quality.value,
        "collected_at": ev.collected_at.isoformat() if ev.collected_at else None,
        "verified": ev.verified,
        "verified_by": ev.verified_by,
    }
    if ev.metadata:
        out["metadata"] = dict(ev.metadata)
    return out


def knowledge_dict_to_canonical(ko: Dict[str, Any]) -> Any:
    """قاموس كائن معرفة عام (بوابات الجودة وغيرها) → الكائن المعتمد.
    
    المفاتيح المتوقعة (كلها اختيارية — والناقص يُعلن عند الفحص):
    name/title، content، source، evidence (قائمة قواميس أو قيم خام)،
    confidence، version، lineage، created_at (ISO أو None).
    لا يُختلق شيء: القيمة الخام غير القابلة للتحويل تعلن نقصاً.
    """
    from datetime import datetime as _dt
    from .models import Knowledge, KnowledgeMetadata, KnowledgeType

    title = str(ko.get("title") or ko.get("name") or ko.get("content", "") or "knowledge")
    created_at = None
    raw_created = ko.get("created_at")
    if isinstance(raw_created, _dt):
        created_at = raw_created
    elif isinstance(raw_created, str) and raw_created.strip():
        try:
            created_at = _dt.fromisoformat(raw_created)
        except ValueError:
            created_at = None   # غير قابل للتحويل → نقص معلن

    # الأدلة: القواميس تمر كما هي؛ والقيم الخام (سلاسل/أرقام) تلف بلا مصدر
    # مختلق — مصدرها الخالي نقص يُعلن عند الفحص؛ وقيمة غير قائمة لا تُحوَّل
    # إلى ما يجتاز الفحص (المدقق يخرقها باسم Evidence)
    raw_evidence = ko.get("evidence")
    if not isinstance(raw_evidence, list):
        raw_evidence = []
    normalized_evidence = []
    for i, ev in enumerate(raw_evidence):
        if isinstance(ev, dict):
            normalized_evidence.append(ev)
        else:
            normalized_evidence.append({"content": str(ev), "source": ""})

    # المصدر الأولي: السلاسل فقط — لا تحويل رقم/None إلى نص يبدو صالحاً
    raw_source = ko.get("source")
    primary_source = raw_source if isinstance(raw_source, str) else ""
    # الإصدار: السلاسل فقط — لا تحويل رقم إلى "123" يبدو صالحاً (خرق Version معلن)
    raw_version = ko.get("version")
    ko_version = raw_version if isinstance(raw_version, str) else ""
    metadata = KnowledgeMetadata(
        title=str(title)[:60],
        sources=[primary_source] if primary_source else [],
        version=ko_version,
    )
    return Knowledge(
        id=str(ko.get("id") or ko.get("name") or "ko"),
        knowledge_type=KnowledgeType.FACT,
        metadata=metadata,
        summary=str(ko.get("content", "")),
        content={"raw": str(ko.get("content", ""))},
        evidence=[evidence_dict_to_canonical(ev, str(ko.get("id") or ko.get("name") or "ko"), i)
                 for i, ev in enumerate(normalized_evidence)],
        source=primary_source,
        confidence=ko.get("confidence"),
        lineage=ko.get("lineage"),
        created_at=created_at,
    )
