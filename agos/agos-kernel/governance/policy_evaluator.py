"""مقيم السياسات المعتمد — مسار واحد لتقييم السياسات (R-W1-007، ADR-0010).

المقيم الذي تستعمله ``GovernanceRuntime`` والواجهات القديمة جميعاً التي
تقيّم سياسات. الحكم معلل دائماً؛ وغياب القاعدة أو نقص المدخل **ليس
امتثالاً مثبتاً**:

- ``compliant``: فحص ناجح لقاعدة معروفة بمواصفة تنفيذية ومدخل كامل.
- ``violation``: فحص ناجح كشف مخالفة (مع سبب معلل).
- ``unverified``: القاعدة غير معروفة، أو بلا مواصفة تنفيذية، أو المدخل
  ناقص — لا يُدّعى امتثال ولا تُختلق مخالفة.

القاعدة بلا مواصفة تنفيذية = حكم غير مثبت (مسار ``GovernanceRuntime``
القديم يبقى حرفياً لها — ADR-0010 §القرار 2).
"""
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

# أحكام التقييم الثلاثة — لا امتثالاً مثبتاً عند غياب القاعدة أو نقص المدخل
VERDICT_COMPLIANT = "compliant"
VERDICT_VIOLATION = "violation"
VERDICT_UNVERIFIED = "unverified"


@dataclass
class PolicyVerdict:
    """حكم معلل على كيان تجاه قاعدة سياسات."""

    rule_id: str
    verdict: str
    reason: str

    @property
    def compliant_proven(self) -> bool:
        """الامتثال المثبت فقط — حكم unverified ليس امتثالاً."""
        return self.verdict == VERDICT_COMPLIANT


class PolicyEvaluator:
    """مقيم سياسات واحد (ADR-0010): قواعد ذات مواصفات تنفيذية وأحكام معللة.

    المواصفة (spec) تحدد نوع الفحص ومدخلاته المطلوبة — القاعدة من دون
    مواصفة لا تُقيَّم (حكم unverified) ولا يُدّعى لها امتثال.
    """

    def __init__(self) -> None:
        self._specs: Dict[str, Dict[str, Any]] = {}
        # سجل الاستدعاءات — يُثبت وصول الواجهات إلى المقيم (اختبار التتبع)
        self.evaluation_log: List[Any] = []

    def register_spec(self, rule_id: str, spec: Dict[str, Any]) -> None:
        """تسجيل المواصفة التنفيذية لقاعدة — القاعدة نصاً والمواصفة فحصاً."""
        self._specs[rule_id] = spec

    def get_spec(self, rule_id: str) -> Optional[Dict[str, Any]]:
        return self._specs.get(rule_id)

    def evaluate(self, rule_id: str, entity: Dict[str, Any]) -> PolicyVerdict:
        """تقييم كيان تجاه قاعدة — الحكم معلل ولا امتثال بلا فحص ناجح.

        - قاعدة غير معروفة أو بلا مواصفة ⇒ ``unverified`` (لا يُدّعى تقييم).
        - مواصفة ``applies_to_types``: إن لم يكن نوع الكيان منصوصاً فيه فلا
          تُطبَّق القاعدة عليه أصلاً (لا امتثال ولا مخالفة يُدَّعى)؛ وغياب
          النوع من المدخل كلياً ⇒ ``unverified``.
        - مواصفة ``required_fields``: الحقول المطلوبة من مدخل الكيان؛ الحقل
          المطلوب غائب عن الكيان ⇒ ``violation`` معللة.
        """
        self.evaluation_log.append((rule_id, dict(entity)))
        spec = self._specs.get(rule_id)
        if spec is None:
            return PolicyVerdict(
                rule_id=rule_id,
                verdict=VERDICT_UNVERIFIED,
                reason="قاعدة غير معروفة أو بلا مواصفة تنفيذية — "
                       "لا فحص ولا امتثال مثبت",
            )
        applies_to = spec.get("applies_to_types")
        if applies_to is not None:
            entity_type = entity.get("type")
            if entity_type is None:
                return PolicyVerdict(
                    rule_id=rule_id,
                    verdict=VERDICT_UNVERIFIED,
                    reason="نوع الكيان غائب من المدخل — لا يُعرف هل تنطبق "
                           "القاعدة عليه",
                )
            if entity_type not in applies_to:
                return PolicyVerdict(
                    rule_id=rule_id,
                    verdict=VERDICT_UNVERIFIED,
                    reason="القاعدة لا تنطبق على نوع {!r} — "
                           "لا امتثال ولا مخالفة يُدَّعى".format(entity_type),
                )
        kind = spec.get("kind")
        if kind == "required_fields":
            # المواصفة الناقصة ليست قائمة سماح فارغة (تصحيح المراجعة):
            # غياب تعريف الحقول المطلوبة أو فراغها = لا حقول مفحوصة —
            # حكم unverified بسبب نقص المواصفة، لا امتثال بلا فحص
            required = spec.get("required_fields")
            if not isinstance(required, list) or not required:
                return PolicyVerdict(
                    rule_id=rule_id,
                    verdict=VERDICT_UNVERIFIED,
                    reason="مواصفة ناقصة — لا حقول مفحوصة معرفة، فلا فحص "
                           "ولا امتثال مثبت",
                )
            for field_name in required:
                if field_name not in entity:
                    return PolicyVerdict(
                        rule_id=rule_id,
                        verdict=VERDICT_VIOLATION,
                        reason="الكيان من نوع منصوص تخلو مدخلاته من الحقل "
                               "المطلوب {!r} (مخالفة معلنة)".format(field_name),
                    )
            return PolicyVerdict(
                rule_id=rule_id,
                verdict=VERDICT_COMPLIANT,
                reason="فحص الحقول المطلوبة ناجح — امتثال مثبت",
            )
        return PolicyVerdict(
            rule_id=rule_id,
            verdict=VERDICT_UNVERIFIED,
            reason="نوع فحص غير معروف {!r} — لا يُدّعى تقييم".format(kind),
        )


