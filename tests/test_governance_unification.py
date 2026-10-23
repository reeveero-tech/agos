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
    """القواعد بلا مواصفات: حكم unverified معلل (منقّح بتصحيح المراجعة على
    الشريحة الأولى — ADR-0010 §القرار 2): لا مخالفة بلا فحص ولا امتثال بلا
    فحص؛ توقع test_civilization القديم عُدّل بلا حذف اسمه."""
    runtime = GovernanceRuntime()
    runtime.create_rule(
        name="Security Check",
        domain=GovernanceDomain.SECURITY,
        description="All deployments must pass security check",
        severity="error",
    )
    # قاعدة بلا مواصفة وبشدة error — لا تُحتسب مخالفة بلا فحص
    result = runtime.check_compliance("e1", "deployment")
    assert result["compliant"] is False
    assert result["violations"] == []
    assert len(result["unverified"]) == 1
    assert result["unverified"][0]["rule_name"] == "Security Check"
    assert "بلا مواصفة" in result["unverified"][0]["reason"]
    # وبشدة warning كذلك — لا امتثال معلناً بلا فحص
    runtime2 = GovernanceRuntime()
    runtime2.create_rule(
        name="Advisory Check",
        domain=GovernanceDomain.SECURITY,
        description="Advisory only",
        severity="warning",
    )
    result2 = runtime2.check_compliance("e2", "deployment")
    assert result2["compliant"] is False
    assert result2["violations"] == []
    assert len(result2["unverified"]) == 1


def test_no_rules_in_scope_not_proven_compliance():
    """لا حكم بلا قواعد مفحوصة (تصحيح المراجعة على الشريحة الأولى): محرك
    بلا قواعد، أو تصفية نطاق لا تجد قاعدة نشطة — عدم إجراء أي فحص ليس
    امتثالاً مثبتاً؛ unverified معلل ولا تُختلق مخالفة."""
    runtime = GovernanceRuntime()
    result = runtime.check_compliance(
        "e1", "contract",
        entity={"type": "Contracts", "version": "1.0"},
    )
    assert result["compliant"] is False
    assert result["violations"] == []
    assert result["unverified"]
    assert "لا توجد قاعدة نشطة ضمن نطاق الفحص" in result["unverified"][0]["reason"]
    # حالة توجد فيها قواعد لكن لا تبقى نشطة بعد تصفية domain
    runtime2 = _runtime_with_article5()
    filtered = runtime2.check_compliance(
        "e1", "contract",
        domain=GovernanceDomain.SECURITY,   # القاعدة في POLICIES لا SECURITY
        entity={"type": "Contracts", "version": "1.0"},
    )
    assert filtered["compliant"] is False
    assert filtered["violations"] == []
    assert "لا توجد قاعدة نشطة ضمن نطاق الفحص" in \
        filtered["unverified"][0]["reason"]


def test_incomplete_spec_is_unverified():
    """المواصفة الناقصة ليست قائمة سماح فارغة: غياب تعريف الحقول المطلوبة
    حكم unverified بسبب نقص المواصفة — لا امتثال بلا فحص؛ وتغيير مواصفة
    المادة 5 إلى ناقصة يجعل المحرك والواجهة القديمة لا يثبتان الامتثال
    معاً."""
    evaluator = get_shared_evaluator()
    # مباشرة: مواصفة مكسورة بلا تعريف الحقول
    evaluator.register_spec("broken", {"kind": "required_fields"})
    verdict = evaluator.evaluate("broken", {})
    assert verdict.verdict == "unverified"
    assert "مواصفة ناقصة" in verdict.reason
    # وبتغيير مواصفة المادة 5 إلى ناقصة — المساران لا يثبتان امتثالاً معاً
    original_spec = evaluator.get_spec(
        CONSTITUTION_ARTICLE_5_RULE_ID)
    incomplete = {k: v for k, v in original_spec.items()
                 if k != "required_fields"}
    evaluator.register_spec(
        CONSTITUTION_ARTICLE_5_RULE_ID, incomplete)
    try:
        validator = VersionValidator()
        entity = {"type": "Contracts", "version": "1.0"}
        assert validator.validate(dict(entity)) is False
        assert "مواصفة ناقصة" in validator.last_verdict.reason
        runtime = _runtime_with_article5()
        result = runtime.check_compliance(
            "e1", "contract", entity=dict(entity))
        assert result["compliant"] is False
        assert result["violations"] == []
        assert "مواصفة ناقصة" in result["unverified"][0]["reason"]
    finally:
        evaluator.register_spec(
            CONSTITUTION_ARTICLE_5_RULE_ID, original_spec)
    # وبعد الاستعادة يعود الامتثال المثبت في المسارين
    assert validator.validate(dict(entity)) is True


