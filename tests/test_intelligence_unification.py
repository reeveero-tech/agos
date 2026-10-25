"""R-W1-006 — اختبارات توحيد الذكاء (ADR-0009).

الجزء الأول: **توصيف القائم على HEAD قبل أي تعديل سلوكي** — المحلل والمتحقق
والمخطط والمترجم ونظام الاعتماد بأشكالها الحالية بالضبط (لا حكم، لا تغيير).
"""
import os
import shutil
import sys
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve()
_KERNEL = _HERE.parent.parent / "agos" / "agos-kernel"
if str(_KERNEL) not in sys.path:
    sys.path.insert(0, str(_KERNEL))

from mission import Mission  # noqa: E402
from mission_engine import (  # noqa: E402
    MissionParser, MissionPlanner, MissionValidator)
from approval import ApprovalRuntime, ApprovalSource, ApprovalStatus  # noqa: E402
from agos_kernel.execution import MissionCompiler  # noqa: E402


# ===============================================================
# توصيف المحلل (MissionParser) — الشكل الحالي بالضبط
# ===============================================================
def test_parser_dict_to_mission():
    mission = MissionParser.parse({
        "name": "auth", "description": "بناء مصادقة",
        "capability": "CodeGeneration", "parameters": {"lang": "py"},
    })
    assert isinstance(mission, Mission)
    assert mission.name == "auth"
    assert mission.description == "بناء مصادقة"
    assert mission.capability == "CodeGeneration"
    assert mission.parameters == {"lang": "py"}
    assert mission.id  # معرّف موجود (توليد داخلي)


def test_parser_dict_without_id_gets_fresh_one():
    first = MissionParser.parse({"name": "n", "capability": "C"})
    second = MissionParser.parse({"name": "n", "capability": "C"})
    assert first.id and second.id and first.id != second.id


def test_parser_mission_passthrough_is_identity():
    mission = Mission(name="n", capability="C")
    assert MissionParser.parse(mission) is mission


def test_parser_rejects_other_types():
    try:
        MissionParser.parse("نص حر")
        raised = False
    except ValueError as e:
        raised = "Cannot parse" in str(e)
    assert raised


# ===============================================================
# توصيف المتحقق (MissionValidator) — الرفض قبل أي تنفيذ
# ===============================================================
def test_validator_requires_name_and_capability():
    result = MissionValidator().validate(Mission(name="", capability=""))
    assert result.valid is False
    assert any("name is required" in e for e in result.errors)
    assert any("capability is required" in e for e in result.errors)


def test_validator_accepts_complete_mission():
    result = MissionValidator().validate(
        Mission(name="n", capability="CodeGeneration", parameters={"x": 1}))
    assert result.valid is True
    assert result.errors == []


def test_validator_warnings_kept():
    result = MissionValidator().validate(
        Mission(name="n", capability="code"))  # حرف صغير + بلا معاملات
    assert result.valid is True
    assert any("uppercase" in w for w in result.warnings)
    assert any("No parameters" in w for w in result.warnings)


# ===============================================================
# توصيف المخطط (MissionPlanner) — القالب الحالي بالضبط
# ===============================================================
def test_planner_fixed_six_steps():
    plan = MissionPlanner().plan(Mission(name="n", capability="CodeGeneration"))
    assert plan.steps == [
        "resolve_capability", "resolve_provider", "create_context",
        "execute_skills", "collect_results", "generate_output"]
    assert plan.estimated_duration_ms == 5000      # حرفي في القائم
    assert plan.required_capabilities == ["CodeGeneration"]
    assert plan.required_skills == []


# ===============================================================
# توصيف المترجم (MissionCompiler) — المخرجات الفعلية الحالية
# ===============================================================
def test_compiler_ten_phases_and_thin_outputs():
    compiler = MissionCompiler()
    mission = compiler.compile(
        "بناء نظام مصادقة كامل بجودة إنتاجية",
        context={"team": 3},
        knowledge=["k1"], capabilities=["CodeGeneration"],
    )
    # 10 مراحل مكتملة
    assert len(mission.phases) == 10
    assert all(p.status == "completed" for p in mission.phases)
    # الهدف: صدى للنص (أول 50 حرفاً) — الشكل الحالي
    assert len(mission.goals) == 1
    assert mission.goals[0].description == \
        "Goal: بناء نظام مصادقة كامل بجودة إنتاجية"[:57]
    # قيد واحد حرفي (وقت 3600 لين)
    assert len(mission.constraints) == 1
    assert mission.constraints[0].type == "time"
    assert mission.constraints[0].value == 3600
    # سياسات حرفية
    assert mission.metadata["policies"] == ["default-policy"]
    # المعرفة/القدرات تخزين مرور
    assert mission.metadata["knowledge"] == ["k1"]
    assert mission.metadata["capabilities"] == ["CodeGeneration"]
    # رسم تنفيذ قالب ثابت 4 عقد
    assert mission.execution_graph is not None
    assert len(mission.execution_graph["nodes"]) == 4
    assert len(mission.execution_graph["edges"]) == 3
    # قابلية التنفيذ
    assert mission.metadata["executable"] is True


def test_compiler_intent_confidence_is_literal():
    compiler = MissionCompiler()
    mission = compiler.compile("أي قصد", knowledge=[], capabilities=[])
    # ثقة القصد حرفية 0.8 — لا تفسير قصد حراً في القائم (فجوة مسماة ADR-0009)
    assert mission.intent.confidence == 0.8


# ===============================================================
# توصيف نظام الاعتماد (ApprovalRuntime) — الشكل الحالي بالضبط
# ===============================================================
def test_approval_lifecycle_current_shape():
    rt = ApprovalRuntime()
    req = rt.create_request(
        request_type="test.plan", description="خطة",
        source=ApprovalSource.HUMAN, requester="user")
    assert req.status is ApprovalStatus.PENDING
    assert rt.get_request(req.id) is req

    assert rt.approve(req.id, approver="مدير") is True
    assert req.status is ApprovalStatus.APPROVED
    assert "مدير" in req.approved_by
    assert req.decided_at is not None

    other = rt.create_request("test.plan2", "أخرى")
    assert rt.reject(other.id, rejected_by="مدير", reason="غير مناسب") is True
    assert other.status is ApprovalStatus.REJECTED
    assert other.rejected_by == "مدير"

    skipped = rt.create_request("test.plan3", "ثالثة")
    assert rt.skip(skipped.id, reason="تخطي") is True
    assert skipped.status is ApprovalStatus.SKIPPED

    assert rt.get_request("غير-موجود") is None
    assert rt.approve("غير-موجود", "x") is False


def test_approval_policy_and_analytics_current_shape():
    rt = ApprovalRuntime()
    from approval.runtime import ApprovalRule
    # R-Q-011 (سجل العمل 0042): القاعدة تطابق النوع من
    # ``conditions["request_type"]`` (حرفي أو "*") — كان الكود يقرأ
    # ``rule.request_type`` غير الموجود في ``ApprovalRule`` فيفشل بعالقاعدة
    # واحدة (موثق في سجل العمل 0040 §6) — الآن عقد معلن وسلوك مختبر.
    rt.add_rule(ApprovalRule(id="r1", name="auto",
                             conditions={"request_type": "t.x"},
                             auto_approve=True))
    rt.add_rule(ApprovalRule(id="r2", name="wild",
                             conditions={"request_type": "*"},
                             auto_approve=False))
    # المطابقة الحرفية مع auto_approve → موافقة آلية.
    assert rt.check_policy("t.x", {}) is True
    # النوع غير المطابق لا يوافق آلياً (القاعدة النجمية بلا auto_approve).
    assert rt.check_policy("t.y", {}) is False
    # evidence مقبول في التوقيع ولا يغيّر القرار (حدّ مسمّى في العقد).
    assert rt.check_policy("t.x", {"k": "v"}) is True
    # بلا قواعد → لا موافقة آلية.
    assert ApprovalRuntime().check_policy("t.x", {}) is False

    req = rt.create_request("t.x", "وصف")
    rt.approve(req.id, "a")
    analytics = rt.get_analytics()
    assert analytics["total_requests"] == 1
    assert analytics["approved"] == 1
    # R-Q-011: المعلق = غير المحسوم فعلاً — المقرَّر يبقى في ``requests``
    # (فلا يفقد ``get_request`` أثره) لكنه لا يُعدّ معلقاً بعد قراره.
    assert analytics["pending"] == 0
    assert analytics["approval_rate"] == 1.0
    assert rt.get_request(req.id) is req


def test_approval_pending_counts_only_undecided_requests():
    """R-Q-011: analytics["pending"] يعد غير المحسوم فقط في كل مسارات
    القرار — approve/reject/skip كلها تُخرج الطلب من العد بلا إزالته
    من ``requests`` (فبقاء ``get_request`` مضموناً)."""
    rt = ApprovalRuntime()
    a = rt.create_request("t.a", "أ")
    b = rt.create_request("t.b", "ب")
    c = rt.create_request("t.c", "ج")
    assert rt.get_analytics()["pending"] == 3

    assert rt.approve(a.id, "x") is True
    assert rt.reject(b.id, "y", "سبب") is True
    assert rt.skip(c.id, reason="تخطي") is True

    assert rt.get_analytics()["pending"] == 0
    # الطلبات الثلاثة ما زالت قابلة للاسترجاع بعد قراراتها.
    assert rt.get_request(a.id) is a
    assert rt.get_request(b.id) is b
    assert rt.get_request(c.id) is c
    # وطلبات جديدة تُعدّ معلقة مرة أخرى.
    d = rt.create_request("t.d", "د")
    assert rt.get_analytics()["pending"] == 1
    assert rt.get_request(d.id) is d


def test_approval_request_is_mutable_today():
    """توصيف: طلب الاعتماد القائم قابل للتعديل — الاعتماد على حالة مرفوضة
    يمكن قلبها إلى APPROVED بتغيير الحالة مباشرة (سلوك قائم يوثَّق؛ حارس
    الواجهة الجديد يحمي دونه — ADR-0009)."""
    rt = ApprovalRuntime()
    req = rt.create_request("m.x", "خطة")
    rt.reject(req.id, rejected_by="مدير", reason="لا")
    assert req.status is ApprovalStatus.REJECTED
    req.status = ApprovalStatus.APPROVED      # التعديل المباشر يمر اليوم
    assert req.status is ApprovalStatus.APPROVED


# ===============================================================
# ADR-0009 — الواجهة: عقود الأنماط وحدودها (R-W1-006)
# ===============================================================
from intelligence.interface import (  # noqa: E402
    IntelligenceInterface, IntelligenceMode, IntelligenceRequest,
    IntelligenceResult, IntelligenceStatus, EngineeringCandidate,
    compare_candidates)
from pipeline import ExecutionPipeline  # noqa: E402
from mission_engine import MissionEngine, MissionState  # noqa: E402
from events import EventBus  # noqa: E402
from resolvers import (  # noqa: E402
    CapabilitySelection, ProviderSelection, ResolutionStatus, SelectionScore)
from agos_kernel.execution.engine import (  # noqa: E402
    InvocationOutcome as _Outcome)


class _GuardCapability:
    """حارس: أي استدعاء خارج النواة يفشل الاختبار (ADR-0008/0009)."""

    def execute(self, parameters):
        raise AssertionError("القدرة استُدعيت خارج النواة (ADR-0009)")


class _FakeCore:
    """نواة زائفة حتمية — إثبات المرور المميّز (هوية الدالة والمعاملات)."""

    def __init__(self):
        self.calls = []

    def invoke_sync(self, func, *args, **kwargs):
        self.calls.append((func, args, kwargs))
        return _Outcome(value={"marker": "CORE-ROUTED"})


class _MutableCapResolver:
    """محلل زائف قابل للتبديل — لهوية اختيار قابلة للتغيير (اختبار الحارس)."""

    def __init__(self, capability, name="GuardCap"):
        self._capability = capability
        self._name = name

    def set_identity(self, name):
        self._name = name

    def resolve(self, mission, context):
        return CapabilitySelection(
            capability=self._capability, capability_name=self._name,
            manifest_id="", status=ResolutionStatus.SUCCESS,
            score=SelectionScore(), reason="deterministic-fake",
            record="cap-record")


class _FakeProvResolver:
    """محلل مزوّد زائف — مثيل ثابت واحد كما السجل الحقيقي (الشريحة 0097:
    حلّان على الهوية نفسها عند الربط وعند التنفيذ — object() جديد لكل حل
    كان يجعل الهوية غير مستقرة خلافاً لسبب الحل المعلن «deterministic-fake»)."""

    def __init__(self):
        self._provider = object()

    def resolve(self, capability, mission):
        return ProviderSelection(
            provider=self._provider, provider_name="FakeProvider",
            status=ResolutionStatus.SUCCESS, score=SelectionScore(),
            reason="deterministic-fake", record="prov-record")


def _interface_with_core(core, resolver_name="GuardCap"):
    """واجهة فوق سلسلة حية حقيقية (أنبوب + MissionEngine) بنواة زائفة —
    المحلل نفسه يُستعمل للتحقق والتنفيذ (اتساق الاعتماد)."""
    core.reset() if hasattr(core, "reset") else None
    guard = _GuardCapability()
    resolver = _MutableCapResolver(guard, name=resolver_name)
    pipeline = ExecutionPipeline(
        event_bus=EventBus(),
        capability_resolver=resolver,
        provider_resolver=_FakeProvResolver(),
        execution_engine=core)
    engine = MissionEngine(pipeline)
    return IntelligenceInterface(
        mission_engine=engine, capability_resolver=resolver), resolver


def _mission_spec(capability="GuardCap", parameters=None):
    return {"name": "مهمة اختبار", "description": "وصف",
            "capability": capability, "parameters": parameters or {"x": 1}}


# ---------- النمط: إلزامي ومتحقق قبل أي عمل ----------
def test_mode_is_mandatory_and_validated_before_work():
    interface, _ = _interface_with_core(_FakeCore())
    for bad_mode in (None, "fast", 3, IntelligenceMode):
        try:
            interface.run(IntelligenceRequest(mode=bad_mode))
            raised = False
        except ValueError as e:
            raised = "نمط ذكاء غير صالح" in str(e)
        assert raised is True        # خطأ صريح — لا تحويل صامت لنمط آخر


# ---------- Instant ----------
def test_instant_routes_through_core_with_evidence():
    core = _FakeCore()
    interface, _ = _interface_with_core(core)
    result = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.INSTANT, mission=_mission_spec()))
    assert result.status is IntelligenceStatus.COMPLETED
    assert result.result == {"marker": "CORE-ROUTED"}
    assert result.decision_records == ["cap-record", "prov-record"]
    assert len(core.calls) == 1
    assert core.calls[0][0].__self__ is interface._capability_resolver._capability
    assert core.calls[0][0].__func__ is _GuardCapability.execute  # والدالة نفسها
    assert core.calls[0][1] == ({"x": 1},)        # المعاملات كما هي
    assert core.calls[0][2] == {}
    assert "intent-interpretation" in result.gaps  # الفجوة مسماة لا مخفية


def test_instant_validation_blocks_execution_before_any_work():
    core = _FakeCore()
    interface, _ = _interface_with_core(core)
    result = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.INSTANT,
        mission={"name": "", "capability": ""}))   # التحقق يرفض
    assert result.status is IntelligenceStatus.FAILED
    assert "capability is required" in (result.error or "")
    assert core.calls == []                       # لا استدعاء قبل التحقق


def test_instant_without_mission_spec_fails_with_named_gap():
    interface, _ = _interface_with_core(_FakeCore())
    result = interface.run(IntelligenceRequest(mode=IntelligenceMode.INSTANT))
    assert result.status is IntelligenceStatus.FAILED
    assert "intent-interpretation" in (result.error or "")
    assert "intent-interpretation" in result.gaps


# ---------- Engineer: الخطة ثم الاعتماد ----------
def test_engineer_awaits_approval_with_zero_execution():
    core = _FakeCore()
    interface, _ = _interface_with_core(core)
    result = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.ENGINEER, mission=_mission_spec()))
    assert result.status is IntelligenceStatus.AWAITING_APPROVAL
    assert result.plan is not None
    assert result.plan.steps == [
        "resolve_capability", "resolve_provider", "create_context",
        "execute_skills", "collect_results", "generate_output"]
    assert result.approval_id
    assert result.decision_records == ["cap-record"]   # المفاضلة قبل الاعتماد
    assert core.calls == []                       # لا أي استدعاء تنفيذ (الحارس)


def test_engineer_plan_components_are_honest_projections():
    """R-W1-006 المتبقي (سجل العمل 0043): مكونات خطة Engineer — إسقاط موثق
    المصدر لما هو كائن فعلاً: المتطلبات مواصفة المرسل حرفياً، والبدائل مرشحو
    دليل القرار، والتكلفة المدة المعلنة حرفياً؛ ولا يُختلق تقييم مخاطر ولا
    تصميم معماري — None مع فجوة مسماة."""
    interface, _ = _interface_with_core(_FakeCore())
    result = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.ENGINEER, mission=_mission_spec()))
    assert result.status is IntelligenceStatus.AWAITING_APPROVAL
    ep = result.engineering_plan
    assert ep is not None
    # المتطلبات: مواصفة المرسل منقولة حرفياً بوسم مصدرها
    reqs = {r["ref"]: r for r in ep["requirements"]}
    assert reqs["mission.name"]["value"] == "مهمة اختبار"
    assert reqs["mission.description"]["value"] == "وصف"
    assert reqs["mission.capability"]["value"] == "GuardCap"
    assert reqs["mission.parameters.x"]["value"] == 1
    assert all(r["source"] == "caller-provided"
               for r in ep["requirements"])
    # البدائل: من دليل القرار — ليست بدائل تصميم/معمارية
    assert ep["alternatives"]["kind"] == "capability-selection"
    # التكلفة: المدة المعلنة حرفياً في الخطة — لا قياس يُدّعى
    assert ep["cost"]["estimated_duration_ms"] == 5000
    assert ep["cost"]["source"] == "declared-literal"
    assert ep["cost"]["measured"] == []
    # ما لا اشتقاق صادقاً له: لا يُختلق — None والفجوة مسماة
    assert ep["risks"] is None
    assert ep["architecture_design"] is None
    for gap in ("engineering-plan-requirements-analysis",
               "engineering-plan-risks",
               "engineering-plan-design-alternatives",
               "engineering-plan-cost-estimate",
               "engineering-plan-architecture"):
        assert gap in result.gaps


