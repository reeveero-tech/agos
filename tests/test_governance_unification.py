"""اختبارات توحيد الحوكمة (R-W1-007، الشريحة الأولى — ADR-0010).

مسار واحد لتقييم السياسات: المقيم المعتمد داخل agos_kernel.governance
يستعمله GovernanceRuntime والواجهة القديمة معاً. الحكم معلل، وغياب القاعدة
أو نقص المدخل ليس امتثالاً مثبتاً.
"""
from agos_kernel.governance import GovernanceDomain, GovernanceRuntime
from agos_kernel.governance.policy_evaluator import (
    CONSTITUTION_ARTICLE_5_RULE_ID, get_shared_evaluator)
from agos_kernel.governance.runtime import GovernanceRule
from agos.governance.enforcement import VersionValidator
from agos.constitution.constitution import VERSIONED_ENTITIES


def _runtime_with_article5() -> GovernanceRuntime:
    runtime = GovernanceRuntime()
    runtime.add_rule(GovernanceRule(
        id=CONSTITUTION_ARTICLE_5_RULE_ID,
        name="الدستور المادة 5 — الإصدار",
        domain=GovernanceDomain.POLICIES,
        description="كل كيان من الأنواع المنصوصة يحمل إصداراً",
        severity="error",
    ))
    return runtime


def test_same_rule_compliant_and_violation():
    """القاعدة نفسها: حالة مسموحة وأخرى مخالفة — عبر المسارين معاً."""
    runtime = _runtime_with_article5()
    ok_entity = {"type": "Contracts", "version": "1.0"}
    bad_entity = {"type": "Contracts"}
    # المحرك
    ok_result = runtime.check_compliance(
        "e1", "contract", entity=ok_entity)
    bad_result = runtime.check_compliance(
        "e2", "contract", entity=bad_entity)
    assert ok_result["compliant"] is True
    assert ok_result["violations"] == []
    assert bad_result["compliant"] is False
    assert bad_result["violations"][0]["rule_id"] == \
        CONSTITUTION_ARTICLE_5_RULE_ID
    assert "version" in bad_result["violations"][0]["description"]
    # الواجهة القديمة — القاعدة نفسها
    validator = VersionValidator()
    assert validator.validate(dict(ok_entity)) is True
    assert validator.validate(dict(bad_entity)) is False
    assert "version" in validator.last_verdict.reason


def test_missing_input_and_unknown_rule_not_proven_compliance():
    """نقص المدخل أو قاعدة غير معروفة لا ينتج امتثالاً مثبتاً."""
    runtime = _runtime_with_article5()
    # مدخل الكيان غائب كلياً — لا فحص ولا امتثال مثبت
    no_input = runtime.check_compliance("e1", "contract")
    assert no_input["compliant"] is False
    assert no_input["unverified"][0]["rule_id"] == \
        CONSTITUTION_ARTICLE_5_RULE_ID
    assert "غائب" in no_input["unverified"][0]["reason"]
    # نوع الكيان غائب من المدخل — unverified لا امتثال
    no_type = runtime.check_compliance(
        "e2", "contract", entity={"version": "1.0"})
    assert no_type["compliant"] is False
    assert no_type["unverified"][0]["rule_id"] == \
        CONSTITUTION_ARTICLE_5_RULE_ID
    # قاعدة غير معروفة — حكم unverified لا True أعمى
    verdict = get_shared_evaluator().evaluate("unknown-rule", {"x": 1})
    assert verdict.verdict == "unverified"
    assert verdict.compliant_proven is False
    # الواجهة القديمة بلا نوع منصوص — False مع سبب عدم التحقق
    validator = VersionValidator()
    assert validator.validate({"version": "1.0"}) is False
    assert validator.last_verdict.verdict == "unverified"
    assert "نوع الكيان غائب" in validator.last_verdict.reason