def test_enforcement_pipeline_blocks_on_rejection():
    """بوابة التجميع لا تتجاهل الرفض: رفض مدقق الإصدار (أو تعذر تحققه)
    يمنع نجاح validate_all — والسبب من last_verdict يُنقل إلى الإخفاقات."""
    from agos.governance.enforcement import ArchitecturalEnforcement
    pipeline = ArchitecturalEnforcement()
    pipeline.validators = {"version": VersionValidator()}
    # مخالفة: نوع منصوص بلا إصدار — الرفض يمنع النجاح
    result = pipeline.validate_all({"version": {"type": "Contracts"}})
    assert result["validators"]["version"] is False
    assert result["passed"] is False
    assert any(f.get("validator") == "version"
               for f in result["failures"])
    # وتعذر التحقق (بلا نوع منصوص) يمنع النجاح كذلك
    result2 = pipeline.validate_all({"version": {"version": "1"}})
    assert result2["validators"]["version"] is False
    assert result2["passed"] is False
    # والامتثال المثبت ينجح
    result3 = pipeline.validate_all(
        {"version": {"type": "Contracts", "version": "1.0"}})
    assert result3["validators"]["version"] is True
    assert result3["passed"] is True


def test_enterprise_policy_runtime_delegates_to_shared_evaluator():
    """الشريحة الثانية (enterprise.PolicyRuntime — ADR-0010): السماح والمنع
    وعدم التحقق عبر تفويض المقيم المعتمد — لا True أعمى؛ والنص الحر لا
    يُحوَّل آلياً إلى شرط تنفيذي."""
    from agos.enterprise.governance import PolicyRuntime
    runtime = PolicyRuntime()
    runtime.create_policy(
        "versioned-entities", [CONSTITUTION_ARTICLE_5_RULE_ID])
    # السماح: فحص ناجح لكل القواعد
    assert runtime.evaluate(
        "versioned-entities", {"type": "Contracts", "version": "1.0"}) is True
    assert "سماح مثبت" in runtime.last_reason
    # المنع: مخالفة معللة (بلا إصدار)
    assert runtime.evaluate(
        "versioned-entities", {"type": "Contracts"}) is False
    assert runtime.last_reason.startswith("violation")
    # عدم التحقق: مدخل ناقص (بلا نوع منصوص) — لا يُعلن سماحاً
    assert runtime.evaluate(
        "versioned-entities", {"version": "1.0"}) is False
    assert runtime.last_reason.startswith("unverified")
    # قاعدة نص حر بلا مواصفة — غير قابلة للفحص لا تُحوَّل آلياً
    runtime.create_policy("free-text", ["يجب أن يكون آمناً"])
    assert runtime.evaluate("free-text", {"type": "Contracts"}) is False
    assert "غير قابلة للفحص" in runtime.last_reason
    # سياسة مجهولة — لا فحص ولا سماح
    assert runtime.evaluate("unknown-policy", {}) is False
    assert "سياسة مجهولة" in runtime.last_reason
    # سياسة بلا قواعد — لا فحص ولا سماح
    runtime.create_policy("empty", [])
    assert runtime.evaluate("empty", {"type": "Contracts"}) is False
    assert "بلا قواعد" in runtime.last_reason


