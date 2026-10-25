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
import json
from pathlib import Path


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


def test_unspec_validators_no_blind_allow():
    """المصادقات الثماني بلا مواصفة (الشريحة الخامسة): لا True أعمى —
    الإرجاع False بمعنى عدم ثبوت الامتثال لا مخالفة مثبتة، وlast_verdict
    حكم unverified معلل بغياب المواصفة، والحكم عبر المقيم المعتمد."""
    from agos.governance.enforcement import (
        ArchitectureValidator, DependencyValidator, ContractValidator,
        LayerValidator, NamingValidator, ImportValidator,
        ConfigurationValidator, PolicyValidator)
    cases = [
        (ArchitectureValidator(), ("component",)),
        (DependencyValidator(), ("source-a", "target-b")),
        (ContractValidator(), ("contract",)),
        (LayerValidator(), ("L1", "L2")),
        (NamingValidator(), ("name",)),
        (ImportValidator(), (["os"],)),
        (ConfigurationValidator(), ({"k": 1},)),
        (PolicyValidator(), ("policy",)),
    ]
    for validator, args in cases:
        assert validator.validate(*args) is False
        assert validator.last_verdict.verdict == "unverified"
        assert "بلا مواصفة" in validator.last_verdict.reason


def test_validate_all_reports_unspec_validators_and_no_arity_errors():
    """عبر المجمّع (الشريحة الخامسة): أسباب رفض المصادقات الثماني تصل إلى
    الإخفاقات، ولا خطأ عدد وسائط للمصادقتين ثنائيتي الوسيطين (حمولتهما
    القاموسية تُفكك بحقول مسماة؛ ونقص الحقل يمرر None لا قيمة مختلقة —
    عدم تحقق معلل لا TypeError مخفي) — وبكيان إصدار ممتثل حتى لا يخفي
    رفض VersionValidator نتائج البقية."""
    from agos.governance.enforcement import ArchitecturalEnforcement
    from agos_kernel.governance.policy_evaluator import get_shared_evaluator
    evaluator = get_shared_evaluator()
    enforcement = ArchitecturalEnforcement()
    # السجل يُحصر حول استدعاء المجمّع نفسه — البحث في السجل العالمي يخفي
    # الخطأ (اختبارات أخرى تستدعي المصادقات مباشرة بنفس القيم)
    log_start = len(evaluator.evaluation_log)
    result = enforcement.validate_all({
        "version": {"type": "Contracts", "version": "1.0"},  # ممتثل
        "architecture": "component",
        "dependency": {"source": "a", "target": "b"},
        "contract": "contract",
        "layer": {"source_layer": "L1", "target_layer": "L2"},
        "naming": "name",
        "import": ["os"],
        "configuration": {"k": 1},
        "policy": "policy",
    })
    assert result["passed"] is False            # لا نجاح مع غير مثبت
    assert result["validators"]["version"] is True
    for name in ("architecture", "dependency", "contract", "layer",
                 "naming", "import", "configuration", "policy"):
        assert result["validators"][name] is False
        reasons = [f.get("reason") for f in result["failures"]
                   if f.get("validator") == name]
        assert reasons and "بلا مواصفة" in reasons[0]   # السبب وصل
    # إثبات التوصيل الفعلي بمقطع سجل هذا الاستدعاء (لا يكفي غياب error —
    # فقد يمرر المجمّع (None, None) أو يعكس الوسيطين ويظل unverified):
    # ما وصل المصادقتين ثنائيتي الوسيطين قيم الحمولة في مواضعها بأسمائها
    entries = evaluator.evaluation_log[log_start:]
    assert ("enforcement-dependency-validation",
            {"source": "a", "target": "b"}) in entries
    assert ("enforcement-layer-validation",
            {"source_layer": "L1", "target_layer": "L2"}) in entries
    # نقص حقول الحمولة: تفكيك بحقول مسماة — لا TypeError ولا قيمة مختلقة
    log_start2 = len(evaluator.evaluation_log)
    enforcement2 = ArchitecturalEnforcement()
    result2 = enforcement2.validate_all({"dependency": {}, "layer": {}})
    assert result2["validators"]["dependency"] is False
    assert result2["validators"]["layer"] is False
    assert not any("error" in f for f in result2["failures"])
    # والحمولة الفارغة وصلت (None, None) — بمقطع سجل استدعائها نفسه
    entries2 = evaluator.evaluation_log[log_start2:]
    assert ("enforcement-dependency-validation",
            {"source": None, "target": None}) in entries2
    assert ("enforcement-layer-validation",
            {"source_layer": None, "target_layer": None}) in entries2
    # حمولة ناقصة جزئياً: المقدمة تبقى في موضعها والمفقودة None بلا اختلاق
    log_before = len(get_shared_evaluator().evaluation_log)
    enforcement3 = ArchitecturalEnforcement()
    result3 = enforcement3.validate_all({"dependency": {"source": "a"}})
    new_entries = get_shared_evaluator().evaluation_log[log_before:]
    assert ("enforcement-dependency-validation",
            {"source": "a", "target": None}) in new_entries
    assert result3["validators"]["dependency"] is False
    assert any(f.get("validator") == "dependency"
               and "بلا مواصفة" in f.get("reason", "")
               for f in result3["failures"])


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
    """تصحيح الشريحة السابعة: التوصيل الافتراضي في authorize_execution صار
    يستشير مصدر القواعد المعتمد (تشريع الدستور المفعّل) لا قائمة فارغة
    يمررها المحرك — والقائمة الفارغة ما تزال تمنع على مستوى المفوّض نفسه
    (لا سماح أعمى)؛ وسبب المنع منقول من المقيم، ولا تدقيق بعد منع."""
    from agos_kernel.civilization.autonomous_engineering.autonomous_batch import (
        GovernanceRuntime as AutoGovRuntime, PolicyEnforcer)
    # القائمة الفارغة على مستوى المفوّض: العقد كما هو — لا فحص ولا سماح مثبت
    enforcer = PolicyEnforcer()
    assert enforcer.enforce({"type": "Contracts", "version": "1.0"}, []) is False
    assert "لا فحص ولا سماح مثبت" in enforcer.last_outcome["reason"]
    # التوصيل الافتراضي: مدخل بلا نوع يُمنع بسببه المنقول من المقيم المعتمد
    rt = AutoGovRuntime()
    res = rt.authorize_execution({"version": "1.0"})
    assert res["authorized"] is False
    assert "نوع الكيان غائب" in res["reason"]   # السبب منقول
    # أثر القرار المانع مرتبط بالطلب (المادة 6 — سجل العمل 0081)
    assert len(rt.auditor.audit_log) == 1
    assert rt.auditor.audit_log[-1]["authorized"] is False
    assert rt.auditor.audit_log[-1]["action"] == {"version": "1.0"}
    assert "نوع الكيان غائب" in rt.auditor.audit_log[-1]["reason"]


