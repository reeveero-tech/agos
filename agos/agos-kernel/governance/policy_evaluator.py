"""مقيم السياسات المعتمد — مسار واحد لتقييم السياسات (R-W1-007، ADR-0010).

المقيم الذي تستعمله ``GovernanceRuntime`` والواجهات القديمة جميعاً التي
تقيّم سياسات. الحكم معلل دائماً؛ وغياب القاعدة أو نقص المدخل **ليس
امتثالاً مثبتاً**:

- ``compliant``: فحص ناجح لقاعدة معروفة بمواصفة تنفيذية ومدخل كامل.
- ``violation``: فحص ناجح كشف مخالفة (مع سبب معلل).
- ``unverified``: القاعدة غير معروفة، أو بلا مواصفة تنفيذية، أو المدخل
  ناقص — لا يُدّعى امتثال ولا تُختلق مخالفة.

القاعدة بلا مواصفة تنفيذية = حكم غير مثبت: ``unverified`` معلل عبر
``GovernanceRuntime`` كذلك (ADR-0010 §القرار 2 منقّح — سجل العمل 0062).
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

    def registered_rule_ids(self) -> List[str]:
        """المعرّفات المسجلة لدى المقيم بترتيب الإدراج — الإفصاح عن التشريع
        المفعّل (يستعمله مصدر القواعد الافتراضي واختبارات الاتساق)."""
        return list(self._specs)

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
        if kind == "declared_membership":
            # عضوية قيمة في قوائم معلنة (توحيد حالة وعضوية كاملة — لا بحث
            # عن عبارات داخل نص حر): حكم على التصنيف النصي المقدم وفق
            # الإعلان المعتمد، لا على التغيير البرمجي الفعلي
            frozen = spec.get("frozen_components")
            allowed = spec.get("allowed_changes")
            forbidden = spec.get("forbidden_changes")
            if not all(isinstance(lst, list) and lst
                      for lst in (frozen, allowed, forbidden)):
                return PolicyVerdict(
                    rule_id=rule_id,
                    verdict=VERDICT_UNVERIFIED,
                    reason="مواصفة ناقصة — قوائم العضوية المعلنة غير "
                           "معرفة، فلا فحص ولا امتثال مثبت",
                )
            change = entity.get("change")
            component = entity.get("component")
            if change is None or component is None:
                return PolicyVerdict(
                    rule_id=rule_id,
                    verdict=VERDICT_UNVERIFIED,
                    reason="مدخل ناقص — التصنيف أو المكوّن غائب فلا فحص",
                )

            def _norm(value: Any) -> str:
                return str(value).strip().casefold()

            # توحيد الحالة للتصنيف فقط؛ أما عضوية المكوّن فمطابقة
            # لمفاتيح الإعلان كما هي — لا تُختلق أسماء بديلة للمكوّنات
            # (المقيم قد يوحد الحالة فيسمح لمعرّف لا تعدّه الواجهة مسجلاً)
            change_n = _norm(change)
            frozen_exact = {str(c) for c in frozen}
            allowed_n = {_norm(c) for c in allowed}
            forbidden_n = {_norm(c) for c in forbidden}
            if component not in frozen_exact:
                return PolicyVerdict(
                    rule_id=rule_id,
                    verdict=VERDICT_UNVERIFIED,
                    reason="المكوّن غير مسجل في إعلان التجميد — لا قاعدة "
                           "تجميد في نطاقه فلا امتثال مثبت",
                )
            in_allowed = change_n in allowed_n
            in_forbidden = change_n in forbidden_n
            if in_allowed and in_forbidden:
                return PolicyVerdict(
                    rule_id=rule_id,
                    verdict=VERDICT_UNVERIFIED,
                    reason="التصنيف معلن في القائمتين معاً (تعارض "
                           "الإعلان) — لا يُعلن سماح",
                )
            if in_forbidden:
                return PolicyVerdict(
                    rule_id=rule_id,
                    verdict=VERDICT_VIOLATION,
                    reason="التصنيف ممنوع في إعلان التجميد للمكوّن المجمد",
                )
            if in_allowed:
                return PolicyVerdict(
                    rule_id=rule_id,
                    verdict=VERDICT_COMPLIANT,
                    reason="التصنيف النصي المقدم مسموح وفق إعلان التجميد — "
                           "ضمن حدود التصنيف فقط، لا حكماً على التغيير "
                           "البرمجي الفعلي",
                )
            return PolicyVerdict(
                rule_id=rule_id,
                verdict=VERDICT_UNVERIFIED,
                reason="تصنيف مجهول — ليس في قوائم الإعلان فلا امتثال مثبت",
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


# ---------------------------------------------------------------
# قاعدة تغييرات التجميد المعماري: حكم العضوية في قوائم إعلان التجميد
# (الشريحة السادسة — R-W1-007). المواصفة تُبنى من الإعلان الحالي نفسه
# عند كل حكم فلا تنفصل القوائم التي يقرأها المدير عن التي يحكم بها
# المقيم؛ والمثبت محدود: التصنيف النصي المقدم مسموح/ممنوع وفق الإعلان —
# لا حكماً على التغيير البرمجي الفعلي.
# ---------------------------------------------------------------
FREEZE_CHANGE_RULE_ID = "architecture-freeze-change-classification"


def freeze_change_spec(
        frozen_components: List[str],
        allowed_changes: List[str],
        forbidden_changes: List[str]) -> Dict[str, Any]:
    """مواصفة حكم تغييرات التجميد — المدخل قوائم الإعلان نفسها."""
    return {
        "kind": "declared_membership",
        "source": "إعلان التجميد — ArchitectureFreeze",
        "applies_to_types": ["ArchitectureChange"],
        "frozen_components": list(frozen_components),
        "allowed_changes": list(allowed_changes),
        "forbidden_changes": list(forbidden_changes),
    }


def shared_evaluator() -> PolicyEvaluator:
    """المقيم المشترك المعتمد — مسار تقييم واحد للجميع (ADR-0010).

    يسجّل التشريع المفعّل من إعلانه الواحد (``enacted_constitution_specs``)
    — المادة 5 من مصدرها النصي المعلن (قائمة الأنواع في الدستور تُقرأ من
    الوثيقة نفسها، لا تُنسخ هنا فينسى تحديثها).
    """
    evaluator = PolicyEvaluator()
    for rule_id, spec in enacted_constitution_specs().items():
        evaluator.register_spec(rule_id, spec)
    return evaluator


def evaluate_rule_dicts(rules: List[Any],
                         context: Dict[str, Any]) -> Dict[str, Any]:
    """تقييم قواعد سياسة (قواميس) عبر المقيم المعتمد — للواجهات المكتشفة
    (R-W1-007، الشريحة الثالثة — ADR-0010).

    القاعدة القابلة للفحص الوحيدة: **قاموس يحمل ``rule_id`` معرّفَ قاعدة
    مسجلة** لدى المقيم؛ ما سواه (نص حر، قاموس بلا rule_id، معرّف غير
    مسجل) غير قابل للفحص — لا يُعلن سماحاً بلا فحص. السماح مثبت فقط بفحص
    ناجح لكل القواعد؛ والمخالفة والتحقق المتعذر كلاهما لا يُعلن سماحاً.
    """
    evaluator = get_shared_evaluator()
    results: List[Dict[str, Any]] = []
    if not rules:
        return {"allowed": False,
                "reason": "السياسة بلا قواعد — لا فحص ولا سماح مثبت",
                "results": results}
    # نتيجة معللة لكل قاموس قاعدة بالترتيب (تصحيح المراجعة — الشريحة
    # الثالثة): لا تُسقط نتائج القواعد اللاحقة بسبب أول رفض؛ وواجهة
    # الحضارة السابقة كانت تُرجع نتيجة لكل قاموس قاعدة — والحكم الإجمالي
    # يُحسب بعد جمع كل النتائج
    decisive_reason = None

    def _note(reason: str) -> None:
        nonlocal decisive_reason
        if decisive_reason is None:
            decisive_reason = reason

    for rule in rules:
        if not isinstance(rule, dict) or "rule_id" not in rule:
            # قاعدة غير قابلة للفحص: تظهر نتيجتها (passed=False و
            # unverified) ولا تُختفى — عدم التحقق يشمل غياب المواصفة
            # التنفيذية لا نقص مدخل قاعدة معروفة فقط
            results.append({
                "rule": (rule.get("name")
                         if isinstance(rule, dict) else None),
                "passed": False,
                "verdict": VERDICT_UNVERIFIED,
                "reason": "قاعدة غير قابلة للفحص (ليست قاموساً بمعرّف قاعدة "
                          "rule_id) — لا يُحوَّل الشكل الحر آلياً"})
            _note("قاعدة غير قابلة للفحص (ليست قاموساً بمعرّف قاعدة "
                  "rule_id) — لا يُحوَّل الشكل الحر آلياً")
            continue
        rule_id = str(rule["rule_id"])
        if evaluator.get_spec(rule_id) is None:
            results.append({
                "rule": rule.get("name"),
                "passed": False,
                "rule_id": rule_id,
                "verdict": VERDICT_UNVERIFIED,
                "reason": "قاعدة غير قابلة للفحص (معرّف غير مسجل): "
                          "{!r}".format(rule_id)})
            _note("قاعدة غير قابلة للفحص (معرّف غير مسجل): "
                  "{!r}".format(rule_id))
            continue
        verdict = evaluator.evaluate(rule_id, context)
        # عقد المخرج المتداخل محفوظ: ``rule`` اسم القاعدة كما كان في واجهة
        # الحضارة (لا المعرّف)؛ و``passed`` منطقي — True للامتثال المثبت
        # فقط وFalse للمخالفة وعدم التحقق؛ وrule_id/verdict إضافتان لا
        # استبدال
        results.append({"rule": rule.get("name"),
                        "passed": verdict.verdict == VERDICT_COMPLIANT,
                        "rule_id": rule_id,
                        "verdict": verdict.verdict,
                        "reason": verdict.reason})
        if verdict.verdict != VERDICT_COMPLIANT:
            # مخالفة معللة أو تحقق متعذر — كلاهما لا يُعلن سماحاً
            _note("{}: {}".format(verdict.verdict, verdict.reason))
    if decisive_reason is None:
        return {"allowed": True,
                "reason": "فحص كل قواعد السياسة ناجح — سماح مثبت",
                "results": results}
    return {"allowed": False,
            "reason": decisive_reason,
            "results": results}


# المقيم المشترك على مستوى الوحدة — هوية واحدة للتفويض (مسار واحد)
_SHARED: Optional[PolicyEvaluator] = None


def get_shared_evaluator() -> PolicyEvaluator:
    """المقيم المشترك (كائن واحد — استخدام الواجهات له يثبت المسار الموحد)."""
    global _SHARED
    if _SHARED is None:
        _SHARED = shared_evaluator()
    return _SHARED


# ---------------------------------------------------------------
# التشريع المفعّل — إعلان واحد يستهلكه المصنع المعتمد ومصدر القواعد
# الافتراضي معاً (تصحيح الشريحة السابعة — سجل العمل 0075): إضافة تشريع
# هنا تُحدّث المصنع والمصدر معاً بلا نسختين تنفصل إحداهما عن الأخرى.
# بناء المواصفة كسول (لا استيراد دستوري عند استيراد الوحدة).
# ---------------------------------------------------------------
_ENACTED_CONSTITUTION_SPEC_BUILDERS = {
    CONSTITUTION_ARTICLE_5_RULE_ID: lambda: constitution_article_5_spec(
        _constitution_versioned_entities()),
}

ENACTED_CONSTITUTION_RULE_IDS = tuple(_ENACTED_CONSTITUTION_SPEC_BUILDERS)


def _constitution_versioned_entities() -> List[str]:
    """قائمة الأنواع المنصوصة من النص الدستوري نفسه — لا نسخة هنا."""
    from agos.constitution.constitution import VERSIONED_ENTITIES
    return VERSIONED_ENTITIES


def enacted_constitution_specs() -> Dict[str, Dict[str, Any]]:
    """التشريع المفعّل كاملاً بمواصفاته — الإعلان الواحد الذي يسجله المصنع
    المعتمد وتُبنى منه قواعد الترخيص الافتراضية."""
    return {rule_id: build()
            for rule_id, build in _ENACTED_CONSTITUTION_SPEC_BUILDERS.items()}


def default_policy_rules() -> List[Dict[str, Any]]:
    """قواعد الترخيص الافتراضية للمحرك المحلي — من الإعلان الواحد نفسه الذي
    يستهلكه المصنع المعتمد (لا نسخة ثانية تنفصل عن المقيم).

    القاعدة القابلة للفحص قاموس يحمل ``rule_id`` معرّفَ قاعدة مسجلة؛ والمصدر
    هنا التشريع المفعّل المعلن في ``_ENACTED_CONSTITUTION_SPEC_BUILDERS``
    (تُستورد معرفاته من ``ENACTED_CONSTITUTION_RULE_IDS``)، فأي تشريع جديد
    يضاف للإعلان يظهر في المصنع والمصدر معاً. البوابة
    (``GovernanceRuntime.authorize_execution``) تستشير هذا المصدر بدل قائمة
    فارغة يختارها الطلب لنفسه — والسماح يبقى مثبتاً فقط بفحص ناجح لكل
    القواعد (لا امتثال بلا فحص).
    """
    return [{"rule_id": rule_id} for rule_id in ENACTED_CONSTITUTION_RULE_IDS]