def test_enterprise_policy_change_flips_both_paths():
    """تغيير السياسة يقلب حكم الواجهة المؤسسية والمحرك معاً — مصدر واحد."""
    from agos.enterprise.governance import PolicyRuntime
    evaluator = get_shared_evaluator()
    original_spec = evaluator.get_spec(CONSTITUTION_ARTICLE_5_RULE_ID)
    enterprise = PolicyRuntime()
    enterprise.create_policy(
        "versioned-entities", [CONSTITUTION_ARTICLE_5_RULE_ID])
    runtime = _runtime_with_article5()
    entity = {"type": "Contracts", "version": "1.0"}
    # قبل التغيير: سماح في المسارين
    assert enterprise.evaluate("versioned-entities", dict(entity)) is True
    assert runtime.check_compliance(
        "e1", "contract", entity=dict(entity))["compliant"] is True
    # تغيير السياسة: حقل إضافي مطلوب
    changed = dict(original_spec)
    changed["required_fields"] = ["version", "name"]
    evaluator.register_spec(CONSTITUTION_ARTICLE_5_RULE_ID, changed)
    try:
        # الكيان بلا name — منع في المسارين معاً
        assert enterprise.evaluate("versioned-entities", dict(entity)) is False
        assert enterprise.last_reason.startswith("violation")
        assert runtime.check_compliance(
            "e1", "contract", entity=dict(entity))["compliant"] is False
    finally:
        evaluator.register_spec(
            CONSTITUTION_ARTICLE_5_RULE_ID, original_spec)
    # وبعد الاستعادة يعود السماح في المسارين
    assert enterprise.evaluate("versioned-entities", dict(entity)) is True


def test_enterprise_policy_delegation_traced():
    """تتبع التفويض: تقييم الواجهة المؤسسية يمر بالمقيم المشترك فعلاً."""
    from agos.enterprise.governance import PolicyRuntime
    evaluator = get_shared_evaluator()
    evaluator.evaluation_log.clear()
    enterprise = PolicyRuntime()
    enterprise.create_policy(
        "versioned-entities", [CONSTITUTION_ARTICLE_5_RULE_ID])
    entity = {"type": "Schemas", "version": "2.0"}
    assert enterprise.evaluate("versioned-entities", entity) is True
    # الاستدعاء مسجل في المقيم المشترك — الواجهة المؤسسية مرّت به فعلاً
    assert (CONSTITUTION_ARTICLE_5_RULE_ID, entity) in evaluator.evaluation_log


def test_discovered_foundation_policy_delegates():
    """الشريحة الثالثة (المسار المكتشف الأول — foundation/policy.py):
    UniversalPolicyRuntime كان يرجع allowed=True أعمى بلا مستهلكين —
    السماح الآن مثبتاً فقط عبر المقيم المعتمد، والقاعدة القابلة للفحص
    قاموس بمعرّف مسجل (rule_id) لا شكل حر يُحوَّل آلياً."""
    from agos.foundation.policy import UniversalPolicyRuntime
    runtime = UniversalPolicyRuntime()
    rule = {"rule_id": CONSTITUTION_ARTICLE_5_RULE_ID}
    runtime.create_policy("Security", "versioned", "desc", [dict(rule)])
    # السماح: فحص ناجح
    ok = runtime.evaluate(
        "policy_versioned", {"type": "Contracts", "version": "1.0"})
    assert ok["allowed"] is True
    assert "سماح مثبت" in ok["reason"]
    # المنع: مخالفة معللة (بلا إصدار)
    denied = runtime.evaluate("policy_versioned", {"type": "Contracts"})
    assert denied["allowed"] is False
    assert denied["reason"].startswith("violation")
    # عدم التحقق: مدخل ناقص (بلا نوع)
    unv = runtime.evaluate("policy_versioned", {"version": "1.0"})
    assert unv["allowed"] is False
    assert unv["reason"].startswith("unverified")
    # قاعدة شكل حر (بلا rule_id) — غير قابلة للفحص
    runtime.create_policy("Security", "freeform", "desc", [{"name": "آمن"}])
    free = runtime.evaluate("policy_freeform", {"type": "Contracts"})
    assert free["allowed"] is False
    assert "غير قابلة للفحص" in free["reason"]
    # معرّف غير مسجل
    runtime.create_policy("Security", "unregistered", "d",
                          [{"rule_id": "no-such-rule"}])
    assert runtime.evaluate(
        "policy_unregistered", {})["allowed"] is False
    # سياسة بلا قواعد — لا فحص ولا سماح
    runtime.create_policy("Security", "empty", "d", [])
    assert runtime.evaluate("policy_empty", {})["allowed"] is False
    # سياسة غير موجودة — مسار الخطأ محفوظ كما كان
    assert runtime.evaluate("policy_missing", {}) == {
        "error": "Policy not found"}