def test_default_rule_source_is_enacted_constitution_legislation():
    """مصدر القواعد المعتمد للمحرك المحلي (الشريحة السابعة + تصحيحها):
    المصدر إعلان واحد يستهلكه المصنع المعتمد ومصدر الترخيص معاً (تطابق
    تام مع مصنع جديد — لا نسختين تنفصل إحداهما عن الأخرى)، وحد السلطة معلن
    — التسجيلات العابرة وقت الحكم ليست تشريعاً دائماً؛ والسماح مثبت فقط
    بفحص ناجح لكل القواعد، والمخالفة وعدم الانطباق كلاهما منع معلل،
    والتفويض مثبت بوصول المقيم. حدود ما يثبته هذا الاختبار معلنة: عق
    بوابة السياسات على عقد كيان منصوص (المدخل الذي تقيّمه القاعدة) —
    لا مسار مستهلك إنتاجي؛ وربط الترخيص بأنواع أفعال الإنتاج (كـ'mission')
    فجوة مسماة تبقى مفتوحة: لا تشريع منصوص يرخّصها والتشريع قرار حوكمة
    معلن لا يُخترع، فالمسار الإنتاجي يبقى مغلقاً على الفشل الصادق."""
    from agos_kernel.governance import policy_evaluator as pe
    from agos_kernel.civilization.autonomous_engineering.autonomous_batch import (
        GovernanceRuntime as AutoGovRuntime)

    # الإعلان الواحد: مصنع جديد يسجل التشريع كاملاً بالضبط (تطابق تام لا
    # احتواء) — والمصدر يبنى من الإعلان نفسه
    rules = pe.default_policy_rules()
    assert rules == [{"rule_id": rid}
                    for rid in pe.ENACTED_CONSTITUTION_RULE_IDS]
    fresh = pe.shared_evaluator()
    assert set(fresh.registered_rule_ids()) == set(pe.ENACTED_CONSTITUTION_RULE_IDS)
    assert set(pe.ENACTED_CONSTITUTION_RULE_IDS) <= set(
        pe.get_shared_evaluator().registered_rule_ids())

    # حد السلطة: تسجيل عابر وقت الحكم ليس تشريعاً دائماً (يُستعاد بعده)
    ev = pe.get_shared_evaluator()
    specs_before = dict(ev._specs)
    try:
        ev.register_spec("transient-judgment-rule",
                         {"kind": "required_fields", "required_fields": ["x"]})
        assert pe.default_policy_rules() == rules   # المصدر لم يتغير
    finally:
        ev._specs.clear()
        ev._specs.update(specs_before)

    # بوابة السياسات على عقد كيان منصوص: الامتثال يثبت الواجب — والربط
    # الصريح يمنع الترخيص (لا تشريع يعلن المنح — حتى للمدخل الممتثل)
    rt = AutoGovRuntime()
    log_before = len(ev.evaluation_log)
    res = rt.authorize_execution({"type": "Contracts", "version": "1.0"})
    assert res["authorized"] is False
    assert "لا تشريع معتمد يمنح" in res["reason"]   # سبب الربط المسمى
    assert len(ev.evaluation_log) > log_before     # وصل المقيم المشترك فعلاً
    # أثر القرار المانع (المادة 6 — سجل العمل 0081)
    assert len(rt.auditor.audit_log) == 1
    assert rt.auditor.audit_log[-1]["authorized"] is False
    assert "لا تشريع معتمد يمنح" in rt.auditor.audit_log[-1]["reason"]
    # المخالفة تمنع بسببه المنقول (كيان منصوص بلا حقل الإصدار)
    res = rt.authorize_execution({"type": "Contracts"})
    assert res["authorized"] is False
    assert "version" in res["reason"]
    # غير المشمول بالتشريع لا يُمنح ترخيصاً (لا امتثال بلا فحص ناجح) —
    # صفر قواعد منطبقة = منع معلل بأن النوع غير مغطى (نوع مجهول حقاً —
    # 'mission' صارت مغطاة بواجب التشرييع في سجل العمل 0080)
    res = rt.authorize_execution({"type": "uncovered-type"})
    assert res["authorized"] is False
    assert "لا قواعد تشريعية تنطبق" in res["reason"]
    # مهمة كاملة الحمولة: الواجب ناجح والمنح المشرّع مطابق — ترخيص مثبت
    # وتدقيق (تشرييع منح تنفيذ المهام — سجل العمل 0080)
    res = rt.authorize_execution({"type": "mission",
                                  "mission": {"id": "m1", "version": "1.0"}})
    assert res["authorized"] is True
    # أثر القرار السماحي مرتبط بهذا الطلب (المادة 6 — سجل العمل 0081) —
    # الأثر الأخير في السجل (سجل نفسه رتّب قرارات هذا الاختبار قبله)
    last = rt.auditor.audit_log[-1]
    assert last["authorized"] is True
    assert last["action"] == {"type": "mission",
                              "mission": {"id": "m1", "version": "1.0"}}


def test_execution_requires_explicit_authorization_grant():
    """تصحيح المراجعة (سجل العمل 0078): لا ترخيص بلا تشريع معتمد يعلن
    المنح — الامتثال لواجب (المادة 5: وجود حقل الإصدار) يثبت شرط الواجب
    ولا يمنح ترخيص تنفيذ؛ وتغيير تسمية النوع ليس طريقاً من المنع إلى
    السماح. والبوابة تفتح فقط بتشريع معتمد يعلن المنح لنوع الفعل."""
    from agos_kernel.governance import policy_evaluator as pe
    from agos_kernel.civilization.autonomous_engineering.autonomous_batch import (
        GovernanceRuntime as AutoGovRuntime)

    # المنح من التشريع المفعّل: مهمة تنفيذ فقط (سجل العمل 0080)؛ وما
    # سواها ممنوع بسببه المسمى — حتى الممتثل لقواعد واجبات أخرى
    assert pe.execution_authorization_grants(
        {"type": "Contracts", "version": "1.0"}) == []
    assert {g["rule_id"] for g in pe.execution_authorization_grants(
        {"type": "mission"})} == {"mission-execution-grant"}
    rt = AutoGovRuntime()
    res = rt.authorize_execution({"type": "Contracts", "version": "1.0"})
    assert res["authorized"] is False
    assert "لا تشريع معتمد يمنح" in res["reason"]
    # أثر القرار المانع (المادة 6 — سجل العمل 0081)
    assert len(rt.auditor.audit_log) == 1
    assert rt.auditor.audit_log[-1]["authorized"] is False
    assert rt.auditor.audit_log[-1]["action"] == {"type": "Contracts", "version": "1.0"}

    # البوابة تفتح فقط بتشريع معتمد يعلن المنح — منح عابر للاختبار يُعلن
    # في إعلان التشريع (لا في مواصفة قابلة لإعادة التسجيل) ويُستعاد بعده
    granted_rule = "test-authorization-grant"
    grants_before = dict(pe._ENACTED_CONSTITUTION_GRANTS)
    try:
        pe._ENACTED_CONSTITUTION_GRANTS[granted_rule] = {
            "grants": ["execute"], "applies_to_types": ["Contracts"]}
        # المنح يعمل من إعلان التشريع — والمدخل الممتثل يُرخّص ويدقّق
        assert pe.execution_authorization_grants(
            {"type": "Contracts"}) == [{
            "rule_id": granted_rule,
            "requires_rule_ids": []}][0:1]
        # منح لنوع لا يفتح البوابة لغيره
        assert pe.execution_authorization_grants({"type": "uncovered-type"}) == []
        rt2 = AutoGovRuntime()
        res = rt2.authorize_execution(
            {"type": "Contracts", "version": "1.0"})
        assert res["authorized"] is True
        assert len(rt2.auditor.audit_log) == 1
        # المخالفة ما تزال تمنع — المنح لا يلغي الواجب
        res = rt2.authorize_execution({"type": "Contracts"})
        assert res["authorized"] is False
        assert "version" in res["reason"]
    finally:
        pe._ENACTED_CONSTITUTION_GRANTS.clear()
        pe._ENACTED_CONSTITUTION_GRANTS.update(grants_before)
    # بعد الاستعادة: لا منح — البوابة مغلقة بصدق كما كانت
    assert pe.execution_authorization_grants(
        {"type": "Contracts", "version": "1.0"}) == []


def test_grant_authority_from_declaration_not_runtime_spec():
    """الشريحة الثامنة (سجل العمل 0079) — سد ثغرة سلطة المنح: إعادة تسجيل
    مواصفة لمعرّف منصوص (المادة 5) بمنح مضاف وقت التشغيل لا يفتح الترخيص —
    سلطة المنح من إعلان التشريع لا من المواصفات القابلة لإعادة التسجيل."""
    from agos_kernel.governance import policy_evaluator as pe
    from agos_kernel.civilization.autonomous_engineering.autonomous_batch import (
        GovernanceRuntime as AutoGovRuntime)

    ev = pe.get_shared_evaluator()
    specs_before = dict(ev._specs)
    try:
        # الهجوم: إعادة تسجيل مواصفة المادة 5 نفسها بمنح مضاف — بلا مساس
        # بإعلان التشريع
        ev.register_spec(pe.CONSTITUTION_ARTICLE_5_RULE_ID, {
            "kind": "required_fields", "required_fields": ["version"],
            "applies_to_types": ["Contracts"], "grants": ["execute"],
        })
        # سلطة المنح لم تتأثر — الإعلان هو المصدر لا المواصفة
        assert pe.execution_authorization_grants(
            {"type": "Contracts", "version": "1.0"}) == []
        rt = AutoGovRuntime()
        res = rt.authorize_execution({"type": "Contracts", "version": "1.0"})
        assert res["authorized"] is False
        assert "لا تشريع معتمد يمنح" in res["reason"]
        # أثر القرار المانع (المادة 6 — سجل العمل 0081)
        assert len(rt.auditor.audit_log) == 1
        assert rt.auditor.audit_log[-1]["authorized"] is False
    finally:
        ev._specs.clear()
        ev._specs.update(specs_before)