def test_old_interface_reaches_shared_evaluator():
    """تتبع الاستدعاء: الواجهة القديمة تصل إلى المقيم المعتمد فعلاً."""
    evaluator = get_shared_evaluator()
    evaluator.evaluation_log.clear()
    validator = VersionValidator()
    entity = {"type": "Schemas", "version": "2.0"}
    assert validator.validate(entity) is True
    # الاستدعاء مسجل في المقيم المشترك — الواجهة القديمة مرّت به فعلاً
    assert (CONSTITUTION_ARTICLE_5_RULE_ID, entity) in evaluator.evaluation_log
    # والمحرك يستخدم المقيم نفسه (هوية واحدة — مسار واحد)
    runtime = GovernanceRuntime()
    assert runtime.evaluator is evaluator


def test_policy_change_changes_both_paths():
    """تغيير السياسة يغيّر حكم المسارين معاً — نجاح اختبار الهوية وحده
    لا يكفي: مواصفة معدلة على المقيم المشترك تقلب حكم الواجهة القديمة
    والمحرك معاً."""
    evaluator = get_shared_evaluator()
    original_spec = evaluator.get_spec(CONSTITUTION_ARTICLE_5_RULE_ID)
    runtime = _runtime_with_article5()
    validator = VersionValidator()
    entity = {"type": "Contracts", "version": "1.0"}
    # قبل التغيير: امتثال في المسارين
    assert validator.validate(dict(entity)) is True
    assert runtime.check_compliance(
        "e1", "contract", entity=dict(entity))["compliant"] is True
    # تغيير السياسة: الحقل المطلوب صار "name" أيضاً
    changed = dict(original_spec)
    changed["required_fields"] = ["version", "name"]
    evaluator.register_spec(CONSTITUTION_ARTICLE_5_RULE_ID, changed)
    try:
        # الكيان بلا name — مخالفة في المسارين معاً (نفس المصدر الواحد)
        assert validator.validate(dict(entity)) is False
        assert validator.last_verdict.verdict == "violation"
        result = runtime.check_compliance(
            "e1", "contract", entity=dict(entity))
        assert result["compliant"] is False
        assert result["violations"][0]["rule_id"] == \
            CONSTITUTION_ARTICLE_5_RULE_ID
        assert "name" in result["violations"][0]["description"]
        # والكيان المستوفي للحقلين يعود امتثالاً في المسارين
        complete = {"type": "Contracts", "version": "1.0", "name": "x"}
        assert validator.validate(dict(complete)) is True
        assert runtime.check_compliance(
            "e2", "contract", entity=dict(complete))["compliant"] is True
    finally:
        evaluator.register_spec(
            CONSTITUTION_ARTICLE_5_RULE_ID, original_spec)


def test_legacy_rules_keep_literal_path():
    """القواعد بلا مواصفات تبقى على المسار القديم الحرفي (متطلب قائم
    مثبت في test_civilization) — لا يُدّعى تقييمها."""
    runtime = GovernanceRuntime()
    runtime.create_rule(
        name="Security Check",
        domain=GovernanceDomain.SECURITY,
        description="All deployments must pass security check",
        severity="error",
    )
    result = runtime.check_compliance("e1", "deployment")
    assert result["compliant"] is False
    assert result["violations"][0]["description"].startswith(
        "Compliance check:")
    assert result["unverified"] == []


def test_spec_comes_from_constitution_text():
    """المواصفة تُقرأ من النص الدستوري نفسه لا نسخة مستقلة عنه."""
    spec = get_shared_evaluator().get_spec(
        CONSTITUTION_ARTICLE_5_RULE_ID)
    assert spec["applies_to_types"] == VERSIONED_ENTITIES
    assert spec["source"] == "الدستور المادة 5 — VERSIONED_ENTITIES"
    # كيان من نوع منصوص في الدستور يُفحص فعلاً (المادة 5 تنطبق عليه)
    assert "Contracts" in VERSIONED_ENTITIES