# ---------------------------------------------------------------
# القاعدة المنصوصة للشريحة الأولى: الدستور المادة 5 (VERSIONED_ENTITIES)
# — «كل كيان من هذه الأنواع يحمل إصداراً». النص المرجعي:
#   agos/constitution/constitution.py (VERSIONED_ENTITIES)؛ الفحص: وجود
#   حقل الإصدار في مدخل الكيان.
# ---------------------------------------------------------------
CONSTITUTION_ARTICLE_5_RULE_ID = "constitution-article-5-versioning"


def constitution_article_5_spec(
        versioned_entities: List[str]) -> Dict[str, Any]:
    """مواصفة المادة 5 التنفيذية — المدخل قائمة الأنواع المنصوصة نفسها."""
    return {
        "kind": "required_fields",
        "source": "الدستور المادة 5 — VERSIONED_ENTITIES",
        "applies_to_types": list(versioned_entities),
        "required_fields": ["version"],
    }


def shared_evaluator() -> PolicyEvaluator:
    """المقيم المشترك المعتمد — مسار تقييم واحد للجميع (ADR-0010).

    يسجّل مواصفة المادة 5 من مصدرها النصي المعلن (قائمة الأنواع في الدستور
    تُقرأ من الوثيقة نفسها، لا تُنسخ هنا فينسى تحديثها).
    """
    evaluator = PolicyEvaluator()
    from agos.constitution.constitution import VERSIONED_ENTITIES
    evaluator.register_spec(
        CONSTITUTION_ARTICLE_5_RULE_ID,
        constitution_article_5_spec(VERSIONED_ENTITIES),
    )
    return evaluator


# المقيم المشترك على مستوى الوحدة — هوية واحدة للتفويض (مسار واحد)
_SHARED: Optional[PolicyEvaluator] = None


def get_shared_evaluator() -> PolicyEvaluator:
    """المقيم المشترك (كائن واحد — استخدام الواجهات له يثبت المسار الموحد)."""
    global _SHARED
    if _SHARED is None:
        _SHARED = shared_evaluator()
    return _SHARED