def test_engineer_plan_components_project_real_decision_record():
    """البدائل تُشتق من دليل قرار حقيقي: مرشحوه بدرجاتهم واستبعادهم
    والاختيار وكسر التعادل — إسقاط مطابق للسجل لا نسخة منفصلة."""
    from decision_pipeline import (
        CandidateEvaluation, DecisionRecord, DecisionScore)
    from intelligence.interface import _engineering_plan
    record = DecisionRecord(
        decision_id="d1", kind="capability", policy_id="p1",
        policy_version="1",
        candidates=[
            CandidateEvaluation(
                name="CapA", offered_skills=["s1"],
                score=DecisionScore(total=2.0, skill_match=1.0),
                values_used={"skill_match": {"s1": 1.0}}),
            CandidateEvaluation(
                name="CapB", offered_skills=["s2"],
                excluded=True, exclusion_reason="skill-missing"),
        ],
        selected="CapA", ranked_alternatives=[],
        tie_break="registration-order", status="selected")
    mission = Mission(name="n", capability="CapA", parameters={"x": 1})
    plan = MissionPlanner().plan(mission)
    ep = _engineering_plan(mission, plan, [record])
    alt = ep["alternatives"]
    assert alt["kind"] == "capability-selection"
    assert alt["selected"] == "CapA"
    assert alt["tie_break"] == "registration-order"
    assert [c["name"] for c in alt["candidates"]] == ["CapA", "CapB"]
    # المستبعد باقٍ في الدليل بموضع فشله — لا يُحذف ولا يُجمّل
    assert alt["candidates"][1]["excluded"] is True
    assert alt["candidates"][1]["exclusion_reason"] == "skill-missing"
    # المختار بدرجته كاملة لا بالإجمالي وحده
    assert alt["candidates"][0]["score"]["total"] == 2.0
    assert alt["candidates"][0]["score"]["skill_match"] == 1.0


def test_engineer_failed_results_have_no_engineering_plan():
    """الفشل قبل الخطة والاختيار لا يعرض مكونات — لا شيء يُسقط ولا يُختلق."""
    interface, _ = _interface_with_core(_FakeCore())
    result = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.ENGINEER,
        mission={"name": "x", "capability": ""}))   # تحقق فاشل
    assert result.status is IntelligenceStatus.FAILED
    assert result.engineering_plan is None


def test_intelligence_result_positional_fields_unchanged():
    """G2/توافق: الحقل الجديد engineering_plan أُضيف بعد الحقول القائمة
    كلها — المنشئ الموضعي القديم لا يزال يضع gaps في موضعه لا في الجديد."""
    r = IntelligenceResult(
        IntelligenceMode.ENGINEER, IntelligenceStatus.FAILED,
        "m1", None, "خطأ", ["record"], None, None, None, None, ["g"])
    assert r.gaps == ["g"]
    assert r.engineering_plan is None


def test_engineer_plan_components_mutation_invalidates_approval():
    """سجل العمل 0044: المكونات المعروضة كائن مشترك كالخطة — تعديل أي
    مكوّن منها بعد العرض يُكشف ببصمة عميقة عند بوابتي الاعتماد **والتنفيذ**
    فيُرفض بلا استدعاء نواة، والمسار غير المعدّل يعتمد وينفذ مرة واحدة
    كما كان."""
    # المسار غير المعدّل أولاً: يعتمد وينفذ مرة واحدة (بلا انكسار)
    core = _FakeCore()
    interface, _ = _interface_with_core(core)
    clean = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.ENGINEER, mission=_mission_spec()))
    approved = interface.approve(clean.approval_id, approver="م")
    assert approved.status is IntelligenceStatus.APPROVED
    executed = interface.execute_approved(clean.approval_id)
    assert executed.status is IntelligenceStatus.COMPLETED
    assert core.calls != []

    # بوابة الاعتماد: تعديل المتطلبات بعد العرض — يُرفض بلا استدعاء نواة
    core1 = _FakeCore()
    interface2, _ = _interface_with_core(core1)
    r1 = interface2.run(IntelligenceRequest(
        mode=IntelligenceMode.ENGINEER, mission=_mission_spec()))
    r1.engineering_plan["requirements"].append(
        {"ref": "mission.name", "value": "مزيف", "source": "caller-provided"})
    rejected = interface2.approve(r1.approval_id, approver="م")
    assert rejected.status is IntelligenceStatus.FAILED
    assert "تغيّر" in (rejected.error or "")
    assert core1.calls == []            # لا نواة استُدعيت

    # بوابة التنفيذ: اعتماد سليم ثم تعديل المتطلبات قبل التنفيذ — يُرفض
    core2 = _FakeCore()
    interface3, _ = _interface_with_core(core2)
    r2 = interface3.run(IntelligenceRequest(
        mode=IntelligenceMode.ENGINEER, mission=_mission_spec()))
    ok = interface3.approve(r2.approval_id, approver="م")
    assert ok.status is IntelligenceStatus.APPROVED
    r2.engineering_plan["requirements"].append(
        {"ref": "mission.name", "value": "مزيف", "source": "caller-provided"})
    rejected_exec = interface3.execute_approved(r2.approval_id)
    assert rejected_exec.status is IntelligenceStatus.FAILED
    assert "اختلاف المحتوى" in (rejected_exec.error or "")
    assert core2.calls == []            # لا نواة استُدعيت

    # بوابة التنفيذ: تعديل البدائل بعد الاعتماد — يُرفض كذلك
    core3 = _FakeCore()
    interface4, _ = _interface_with_core(core3)
    r3 = interface4.run(IntelligenceRequest(
        mode=IntelligenceMode.ENGINEER, mission=_mission_spec()))
    interface4.approve(r3.approval_id, approver="م")
    r3.engineering_plan["alternatives"]["kind"] = "fabricated"
    rejected2 = interface4.execute_approved(r3.approval_id)
    assert rejected2.status is IntelligenceStatus.FAILED
    assert "اختلاف المحتوى" in (rejected2.error or "")
    assert core3.calls == []

    # بوابة التنفيذ: تعديل التكلفة بعد الاعتماد — يُرفض كذلك
    core4 = _FakeCore()
    interface5, _ = _interface_with_core(core4)
    r4 = interface5.run(IntelligenceRequest(
        mode=IntelligenceMode.ENGINEER, mission=_mission_spec()))
    interface5.approve(r4.approval_id, approver="م")
    r4.engineering_plan["cost"]["estimated_duration_ms"] = 99999
    rejected3 = interface5.execute_approved(r4.approval_id)
    assert rejected3.status is IntelligenceStatus.FAILED
    assert "اختلاف المحتوى" in (rejected3.error or "")
    assert core4.calls == []


def test_engineering_plan_fingerprint_preserves_types():
    """سجل العمل 0045: البصمة محافظة على الأنواع — القائمة والصف تمثيلان
    مختلفان (JSON كان يطويهما)، وتغيير نوع قيمة متطلب بعد العرض يُرفض
    بلا تغيير معاملات المهمة الأصلية."""
    from intelligence.interface import _engineering_plan_fingerprint
    # القائمة والصف محتوى «متشابه» لكنهما نوعان مختلفان — لا يُطوى أحدهما
    assert _engineering_plan_fingerprint(
        {"value": [1, 2]}) != _engineering_plan_fingerprint(
        {"value": (1, 2)})
    # النص والرقم لا يُطويان معاً
    assert _engineering_plan_fingerprint(
        {"v": "1"}) != _engineering_plan_fingerprint({"v": 1})
    # تعديل نوع قيمة متطلب بعد العرض (بلا تغيير معاملات المهمة) يُكشف
    core = _FakeCore()
    interface, _ = _interface_with_core(core)
    result = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.ENGINEER, mission=_mission_spec()))
    req = result.engineering_plan["requirements"][0]
    assert req["ref"] == "mission.name"
    req["value"] = [result.engineering_plan["requirements"][0]["value"]]
    rejected = interface.approve(result.approval_id, approver="م")
    assert rejected.status is IntelligenceStatus.FAILED
    assert "تغيّر" in (rejected.error or "")
    assert core.calls == []


def test_engineer_validation_blocks_plan_and_approval():
    interface, _ = _interface_with_core(_FakeCore())
    result = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.ENGINEER,
        mission={"name": "x", "capability": ""}))   # تحقق فاشل
    assert result.status is IntelligenceStatus.FAILED
    assert "فشل التحقق" in (result.error or "")
    assert result.approval_id is None            # لا خطة ولا اعتماد


def test_engineer_approve_then_execute_once_via_core():
    core = _FakeCore()
    interface, _ = _interface_with_core(core)
    awaiting = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.ENGINEER, mission=_mission_spec()))
    approval_id = awaiting.approval_id

    approved = interface.approve(approval_id, approver="مدير")
    assert approved.status is IntelligenceStatus.APPROVED    # اعتماد بلا تنفيذ
    assert core.calls == []

    executed = interface.execute_approved(approval_id)
    assert executed.status is IntelligenceStatus.COMPLETED
    assert executed.result == {"marker": "CORE-ROUTED"}
    assert executed.decision_records == ["cap-record", "prov-record"]
    assert len(core.calls) == 1
    assert core.calls[0][1] == ({"x": 1},)

    # الإجازة استُهلكت — طلب ثانٍ يُرفض ولا إعادة تنفيذ
    second = interface.execute_approved(approval_id)
    assert second.status is IntelligenceStatus.FAILED
    assert "نهائياً" in (second.error or "")          # إعادة الاستخدام نهائية
    assert len(core.calls) == 1                     # لم يُستدع عمل ثانٍ


def test_engineer_rejection_blocks_execution():
    core = _FakeCore()
    interface, _ = _interface_with_core(core)
    awaiting = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.ENGINEER, mission=_mission_spec()))
    rejected = interface.reject(awaiting.approval_id,
                                rejected_by="مدير", reason="غير مناسب")
    assert rejected.status is IntelligenceStatus.REJECTED
    after = interface.execute_approved(awaiting.approval_id)
    assert after.status is IntelligenceStatus.FAILED
    assert core.calls == []                          # لا تنفيذ بعد الرفض


def test_engineer_rejected_not_reusable_even_if_status_mutated():
    """الرفض نهائي عند الحارس — حتى لو غُيّرت حالة الطلب القابل للتعديل
    لاحقاً إلى APPROVED (التوصيف أثبت قابلية التعديل المباشر)."""
    core = _FakeCore()
    interface, _ = _interface_with_core(core)
    awaiting = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.ENGINEER, mission=_mission_spec()))
    interface.reject(awaiting.approval_id, rejected_by="مدير", reason="لا")
    # تعديل مباشر للحالة (السلوك القائم الموصوف) — الحارس لا يخدع
    underlying = interface._approval.get_request(awaiting.approval_id)
    underlying.status = ApprovalStatus.APPROVED
    approve_try = interface.approve(awaiting.approval_id, approver="مدير")
    assert approve_try.status is IntelligenceStatus.FAILED
    execute_try = interface.execute_approved(awaiting.approval_id)
    assert execute_try.status is IntelligenceStatus.FAILED
    assert core.calls == []


def test_engineer_plan_change_invalidates_prior_approval():
    core = _FakeCore()
    interface, _ = _interface_with_core(core)
    first = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.ENGINEER,
        mission=_mission_spec(parameters={"x": 1})))
    # خطة جديدة لنفس المهمة (بمعرفها المثبت) بمعاملات مختلفة
    same_id = dict(_mission_spec(parameters={"x": 2}))
    same_id["id"] = first.mission_id
    second = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.ENGINEER, mission=same_id))
    assert second.approval_id != first.approval_id
    interface.approve(first.approval_id, approver="مدير")
    after = interface.execute_approved(first.approval_id)
    assert after.status is IntelligenceStatus.FAILED      # الاعتماد السابق أُبطل
    assert core.calls == []


def test_engineer_selection_change_refuses_execution():
    """إعادة الحل تختار غير الموافق عليه — فشل صريح قبل أي تنفيذ (الاعتماد
    لا يُستعمل لاختيار مختلف)."""
    core = _FakeCore()
    interface, resolver = _interface_with_core(core)
    awaiting = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.ENGINEER, mission=_mission_spec()))
    interface.approve(awaiting.approval_id, approver="مدير")
    resolver.set_identity("DifferentSelection")    # تغيّر الاختيار بعد الاعتماد
    after = interface.execute_approved(awaiting.approval_id)
    assert after.status is IntelligenceStatus.FAILED
    assert "سُجل إبطال" in (after.error or "")         # إبطال نهائي مسجل
    assert core.calls == []                          # لا تنفيذ باختيار مختلف


def test_engineer_skipped_is_not_approval():
    core = _FakeCore()
    interface, _ = _interface_with_core(core)
    awaiting = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.ENGINEER, mission=_mission_spec()))
    interface._approval.skip(awaiting.approval_id, reason="تخطي")
    approve_try = interface.approve(awaiting.approval_id, approver="مدير")
    assert approve_try.status is IntelligenceStatus.FAILED   # SKIPPED لا يعتمد
    execute_try = interface.execute_approved(awaiting.approval_id)
    assert execute_try.status is IntelligenceStatus.FAILED    # ولا يجيز التنفيذ
    assert core.calls == []


# ---------- Research: المقارنة المسندة ----------
def _write_repo(path, files):
    path.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        (path / name).write_text(content, encoding="utf-8")


def test_research_ranking_with_real_evidence(tmp_path):
    repo = tmp_path / "pyrepo"
    _write_repo(repo, {"a.py": "x = 1\n", "b.py": "y = 2\n"})
    interface = IntelligenceInterface()
    result = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.RESEARCH,
        question="كيف أبني هذه الخدمة؟",
        evidence_path=str(repo),
        candidates=[
            EngineeringCandidate(id="py", name="PyApp",
                                 technologies=["Python"]),
            EngineeringCandidate(id="rust", name="RustApp",
                                 technologies=["Rust"]),
        ]))
    assert result.status is IntelligenceStatus.COMPLETED
    comparison = result.comparison
    assert comparison.policy_id == "repository-stack-alignment"
    assert comparison.best.candidate_id == "py"           # المرتب الأول
    assert comparison.best.score == 1
    assert comparison.best.matched_technologies == ("python",)   # الدليل (الصيغة المعيارية للتقاطع)
    ranked_ids = [c.candidate_id for c in comparison.ranked]
    assert ranked_ids == ["py", "rust"]                   # الأعلى ثم الأدنى
    assert "python" in result.evidence_snapshot["detected_stack"]
    assert result.evidence_snapshot["detected"]["languages"]["Python"]["files"] >= 1


def test_research_evidence_change_changes_ranking(tmp_path):
    """الحاسم: تغيير الدليل يغيّر المقارنة وفق السياسة المعلنة."""
    py_repo = tmp_path / "pyrepo"
    _write_repo(py_repo, {"a.py": "x = 1\n"})
    js_repo = tmp_path / "jsrepo"
    _write_repo(js_repo, {"a.js": "let x = 1;\n"})
    interface = IntelligenceInterface()
    candidates = [
        EngineeringCandidate(id="py", name="PyApp", technologies=["Python"]),
        EngineeringCandidate(id="js", name="JsApp", technologies=["JavaScript"]),
    ]
    on_py = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.RESEARCH, evidence_path=str(py_repo),
        candidates=candidates))
    on_js = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.RESEARCH, evidence_path=str(js_repo),
        candidates=candidates))
    assert on_py.comparison.best.candidate_id == "py"
    assert on_js.comparison.best.candidate_id == "js"      # انقلب الترتيب بالدليل


def test_research_zero_intersection_is_unavailable_not_first_by_tie(tmp_path):
    """تقاطع الجميع صفراً: لا توصية — قاعدة كسر التعادل لا تعوّض غياب المواءمة،
    والمقارنة محفوظة في النتيجة."""
    repo = tmp_path / "pyrepo"
    _write_repo(repo, {"a.py": "x = 1\n"})
    interface = IntelligenceInterface()
    result = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.RESEARCH, evidence_path=str(repo),
        candidates=[
            EngineeringCandidate(id="cobol1", name="C1", technologies=["Cobol"]),
            EngineeringCandidate(id="cobol2", name="C2", technologies=["COBOL"]),
        ]))
    assert result.status is IntelligenceStatus.RECOMMENDATION_UNAVAILABLE
    assert "no-relevant-evidence" in (result.error or "")
    assert result.comparison is not None               # المقارنة محفوظة
    assert result.comparison.best is None              # لا مرتب أول بلا مواءمة
    assert all(c.score == 0 for c in result.comparison.ranked)


def test_research_no_candidates_is_explicit_unavailable(tmp_path):
    repo = tmp_path / "pyrepo"
    _write_repo(repo, {"a.py": "x = 1\n"})
    interface = IntelligenceInterface()
    result = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.RESEARCH, evidence_path=str(repo)))
    assert result.status is IntelligenceStatus.RECOMMENDATION_UNAVAILABLE
    assert "no-candidates" in result.gaps


def test_research_no_evidence_source_is_explicit_unavailable():
    interface = IntelligenceInterface()
    result = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.RESEARCH, question="سؤال"))
    assert result.status is IntelligenceStatus.RECOMMENDATION_UNAVAILABLE
    assert "no-evidence-source" in result.gaps


def test_research_candidate_technologies_are_caller_provided():
    """التقنيات المعلنة caller-provided — توثقها المقارنة ولا تدّعي أنها
    حقائق أثبتها التحليل (الأدلة المثبتة هي المتقاطع مع الحزمة المكتشفة)."""
    from pathlib import Path
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "r"
        _write_repo(repo, {"a.py": "x = 1\n"})
        shared = IntelligenceInterface()._analyze(str(repo))
        comparison = compare_candidates(
            [EngineeringCandidate(id="c", name="C", technologies=["Python"])],
            shared)
        # المكتشف مفصول الحقول بمصدر كل حقل من الخدمة المعتمدة
        assert comparison.evidence_snapshot["detected"]["languages"][
            "Python"]["files"] >= 1
        assert comparison.ranked[0].matched_technologies == ("python",)