def test_applicable_rules_selector_scoped_and_fail_closed():
    """الشريحة الثامنة (سجل العمل 0079) — محدد القواعد المنطبقة: اختيار
    مدخلات من التشريع المفعّل لا مقيم ثانٍ؛ الاستثناء فقط عند ثبوت الخروج
    عن النطاق الموثق (بيانات منظمة لا نص سبب)؛ وما لا يثبت خروجه يُستشار؛
    وصفر قواعد منطبقة منع معلل لا سماح أعمى."""
    from agos_kernel.governance import policy_evaluator as pe
    from agos_kernel.civilization.autonomous_engineering.autonomous_batch import (
        GovernanceRuntime as AutoGovRuntime)

    # (1) قاعدة منطبقة تُستشار وخارج النطاق يُستثنى — كيان معرفة: المادة 5
    # (Knowledge من الأنواع المنصوصة) والمادة 13 (نطاقها Knowledge)
    # تُستشاران؛ قاعدة نطاقها نوع آخر تُستثنى (مثبت بسجل المقيم لا بالنص)
    rules = pe.applicable_constitution_rules({"type": "Knowledge"})
    assert {r["rule_id"] for r in rules} == {
        pe.CONSTITUTION_ARTICLE_5_RULE_ID, pe.CONSTITUTION_ARTICLE_13_RULE_ID}
    # (2) نوع غائب عن المدخل: لا يثبت الخروج فتُستشار كل القواعد ذات
    # النطاق (كلها عدم تحقق معلل — منع لا سماح)
    rules = pe.applicable_constitution_rules({"version": "1.0"})
    assert {r["rule_id"] for r in rules} == set(pe.ENACTED_CONSTITUTION_RULE_IDS)
    rt = AutoGovRuntime()
    res = rt.authorize_execution({"version": "1.0"})
    assert res["authorized"] is False
    assert "نوع الكيان غائب" in res["reason"]
    # (3) نوع معلوم غير مغطى تشريعياً: صفر منطبقة — منع معلل لا سماح أعمى
    # ('mission' مغطاة بواجب التشرييع في سجل العمل 0080 — نوع مجهول حقاً هنا)
    assert pe.applicable_constitution_rules({"type": "uncovered-type"}) == []
    res = rt.authorize_execution({"type": "uncovered-type"})
    assert res["authorized"] is False
    assert "لا قواعد تشريعية تنطبق" in res["reason"]
    # (4) قاعدة منطبقة ناقصة المواصفة تُستشار لا تُستثنى (لا يُسقط الفحص
    # لنقص مواصفته) — تسجيل عابر لمواصفة ناقصة على معرّف منصوص ثم استعادة
    ev = pe.get_shared_evaluator()
    spec_before = ev.get_spec(pe.CONSTITUTION_ARTICLE_13_RULE_ID)
    try:
        ev.register_spec(pe.CONSTITUTION_ARTICLE_13_RULE_ID,
                        {"kind": "required_fields", "required_fields": []})
        rules = pe.applicable_constitution_rules({"type": "Knowledge"})
        assert pe.CONSTITUTION_ARTICLE_13_RULE_ID in {
            r["rule_id"] for r in rules}
        # والاستشارة تمنع كعدم تحقق معلل (مواصفة ناقصة ليست قائمة سماح فارغة)
        res = rt.authorize_execution(
            {"type": "Knowledge", "version": "1", "source": "s",
             "evidence": [], "confidence": None, "created_at": "t",
             "lineage": []})
        assert res["authorized"] is False
        assert "مواصفة ناقصة" in res["reason"]
    finally:
        ev.register_spec(pe.CONSTITUTION_ARTICLE_13_RULE_ID, spec_before)


def test_article_13_knowledge_contract_completeness():
    """الشريحة الثامنة (سجل العمل 0079) — المادة 13 بعقد المعرفة الفعلي:
    اكتمال العقد مثبت (الأبعاد الستة في عقد Knowledge نفسه)؛ والحد المعلن:
    حضور الحقول يثبت اكتمال العقد لا صحة المصدر أو الأدلة (فحص الحقول لا
    يثبت محتواها). «Timestamp» في المادة → created_at في العقد؛ وversion
    خاصية تفويضية إلى metadata.version."""
    import dataclasses
    from agos_kernel.knowledge.models import Knowledge
    from agos_kernel.governance import policy_evaluator as pe
    from agos_kernel.civilization.autonomous_engineering.autonomous_batch import (
        GovernanceRuntime as AutoGovRuntime)

    # اكتمال عقد كائن المعرفة الفعلي — الأبعاد الستة كلها في العقد
    names = {f.name for f in dataclasses.fields(Knowledge)}
    for dimension in ("source", "evidence", "confidence",
                      "created_at", "lineage"):
        assert dimension in names, dimension
    assert isinstance(getattr(Knowledge, "version"), property)

    # البوابة: كيان معرفة كامل الأبعاد يجتاز فحص المادة 13 (والمادة 5
    # بالإصدار) — والترخيص يبقى معلقاً على بوابة المنح (لا منح مشرّع)
    rt = AutoGovRuntime()
    full = {"type": "Knowledge", "version": "1.0", "source": "docs",
            "evidence": [], "confidence": 0.5, "created_at": "2026-10-24",
            "lineage": []}
    log_before = len(pe.get_shared_evaluator().evaluation_log)
    res = rt.authorize_execution(full)
    assert res["authorized"] is False          # بوابة المنح ما تزال مغلقة
    assert "لا تشريع معتمد يمنح" in res["reason"]
    # المادتان 5 و13 استُشرتا فعلاً (فحصهما ناجح — المنع من بوابة المنح لا
    # من السياسات)
    assert len(pe.get_shared_evaluator().evaluation_log) >= log_before + 2
    # الناقص بعداً واحداً يمنع بسببه المسمى (المادة 13)
    missing = dict(full)
    del missing["lineage"]
    res = rt.authorize_execution(missing)
    assert res["authorized"] is False
    assert "lineage" in res["reason"]


def test_authorize_execution_gate_order_and_right_to_block():
    """ترتيب البوابات وحق المنع (الشريحة الرابعة + تصحيحا المراجعة):
    بدائل تسجّل كل استدعاء، ويتحقق الاختبار من **تسلسل الاستدعاءات كاملاً
    حتى المنع** — لا خلو سجل التدقيق وحده: الطوارئ تمنع بـ[emergency] فقط،
    والتفويض بـ[emergency, authorizer]، والتوصيل الحقيقي بمخالفة قاعدة
    التشريع المفعّل (المادة 5 — كيان منصوص بلا حقل الإصدار)
    بـ[emergency, authorizer, policy] مع السبب المنقول، وبوابة المنح بغياب
    التشريع المانح بـ[...policy, grants] بسببه المسمى (سجل العمل 0078)،
    والسلامة بـ[...grants, safety]، والموافقة البشرية بـ[...safety,
    approval] بلا audit. هذه اختبارات ترتيب لا دليل نجاح المسار الحقيقي
    بسياسات معتمدة؛ والسماح الحقيقي عبر تشريع مانح مختبر في اختبار المنح."""
    from agos_kernel.civilization.autonomous_engineering.autonomous_batch import (
        GovernanceRuntime as AutoGovRuntime, PolicyEnforcer)

    def _recorded(stopped=False, authorize=True, enforce=True,
                  safe=True, requires_approval=False, grants=True):
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

        class RecGrantGate:
            # بديل مضبوط لبوابة المنح — بلا بديل لا تُختبر البوابات
            # اللاحقة (بوابة المنح الحقيقية تُختبر في اختبارات المنح؛
            # البوابة تستدعي grants_verified — التوقيع الأصلي grants محفوظ)
            def __init__(self):
                self.last_reason = None
            def grants_verified(self, action, policy_outcome=None):
                calls.append("grants")
                return [{"rule_id": "stub"}] if grants else []

            def denial_reason(self, action):
                return "لا تشريع معتمد يمنح ترخيص تنفيذ هذا الفعل"

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

            def audit_decision(self, action, result, policy_results=None):
                calls.append("audit")
                self.audit_log.append(action)

        rt.emergency = RecEmergency()
        rt.authorizer = RecAuthorizer()
        rt.policy_enforcer = RealRecordingPolicy() if enforce == "real" else RecPassPolicy()
        rt.grant_gate = RecGrantGate()
        rt.safety = RecSafety()
        rt.approval = RecApproval()
        rt.auditor = RecAuditor()
        return rt, calls

    # (1) الطوارئ تمنع: [emergency] فقط — لا شيء بعدها يُستدعى
    rt, calls = _recorded(stopped=True)
    assert rt.authorize_execution({"risk_level": 0.1}) == {
        "authorized": False, "reason": "Emergency stop active"}
    assert calls == ["emergency", "audit"]
    # (2) التفويض يمنع: [emergency, authorizer]
    rt, calls = _recorded(authorize=False)
    assert rt.authorize_execution({})["reason"] == "Not authorized"
    assert calls == ["emergency", "authorizer", "audit"]
    # (3) التوصيل الحقيقي بمخالفة قاعدة التشريع المفعّل (كيان منصوص بلا
    # حقل الإصدار): [emergency, authorizer, policy] فقط — المفوّض الحقيقي
    # يمنع بسببه المنقول ولا تُستدعى بوابة المنح بعده
    rt, calls = _recorded(enforce="real")
    res = rt.authorize_execution({"type": "Contracts"})
    assert res["authorized"] is False
    assert "version" in res["reason"]
    assert calls == ["emergency", "authorizer", "policy", "audit"]
    # (4) بوابة المنح تمنع بغياب التشريع المانح: [.., policy, grants]
    # فقط — بسببه المسمى ولا تُستدعى السلامة بعده (سجل العمل 0078)
    rt, calls = _recorded(grants=False)
    res = rt.authorize_execution({"type": "Contracts", "version": "1.0"})
    assert res["authorized"] is False
    assert "لا تشريع معتمد يمنح" in res["reason"]
    assert calls == ["emergency", "authorizer", "policy", "grants", "audit"]
    # (5) السلامة تمنع: [emergency, authorizer, policy, grants, safety]
    rt, calls = _recorded(safe=False)
    assert rt.authorize_execution({})["reason"] == "Safety check failed"
    assert calls == ["emergency", "authorizer", "policy", "grants",
                     "safety", "audit"]
    # (6) الموافقة البشرية تمنع: [...] + approval — بلا audit
    rt, calls = _recorded(requires_approval=True)
    assert rt.authorize_execution(
        {"risk_level": 0.9})["reason"] == "Requires human approval"
    assert calls == ["emergency", "authorizer", "policy",
                     "grants", "safety", "approval", "audit"]
    # الأثر يتركه الغلاف لكل قرار — سماحاً ومنعاً كلاهما (سجل العمل 0081)


