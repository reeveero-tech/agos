"""R-W1-006 — اختبارات توحيد الذكاء (ADR-0009).

الجزء الأول: **توصيف القائم على HEAD قبل أي تعديل سلوكي** — المحلل والمتحقق
والمخطط والمترجم ونظام الاعتماد بأشكالها الحالية بالضبط (لا حكم، لا تغيير).
"""
import os
import sys
from pathlib import Path

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
    def resolve(self, capability, mission):
        return ProviderSelection(
            provider=object(), provider_name="FakeProvider",
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