# ===============================================================
# مراجعة الحدود — الاعتماد والمقارنة والمدخل الخارجي (جولة المراجعة)
# ===============================================================
def test_engineer_plan_object_mutation_refused(tmp_path=None):
    """تعديل **الخطة نفسها** مع إبقاء المعرّف والعمل والمعاملات — لا يمر:
    الخطة المعروضة كائن مشترك، وتعديلها يظهر عند التنفيذ فيُرفض نهائياً."""
    core = _FakeCore()
    interface, _ = _interface_with_core(core)
    awaiting = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.ENGINEER, mission=_mission_spec()))
    interface.approve(awaiting.approval_id, approver="مدير")
    # تعديل الخطة المعروضة — المعرّف والعمل والمعاملات كما هما
    awaiting.plan.steps = ("خطوة-معدلة",)
    after = interface.execute_approved(awaiting.approval_id)
    assert after.status is IntelligenceStatus.FAILED
    assert "سُجل إبطال" in (after.error or "")         # إبطال نهائي مسجل
    assert core.calls == []                       # لا تنفيذ بخطة معدلة
    # النهائية: إرجاع الخطوات كما كانت لا يحيي الإجازة
    awaiting.plan.steps = [
        "resolve_capability", "resolve_provider", "create_context",
        "execute_skills", "collect_results", "generate_output"]
    again = interface.execute_approved(awaiting.approval_id)
    assert again.status is IntelligenceStatus.FAILED
    assert core.calls == []


def test_engineer_expired_then_restored_is_terminal():
    """انتهاء الاعتماد ثم استرجاع حالته: المنع نهائي — استرجاع الحالة لا
    يحيي الإجازة (الحارس يسجل الإبطال عند رصد الحالة غير المعتمدة)."""
    core = _FakeCore()
    interface, _ = _interface_with_core(core)
    awaiting = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.ENGINEER, mission=_mission_spec()))
    interface.approve(awaiting.approval_id, approver="مدير")
    underlying = interface._approval.get_request(awaiting.approval_id)
    # انتهاء الصلاحية ثم محاولة تنفيذ — رفض
    underlying.status = ApprovalStatus.EXPIRED
    first_try = interface.execute_approved(awaiting.approval_id)
    assert first_try.status is IntelligenceStatus.FAILED
    assert core.calls == []
    # استرجاع الحالة ثم محاولة مجددة — الرفض نهائي لا يُحيى
    underlying.status = ApprovalStatus.APPROVED
    second_try = interface.execute_approved(awaiting.approval_id)
    assert second_try.status is IntelligenceStatus.FAILED
    assert "نهائياً" in (second_try.error or "") or "لا يحييها" in (second_try.error or "")
    assert core.calls == []


def test_engineer_pipeline_selection_change_refused_at_invocation():
    """الفاصل: محلل يعيد A عند التخطيط والتحقق ثم **B داخل الأنبوب** —
    يجب ألا يُستدعى B: النواة المُتحققة تعترض عند حد الاستدعاء نفسه."""
    core = _FakeCore()
    interface, resolver = _interface_with_core(core)

    class _SwitchingResolver:
        """يعيد A ثم B ثم B... — التبديل بين التحقق والأنبوب."""

        def __init__(self):
            self.calls = 0

        def resolve(self, mission, context):
            self.calls += 1
            capability = _GuardCapability()
            return CapabilitySelection(
                capability=capability,
                capability_name="GuardCap",
                manifest_id="", status=ResolutionStatus.SUCCESS,
                score=SelectionScore(), reason="switching",
                record="cap-record")

    interface._capability_resolver = resolver  # محلل ثابت للتحقق (A)
    awaiting = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.ENGINEER, mission=_mission_spec()))
    interface.approve(awaiting.approval_id, approver="مدير")
    # الآن نبدّل محلل الأنبوب إلى المحول المبدّل — يعيد كائناً جديداً (B) داخل run
    interface._mission_engine.executor.pipeline.capability_resolver = _SwitchingResolver()
    after = interface.execute_approved(awaiting.approval_id)
    assert after.status is IntelligenceStatus.FAILED
    # B لم يمر إلى النواة الداخلية: النواة المُتحققة رفضته عند حد الاستدعاء
    assert "ليس العمل الموافق عليه" in (after.error or "")
    assert core.calls == []                       # لا استدعاء عمل إطلاقاً
    assert after.result is None                   # لا نتيجة عمل — الفشل صريح


def test_engineer_same_name_and_id_different_object_refused():
    """تطبيقان مختلفان يحملان الاسم والمعرّف نفسيهما: هوية الكائن هي الفيصل —
    الثاني لا يمر إلى النواة."""
    core = _FakeCore()
    interface, _ = _interface_with_core(core)
    awaiting = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.ENGINEER, mission=_mission_spec()))
    interface.approve(awaiting.approval_id, approver="مدير")

    # محلل يعيد كائناً **جديداً** بنفس الاسم والمعرّف تماماً
    class _SameNameResolver:
        def resolve(self, mission, context):
            return CapabilitySelection(
                capability=_GuardCapability(),      # كائن جديد — نفس الاسم
                capability_name="GuardCap", manifest_id="",
                status=ResolutionStatus.SUCCESS, score=SelectionScore(),
                reason="same-name-new-object", record="cap-record")

    interface._mission_engine.executor.pipeline.capability_resolver = _SameNameResolver()
    after = interface.execute_approved(awaiting.approval_id)
    assert after.status is IntelligenceStatus.FAILED
    assert "ليس العمل الموافق عليه" in (after.error or "")


def test_engineer_core_failure_consumes_permit_no_retry():
    """فشل النواة ثم محاولة ثانية: الإجازة استُهلكت رغم الفشل — لا إعادة
    تلقائية (محاولة واحدة داخل الواجهة)."""
    class _FailingCore:
        def __init__(self):
            self.calls = []

        def invoke_sync(self, func, *args, **kwargs):
            self.calls.append((func, args, kwargs))
            from agos_kernel.execution.engine import InvocationOutcome
            return InvocationOutcome(error=RuntimeError("core-failure"))

    core = _FailingCore()
    interface, _ = _interface_with_core(core)
    awaiting = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.ENGINEER, mission=_mission_spec()))
    interface.approve(awaiting.approval_id, approver="مدير")
    first = interface.execute_approved(awaiting.approval_id)
    assert first.status is IntelligenceStatus.FAILED
    assert "core-failure" in (first.error or "")
    assert len(core.calls) == 1                 # حاول مرة
    second = interface.execute_approved(awaiting.approval_id)
    assert second.status is IntelligenceStatus.FAILED      # لا إعادة بالإجازة نفسها
    assert len(core.calls) == 1                 # لم يُستدع عمل ثانٍ


def test_instant_full_path_failure_carries_both_decision_records():
    """الفشل عبر المسار الكامل (واجهة ← MissionEngine ← أنبوب ← نواة): سجلا
    القرار نفسيهما يصلان مع الفشل — الدليل لا يسقط."""
    class _FailingCore:
        def __init__(self):
            self.calls = []

        def invoke_sync(self, func, *args, **kwargs):
            self.calls.append((func, args, kwargs))
            from agos_kernel.execution.engine import InvocationOutcome
            return InvocationOutcome(error=RuntimeError("core-failure"))

    core = _FailingCore()
    interface, _ = _interface_with_core(core)
    result = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.INSTANT, mission=_mission_spec()))
    assert result.status is IntelligenceStatus.FAILED
    assert "core-failure" in (result.error or "")
    assert result.decision_records == ["cap-record", "prov-record"]   # الدليل مع الفشل
    assert len(core.calls) == 1
    assert core.calls[0][0].__self__.__class__ is _GuardCapability


def test_mission_object_supported_not_just_dict():
    """العقد: مواصفة المهمة قاموس **أو كائن Mission** — الحالتان تعملان،
    وكائن Mission المرسل معزول عن تعديل المرسل (نسخة عميقة)."""
    from mission import Mission as _Mission
    core = _FakeCore()
    interface, _ = _interface_with_core(core)
    mission = _Mission(name="مهمة-كائن", capability="GuardCap",
                       parameters={"k": "v"})
    result = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.INSTANT, mission=mission))
    assert result.status is IntelligenceStatus.COMPLETED
    assert result.result == {"marker": "CORE-ROUTED"}
    assert core.calls[0][1] == ({"k": "v"},)


def test_research_duplicate_and_case_technologies_do_not_inflate():
    """التكرار واختلاف الحالة لا يحسّنان الدرجة: مجموعة معيارية واحدة لكل
    مرشح قبل التقاطع (تطبيع وإزالة تكرار)."""
    from pathlib import Path
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "r"
        _write_repo(repo, {"a.py": "x = 1\n"})
        shared = IntelligenceInterface()._analyze(str(repo))
        duplicated = compare_candidates(
            [EngineeringCandidate(id="d", name="D",
                                  technologies=["Python", "python", "PYTHON"])],
            shared)
        honest = compare_candidates(
            [EngineeringCandidate(id="h", name="H", technologies=["Python"])],
            shared)
        assert duplicated.ranked[0].score == honest.ranked[0].score == 1


def test_research_declared_technologies_tagged_caller_provided():
    """التقنيات المعلنة محفوظة بمصدرها الصريح (caller-provided) مفصولة عن
    الحقائق المكتشفة — والحقائق تحمل مصدر الخدمة المعتمدة لكل حقل."""
    from pathlib import Path
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "r"
        _write_repo(repo, {"a.py": "x = 1\n"})
        shared = IntelligenceInterface()._analyze(str(repo))
        comparison = compare_candidates(
            [EngineeringCandidate(id="c", name="C", technologies=["Python"])],
            shared)
        # المعلن: بمصدره الصريح
        assert comparison.declared_technologies == {"c": ["Python"]}
        assert comparison.declared_source == "caller-provided"
        # المكتشف يحمل أدلة المصدر الفعلية: قياس اللغة (ملفات/أسطر) لا اسم آلية
        detected = comparison.evidence_snapshot["detected"]
        assert detected["languages"]["Python"]["files"] >= 1
        assert detected["languages"]["Python"]["lines"] >= 1


def test_external_entry_delegates_to_reference_interface():
    """المدخل الخارجي (agos.intelligence) يفوّض للواجهة المرجعية فعلاً — لا
    محرك موازٍ (يُعدّ R-W3-019 على هذا الربط)."""
    import agos.intelligence as external
    # رفض النمط الغائب يمر عبر الواجهة المرجعية نفسها (عقد التحقق قبل العمل)
    try:
        external.run_intelligence(IntelligenceRequest())
        raised = False
    except ValueError as e:
        raised = "نمط ذكاء غير صالح" in str(e)
    assert raised is True
    from agos_kernel.intelligence.interface import IntelligenceInterface as Ref
    assert external.get_intelligence_interface().__class__ is Ref


# ===============================================================
# مراجعة الحدود — جولة 2: المدخل الموحد وحارس العمل الكامل وأدلة المصدر
# ===============================================================
def test_external_entry_same_reference_approves_and_executes(monkeypatch):
    """المدخل الخارجي يفوّض للنسخة المرجعية نفسها: معرّف الاعتماد الذي
    يعود من run_intelligence تعتمده النسخة المرجعية وتنفّذه — لا نسختان
    (الحقن عبر monkeypatch — يستعاد تلقائياً، لا تسريب)."""
    import agos.intelligence as external
    interface, _ = _interface_with_core(_FakeCore())
    monkeypatch.setattr(external, "_INTELLIGENCE_INTERFACE", interface,
                        raising=False)
    awaiting = external.run_intelligence(IntelligenceRequest(
        mode=IntelligenceMode.ENGINEER, mission=_mission_spec()))
    assert awaiting.status is IntelligenceStatus.AWAITING_APPROVAL
    reference = external.get_intelligence_interface()
    assert reference is interface                      # المدخل يفوّض لها نفسها
    approved = reference.approve(awaiting.approval_id, approver="مدير")
    assert approved.status is IntelligenceStatus.APPROVED
    executed = reference.execute_approved(awaiting.approval_id)
    assert executed.status is IntelligenceStatus.COMPLETED
    assert executed.result == {"marker": "CORE-ROUTED"}


def test_external_entry_distinctive_delegation():
    """إثبات تفويض مميز: الطلب نفسه يصل الواجهة المرجعية وعلامتها تعود —
    بترقيع مؤقت لمسار واحد في النسخة المرجعية."""
    import agos.intelligence as external
    from agos_kernel.intelligence.interface import IntelligenceInterface as Ref
    received = []

    def _spy_run(self, request):
        received.append(request)
        return IntelligenceResult(
            mode=IntelligenceMode.RESEARCH,
            status=IntelligenceStatus.COMPLETED,
            result={"marker": "REFERENCE-DELEGATED"})

    original = Ref.run
    original_instance = getattr(external, "_INTELLIGENCE_INTERFACE", None)
    Ref.run = _spy_run
    try:
        request = IntelligenceRequest(mode=IntelligenceMode.RESEARCH,
                                      question="سؤال")
        result = external.run_intelligence(request)
    finally:
        Ref.run = original
        if original_instance is not None:
            external._INTELLIGENCE_INTERFACE = original_instance
        else:
            del external._INTELLIGENCE_INTERFACE     # استعادة — لا تسريب إعداد
    assert len(received) == 1
    assert received[0] is request                     # الطلب نفسه وصل المرجع
    assert result.result == {"marker": "REFERENCE-DELEGATED"}


def test_engineer_swapped_execute_function_refused():
    """تبديل ``execute`` على الكائن نفسه بعد الاعتماد — لا يمر: حارس
    الاستدعاء يتحقق من الدالة نفسها لا الكائن وحده."""
    core = _FakeCore()
    interface, _ = _interface_with_core(core)
    awaiting = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.ENGINEER, mission=_mission_spec()))
    interface.approve(awaiting.approval_id, approver="مدير")
    guard = interface._bound_work[awaiting.approval_id][0]
    # تبديل الدالة على الكائن نفسه (الكائن والاسم والمعرّف كما هما)
    guard.execute = lambda parameters: {"marker": "SWAPPED"}
    after = interface.execute_approved(awaiting.approval_id)
    assert after.status is IntelligenceStatus.FAILED
    assert "لم تُعتمد" in (after.error or "") or "ليس العمل الموافق عليه" in (after.error or "")
    assert core.calls == []                          # العمل المبدَّل لم يصل النواة


def test_engineer_pipeline_parameter_change_refused_at_invocation():
    """تغيير المعاملات داخل حل الأنبوب (بعد فحص اللقطة) — لا يمر: الحارس
    يقارن المعاملات المارّة بالمعاملات الموافق عليها عند حد الاستدعاء."""
    core = _FakeCore()
    interface, resolver = _interface_with_core(core)
    awaiting = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.ENGINEER, mission=_mission_spec()))
    interface.approve(awaiting.approval_id, approver="مدير")

    class _ParameterMutatingResolver:
        """يغير معاملات المهمة أثناء الحل داخل الأنبوب — بعد فحص اللقطة."""

        def resolve(self, mission, context):
            mission.parameters["injected"] = True
            return CapabilitySelection(
                capability=resolver._capability,      # التطبيق نفسه
                capability_name="GuardCap", manifest_id="",
                status=ResolutionStatus.SUCCESS, score=SelectionScore(),
                reason="mutating", record="cap-record")

    interface._mission_engine.executor.pipeline.capability_resolver = _ParameterMutatingResolver()
    after = interface.execute_approved(awaiting.approval_id)
    assert after.status is IntelligenceStatus.FAILED
    assert "المعاملات" in (after.error or "")
    assert core.calls == []                          # لا عمل بمعاملات غير معتمدة


def test_engineer_unsuccessful_selection_refused_before_approval():
    """اختيار غير ناجح عند التخطيط: لا يُنشأ اعتماد أصلاً — Engineer بلا عمل
    معتمد مرفوض (مفصول عن Instant الذي لا حد اعتماد عليه)."""
    core = _FakeCore()

    class _FailingResolver:
        def resolve(self, mission, context):
            return CapabilitySelection(
                capability=None, capability_name="", manifest_id="",
                status=ResolutionStatus.NO_MATCH, score=SelectionScore(),
                reason="لا قدرة مطابقة", record="cap-record")

    interface, _ = _interface_with_core(core)
    interface._capability_resolver = _FailingResolver()
    result = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.ENGINEER, mission=_mission_spec()))
    assert result.status is IntelligenceStatus.FAILED
    assert "لا اختيار صالح" in (result.error or "")
    assert result.approval_id is None                # لا اعتماد بلا عمل
    assert core.calls == []


def test_engineer_plan_mission_id_change_refused():
    """تغيير ``mission_id`` في الخطة وحده — اللقطة الكاملة تراه: كل حقول
    الخطة الفعلية محفوظة بلا تحويلات تمحو الاختلاف."""
    core = _FakeCore()
    interface, _ = _interface_with_core(core)
    awaiting = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.ENGINEER, mission=_mission_spec()))
    interface.approve(awaiting.approval_id, approver="مدير")
    awaiting.plan.mission_id = "معرّف-معدل"
    after = interface.execute_approved(awaiting.approval_id)
    assert after.status is IntelligenceStatus.FAILED
    assert "سُجل إبطال" in (after.error or "")         # إبطال نهائي مسجل
    assert core.calls == []


def test_research_framework_recommendation_carries_discovery_evidence(tmp_path):
    """توصية تعتمد على إطار مكتشف تحمل **دليل اكتشافه من المستودع** (الاعتمادية
    والملف) — لا مجرد اسم آلية التحليل؛ وما لا توفره الخدمة يُصرَّح بغيابه."""
    repo = tmp_path / "flaskrepo"
    _write_repo(repo, {
        "app.py": "from flask import Flask\n",
        "requirements.txt": "flask==2.0.1\n",
    })
    interface = IntelligenceInterface()
    result = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.RESEARCH,
        evidence_path=str(repo),
        candidates=[
            EngineeringCandidate(id="flask", name="FlaskApp",
                                 technologies=["Flask"]),
            EngineeringCandidate(id="django", name="DjangoApp",
                                 technologies=["Django"]),
        ]))
    assert result.status is IntelligenceStatus.COMPLETED
    assert result.comparison.best.candidate_id == "flask"
    detected = result.evidence_snapshot["detected"]
    # دليل الاكتشاف الفعلي من المستودع: الاعتمادية والملف
    flask_evidence = detected["frameworks"].get("Flask", [])
    assert flask_evidence, "يجب أن يحمل الإطار دليل اكتشافه"
    assert any(e["dependency"] == "flask" and "requirements.txt" in e["manifest"]
               for e in flask_evidence)
    # قياس اللغة الفعلي (ملفات/أسطر) — لا اسم آلية
    assert detected["languages"]["Python"]["files"] >= 1
    assert detected["languages"]["Python"]["lines"] >= 1
    # وما لا توفره الخدمة يُصرَّح بغيابه
    assert detected["runtimes"]["per_fact_provenance"].startswith("لا توفره")