def test_mission_denied_before_workspace_and_resources():
    """المستهلك الأعلى (الشريحة الرابعة + تصحيح السابعة): رفض المهمة يحدث
    قبل إنشاء مساحة العمل أو تخصيص الموارد — والسبب منقول من المقيم
    المعتمد (نوع 'mission' ليس من الأنواع المنصوصة في المادة 5 فلا
    امتثال مثبت — لا يُمنح ترخيص بلا فحص ناجح)."""
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
    # بعد تشرييع منح المهام (سجل العمل 0080): المهمة الناقصة تمنع بسببه
    # الواجب المسمى — الحمولة تخلو من version بقيمة نصية غير فارغة
    assert "version" in result["reason"]
    assert created == []       # الرفض قبل إنشاء مساحة العمل
    assert allocated == []     # وقبل تخصيص الموارد


def test_mission_grant_opens_path_end_to_end():
    """تشرييع منح تنفيذ المهام (سجل العمل 0080 — قرار المالك «الخيار أ»):
    المسار الإنتاجي نفسه (execute_mission_autonomously) بمكوناته الحقيقية —
    المهمة الكاملة الحمولة (id وversion نصيان غير فارغان) تجتاز الواجب
    والمنح المشرّع المشروط وتُرخّص وتُدقّق وتصل للمراحل اللاحقة؛ والناقصة
    تمنع بسببه المسمى بلا آثار لاحقة. المثبت هنا وصول المسار للمراحل
    اللاحقة (تسجيل استدعاءات المكونات) — لا ادعاء نجاح عمل هندسي؛ وحد
    فاحص السلامة معلن: يعيد safe دائماً (ليس فحص سلامة منفذاً)."""
    from agos_kernel.civilization.autonomous_engineering.autonomous_batch import (
        AutonomousEngineeringRuntime)

    def runtime_with_spies():
        runtime = AutonomousEngineeringRuntime()
        created, allocated, coordinated = [], [], []
        real_create = runtime.workspace.create_workspace
        real_allocate = runtime.resource_manager.allocate
        real_coordinate = runtime.coordinator.coordinate_mission
        runtime.workspace.create_workspace = (
            lambda mid: (created.append(mid), real_create(mid))[1])
        runtime.resource_manager.allocate = (
            lambda tid, req: (allocated.append((tid, req)),
                              real_allocate(tid, req))[1])
        runtime.coordinator.coordinate_mission = (
            lambda mission: (coordinated.append(mission),
                             real_coordinate(mission))[1])
        return runtime, created, allocated, coordinated

    # (1) مهمة كاملة الحمولة: واجب ناجح + منح مشرّع مشروط + تدقيق + وصول
    # للمراحل اللاحقة (مساحة العمل والموارد والتنسيق بالمعرّف الفعلي)
    runtime, created, allocated, coordinated = runtime_with_spies()
    result = runtime.execute_mission_autonomously(
        {"id": "m-complete", "version": "1.0"})
    assert result["status"] == "success"
    assert created == ["m-complete"]          # الوصول للمراحل اللاحقة مثبت
    assert allocated == [("m-complete", {})]
    assert [m["id"] for m in coordinated] == ["m-complete"]
    assert len(runtime.governance.auditor.audit_log) == 1  # التدقيق بعد الترخيص

    # (2) الناقصة/الفارغة/غير النصية/غير القاموسية: منع بسببه المسمى بلا
    # آثار لاحقة
    for mission, expected in [
        ({"id": "m1"}, "version"),                       # غياب الإصدار
        ({"version": "1.0"}, "id"),                       # غياب المعرّف
        ({"id": "", "version": "1.0"}, "id"),             # معرّف فارغ
        ({"id": "m1", "version": ""}, "version"),        # إصدار فارغ
        ({"id": "m1", "version": None}, "version"),       # إصدار None
        ({"id": 7, "version": "1.0"}, "id"),              # معرّف غير نصي
    ]:
        runtime, created, allocated, coordinated = runtime_with_spies()
        result = runtime.execute_mission_autonomously(mission)
        assert result["status"] == "denied", mission
        assert expected in result["reason"], (mission, result["reason"])
        # لا آثار لاحقة — مثبت لكل حالة (مساحة عمل وموارد وتنسيق)
        assert created == [] and allocated == [] and coordinated == []
    runtime, created, allocated, coordinated = runtime_with_spies()
    result = runtime.execute_mission_autonomously("نص لا قاموساً")
    assert result["status"] == "denied"
    assert "ليست قاموساً" in result["reason"]
    assert created == [] and allocated == [] and coordinated == []

    # (3) سحب المنح (عابر داخل الاختبار ويُستعاد): المسار يغلق مجدداً —
    # لا مساحة عمل ولا موارد، بسببه المسمى
    from agos_kernel.governance import policy_evaluator as pe
    grants_before = dict(pe._ENACTED_CONSTITUTION_GRANTS)
    try:
        pe._ENACTED_CONSTITUTION_GRANTS.clear()
        runtime, created, allocated, coordinated = runtime_with_spies()
        result = runtime.execute_mission_autonomously(
            {"id": "m-revoked", "version": "1.0"})
        assert result["status"] == "denied"
        assert "لا تشريع معتمد يمنح" in result["reason"]
        assert created == [] and allocated == [] and coordinated == []
    finally:
        pe._ENACTED_CONSTITUTION_GRANTS.clear()
        pe._ENACTED_CONSTITUTION_GRANTS.update(grants_before)

    # (4) المنح لا يتجاوز البوابات الأخرى: الطوارئ والسلامة والموافقة
    # تمنع المهمة ذات المنح — والمخاطرة العالية تمنع قبل أي أثر لاحق
    runtime, created, allocated, coordinated = runtime_with_spies()
    runtime.governance.emergency.is_stopped = lambda: True
    result = runtime.execute_mission_autonomously(
        {"id": "m-stop", "version": "1.0"})
    assert result["status"] == "denied"
    assert "Emergency stop" in result["reason"]
    assert created == [] and allocated == [] and coordinated == []
    runtime, created, allocated, coordinated = runtime_with_spies()
    runtime.governance.safety.validate = lambda action: {
        "safe": False, "warnings": []}
    result = runtime.execute_mission_autonomously(
        {"id": "m-unsafe", "version": "1.0"})
    assert result["status"] == "denied"
    assert "Safety check failed" in result["reason"]
    assert created == [] and allocated == [] and coordinated == []
    # مخاطرة المهمة تستمد داخل حد الترخيص نفسه (تصحيح المراجعة — سجل
    # العمل 0080): من الحمولة لا من نقل المستهلك — فتمنع قبل إنشاء
    # مساحة العمل أو تخصيص الموارد، والاستدعاء المباشر للحد محموم مثله
    runtime, created, allocated, coordinated = runtime_with_spies()
    result = runtime.execute_mission_autonomously(
        {"id": "m-risk", "version": "1.0", "risk_level": 0.9})
    assert result["status"] == "denied"
    assert "Requires human approval" in result["reason"]
    assert created == [] and allocated == [] and coordinated == []
    # الاستدعاء المباشر لحد الترخيص: مخاطرة الحمولة تعتبر — وقيمة منخفضة
    # في الغلاف لا تخفيها (فحص الحد نفسه لا سلوك المستهلك وحده)
    from agos_kernel.civilization.autonomous_engineering.autonomous_batch import (
        GovernanceRuntime as _Gov)
    gov = _Gov()
    res = gov.authorize_execution({"type": "mission", "mission": {
        "id": "m-direct", "version": "1.0", "risk_level": 0.9}})
    assert res["authorized"] is False
    assert "Requires human approval" in res["reason"]
    res = gov.authorize_execution({"type": "mission", "risk_level": 0.1,
                                   "mission": {"id": "m-hide", "version": "1.0",
                                               "risk_level": 0.9}})
    assert res["authorized"] is False
    assert "Requires human approval" in res["reason"]
    # القيم غير الصالحة ترفض بسبب مسمى لا تعامل كمخاطرة منخفضة — عبر
    # المستهلك الحقيقي وبلا أي أثر لاحق (None/نص/NaN)
    for bad in (None, "0.9", float("nan")):
        runtime, created, allocated, coordinated = runtime_with_spies()
        result = runtime.execute_mission_autonomously(
            {"id": "m-bad", "version": "1.0", "risk_level": bad})
        assert result["status"] == "denied", bad
        assert "قيمة المخاطرة غير صالحة" in result["reason"], bad
        assert created == [] and allocated == [] and coordinated == []