def test_discovered_civilization_policy_delegates():
    """الشريحة الثالثة (المسار المكتشف الثاني — civilization/policy_runtime):
    PolicyEvaluator كان يعلن passed=True لكل قاعدة أياً كان الفحص — السماح
    الآن مثبتاً فقط عبر المقيم المعتمد (مع حفظ شكل النتيجة: policy_id/
    passed/results) والسبب في reason."""
    from agos_kernel.civilization.policy_runtime import (
        PolicyRuntime as CivPolicyRuntime, PolicyType)
    runtime = CivPolicyRuntime()
    runtime.create_policy(
        "versioned", PolicyType.SECURITY,
        [{"rule_id": CONSTITUTION_ARTICLE_5_RULE_ID}])
    # السماح
    ok = runtime.evaluate_policies(
        PolicyType.SECURITY, {"type": "Contracts", "version": "1.0"})
    assert len(ok) == 1
    assert ok[0]["passed"] is True
    assert "سماح مثبت" in ok[0]["reason"]
    # المنع: مخالفة معللة
    denied = runtime.evaluate_policies(
        PolicyType.SECURITY, {"type": "Contracts"})
    assert denied[0]["passed"] is False
    assert denied[0]["reason"].startswith("violation")
    # عدم التحقق: مدخل ناقص
    unv = runtime.evaluate_policies(
        PolicyType.SECURITY, {"version": "1.0"})
    assert unv[0]["passed"] is False
    assert unv[0]["reason"].startswith("unverified")
    # شكل حر — غير قابل للفحص (النوع يجمع سياستيه: المنع لـversioned
    # وغير القابل للفحص لـfreeform — كلتاهما لا تُعلن سماحاً)
    runtime.create_policy("freeform", PolicyType.SECURITY, [{"name": "آمن"}])
    free = runtime.evaluate_policies(PolicyType.SECURITY, {"type": "Contracts"})
    assert all(r["passed"] is False for r in free)
    assert any("غير قابلة للفحص" in r["reason"] for r in free)