# ===============================================================
# مراجعة الحدود — جولة 3: نهائية الاعتماد وفحص المحتوى عند الاعتماد
# ===============================================================
def test_engineer_expired_then_restore_pending_is_terminal():
    """النهائية عند الاعتماد أيضاً: انتهاء الطلب ثم رفض الاعتماد ثم استرجاع
    الحالة إلى PENDING — لا يُعتمد ولا يُنفَّذ (الرفض المرصود نهائي)."""
    core = _FakeCore()
    interface, _ = _interface_with_core(core)
    awaiting = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.ENGINEER, mission=_mission_spec()))
    underlying = interface._approval.get_request(awaiting.approval_id)
    underlying.status = ApprovalStatus.EXPIRED
    refused = interface.approve(awaiting.approval_id, approver="مدير")
    assert refused.status is IntelligenceStatus.FAILED       # رفض الاعتماد
    # استرجاع الحالة ثم محاولة الاعتماد والتنفيذ — نهائي لا يُحيى
    underlying.status = ApprovalStatus.PENDING
    revived = interface.approve(awaiting.approval_id, approver="مدير")
    assert revived.status is IntelligenceStatus.FAILED
    executed = interface.execute_approved(awaiting.approval_id)
    assert executed.status is IntelligenceStatus.FAILED
    assert core.calls == []                           # لا عمل إطلاقاً


def test_engineer_modified_plan_refused_at_approval_no_revival():
    """فحص المحتوى **عند الاعتماد**: خطة معدلة لا تُعتمد، واسترجاعها لا يحيي
    الطلب — التعديل يحتاج طلب اعتماد جديداً، ولا يصل أي عمل إلى النواة."""
    core = _FakeCore()
    interface, _ = _interface_with_core(core)
    awaiting = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.ENGINEER, mission=_mission_spec()))
    # تعديل الخطة المعروضة ثم محاولة الاعتماد — رفض
    original_steps = list(awaiting.plan.steps)
    awaiting.plan.steps = ("خطوة-معدلة",)
    refused = interface.approve(awaiting.approval_id, approver="مدير")
    assert refused.status is IntelligenceStatus.FAILED
    assert "تغيّر" in (refused.error or "")
    # استرجاع الخطوات ثم الاعتماد والتنفيذ — لا إحياء
    awaiting.plan.steps = original_steps
    revived = interface.approve(awaiting.approval_id, approver="مدير")
    assert revived.status is IntelligenceStatus.FAILED
    executed = interface.execute_approved(awaiting.approval_id)
    assert executed.status is IntelligenceStatus.FAILED
    assert core.calls == []                           # لا عمل إطلاقاً


def test_engineer_failed_selection_record_preserved():
    """اختيار غير ناجح يحمل كائن دليل مميزاً: **الكائن نفسه** يصل المخرج مع
    الفشل — الدليل لا يسقط عند فشل الحل؛ ولا اعتماد ولا استدعاء تنفيذ."""
    core = _FakeCore()
    distinctive_record = {"decision": "no-match", "marker": "DISTINCTIVE-RECORD"}

    class _FailingResolverWithRecord:
        def resolve(self, mission, context):
            return CapabilitySelection(
                capability=None, capability_name="", manifest_id="",
                status=ResolutionStatus.NO_MATCH, score=SelectionScore(),
                reason="لا قدرة مطابقة", record=distinctive_record)

    interface, _ = _interface_with_core(core)
    interface._capability_resolver = _FailingResolverWithRecord()
    result = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.ENGINEER, mission=_mission_spec()))
    assert result.status is IntelligenceStatus.FAILED
    assert "لا اختيار صالح" in (result.error or "")
    assert len(result.decision_records) == 1
    assert result.decision_records[0] is distinctive_record  # الكائن نفسه (هوية)
    assert result.approval_id is None                # لا اعتماد بلا عمل
    assert core.calls == []                           # ولا استدعاء تنفيذ


# ===============================================================
# مراجعة الحدود — جولة 4: رصد الحالات النهائية قبل بوابات المرحلة
# ===============================================================
def test_engineer_expired_after_approval_then_restore_still_refused():
    """اعتماد ناجح ← انتهاء ← محاولة اعتماد ثانية (رفض مبكر **مع تسجيل
    الإبطال**) ← استرجاع APPROVED ← تنفيذ — مرفوض: الرصد قبل بوابات المرحلة
    فلا يمر الاسترجاع."""
    core = _FakeCore()
    interface, _ = _interface_with_core(core)
    awaiting = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.ENGINEER, mission=_mission_spec()))
    assert interface.approve(awaiting.approval_id, approver="مدير").status \
        is IntelligenceStatus.APPROVED
    underlying = interface._approval.get_request(awaiting.approval_id)
    underlying.status = ApprovalStatus.EXPIRED
    second_approve = interface.approve(awaiting.approval_id, approver="مدير")
    assert second_approve.status is IntelligenceStatus.FAILED   # سُجل الإبطال
    underlying.status = ApprovalStatus.APPROVED                 # استرجاع
    executed = interface.execute_approved(awaiting.approval_id)
    assert executed.status is IntelligenceStatus.FAILED         # لا يُحيى
    assert core.calls == []


def test_engineer_expired_before_approval_then_execute_no_revival():
    """طلب معلق يصبح EXPIRED ثم تُطلب محاولة تنفيذه **قبل الاعتماد** — رصد
    الانتهاء يُسجل؛ واسترجاع الحالة لاحقاً لا يحييه عند الاعتماد."""
    core = _FakeCore()
    interface, _ = _interface_with_core(core)
    awaiting = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.ENGINEER, mission=_mission_spec()))
    underlying = interface._approval.get_request(awaiting.approval_id)
    underlying.status = ApprovalStatus.EXPIRED
    early_execute = interface.execute_approved(awaiting.approval_id)
    assert early_execute.status is IntelligenceStatus.FAILED    # رصد الانتهاء
    underlying.status = ApprovalStatus.PENDING                  # استرجاع
    revived_approve = interface.approve(awaiting.approval_id, approver="مدير")
    assert revived_approve.status is IntelligenceStatus.FAILED  # لا إحياء
    assert core.calls == []


# ===============================================================
# مراجعة الحدود — جولة 5: رصد اختلاف المحتوى قبل بوابات المرحلة
# ===============================================================
def test_engineer_modified_plan_at_early_execute_no_revival():
    """تعديل الخطة ثم تنفيذ مبكر **قبل الاعتماد** — رصد الاختلاف يُسجل قبل
    بوابات المرحلة (إبطال نهائي)؛ استرجاع الخطوات ثم الاعتماد والتنفيذ —
    مرفوضان: الإبطال لا يُحييه استرجاع المحتوى."""
    core = _FakeCore()
    interface, _ = _interface_with_core(core)
    awaiting = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.ENGINEER, mission=_mission_spec()))
    original_steps = list(awaiting.plan.steps)
    awaiting.plan.steps = ("خطوة-معدلة",)
    early = interface.execute_approved(awaiting.approval_id)
    assert early.status is IntelligenceStatus.FAILED      # رصد الاختلاف سُجل
    awaiting.plan.steps = original_steps                 # استرجاع
    approved = interface.approve(awaiting.approval_id, approver="مدير")
    assert approved.status is IntelligenceStatus.FAILED  # لا إحياء
    executed = interface.execute_approved(awaiting.approval_id)
    assert executed.status is IntelligenceStatus.FAILED
    assert core.calls == []                               # لا عمل إطلاقاً


def test_engineer_early_execute_unchanged_plan_not_invalidated():
    """محاولة تنفيذ مبكرة بخطة **لم تتغير**: تُرفض فحسب (غير معتمد) دون إبطال
    — ثم الاعتماد والتنفيذ ينجحان (الإبطال للحالات النهائية واختلاف
    المحتوى فقط، لا للمحاولات المبكرة السليمة)."""
    core = _FakeCore()
    interface, _ = _interface_with_core(core)
    awaiting = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.ENGINEER, mission=_mission_spec()))
    early = interface.execute_approved(awaiting.approval_id)
    assert early.status is IntelligenceStatus.FAILED      # مرفوض فحسب
    # الرسالة لا تدّعي إبطالاً نهائياً — محاولة مبكرة سليمة رفضٌ مؤقت فقط
    assert "نهائياً" not in (early.error or "")
    assert "لا تُبطل" in (early.error or "")
    approved = interface.approve(awaiting.approval_id, approver="مدير")
    assert approved.status is IntelligenceStatus.APPROVED  # لم يُبطل
    executed = interface.execute_approved(awaiting.approval_id)
    assert executed.status is IntelligenceStatus.COMPLETED
    assert len(core.calls) == 1                            # العمل نفّذ مرة


# ===============================================================
# الربط الحي (سجل العمل 0046): السلسلة الافتراضية من الإقلاع المعتمد
# ===============================================================

def test_default_interface_boots_live_registry():
    """الواجهة الافتراضية ترى القدرات المسجلة فعلاً — لا سجلاً فارغاً
    منسوخاً بجانب الإقلاع (كانت السلسلة الافتراضية تبني سجلات خاوية
    فلا يرى المحلل شيئاً في عملية جديدة)."""
    interface = IntelligenceInterface()
    registry = getattr(interface._capability_resolver, "capability_registry", None)
    assert registry is not None
    names = [c.name for c in registry.list_all()]
    assert len(names) > 0                       # سجل حي لا فارغ
    # القدرات الفعلية التي يحمّلها Bootstrapper من capabilities/
    assert "RepositoryAnalysis" in names
    assert "RepositoryProcessingPipeline" in names
    # الإقلاع نفسه جاهز
    assert interface._kernel_runtime is not None
    assert interface._kernel_runtime.ready is True


def test_resolution_and_execution_use_same_live_registry():
    """الحل والتنفيذ يستخدمان السجل الحي نفسه — كائناً واحداً لا نسختين."""
    interface = IntelligenceInterface()
    pipeline = getattr(getattr(interface._mission_engine, "executor", None),
                       "pipeline", None)
    assert pipeline is not None
    resolver_registry = interface._capability_resolver.capability_registry
    pipeline_registry = pipeline.capability_resolver.capability_registry
    runtime_registry = interface._kernel_runtime.capability_registry
    assert resolver_registry is pipeline_registry
    assert resolver_registry is runtime_registry


def test_real_mission_through_live_core(tmp_path):
    """مهمة حقيقية تمر عبر النواة الحية والسجل الحي — لا عبر نواة زائفة:
    تحليل مستودع git حقيقي محلي بقدرة مسجلة فعلاً، والنتيجة DNA فعلي."""
    import subprocess
    repo = tmp_path / "liverepo"
    _write_repo(repo, {
        "app.py": "import json\nprint('x')\n",
        "requirements.txt": "flask>=2.0\n",
        "README.md": "# live\n",
    })
    subprocess.run(["git", "init", "-q"], cwd=str(repo), check=True)
    subprocess.run(["git", "add", "-A"], cwd=str(repo), check=True,
                   env={**os.environ, "GIT_AUTHOR_NAME": "t",
                        "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
                        "GIT_COMMITTER_EMAIL": "t@t"})
    subprocess.run(["git", "commit", "-qm", "init"], cwd=str(repo), check=True,
                   env={**os.environ, "GIT_AUTHOR_NAME": "t",
                        "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
                        "GIT_COMMITTER_EMAIL": "t@t"})
    interface = IntelligenceInterface()
    result = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.INSTANT,
        mission={"name": "تحليل حي",
                 "capability": "RepositoryAnalysis",
                 "parameters": {"url": str(repo)}}))
    assert result.status is IntelligenceStatus.COMPLETED, result.error
    dna = result.result
    # مخرج فعلي من قدرة إنتاجية حقيقية — ليس قيمة زائفة
    assert dna is not None
    name = dna.get("name") if isinstance(dna, dict) else getattr(dna, "name", None)
    assert name == "liverepo"
    # المهمة سُجلت في سجل التنفيذات القائم (المالك: rt.missions)
    assert len(interface._kernel_runtime.missions) >= 1
    recorded = interface._kernel_runtime.missions[-1]
    assert recorded.state.value == "completed"
    assert recorded.duration_ms > 0          # المنفذ قاس المدة فعلاً


def test_boot_failure_is_reported_not_ready(tmp_path):
    """فشل الإقلاع يُبلَّغ باستثناء صريح — لا واجهة \"جاهزة\" فوق إقلاع فاشل."""
    empty = tmp_path / "empty_boot"
    empty.mkdir()
    with pytest.raises(RuntimeError):
        IntelligenceInterface._boot_live_runtime(base_path=str(empty))


# ===============================================================
# تفسير النية (سجل العمل 0047): معجم ثنائي معلن + إيفاء مُثبت بالمخرجات
# ===============================================================
from intelligence import intent as _intent  # noqa: E402
from intelligence import interface as _iface_module  # noqa: E402

_LIVE_REGISTRY_NAMES = [
    "RepositoryAnalysis", "RepositoryDNAGeneration", "RepositoryProcessingPipeline",
    "SecurityScan", "LicenseAnalysis", "ConfigurationAnalysis",
    "DocumentationAnalysis", "InfrastructureAnalysis", "CapabilityGenome",
    "EngineeringKnowledgeExtraction",
]


def test_intent_acceptance_example_tie_is_named_ambiguity():
    """مثال القبول: طلب الأطر والاعتماديات واللغات له ثلاثة مرشحين حقيقيين
    متكافئين (RA/RDNG/RPP) — تعادل مسمّى لا اختيار بلا تعليل في Instant
    (المقارنة المعللة مسار engineer)."""
    text = ("أريد فحص مستودع https://github.com/psf/requests والكشف عن "
            "أطره واعتمادياته ولغاته")
    interpretation = _intent.interpret(text)
    # المفاهيم مشتقة من نص المستخدم (لا من قدرة مختارة — لا تحقق دائري)
    assert set(interpretation.required_concepts) == {
        "frameworks", "dependencies", "languages", "repository-analysis"}
    assert interpretation.artifacts["url"] == "https://github.com/psf/requests"
    mission, error = _intent.build_mission(interpretation, _LIVE_REGISTRY_NAMES)
    assert mission is None
    assert "تعادل" in error
    # المرشحان المُوفِيان فعلاً مسمّيان في الخطأ — RDNG ليس بينهما: مخرجه
    # dict بلا dependencies (تأسيس مُختبر بالقيم الفعلية في 0050)
    for cap in ("RepositoryAnalysis", "RepositoryProcessingPipeline"):
        assert cap in error
    assert "RepositoryDNAGeneration" not in error


def test_intent_dedicated_fulfillment_beats_incidental():
    """رخصة المستودع: LicenseAnalysis (مخرجها كله المفهوم) تسبق
    RepositoryAnalysis (يحملها حقلاً بين حقول DNA) — ترتيب إيفاء معلن."""
    interpretation = _intent.interpret(
        "افحص رخصة مستودع https://github.com/psf/requests")
    mission, error = _intent.build_mission(interpretation, _LIVE_REGISTRY_NAMES)
    assert error is None
    assert mission["capability"] == "LicenseAnalysis"
    assert mission["parameters"] == {"url": "https://github.com/psf/requests"}
    # المعاملات المستخرجة نصياً فقط — لا تخمين فرع ولا عمق
    assert set(mission["parameters"]) == {"url"}


def test_intent_negation_excludes_concept_and_changes_outcome():
    """النفي يستبعد المفهوم من المطلوب — ويغير النتيجة: بلا نفي لا مُوفٍ
    (أمن + رخص لا تحققهما قدرة واحدة معاً)، وبالنفي يفوز المُوفّي المتبقي."""
    both = _intent.interpret("افحص رخص وأمن المستودع /tmp/r")
    assert set(both.required_concepts) >= {"license", "security"}
    mission, error = _intent.build_mission(both, _LIVE_REGISTRY_NAMES)
    assert mission is None and "لا قدرة مسجلة تحقق" in error
    negated = _intent.interpret("افحص رخص المستودع /tmp/r بدون أمن")
    assert "security" in negated.negated_concepts
    assert "security" not in negated.required_concepts
    mission, error = _intent.build_mission(negated, _LIVE_REGISTRY_NAMES)
    assert mission is not None and mission["capability"] == "LicenseAnalysis"


def test_intent_interrogative_is_question_not_execution_order():
    """السؤال لا يُعامل كأمر تنفيذ — فشل مسمّى لا تنفيذ."""
    interpretation = _intent.interpret("هل يمكنك تحليل هذا المستودع؟")
    assert interpretation.interrogative is True
    mission, error = _intent.build_mission(interpretation, _LIVE_REGISTRY_NAMES)
    assert mission is None and "استفهامي" in error


def test_intent_missing_required_input_is_named_gap():
    """المرشح يحتاج مصدر مستودع ولم يُذكر — فجوة مسماة لا اختلاق معامل."""
    interpretation = _intent.interpret("افحص أمن المستودع")
    mission, error = _intent.build_mission(interpretation, _LIVE_REGISTRY_NAMES)
    assert mission is None
    assert "المدخل المطلوب غائب" in error and "SecurityScan" in error


def test_intent_fulfillment_table_grounded_in_code():
    """تأسيس جدول الإيفاء: الحقول المزعومة موجودة فعلاً في عقد المخرج
    (RepositoryDNA) — لا انجراف صامت بين الجدول والكود."""
    from dataclasses import fields
    from contracts import RepositoryDNA   # عقد المخرج الفعلي
    dna_fields = {f.name for f in fields(RepositoryDNA)}
    for claimed in ("frameworks", "dependencies", "languages", "license",
                    "config_files"):
        assert claimed in dna_fields, claimed
    # كل قدرة في الجدول موجودة في السجل الحي أو مسماة صراحة
    for concept, caps in _intent.FULFILLMENT.items():
        for cap in caps:
            assert cap in _LIVE_REGISTRY_NAMES, (concept, cap)