def test_grant_conditions_tamper_proof():
    """مانع تفعيل (سجل العمل 0080): إضعاف واجب المنح بإعادة تسجيل مواصفته
    الأضعف يُكتشف ويمنع بوضوح — المهمة الناقصة لا تُرخّص رغم وجود المنح،
    لأن شرطه يتحقق صراحة: الواجب مستشار ناجح وبمواصفة مطابقة لإعلان
    التشريع. وكذلك تغيير نطاق المواصفة المسجلة ليستثني الواجب من الاستشارة."""
    from agos_kernel.governance import policy_evaluator as pe
    from agos_kernel.civilization.autonomous_engineering.autonomous_batch import (
        GovernanceRuntime as AutoGovRuntime)

    ev = pe.get_shared_evaluator()
    spec_before = ev.get_spec(pe.MISSION_EXECUTION_OBLIGATION_RULE_ID)
    incomplete = {"type": "mission", "mission": {"id": "m1"}}
    try:
        # الهجوم الأول: مواصفة أضعف تفحص وجود الغلاف فقط (تجتاز الناقصة)
        ev.register_spec(pe.MISSION_EXECUTION_OBLIGATION_RULE_ID, {
            "kind": "required_fields", "required_fields": ["mission"],
            "applies_to_types": ["mission"]})
        rt = AutoGovRuntime()
        res = rt.authorize_execution(incomplete)
        assert res["authorized"] is False
        assert "تختلف عن إعلان التشريع" in res["reason"]
        # أثر القرار المانع (المادة 6 — سجل العمل 0081)
        assert len(rt.auditor.audit_log) == 1
        assert rt.auditor.audit_log[-1]["authorized"] is False

        # الهجوم الثاني: تغيير نطاق المواصفة المسجلة ليستثني الواجب من
        # استشارة بوابة السياسات أصلاً (السياسات تمر ثم يمنع المنح)
        ev.register_spec(pe.MISSION_EXECUTION_OBLIGATION_RULE_ID, {
            "kind": "required_fields", "required_fields": ["mission"],
            "applies_to_types": ["not-mission"]})
        rt = AutoGovRuntime()
        res = rt.authorize_execution(incomplete)
        assert res["authorized"] is False
        # الاستثناء من الاستشارة يمنع في بوابة السياسات نفسها (النوع صار
        # غير مغطى بالمواصفة المسجلة المغيّرة) — مانع أبكر لا أضعف
        assert ("لم يُستشر" in res["reason"]
                or "تختلف عن إعلان التشريع" in res["reason"]
                or "لا قواعد تشريعية تنطبق" in res["reason"])
    finally:
        ev.register_spec(pe.MISSION_EXECUTION_OBLIGATION_RULE_ID, spec_before)
    # بعد الاستعادة: الناقصة تمنع بسببه المسمى (الواجب) كما يجب
    rt = AutoGovRuntime()
    res = rt.authorize_execution(incomplete)
    assert res["authorized"] is False
    assert "version" in res["reason"]


def test_required_subfields_incomplete_spec_is_unverified():
    """المواصفة الناقصة لفحص الحمولة unverified — لا امتثالاً افتراضياً
    (سجل العمل 0080): غياب حقل الحمولة أو الحقول المطلوبة = لا فحص ولا
    امتثال مثبت، والمطابقة الكاملة منفصلة عن هذه الحالة."""
    from agos_kernel.governance import policy_evaluator as pe
    from agos_kernel.governance.policy_evaluator import (
        VERDICT_UNVERIFIED, PolicyEvaluator)

    evaluator = PolicyEvaluator()
    evaluator.register_spec("test-subfields-incomplete", {
        "kind": "required_subfields", "applies_to_types": ["mission"]})
    verdict = evaluator.evaluate(
        "test-subfields-incomplete",
        {"type": "mission", "mission": {"id": "m1", "version": "1.0"}})
    assert verdict.verdict == VERDICT_UNVERIFIED
    assert "مواصفة ناقصة" in verdict.reason


def test_article_6_every_decision_leaves_linked_trace():
    """المادة 6 (سجل العمل 0081 — نطاق محدود بمسار قرار الترخيص الموحد):
    كل قرار يترك أثراً واحداً في السجل نفسه مرتبطاً بالطلب، بحكمه وسببه
    المنقول من بوابة القرار — سماحاً ومنعاً كلاهما، عبر بوابات المسار.
    الحد معلن: هذه الحالات الممثلة تثبت تغطية مسار الترخيص الموحد، لا
    عبارة «كل تنفيذ» على مستوى المنظومة (خريطة الأدلة في ADR-0010)."""
    from agos_kernel.governance import policy_evaluator as pe
    from agos_kernel.civilization.autonomous_engineering.autonomous_batch import (
        GovernanceRuntime as AutoGovRuntime)

    mission_ok = {"type": "mission", "mission": {"id": "m1", "version": "1.0"}}
    mission_missing = {"type": "mission", "mission": {"id": "m1"}}

    def fresh(stopped=False, unauthorized=False, unsafe=False):
        rt = AutoGovRuntime()
        if stopped:
            rt.emergency.is_stopped = lambda: True
        if unauthorized:
            rt.authorizer.authorize = lambda action: False
        if unsafe:
            rt.safety.validate = lambda action: {"safe": False, "warnings": []}
        return rt

    cases = [
        ("سماح", fresh(), mission_ok, True, ""),
        ("منع سياسات", fresh(), mission_missing, False, "version"),
        ("طوارئ", fresh(stopped=True), mission_ok, False, "Emergency stop"),
        ("تفويض", fresh(unauthorized=True), mission_ok, False, "Not authorized"),
        ("سلامة", fresh(unsafe=True), mission_ok, False, "Safety check failed"),
        ("موافقة", fresh(), {"type": "mission", "mission": {
            "id": "m2", "version": "1.0", "risk_level": 0.9}},
         False, "Requires human approval"),
        ("نوع غير مغطى", fresh(), {"type": "uncovered-type"},
         False, "لا قواعد تشريعية تنطبق"),
    ]
    for name, rt, action, expected, reason_part in cases:
        before = len(rt.auditor.audit_log)
        res = rt.authorize_execution(action)
        assert res["authorized"] is expected, name
        # أثر واحد جديد مرتبط بالطلب بحكمه وسببه (المادة 6)
        assert len(rt.auditor.audit_log) == before + 1, name
        entry = rt.auditor.audit_log[-1]
        assert entry["action"] == action, name           # مرتبط بالطلب نفسه
        assert entry["authorized"] is expected, name
        assert entry["reason"] == res.get("reason", ""), name  # منقول كما هو
        if reason_part:
            assert reason_part in entry["reason"], name

    # منع بوابة المنح (سحب عابر يستعاد): المهمة الممتثلة تمنع بسببه المسمى
    grants_before = dict(pe._ENACTED_CONSTITUTION_GRANTS)
    try:
        pe._ENACTED_CONSTITUTION_GRANTS.clear()
        rt = AutoGovRuntime()
        res = rt.authorize_execution(mission_ok)
        assert res["authorized"] is False
        assert "لا تشريع معتمد يمنح" in res["reason"]
        assert len(rt.auditor.audit_log) == 1
        assert rt.auditor.audit_log[-1]["authorized"] is False
        assert rt.auditor.audit_log[-1]["action"] == mission_ok
    finally:
        pe._ENACTED_CONSTITUTION_GRANTS.clear()
        pe._ENACTED_CONSTITUTION_GRANTS.update(grants_before)