def test_discovered_paths_delegation_traced_and_policy_change():
    """تتبع التفويض وتأثير تغيير السياسة عبر المسارين المكتشفين معاً
    (والمحرك) — مصدر واحد للمواصفة يقلب الجميع."""
    from agos.foundation.policy import UniversalPolicyRuntime
    from agos_kernel.civilization.policy_runtime import (
        PolicyRuntime as CivPolicyRuntime, PolicyType)
    evaluator = get_shared_evaluator()
    original_spec = evaluator.get_spec(CONSTITUTION_ARTICLE_5_RULE_ID)
    # تتبع التفويض: تقييم المسارين يمر بالمقيم المشترك فعلاً
    evaluator.evaluation_log.clear()
    foundation = UniversalPolicyRuntime()
    foundation.create_policy("Security", "v", "d",
                             [{"rule_id": CONSTITUTION_ARTICLE_5_RULE_ID}])
    foundation.evaluate("policy_v", {"type": "Contracts", "version": "1"})
    civ = CivPolicyRuntime()
    civ.create_policy("v", PolicyType.EXECUTION,
                      [{"rule_id": CONSTITUTION_ARTICLE_5_RULE_ID}])
    civ.evaluate_policies(PolicyType.EXECUTION,
                          {"type": "Contracts", "version": "1"})
    assert evaluator.evaluation_log.count(
        (CONSTITUTION_ARTICLE_5_RULE_ID,
         {"type": "Contracts", "version": "1"})) == 2
    # تغيير السياسة يقلب المسارين المكتشفين والمحرك معاً
    entity = {"type": "Contracts", "version": "1.0"}
    assert foundation.evaluate("policy_v", dict(entity))["allowed"] is True
    assert civ.evaluate_policies(
        PolicyType.EXECUTION, dict(entity))[0]["passed"] is True
    changed = dict(original_spec)
    changed["required_fields"] = ["version", "name"]
    evaluator.register_spec(CONSTITUTION_ARTICLE_5_RULE_ID, changed)
    try:
        assert foundation.evaluate(
            "policy_v", dict(entity))["allowed"] is False
        assert civ.evaluate_policies(
            PolicyType.EXECUTION, dict(entity))[0]["passed"] is False
        assert _runtime_with_article5().check_compliance(
            "e1", "contract", entity=dict(entity))["compliant"] is False
    finally:
        evaluator.register_spec(
            CONSTITUTION_ARTICLE_5_RULE_ID, original_spec)
    # وبعد الاستعادة يعود السماح في الثلاثة
    assert foundation.evaluate("policy_v", dict(entity))["allowed"] is True
    assert civ.evaluate_policies(
        PolicyType.EXECUTION, dict(entity))[0]["passed"] is True


def test_civilization_nested_output_contract_preserved():
    """عقد المخرج المتداخل محفوظ (تصحيح المراجعة على الشريحة الثالثة):
    ``rule`` اسم القاعدة كما كان — لا المعرّف؛ و``passed`` منطقي — True
    للامتثال المثبت فقط وFalse للمخالفة وعدم التحقق؛ وrule_id/verdict
    إضافتان لا استبدال. بقاعدة اسمها مختلف عن معرّفها عبر evaluate_policies
    في الحالات الثلاث."""
    from agos_kernel.civilization.policy_runtime import (
        PolicyRuntime as CivPolicyRuntime, PolicyType)
    runtime = CivPolicyRuntime()
    # قاعدة اسمها «قاعدة الإصدار» ومعرّفها المادة 5 — اسمان مختلفان
    runtime.create_policy(
        "named", PolicyType.COMPLIANCE,
        [{"name": "قاعدة الإصدار",
          "rule_id": CONSTITUTION_ARTICLE_5_RULE_ID}])
    # امتثال: passed=True وrule بالاسم لا المعرّف
    ok = runtime.evaluate_policies(
        PolicyType.COMPLIANCE, {"type": "Contracts", "version": "1.0"})
    entry_ok = ok[0]["results"][0]
    assert entry_ok["rule"] == "قاعدة الإصدار"
    assert entry_ok["rule_id"] == CONSTITUTION_ARTICLE_5_RULE_ID
    assert entry_ok["passed"] is True
    assert entry_ok["verdict"] == "compliant"
    assert "امتثال مثبت" in entry_ok["reason"]   # سبب المقيم يصل نتيجتها
    # مخالفة: passed=False والاسم كما هو
    bad = runtime.evaluate_policies(
        PolicyType.COMPLIANCE, {"type": "Contracts"})
    entry_bad = bad[0]["results"][0]
    assert entry_bad["rule"] == "قاعدة الإصدار"
    assert entry_bad["passed"] is False
    assert entry_bad["verdict"] == "violation"
    assert "version" in entry_bad["reason"]      # سبب المخالفة يصل نتيجتها
    assert bad[0]["passed"] is False
    # عدم تحقق: passed=False والاسم كما هو
    unv = runtime.evaluate_policies(
        PolicyType.COMPLIANCE, {"version": "1.0"})
    entry_unv = unv[0]["results"][0]
    assert entry_unv["rule"] == "قاعدة الإصدار"
    assert entry_unv["passed"] is False
    assert entry_unv["verdict"] == "unverified"
    assert "نوع الكيان غائب" in entry_unv["reason"]   # سبب عدم التحقق يصلها
    assert unv[0]["passed"] is False