def test_intent_rpp_fulfillment_grounded_by_execution(tmp_path):
    """تأسيس إيفاء RPP بالنتيجة الفعلية: تشغيله على مستودع حقيقي صغير
    يُخرج حقائق languages/frameworks في سمات uro — الإثبات نتيجة لا وصف."""
    import subprocess
    repo = tmp_path / "rppground"
    _write_repo(repo, {"app.py": "import json\n", "requirements.txt": "flask>=2\n"})
    subprocess.run(["git", "init", "-q"], cwd=str(repo), check=True)
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    subprocess.run(["git", "add", "-A"], cwd=str(repo), check=True, env=env)
    subprocess.run(["git", "commit", "-qm", "i"], cwd=str(repo), check=True, env=env)
    from capabilities.rpp import RepositoryProcessingPipelineCapability
    outcome = RepositoryProcessingPipelineCapability().execute(
        {"repo_path": str(repo)})
    uro = outcome["universal_repository_object"]
    # المفاهيم الثلاثة حقول عُليا في uro — كما أثبت التنفيذ الفعلي
    assert uro["all_languages"]          # لغات مكتشفة فعلاً
    assert "frameworks" in uro and "dependencies" in uro and "all_languages" in uro


def test_instant_natural_text_runs_through_live_interface(tmp_path):
    """المسار الحي الكامل للطلب الطبيعي: نص عربي → تفسير → مهمة → تنفيذ
    عبر النواة الحية، والفجوة intent-interpretation مغلقة للمسار المفسر."""
    import subprocess
    repo = tmp_path / "natrepo"
    _write_repo(repo, {"app.py": "import json\n", "requirements.txt": "flask>=2\n"})
    subprocess.run(["git", "init", "-q"], cwd=str(repo), check=True)
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    subprocess.run(["git", "add", "-A"], cwd=str(repo), check=True, env=env)
    subprocess.run(["git", "commit", "-qm", "i"], cwd=str(repo), check=True, env=env)
    interface = IntelligenceInterface()
    result = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.INSTANT,
        natural_text=f"افحص أمن المستودع {repo}"))
    assert result.status is IntelligenceStatus.COMPLETED, result.error
    assert isinstance(result.result, dict) and result.result   # تقرير فعلي
    # الفجوة أُغلقت للمسار المفسر — لا تُرد فجوة آلية غاب مسبباها
    assert "intent-interpretation" not in result.gaps
    # سُجلت في سجل التنفيذات القائم بمدة مقيسة
    recorded = interface._kernel_runtime.missions[-1]
    assert recorded.state.value == "completed" and recorded.duration_ms > 0


def test_instant_natural_text_interrogative_fails_named(tmp_path):
    interface = IntelligenceInterface()
    result = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.INSTANT,
        natural_text="هل يمكنك تحليل هذا المستودع؟"))
    assert result.status is IntelligenceStatus.FAILED
    assert "استفهامي" in (result.error or "")
    assert "intent-interpretation" in result.gaps


# ===============================================================
# مسار القبول الحي لمثال القبول (سجل العمل 0048): طلب طبيعي ←
# متطلبات قبل الاختيار ← بدائل تقارن بدليل القرار ← خطة مشتقة ←
# اعتماد ← تنفيذ واحد — والقياس يغلق فجوة التكلفة في الطلب التالي
# ===============================================================

def _natrepo(tmp_path, name="natrepo"):
    import subprocess
    repo = tmp_path / name
    _write_repo(repo, {"app.py": "import json\nprint('x')\n",
                      "requirements.txt": "flask>=2.0\n",
                      "README.md": "# live\n"})
    subprocess.run(["git", "init", "-q"], cwd=str(repo), check=True)
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    subprocess.run(["git", "add", "-A"], cwd=str(repo), check=True, env=env)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=str(repo), check=True,
                   env=env)
    return repo


def test_engineer_natural_text_acceptance_path(tmp_path):
    """مثال القبول كاملاً: نص عربي طبيعي (أطر/اعتماديات/لغات + مستودع)
    → متطلبات مشتقة قبل الاختيار → بدائل الإيفاء الثلاثة تقارن بدليل
    القرار القائم → خطة بمكونات مشتقة → اعتماد → تنفيذ واحد فعلي."""
    repo = _natrepo(tmp_path)
    interface = IntelligenceInterface()
    text = f"أريد فحص مستودع {repo} والكشف عن أطره واعتمادياته ولغاته"
    result = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.ENGINEER, natural_text=text))
    # خطة معروضة بانتظار الاعتماد — صفر تنفيذ قبل الإجازة
    assert result.status is IntelligenceStatus.AWAITING_APPROVAL, result.error
    assert len(interface._kernel_runtime.missions) == 0   # لا تنفيذ قبل الاعتماد
    ep = result.engineering_plan
    assert ep is not None
    # 1) المتطلبات مشتقة من نص المستخدم قبل الاختيار — لا من قدرة
    req_refs = [r["ref"] for r in ep["requirements"]]
    assert "natural_text" in req_refs
    assert any(r.startswith("intent.required.frameworks") for r in req_refs)
    assert all(r.get("source") != "caller-provided" for r in ep["requirements"])
    # 2) البدائل: مرشحو الإيفاء الثلاثة بإثبات حوامل المخرجات + المقارنة
    assert ep["alternatives"]["kind"] == "design-alternatives-compared"
    names = {c["name"] for c in ep["alternatives"]["candidates"]}
    # المُوفِيان الفعليان للمفاهيم الأربعة (RDNG مخرجه dict بلا dependencies)
    assert names == {"RepositoryAnalysis", "RepositoryProcessingPipeline"}
    ra_row = next(c for c in ep["alternatives"]["candidates"]
                 if c["name"] == "RepositoryAnalysis")
    assert "RepositoryDNA.frameworks" in ra_row["fulfillment_evidence"]["frameworks"]
    assert ep["alternatives"]["selection"]["selected"] in names
    # 3) المخاطر مشتقة بأسانيد (احتمالية غير معلومة — لا تُختلق)
    assert ep["risks"], "المخاطر يجب أن تشتق للمسار المفسر"
    for risk in ep["risks"]:
        assert risk["evidence"] and risk["impact"] and risk["probability"] is None
    # 4) المعمارية: مقترح مشتق من المتطلبات والعقد — بوسم مقترح
    assert ep["architecture_design"]["kind"] == "proposal"
    assert ep["architecture_design"]["components"]
    # 5) التكلفة: معلنة حرفياً أول مرة (لا تاريخ) — الفجوة مسماة صادقة
    assert ep["cost"]["source"] == "declared-literal"
    # 6) الفجوات: ما اشتُق يُغلق وما لا قياس له يبقى
    assert "engineering-plan-requirements-analysis" not in result.gaps
    assert "engineering-plan-design-alternatives" not in result.gaps
    assert "engineering-plan-risks" not in result.gaps
    assert "engineering-plan-architecture" not in result.gaps
    assert "engineering-plan-cost-estimate" in result.gaps   # لا قياس بعد
    assert "intent-interpretation" not in result.gaps
    # 7) عدّاد استدعاء الحارس (سجل العمل 0051): صفر قبل الاعتماد،
    # وتنفيذ واحد فقط بعده — مثال القبول يحسب الاستدعاءات الفعلية
    guard = interface._core_wrapper
    assert guard.invocations == 0
    # 8) المقارنة تعادل إيفاء حقيقي بسياسة معلنة وقاعدة اختيار معلنة —
    # لا أفضلية من عدد التبعيات؛ والمفاضلات التصميمية معروضة لكل بديل
    assert ep["alternatives"]["selection"]["policy_id"] == \
        "design-alternatives-fulfillment-tie"
    for candidate_row in ep["alternatives"]["candidates"]:
        assert candidate_row["design_tradeoffs"], candidate_row["name"]
    # التعادل حقيقي بالدرجات الفعلية لا بالادعاء: كل المرشحين درجتهم
    # متساوية، وقاعدة كسر التعادل معلنة من السياسة
    evals = [c["evaluation"] for c in ep["alternatives"]["candidates"]]
    assert len(evals) >= 2
    assert all(e["score"] == evals[0]["score"] for e in evals)
    assert ep["alternatives"]["selection"]["tie_break"] == \
        "stable-registration-order"
    # ---- الاعتماد ثم التنفيذ مرة واحدة ----
    approved = interface.approve(result.approval_id, "المعتمِد")
    assert approved.status is IntelligenceStatus.APPROVED
    assert guard.invocations == 0               # الاعتماد وحده لا يستدعي
    executed = interface.execute_approved(result.approval_id)
    assert executed.status is IntelligenceStatus.COMPLETED, executed.error
    assert executed.result is not None          # مخرج فعلي (DNA أو uro)
    assert guard.invocations == 1               # تنفيذ واحد فقط
    # التنفيذ سُجل في rt.missions (المالك) بإسناد القدرة — لا نسخة موازية
    assert len(interface._kernel_runtime.missions) == 1
    recorded = interface._kernel_runtime.missions[-1]
    attribution = interface._mission_attribution[recorded.mission_id]
    assert attribution["capability"] == ep["alternatives"]["selection"]["selected"]
    assert recorded.state.value == "completed" and recorded.duration_ms > 0


def test_engineer_natural_text_second_request_closes_cost_gap(tmp_path):
    """بعد تنفيذ مقيس، الطلب الثاني لنفس الهدف تُغلق فجوة التكلفة بقياس
    فعلي (وسائط وعينة مدى ملحوظ) — لا يعود معلناً حرفياً."""
    repo = _natrepo(tmp_path, "costrepo")
    interface = IntelligenceInterface()
    text = f"افحص أمن المستودع {repo}"        # SecurityScan — مرشح وحيد
    first = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.ENGINEER, natural_text=text))
    assert first.status is IntelligenceStatus.AWAITING_APPROVAL
    assert first.engineering_plan["cost"]["source"] == "declared-literal"
    assert "engineering-plan-cost-estimate" in first.gaps
    assert interface.approve(first.approval_id, "م").status is IntelligenceStatus.APPROVED
    assert interface.execute_approved(
        first.approval_id).status is IntelligenceStatus.COMPLETED
    second = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.ENGINEER, natural_text=text))
    assert second.status is IntelligenceStatus.AWAITING_APPROVAL
    cost = second.engineering_plan["cost"]
    assert cost["source"] == "measured"
    assert cost["n"] >= 1 and cost["median_ms"] > 0
    assert cost["observed_min_ms"] <= cost["median_ms"] <= cost["observed_max_ms"]
    assert "engineering-plan-cost-estimate" not in second.gaps


def test_engineer_natural_text_interrogative_and_guards(tmp_path):
    interface = IntelligenceInterface()
    result = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.ENGINEER,
        natural_text="هل يمكنك تحليل هذا المستودع؟"))
    assert result.status is IntelligenceStatus.FAILED
    assert "استفهامي" in (result.error or "")
    missing = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.ENGINEER, natural_text="افحص أمن المستودع"))
    assert missing.status is IntelligenceStatus.FAILED
    assert "المدخل المطلوب غائب" in (missing.error or "")


# ===============================================================
# البحث متعدد المصادر (سجل العمل 0049): إثبات لكل مصدر لكل مرشح —
# لا اتحاد، والتعارض ادعاءان متنافسان، والغياب مسمّى، والسؤال يقود الجمع
# ===============================================================

def test_research_multi_source_per_source_evidence_no_merge(tmp_path):
    """مصدران بمكدسين مختلفين: كل مصدر بدليله ومقارنته — لا اتحاد؛ والتعارض
    ادعاءان متنافسان على الموضوع والسياق نفسه (عرض تبادلي)؛ وفجوة اتساع
    البحث مغلقة (البحث متعدد المصادر قائم)."""
    py_repo = tmp_path / "pyrepo"
    _write_repo(py_repo, {"a.py": "x = 1\n"})
    js_repo = tmp_path / "jsrepo"
    _write_repo(js_repo, {"a.js": "let x = 1;\n"})
    interface = IntelligenceInterface()
    candidates = [
        EngineeringCandidate(id="py", name="PyApp", technologies=["Python"]),
        EngineeringCandidate(id="js", name="JsApp", technologies=["JavaScript"]),
    ]
    result = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.RESEARCH,
        question="أي مرشح يناسب هذه المستودعات؟",
        evidence_paths=[str(py_repo), str(js_repo)],
        candidates=candidates))
    assert result.status is IntelligenceStatus.RECOMMENDATION_UNAVAILABLE
    # لا توصية مدمجة — المصدران يختلفان (خلط المواءمة ملاحظة لا دمج)
    snapshot = result.evidence_snapshot
    assert len(snapshot["sources"]) == 2
    for source in snapshot["sources"]:
        assert source["comparison"].policy_id == "repository-stack-alignment"
    # كل مصدر بدليله: مقارنة الأول ترشح py والثاني js — على حدة
    by_path = {s["path"]: s for s in snapshot["sources"]}
    assert by_path[str(py_repo)]["comparison"].best.candidate_id == "py"
    assert by_path[str(js_repo)]["comparison"].best.candidate_id == "js"
    # اختلاف المستودعات اختلاف موثق لا تعارض: Python مكتشف في الأول دون
    # الثاني — ملاحظتان لكل مصدر (غياب الدليل ليس إثبات عدم)، والتعارض
    # الحقيقي (موضوع وسياق واحد) فارغ معلل
    differences = snapshot["cross_source"]["differences"]
    subjects = {d["subject"] for d in differences}
    assert "stack: python" in subjects
    py_diff = next(d for d in differences if d["subject"] == "stack: python")
    assert len(py_diff["observations"]) == 2         # مصدر لكل ملاحظة
    assert snapshot["cross_source"]["conflicts"] == []
    assert "اختلاف موثق لا تعارض" in snapshot["cross_source"]["note"]
    # فجوة اتساع البحث مغلقة — البحث متعدد المصادر قائم
    assert "research-breadth" not in result.gaps


def test_research_multi_source_missing_source_is_named(tmp_path):
    """غياب دليل مصدر مسمّى — لا نتيجة مزعومة ولا إسقاط صامت: المصدر
    الفاشل يُسمّى في الخطأ، والمصدر السليم تبقى أدلته معروضة."""
    good = tmp_path / "good"
    _write_repo(good, {"a.py": "x = 1\n"})
    interface = IntelligenceInterface()
    result = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.RESEARCH,
        evidence_paths=[str(good), str(tmp_path / "nonexistent")],
        candidates=[EngineeringCandidate(id="py", name="PyApp",
                                         technologies=["Python"])]))
    assert result.status is IntelligenceStatus.FAILED
    assert "nonexistent" in (result.error or "")          # مسمّى بالاسم
    assert "غياب دليل مصدر" in (result.error or "")
    # أدلة المصدر السليم محفوظة (لا إسقاط صامت)
    good_entry = next(s for s in result.evidence_snapshot["sources"]
                     if s["path"] == str(good))
    assert good_entry["comparison"].best.candidate_id == "py"


def test_research_question_drives_gathered_evidence(tmp_path):
    """السؤال يقود جمع الأدلة: سؤال الأطر يجمع فئات الأطر فقط، وسؤال اللغات
    يجمع اللغات فقط — تغيير السؤال يغيّر الأدلة المجمعة (لا قصّ صامت:
    المستبعد يُسمّى)."""
    repo = tmp_path / "qrepo"
    _write_repo(repo, {"a.py": "import flask\n", "requirements.txt": "flask\n"})
    interface = IntelligenceInterface()
    on_frameworks = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.RESEARCH, evidence_path=str(repo),
        question="ما أطر هذا المستودع؟"))
    on_languages = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.RESEARCH, evidence_path=str(repo),
        question="ما لغات هذا المستودع؟"))
    fw = on_frameworks.evidence_snapshot
    lg = on_languages.evidence_snapshot
    assert "frameworks" in fw["question_concepts"]
    assert "languages" in lg["question_concepts"]
    # الفئات المجمعة تختلف بتغير السؤال
    assert "frameworks" in fw["fact_categories_gathered"]
    assert fw["fact_categories_gathered"] != lg["fact_categories_gathered"]
    assert "languages" in lg["fact_categories_gathered"]
    # الاستبعاد مسمّى لا صامت
    assert "languages" in fw["detected"]["excluded_by_question"]
    assert "frameworks" in lg["detected"]["excluded_by_question"]


def test_research_multi_source_agreement_is_observation_not_merge(tmp_path):
    """مصدران متفقان: الحالة مكتملة والاتفاق ملاحظة معروضة — كل مصدر
    بدليله ومقارنته (لا اتحاد أدلة ولا توصية مدمجة فوق المصادر)."""
    repo1 = tmp_path / "r1"
    _write_repo(repo1, {"a.py": "x = 1\n"})
    repo2 = tmp_path / "r2"
    _write_repo(repo2, {"b.py": "y = 2\n"})
    interface = IntelligenceInterface()
    candidates = [EngineeringCandidate(id="py", name="PyApp",
                                       technologies=["Python"])]
    result = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.RESEARCH,
        evidence_paths=[str(repo1), str(repo2)],
        candidates=candidates))
    assert result.status is IntelligenceStatus.COMPLETED
    cross = result.evidence_snapshot["cross_source"]
    assert {"subject": "stack: python",
            "claim": "مكتشف في كل المصادر"} in cross["agreements"]
    # ومع ذلك: النتيجة بلا comparison مدمجة — كل مقارنة داخل مصدرها
    assert result.comparison is None


# ===============================================================
# اختبارات المراجعة النهائية (سجل العمل 0050): النفي صفر تنفيذ،
# وعدّاد الاستدعاءات، والسؤال يقود المقارنة نفسها، وتعديل كل مكوّن مشتق
# ===============================================================

def test_verbal_negation_is_zero_execution(tmp_path):
    """«لا أريد فحص أمن المستودع» — نفي فعلي نطاقه الجملة: لا تنفيذ إطلاقاً
    (صفر مهمام في rt.missions وصفر استدعاء نواة عبر الحارس)."""
    repo = _natrepo(tmp_path, "negrepo")
    interface = IntelligenceInterface()
    result = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.INSTANT,
        natural_text=f"لا أريد فحص أمن المستودع {repo}"))
    assert result.status is IntelligenceStatus.FAILED
    assert "نفي فعلي" in (result.error or "")
    assert interface._kernel_runtime.missions == []      # صفر تنفيذ
    assert interface._core_wrapper.invocations == 0       # صفر استدعاء نواة