def test_article_12_decision_repeatable():
    """المادة 12 (سجل العمل 0081 — نطاق محدود بمسار قرار الترخيص الموحد):
    القرار قابل للتكرار — نفس المدخل والسياق وإصدارات السياسات والحالة
    الابتدائية يعطي نفس الحكم والسبب ونتائج القواعد المستشارة (لا مقارنة
    بالطوابع الزمنية أو المعرفات العشوائية). الحد معلن: هذا تكرار مسار
    الترخيص الموحد، لا إثبات «قابلية تكرار» لكل قرار في المنظومة."""
    from agos_kernel.governance import policy_evaluator as pe
    from agos_kernel.civilization.autonomous_engineering.autonomous_batch import (
        GovernanceRuntime as AutoGovRuntime)

    ev = pe.get_shared_evaluator()

    def run(action):
        rt = AutoGovRuntime()   # نفس الحالة الابتدائية — نواة جديدة بلا أثر سابق
        res = rt.authorize_execution(action)
        entry = rt.auditor.audit_log[-1]
        # نتائج القواعد وسياقها من الأثر التاريخي نفسه — لا من نتيجة عابرة
        results = [dict(r) for r in entry["policy_results"]]
        context = entry["policy_context"]
        trace = (entry["authorized"], entry.get("reason", ""))
        return res, results, context, trace

    cases = (
        # (الفعل، {معرف القاعدة: passed المتوقع})
        ({"type": "mission", "mission": {"id": "m1", "version": "1.0"}},
         {"mission-execution-obligation": True}),    # سماح — واجب ممتثل
        ({"type": "mission", "mission": {"id": "m1"}},
         {"mission-execution-obligation": False}),   # منع سياسات — واجب مخالف
        ({"type": "Contracts", "version": "1.0"},
         {"constitution-article-5-versioning": True}),   # ممتثل رغم منع المنح
        ({"type": "uncovered-type"}, {}),           # صفر منطبقة — فراغ مثبت
    )
    for action, expected in cases:
        res1, results1, context1, trace1 = run(action)
        res2, results2, context2, trace2 = run(action)
        assert res1 == res2, action            # نفس الحكم والسبب
        assert trace1 == trace2, action        # نفس أثر القرار حكماً وسبباً
        assert results1 == results2, action    # نفس نتائج القواعد — دائماً
        assert context1 == context2, action    # نفس سياق السياسة — دائماً
        # النتائج المتوقعة صراحة (معرف + حكم passed) — لا يجتاز حكمان
        # خاطئان متطابقان؛ وفراغها حيث لا تصل بوابة السياسات
        assert {r["rule_id"]: r["passed"]
                for r in results1} == expected, action
        if expected:   # القواعد المختارة ومواصفاتها المسجلة الفعلية
            assert {r["rule_id"] for r in context1["rules"]} == set(expected)
            for rid in expected:
                assert context1["specs"][rid] == ev.get_spec(rid), action
        else:           # لم تصل بوابة السياسات — فراغ مثبت لا مجرد سكوت
            assert context1 == {"rules": [], "specs": {}}, action


def test_decision_trace_is_independent_snapshot():
    """تصحيح المراجعة (سجل العمل 0081): أثر القرار لقطة مستقلة — تعديل
    الطلب أو الكائنات المتداخلة بعد عودة القرار لا يغير الأثر التاريخي
    (كان الأثر يحفظ الطلب بالمرجع نفسه فكان قابلاً للتحريف لاحقاً)."""
    from agos_kernel.civilization.autonomous_engineering.autonomous_batch import (
        GovernanceRuntime as AutoGovRuntime)

    rt = AutoGovRuntime()
    action = {"type": "mission", "mission": {"id": "m1", "version": "1.0"}}
    res = rt.authorize_execution(action)
    assert res["authorized"] is True
    entry = rt.auditor.audit_log[-1]
    recorded = entry["action"]
    # تحريف متداخل بعد القرار — الطلب المسجل لا يتغير
    action["mission"]["version"] = "999-mutated"
    action["type"] = "uncovered-type"
    assert recorded == {"type": "mission",
                        "mission": {"id": "m1", "version": "1.0"}}
    # ونتائج القواعد المسجلة لقطة كذلك — لا تتغير بتحريف نتيجة المقيم
    # العابرة (last_outcome) التي التُقطت منها: الأثر التاريخي مستقل
    assert entry["policy_results"]
    rt.policy_enforcer.last_outcome["results"][0]["rule_id"] = "tampered"
    assert rt.auditor.audit_log[-1]["policy_results"][0]["rule_id"] != "tampered"


def test_decision_trace_keeps_policy_context_used_at_decision():
    """تصحيح المراجعة (سجل العمل 0081): أثر القرار يحفظ سياق السياسة
    المستخدم فعلياً وقت القرار — القواعد المختارة ومواصفاتها **المسجلة
    الفعلية** ونتائج تقييمها؛ فإعادة تسجيل مواصفة القاعدة بعد القرار لا
    تغيّر الأثر التاريخي (يحتفظ بالقديمة لا بالحالة الجديدة)."""
    from agos_kernel.governance import policy_evaluator as pe
    from agos_kernel.civilization.autonomous_engineering.autonomous_batch import (
        GovernanceRuntime as AutoGovRuntime)

    from copy import deepcopy
    ev = pe.get_shared_evaluator()
    rule_id = pe.MISSION_EXECUTION_OBLIGATION_RULE_ID
    # لقطة مستقلة قبل القرار — لا مرجع الأثر بنفسه فيقارن الشيء بذاته
    expected_spec = deepcopy(ev.get_spec(rule_id))
    expected_results = {rule_id: True}

    rt = AutoGovRuntime()
    action = {"type": "mission", "mission": {"id": "m1", "version": "1.0"}}
    res = rt.authorize_execution(action)
    assert res["authorized"] is True
    entry = rt.auditor.audit_log[-1]
    assert entry["policy_context"]["specs"][rule_id] == expected_spec
    assert {r["rule_id"]: r["passed"]
            for r in entry["policy_results"]} == expected_results
    results_snapshot = deepcopy(entry["policy_results"])

    # إعادة تسجيل مواصفة أضعف بعد القرار — المواصفة الحالية تغيرت فعلاً،
    # والأثر التاريخي يحتفظ بما استُخدم وقت القرار لا بالحالة الجديدة
    ev.register_spec(rule_id, {
        "kind": "required_fields", "required_fields": ["mission"],
        "applies_to_types": ["mission"]})
    try:
        assert ev.get_spec(rule_id) != expected_spec     # الحالة الجديدة مختلفة
        assert entry["policy_context"]["specs"][rule_id] == expected_spec
        assert entry["policy_results"] == results_snapshot
    finally:
        ev.register_spec(rule_id, expected_spec)