def test_civilization_results_cover_every_rule_in_order():
    """نتيجة معللة لكل قاموس قاعدة بالترتيب (تصحيح المراجعة على الشريحة
    الثالثة): القواعد غير المتحققة تظهر نتائجها ولا تختفي؛ ولا تُسقط
    نتائج القواعد اللاحقة بسبب أول رفض — وعدم التحقق يشمل غياب المواصفة
    التنفيذية لا نقص مدخل قاعدة معروفة فقط."""
    from agos_kernel.civilization.policy_runtime import (
        PolicyRuntime as CivPolicyRuntime, PolicyType)
    runtime = CivPolicyRuntime()
    # (1) قاعدة مسماة بلا rule_id، وأخرى بمعرّف غير مسجل — تظهر نتيجتاهما
    runtime.create_policy("mixed-uncheckable", PolicyType.EXECUTION, [
        {"name": "قاعدة وصفية"},
        {"name": "الثانية", "rule_id": "unknown-rule"},
    ])
    res = runtime.evaluate_policies(
        PolicyType.EXECUTION, {"type": "Contracts", "version": "1.0"})
    assert res[0]["passed"] is False
    assert len(res[0]["results"]) == 2          # نتيجتان لا اختفاء
    first, second = res[0]["results"]
    assert first["rule"] == "قاعدة وصفية"      # بالاسم كما كان
    assert first["passed"] is False
    assert first["verdict"] == "unverified"
    # سبب كل نتيجة على حدة يصل نتيجتها (لا الحكم الإجمالي وحده)
    assert "rule_id" in first["reason"]         # تشرح غياب المعرّف
    assert second["rule"] == "الثانية"
    assert second["passed"] is False
    assert second["verdict"] == "unverified"
    assert "unknown-rule" in second["reason"]    # تشرح أن المعرّف غير مسجل
    assert "غير قابلة للفحص" in res[0]["reason"]
    # (2) عدة قواعد أولها مخالفة — تبقى نتيجة لكل قاعدة وبالترتيب
    # (نوع مختلف حتى لا تختلط بسياستي الحالة الأولى في النتائج)
    runtime.create_policy("ordered", PolicyType.SECURITY, [
        {"name": "الأولى", "rule_id": CONSTITUTION_ARTICLE_5_RULE_ID},
        {"name": "الثانية", "rule_id": CONSTITUTION_ARTICLE_5_RULE_ID},
    ])
    res2 = runtime.evaluate_policies(
        PolicyType.SECURITY, {"type": "Contracts"})
    assert res2[0]["passed"] is False
    assert len(res2[0]["results"]) == 2
    assert [r["rule"] for r in res2[0]["results"]] == ["الأولى", "الثانية"]
    assert all(r["passed"] is False for r in res2[0]["results"])
    assert res2[0]["results"][0]["verdict"] == "violation"
    assert res2[0]["reason"].startswith("violation")