def test_engineer_natural_text_call_counter_single_execution(tmp_path):
    """عدّاد الاستدعاءات الإنتاجية (عبر الحارس): صفر قبل الاعتماد، وصفر بعد
    الاعتماد وحده، وواحد بعد التنفيذ، ويبقى واحداً بعد محاولة الإعادة
    (الإعادة تُرفض — إجازة تُستهلك مرة)."""
    repo = _natrepo(tmp_path, "countrepo")
    interface = IntelligenceInterface()
    result = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.ENGINEER,
        natural_text=f"افحص أمن المستودع {repo}"))
    assert result.status is IntelligenceStatus.AWAITING_APPROVAL
    guard = interface._core_wrapper
    assert guard.invocations == 0                      # قبل الاعتماد: صفر
    approved = interface.approve(result.approval_id, "م")
    assert approved.status is IntelligenceStatus.APPROVED
    assert guard.invocations == 0                      # الاعتماد وحده: صفر
    executed = interface.execute_approved(result.approval_id)
    assert executed.status is IntelligenceStatus.COMPLETED
    assert guard.invocations == 1                      # تنفيذ واحد فقط
    again = interface.execute_approved(result.approval_id)
    assert again.status is IntelligenceStatus.FAILED     # الإعادة مرفوضة
    assert guard.invocations == 1                      # ما زال واحداً


def test_engineer_natural_text_every_derived_component_mutation_rejected(tmp_path):
    """تعديل كل مكوّن مشتق (متطلبات/بدائل/مخاطر/تكلفة/معمارية) بعد العرض
    يُرفض عند بوابتي الاعتماد والتنفيذ — بصمة عميقة لا تعرف الاستثناءات."""
    repo = _natrepo(tmp_path, "mutrepo")
    interface = IntelligenceInterface()
    base = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.ENGINEER,
        natural_text=f"افحص أمن المستودع {repo}"))
    assert base.status is IntelligenceStatus.AWAITING_APPROVAL
    ep = base.engineering_plan

    # بوابتا الاعتماد والتنفيذ: تعديل كل مكوّن من المكونات الخمسة — يُرفض
    # في البوابتين معاً (سجل العمل 0051 — تصحيح 0050: الاعتماد كان يختبر
    # المخاطر فقط) وبصفر استدعاء نواة في كل رفض
    mutations = (
        ("requirements", lambda e: e["requirements"].append(
            {"ref": "x", "value": "مزيف"})),
        ("alternatives", lambda e: e["alternatives"]["selection"].update(
            {"selected": "مزيف"})),
        ("risks", lambda e: e["risks"].append({"risk": "مزيف"})),
        ("cost", lambda e: e["cost"].update({"median_ms": 1})),
        ("architecture", lambda e: e["architecture_design"].update(
            {"kind": "fabricated"})))
    for component, mutate in mutations:
        # بوابة الاعتماد: تعديل المكوّن قبل الاعتماد — يُرفض
        fresh = IntelligenceInterface()
        r = fresh.run(IntelligenceRequest(
            mode=IntelligenceMode.ENGINEER,
            natural_text=f"افحص أمن المستودع {repo}"))
        mutate(r.engineering_plan)
        rejected = fresh.approve(r.approval_id, "م")
        assert rejected.status is IntelligenceStatus.FAILED, component
        assert "تغيّر" in (rejected.error or ""), component
        assert fresh._core_wrapper.invocations == 0, component
        # بوابة التنفيذ: تعديل المكوّن بعد اعتماد سليم — يُرفض
        fresh2 = IntelligenceInterface()
        r2 = fresh2.run(IntelligenceRequest(
            mode=IntelligenceMode.ENGINEER,
            natural_text=f"افحص أمن المستودع {repo}"))
        assert fresh2.approve(r2.approval_id, "م").status is \
            IntelligenceStatus.APPROVED
        mutate(r2.engineering_plan)
        rejected_exec = fresh2.execute_approved(r2.approval_id)
        assert rejected_exec.status is IntelligenceStatus.FAILED, component
        assert "اختلاف المحتوى" in (rejected_exec.error or ""), component
        assert fresh2._core_wrapper.invocations == 0, component


def test_research_question_drives_comparison_result(tmp_path):
    """السؤال يقود المقارنة نفسها (لا العرض فقط): مستودع بPython وFlask —
    سؤال الأطر يجعل مرشح Flask يتقدم، وسؤال اللغات يجعل مرشح Python يتقدم:
    تغيير السؤال يغيّر أدلة المقارنة ونتيجتها حيث توجد قرينة مميزة."""
    repo = tmp_path / "mixrepo"
    _write_repo(repo, {"app.py": "import flask\n", "requirements.txt": "flask>=2\n"})
    interface = IntelligenceInterface()
    candidates = [
        EngineeringCandidate(id="lang", name="LangApp",
                             technologies=["Python"]),
        EngineeringCandidate(id="fw", name="FwApp", technologies=["Flask"]),
    ]
    on_fw = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.RESEARCH, evidence_path=str(repo),
        question="ما أطر هذا المستودع؟", candidates=candidates))
    on_lang = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.RESEARCH, evidence_path=str(repo),
        question="ما لغات هذا المستودع؟", candidates=candidates))
    assert on_fw.status is IntelligenceStatus.COMPLETED
    assert on_lang.status is IntelligenceStatus.COMPLETED
    assert on_fw.comparison.best.candidate_id == "fw"     # قرينة الأطر
    assert on_lang.comparison.best.candidate_id == "lang"  # قرينة اللغات
    # الحزمة المستخدمة في كل مقارنة موسومة في اللقطة — الاستبعاد معلن
    assert "flask" in on_fw.evidence_snapshot["detected_stack"]
    assert "flask" not in on_lang.evidence_snapshot["detected_stack"]
    assert "python" in on_lang.evidence_snapshot["detected_stack"]


def test_intent_fulfillment_actual_values_for_each_alternative(tmp_path):
    """تأسيس الإيفاء بالقيم الفعلية لا بوجود المفاتيح: كل مُوفٍ في مثال
    القبول يُنفَّذ على مستودع معلوم المحتوى وتُفحص قيم الأطر والاعتماديات
    واللغات وأدلتها — RDNG لا يُوفّي dependencies (dict بلا المفتاح)."""
    import subprocess
    repo = tmp_path / "fulrepo"
    _write_repo(repo, {"app.py": "import json\nimport flask\n",
                      "requirements.txt": "flask>=2.0\nrequests\n"})
    subprocess.run(["git", "init", "-q"], cwd=str(repo), check=True)
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    subprocess.run(["git", "add", "-A"], cwd=str(repo), check=True, env=env)
    subprocess.run(["git", "commit", "-qm", "i"], cwd=str(repo), check=True, env=env)
    interface = IntelligenceInterface()
    registry = interface._capability_resolver.capability_registry
    registered = {c.name: c for c in registry.list_all()}
    # RA: RepositoryDNA فعلي بقيم حقيقية
    dna = registered["RepositoryAnalysis"].execute({"url": str(repo)})
    assert "Flask" in dna.frameworks and "Python" in dna.languages
    assert "flask" in dna.dependencies and "requests" in dna.dependencies
    # RPP: uro بقيم حقيقية
    rpp = registered["RepositoryProcessingPipeline"].execute(
        {"repo_path": str(repo)})
    uro = rpp["universal_repository_object"]
    assert "Flask" in uro["frameworks"] and "Python" in uro["all_languages"]
    assert {"flask", "requests"} <= {d["name"] for d in uro["dependencies"]}
    # RDNG: dict بلا dependencies — لا يُوفّي المفهوم (تأسيس جدول الإيفاء)
    rdng = registered["RepositoryDNAGeneration"].execute({"url": str(repo)})
    assert "Flask" in rdng["frameworks"] and "Python" in rdng["languages"]
    assert "dependencies" not in rdng
    assert "RepositoryDNAGeneration" not in _intent.FULFILLMENT["dependencies"]


def test_instant_provider_selection_gap_closed_with_evidence(tmp_path):
    """فجوة knowledge-driven-provider-selection (محتوى 0050 مصحح 0051
    وإسناده صُحح 0053 — الاسم محفوظ G2): إغلاق 0050 كان بلا دليل؛
    الاختيار الحي بسياسات معلنة (ADR-0006) لا بقاعدة معرفة/خبرة —
    الفجوة مسماة بغيابها الصادق (أصلها تعليق التنفيذ الأصلي نفسه)؛
    نص قبول البند (ADR-0009) لا يتطلبها ولا يؤجلها صراحةً ولا يُدَّعى
    إسنادها لأي محرك بغير نص؛ سجل مزود معلل لا يثبت استهلاك مدخل معرفة
    فلا يغلقها — الفجوة باقية مسماة."""
    repo = _natrepo(tmp_path, "providrepo")
    interface = IntelligenceInterface()
    result = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.INSTANT,
        mission={"name": "تحليل", "capability": "RepositoryAnalysis",
                 "parameters": {"url": str(repo)}}))
    assert result.status is IntelligenceStatus.COMPLETED
    # الفجوة باقية بأمانة — المسار يفاضل بسياسات معلنة لا بمعرفة/خبرة
    assert "knowledge-driven-provider-selection" in result.gaps
    # سجل اختيار المزود معلل موجود في سجلات القرار (سياسات معلنة)
    provider_records = [r for r in (result.decision_records or [])
                       if getattr(r, "kind", "") == "provider"
                       or "provider" in str(getattr(r, "requested_name", ""))]
    assert provider_records or any(
        "provider" in str(r).lower() for r in (result.decision_records or []))


# ------------------------------------------------------------------ 0051 --
def test_negation_constraint_named_failure_zero_execution_instant(tmp_path):
    """القيد المنفي مُلزم (0051): «بدون فحص الأطر» والمختار (RA) يحمل
    frameworks في مخرجه وعقده لا يعلّم تعطيله — فشل مسمى وصفر تنفيذ
    وصفر استدعاء للحارس (لا تنفيذ صامت يتجاهل الاستثناء)."""
    repo = _natrepo(tmp_path, "negrepo")
    interface = IntelligenceInterface()
    result = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.INSTANT,
        natural_text="افحص رخصة واعتماديات ولغات المستودع " + str(repo)
                     + " بدون فحص الأطر"))
    assert result.status is IntelligenceStatus.FAILED
    assert "القيد المنفي" in (result.error or "")
    assert "frameworks" in (result.error or "")
    assert result.mission_id is None      # لا مهمة أُنشئت أو نُفذت
    # الحارس لم يُستدع أصلاً — لا تنفيذ صامت
    assert interface._core_wrapper.invocations == 0


def test_negation_constraint_named_failure_zero_execution_engineer(tmp_path):
    """القيد المنفي مُلزم في مسار Engineer أيضاً (0051): لا اعتماد ولا
    تنفيذ — فشل مسمى وصفر استدعاء للحارس."""
    repo = _natrepo(tmp_path, "negrepo2")
    interface = IntelligenceInterface()
    result = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.ENGINEER,
        natural_text="افحص رخصة واعتماديات ولغات المستودع " + str(repo)
                     + " بدون فحص الأطر"))
    assert result.status is IntelligenceStatus.FAILED
    assert "القيد المنفي" in (result.error or "")
    assert interface._core_wrapper.invocations == 0
    assert result.mission_id is None
    assert result.approval_id is None


def test_verbal_negation_zero_execution_engineer_mode(tmp_path):
    """النفي اللفظي («لا أريد فحص أمن») في مسار Engineer: لا اعتماد ولا
    تنفيذ — التوثيق يذكر الوضعين فيجب اختبار الوضعين (0051)."""
    interface = IntelligenceInterface()
    repo = _natrepo(tmp_path / "vn2dir", "vn2")
    result = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.ENGINEER,
        natural_text="لا أريد فحص أمن، حلل التبعيات للمستودع " + str(repo)))
    assert result.status is IntelligenceStatus.FAILED
    assert "نفي فعلي" in (result.error or "")
    assert interface._core_wrapper.invocations == 0


def test_instant_execution_does_not_close_engineer_cost_gap(tmp_path):
    """عينات التكلفة مفصولة (0051): تنفيذ instant لا يغلق فجوة تقدير تكلفة
    خطة engineer — العينة من وضع آخر فلا تُدمج في وسيط وضع مختلف؛ وتنفيذ
    engineer وحده يغلقها في الطلب التالي بشروط عينته (الوضع)."""
    repo = _natrepo(tmp_path, "costmode")
    interface = IntelligenceInterface()
    url = str(repo)
    instant = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.INSTANT,
        mission={"name": "فحص", "capability": "SecurityScan",
                 "parameters": {"url": url}}))
    assert instant.status is IntelligenceStatus.COMPLETED
    # عينة instant موجودة لكنها ليست من وضع engineer
    measured = interface._measured_executions("SecurityScan")
    assert all(e["mode"] == "instant" for e in measured)
    engineer = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.ENGINEER,
        natural_text="افحص أمن المستودع " + url))
    assert engineer.status is IntelligenceStatus.AWAITING_APPROVAL
    # العينة الوحيدة من وضع instant — لا تغلق فجوة تكلفة خطة engineer
    assert "engineering-plan-cost-estimate" in engineer.gaps
    assert engineer.engineering_plan["cost"]["source"] == "declared-literal"
    # تنفيذ engineer وحده يغلقها في الطلب التالي
    interface.approve(engineer.approval_id, approver="م")
    approved = interface.execute_approved(engineer.approval_id)
    assert approved.status is IntelligenceStatus.COMPLETED
    second = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.ENGINEER,
        natural_text="افحص أمن المستودع " + url))
    assert second.status is IntelligenceStatus.AWAITING_APPROVAL
    assert "engineering-plan-cost-estimate" not in second.gaps
    cost = second.engineering_plan["cost"]
    assert cost["source"] == "measured"
    # وسيط العينة من وضع engineer فقط — لا دمج وضعين في وسيط واحد
    assert cost["conditions"]["modes"] == ["engineer"]


def test_measured_cost_records_sample_conditions(tmp_path):
    """شروط العينة المعروضة فعلاً (0051): الوضع والمدخل (url) في سجل
    العينة — لا وسيط بلا شروطه."""
    interface = IntelligenceInterface()
    url = str(_natrepo(tmp_path, "condrepo"))
    result = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.ENGINEER,
        natural_text="افحص أمن المستودع " + url))
    assert result.status is IntelligenceStatus.AWAITING_APPROVAL
    interface.approve(result.approval_id, approver="م")
    interface.execute_approved(result.approval_id)
    again = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.ENGINEER,
        natural_text="افحص أمن المستودع " + url))
    cost = again.engineering_plan["cost"]
    assert cost["source"] == "measured"
    measured = cost.get("measured") or []
    conditions = cost.get("conditions") or (measured[0].get("conditions")
                                            if measured else {})
    assert cost["n"] >= 1
    assert conditions["modes"] == ["engineer"]
    assert url in conditions["inputs"]
    assert "parameters" in conditions or "inputs" in conditions


def test_cross_source_unverified_member_does_not_hide_verified_conflict():
    """عضو غير متحقق لا يخفي تعارض المتحققين (0058): ثلاثة سجلات للموضوع
    نفسه (المسار نفسه) بسياقات فعلية H وH وNone وسياق معلن H للجميع —
    تعارض الأولين المتحققين قائم، والثالثة محفوظة منفصلة بلا إبطال."""
    interface = IntelligenceInterface()
    head = "abc123def"
    sources = []
    for sid, actual in enumerate([head, head, None]):
        sources.append({
            "path": "/repos/x", "source_id": sid,
            "actual_context": actual,
            "detected_stack": ["flask"],
            "explicit_claims": {"flask": {
                "value": sid != 1,
                "evidence": f"دعوى المصدر {sid}",
                "context": head,
                "origin": "caller-provided"}}})
    cross = interface._cross_source_view(sources)
    assert len(cross["conflicts"]) == 1
    assert {c["source_id"] for c in cross["conflicts"][0]["claims"]} == {0, 1}
    # والثالثة محفوظة منفصلة (سياق معلن غير متحقق — لا مقارنة ولا إبطال)
    assert any("غير متحقق" in str(i.get("note", ""))
               for i in cross["incomparable_claims"])
    assert cross["caller_claims_contradictions"] == []


def test_research_context_unverified_when_file_changes_during_analysis(
        tmp_path, monkeypatch):
    """اللقطة المستقلة من المراجعة (0059 — تصحيح 0058؛ اسم الاختبار من
    0057 محفوظ حاكماً): تغيير ملف المصدر الأصلي عند دخول التحليل ثم
    استعادة بايتاته بعد قراءة المحلل وقبل عودته — المحلل يقرأ لقطة H
    المستقلة فعلاً فيصح الإسناد إليها (يُثبت المحتوى المقروء: flask
    الملتزم لا django التغيير)؛ ومصدر بلا git يُحلَّل حياً فيبقى سياقه
    غير متحقق دائماً (لا ترقية بفحوص حالة)."""
    repo = _natrepo(tmp_path / "tourepo", "tourepo")
    (repo / "app.py").write_text("import flask\n", encoding="utf-8")
    (repo / "requirements.txt").write_text("flask>=2\n", encoding="utf-8")
    import subprocess
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    subprocess.run(["git", "add", "-A"], cwd=str(repo), check=True, env=env)
    subprocess.run(["git", "commit", "-qm", "claims"], cwd=str(repo),
                   check=True, env=env)
    head = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                          capture_output=True, text=True, check=True
                          ).stdout.strip()
    original = IntelligenceInterface._analyze
    original_bytes = (repo / "requirements.txt").read_bytes()

    def _change_then_analyze(self, path):
        # تغيير ملف المصدر الأصلي (لا مسار اللقطة المحلَّلة) عند دخول
        # التحليل — ثم استعادة بايتاته بعد قراءة المحلل وقبل عودته (خدعة
        # الفحصين في 0058 لا تنفع هنا: المحلل يقرأ لقطة المراجعة، فلو قرأ
        # الحية لرأى django)
        (repo / "requirements.txt").write_text(
            "django>=4\n", encoding="utf-8")
        try:
            return original(self, path)
        finally:
            (repo / "requirements.txt").write_bytes(original_bytes)

    monkeypatch.setattr(
        IntelligenceInterface, "_analyze", _change_then_analyze)
    interface = IntelligenceInterface()
    result = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.RESEARCH,
        question="ما إطار هذا المستودع؟",
        evidence_paths=[str(repo), str(repo)],
        source_claims=[
            {"source_id": 0, "path": str(repo), "property": "flask",
             "value": True, "context": head,
             "evidence": "دعوى بسياق H مع تغيير أثناء التحليل"},
            {"source_id": 1, "path": str(repo), "property": "flask",
             "value": False, "context": head,
             "evidence": "أخرى بسياق H مع تغيير أثناء التحليل"},
        ]))
    cross = result.evidence_snapshot["cross_source"]
    # إثبات المحتوى المقروء: المحلل قرأ لقطة H (flask الملتزم) لا الحية
    # (django التغيير) — فيصح الإسناد إلى H والتعارض المُحقَّق معلن
    src0 = result.evidence_snapshot["sources"][0]
    assert "flask" in src0["detected_stack"]
    assert "django" not in src0["detected_stack"]
    assert "المراجعة" in str(src0["analysis_scope"])
    assert len(cross["conflicts"]) == 1
    assert {c["source_id"] for c in cross["conflicts"][0]["claims"]} == {0, 1}

    # والمصدر بلا git يُحلَّل حياً — سياقه غير متحقق دائماً مهما تغير
    live = tmp_path / "liverepo"
    live.mkdir()
    (live / "app.py").write_text("import flask\n", encoding="utf-8")
    (live / "requirements.txt").write_text("flask>=2\n", encoding="utf-8")
    live_result = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.RESEARCH,
        question="ما إطار هذا المستودع؟",
        evidence_paths=[str(live), str(live)],
        source_claims=[
            {"source_id": 0, "path": str(live), "property": "flask",
             "value": True, "context": "أي سياق",
             "evidence": "دعوى مصدر حي بلا git"},
            {"source_id": 1, "path": str(live), "property": "flask",
             "value": False, "context": "أي سياق",
             "evidence": "أخرى مصدر حي بلا git"},
        ]))
    cross_l = live_result.evidence_snapshot["cross_source"]
    assert cross_l["conflicts"] == []      # تحليل الشجرة الحية غير متحقق
    assert len(cross_l["caller_claims_contradictions"]) == 1
    assert "غير متحقق" in str(
        cross_l["caller_claims_contradictions"][0]["context"])