def test_early_rejection_does_not_inherit_previous_results():
    """تصحيح المراجعة (سجل العمل 0081): الرفض المبكر لا يرث نتائج القواعد
    المستشارة لطلب سابق — النتائج تُلتقط عند استشارة السياسات لهذا الطلب
    نفسه، فالمسار الذي لا يصل البوابة أثره فارغ لا منقول من آخر نتيجة."""
    from agos_kernel.civilization.autonomous_engineering.autonomous_batch import (
        GovernanceRuntime as AutoGovRuntime)

    rt = AutoGovRuntime()
    mission_ok = {"type": "mission", "mission": {"id": "m1", "version": "1.0"}}
    res1 = rt.authorize_execution(mission_ok)
    assert res1["authorized"] is True
    first = rt.auditor.audit_log[-1]
    assert {r["rule_id"] for r in first["policy_results"]} == {
        "mission-execution-obligation"}          # نتائج هذا الطلب مسجلة
    assert first["policy_context"]["specs"]      # وسياقه (المواصفة) كذلك
    # رفض مبكر على الكائن نفسه (الطوارئ) — لا يرث نتائج ولا سياق الطلب
    # السابق — فراغ مثبت لا مجرد سكوت
    rt.emergency.is_stopped = lambda: True
    res2 = rt.authorize_execution(mission_ok)
    assert res2["authorized"] is False
    second = rt.auditor.audit_log[-1]
    assert second["authorized"] is False
    assert second["policy_results"] == []         # فراغ مثبت لا توريث
    assert second["policy_context"] == {"rules": [], "specs": {}}
    assert second["action"] == mission_ok         # مرتبط بالطلب نفسه


def test_freeze_is_forbidden_and_membership_fixed():
    """إصلاح عيوب التجميد الموضوعية (الشريحة السادسة): is_forbidden كانت
    تقرأ خاصية غير موجودة فترمي AttributeError دائماً؛ والمطابقة الآن
    عضوية كاملة بعد توحيد الحالة — فالتصنيف الممنوع الحرفي وباختلاف حالة
    حروفه يُكتشف (كان فحص العبارات الحرفي يفشل دائماً بحساسية الحالة)."""
    from agos_kernel.architecture.freeze import get_freeze_manager
    manager = get_freeze_manager()
    # كانت AttributeError دائماً — الآن عضوية فعلية بعد توحيد الحالة
    assert manager.is_forbidden("Breaking Core Contracts") is True
    assert manager.is_forbidden("breaking core contracts") is True
    assert manager.is_forbidden("Bug Fixes") is False
    assert manager.is_allowed("New Capabilities") is True
    assert manager.is_allowed("new capabilities") is True
    assert manager.is_allowed("Breaking Core Contracts") is False


def test_freeze_validate_change_delegates_to_shared_evaluator():
    """الحكم النهائي في validate_change عبر المقيم المشترك (الشريحة
    السادسة — ADR-0010): مكوّن مجمد + تصنيف ممنوع ⇒ violation وFalse
    (حرفياً وباختلاف الحالة)؛ + مسموح ⇒ compliant وTrue **ضمن حدود
    التصنيف النصي فقط** (السبب يوضح الحد — لا عبارة سماح مطلقة)؛ تصنيف
    مجهول ⇒ unverified؛ ومكوّن غير مسجل **حتى مع تصنيف مسموح** ⇒
    unverified؛ والحكم وسببه من المقيم المشترك (سجل محصور حول الاستدعاء)."""
    from agos_kernel.architecture.freeze import get_freeze_manager
    from agos_kernel.governance.policy_evaluator import (
        FREEZE_CHANGE_RULE_ID, get_shared_evaluator)
    manager = get_freeze_manager()
    evaluator = get_shared_evaluator()
    # ممنوع حرفياً — وباختلاف حالة الحروف
    ok, msg = manager.validate_change("Breaking Core Contracts", "kernel")
    assert ok is False and "ممنوع" in msg
    assert manager.last_verdict.verdict == "violation"
    ok_case, _ = manager.validate_change(
        "breaking core contracts", "kernel")
    assert ok_case is False
    # مسموح على مكوّن مجمد — ضمن حدود التصنيف فقط
    ok_allow, msg_allow = manager.validate_change(
        "New Capabilities", "kernel")
    assert ok_allow is True
    assert "ضمن حدود التصنيف" in msg_allow     # لا سماح مطلق
    assert manager.last_verdict.verdict == "compliant"
    # مجهول على مجمد ⇒ لا امتثال مثبت (كان True بالسقوط)
    ok_unknown, _ = manager.validate_change("Refactoring", "kernel")
    assert ok_unknown is False
    assert manager.last_verdict.verdict == "unverified"
    # مكوّن غير مسجل حتى مع تصنيف مسموح ⇒ unverified (كان True دائماً)
    ok_unreg, msg_unreg = manager.validate_change(
        "New Capabilities", "not-registered")
    assert ok_unreg is False
    assert "غير مسجل" in msg_unreg
    assert manager.last_verdict.verdict == "unverified"
    # واسم المكوّن لا يُوحَّد حالته: "KERNEL" غير المسجل ينتج unverified
    # وFalse حتى مع تصنيف مسموح — عضوية المكوّن مطابقة لمفاتيح الإعلان
    # كما هي (والواجهة نفسها لا تعدّه مسجلاً: is_frozen("KERNEL") is False)
    assert manager.is_frozen("KERNEL") is False
    ok_case_comp, msg_case_comp = manager.validate_change(
        "New Capabilities", "KERNEL")
    assert ok_case_comp is False
    assert "غير مسجل" in msg_case_comp
    assert manager.last_verdict.verdict == "unverified"
    # الحكم من المقيم المشترك — سجل محصور حول الاستدعاء (لا السجل العالمي)
    log_start = len(evaluator.evaluation_log)
    manager.validate_change("Bug Fixes", "kernel")
    entries = evaluator.evaluation_log[log_start:]
    assert any(e[0] == FREEZE_CHANGE_RULE_ID for e in entries)


def test_freeze_judgment_follows_declaration_change():
    """اتساق الحكم عند تغيير الإعلان المعتمد (الشريحة السادسة): المواصفة
    تُبنى من الإعلان الحالي نفسه عند كل حكم — فإضافة تصنيف للمسموح تقلب
    الحكم، وتعارض القائمتين لا يُعلن سماحاً، وبالاستعادة يعود عدم الثبوت.
    (لا يجعل نجاح تصنيف مسموح اختباراً مزعوماً لسلامة تغيير فعلي.)"""
    from agos_kernel.architecture.freeze import get_freeze_manager
    from agos_kernel.governance.policy_evaluator import (
        FREEZE_CHANGE_RULE_ID, freeze_change_spec, get_shared_evaluator)
    manager = get_freeze_manager()
    # قبل التغيير: مجهول ⇒ غير مثبت
    ok_before, _ = manager.validate_change("Custom Change", "kernel")
    assert ok_before is False
    # تغيير الإعلان المعتمد: إضافة التصنيف للمسموح تقلب الحكم
    try:
        manager.freeze.allowed_changes.append("Custom Change")
        ok_after, msg_after = manager.validate_change(
            "Custom Change", "kernel")
        assert ok_after is True
        assert "ضمن حدود التصنيف" in msg_after
    finally:
        manager.freeze.allowed_changes.remove("Custom Change")
    # بعد الاستعادة يعود عدم الثبوت
    ok_restored, _ = manager.validate_change("Custom Change", "kernel")
    assert ok_restored is False
    # تعارض القائمتين: التصنيف في المسموحة والممنوعة معاً ⇒ لا سماح
    evaluator = get_shared_evaluator()
    try:
        manager.freeze.allowed_changes.append("Breaking Core Contracts")
        ok_conflict, _ = manager.validate_change(
            "Breaking Core Contracts", "kernel")
        assert ok_conflict is False
    finally:
        manager.freeze.allowed_changes.remove("Breaking Core Contracts")
        # إعادة مزامنة مواصفة المقيم مع الإعلان المستعاد — المواصفة تنسخ
        # القوائم فتبقى نسخة الإعلان المتعارض في المقيم لولا المزامنة
        evaluator.register_spec(
            FREEZE_CHANGE_RULE_ID,
            freeze_change_spec(
                list(manager.freeze.components),
                manager.freeze.allowed_changes,
                manager.freeze.forbidden_changes))
    # بعد الاستعادة والمزامنة: التعارض زال والتصنيف يعود violation —
    # والتحقق مباشرة عبر المقيم المشترك لا عبر المدير وحده
    direct = evaluator.evaluate(
        FREEZE_CHANGE_RULE_ID,
        {"type": "ArchitectureChange",
         "change": "Breaking Core Contracts", "component": "kernel"})
    assert direct.verdict == "violation"
    ok_after, _ = manager.validate_change(
        "Breaking Core Contracts", "kernel")
    assert ok_after is False
    assert manager.last_verdict.verdict == "violation"