def test_autonomous_policy_enforcer_delegates_to_shared_evaluator():
    """المفوّض الحقيقي (الشريحة الرابعة — autonomous_batch): حكم تقييم
    السياسات في PolicyEnforcer يمر عبر المقيم المعتمد — امتثال مثبت،
    مخالفة معللة، تعذر تحقق، وقائمة فارغة؛ والسماح المثبت وحده يُعلن."""
    from agos_kernel.civilization.autonomous_engineering.autonomous_batch import (
        PolicyEnforcer)
    from agos_kernel.governance.policy_evaluator import get_shared_evaluator
    enforcer = PolicyEnforcer()
    rules = [{"name": "قاعدة الإصدار",
              "rule_id": CONSTITUTION_ARTICLE_5_RULE_ID}]
    log_before = len(get_shared_evaluator().evaluation_log)
    # امتثال مثبت
    assert enforcer.enforce({"type": "Contracts", "version": "1.0"},
                            rules) is True
    assert enforcer.last_outcome["allowed"] is True
    assert "سماح مثبت" in enforcer.last_outcome["reason"]
    # مخالفة معللة
    assert enforcer.enforce({"type": "Contracts"}, rules) is False
    assert enforcer.last_outcome["allowed"] is False
    assert "version" in enforcer.last_outcome["reason"]
    # تعذر تحقق
    assert enforcer.enforce({"version": "1.0"}, rules) is False
    assert enforcer.last_outcome["allowed"] is False
    assert "نوع الكيان غائب" in enforcer.last_outcome["reason"]
    # قائمة فارغة — لا سماح أعمى
    assert enforcer.enforce({"type": "Contracts"}, []) is False
    assert "لا فحص ولا سماح مثبت" in enforcer.last_outcome["reason"]
    # التقييم وصل المقيم المشترك فعلاً (السجل نما بالأحكام)
    assert len(get_shared_evaluator().evaluation_log) > log_before


def test_authorize_execution_empty_policies_denies_with_reason():
    """التوصيل الحالي (الشريحة الرابعة): authorize_execution يمنع عند
    القائمة الفارغة وينقل سبب غياب القواعد (لا اختزال في Policy
    violation)، ولا يستدعي التدقيق بعد المنع."""
    from agos_kernel.civilization.autonomous_engineering.autonomous_batch import (
        GovernanceRuntime as AutoGovRuntime)
    rt = AutoGovRuntime()
    res = rt.authorize_execution({"type": "Contracts", "version": "1.0"})
    assert res["authorized"] is False
    assert "لا فحص ولا سماح مثبت" in res["reason"]   # السبب منقول
    assert len(rt.auditor.audit_log) == 0            # لا تدقيق بعد منع


