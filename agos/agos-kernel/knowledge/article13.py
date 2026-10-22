#!/usr/bin/env python3
"""مدقق المادة 13 — متطلبات كائن المعرفة (R-W1-005 / ADR-0002).

الدستور (`agos/constitution/constitution.py`) ينص:
    KNOWLEDGE_OBJECT_REQUIREMENTS = ["Source", "Evidence", "Confidence",
                                      "Version", "Timestamp", "Lineage"]

هذه الوحدة تنفذ الفحص على النموذج المعتمد `knowledge.models.Knowledge`.
النواة لا تستورد حزمة الدستور الخارجية (اتجاه اعتماد نظيف)؛ المطلوبات
تُعلن هنا ويُثبت اختبار المساواة (في test_knowledge_unification) أنها مطابقة
حرفياً لثابت الدستور — أي تعديل دستوري لاحق يكسر الاختبار فوراً.

دلالات الحقول (ADR-0002):
- Source: `source` غير خاوٍ؛ وإن وُجدت `metadata.sources` فلا بد أن يكون
  المصدر الأولي ضمنها (لا تضارب بين مصدرين للحقيقة نفسها).
- Evidence: قائمة أدلة غير خاوية، وكل دليل مصدره غير خاوٍ.
- Confidence: `None` = مجهولة (نقص معلن)، `0.0` = صفر معلن مقبول،
  وإلا يجب أن تكون في `[0, 1]`.
- Version: `metadata.version` غير خاوٍ.
- Timestamp: `created_at` غير خاوٍ (ختم إنشاء الكائن المعتمد نفسه).
- Lineage: `None` = مجهول (نقص معلن)، `[]` = جذر معلن صراحة،
  وقائمة معرفات = معرفة مشتقة.
"""
from __future__ import annotations

from typing import Any, Dict, List

# مطابقة حرفياً لثابت الدستور — يثبتها اختبار المزامنة
ARTICLE_13_REQUIREMENTS: List[str] = [
    "Source", "Evidence", "Confidence", "Version", "Timestamp", "Lineage",
]


def _violation(requirement: str, message: str) -> Dict[str, Any]:
    return {
        "article": 13,
        "requirement": requirement,
        "severity": "high",
        "message": message,
    }


def validate_article_13(knowledge) -> List[Dict[str, Any]]:
    """أعد قائمة خرق المادة 13 على كائن معرفة معتمد.

    القائمة الخاوية = كائن مكتمل دستورياً. النقص يُعاد باسمه — لا يُختلق
    مصدر ولا دليل ولا ثقة لاجتياز الفحص (سياسة البيانات القديمة).
    """
    violations: List[Dict[str, Any]] = []

    # Source — المصدر الأولي غير الخاوي واتساقه مع قائمة المصادر
    source = (getattr(knowledge, "source", "") or "").strip()
    if not source:
        violations.append(_violation(
            "Source", "primary source is empty"))
    metadata_sources = getattr(getattr(knowledge, "metadata", None), "sources", None)
    if metadata_sources and source and source not in metadata_sources:
        violations.append(_violation(
            "Source",
            f"primary source {source!r} not among metadata.sources"))

    # Evidence — قائمة أدلة غير خاوية وكل دليل بمصدره
    evidence = getattr(knowledge, "evidence", None) or []
    if not evidence:
        violations.append(_violation(
            "Evidence", "no evidence attached"))
    else:
        for ev in evidence:
            if not (getattr(ev, "source", "") or "").strip():
                violations.append(_violation(
                    "Evidence", f"evidence {getattr(ev, 'id', '?')} has empty source"))

    # Confidence — معلومة لا مجهولة، وداخل النطاق [0, 1]
    confidence = getattr(knowledge, "confidence", None)
    if confidence is None:
        violations.append(_violation(
            "Confidence", "confidence is unknown (None)"))
    elif not (0.0 <= confidence <= 1.0):
        violations.append(_violation(
            "Confidence", f"confidence {confidence} outside [0, 1]"))

    # Version — إصدار غير خاوٍ (مصدر الحقيقة الوحيد: metadata.version)
    version = (getattr(knowledge, "version", "") or "").strip()
    if not version:
        violations.append(_violation(
            "Version", "version is empty"))

    # Timestamp — ختم إنشاء الكائن المعتمد نفسه (يجب أن يكون طابعاً زمنياً صالحاً)
    from datetime import datetime as _dt
    created_at = getattr(knowledge, "created_at", None)
    if not isinstance(created_at, _dt):
        violations.append(_violation(
            "Timestamp", "created_at is not a valid timestamp"))

    # Lineage — نسب معلن: جذر صريح [] أو قائمة معرفات صالحة (سلاسل غير خاوية)؛
    # المجهول والأنواع غير القائمة (سلسلة/رقم/غيره) نقص معلن
    lineage = getattr(knowledge, "lineage", None)
    valid_lineage = (
        isinstance(lineage, list)
        and all(isinstance(item, str) and item.strip() for item in lineage)
    )
    if not valid_lineage:
        violations.append(_violation(
            "Lineage", "lineage is not a list of valid parent ids (or declared root [])"))

    return violations


def article13_status(knowledge) -> Dict[str, Any]:
    """حالة المادة 13 لكائن معرفة — تُختم عند التسجيل (حد الاعتماد، ADR-0002)."""
    violations = validate_article_13(knowledge)
    return {
        "valid": len(violations) == 0,
        "violations": violations,
        "requirements": list(ARTICLE_13_REQUIREMENTS),
    }