def test_cross_source_real_conflict_same_path_different_stacks():
    """آلية التعارض (0054 — تصحيح 0053): قوائم الكشف ليست ادعاءات حصرية —
    اختلافها اختلاف موثق دائماً؛ التعارض الوحيد المثبت: دعويان صريحتان
    متنافيتان عن الخاصية نفسها لمسار واحد (بقيمة كل دعوى ودليلها وهوية
    مصدرها)؛ والمصدر الصامت عن الخاصية لا يُسقط تعارض المدّعيين."""
    def _claim(value, evidence="", context="rev-abc"):
        return {"value": value, "evidence": evidence, "context": context}

    # كاشف (1): مكدسان مختلفان — اختلاف لا تعارض (لا حصرية في القوائم)
    e1 = {"path": "samer", "source_id": 0,
          "detected_stack": ["python", "flask"]}
    e2 = {"path": "samer", "source_id": 1,
          "detected_stack": ["python", "django"]}
    view = IntelligenceInterface()._cross_source_view([e1, e2])
    assert view["conflicts"] == []
    assert view["differences"] != []
    # كاشف (2): دعويان صريحتان متنافيتان (flask) بمسار واحد **بسياق
    # متحقق بدليل المصدر الفعلي** (actual_context للمصدرين = rev-9) —
    # تعارض بقيمة كل دعوى ودليلها وهوية مصدرها
    c1 = dict(e1, actual_context="rev-9",
              explicit_claims={"flask": _claim(
                  True, "بيان requirements.txt", context="rev-9")})
    c2 = dict(e2, actual_context="rev-9",
              explicit_claims={"flask": _claim(
                  False, "فحص يدوي للبيان", context="rev-9")})
    view_c = IntelligenceInterface()._cross_source_view([c1, c2])
    assert len(view_c["conflicts"]) == 1
    conflict = view_c["conflicts"][0]
    assert "flask" in conflict["subject"]
    assert "samer" in conflict["context"] and "rev-9" in conflict["context"]
    assert "متحقق بدليل المصدر" in conflict["context"]
    claims = conflict["claims"]
    assert {cl["source_id"] for cl in claims} == {0, 1}
    values = {cl["claim"] for cl in claims}
    assert values == {"أثبت", "أنكر صراحةً"}
    # دليل كل دعوى محفوظ
    evidences = {cl["evidence"] for cl in claims}
    assert "بيان requirements.txt" in evidences
    assert "فحص يدوي للبيان" in evidences
    # كاشف (3): مصدر ثالث صامت عن flask لا يُسقط تعارض المدّعيين
    silent = {"path": "samer", "source_id": 2,
              "detected_stack": ["python"]}
    view_s = IntelligenceInterface()._cross_source_view([c1, c2, silent])
    assert len(view_s["conflicts"]) == 1
    assert {cl["source_id"] for cl in view_s["conflicts"][0]["claims"]} == {0, 1}
    # كاشف (3-ب): سياقان مختلفان (مراجعة قديمة × جديدة) — مجموعتان
    # مستقلتان: لا تعارض مثبت والدعاوى محفوظة منفصلة (لا تُبطل إحداها
    # الأخرى)
    old_rev = dict(e1, actual_context="rev-7",
                  explicit_claims={"flask": _claim(
                      True, "بيان المراجعة القديمة", context="rev-7")})
    view_i = IntelligenceInterface()._cross_source_view([old_rev, c2])
    assert view_i["conflicts"] == []
    assert len(view_i["incomparable_claims"]) == 1
    assert "مجموعات منفصلة" in view_i["incomparable_claims"][0]["note"]
    # كاشف (3-ج): نصا سياق متساويان لكن غير متحققين بدليل المصدر —
    # تناقض دعاوى المرسل يُعرض منفصلاً ولا يُسمى تعارض مصادر
    u1 = dict(e1, actual_context=None,
              explicit_claims={"flask": _claim(
                  True, "دعوى بسياق معلن غير فعلي", context="rev-x")})
    u2 = dict(e2, actual_context=None,
              explicit_claims={"flask": _claim(
                  False, "أخرى بسياق معلن غير فعلي", context="rev-x")})
    view_u = IntelligenceInterface()._cross_source_view([u1, u2])
    assert view_u["conflicts"] == []
    assert len(view_u["caller_claims_contradictions"]) == 1
    assert "ليس إثبات تعارض مصادر" in \
        view_u["caller_claims_contradictions"][0]["note"]
    # كاشف (3-د): دعوى ثالثة عن مراجعة أخرى لا تُخفي تعارض المتحققين
    other_rev = dict(e1, actual_context="rev-8",
                     explicit_claims={"flask": _claim(
                         True, "دعوى عن مراجعة أخرى", context="rev-8")})
    view_o = IntelligenceInterface()._cross_source_view(
        [c1, c2, other_rev])
    assert len(view_o["conflicts"]) == 1   # تعارض rev-9 قائم
    # كاشف (3-هـ): سياق غائب فعلاً — تناقض دعاوى مرسل غير متحقق لا تعارض
    no_ctx_a = dict(e1, actual_context=None,
                    explicit_claims={"flask": _claim(
                        True, "دليل بلا سياق", context="")})
    no_ctx_b = dict(e2, actual_context=None,
                    explicit_claims={"flask": _claim(
                        False, "أخرى بلا سياق", context="")})
    view_n = IntelligenceInterface()._cross_source_view([no_ctx_a, no_ctx_b])
    assert view_n["conflicts"] == []
    assert len(view_n["caller_claims_contradictions"]) == 1
    # كاشف (4): ادعاءان متفقان (لا تنافي) — لا تعارض
    c3 = dict(e1, explicit_claims={"flask": _claim(True, "d")})
    view_a = IntelligenceInterface()._cross_source_view([c1, c3])
    assert view_a["conflicts"] == []
    # كاشف (5): مصادر مختلفة المسار — اختلاف موثق لا تعارض
    other = {"path": "other", "source_id": 4,
             "explicit_claims": {"flask": _claim(False, "d")},
             "detected_stack": ["python"]}
    view_o = IntelligenceInterface()._cross_source_view([c1, other])
    assert view_o["conflicts"] == []
    # كاشف (6): غياب الكشف ليس ادعاءً — لا يولّد تعارضاً
    e4 = {"path": "samer", "source_id": 3, "detected_stack": []}
    view3 = IntelligenceInterface()._cross_source_view([e1, e4])
    assert view3["conflicts"] == []


def test_source_claims_conflict_reaches_research_result(tmp_path):
    """الدعاوى تصل عبر الواجهة فعلًا (0054-0056): التساوي النصي للسياق
    ليس تحققاً — التحقق بدليل المصدر الفعلي (مراجعة git المسجلة)؛ المتحقق
    المتوافق يُعلن تعارضاً ولا يسقطه مصدر صامت ولا دعوى عن مراجعة أخرى؛
    والنصان المتساويان غير المتحققين ⇒ تناقض دعاوى مرسل منفصل لا تعارض
    مصادر؛ والقيمة الغائبة والسياق الغائب فعلاً عبر run؛ وقوائم الكشف
    وحدها اختلاف لا تعارض."""
    repo = _natrepo(tmp_path / "claimrepo", "claimrepo")
    (repo / "app.py").write_text("import flask\n", encoding="utf-8")
    (repo / "requirements.txt").write_text("flask>=2\n", encoding="utf-8")
    import subprocess
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    subprocess.run(["git", "add", "-A"], cwd=str(repo), check=True, env=env)
    subprocess.run(["git", "commit", "-qm", "claims"], cwd=str(repo),
                   check=True, env=env)
    head = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                          capture_output=True, text=True, check=True
                          ).stdout.strip()
    interface = IntelligenceInterface()
    # (1) سياق متحقق بدليل المصدر الفعلي (HEAD) + دعويان متنافيتان —
    # ودعوى ثالثة عن مراجعة أخرى ومصدر رابع صامت: التعارض قائم لا يسقطهما
    result = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.RESEARCH,
        question="ما إطار هذا المستودع؟",
        evidence_paths=[str(repo), str(repo), str(repo), str(repo)],
        source_claims=[
            {"source_id": 0, "path": str(repo), "property": "flask",
             "value": True, "context": head,
             "evidence": "بيان requirements.txt يذكر flask"},
            {"source_id": 1, "path": str(repo), "property": "flask",
             "value": False, "context": head,
             "evidence": "فحص يدوي: لا أثر للاستيراد"},
            # دعوى عن مراجعة أخرى (نص مختلف عن HEAD) — لا تُخفي تعارض
            # المتحققين (مجموعات سياق مستقلة)
            {"source_id": 2, "path": str(repo), "property": "flask",
             "value": True, "context": "rev-older",
             "evidence": "دعوى عن مراجعة أخرى"},
        ]))
    assert result.status in (IntelligenceStatus.RECOMMENDATION_UNAVAILABLE,
                            IntelligenceStatus.COMPLETED)
    cross = result.evidence_snapshot["cross_source"]
    conflicts = cross["conflicts"]
    assert len(conflicts) == 1
    conflict = conflicts[0]
    assert "flask" in conflict["subject"]
    assert head in conflict["context"]
    assert "متحقق بدليل المصدر" in conflict["context"]
    claims = conflict["claims"]
    assert {cl["source_id"] for cl in claims} == {0, 1}   # لا الثالث
    assert {cl["claim"] for cl in claims} == {"أثبت", "أنكر صراحةً"}
    joined = " ".join(cl.get("evidence", "") for cl in claims)
    assert "requirements.txt" in joined
    assert "فحص يدوي" in joined
    assert all(cl.get("origin") == "caller-provided" for cl in claims)
    # ودعوى المراجعة الأخرى محفوظة منفصلة (لا تُبطل غيرها)
    assert len(cross["incomparable_claims"]) == 1
    assert "مجموعات منفصلة" in cross["incomparable_claims"][0]["note"]

    # (2) نصا سياق متساويان لكن غير متحققين (ليسا HEAD) — لا تعارض مثبت؛
    # تناقض دعاوى المرسل يُعرض منفصلاً بوسمها
    unverified = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.RESEARCH,
        question="ما إطار هذا المستودع؟",
        evidence_paths=[str(repo), str(repo)],
        source_claims=[
            {"source_id": 0, "path": str(repo), "property": "flask",
             "value": True, "context": "declared-x",
             "evidence": "دعوى بسياق معلن غير فعلي"},
            {"source_id": 1, "path": str(repo), "property": "flask",
             "value": False, "context": "declared-x",
             "evidence": "أخرى بسياق معلن غير فعلي"},
        ]))
    cross_u = unverified.evidence_snapshot["cross_source"]
    assert cross_u["conflicts"] == []
    assert len(cross_u["caller_claims_contradictions"]) == 1
    assert "ليس إثبات تعارض مصادر" in \
        cross_u["caller_claims_contradictions"][0]["note"]

    # (3) القيمة الغائبة فعلاً: دعوى بلا قيمة منطقية — تُرفض وتُسمّى ولا
    # تصنع تعارضاً (غياب القيمة ليس إنكاراً يُستنتج)
    no_value = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.RESEARCH,
        question="ما إطار هذا المستودع؟",
        evidence_paths=[str(repo), str(repo)],
        source_claims=[
            {"source_id": 0, "path": str(repo), "property": "flask",
             "context": head,
             "evidence": "دعوى بلا قيمة"},
            {"source_id": 1, "path": str(repo), "property": "flask",
             "value": False, "context": head,
             "evidence": "مقابل بلا قيمة"},
        ]))
    cross_nv = no_value.evidence_snapshot["cross_source"]
    assert cross_nv["conflicts"] == []
    assert cross_nv["caller_claims_contradictions"] == []
    assert cross_nv["invalid_source_claims_named"] >= 1

    # (4) السياق الغائب فعلاً عبر run: دعويان متنافيتان بلا سياق — لا
    # تعارض مثبت (تناقض دعاوى مرسل غير متحقق)
    no_ctx = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.RESEARCH,
        question="ما إطار هذا المستودع؟",
        evidence_paths=[str(repo), str(repo)],
        source_claims=[
            {"source_id": 0, "path": str(repo), "property": "flask",
             "value": True, "evidence": "دعوى بلا سياق"},
            {"source_id": 1, "path": str(repo), "property": "flask",
             "value": False, "evidence": "أخرى بلا سياق"},
        ]))
    cross_nc = no_ctx.evidence_snapshot["cross_source"]
    assert cross_nc["conflicts"] == []
    assert len(cross_nc["caller_claims_contradictions"]) == 1

    # (5) اللقطة المستقلة من المراجعة (0059 — تصحيح 0058): تغيير غير ملتزم
    # في الشجرة الحية لا يصل إلى المحلل — التحليل لمحتوى المراجعة نفسها
    # (يُعلن ذلك في analysis_scope) والإسناد إليها مثبت؛ ويُثبت المحتوى
    # المقروء: كشف اللقطة flask (المحتوى الملتزم) لا django (التغيير المحلي)
    dirty = tmp_path / "dirtyrepo"
    shutil.copytree(repo, dirty)
    (dirty / "requirements.txt").write_text("django>=4\n", encoding="utf-8")
    # بلا التزام — الشجرة الحية وسخة؛ التحليل للقطة المراجعة
    dirty_result = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.RESEARCH,
        question="ما إطار هذا المستودع؟",
        evidence_paths=[str(dirty), str(dirty)],
        source_claims=[
            {"source_id": 0, "path": str(dirty), "property": "flask",
             "value": True, "context": head,
             "evidence": "دعوى بسياق HEAD مع شجرة وسخة"},
            {"source_id": 1, "path": str(dirty), "property": "flask",
             "value": False, "context": head,
             "evidence": "أخرى بسياق HEAD مع شجرة وسخة"},
        ]))
    cross_d = dirty_result.evidence_snapshot["cross_source"]
    # إثبات المحتوى المقروء: اللقطة (flask الملتزم) لا الحية (django المحلي)
    src0 = dirty_result.evidence_snapshot["sources"][0]
    assert "flask" in src0["detected_stack"]
    assert "django" not in src0["detected_stack"]
    assert "المراجعة" in str(src0["analysis_scope"])
    # والإسناد إلى المراجعة مثبت — التعارض المُحقَّق معلن
    assert len(cross_d["conflicts"]) == 1
    assert cross_d["caller_claims_contradictions"] == []

    # (6) مسار الدعوى لا يطابق مصدرها (0058 — تصحيح 0057): إسناد دعوى
    # لمصدر آخر بموضوع من نص المرسل غير مُثبت — تُرفض رفضاً مسمى ولا
    # تجعل نص المرسل موضوع التحقق؛ وتعارض المتحققين على مصدريهما لا
    # يتأثر بها
    mismatch = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.RESEARCH,
        question="ما إطار هذا المستودع؟",
        evidence_paths=[str(repo), str(repo)],
        source_claims=[
            {"source_id": 0, "path": str(repo), "property": "flask",
             "value": True, "context": head,
             "evidence": "متحققة أولى"},
            {"source_id": 1, "path": str(repo), "property": "flask",
             "value": False, "context": head,
             "evidence": "متحققة ثانية"},
            # مسارها المعلن ليس مسار مصدرها — رفض مسمى لا موضوع جديد
            {"source_id": 1, "path": str(dirty), "property": "flask",
             "value": True, "context": head,
             "evidence": "دعوى بمسار لا يطابق مصدرها"},
        ]))
    cross_m = mismatch.evidence_snapshot["cross_source"]
    assert cross_m["invalid_source_claims_named"] >= 1   # رفض مسمى
    assert any("لا يطابق مصدرها" in str(c.get("reason", ""))
               for src in mismatch.evidence_snapshot["sources"]
               for c in (src.get("invalid_source_claims") or []))
    assert len(cross_m["conflicts"]) == 1   # تعارض المتحققين قائم
    assert {cl["source_id"] for cl in
            cross_m["conflicts"][0]["claims"]} == {0, 1}

    # (7) القيمة النصية "false" ليست إثباتاً (استعادة تغطية 0055 عبر
    # run): تُرفض وتُسمّى ولا تصنع تعارضاً
    str_false = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.RESEARCH,
        question="ما إطار هذا المستودع؟",
        evidence_paths=[str(repo), str(repo)],
        source_claims=[
            {"source_id": 0, "path": str(repo), "property": "flask",
             "value": "false", "context": head,
             "evidence": "قيمة نصية لا منطقية"},
            {"source_id": 1, "path": str(repo), "property": "flask",
             "value": True, "context": head,
             "evidence": "دعوى صحيحة مقابل المرفوضة"},
        ]))
    cross_sf = str_false.evidence_snapshot["cross_source"]
    assert cross_sf["conflicts"] == []
    assert cross_sf["invalid_source_claims_named"] >= 1

    # (8) الدليل الفارغ: الدعوى غير مسندة تُرفض وتُسمّى (استعادة 0055)
    no_ev = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.RESEARCH,
        question="ما إطار هذا المستودع؟",
        evidence_paths=[str(repo), str(repo)],
        source_claims=[
            {"source_id": 0, "path": str(repo), "property": "flask",
             "value": True, "context": head, "evidence": ""},
            {"source_id": 1, "path": str(repo), "property": "flask",
             "value": False, "context": head, "evidence": "مقابل بلا دليل"},
        ]))
    cross_ne = no_ev.evidence_snapshot["cross_source"]
    assert cross_ne["conflicts"] == []
    assert cross_ne["invalid_source_claims_named"] >= 1