def test_authorize_execution_gate_order_and_right_to_block():
    """ترتيب البوابات وحق المنع (الشريحة الرابعة — تصحيح المراجعة): بدائل
    تسجّل كل استدعاء، ويتحقق الاختبار من **تسلسل الاستدعاءات كاملاً حتى
    المنع** — لا خلو سجل التدقيق وحده: الطوارئ تمنع بـ[emergency] فقط،
    والتفويض بـ[emergency, authorizer]، والتوصيل الحقيقي بالقائمة الفارغة
    بـ[emergency, authorizer, policy] مع السبب المنقول، والسلامة
    بـ[...policy, safety]، والموافقة البشرية بـ[...safety, approval] بلا
    audit. هذه اختبارات ترتيب لا دليل نجاح المسار الحقيقي بسياسات معتمدة."""
    from agos_kernel.civilization.autonomous_engineering.autonomous_batch import (
        GovernanceRuntime as AutoGovRuntime, PolicyEnforcer)

    def _recorded(stopped=False, authorize=True, enforce=True,
                  safe=True, requires_approval=False):
        rt = AutoGovRuntime()
        calls = []

        class RecEmergency:
            def is_stopped(self):
                calls.append("emergency")
                return stopped

        class RecAuthorizer:
            def authorize(self, action):
                calls.append("authorizer")
                return authorize

        class RealRecordingPolicy(PolicyEnforcer):
            # المفوّض الحقيقي نفسه مع تسجيل الاستدعاء — التفويض لا يُستبدل
            def enforce(self, action, policies):
                calls.append("policy")
                return super().enforce(action, policies)

        class RecPassPolicy:
            # بديل مضبوط يسمح — لاختبار البوابات اللاحقة في مواضعها
            def __init__(self):
                self.last_outcome = {"allowed": True, "reason": "سماح مثبت"}
            def enforce(self, action, policies):
                calls.append("policy")
                return True

        class RecSafety:
            def validate(self, action):
                calls.append("safety")
                return {"safe": safe, "warnings": []}

        class RecApproval:
            def requires_approval(self, action):
                calls.append("approval")
                return requires_approval

        class RecAuditor:
            def __init__(self):
                self.audit_log = []
            def audit(self, action):
                calls.append("audit")
                self.audit_log.append(action)

        rt.emergency = RecEmergency()
        rt.authorizer = RecAuthorizer()
        rt.policy_enforcer = RealRecordingPolicy() if enforce == "real" else RecPassPolicy()
        rt.safety = RecSafety()
        rt.approval = RecApproval()
        rt.auditor = RecAuditor()
        return rt, calls

    # (1) الطوارئ تمنع: [emergency] فقط — لا شيء بعدها يُستدعى
    rt, calls = _recorded(stopped=True)
    assert rt.authorize_execution({"risk_level": 0.1}) == {
        "authorized": False, "reason": "Emergency stop active"}
    assert calls == ["emergency"]
    # (2) التفويض يمنع: [emergency, authorizer]
    rt, calls = _recorded(authorize=False)
    assert rt.authorize_execution({})["reason"] == "Not authorized"
    assert calls == ["emergency", "authorizer"]
    # (3) التوصيل الحقيقي بالقائمة الفارغة: [emergency, authorizer, policy]
    # فقط — المفوّض الحقيقي يمنع بسببه المنقول ولا تُستدعى السلامة بعده
    rt, calls = _recorded(enforce="real")
    res = rt.authorize_execution({"type": "Contracts", "version": "1.0"})
    assert res["authorized"] is False
    assert "لا فحص ولا سماح مثبت" in res["reason"]
    assert calls == ["emergency", "authorizer", "policy"]
    # (4) السلامة تمنع: [emergency, authorizer, policy, safety]
    rt, calls = _recorded(safe=False)
    assert rt.authorize_execution({})["reason"] == "Safety check failed"
    assert calls == ["emergency", "authorizer", "policy", "safety"]
    # (5) الموافقة البشرية تمنع: [...] + approval — بلا audit
    rt, calls = _recorded(requires_approval=True)
    assert rt.authorize_execution(
        {"risk_level": 0.9})["reason"] == "Requires human approval"
    assert calls == ["emergency", "authorizer", "policy",
                     "safety", "approval"]
    assert "audit" not in calls


def test_mission_denied_before_workspace_and_resources():
    """المستهلك الأعلى (الشريحة الرابعة): رفض المهمة يحدث قبل إنشاء مساحة
    العمل أو تخصيص الموارد — والسبب منقول."""
    from agos_kernel.civilization.autonomous_engineering.autonomous_batch import (
        AutonomousEngineeringRuntime)
    runtime = AutonomousEngineeringRuntime()
    created, allocated = [], []
    runtime.workspace.create_workspace = (
        lambda mid: (created.append(mid), "/tmp/ws")[1])
    runtime.resource_manager.allocate = (
        lambda tid, req: (allocated.append(tid), True)[1])
    result = runtime.execute_mission_autonomously({"id": "m1"})
    assert result["status"] == "denied"
    assert "لا فحص ولا سماح مثبت" in result["reason"]
    assert created == []       # الرفض قبل إنشاء مساحة العمل
    assert allocated == []     # وقبل تخصيص الموارد


def test_spec_comes_from_constitution_text():
    """المواصفة تُقرأ من النص الدستوري نفسه لا نسخة مستقلة عنه."""
    spec = get_shared_evaluator().get_spec(
        CONSTITUTION_ARTICLE_5_RULE_ID)
    assert spec["applies_to_types"] == VERSIONED_ENTITIES
    assert spec["source"] == "الدستور المادة 5 — VERSIONED_ENTITIES"
    # كيان من نوع منصوص في الدستور يُفحص فعلاً (المادة 5 تنطبق عليه)
    assert "Contracts" in VERSIONED_ENTITIES
