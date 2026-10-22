"""R-W1-004 — توحيد القرار: مسار قرار واحد يُنتج دليلاً.

كل تأكيد فعلي (R-Q-001): كل مسارات الاختيار داخل نطاق البند تفوّض إلى
القلب الموحد (قرار القدرة وقرار الموفّر في المسار الحي عبر ``resolvers/``،
والمحرك القديم ``decision/``) — والتفويض مثبت بتجسس لا بتطابق نتائج،
والدليل كامل (مرشحون، قيم كل قاعدة، استبعادات مسماة، سياسة معلنة، كسر
تعادل، نقص معلن، أخطاء مسماة)، وسلوكان صُلحا ووثّقا (موفّر بلا دعم
مطلوب يُستبعد، وقدرة بلا علاقة لا تُختار افتراضياً)، والحتمية محفوظة.
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agos" / "agos-kernel"))

from decision_pipeline import (  # noqa: E402
    DECISION_CORE, DecisionCandidate, DecisionRequest, DecisionPolicy,
    LIVE_CAPABILITY_POLICY, LIVE_PROVIDER_POLICY, FIRST_PROVIDER_POLICY,
)
from decision import DecisionEngine  # noqa: E402
from mission import Mission  # noqa: E402
from registry.capability import CapabilityRegistry  # noqa: E402
from registry.provider import ProviderRegistry  # noqa: E402
from resolvers import CapabilityResolver, ProviderResolver  # noqa: E402

AT = datetime(2026, 10, 22, 18, 0, tzinfo=timezone.utc)


class FakeCapability:
    def __init__(self, name, skills, priority=1.0):
        self.name = name
        self.skills = list(skills)
        self.priority = priority

    def execute(self, parameters):
        return {"status": "success", "parameters": parameters}


class FakeProvider:
    def __init__(self, name, skills, priority=1.0):
        self.name = name
        self._skills = set(skills)
        self.priority = priority

    def supports_skill(self, skill):
        return skill in self._skills


def _cap_registry(*caps):
    r = CapabilityRegistry()
    for c in caps:
        r.register(c)
    return r


def _prov_registry(*provs):
    r = ProviderRegistry()
    for p in provs:
        r.register(p)
    return r


def _mission(capability, **params):
    return Mission(name="m", description="d", capability=capability,
                   parameters=params)


# ---------------------------------------------------------------------------
# التفويض الفعلي — تجسس لا تطابق نتائج
# ---------------------------------------------------------------------------

class TestDelegation:
    def test_capability_resolver_calls_the_unified_core(self, monkeypatch):
        calls = []
        original = DECISION_CORE.evaluate

        def spy(request, candidates, policy, **kw):
            calls.append((policy.policy_id, kw.get("decision_id")))
            return original(request, candidates, policy, **kw)

        monkeypatch.setattr(DECISION_CORE, "evaluate", spy)
        resolver = CapabilityResolver(_cap_registry(
            FakeCapability("Alpha", ["s1"])))
        selection = resolver.resolve(_mission("Alpha"))
        assert calls and calls[0][0] == "live-capability-resolution"
        assert selection.record.policy_id == "live-capability-resolution"
        assert selection.status.value == "success"

    def test_provider_resolver_calls_the_unified_core(self, monkeypatch):
        calls = []
        original = DECISION_CORE.evaluate

        def spy(request, candidates, policy, **kw):
            calls.append(policy.policy_id)
            return original(request, candidates, policy, **kw)

        monkeypatch.setattr(DECISION_CORE, "evaluate", spy)
        resolver = ProviderResolver(
            _prov_registry(FakeProvider("P1", ["s1"])),
            _cap_registry())
        capability = FakeCapability("Alpha", ["s1"])
        selection = resolver.resolve(capability)
        assert calls == ["live-provider-resolution"]
        assert selection.record.policy_id == "live-provider-resolution"

    def test_old_decision_engine_calls_the_unified_core(self, monkeypatch):
        calls = []
        original = DECISION_CORE.evaluate

        def spy(request, candidates, policy, **kw):
            calls.append(policy.policy_id)
            return original(request, candidates, policy, **kw)

        monkeypatch.setattr(DECISION_CORE, "evaluate", spy)

        class Ctx:
            mission = _mission("Alpha")

        engine = DecisionEngine(_cap_registry(FakeCapability("Alpha", ["s1"])),
                                _prov_registry(FakeProvider("P1", ["s1"])))
        result = engine.decide(Ctx())
        assert result.status.value == "success"
        assert calls == ["first-provider-for-skill"]
        assert result.data.record.policy_id == "first-provider-for-skill"

    def test_live_mission_produces_evidence_records(self):
        # عبر المسار الحي كاملاً: boot() → mission engine → pipeline → resolvers
        import agos_runtime
        k = agos_runtime.boot()
        out = k.run({"name": "t", "description": "d",
                     "capability": "RepositoryProcessingPipeline",
                     "parameters": {"repo_path": str(
                         Path(__file__).resolve().parents[1])}})
        assert out.state.value == "completed"
        assert len(out.decision_records) == 2
        cap_record, prov_record = out.decision_records
        assert cap_record.kind == "capability"
        assert cap_record.selected == "RepositoryProcessingPipeline"
        assert prov_record.kind == "provider"
        assert prov_record.selected
        # الدليل متاح عبر النتيجة — لا يُنتج ثم يُسقط
        assert cap_record.to_dict()["policy"]["policy_id"] == \
            "live-capability-resolution"


# ---------------------------------------------------------------------------
# عقد الدليل — المحتوى لا الشكل
# ---------------------------------------------------------------------------

class TestEvidenceContract:
    def test_record_carries_candidates_values_and_policy(self):
        request = DecisionRequest(kind="provider", required_skills=["s1", "s2"])
        candidates = [
            DecisionCandidate(name="P1", offered_skills=["s1", "s2"],
                               priority=5.0),
            DecisionCandidate(name="P2", offered_skills=["s1"], priority=9.0)]
        record = DECISION_CORE.evaluate(
            request, candidates, LIVE_PROVIDER_POLICY,
            decision_id="d1", timestamp=AT.isoformat())
        # سياسة معلنة بهوية وإصدار
        assert record.policy_id == "live-provider-resolution"
        assert record.policy_version == "1.0.0"
        # كل مرشح بقيم القواعد التي استخدمت فعلاً
        by_name = {c.name: c for c in record.candidates}
        assert by_name["P1"].values_used["skill_match"] == 1.0
        assert by_name["P2"].values_used["skill_match"] == 0.5
        assert by_name["P1"].values_used["priority"] == 0.5
        # المختار والبدائل مرتبة
        assert record.selected == "P1"
        assert record.ranked_alternatives == ["P1", "P2"]

    def test_competitive_flip_is_traceable_to_the_rule(self):
        # تغيّر معلومة محددة يغيّر الاختيار — والسبب قابل للتتبع للقاعدة
        request_a = DecisionRequest(kind="provider", required_skills=["s1"])
        request_b = DecisionRequest(kind="provider", required_skills=["s2"])
        candidates = [
            DecisionCandidate(name="P1", offered_skills=["s1"]),
            DecisionCandidate(name="P2", offered_skills=["s2"])]
        first = DECISION_CORE.evaluate(request_a, candidates,
                                       LIVE_PROVIDER_POLICY,
                                       decision_id="d1", timestamp=AT.isoformat())
        second = DECISION_CORE.evaluate(request_b, candidates,
                                        LIVE_PROVIDER_POLICY,
                                        decision_id="d2", timestamp=AT.isoformat())
        assert first.selected == "P1"
        assert second.selected == "P2"
        # الاستبعاد مسمّى بالقاعدة
        assert next(c for c in first.candidates
                    if c.name == "P2").exclusion_reason == \
            "no-required-skill-support"

    def test_zero_skill_provider_is_excluded_not_scored_in(self):
        # سلوك مصحح وموثق: مساهمات الأولوية/القيود الافتراضية لم تعد تكفي
        request = DecisionRequest(kind="provider", required_skills=["s1"])
        candidates = [
            DecisionCandidate(name="Zero", offered_skills=[], priority=10.0)]
        record = DECISION_CORE.evaluate(
            request, candidates, LIVE_PROVIDER_POLICY,
            decision_id="d1", timestamp=AT.isoformat())
        assert record.status == "no_match"
        assert record.candidates[0].excluded
        assert record.candidates[0].exclusion_reason == \
            "no-required-skill-support"

    def test_unrelated_capability_is_excluded_not_defaulted(self):
        # سلوك مصحح وموثق: بلا علاقة اسم ولا مهارات — لا اختيار افتراضي
        request = DecisionRequest(kind="capability", requested_name="Zeta",
                                  required_skills=[])
        candidates = [DecisionCandidate(name="Alpha", offered_skills=["s1"])]
        record = DECISION_CORE.evaluate(
            request, candidates, LIVE_CAPABILITY_POLICY,
            decision_id="d1", timestamp=AT.isoformat())
        assert record.status == "no_match"
        assert record.candidates[0].exclusion_reason == \
            "no-name-or-skill-relationship"

    def test_constraints_are_declared_not_evaluated(self):
        # القيود مساهمة افتراضية معلنة — وفحصها نقص مسمّى لا ادعاء استيفاء
        request = DecisionRequest(kind="provider", required_skills=["s1"],
                                   constraints=[{"c": "x"}])
        candidates = [DecisionCandidate(name="P1", offered_skills=["s1"])]
        record = DECISION_CORE.evaluate(
            request, candidates, LIVE_PROVIDER_POLICY,
            decision_id="d1", timestamp=AT.isoformat())
        assert record.missing_info
        assert any(m.startswith("constraints-not-evaluated") for m in
                   record.missing_info)
        values = record.candidates[0].values_used
        # معلنة كافتراضية غير مُقيَّمة — قيمة وأصل معلنان
        assert values["constraint_contribution"]["value"] == 1.0
        assert values["constraint_contribution"]["basis"] == \
            "declared-default-unevaluated"

    def test_tie_break_is_declared_and_deterministic(self):
        request = DecisionRequest(kind="provider", required_skills=["s1"])
        candidates = [
            DecisionCandidate(name="P1", offered_skills=["s1"]),
            DecisionCandidate(name="P2", offered_skills=["s1"])]
        record = DECISION_CORE.evaluate(
            request, candidates, LIVE_PROVIDER_POLICY,
            decision_id="d1", timestamp=AT.isoformat())
        assert record.tie_break == "stable-registration-order"
        # ترتيب التسجيل يكسر التعادل — حتمي معلن
        assert record.selected == "P1"

    def test_no_candidates_is_named_gap(self):
        record = DECISION_CORE.evaluate(
            DecisionRequest(kind="provider", required_skills=["s1"]),
            [], LIVE_PROVIDER_POLICY,
            decision_id="d1", timestamp=AT.isoformat())
        assert record.status == "no_match"
        assert "no-candidates-registered" in record.missing_info

    def test_evaluation_failure_is_named_error(self):
        class Exploding:
            name = "boom"
            offered_skills = ["s1"]
            priority = 1.0
            ref = None

        # نجعل التقييم يفشل عبر سياسة بأوزان غير قابلة للضرب
        bad_policy = DecisionPolicy(policy_id="bad", version="0",
                                     kind="provider", weights={"skill": "x"})
        record = DECISION_CORE.evaluate(
            DecisionRequest(kind="provider", required_skills=["s1"]),
            [Exploding()], bad_policy,
            decision_id="d1", timestamp=AT.isoformat())
        assert record.status == "error"
        assert record.errors

    def test_deterministic_selection_and_evidence(self):
        request = DecisionRequest(kind="provider", required_skills=["s1", "s2"])
        candidates = [
            DecisionCandidate(name="P1", offered_skills=["s1"], priority=3.0),
            DecisionCandidate(name="P2", offered_skills=["s1", "s2"], priority=1.0)]
        first = DECISION_CORE.evaluate(
            request, candidates, LIVE_PROVIDER_POLICY,
            decision_id="d1", timestamp=AT.isoformat())
        second = DECISION_CORE.evaluate(
            request, list(candidates), LIVE_PROVIDER_POLICY,
            decision_id="d2", timestamp=AT.isoformat())
        # الاختيار والدليل الحسابي نفسهما — الهوية والزمن وحدهما اختلفا
        assert first.selected == second.selected
        assert first.ranked_alternatives == second.ranked_alternatives
        assert [c.to_dict() for c in first.candidates] == \
            [c.to_dict() for c in second.candidates]
        assert first.to_dict() != second.to_dict()   # الهوية تفرق فقط


# ---------------------------------------------------------------------------
# التوافق — الواجهات القديمة كما هي
# ---------------------------------------------------------------------------

class TestCompatibility:
    def test_decision_engine_output_shape(self):
        class Ctx:
            mission = _mission("Alpha")

        engine = DecisionEngine(
            _cap_registry(FakeCapability("Alpha", ["s1", "s2"])),
            _prov_registry(FakeProvider("P1", ["s1"]),
                           FakeProvider("P2", ["s1", "s2"])))
        result = engine.decide(Ctx())
        assert result.status.value == "success"
        decision = result.data
        # التواقيع والأنواع كما كانت — مع الدليل إضافةً لا استبدالاً
        assert decision.capability == "Alpha"
        # قاعدة المحرك القديم منفذة فعلياً: أول مهارة (s1) → أول موفّر
        # بترتيب التسجيل يدعمها (P1) — لا الأفضل تغطية (P2)
        assert decision.provider == "P1"
        assert decision.skills == ["s1", "s2"]
        assert decision.record.selected == decision.provider

    def test_resolver_selections_keep_fields(self):
        caps = CapabilityResolver(_cap_registry(
            FakeCapability("Alpha", ["s1"])))
        selection = caps.resolve(_mission("Alpha"))
        assert selection.capability.name == "Alpha"
        assert selection.capability_name == "Alpha"
        assert selection.status.value == "success"
        assert selection.reason == "Exact name match"
        assert selection.score.total > 0

        provs = ProviderResolver(
            _prov_registry(FakeProvider("P1", ["s1", "s2"])),
            _cap_registry())
        pselection = provs.resolve(FakeCapability("Alpha", ["s1", "s2"]))
        assert pselection.provider.name == "P1"
        assert pselection.supported_skills == ["s1", "s2"]
        assert pselection.reason.startswith("Supports 2/2")

    def test_missing_capability_still_fails_with_same_message(self):
        resolver = CapabilityResolver(_cap_registry(
            FakeCapability("Alpha", ["s1"])))
        selection = resolver.resolve(_mission("NoSuchCap"))
        # رسالة التوافق كما كانت — والفرق الموثق: لا اختيار لغير المناسب
        assert selection.status.value == "no_match"
        assert selection.reason == "No capability matches the requirements"

    def test_no_provider_support_still_fails_with_same_message(self):
        resolver = ProviderResolver(
            _prov_registry(FakeProvider("P1", ["other"])),
            _cap_registry())
        selection = resolver.resolve(FakeCapability("Alpha", ["s1"]))
        assert selection.status.value == "no_match"
        assert selection.reason == "No providers support required skills"

    def test_cognitive_decision_marks_caller_provenance(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agos"))
        from cognitive.decision import UniversalDecisionPlatform
        platform = UniversalDecisionPlatform()
        decision = platform.create_decision("d", ["a", "b"])
        ok = platform.make_decision(decision.decision_id, "a",
                                    evidence=["caller said so"],
                                    reasoning="caller", confidence=0.9)
        assert ok
        # المصدر معلن: مقدَّم من المستدعي — لا ادعاء تقييم المحرك
        assert decision.evidence_provenance == "caller-provided"
        assert decision.chosen_option == "a"
        assert decision.rejected_options == ["b"]


# ---------------------------------------------------------------------------
# جولة المراجعة الثانية — ما كشفته المراجعة
# ---------------------------------------------------------------------------

class TestBatchPipelineDelegation:
    def test_decision_pipeline_decide_itself_calls_the_core(self, monkeypatch):
        """مسار الدُفعة نفسه (DecisionPipeline.decide) يفوّض — لا الاسم فقط."""
        from decision_pipeline import DecisionPipeline, DecisionContext
        calls = []
        original = DECISION_CORE.evaluate

        def spy(request, candidates, policy, **kw):
            calls.append(policy.policy_id)
            return original(request, candidates, policy, **kw)

        monkeypatch.setattr(DECISION_CORE, "evaluate", spy)
        pipeline = DecisionPipeline(_cap_registry(FakeCapability("Alpha", ["s1", "s2"])),
                                    _prov_registry(FakeProvider("P1", ["s1"]),
                                                   FakeProvider("P2", ["s1", "s2"])))
        result = pipeline.decide(DecisionContext(_mission("Alpha")))
        # المرحلتان معاً من القلب — بأثر القدرة والموفّر
        assert calls == ["pipeline-capability-selection",
                         "pipeline-provider-selection"]
        assert result.status.value == "selected"
        assert [r.policy_id for r in result.records] == \
            ["pipeline-capability-selection", "pipeline-provider-selection"]
        assert result.capability == "Alpha"
        assert result.provider in {"P1", "P2"}

    def test_decision_pipeline_records_kept_on_failure(self):
        from decision_pipeline import DecisionPipeline, DecisionContext
        pipeline = DecisionPipeline(_cap_registry(FakeCapability("Alpha", ["s1"])),
                                     _prov_registry(FakeProvider("P1", ["other"])))
        result = pipeline.decide(DecisionContext(_mission("Alpha")))
        assert result.status.value == "failed"
        # أثر المرحلتين محفوظ حتى عند فشل المسار — المجمّع القديم يسقط
        # إلى كل الموفّرين عند عدم الدعم، فكلا العقدين موجودان والفشل مسمّى
        assert [r.policy_id for r in result.records] == \
            ["pipeline-capability-selection", "pipeline-provider-selection"]
        assert result.error


class TestFirstProviderRuleActuallyImplemented:
    def test_first_skill_first_registered_provider_wins(self):
        # المهارات [s1,s2]؛ P1 يدعم s1 والثاني يدعم الاثنين —
        # القاعدة القديمة: P1 (أول مهارة → أول موفّر بترتيب التسجيل)
        request = DecisionRequest(kind="provider", required_skills=["s1", "s2"])
        candidates = [
            DecisionCandidate(name="P1", offered_skills=["s1"]),
            DecisionCandidate(name="P2", offered_skills=["s1", "s2"])]
        record = DECISION_CORE.evaluate(
            request, candidates, FIRST_PROVIDER_POLICY,
            decision_id="d1", timestamp=AT.isoformat())
        assert record.selected == "P1"

    def test_first_skill_decides_not_registration(self):
        # P1 يدعم s2 فقط، P2 يدعم s1 فقط — القديم: P2 (أول مهارة s1)
        request = DecisionRequest(kind="provider", required_skills=["s1", "s2"])
        candidates = [
            DecisionCandidate(name="P1", offered_skills=["s2"]),
            DecisionCandidate(name="P2", offered_skills=["s1"])]
        record = DECISION_CORE.evaluate(
            request, candidates, FIRST_PROVIDER_POLICY,
            decision_id="d1", timestamp=AT.isoformat())
        assert record.selected == "P2"

    def test_empty_skills_capability_keeps_old_failure(self):
        # قدرة بلا مهارات: المحرك القديم يفشل — لا يختار موفّراً
        class Ctx:
            mission = _mission("Alpha")

        engine = DecisionEngine(
            _cap_registry(FakeCapability("Alpha", [])),
            _prov_registry(FakeProvider("P1", ["s1"])))
        result = engine.decide(Ctx())
        assert result.status.value == "failure"
        assert result.error == "No provider found for skills: []"


class TestEvidenceSurvivesFailure:
    def test_capability_resolution_failure_keeps_record(self):
        # فشل حل القدرة — أثر محاولة القرار محفوظ في النتيجة
        import agos_runtime
        k = agos_runtime.boot()
        out = k.run({"name": "t", "description": "d",
                     "capability": "NoSuchCapability",
                     "parameters": {}})
        assert out.state.value == "failed"
        assert len(out.decision_records) == 1
        assert out.decision_records[0].status == "no_match"

    def test_provider_resolution_failure_keeps_both_records(self):
        import agos_runtime
        k = agos_runtime.boot()
        out = k.run({"name": "t", "description": "d",
                     "capability": "RepositoryAnalysis",
                     "parameters": {"repo_path": str(
                         Path(__file__).resolve().parents[1])}})
        assert out.state.value in {"failed", "completed"}
        # العقدان موجودان أياً كانت حالة التنفيذ — الدليل لا يُسقط
        assert len(out.decision_records) == 2

    def test_execution_failure_after_selection_keeps_records(self):
        # نجاح الاختيار وفشل التنفيذ — العقدين في النتيجة الفاشلة
        import agos_runtime
        k = agos_runtime.boot()
        out = k.run({"name": "t", "description": "d",
                     "capability": "RepositoryAnalysis",
                     "parameters": {"repo_path": "/nonexistent/path/xyz"}})
        if out.state.value == "failed":
            assert len(out.decision_records) == 2
        else:  # المزوّد المحلي قد ينجح بغض النظر — العقدان موجودان
            assert len(out.decision_records) == 2


class TestNoUndocumentedBehaviorChanges:
    def test_priority_zero_is_not_coerced_to_one(self):
        # الأولوية 0 تبقى 0 — لا تحويل إلى 1 (مساهمات القلب الحسابية)
        request = DecisionRequest(kind="provider", required_skills=["s1"])
        candidates = [
            DecisionCandidate(name="P1", offered_skills=["s1"], priority=0.0)]
        record = DECISION_CORE.evaluate(
            request, candidates, LIVE_PROVIDER_POLICY,
            decision_id="d1", timestamp=AT.isoformat())
        assert record.candidates[0].values_used["priority"] == 0.0

    def test_no_required_skills_all_equal_registration_order(self):
        # بلا مهارات مطلوبة: الجميع 1.0 والاختيار بترتيب التسجيل —
        # الأولوية لا تؤثر (السلوك القديم حرفياً)
        request = DecisionRequest(kind="provider", required_skills=[])
        candidates = [
            DecisionCandidate(name="P1", offered_skills=[], priority=1.0),
            DecisionCandidate(name="P2", offered_skills=[], priority=9.0)]
        record = DECISION_CORE.evaluate(
            request, candidates, LIVE_PROVIDER_POLICY,
            decision_id="d1", timestamp=AT.isoformat())
        assert record.selected == "P1"
        assert all(c.values_used.get("total") == 1.0 for c in record.candidates)

    def test_evaluation_error_named_and_kept(self):
        # فشل تقييم مرشح داخل القلب: خطأ مسمّى بالمرشح + الأثر المتراكم محفوظ
        from decision_pipeline import DecisionCandidate, DecisionRequest
        from decision_pipeline import LIVE_PROVIDER_POLICY as LPP
        rec = DECISION_CORE.evaluate(
            DecisionRequest(kind="provider", required_skills=["s1"]),
            [DecisionCandidate(name="ok", offered_skills=["s1"]),
             DecisionCandidate(name="x", offered_skills=["s1"],
                               priority=object())],  # غير قابل للتحويل
            LPP, decision_id="d1", timestamp=AT.isoformat())
        assert rec.status == "error"
        assert rec.candidates  # تقييم من سبق الفشل محفوظ
        assert rec.errors[0].startswith("candidate x:")

    def test_error_status_mapped_to_error_not_no_match(self, monkeypatch):
        # المحول يبلّغ تعذر التقييم ERROR — لا يخلطه بعدم المطابقة
        from decision_pipeline import DecisionRecord
        error_record = DecisionRecord(
            decision_id="d1", kind="provider",
            requested={}, policy_id="live-provider-resolution",
            policy_version="1.0.0", status="error",
            errors=["ValueError: cannot convert priority"])
        monkeypatch.setattr(DECISION_CORE, "evaluate",
                            lambda *a, **kw: error_record)
        resolver = ProviderResolver(
            _prov_registry(FakeProvider("P1", ["s1"])),
            _cap_registry())
        selection = resolver.resolve(FakeCapability("Alpha", ["s1"]))
        assert selection.status.value == "error"
        assert "ValueError" in selection.reason
        assert selection.record is error_record  # الدليل لا يُسقط


class TestSerializedEvidenceStrength:
    def test_to_dict_exports_components_and_policy_snapshot(self):
        request = DecisionRequest(kind="provider", required_skills=["s1"])
        record = DECISION_CORE.evaluate(
            request, [DecisionCandidate(name="P1", offered_skills=["s1"],
                                         priority=2.0)],
            LIVE_PROVIDER_POLICY, decision_id="d1", timestamp=AT.isoformat())
        data = record.to_dict()
        # مكونات الدرجة كاملة لا الإجمالي وحده
        assert data["candidates"][0]["score"]["skill_match"] == 1.0
        assert "total" in data["candidates"][0]["score"]
        # لقطة السياسة المستخدمة: الأوزان والقواعد — لا الهوية فقط
        assert data["policy"]["policy_id"] == "live-provider-resolution"
        assert data["policy"]["weights"]["skill"] == 0.8
        assert data["policy"]["rules"]["tie_break"] == "stable-registration-order"

    def test_name_ladder_comes_from_policy_rules(self):
        # سلّم الأسماء يحكم فعلاً من قواعد السياسة المعلنة — لا ثوابت خفية
        request = DecisionRequest(kind="capability",
                                  requested_name="RepositoryAnalysis")
        candidates = [DecisionCandidate(name="RepositoryAnalysisExtended",
                                        offered_skills=[])]
        record = DECISION_CORE.evaluate(
            request, candidates, LIVE_CAPABILITY_POLICY,
            decision_id="d1", timestamp=AT.isoformat())
        # requested_in_name = 0.8 (من rules.name_match)
        assert record.candidates[0].values_used["skill_match"] == 0.8
        # تغيير السلّم يغيّر النتيجة — القاعدة تتحكم فعلاً
        from decision_pipeline import DecisionPolicy
        custom = DecisionPolicy(
            policy_id="custom", version="1", kind="capability",
            weights={"skill": 1.0, "constraint": 0.0, "priority": 0.0},
            rules={"name_match": {"exact": 1.0, "requested_in_name": 0.5,
                                  "name_in_requested": 0.2}})
        record2 = DECISION_CORE.evaluate(
            request, candidates, custom,
            decision_id="d2", timestamp=AT.isoformat())
        assert record2.candidates[0].values_used["skill_match"] == 0.5

    def test_constraint_contribution_labeled_unevaluated(self):
        request = DecisionRequest(kind="provider", required_skills=["s1"],
                                   constraints=[{"c": "x"}])
        record = DECISION_CORE.evaluate(
            request, [DecisionCandidate(name="P1", offered_skills=["s1"])],
            LIVE_PROVIDER_POLICY, decision_id="d1", timestamp=AT.isoformat())
        entry = record.candidates[0].values_used["constraint_contribution"]
        assert entry["basis"] == "declared-default-unevaluated"


# ---------------------------------------------------------------------------
# جولة المراجعة الثالثة — ما كشفته المراجعة
# ---------------------------------------------------------------------------

class TestDeterministicFailureCases:
    """حالات الفشل الثلاث مثبتة بتجهيزات محلية حتمية — لا قبول مزدوج."""

    def _kernel_parts(self, caps, provs):
        from events import EventBus
        from pipeline import ExecutionPipeline
        from mission_engine import MissionExecutor
        cap_resolver = CapabilityResolver(_cap_registry(*caps))
        prov_resolver = ProviderResolver(_prov_registry(*provs), _cap_registry())
        pipeline = ExecutionPipeline(EventBus(), cap_resolver, prov_resolver)
        return MissionExecutor(pipeline)

    def test_capability_resolution_failure_keeps_one_record(self):
        executor = self._kernel_parts([FakeCapability("Alpha", ["s1"])],
                                      [FakeProvider("P1", ["s1"])])
        out = executor.execute(_mission("NoSuchCapability"))
        assert out.state.value == "failed"
        assert "Capability resolution failed" in (out.error or "")
        # أثر محاولة اختيار القدرة محفوظ — بحالة no_match صريحة
        assert len(out.decision_records) == 1
        assert out.decision_records[0].status == "no_match"
        assert out.decision_records[0].kind == "capability"

    def test_provider_resolution_failure_keeps_both_records(self):
        # قدرة مطلوبة مهاراتها لا يدعمها أي موفّر — فشل حتمي بالعقدين
        executor = self._kernel_parts([FakeCapability("Alpha", ["s1"])],
                                      [FakeProvider("P1", ["other"])])
        out = executor.execute(_mission("Alpha"))
        assert out.state.value == "failed"
        assert "Provider resolution failed" in (out.error or "")
        assert len(out.decision_records) == 2
        assert out.decision_records[0].status == "selected"
        assert out.decision_records[1].status == "no_match"
        assert out.decision_records[1].kind == "provider"

    def test_execution_failure_after_selection_keeps_both_records(self):
        class ExplodingCapability(FakeCapability):
            def execute(self, parameters):
                raise RuntimeError("boom during execution")

        executor = self._kernel_parts(
            [ExplodingCapability("Alpha", ["s1"])],
            [FakeProvider("P1", ["s1"])])
        out = executor.execute(_mission("Alpha"))
        assert out.state.value == "failed"
        assert "boom during execution" in (out.error or "")
        # الاختياران نجحا — والدليل باقٍ في النتيجة الفاشلة
        assert len(out.decision_records) == 2
        assert all(r.status == "selected" for r in out.decision_records)


class TestAdapterBuildErrors:
    def test_supports_skill_failure_is_named_error_with_record(self):
        class ExplodingProvider:
            name = "Kaboom"
            priority = 1.0

            def supports_skill(self, skill):
                raise RuntimeError("supports_skill exploded")

        resolver = ProviderResolver(_prov_registry(ExplodingProvider()),
                                    _cap_registry())
        selection = resolver.resolve(FakeCapability("Alpha", ["s1"]))
        # خطأ مسمّى بالمرشح + دليل — لا استثناء بلا سجل
        assert selection.status.value == "error"
        assert "candidate Kaboom" in selection.reason
        assert selection.record.status == "error"
        assert selection.record.errors[0].startswith("candidate Kaboom:")

    def test_unconvertible_priority_is_named_error_with_record(self):
        class WeirdPriorityCapability(FakeCapability):
            def __init__(self):
                super().__init__("Alpha", ["s1"])
                self.priority = object()  # غير قابل للتحويل

        resolver = CapabilityResolver(_cap_registry(WeirdPriorityCapability()))
        selection = resolver.resolve(_mission("Alpha"))
        assert selection.status.value == "error"
        assert "candidate Alpha" in selection.reason
        assert selection.record.errors[0].startswith("candidate Alpha:")

    def test_build_error_does_not_hide_working_candidates(self):
        # موفّر يفشل بناؤه وآخر سليم — الخطأ مسمّى بالمرشح، والسليم
        # ظاهر في الدليل مُقيَّماً، لكن لا اختيار: المتعذر قد يكون الفائز
        # فتعذره يمنع إثبات النتيجة (سياسة معلنة لا تجاهل صامت)
        class ExplodingProvider:
            name = "Kaboom"
            priority = 1.0

            def supports_skill(self, skill):
                raise RuntimeError("nope")

        resolver = ProviderResolver(
            _prov_registry(ExplodingProvider(), FakeProvider("P1", ["s1"])),
            _cap_registry())
        selection = resolver.resolve(FakeCapability("Alpha", ["s1"]))
        assert selection.status.value == "error"
        assert any(e.startswith("candidate Kaboom:")
                   for e in selection.record.errors)
        by_name = {c.name: c for c in selection.record.candidates}
        assert by_name["P1"].values_used["skill_match"] == 1.0
        assert "no-candidates-registered" not in selection.record.missing_info


class TestBatchPipelineHardening:
    def test_batch_decide_selects_best_coverage_specifically(self):
        from decision_pipeline import (DecisionPipeline, DecisionContext)
        pipeline = DecisionPipeline(
            _cap_registry(FakeCapability("Alpha", ["s1", "s2"])),
            _prov_registry(FakeProvider("P1", ["s1"]),
                           FakeProvider("P2", ["s1", "s2"])))
        result = pipeline.decide(DecisionContext(_mission("Alpha")))
        assert result.status.value == "selected"
        # سياسة الدُفعة ترتب بالتغطية — P2 تحديداً لا أيّاً كان
        assert result.provider == "P2"
        assert result.capability == "Alpha"

    def test_batch_empty_registries_named_gap_with_record(self):
        # لا مرشحين: لا خروج مبكر — القلب يوثق النقص المسمّى بنفسه
        from decision_pipeline import (DecisionPipeline, DecisionContext)
        pipeline = DecisionPipeline(_cap_registry(), _prov_registry())
        result = pipeline.decide(DecisionContext(_mission("Anything")))
        assert result.status.value == "failed"
        assert "no-candidates-registered" in result.records[0].missing_info
        assert result.records[0].status == "no_match"

    def test_batch_constraints_carried_and_declared(self):
        # القيود تصل طلب الدُفعة — وتُعلن غير مُقيَّمة في الدليل
        from decision_pipeline import (DecisionPipeline, DecisionContext)
        pipeline = DecisionPipeline(
            _cap_registry(FakeCapability("Alpha", ["s1"])),
            _prov_registry(FakeProvider("P1", ["s1"])))

        class MissionWithConstraints:
            capability = "Alpha"
            parameters = {"constraints": [{"max_cost": 5}]}

        result = pipeline.decide(DecisionContext(MissionWithConstraints()))
        assert result.status.value == "selected"
        for rec in result.records:
            assert rec.requested["constraints"] == [{"max_cost": 5}]
            assert any(m.startswith("constraints-not-evaluated")
                       for m in rec.missing_info)

    def test_first_provider_ranked_alternatives_follow_selection_rule(self):
        # P1 يدعم s2 وP2 يدعم s1 والمطلوب [s1,s2] — المختار P2 والترتيب
        # وفق قاعدة الاختيار (أول مهارة مدعومة) لا درجة التغطية وحدها
        request = DecisionRequest(kind="provider", required_skills=["s1", "s2"])
        candidates = [
            DecisionCandidate(name="P1", offered_skills=["s2"]),
            DecisionCandidate(name="P2", offered_skills=["s1"])]
        record = DECISION_CORE.evaluate(
            request, candidates, FIRST_PROVIDER_POLICY,
            decision_id="d1", timestamp=AT.isoformat())
        assert record.selected == "P2"
        assert record.ranked_alternatives == ["P2", "P1"]
        assert record.tie_break == "first-required-skill-then-registration-order"

    def test_result_to_dict_serializes_records_success_and_failure(self):
        import json
        from decision_pipeline import (DecisionPipeline, DecisionContext)
        pipeline = DecisionPipeline(
            _cap_registry(FakeCapability("Alpha", ["s1", "s2"])),
            _prov_registry(FakeProvider("P1", ["s1"]),
                           FakeProvider("P2", ["s1", "s2"])))
        ok = pipeline.decide(DecisionContext(_mission("Alpha")))
        payload = ok.to_dict()
        assert payload["records"] == [r.to_dict() for r in ok.records]
        json.dumps(payload)

        bad = DecisionPipeline(_cap_registry(), _prov_registry()).decide(
            DecisionContext(_mission("Anything")))
        payload = bad.to_dict()
        assert payload["records"] == [r.to_dict() for r in bad.records]
        json.dumps(payload)

    def test_constraints_with_no_required_skills_still_declared(self):
        # قيود مع قائمة مهارات فارغة — النقص المسمّى لا يُخفى بالفرع المبكر
        request = DecisionRequest(kind="provider", required_skills=[],
                                   constraints=[{"c": "x"}])
        record = DECISION_CORE.evaluate(
            request, [DecisionCandidate(name="P1", offered_skills=[])],
            LIVE_PROVIDER_POLICY, decision_id="d1", timestamp=AT.isoformat())
        # السلوك القديم محفوظ: الجميع 1.0 والاختيار بترتيب التسجيل —
        # لكن النقص المسمّى للقيود لا يُخفى بالفرع المبكر
        assert record.status == "selected"
        assert record.selected == "P1"
        assert any(m.startswith("constraints-not-evaluated")
                   for m in record.missing_info)


# ---------------------------------------------------------------------------
# جولة المراجعة الرابعة — التوافق مع الأصل مثبتاً + مسارات الأخطاء
# ---------------------------------------------------------------------------

class TestBatchCompatibilityWithHead:
    def test_exact_name_conditional_eligibility_preserved(self):
        # الحالة الكاشفة: الأصل يحصر المنافسة في المطابقة التامة —
        # فالأولوية 10 لا تُغلب المطابقة التامة (لا تقريب أوزان)
        from decision_pipeline import (DecisionPipeline, DecisionContext)
        cap_hi = FakeCapability("AlphaExtra", [], priority=10.0)
        cap_exact = FakeCapability("Alpha", [], priority=0.0)
        pipeline = DecisionPipeline(
            _cap_registry(cap_exact, cap_hi), _prov_registry())
        result = pipeline.decide(DecisionContext(_mission("Alpha")))
        # (لا موفّرين مسجلين فالمرحلة الثانية تفشل — اختيار القدرة مثبت
        # في سجلها) الاستبعاد مسمّى بأثره في الدليل
        rec = result.records[0]
        assert rec.status == "selected"
        assert rec.selected == "Alpha"
        excluded = next(c for c in rec.candidates
                        if c.name == "AlphaExtra")
        assert excluded.exclusion_reason == \
            "not-an-exact-name-match-while-exact-available"

    def test_provider_full_support_conditional_eligibility(self):
        # الأصل: إن وُجد موفّر يدعم كل المهارات فالمنافسة محصورة فيهم
        from decision_pipeline import (DecisionPipeline, DecisionContext)
        pipeline = DecisionPipeline(
            _cap_registry(FakeCapability("Alpha", ["s1", "s2"])),
            _prov_registry(FakeProvider("Partial", ["s1"], priority=10.0),
                           FakeProvider("Full", ["s1", "s2"], priority=0.0)))
        result = pipeline.decide(DecisionContext(_mission("Alpha")))
        assert result.provider == "Full"
        rec = result.records[1]
        # المستبعد بفحص all() ظاهر في الدليل بمسوّغ وحدود استعلامه —
        # «لم يُسأل بعد الفحص» لا تساوي «غير مدعوم»
        excluded = next(c for c in rec.candidates if c.name == "Partial")
        assert excluded.exclusion_reason == "did-not-pass-all-skills-filter"
        # فحص all(): سأل s1 (مدعومة) ثم s2 (غير مدعومة → وقف) — كحدود الأصل
        assert excluded.values_used["query_stages"]["filtering"] == \
            ["s1", "s2"]
        assert excluded.values_used["note"] == "not-queried-beyond-filter"

    def test_batch_capability_scoring_is_jaccard_not_ladder(self):
        # حساب الدُبعة الأصلي: جاكار مع تجاوز الاسم التام — لا سلّم
        # أسماء المسار الحي. بلا مطابقة تامة وبلا مهارات: الجميع 1.0
        # والأولوية تحكم (سلوك الأصل حرفياً)
        from decision_pipeline import (DecisionPipeline, DecisionContext)
        pipeline = DecisionPipeline(
            _cap_registry(FakeCapability("Beta", [], priority=1.0),
                          FakeCapability("Gamma", [], priority=9.0)),
            _prov_registry())
        result = pipeline.decide(DecisionContext(_mission("Alpha")))
        rec = result.records[0]
        # الأولوية تحكم — كالأصل (بلا مطابقة تامة وبلا مهارات: الجميع
        # 1.0 والترتيب بالأولوية)؛ الاختيار مثبت في سجل القدرة
        assert rec.status == "selected"
        assert rec.selected == "Gamma"
        by_name = {c.name: c for c in rec.candidates}
        assert by_name["Beta"].values_used["skill_match"] == 1.0
        assert by_name["Beta"].values_used["scoring"] == \
            "jaccard-exact-override"

    def test_batch_provider_ranking_by_coverage_only(self):
        # المُقيّم الأصلي ثبّت أولوية الموفّر 1.0 دائماً — فالترتيب
        # بالتغطية وحدها؛ أولوية 10 لا تُغلب تغطية أعلى
        from decision_pipeline import (DecisionPipeline, DecisionContext)
        pipeline = DecisionPipeline(
            _cap_registry(FakeCapability("Alpha", ["s1", "s2"])),
            _prov_registry(FakeProvider("HiPri", ["s1"], priority=10.0),
                           FakeProvider("FullCov", ["s1", "s2"],
                                        priority=0.0)))
        result = pipeline.decide(DecisionContext(_mission("Alpha")))
        assert result.provider == "FullCov"


class TestBatchAndEngineErrorRecords:
    def test_batch_exploding_provider_produces_named_provider_record(self):
        # موفّر متفجر عبر DecisionPipeline.decide نفسه: سجل القدرة
        # محفوظ وسجل تعذر الموفّر مسمّى بالمرشح — لا استثناء بلا سجل
        from decision_pipeline import (DecisionPipeline, DecisionContext)

        class ExplodingProvider:
            name = "Kaboom"
            priority = 1.0

            def supports_skill(self, skill):
                raise RuntimeError("supports_skill exploded")

        pipeline = DecisionPipeline(
            _cap_registry(FakeCapability("Alpha", ["s1"])),
            _prov_registry(ExplodingProvider()))
        result = pipeline.decide(DecisionContext(_mission("Alpha")))
        assert result.status.value == "failed"
        assert [r.policy_id for r in result.records] == \
            ["pipeline-capability-selection", "pipeline-provider-selection"]
        prov_rec = result.records[1]
        assert prov_rec.status == "error"
        assert prov_rec.errors[0].startswith("candidate Kaboom:")
        assert "no-candidates-registered" not in prov_rec.missing_info

    def test_old_engine_failure_carries_record(self):
        # فشل المحرك القديم لا يُسقط الدليل — متاح في النتيجة (إضافة
        # متوافقة على Result)
        class Ctx:
            mission = _mission("Alpha")

        engine = DecisionEngine(
            _cap_registry(FakeCapability("Alpha", [])),
            _prov_registry(FakeProvider("P1", ["s1"])))
        result = engine.decide(Ctx())
        assert result.status.value == "failure"
        assert result.error == "No provider found for skills: []"
        assert result.record is not None
        assert result.record.status == "no_match"

    def test_mission_result_serializes_records_success_and_failure(self):
        import json

        class ExplodingCapability(FakeCapability):
            def execute(self, parameters):
                raise RuntimeError("boom")

        from events import EventBus
        from pipeline import ExecutionPipeline
        from mission_engine import MissionExecutor

        def _executor(caps, provs):
            return MissionExecutor(ExecutionPipeline(
                EventBus(), CapabilityResolver(_cap_registry(*caps)),
                ProviderResolver(_prov_registry(*provs), _cap_registry())))

        ok = _executor([FakeCapability("Alpha", ["s1"])],
                       [FakeProvider("P1", ["s1"])]).execute(_mission("Alpha"))
        assert ok.state.value == "completed"
        payload = ok.to_dict()
        assert payload["decision_records"] == \
            [r.to_dict() for r in ok.decision_records]
        json.dumps(payload)

        bad = _executor([ExplodingCapability("Alpha", ["s1"])],
                        [FakeProvider("P1", ["s1"])]).execute(
                            _mission("Alpha"))
        assert bad.state.value == "failed"
        payload = bad.to_dict()
        assert payload["decision_records"] == \
            [r.to_dict() for r in bad.decision_records]
        json.dumps(payload)


# ---------------------------------------------------------------------------
# جولة المراجعة الخامسة — التوافق الموضعي وحدود الحساب
# ---------------------------------------------------------------------------

class TestRound5Compatibility:
    def test_result_positional_call_unchanged(self):
        # الاستدعاء الموضعي القديم: (status, data, error, timestamp) —
        # الحقل الجديد بعده فلا يزاحمه
        from shared import Result, ResultStatus
        from datetime import datetime, timezone
        at = datetime(2026, 10, 22, 12, 0, tzinfo=timezone.utc)
        r = Result(ResultStatus.SUCCESS, {"x": 1}, "err", at)
        assert r.timestamp == at
        assert r.data == {"x": 1}
        assert r.error == "err"
        assert r.record is None

    def test_eligibility_excludes_before_evaluation(self):
        # مطابقة تامة موجودة → المنافس خارجها لا يُقيَّم أصلاً (كالمجمّع
        # الأصلي): أولويته غير القابلة للتحويل لا تفشل القرار
        from decision_pipeline import (DecisionPipeline, DecisionContext)
        pipeline = DecisionPipeline(
            _cap_registry(FakeCapability("Alpha", ["s1"], priority=1.0),
                          FakeCapability("AlphaExtra", ["s1"],
                                         priority=object())),
            _prov_registry(FakeProvider("P1", ["s1"])))
        result = pipeline.decide(DecisionContext(_mission("Alpha")))
        assert result.status.value == "selected"
        assert result.capability == "Alpha"
        extra = next(c for c in result.records[0].candidates
                     if c.name == "AlphaExtra")
        assert extra.excluded
        assert not extra.build_failed  # لم يُقيَّم أصلاً — لا تعذر
        assert extra.values_used["excluded_by"] == \
            "conditional-eligibility-before-evaluation"

    def test_batch_provider_priority_is_constant_contribution(self):
        # مسار الدُبعة الأصلي: total = skill*0.9 + 0.1 — أولوية الموفّر
        # غير مقروءة. الداعم الكامل درجته 1.0 بالضبط، وموفّر بأولوية غير
        # قابلة للتحويل صالح (كما كان)
        from decision_pipeline import (DecisionPipeline, DecisionContext)
        pipeline = DecisionPipeline(
            _cap_registry(FakeCapability("Alpha", ["s1", "s2"])),
            _prov_registry(FakeProvider("Full", ["s1", "s2"],
                                       priority=object())))
        result = pipeline.decide(DecisionContext(_mission("Alpha")))
        assert result.status.value == "selected"
        full = next(c for c in result.records[1].candidates
                    if c.name == "Full")
        assert full.score.total == 1.0
        assert full.values_used["priority_basis"] == "constant-1.0-not-read"

    def test_capability_build_error_prevents_selection(self):
        # قدرة مطلوبة أولويتها تتعذر وقدرة أخرى سليمة — لا نجاح بالباقية:
        # المتعذرة قد تكون الفائزة فالتعذر يمنع إثبات النتيجة
        class WeirdPriorityCapability(FakeCapability):
            def __init__(self, name, skills):
                super().__init__(name, skills)
                self.priority = object()

        resolver = CapabilityResolver(_cap_registry(
            WeirdPriorityCapability("Alpha", ["s1"]),
            FakeCapability("AlphaExtra", ["s1"])))
        selection = resolver.resolve(_mission("Alpha"))
        assert selection.status.value == "error"
        assert selection.record.selected is None
        assert selection.record.errors[0].startswith("candidate Alpha:")

    def test_all_candidates_fail_to_build_no_registration_claim(self):
        # تعذر بناء الجميع — النقص مسمّى بالخطأ لا بادعاء غياب التسجيل
        class ExplodingProvider:
            name = "Boom"
            priority = 1.0

            def supports_skill(self, skill):
                raise RuntimeError("nope")

        resolver = ProviderResolver(_prov_registry(ExplodingProvider()),
                                    _cap_registry())
        selection = resolver.resolve(FakeCapability("Alpha", ["s1"]))
        assert selection.status.value == "error"
        assert "no-candidates-registered" not in \
            selection.record.missing_info
        failed = [c for c in selection.record.candidates if c.build_failed]
        assert len(failed) == 1
        assert failed[0].build_error.startswith("candidate-building:")

    def test_failed_candidate_present_in_evidence_with_prior_evaluations(self):
        # فشل تقييم المرشح الثاني داخل القلب: الأول محفوظ التقييم
        # والمتعذر في الدليل بموضع فشله — لا يختفي
        from decision_pipeline import DecisionCandidate, DecisionRequest
        from decision_pipeline import LIVE_PROVIDER_POLICY
        record = DECISION_CORE.evaluate(
            DecisionRequest(kind="provider", required_skills=["s1"]),
            [DecisionCandidate(name="ok", offered_skills=["s1"]),
             DecisionCandidate(name="x", offered_skills=["s1"],
                               priority=object())],
            LIVE_PROVIDER_POLICY, decision_id="d1", timestamp=AT.isoformat())
        assert record.status == "error"
        by_name = {c.name: c for c in record.candidates}
        assert by_name["ok"].score is not None  # تقييمه محفوظ
        assert by_name["x"].build_failed
        assert by_name["x"].build_error.startswith("evaluation:")
        assert record.selected is None

    def test_engine_build_error_visible_in_failure(self):
        # المحرك القديم نفسه: موفّر متفجر قبل سليم — رسالة التعذر تسمّي
        # الخطأ (الرسالة العامة لحالة عدم المطابقة الحقيقية فقط)
        class ExplodingProvider:
            name = "Kaboom"
            priority = 1.0

            def supports_skill(self, skill):
                raise RuntimeError("supports_skill exploded")

        class Ctx:
            mission = _mission("Alpha")

        engine = DecisionEngine(
            _cap_registry(FakeCapability("Alpha", ["s1"])),
            _prov_registry(ExplodingProvider(),
                           FakeProvider("P1", ["s1"])))
        result = engine.decide(Ctx())
        assert result.status.value == "failure"
        assert "candidate Kaboom" in result.error
        # حدود المحرك الأصلي: استعلام مهارةً مهارةً — الخطأ مسمّى بالمهارة
        assert "stage=skill-query(s1)" in result.error
        # الرسالة القديمة محفوظة لحالة no_match الحقيقية
        engine2 = DecisionEngine(
            _cap_registry(FakeCapability("Alpha", ["s1"])),
            _prov_registry(FakeProvider("P1", ["other"])))
        result2 = engine2.decide(Ctx())
        assert result2.error == "No provider found for skills: ['s1']"


# ---------------------------------------------------------------------------
# جولة المراجعة السادسة — حدود القراءة والاستعلام
# ---------------------------------------------------------------------------

class TestRound6ReadAndQueryBoundaries:
    def test_priority_never_read_when_unused(self):
        # خاصية ترفع عند القراءة: السياسات غير المستهلكة للأولوية لا
        # تقرأها أصلاً (قراءة getattr نفسها فشل) — القرار سليم
        class RaisingPriorityProvider:
            name = "P1"
            supports_skill = None

            def __init__(self):
                self._s = {"s1"}

            @property
            def priority(self):
                raise RuntimeError("priority read exploded")

            def _supports(self, skill):
                return skill in self._s

        RaisingPriorityProvider.supports_skill = \
            lambda self, s: self._supports(s)

        class Ctx:
            mission = _mission("Alpha")

        # المحرك القديم (first-provider: الأولوية غير المستهلكة)
        engine = DecisionEngine(
            _cap_registry(FakeCapability("Alpha", ["s1"])),
            _prov_registry(RaisingPriorityProvider()))
        result = engine.decide(Ctx())
        assert result.status.value == "success"
        assert result.data.provider == "P1"

        # مسار الدُبعة (مساهمة ثابتة: الأولوية غير المقروءة)
        from decision_pipeline import (DecisionPipeline, DecisionContext)
        pipeline = DecisionPipeline(
            _cap_registry(FakeCapability("Alpha", ["s1"])),
            _prov_registry(RaisingPriorityProvider()))
        result2 = pipeline.decide(DecisionContext(_mission("Alpha")))
        assert result2.status.value == "selected"
        assert result2.provider == "P1"

    def test_live_resolver_empty_skills_never_converts_priority(self):
        # بلا مهارات مطلوبة: فرع «الجميع 1.0» لا يقرأ الأولوية أصلاً —
        # أولوية غير قابلة للتحويل لا تفشل الحل
        resolver = ProviderResolver(
            _prov_registry(FakeProvider("P1", ["s1"], priority=object())),
            _cap_registry())
        selection = resolver.resolve(FakeCapability("Alpha", []))
        assert selection.status.value == "success"
        assert selection.provider_name == "P1"

    def test_engine_stops_querying_after_first_support(self):
        # المحرك الأصلي: مهارةً مهارةً — الموفّر الذي يدعم s1 يُختار
        # ولا يُسأل عن s2 أصلاً (رفعها عند السؤال لا يحدث)
        class SelectiveProvider:
            name = "P1"
            priority = 1.0

            def supports_skill(self, skill):
                if skill == "s2":
                    raise RuntimeError("s2 query exploded")
                return skill == "s1"

        class Ctx:
            mission = _mission("Alpha")

        engine = DecisionEngine(
            _cap_registry(FakeCapability("Alpha", ["s1", "s2"])),
            _prov_registry(SelectiveProvider()))
        result = engine.decide(Ctx())
        assert result.status.value == "success"
        assert result.data.provider == "P1"
        # والمهارات غير المسؤول عنها بعد الحسم معلنة لا مختفية
        assert any(m.startswith("skills-not-queried-after-decision")
                   for m in result.data.record.missing_info)

    def test_batch_short_circuits_on_first_unsupported(self):
        # فحص all() الأصلي يقف عند أول False — لا يُسأل عن مهارة لاحقة
        # (رفعها عند السؤال لا يحدث أصلاً)
        class FalseThenExplodingProvider:
            name = "P1"
            priority = 1.0
            _queried = []

            def supports_skill(self, skill):
                FalseThenExplodingProvider._queried.append(skill)
                if skill == "s2":
                    raise RuntimeError("s2 query exploded")
                return False  # s1 غير مدعوم — القفز فوري

        from decision_pipeline import (DecisionPipeline, DecisionContext)
        pipeline = DecisionPipeline(
            _cap_registry(FakeCapability("Alpha", ["s1", "s2"])),
            _prov_registry(FalseThenExplodingProvider(),
                           FakeProvider("P2", ["s1", "s2"])))
        result = pipeline.decide(DecisionContext(_mission("Alpha")))
        assert result.status.value == "selected"
        assert result.provider == "P2"
        assert FalseThenExplodingProvider._queried == ["s1"]

    def test_serialized_evidence_includes_build_failure(self):
        import json
        from decision_pipeline import DecisionCandidate, DecisionRequest
        from decision_pipeline import LIVE_PROVIDER_POLICY
        record = DECISION_CORE.evaluate(
            DecisionRequest(kind="provider", required_skills=["s1"]),
            [DecisionCandidate(name="ok", offered_skills=["s1"]),
             DecisionCandidate(name="x", offered_skills=["s1"],
                               priority=object())],
            LIVE_PROVIDER_POLICY, decision_id="d1", timestamp=AT.isoformat())
        payload = json.loads(json.dumps(record.to_dict()))
        by_name = {c["name"]: c for c in payload["candidates"]}
        assert by_name["x"]["build_failed"] is True
        assert by_name["x"]["build_error"].startswith("evaluation:")

    def test_candidates_after_failure_preserved_in_order(self):
        # [ok, x, later]: تعذر الثاني لا يُخفي الثالث — الجميع في الدليل
        # بترتيبهم، والمتعذر مميز عن المُقيَّم
        from decision_pipeline import DecisionCandidate, DecisionRequest
        from decision_pipeline import LIVE_PROVIDER_POLICY
        record = DECISION_CORE.evaluate(
            DecisionRequest(kind="provider", required_skills=["s1"]),
            [DecisionCandidate(name="ok", offered_skills=["s1"]),
             DecisionCandidate(name="x", offered_skills=["s1"],
                               priority=object()),
             DecisionCandidate(name="later", offered_skills=["s1"])],
            LIVE_PROVIDER_POLICY, decision_id="d1", timestamp=AT.isoformat())
        assert record.status == "error"
        assert record.selected is None
        assert [c.name for c in record.candidates] == ["ok", "x", "later"]
        by_name = {c.name: c for c in record.candidates}
        assert by_name["ok"].score is not None
        assert by_name["later"].score is not None  # لم يختفِ
        assert by_name["x"].build_failed
        assert not by_name["x"].excluded  # ليس استبعاد أهلية

    def test_failed_stub_keeps_registration_order(self):
        # متفجر أولاً ثم سليم — المتعذر في الدليل بترتيب تسجيله لا
        # ملحقاً بالسليم
        class ExplodingProvider:
            name = "Kaboom"
            priority = 1.0

            def supports_skill(self, skill):
                raise RuntimeError("nope")

        resolver = ProviderResolver(
            _prov_registry(ExplodingProvider(), FakeProvider("P1", ["s1"])),
            _cap_registry())
        selection = resolver.resolve(FakeCapability("Alpha", ["s1"]))
        assert selection.status.value == "error"
        assert [c.name for c in selection.record.candidates] == \
            ["Kaboom", "P1"]
        by_name = {c.name: c for c in selection.record.candidates}
        assert by_name["Kaboom"].build_failed
        assert by_name["P1"].score is not None

    def test_batch_score_recomputable_from_snapshot(self):
        # الدرجة قابلة لإعادة الحساب من القيم المسجلة ولقطة السياسة —
        # لا حرفية خفية في الحساب
        from decision_pipeline import (DecisionPipeline, DecisionContext)
        pipeline = DecisionPipeline(
            _cap_registry(FakeCapability("Alpha", ["s1", "s2"])),
            _prov_registry(FakeProvider("Full", ["s1", "s2"])))
        result = pipeline.decide(DecisionContext(_mission("Alpha")))
        rec = result.records[1]
        full = next(c for c in rec.candidates if c.name == "Full")
        snapshot = rec.policy_snapshot
        w = snapshot["weights"]
        # total = skill_match*0.9 + 1.0(ثابتة)*0.1 — من اللقطة والقيم
        recomputed = (full.values_used["skill_match"] * w["skill"]
                      + 1.0 * w["priority_weight"])
        assert full.score.total == pytest.approx(recomputed)
        assert full.values_used["priority_basis"] == "constant-1.0-not-read"


# ---------------------------------------------------------------------------
# جولة المراجعة السابعة — دليل الاستعلام المؤجل ومرحلتا الدُبعة
# ---------------------------------------------------------------------------

class TestRound7LazyQueryEvidence:
    def test_lazy_query_evidence_through_engine_serialized(self):
        # عبر المحرك القديم نفسه + تسلسل JSON: لكل مرشح المهارات التي
        # سُئل عنها فعلاً وإجاباتها، والمرشح الذي حسم والمهارة الحاسمة
        import json
        class Ctx:
            mission = _mission("Alpha")

        engine = DecisionEngine(
            _cap_registry(FakeCapability("Alpha", ["s1", "s2"])),
            _prov_registry(FakeProvider("P1", ["s1"]),
                           FakeProvider("P2", ["s1", "s2"])))
        result = engine.decide(Ctx())
        assert result.status.value == "success"
        rec = result.data.record
        payload = json.loads(json.dumps(rec.to_dict()))
        by_name = {c["name"]: c for c in payload["candidates"]}
        # الحاسم: سُئل s1 فأجاب بدعم — والمهارة الحاسمة مسجلة
        assert by_name["P1"]["values_used"]["decided_by_skill"] == "s1"
        assert by_name["P1"]["values_used"]["query_answers"]["s1"] is True
        # غير المسؤولين: لم يُسألوا — ظاهرون لا مختفون ولا مُقيَّمين
        assert by_name["P2"]["values_used"].get("skills_queried", []) == []
        # والمهارات المتبقية بعد الحسم معلنة (s2 لم تُسأل بعد الحسم)
        assert any(m.startswith("skills-not-queried-after-decision:P1")
                   for m in payload["missing_info"])

    def test_no_remaining_skills_no_claim(self):
        # موفّر واحد ومهارة واحدة مدعومة — لا استعلامات متبقية فلا ادعاء
        class Ctx:
            mission = _mission("Alpha")

        engine = DecisionEngine(
            _cap_registry(FakeCapability("Alpha", ["s1"])),
            _prov_registry(FakeProvider("P1", ["s1"])))
        result = engine.decide(Ctx())
        assert result.status.value == "success"
        assert not any(m.startswith("skills-not-queried-after-decision")
                       for m in result.data.record.missing_info)

    def test_lazy_query_failure_marks_the_candidate(self):
        # فشل الاستعلام يوسم المرشح نفسه بالتعذر ومرحلة skill-query —
        # لا خطأ عاماً فقط
        class ExplodingOnQuery:
            name = "Kaboom"
            priority = 1.0

            def supports_skill(self, skill):
                raise RuntimeError("query exploded")

        class Ctx:
            mission = _mission("Alpha")

        engine = DecisionEngine(
            _cap_registry(FakeCapability("Alpha", ["s1"])),
            _prov_registry(ExplodingOnQuery(), FakeProvider("P1", ["s1"])))
        result = engine.decide(Ctx())
        assert result.status.value == "failure"
        rec = result.record
        kaboom = next(c for c in rec.candidates if c.name == "Kaboom")
        assert kaboom.build_failed
        assert "skill-query(s1)" in kaboom.build_error
        assert "stage=skill-query(s1)" in result.error

    def test_batch_fallback_full_coverage_queries(self):
        # لا داعم كامل → عودة الأصل إلى الجميع والتقييم يستعلم كل المهارات:
        # من لا يدعم s1 قد يدعم s2 وs3 — التغطية الحقيقية تحكم، لا بادئة
        # الفحص. [s1,s2,s3]: A يدعم s2,s3 (تغطية 2/3) وB يدعم s1 فقط
        # (1/3) — A يفوز كما في الأصل
        from decision_pipeline import (DecisionPipeline, DecisionContext)

        class QueryCounter:
            counts = {}

        class PartialA:
            name = "A"
            priority = 1.0

            def supports_skill(self, skill):
                QueryCounter.counts.setdefault("A", []).append(skill)
                return skill in {"s2", "s3"}

        class OnlyS1:
            name = "B"
            priority = 1.0

            def supports_skill(self, skill):
                QueryCounter.counts.setdefault("B", []).append(skill)
                return skill == "s1"

        pipeline = DecisionPipeline(
            _cap_registry(FakeCapability("Alpha", ["s1", "s2", "s3"])),
            _prov_registry(PartialA(), OnlyS1()))
        result = pipeline.decide(DecisionContext(_mission("Alpha")))
        assert result.status.value == "selected"
        assert result.provider == "A"
        rec = result.records[1]
        by_name = {c.name: c for c in rec.candidates}
        # A: فحص (s1 فشل) + تقييم كامل (كل المهارات)
        assert by_name["A"].values_used["query_stages"]["filtering"] == ["s1"]
        assert by_name["A"].values_used["query_stages"]["evaluation"] == \
            ["s1", "s2", "s3"]
        assert by_name["A"].values_used["skill_match"] == pytest.approx(2 / 3)
        # B: فحصه وقف عند s2 غير المدعومة (حدود all()) ثم تقييم كامل
        assert by_name["B"].values_used["query_stages"]["filtering"] == \
            ["s1", "s2"]
        assert by_name["B"].values_used["query_stages"]["evaluation"] == \
            ["s1", "s2", "s3"]
        # الاستعلامات فعلاً كاملة في مرحلة التقييم — لا بادئة فحص فقط
        assert QueryCounter.counts["A"] == ["s1", "s1", "s2", "s3"]

    def test_batch_eligibility_excluded_priority_never_read(self):
        # المستبعد بالأهلية (مطابقة تامة موجودة) لا تُقرأ أولويته أصلاً —
        # خاصية ترفع عند القراءة لا تفشل القرار (كما بعد ترشيح الأصل)
        class RaisingPriorityCap(FakeCapability):
            def __init__(self, name, skills):
                self.name = name
                self.skills = list(skills)  # بلا أولوية أصلاً

            @property
            def priority(self):
                raise RuntimeError("priority read exploded")

        from decision_pipeline import (DecisionPipeline, DecisionContext)
        pipeline = DecisionPipeline(
            _cap_registry(FakeCapability("Alpha", ["s1"], priority=1.0),
                          RaisingPriorityCap("AlphaExtra", ["s1"])),
            _prov_registry(FakeProvider("P1", ["s1"])))
        result = pipeline.decide(DecisionContext(_mission("Alpha")))
        assert result.status.value == "selected"
        assert result.capability == "Alpha"
        extra = next(c for c in result.records[0].candidates
                     if c.name == "AlphaExtra")
        assert extra.excluded
        assert not extra.build_failed

    def test_live_capability_raising_priority_named_error(self):
        # قدرة حية خاصية أولويتها ترفع: ERROR بدليل مرشح مسمّى — لا استثناء
        class RaisingPriorityCap:
            def __init__(self, name, skills):
                self.name = name
                self.skills = list(skills)

            @property
            def priority(self):
                raise RuntimeError("priority read exploded")

        resolver = CapabilityResolver(_cap_registry(
            RaisingPriorityCap("Alpha", ["s1"])))
        selection = resolver.resolve(_mission("Alpha"))
        assert selection.status.value == "error"
        assert selection.record.errors[0].startswith("candidate Alpha:")
        failed = next(c for c in selection.record.candidates
                      if c.name == "Alpha")
        assert failed.build_failed


# ---------------------------------------------------------------------------
# جولة المراجعة الثامنة — المرحلتان داخل القلب وحالات الدليل
# ---------------------------------------------------------------------------

class TestRound8StagesInCore:
    def test_eligibility_rule_change_changes_competition(self):
        # قاعدة الأهلية المعلنة هي التي تحدد المنافسة — تغييرها يغيرها
        # فعلاً: بلا قاعدة لا ترشيح والجزئي منافس، وبها يُستبعد بالفحص
        from decision_pipeline import (DecisionPolicy, DecisionRequest,
                                        DECISION_CORE,
                                        PIPELINE_PROVIDER_POLICY)

        class Partial:
            name = "Partial"
            priority = 1.0

            def supports_skill(self, skill):
                return skill == "s1"

        class Full:
            name = "Full"
            priority = 1.0

            def supports_skill(self, skill):
                return True

        cands = [DecisionCandidate(name="Partial",
                                   skill_query=Partial().supports_skill),
                 DecisionCandidate(name="Full",
                                   skill_query=Full().supports_skill)]
        req = DecisionRequest(kind="provider",
                              required_skills=["s1", "s2"], constraints=[])
        ts = "2026-01-01T00:00:00Z"

        with_rule = DECISION_CORE.evaluate(
            req, cands, PIPELINE_PROVIDER_POLICY, decision_id="d1",
            timestamp=ts)
        assert with_rule.status == "selected"
        assert with_rule.selected == "Full"
        partial = next(c for c in with_rule.candidates if c.name == "Partial")
        assert partial.excluded  # مستبعد بالفحص

        no_rule = DecisionPolicy(
            policy_id="no-eligibility", version="1", kind="provider",
            weights={"skill": 0.9, "constraint": 0.0, "priority": 1.0,
                     "constraint_weight": 0.0, "priority_weight": 0.1},
            rules={"provider_stages": "filter-then-evaluate",
                   "priority_contribution": "constant-1.0",
                   "tie_break": "stable-registration-order"})
        without = DECISION_CORE.evaluate(
            req, cands, no_rule, decision_id="d2", timestamp=ts)
        assert without.status == "selected"
        assert without.selected == "Full"  # تغطية أعلى تفوز بالترتيب
        partial2 = next(c for c in without.candidates
                        if c.name == "Partial")
        assert not partial2.excluded  # منافس — لا ترشيح بلا قاعدة
        assert partial2.score is not None  # مُقيَّم فعلاً

    def test_failed_provider_keeps_build_failed_not_excluded(self):
        # متعذر + كامل الدعم: المتعذر يبقى متعذراً بمرحلته — لا يُستبدل
        # بمستبعد بالفحص فيضيع وسم تعذره
        class Exploding:
            name = "Kaboom"
            priority = 1.0

            def supports_skill(self, skill):
                raise RuntimeError("query exploded")

        class Full:
            name = "Full"
            priority = 1.0

            def supports_skill(self, skill):
                return True

        from decision_pipeline import DecisionContext, DecisionPipeline
        pipeline = DecisionPipeline(
            _cap_registry(FakeCapability("Alpha", ["s1", "s2"])),
            _prov_registry(Exploding(), Full()))
        result = pipeline.decide(DecisionContext(_mission("Alpha")))
        # سلوك الأصل: استعلام الترشيح يرفع → الفحص فشل → decide فاشل.
        # والدليل كامل: المتعذر بوسم تعذره ومرحلته، وكامل الدعم مُقيَّم
        # ظاهر — ولا فائز مزعوم (المتعذر كان قد يجيز الفحص فلا يُثبت أحد)
        assert result.status.value == "failed"
        assert result.provider is None
        rec = result.records[1]
        kaboom = next(c for c in rec.candidates if c.name == "Kaboom")
        assert kaboom.build_failed
        assert not kaboom.excluded
        assert kaboom.values_used["failed_stage"] == "filtering"
        full = next(c for c in rec.candidates if c.name == "Full")
        assert full.score is not None

    def test_failed_partial_full_all_three_distinct_in_order(self):
        # متعذر + جزئي + كامل: الثلاثة في الدليل بترتيب تسجيلهم، مميزين
        # بحالاتهم، ولا مدخل معدوم — وسجل الموفّر محفوظ
        class Exploding:
            name = "Kaboom"
            priority = 1.0

            def supports_skill(self, skill):
                raise RuntimeError("query exploded")

        class Partial:
            name = "Partial"
            priority = 1.0

            def supports_skill(self, skill):
                return skill == "s1"

        class Full:
            name = "Full"
            priority = 1.0

            def supports_skill(self, skill):
                return True

        from decision_pipeline import DecisionContext, DecisionPipeline
        pipeline = DecisionPipeline(
            _cap_registry(FakeCapability("Alpha", ["s1", "s2"])),
            _prov_registry(Exploding(), Partial(), Full()))
        result = pipeline.decide(DecisionContext(_mission("Alpha")))
        # فاشل كالأصل (استعلام المتعذر يرفع) — والثلاثة في الدليل بترتيب
        # تسجيلهم مميزين بحالاتهم، وسجل الموفّر محفوظ
        assert result.status.value == "failed"
        assert len(result.records) == 2  # سجل الموفّر محفوظ
        rec = result.records[1]
        assert [c.name for c in rec.candidates] == \
            ["Kaboom", "Partial", "Full"]
        by_name = {c.name: c for c in rec.candidates}
        assert by_name["Kaboom"].build_failed and not by_name["Kaboom"].excluded
        assert by_name["Partial"].excluded and not by_name["Partial"].build_failed
        assert by_name["Full"].score is not None

    def test_evaluation_query_failure_after_filter_pass(self):
        # يجيز الفحص (True) ثم يرفع عند استعلام التقييم — سلوك الأصل:
        # مُقيّمه كان سيستعلم ويرفع → فشل مسمّى بالمرحلة، لا نجاح
        class PassesFilterExplodesAtEvaluation:
            # يجيز الفحص (استعلاماته True) ثم يرفع عند استعلامات التقييم
            # (الاستعلامات نفسها تعاد في مرحلة التقييم — العد يفرق)
            name = "Tricky"
            priority = 1.0
            _count = 0

            def supports_skill(self, skill):
                PassesFilterExplodesAtEvaluation._count += 1
                if PassesFilterExplodesAtEvaluation._count > 2:
                    raise RuntimeError("evaluation query exploded")
                return True

        from decision_pipeline import (DecisionPipeline, DecisionContext)
        pipeline = DecisionPipeline(
            _cap_registry(FakeCapability("Alpha", ["s1", "s2"])),
            _prov_registry(PassesFilterExplodesAtEvaluation()))
        result = pipeline.decide(DecisionContext(_mission("Alpha")))
        assert result.status.value == "failed"
        rec = result.records[1]
        tricky = next(c for c in rec.candidates if c.name == "Tricky")
        assert tricky.build_failed
        assert tricky.values_used["failed_stage"] == "evaluation-queries"
        assert any("stage=evaluation-queries" in e for e in rec.errors)

    def test_lazy_query_states_explicit(self):
        # حالة كل مرشح صريحة: لم يُستعلم (توقف) / استُعلم / حسم / تعذر —
        # والمحاولة الفاشلة مسجلة لا الناجحة وحدها
        import json
        class Ctx:
            mission = _mission("Alpha")

        engine = DecisionEngine(
            _cap_registry(FakeCapability("Alpha", ["s1"])),
            _prov_registry(FakeProvider("P1", ["s1"]),
                           FakeProvider("P2", ["s1"])))
        result = engine.decide(Ctx())
        assert result.status.value == "success"
        rec = result.data.record
        payload = json.loads(json.dumps(rec.to_dict()))
        by_name = {c["name"]: c for c in payload["candidates"]}
        # الحاسم: حسم — وغيره: لم يُستعلم بسبب التوقف (لا «غير مفحوص»
        # مطلقاً بعد الاستعلام)
        assert by_name["P1"]["values_used"]["query_state"] == "decided"
        assert by_name["P2"]["values_used"]["query_state"] == "not_queried"

    def test_lazy_failed_attempt_recorded(self):
        class ExplodingOnQuery:
            name = "Kaboom"
            priority = 1.0

            def supports_skill(self, skill):
                raise RuntimeError("query exploded")

        class Ctx:
            mission = _mission("Alpha")

        engine = DecisionEngine(
            _cap_registry(FakeCapability("Alpha", ["s1"])),
            _prov_registry(ExplodingOnQuery(), FakeProvider("P1", ["s1"])))
        result = engine.decide(Ctx())
        assert result.status.value == "failure"
        rec = result.record
        kaboom = next(c for c in rec.candidates if c.name == "Kaboom")
        # المحاولة الفاشلة مسجلة بالمهارة والخطأ
        assert kaboom.values_used["failed_query"]["skill"] == "s1"
        assert "RuntimeError" in kaboom.values_used["failed_query"]["error"]


# ---------------------------------------------------------------------------
# جولة المراجعة التاسعة — حماية الحساب المرحلي وحالة التعذر
# ---------------------------------------------------------------------------

class TestRound9StageCalculationFailure:
    def test_scoring_failure_in_stages_path_named_error(self):
        # فشل قاعدة حسابية في المسار المرحلي نفسه: خطأ مسمّى بالمرشح
        # ومرحلته — لا استثناء يسقط السجل كله. سياسته المرحلية تقرأ
        # الأولوية (على خلاف سياسة الدُبعة الثابتة) فيفشل تحويلها داخل
        # الحساب بعد نجاح الاستعلامات
        from decision_pipeline import (DecisionPolicy, DecisionRequest,
                                        DECISION_CORE)

        class WeirdPriorityFull:
            name = "Weird"

            def supports_skill(self, skill):
                return True  # يجيز الفحص ويجيب كل استعلامات التقييم

        policy = DecisionPolicy(
            policy_id="stages-reading-priority", version="1",
            kind="provider",
            weights={"skill": 0.9, "constraint": 0.0, "priority": 1.0,
                     "constraint_weight": 0.0, "priority_weight": 0.1},
            rules={"eligibility": "supports-all-if-available",
                   "provider_stages": "filter-then-evaluate",
                   "tie_break": "stable-registration-order"})
        record = DECISION_CORE.evaluate(
            DecisionRequest(kind="provider", required_skills=["s1"],
                            constraints=[]),
            [DecisionCandidate(name="Weird",
                                priority=object(),  # يفشل تحويله في الحساب
                                skill_query=WeirdPriorityFull().supports_skill)],
            policy, decision_id="d1", timestamp=AT.isoformat())
        # استثناء الحساب محمي: سجل كامل بخطأ مسمّى بالمرشح ومرحلته —
        # لا استثناء يهرب ولا سجل يسقط
        assert record.status == "error"
        assert record.selected is None
        weird = next(c for c in record.candidates if c.name == "Weird")
        assert weird.build_failed
        assert weird.values_used["failed_stage"] == "evaluation"
        assert any("stage=evaluation" in e for e in record.errors)
        # استعلامات المرحلتين محفوظة رغم فشل الحساب
        assert weird.values_used["filter_queried"] == ["s1"]
        assert weird.values_used["evaluation_queried"] == ["s1"]

    def test_query_state_failed_after_partial_success(self):
        # إجابة ناجحة عن مهارة ثم تعذر الاستعلام عن التالية: الحالة
        # «failed» لا «queried» — والمحاولة الفاشلة مسجلة بمهارتها
        import json

        class QueriedThenFails:
            # قاعدة الخروج المبكر: أول إجابة ناجحة (True) تحسم — فالإجابة
            # الأولى هنا سالبة (استُعلم وفُحص) والثانية تتعذر
            name = "Tricky"
            priority = 1.0
            _count = 0

            def supports_skill(self, skill):
                QueriedThenFails._count += 1
                if QueriedThenFails._count == 1:
                    return False  # s1 استُعلم وأجاب سلباً
                raise RuntimeError("second query exploded")  # s2 تعذر

        class Ctx:
            mission = _mission("Alpha")

        engine = DecisionEngine(
            _cap_registry(FakeCapability("Alpha", ["s1", "s2"])),
            _prov_registry(QueriedThenFails()))
        result = engine.decide(Ctx())
        assert result.status.value == "failure"
        rec = result.record
        payload = json.loads(json.dumps(rec.to_dict()))
        tricky = next(c for c in payload["candidates"]
                      if c["name"] == "Tricky")
        assert tricky["values_used"]["query_state"] == "failed"
        # الاستعلام السابق الناجح محفوظ بإجابته — والمحاولة الفاشلة
        # مسجلة بمهارتها بعده (لا تُمحى بالتعذر)
        assert tricky["values_used"]["query_answers"]["s1"] is False
        assert tricky["values_used"]["failed_query"]["skill"] == "s2"


# ---------------------------------------------------------------------------
# جولة المراجعة العاشرة — قراءة المهارات بعد الأهلية
# ---------------------------------------------------------------------------

class TestRound10SkillsReadAfterEligibility:
    def test_batch_excluded_competitor_skills_never_read(self):
        # الأصل يحصر المنافسة في المطابقة التامة قبل قراءة بيانات
        # المنافسين — فخاصية مهارات ترفع في منافسٍ مستبعد لا تفشل القرار
        class RaisingSkillsCap:
            def __init__(self, name):
                self.name = name
                self.priority = 1.0
                self.skills_read = False

            @property
            def skills(self):
                RaisingSkillsCap.read_flag = True
                raise RuntimeError("skills read exploded")

        from decision_pipeline import DecisionContext, DecisionPipeline
        extra = RaisingSkillsCap("AlphaExtra")
        RaisingSkillsCap.read_flag = False
        pipeline = DecisionPipeline(
            _cap_registry(FakeCapability("Alpha", ["s1"], priority=1.0),
                          extra),
            _prov_registry(FakeProvider("P1", ["s1"])))
        result = pipeline.decide(DecisionContext(_mission("Alpha")))
        assert result.status.value == "selected"
        assert result.capability == "Alpha"
        # مهارات المنافس المستبعد لم تُقرأ أصلاً
        assert RaisingSkillsCap.read_flag is False
        # وبياناته في الدليل: مستبعد بالأهلية — بلا ادعاء فحص مهاراته
        excluded = next(c for c in result.records[0].candidates
                        if c.name == "AlphaExtra")
        assert excluded.excluded
        # لا ادعاء فحص مهارات لمن لم تُقرأ — بالمفاتيح المستخدمة فعلاً
        assert "offered_skills_read" not in excluded.values_used
        assert "skills_source" not in excluded.values_used

    def test_live_capability_raising_skills_named_error(self):
        # القدرة الحية المؤهلة ذات قراءة مهارات متعذرة: ERROR بدليل
        # مرشح مسمّى — لا استثناء عارياً بلا سجل
        class RaisingSkillsCap:
            def __init__(self):
                self.name = "Alpha"
                self.priority = 1.0

            @property
            def skills(self):
                raise RuntimeError("skills read exploded")

        resolver = CapabilityResolver(_cap_registry(RaisingSkillsCap()))
        selection = resolver.resolve(_mission("Alpha"))
        assert selection.status.value == "error"
        assert selection.record.errors[0].startswith("candidate Alpha:")
        failed = next(c for c in selection.record.candidates
                      if c.name == "Alpha")
        assert failed.build_failed
        assert "RuntimeError" in failed.build_error

    def test_empty_skills_read_distinguished_from_not_read(self):
        # مهارات قُرئت وكانت فارغة ≠ مهارات لم تُقرأ — الأول موثق كمصدره
        class EmptySkillsCap:
            name = "Alpha"
            priority = 1.0
            skills = []  # قُرئت فعلاً (من skills_query)

        resolver = CapabilityResolver(_cap_registry(EmptySkillsCap()))
        selection = resolver.resolve(_mission("Alpha"))
        # لا علاقة اسماً (مطابقة) — المهارات الفارغة المقروءة موثقة بمصدرها
        assert selection.status.value == "success"  # مطابقة الاسم تكفي
        read_eval = next(c for c in selection.record.candidates
                         if c.name == "Alpha")
        assert read_eval.values_used["skills_source"] == "skills_query"