def test_content_digest_reliability_same_length_content_change(tmp_path):
    """موثوقية هوية المحتوى (0053): بلا تجزئة (سياستنا hash_predicate=None)
    تتطابق الهوية مع محتوى مختلف بنفس الطول — فلا تُدَّعى موثوقة ولا يثبت
    بها توافق سياق؛ وبتجزئة فعلية تغيّر المحتوى يغيّر الهوية."""
    interface = IntelligenceInterface()
    repo = tmp_path / "digestrepo"
    _write_repo(repo, {"a.txt": "AAAA\n"})
    shared = interface._analyze(str(repo))
    d1, reliable1 = _iface_module._analysis_content_digest(shared)
    # سياستنا لا تهشّ: الهوية بيانات وصفية (مسار+حجم) — غير موثوقة
    assert reliable1 is False
    # محتوى مختلف بنفس الطول: الهوية تتطابق رغم تغير المحتوى — الدليل
    # على أنها لا تصلح إثبات سياق بلا تجزئة
    (repo / "a.txt").write_text("BBBB\n", encoding="utf-8")
    shared2 = interface._analyze(str(repo))
    d2, reliable2 = _iface_module._analysis_content_digest(shared2)
    assert d1 == d2                 # نفس المسار والحجم بلا هاش
    assert reliable2 is False
    # وبهاش فعلي: الهوية موثوقة ويغيّرها تغيير المحتوى
    class _Hashed:
        pass
    entry = type("E", (), {})()
    entry.path, entry.size_bytes, entry.is_dir, entry.sha256 = \
        "a.txt", 5, False, "hash-of-AAAA"
    shared_h = type("S", (), {})()
    shared_h.files = [entry]
    dh1, rh1 = _iface_module._analysis_content_digest(shared_h)
    entry.sha256 = "hash-of-BBBB"
    dh2, rh2 = _iface_module._analysis_content_digest(shared_h)
    assert rh1 is True and rh2 is True
    assert dh1 != dh2                # تغيّر المحتوى يغيّر الهوية الموثوقة


def test_runtimes_restored_without_question(tmp_path):
    """انحدار 0050 مصلح (0051): عند غياب ترشيح السؤال تُعرض runtimes كاملة —
    مستودع بDockerfile يُظهر docker؛ وترشيح frameworks يستبعدها مقصوداً."""
    repo = _natrepo(tmp_path, "runtimerepo")
    (repo / "Dockerfile").write_text("FROM python:3.12\n", encoding="utf-8")
    interface = IntelligenceInterface()
    result = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.INSTANT,
        mission={"name": "تحليل", "capability": "RepositoryAnalysis",
                 "parameters": {"url": str(repo)}}))
    assert result.status is IntelligenceStatus.COMPLETED
    names = set(_iface_module._detected_stack_names(result.result))
    if "docker" in names:   # السلوك الكامل دون ترشيح — حيث كشف الكاشف
        fw_only = _iface_module._detected_stack_names(
            result.result, fact_categories={"frameworks"})
        assert "docker" not in fw_only   # استبعاد مقصود بالترشيح
    else:
        # الكاشف الحي قد لا يصنف Dockerfile كruntime — الاستبعاد المسمى
        # يختبر حيث توجد العينة فقط (غياب دليل لا إثبات عدم)
        pass


def test_fulfillment_evidence_values_and_evidence(tmp_path):
    """إيفاء المفاهيم بالقيم والأدلة معاً لكل بديل مؤهل (0052): القيم
    (أطر/اعتماديات/لغات) وأسانيدها لـ RA (DNA + framework_evidence بسجلات
    dependency/manifest) وRPP (uro + framework_evidence) — القيم الصحيحة
    وحدها لا تثبت الإيفاء؛ الأدلة معروضة بمساراتها."""

    interface = IntelligenceInterface()   # سجل حقيقي + قدرات حقيقية
    repo = _natrepo(tmp_path, "evidrepo")
    (repo / "app.py").write_text("import flask\n", encoding="utf-8")
    (repo / "requirements.txt").write_text("flask>=2\n", encoding="utf-8")
    text = "افحص اعتماديات وأطر المستودع " + str(repo)
    result = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.ENGINEER, natural_text=text))
    assert result.status is IntelligenceStatus.AWAITING_APPROVAL
    alt = result.engineering_plan["alternatives"]
    # أدلة الإيفاء لحوامل المخرج الفعلية في جدول الإيفاء المعلن
    row = next(r for r in alt["candidates"]
               if r["name"] == "RepositoryProcessingPipeline")
    assert row["fulfillment_evidence"]["frameworks"] == \
        ["universal_repository_object.frameworks"]
    # المختار بقاعدة التعادل المعلنة (ترتيب التسجيل) هو RA — قيمه مقيسة
    # وأدلة أطره محفوظة في DNA نفسه (framework_evidence — إثبات 0051/0052)
    assert result.engineering_plan["alternatives"]["selection"]["selected"] \
        == "RepositoryAnalysis"
    interface.approve(result.approval_id, approver="م")
    approved = interface.execute_approved(result.approval_id)
    assert approved.status is IntelligenceStatus.COMPLETED
    dna = approved.result
    assert "flask" in [f.lower() for f in dna.frameworks]   # القيمة مثبتة
    # قيم كل المفاهيم المطلوبة مثبتة في DNA (الاعتماديات واللغات أيضاً)
    assert "flask" in [str(d).lower() for d in dna.dependencies]
    assert "python" in [str(l).lower() for l in dna.languages]
    # تصحيح 0051: DNA يحمل سجلات أدلة أطر فعلاً (framework_evidence:
    # الاعتمادية/البيان) — ادعاء «قيم بلا أدلة» في 0050 كان خاطئاً
    ra_evidence = getattr(dna, "framework_evidence", None) or []
    def _evget(e, k):
        return (e.get(k) if isinstance(e, dict)
                else getattr(e, k, None))
    assert any(str(_evget(e, "dependency") or "").lower() == "flask"
               and _evget(e, "manifest") for e in ra_evidence)
    # RPP يكمل الصورة: أدلة كشف لكل إطار بمسارات الملفات في uro
    rpp = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.INSTANT,
        mission={"name": "خط", "capability": "RepositoryProcessingPipeline",
                 "parameters": {"url": str(repo)}}))
    assert rpp.status is IntelligenceStatus.COMPLETED
    uro = rpp.result["universal_repository_object"]
    assert "flask" in [f.lower() for f in uro["frameworks"]]
    # قيم كل المفاهيم المطلوبة في uro (الاعتماديات واللغات أيضاً)
    assert any(str(d.get("name", "")).lower() == "flask"
               for d in uro.get("dependencies", []) if isinstance(d, dict))
    assert "python" in [str(l).lower()
                        for l in (uro.get("all_languages") or [])]
    # مخرج uro يصرّح أدلة الكشف كقائمة سجلات (framework/dependency/manifest)
    rpp_evidence = uro.get("framework_evidence") or []
    assert any(str(e.get("dependency", "")).lower() == "flask"
               and e.get("manifest") for e in rpp_evidence)


# ------------------------------------------------------------------ 0052 --
def test_cost_samples_separated_by_request_input(tmp_path):
    """عينات التكلفة مجموعة واحدة بالوضع والمدخل (0052): تنفيذ المستودع A
    لا يغلق فجوة خطة المستودع B — وبعد تنفيذ B لا يُدمج زمنا A وB في وسيط
    واحد (وسيط B من عينة B وحدها)."""
    repo_a = _natrepo(tmp_path / "a", "arepo")
    repo_b = _natrepo(tmp_path / "b", "brepo")
    interface = IntelligenceInterface()
    # تنفيذ A (engineer) — أغلق فجوة A فقط
    first_a = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.ENGINEER,
        natural_text="افحص أمن المستودع " + str(repo_a)))
    assert first_a.status is IntelligenceStatus.AWAITING_APPROVAL
    interface.approve(first_a.approval_id, approver="م")
    assert interface.execute_approved(
        first_a.approval_id).status is IntelligenceStatus.COMPLETED
    # طلب B: عينة A (مدخل آخر) لا تغلق فجوة B — الفجوة باقية
    first_b = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.ENGINEER,
        natural_text="افحص أمن المستودع " + str(repo_b)))
    assert first_b.status is IntelligenceStatus.AWAITING_APPROVAL
    assert "engineering-plan-cost-estimate" in first_b.gaps
    assert first_b.engineering_plan["cost"]["source"] == "declared-literal"
    # تنفيذ B ثم طلب B ثانية: الفجوة تُغلق بعينة B وحدها — لا دمج مع A
    interface.approve(first_b.approval_id, approver="م")
    interface.execute_approved(first_b.approval_id)
    second_b = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.ENGINEER,
        natural_text="افحص أمن المستودع " + str(repo_b)))
    assert second_b.status is IntelligenceStatus.AWAITING_APPROVAL
    assert "engineering-plan-cost-estimate" not in second_b.gaps
    cost = second_b.engineering_plan["cost"]
    assert cost["source"] == "measured"
    # وسيط B من عينة B وحدها: n=1 ومدخل العينة هو B — لا زمن A فيها
    assert cost["n"] == 1
    assert cost["conditions"]["inputs"] == [str(repo_b)]
    assert cost["conditions"]["modes"] == ["engineer"]
    # ووسيط A أيضاً من عينة A وحدها (الطلب التالي لـ A)
    second_a = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.ENGINEER,
        natural_text="افحص أمن المستودع " + str(repo_a)))
    cost_a = second_a.engineering_plan["cost"]
    assert cost_a["n"] == 1
    assert cost_a["conditions"]["inputs"] == [str(repo_a)]


def test_runtimes_restored_without_question_real_runtime(tmp_path):
    """انحدار runtimes (0052 — تصحيح اختبار 0051): العينة تُنتج runtime فعلياً
    (package.json ⇒ Node.js — من ملفات الاعتماديات لا من Dockerfile)؛ ظهوره
    دون ترشيح واستبعاده بترشيح الأطر توكيدين إلزاميين على خط التحليل
    المعتمد نفسه (evidence.stack.runtimes) — لا على مخرج إسقاط."""
    repo = tmp_path / "rtrepo"
    _write_repo(repo, {"app.py": "import json\n",
                       "requirements.txt": "flask>=2.0\n",
                       "package.json": '{"name": "x", "dependencies": {}}\n'})
    interface = IntelligenceInterface()
    shared = interface._analyze(str(repo))   # خط ADR-0005 المعتمد
    stack = getattr(shared, "stack", None)
    assert stack is not None
    # العينة تُنتج runtime فعلياً — وإلا فالكاشف نفسه ناقص (لا تخطي)
    runtimes = {r.lower() for r in (getattr(stack, "runtimes", None) or [])}
    assert "node.js" in runtimes
    # دون ترشيح: runtimes كاملة (السلوك قبل 0050)
    names = set(_iface_module._detected_stack_names(shared))
    assert "node.js" in names
    # بترشيح الأطر: استبعاد مقصود مسمى
    fw_only = _iface_module._detected_stack_names(
        shared, fact_categories={"frameworks"})
    assert "node.js" not in fw_only


# ------------------------------------------------------------------ 0053 --
def test_architecture_not_inherited_for_unverified_capability(tmp_path):
    """العمارة لا تُورَّث (0053): طلب الأمن (SecurityScan) لا يوصف بمسار
    منتجي RA/DNA — producers = None بقصور مسمى، وفجوة المعمارية تبقى
    مسماة لا تُغلق بما لم يُتحقق من مساره."""
    repo = _natrepo(tmp_path, "secrepo")
    interface = IntelligenceInterface()
    result = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.ENGINEER,
        natural_text="افحص أمن المستودع " + str(repo)))
    assert result.status is IntelligenceStatus.AWAITING_APPROVAL
    ep = result.engineering_plan
    assert ep["architecture_design"] is not None
    # لا توريث: مسار المنتجين غير المتحقق يسمّى قصوره ولا يصفه بمسار DNA
    assert ep["architecture_design"]["producers"] is None
    assert ep["architecture_design"]["data_flow"] is None
    assert "قصور مسمى" in ep["architecture_design"]["note"]
    note = ep["architecture_design"]["note"]
    assert "RepositoryAnalysisCapability" not in note
    assert "RepositoryDNA" not in str(ep["architecture_design"])
    # والفجوة تبقى مسماة — لا تُغلق بما لم يتحقق
    assert "engineering-plan-architecture" in result.gaps


def test_fulfillment_evidence_values_and_evidence_committed(tmp_path):
    """أسانيد الإيفاء مكتملة (0053): العينة تُلتزم (git commit) قبل التنفيذ
    فلا يثبت الاختبار محتوى أقدم غير الموصوف؛ والاعتمادية بمصدرها المتوقع
    (requirements.txt) واللغات بقياسها الفعلي (language_stats) والدليل
    متوافق معه — وما لا يحمل المخرج سنده يسمّى قصوره."""
    repo = _natrepo(tmp_path / "comrepo", "evidrepo2")
    (repo / "app.py").write_text("import flask\n", encoding="utf-8")
    (repo / "requirements.txt").write_text("flask>=2\n", encoding="utf-8")
    # التزام التعديلات قبل التنفيذ — المراجعة المحللة هي الموصوفة
    import subprocess
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    subprocess.run(["git", "add", "-A"], cwd=str(repo), check=True, env=env)
    subprocess.run(["git", "commit", "-qm", "sample"], cwd=str(repo),
                   check=True, env=env)
    interface = IntelligenceInterface()
    text = "افحص اعتماديات وأطر ولغات المستودع " + str(repo)
    result = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.ENGINEER, natural_text=text))
    assert result.status is IntelligenceStatus.AWAITING_APPROVAL
    interface.approve(result.approval_id, approver="م")
    approved = interface.execute_approved(result.approval_id)
    assert approved.status is IntelligenceStatus.COMPLETED
    dna = approved.result
    # القيم: كل المفاهيم المطلوبة
    assert "flask" in [f.lower() for f in dna.frameworks]
    assert "python" in [str(l).lower() for l in dna.languages]
    # الاعتمادية بمصدرها المتوقع: سجل الدليل يربطها بالبيان requirements.txt
    ev = [e for e in (getattr(dna, "framework_evidence", None) or [])
          if (e.get("dependency") if isinstance(e, dict)
              else getattr(e, "dependency", "") or "").lower() == "flask"]
    assert ev, "دليل الاعتمادية غائب"
    flask_ev = ev[0]
    manifest = (flask_ev.get("manifest") if isinstance(flask_ev, dict)
                else getattr(flask_ev, "manifest", ""))
    assert manifest == "requirements.txt"
    # وسجل تفاصيل الاعتمادية نفسها يحمل المصدر (dependency_details)
    dep_details = [d for d in (getattr(dna, "dependency_details", None) or [])
                   if isinstance(d, dict)
                   and str(d.get("name", "")).lower() == "flask"]
    assert dep_details, "سجل تفاصيل الاعتمادية غائب في DNA"
    assert any(str(d.get("manifest", "")) == "requirements.txt"
               for d in dep_details)
    # اللغات بقياسها الفعلي من العينة المعروفة: ملف Python واحد (app.py)
    # بسطر واحد — لا يمر قياس أقدم مختلف
    stats = getattr(dna, "language_stats", None) or {}
    py = stats.get("Python") or {}
    assert py.get("files") == 1 and py.get("lines") == 1
    # قصور مسمى: DNA لا يحمل سجل دليل منفصلاً لكل لغة (القياس نفسه
    # هو المتاح) — لا يُدَّعى سند غير موجود
    assert not any("language_evidence" in str(k)
                   for k in dir(dna))
    # ---- البديل الثاني المؤهل على العينة الملتزمة نفسها (0054) ----
    # RPP: القيم والأسانيد نفسها في uro — لا يثبت اختبار RA وحده الإيفاء
    rpp = interface.run(IntelligenceRequest(
        mode=IntelligenceMode.INSTANT,
        mission={"name": "خط", "capability": "RepositoryProcessingPipeline",
                 "parameters": {"url": str(repo)}}))
    assert rpp.status is IntelligenceStatus.COMPLETED
    uro = rpp.result["universal_repository_object"]
    # القيم: كل المفاهيم المطلوبة من العينة الملتزمة المعروفة
    assert "flask" in [f.lower() for f in uro["frameworks"]]
    assert "python" in [str(l).lower()
                        for l in (uro.get("all_languages") or [])]
    # الاعتمادية بمصدرها: سجل uro يحمل الاعتمادية ببيانها requirements.txt
    dep_records = [d for d in (uro.get("dependencies") or [])
                   if isinstance(d, dict)
                   and str(d.get("name", "")).lower() == "flask"]
    assert dep_records, "سجل الاعتمادية غائب في uro"
    assert any(str(d.get("manifest", "")) == "requirements.txt"
               for d in dep_records)
    # دليل الإطار: uro يصرّح أدلة الكشف — سجلات dependency/manifest
    rpp_ev = uro.get("framework_evidence") or []
    flask_ev = [e for e in rpp_ev
                if str(e.get("dependency", "")).lower() == "flask"]
    assert flask_ev, "دليل الإطار غائب في uro"
    assert any(str(e.get("manifest", "")) == "requirements.txt"
               for e in flask_ev)
    # اللغات بقياسها الفعلي من العينة المعروفة: ملف Python واحد (app.py)
    # بسطر واحد — لا يمر قياس أقدم مختلف
    rpp_stats = uro.get("language_stats") or {}
    py_stat = rpp_stats.get("Python") or {}
    assert py_stat.get("files") == 1 and py_stat.get("lines") == 1