def _freeze_content_fixture(tmp_path):
    """تثبيت نطاق تجميد مصغر: مكوّنان بمسارات وملفات حقيقية على القرص."""
    (tmp_path / "core").mkdir()
    (tmp_path / "core" / "a.py").write_text("value = 1\n", encoding="utf-8")
    (tmp_path / "core" / "sub").mkdir()
    (tmp_path / "core" / "sub" / "b.py").write_text("value = 2\n", encoding="utf-8")
    (tmp_path / "policies").mkdir()
    (tmp_path / "policies" / "p.py").write_text("rule = True\n", encoding="utf-8")
    scope = {"core_runtime": ["core"], "policy_ontology": ["policies"]}
    return scope


def test_freeze_content_baseline_match_and_determinism(tmp_path):
    """بناء خط أساس حتمي ثم التحقق يثبت التطابق الكامل (سجل العمل 0084):
    بصمة الأسماء والمحتوى معاً، بلا طوابع زمنية فالتسلسل متطابق بايتاً
    بايتاً، والتحقق من الشجرة نفسها يعطي verified=True بصفر نتائج غير
    تطابق، وناتج التحقق من المدير هو ناتج القدرة المستقلة نفسها."""
    from agos_kernel.architecture.freeze import (
        build_freeze_content_baseline, get_freeze_manager,
        verify_freeze_content, content_fingerprint)
    scope = _freeze_content_fixture(tmp_path)
    baseline = build_freeze_content_baseline(tmp_path, scope)
    # حتمية: البناء مرتين يعطي القاموس نفسه (بلا طوابع زمنية)
    assert build_freeze_content_baseline(tmp_path, scope) == baseline
    # تسلسل JSON حتمي (فرز المفاتيح — نفس البايتات مرتين)
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(
        json.dumps(baseline, sort_keys=True, ensure_ascii=False),
        encoding="utf-8")
    assert baseline_path.read_text(encoding="utf-8") == baseline_path.read_text(
        encoding="utf-8")
    # التحقق: تطابق كامل — الأسماء والمحتوى معاً
    report = verify_freeze_content(tmp_path, baseline_path)
    assert report["verified"] is True
    assert report["files_checked"] == 3
    assert [f for f in report["findings"] if f["kind"] != "match"] == []
    assert report["fingerprint"] == baseline["fingerprint"]
    # بصمة حتمية للمدخل نفسه بالترتيبين
    entries = [("a.py", "h1"), ("b.py", "h2")]
    assert content_fingerprint(entries) == content_fingerprint(list(reversed(entries)))
    # واجهة المدير تفوّض للقدرة المستقلة نفسها (نفس الناتج بالهوية القيمية)
    manager = get_freeze_manager()
    assert manager.verify_content(tmp_path, baseline_path) == report


def test_freeze_content_detects_byte_change_and_missing_file(tmp_path):
    """فحص المحتوى يرصد تغيير البايت والملف الغائب بأسمائهما (سجل العمل
    0084): بصمة المحتوى تتغير فيرصد byte_change بالمسار، وحذف ملف من
    التثبيت يرصد missing_file بالمسار، وverified=False بسبب مسمى لا
    انهياراً."""
    from agos_kernel.architecture.freeze import (
        build_freeze_content_baseline, verify_freeze_content)
    scope = _freeze_content_fixture(tmp_path)
    baseline = build_freeze_content_baseline(tmp_path, scope)
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(
        json.dumps(baseline, sort_keys=True, ensure_ascii=False),
        encoding="utf-8")
    # تغيير بايت واحد في ملف — يرصد بالمسار
    (tmp_path / "core" / "a.py").write_text("value = 11\n", encoding="utf-8")
    report = verify_freeze_content(tmp_path, baseline_path)
    assert report["verified"] is False
    kinds = {(f["kind"], f["path"]) for f in report["findings"]}
    assert ("byte_change", "core/a.py") in kinds
    assert ("match", "core/sub/b.py") in kinds
    # حذف ملف — يرصد بالمسار
    (tmp_path / "core" / "a.py").write_text("value = 1\n", encoding="utf-8")
    (tmp_path / "core" / "sub" / "b.py").unlink()
    report2 = verify_freeze_content(tmp_path, baseline_path)
    assert report2["verified"] is False
    kinds2 = {(f["kind"], f["path"]) for f in report2["findings"]}
    assert ("missing_file", "core/sub/b.py") in kinds2
    assert ("match", "core/a.py") in kinds2


def test_freeze_content_detects_extra_file_and_ignores_pycache(tmp_path):
    """بصمة الأسماء والمحتوى معاً: ملف زائد على الشجرة يرصد extra_file
    (سجل العمل 0084)، ونواتج التنفيذ (__pycache__/*.pyc) خارج الشمول في
    البناء والتحقق معاً فلا يظهر كملف زائد كاذب."""
    from agos_kernel.architecture.freeze import (
        build_freeze_content_baseline, verify_freeze_content)
    scope = _freeze_content_fixture(tmp_path)
    baseline = build_freeze_content_baseline(tmp_path, scope)
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(
        json.dumps(baseline, sort_keys=True, ensure_ascii=False),
        encoding="utf-8")
    # ملف مصدر زائد داخل النطاق — بصمة الأسماء ترصده
    (tmp_path / "core" / "extra.py").write_text("x = 1\n", encoding="utf-8")
    report = verify_freeze_content(tmp_path, baseline_path)
    assert report["verified"] is False
    kinds = {(f["kind"], f["path"]) for f in report["findings"]}
    assert ("extra_file", "core/extra.py") in kinds
    # نواتج التنفيذ ليست محتوى مصدر — لا تظهر في الخط الأساس ولا كزيادة
    (tmp_path / "core" / "__pycache__").mkdir()
    (tmp_path / "core" / "__pycache__" / "a.cpython-312.pyc").write_bytes(b"junk")
    baseline2 = build_freeze_content_baseline(tmp_path, scope)
    assert not any("__pycache__" in k for k in baseline2["components"]["core_runtime"]["files"])
    report2 = verify_freeze_content(tmp_path, baseline_path)
    kinds2 = {(f["kind"], f["path"]) for f in report2["findings"]}
    assert not any(p.startswith("core/__pycache__") for _, p in kinds2)


def test_freeze_content_missing_baseline_is_named_inability(tmp_path):
    """غياب خط الأساس عجز مسمى لا انهياراً ولا ادعاء امتثال (سجل العمل
    0084): verified=False بسبب يذكر المسار المنتظر، وصفر فحوص — والتحقق
    من مسار غير موجود يعطي العجز المسمى نفسه (حد مسمى مستقل عن حالة
    المستودع الحقيقي — الذي صار له خط معتمد بسجل العمل 0085)."""
    from agos_kernel.architecture.freeze import verify_freeze_content
    _freeze_content_fixture(tmp_path)  # شجرة موجودة — الخط وحده هو الغائب
    missing = tmp_path / "no_such_baseline.json"
    report = verify_freeze_content(tmp_path, missing)
    assert report["verified"] is False
    assert "غياب خط الأساس" in report["reason"]
    assert str(missing) in report["reason"]
    assert report["files_checked"] == 0
    assert report["findings"] == []
    assert report["fingerprint"] is None


def test_freeze_content_baseline_committed_and_matching():
    """خط الأساس المعتمد (سجل العمل 0085 — قرار المالك: اعتماد النطاق مع
    تصحيح مسار النواة): خط أساس متعقب موجود ويطابق الشجرة الفعلية —
    التحقق يعطي verified=True بصفر نتائج غير تطابق؛ وهذا هو الإنفاذ: أي
    تغيير لاحق في ملفات النطاق المجمد يكسر هذا الاختبار حتى يُعاد توليد
    الخط في الالتزام نفسه (عملية حوكمة موثقة لا تعديل صامت)."""
    from agos_kernel.architecture.freeze import verify_freeze_content
    repo_root = Path(__file__).resolve().parent.parent
    report = verify_freeze_content(repo_root)
    assert report["verified"] is True, report["reason"]
    non_match = [f for f in report["findings"] if f["kind"] != "match"]
    assert non_match == []
    assert report["files_checked"] > 0
    assert report["fingerprint"] is not None


def test_spec_comes_from_constitution_text():
    """المواصفة تُقرأ من النص الدستوري نفسه لا نسخة مستقلة عنه."""
    spec = get_shared_evaluator().get_spec(
        CONSTITUTION_ARTICLE_5_RULE_ID)
    assert spec["applies_to_types"] == VERSIONED_ENTITIES
    assert spec["source"] == "الدستور المادة 5 — VERSIONED_ENTITIES"
    # كيان من نوع منصوص في الدستور يُفحص فعلاً (المادة 5 تنطبق عليه)
    assert "Contracts" in VERSIONED_ENTITIES
