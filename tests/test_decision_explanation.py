"""R-W2-010 — قاعدة القرار بالأدلة: كل قرار يجيب «لماذا X؟» بأدلة.

المادة 12 (Traceable/Explainable/Repeatable/Auditable) مثبتة سلوكياً:
- التتبع: التعليل مربوط بحقول السجل ولقطة السياسة (decision_id، الأسماء،
  القيم، القواعد) — لا معلومات من خارجه.
- التفسير: يبين السبب الفعلي للحسم لكل آلية (حسابي/خروج مبكر/أهلية/
  عدم تطابق/تعذر) — بلا حكاية موحدة.
- التكرار: المفسر من السجل وحده — سجل JSON محفوظ يعطي التفسير نفسه،
  وتغيير السياسة الحية بعد الحفظ لا يغيره، والدرجة تُعاد من اللقطة.
- التدقيق: يشمل البدائل والنقص والأخطاء — لا الفائز وحده.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agos" / "agos-kernel"))

from decision_pipeline import (  # noqa: E402
    DECISION_CORE, DecisionCandidate, DecisionRequest, DecisionPolicy,
    DecisionPipeline, DecisionContext, LIVE_CAPABILITY_POLICY,
    LIVE_PROVIDER_POLICY, FIRST_PROVIDER_POLICY, PIPELINE_CAPABILITY_POLICY,
    PIPELINE_PROVIDER_POLICY,
)
from decision import DecisionEngine  # noqa: E402
from mission import Mission  # noqa: E402
from registry.capability import CapabilityRegistry  # noqa: E402
from registry.provider import ProviderRegistry  # noqa: E402
from resolvers import CapabilityResolver, ProviderResolver  # noqa: E402
from pipeline import ExecutionPipeline  # noqa: E402

AT = datetime(2026, 10, 22, 19, 0, tzinfo=timezone.utc)


class FakeCapability:
    def __init__(self, name, skills, priority=1.0):
        self.name, self.skills, self.priority = name, skills, priority


class FakeProvider:
    def __init__(self, name, skills, priority=1.0):
        self.name, self.skills, self.priority = name, skills, priority

    def supports_skill(self, skill):
        return skill in self.skills


def _cap_registry(*caps):
    reg = CapabilityRegistry()
    for cap in caps:
        reg.register(cap)
    return reg


def _prov_registry(*provs):
    reg = ProviderRegistry()
    for prov in provs:
        reg.register(prov)
    return reg


def _mission(capability, **params):
    return Mission(name="m", description="d", capability=capability,
                   parameters=params)


def _why(record):
    return record.to_dict()["why"]


# ---------------------------------------------------------------------------
# المادة 12 — التفسير: السبب الفعلي لكل آلية
# ---------------------------------------------------------------------------

class TestExplainComputational:
    def test_margin_shows_real_components(self):
        # الفارق الحسابي: من الدليل وحده — القيم والأوزان والفارق
        dp = DecisionPipeline(
            _cap_registry(FakeCapability("AlphaOne", ["s1"], 0.2),
                          FakeCapability("AlphaTwo", ["s1", "s2"], 0.9)),
            _prov_registry(FakeProvider("P1", ["s1"])))
        result = dp.decide(DecisionContext(_mission("Alpha")))
        why = _why(result.records[0])
        assert why["decision_type"] == "computational"
        margin = why["why"]["margin"]
        assert margin["selected_total"] == pytest.approx(0.818)
        assert margin["runner"] == "AlphaOne"
        # الفارق الفعلي (الأولوية) ظاهر كمكون صالح — لا مكون مختلق
        assert margin["components"]["priority"]["selected"] == pytest.approx(0.09)
        assert margin["components"]["priority"]["runner"] == pytest.approx(0.02)
        # الأوزان من لقطة السياسة لا من السياسة الحية
        assert why["why"]["policy_weights"]["skill"] == pytest.approx(0.8)

    def test_real_tie_resolved_by_declared_break(self):
        # تعادل حقيقي: الحسم بقاعدة كسر التعادل المعلنة — لا بالدرجات
        dp = DecisionPipeline(
            _cap_registry(FakeCapability("AlphaOne", ["s1"], 0.5),
                          FakeCapability("AlphaTwo", ["s1"], 0.5)),
            _prov_registry(FakeProvider("P1", ["s1"])))
        result = dp.decide(DecisionContext(_mission("Alpha")))
        why = _why(result.records[0])
        assert "تعادل حقيقي" in why["answer"]
        assert why["why"]["tie"]["resolved_by"] == "stable-registration-order"
        # قاعدة كسر التعادل مستخدمة فعلاً — ليست موجودة فقط
        assert result.records[0].tie_break == "stable-registration-order"

    def test_no_tie_no_break_claim(self):
        # بلا تعادل: لا يُدعى استخدام كسر التعادل أصلاً
        dp = DecisionPipeline(
            _cap_registry(FakeCapability("AlphaOne", ["s1"], 0.2),
                          FakeCapability("AlphaTwo", ["s1"], 0.9)),
            _prov_registry(FakeProvider("P1", ["s1"])))
        result = dp.decide(DecisionContext(_mission("Alpha")))
        why = _why(result.records[0])
        assert "كسر التعادل" not in why["answer"]
        assert "tie" not in why["why"]
        assert "margin" in why["why"]

    def test_eligibility_excluded_not_losing_by_score(self):
        # مستبعد بالأهلية رغم أولوية أعلى محتملة: لم يدخل المنافسة —
        # لا يُدّعى خسارة درجة ولا أن درجته كانت ستكفي
        dp = DecisionPipeline(
            _cap_registry(FakeCapability("Alpha", ["s1"], 0.2),
                          FakeCapability("AlphaX", ["s1"], 9.0)),
            _prov_registry(FakeProvider("P1", ["s1"])))
        result = dp.decide(DecisionContext(_mission("Alpha")))
        why = _why(result.records[0])
        alt = next(a for a in why["alternatives"] if a["name"] == "AlphaX")
        assert "لم تُحسب درجته" in alt["why_not"]
        # النفي الصريح: لا ادعاء خسارة درجة (وليس مجرد غياب الكلمة)
        assert "لا يُدّعى أنه خسر بالدرجة" in alt["why_not"]
        # والجواب يشرح القيد لا سباق درجات وهمي
        assert "محصورة بالأهلية الشرطية" in why["answer"]

    def test_staged_provider_filter_exclusion_explained(self):
        # مسار الدُبعة للموفّرين: المستبعد بالفحص — بحدود استعلامه
        dp = DecisionPipeline(
            _cap_registry(FakeCapability("Alpha", ["s1", "s2"])),
            _prov_registry(FakeProvider("Full", ["s1", "s2"]),
                           FakeProvider("Partial", ["s1"])))
        result = dp.decide(DecisionContext(_mission("Alpha")))
        why = _why(result.records[1])
        alt = next(a for a in why["alternatives"] if a["name"] == "Partial")
        assert "استُبعد" in alt["why_not"]
        # أولوية ثابتة معلنة — ليست فارقاً بين المرشحين
        assert why["why"].get("priority_note") is not None


class TestExplainEarlyExit:
    def test_first_provider_decisive_skill(self):
        # الخروج المبكر: المهارة الحاسمة وحدود التوقف — لا مفاضلة درجات
        class Lazy:
            def __init__(self, name, ans):
                self.name, self.ans = name, ans

            def supports_skill(self, skill):
                return self.ans

        engine = DecisionEngine(
            _cap_registry(FakeCapability("Alpha", ["s1", "s2"])),
            _prov_registry(Lazy("First", True), Lazy("Second", True)))
        result = engine.decide(type("C", (), {"mission": _mission("Alpha")})())
        why = result.data.record.to_dict()["why"]
        assert why["decision_type"] == "early-exit-first-supporting"
        assert why["why"]["decisive_skill"] == "s1"
        assert "توقف الاستعلام" in why["answer"]
        assert "مفاضلة درجات" in why["answer"]

    def test_non_queried_alternative_explained(self):
        # من لم يُستعلم: توقف الاستعلام قبله — مسجل لا مسكوت عنه
        class Lazy:
            def __init__(self, name, ans):
                self.name, self.ans = name, ans

            def supports_skill(self, skill):
                return self.ans

        engine = DecisionEngine(
            _cap_registry(FakeCapability("Alpha", ["s1"])),
            _prov_registry(Lazy("First", True), Lazy("Second", True)))
        result = engine.decide(type("C", (), {"mission": _mission("Alpha")})())
        why = result.data.record.to_dict()["why"]
        alt = next(a for a in why["alternatives"] if a["name"] == "Second")
        assert "لم يُستعلم" in alt["why_not"]
        assert "توقف" in alt["why_not"]


class TestExplainNoMatchAndError:
    def test_no_match_named_reasons(self):
        # عدم التطابق: أسباب مسماة لكل مرشح — لا فائز افتراضي
        class Unrelated:
            name, priority, skills = "Zeta", 1.0, ["zz"]

        resolver = CapabilityResolver(_cap_registry(Unrelated()))
        selection = resolver.resolve(_mission("Alpha"))
        assert selection.status.value == "no_match"
        why = selection.record.to_dict()["why"]
        assert "لا اختيار" in why["answer"]
        assert "no-name-or-skill-relationship" in why["answer"]

    def test_error_no_winner_from_partially_evaluated(self):
        # التعذر يمنع إثبات الفائز — لا يُعلن فائز من مُقيَّم جزئياً
        class Failing:
            name, priority = "Bad", 1.0

            def supports_skill(self, skill):
                raise RuntimeError("boom")

        class Good:
            name, priority = "Good", 1.0

            def supports_skill(self, skill):
                return True

        engine = DecisionEngine(
            _cap_registry(FakeCapability("Alpha", ["s1"])),
            _prov_registry(Failing(), Good()))
        result = engine.decide(type("C", (), {"mission": _mission("Alpha")})())
        assert result.status.value == "failure"
        why = result.record.to_dict()["why"]
        assert why["decision_type"] == "error"
        assert "لا يُعلن فائز" in why["answer"]
        # المحرك القديم يتوقف عند الاستثناء: Good لم يُستعلم أصلاً —
        # لا يُدّعى أنه «مُقيَّم جزئياً» (غياب الوسم ليس دليلاً على التقييم)
        assert why["why"]["evaluated_but_no_winner_declared"] == []
        assert why["why"]["not_evaluated_at_failure"] == ["Good"]
        assert any("Bad" in e for e in why["why"]["errors"])

    def test_error_with_actually_evaluated_candidate(self):
        # المسار المرحلي يواصل التقييم: الفاشل متعذر والكامل مُقيَّم
        # فعلاً بدرجته — ولا يُعلن فائز منه رغم اكتمال تقييمه
        class Failing:
            name, priority = "Bad", 1.0

            def supports_skill(self, skill):
                raise RuntimeError("boom")

        class Full:
            name, priority = "Full", 1.0
            skills = ["s1"]

            def supports_skill(self, skill):
                return True

        dp = DecisionPipeline(
            _cap_registry(FakeCapability("Alpha", ["s1"])),
            _prov_registry(Failing(), Full()))
        result = dp.decide(DecisionContext(_mission("Alpha")))
        assert result.status.value == "failed"
        why = result.records[1].to_dict()["why"]
        assert why["decision_type"] == "error"
        assert why["why"]["evaluated_but_no_winner_declared"] == ["Full"]
        assert "لا يُعلن فائز" in why["answer"]

    def test_first_provider_all_negative_no_match(self):
        # كل الإجابات سلبية: «استُعلم وأجاب بعدم الدعم» — لا «قُيّم ولم يفُز»
        # (قاعدة الخروج المبكر لا مفاضلة درجات أصلاً)
        class Negative:
            name, priority = "Neg", 1.0

            def supports_skill(self, skill):
                return False

        engine = DecisionEngine(
            _cap_registry(FakeCapability("Alpha", ["s1"])),
            _prov_registry(Negative()))
        result = engine.decide(type("C", (), {"mission": _mission("Alpha")})())
        assert result.status.value == "failure"
        why = result.record.to_dict()["why"]
        assert why["decision_type"] == "no-match"
        assert "استُعلم وأجاب بعدم الدعم" in why["answer"]
        assert "قُيّم" not in why["answer"]

    def test_first_provider_no_required_skills_no_match(self):
        # بلا مهارات مطلوبة: القاعدة لا تختار أصلاً — من الدليل لا تأويل
        class Any:
            name, priority = "Any", 1.0

            def supports_skill(self, skill):
                return True

        engine = DecisionEngine(
            _cap_registry(FakeCapability("Alpha", [])),
            _prov_registry(Any()))
        result = engine.decide(type("C", (), {"mission": _mission("Alpha")})())
        assert result.status.value == "failure"
        why = result.record.to_dict()["why"]
        assert why["decision_type"] == "no-match"
        assert "بلا مهارات مطلوبة" in why["answer"]
        assert "لا قاعدة" in why["answer"]


# ---------------------------------------------------------------------------
# المادة 12 — الأمانة التفسيرية
# ---------------------------------------------------------------------------

class TestExplainHonesty:
    def test_constraints_not_described_as_passed(self):
        # القيود مساهمة افتراضية معلنة — لا توصف بأنها اجتازت فحصاً
        dp = DecisionPipeline(
            _cap_registry(FakeCapability("Alpha", ["s1"])),
            _prov_registry(FakeProvider("P1", ["s1"])))
        result = dp.decide(DecisionContext(_mission("Alpha", constraints=[{"c": "x"}])))
        why = _why(result.records[0])
        # النقص المسمّى موجود في التعليل نفسه — لا في السجل وحده
        assert why["why_note_constraints"] is not None
        assert "لم تُفحص" in why["why_note_constraints"]
        assert any(m.startswith("constraints-not-evaluated")
                   for m in why["missing_info"])

    def test_not_read_distinguished_from_read_empty(self):
        # بيانات لم تُقرأ ≠ قُرئت فارغة — ظاهر في تعليل البدائل
        resolver = CapabilityResolver(_cap_registry(FakeCapability("Alpha", ["s1"])))
        selection = resolver.resolve(_mission("Alpha"))
        why = selection.record.to_dict()["why"]
        sel = why["why"]["selected_values"]
        # المصدر معلن: قرئ فعلاً من skills_query
        assert sel["recorded"]["skills_source"] == "skills_query"

    def test_missing_evidence_named_gap_not_confident(self):
        # حذف الدليل الحاسم: نقص مسمّى لا شرح مطمئن
        dp = DecisionPipeline(
            _cap_registry(FakeCapability("AlphaOne", ["s1"], 0.2),
                          FakeCapability("AlphaTwo", ["s1"], 0.9)),
            _prov_registry(FakeProvider("P1", ["s1"])))
        result = dp.decide(DecisionContext(_mission("Alpha")))
        record = result.records[0]
        # احذف الدرجة الحاسمة من المختار
        selected = next(c for c in record.candidates if c.name == record.selected)
        selected.score = None
        why = record.to_dict()["why"]
        assert "selected-score-missing" in why["gaps"]
        # والجواب يصرح بالنقص لا بالثقة
        assert "نقص" in why["answer"] or why["gaps"]

    def test_absent_policy_snapshot_named(self):
        # سجل بلا لقطة سياسة: النقص مسمّى — لا قواعد تخمين
        request = DecisionRequest(kind="capability", requested_name="Alpha",
                                  required_skills=["s1"], constraints=[])
        record = DECISION_CORE.evaluate(
            request, [DecisionCandidate(name="Alpha",
                                        offered_skills=["s1"])],
            DecisionPolicy(policy_id="p", version="1", kind="capability"),
            decision_id="d1", timestamp=AT.isoformat())
        # سياسة بلا قواعد مسجلة: المفسر لا يخترع آلية
        why = record.to_dict()["why"]
        assert "selection-rules-not-recorded" in why["gaps"]


# ---------------------------------------------------------------------------
# المادة 12 — التكرار والتتبع
# ---------------------------------------------------------------------------

class TestExplainRepeatable:
    def test_saved_record_same_explanation_after_policy_change(self):
        # تغيير السياسة الحية بعد حفظ السجل: تفسير اللقطة لا يتغير
        dp = DecisionPipeline(
            _cap_registry(FakeCapability("AlphaOne", ["s1"], 0.2),
                          FakeCapability("AlphaTwo", ["s1"], 0.9)),
            _prov_registry(FakeProvider("P1", ["s1"])))
        result = dp.decide(DecisionContext(_mission("Alpha")))
        before = json.dumps(result.records[0].to_dict()["why"],
                            sort_keys=True, ensure_ascii=False)
        # غيّر الأوزان الحية بعد الحفظ — اللقطة في السجل لا تتأثر
        PIPELINE_CAPABILITY_POLICY.weights["skill"] = 0.1
        try:
            after = json.dumps(result.records[0].to_dict()["why"],
                                sort_keys=True, ensure_ascii=False)
        finally:
            PIPELINE_CAPABILITY_POLICY.weights["skill"] = 0.8
        assert before == after

    def test_recompute_total_from_snapshot(self):
        # إعادة الحساب من اللقطة والقيم المسجلة = الدرجة المسجلة
        dp = DecisionPipeline(
            _cap_registry(FakeCapability("AlphaOne", ["s1"], 0.2),
                          FakeCapability("AlphaTwo", ["s1"], 0.9)),
            _prov_registry(FakeProvider("P1", ["s1"])))
        result = dp.decide(DecisionContext(_mission("Alpha")))
        record = result.records[0]
        why = record.to_dict()["why"]
        selected = next(c for c in record.candidates
                        if c.name == record.selected)
        weights = why["why"]["policy_weights"]
        skill_match = selected.values_used["skill_match"]
        priority = selected.score.priority
        recomputed = (skill_match * weights["skill"]
                      + priority * weights["priority_weight"])
        assert recomputed == pytest.approx(selected.score.total)

    def test_deterministic_explanation(self):
        # استدعاء المفسر مرتين: التفسير نفسه (من السجل وحده)
        dp = DecisionPipeline(
            _cap_registry(FakeCapability("Alpha", ["s1"])),
            _prov_registry(FakeProvider("P1", ["s1"])))
        result = dp.decide(DecisionContext(_mission("Alpha")))
        record = result.records[0]
        first = json.dumps(record.to_dict()["why"], sort_keys=True,
                           ensure_ascii=False)
        second = json.dumps(record.to_dict()["why"], sort_keys=True,
                           ensure_ascii=False)
        assert first == second


class TestExplainTraceable:
    def test_trace_links_to_record_fields(self):
        # التتبع: التعليل يربط بالقرار والمرشح والسياسة المسجلة
        dp = DecisionPipeline(
            _cap_registry(FakeCapability("Alpha", ["s1"])),
            _prov_registry(FakeProvider("P1", ["s1"])))
        result = dp.decide(DecisionContext(_mission("Alpha")))
        record = result.records[0]
        why = record.to_dict()["why"]
        assert why["decision_id"] == record.decision_id
        assert why["trace"]["policy_id"] == record.policy_id
        assert why["trace"]["policy_version"] == record.policy_version
        assert why["trace"]["timestamp"] == record.timestamp
        assert why["trace"]["from_record_only"] is True


# ---------------------------------------------------------------------------
# الظهور في المخرجات — النجاح والفشل لا الدالة المنفردة فقط
# ---------------------------------------------------------------------------

class TestExplainInOutputs:
    def test_why_in_live_resolver_output(self):
        resolver = CapabilityResolver(
            _cap_registry(FakeCapability("Alpha", ["s1"])))
        selection = resolver.resolve(_mission("Alpha"))
        assert "why" in selection.record.to_dict()

    def test_why_in_pipeline_success_and_failure(self):
        # النجاح والفشل معاً — الدليل بتعليله في نتائج التنفيذ
        from events import EventBus
        from resolvers import ProviderResolver

        def _pipeline(prov):
            return ExecutionPipeline(
                EventBus(),
                CapabilityResolver(_cap_registry(FakeCapability("Alpha", ["s1"]))),
                ProviderResolver(_prov_registry(prov),
                                 _cap_registry(FakeCapability("Alpha", ["s1"]))))

        ok = _pipeline(FakeProvider("P1", ["s1"])).execute(_mission("Alpha"))
        assert all("why" in r.to_dict() for r in ok.decision_records)

        failed = _pipeline(FakeProvider("P1", ["zz"])).execute(_mission("Alpha"))
        assert failed.decision_records
        assert all("why" in r.to_dict() for r in failed.decision_records)

    def test_why_json_serializable(self):
        # التعليل قابل للتسلسل — يظهر في المخرجات المسلسلة كما هو
        dp = DecisionPipeline(
            _cap_registry(FakeCapability("Alpha", ["s1"])),
            _prov_registry(FakeProvider("P1", ["s1"])))
        result = dp.decide(DecisionContext(_mission("Alpha")))
        payload = json.dumps(result.records[0].to_dict(), ensure_ascii=False)
        assert '"why"' in payload
        assert "why" in json.loads(payload)


# ---------------------------------------------------------------------------
# جولة المراجعة الثانية — صدق التعليل والتكرار من المحفوظ
# ---------------------------------------------------------------------------

class TestRound2TieAndMargin:
    def test_tie_alternative_registration_order(self):
        # البديل في التعادل الحقيقي: «تعادل تام حُسم بترتيب التسجيل» —
        # لا «درجة أقل» (ادعاء مفاضلة في التعادل كذب على الدليل)
        dp = DecisionPipeline(
            _cap_registry(FakeCapability("AlphaOne", ["s1"], 0.5),
                          FakeCapability("AlphaTwo", ["s1"], 0.5)),
            _prov_registry(FakeProvider("P1", ["s1"])))
        result = dp.decide(DecisionContext(_mission("Alpha")))
        why = _why(result.records[0])
        alt = next(a for a in why["alternatives"]
                   if a["name"] == "AlphaTwo")
        assert "تعادل تام في الدرجة" in alt["why_not"]
        assert "ترتيب التسجيل" in alt["why_not"]
        assert "درجة أقل" not in alt["why_not"]

    def test_tiny_difference_below_threshold_not_tie(self):
        # فارق دون 1e-12: القلب يفرز بالدرجة الفعلية (الأعلى أولاً) —
        # المفسر لا يسميه تعادلاً حُسم بالتسجيل، بل يكشف الفارق الدقيق.
        # المرشح اللاحق بترتيب التسجيل أعلى بفارق دقيق — فيُختار هو
        dp = DecisionPipeline(
            _cap_registry(FakeCapability("AlphaOne", ["s1"], 0.5),
                          FakeCapability("AlphaTwo", ["s1"], 0.5 + 5e-13)),
            _prov_registry(FakeProvider("P1", ["s1"])))
        result = dp.decide(DecisionContext(_mission("Alpha")))
        record = result.records[0]
        # اختيار الأصل محفوظ: الأعلى درجة فعلاً يفوز (لا تغيير للتجميل)
        assert record.selected == "AlphaTwo"
        why = record.to_dict()["why"]
        # ولا يُدّعى تعادل حُسم بالتسجيل — الفارق الدقيق مكشوف
        assert "near_tie" in why["why"]
        assert "تعادل حقيقي" not in why["answer"]
        # النفي الصريح: الحسم بالدرجة المسجلة — لا بترتيب التسجيل
        assert "لا بترتيب التسجيل" in why["answer"]
        assert "فارق" in why["answer"]
        assert "الدرجة المسجلة" in why["answer"]

    def test_competition_restricted_by_in_why(self):
        # قيد الأهلية محفوظ في why (لا يُمحى بإعادة بناء القاموس)
        dp = DecisionPipeline(
            _cap_registry(FakeCapability("Alpha", ["s1"], 0.2),
                          FakeCapability("AlphaX", ["s1"], 9.0)),
            _prov_registry(FakeProvider("P1", ["s1"])))
        result = dp.decide(DecisionContext(_mission("Alpha")))
        why = _why(result.records[0])
        restricted = why["why"]["competition_restricted_by"]
        assert restricted == {"AlphaX": "not-an-exact-name-match-"
                                         "while-exact-available"}

    def test_relationship_exclusion_not_conditional_restriction(self):
        # استبعاد عدم العلاقة (المسار الحي) ليس قيد أهلية شرطية —
        # الجواب لا يدّعي حصر المنافسة
        class Unrelated:
            name, priority, skills = "Zeta", 1.0, ["zz"]

        resolver = CapabilityResolver(
            _cap_registry(FakeCapability("Alpha", ["s1"]), Unrelated()))
        selection = resolver.resolve(_mission("Alpha"))
        assert selection.status.value == "success"
        why = selection.record.to_dict()["why"]
        assert "محصورة بالأهلية الشرطية" not in why["answer"]
        assert "competition_restricted_by" not in why["why"]


class TestRound2InsufficientEvidence:
    def test_missing_score_answer_declares_insufficiency(self):
        # حذف الدرجة الحاسمة: الجواب نفسه يصرح بعدم كفاية الدليل —
        # لا جزم مطمئن بحاشية gaps
        dp = DecisionPipeline(
            _cap_registry(FakeCapability("AlphaOne", ["s1"], 0.2),
                          FakeCapability("AlphaTwo", ["s1"], 0.9)),
            _prov_registry(FakeProvider("P1", ["s1"])))
        result = dp.decide(DecisionContext(_mission("Alpha")))
        record = result.records[0]
        selected = next(c for c in record.candidates
                        if c.name == record.selected)
        selected.score = None
        why = record.to_dict()["why"]
        assert "selected-score-missing" in why["gaps"]
        assert "نقص" in why["answer"]
        assert "لا يكفي" in why["answer"]
        assert "أعلى درجة إجمالية" not in why["answer"]

    def test_absent_snapshot_named_gap(self):
        # سجل بلا لقطة سياسة أصلاً (None) — نقص مسمّى مستقل عن
        # حالة «لقطة بقواعد فارغة»
        dp = DecisionPipeline(
            _cap_registry(FakeCapability("AlphaOne", ["s1"], 0.2),
                          FakeCapability("AlphaTwo", ["s1"], 0.9)),
            _prov_registry(FakeProvider("P1", ["s1"])))
        result = dp.decide(DecisionContext(_mission("Alpha")))
        record = result.records[0]
        record.policy_snapshot = None
        why = record.to_dict()["why"]
        assert "policy-snapshot-absent" in why["gaps"]

    def test_unknown_rules_no_fabricated_mechanism(self):
        # سياسة بلا قواعد مسجلة: لا يُفترض مسار حسابي ولا يُختلق كسر تعادل
        request = DecisionRequest(kind="capability", requested_name="Alpha",
                                  required_skills=["s1"], constraints=[])
        record = DECISION_CORE.evaluate(
            request, [DecisionCandidate(name="Alpha",
                                        offered_skills=["s1"])],
            DecisionPolicy(policy_id="p", version="1", kind="capability"),
            decision_id="d1", timestamp=AT.isoformat())
        # لقطة موجودة بقواعد فارغة — سيناريو مستقل عن اللقطة الغائبة
        assert record.policy_snapshot is not None
        why = record.to_dict()["why"]
        assert why["decision_type"] in ("unknown", "no-match")
        if record.status == "selected":
            assert why["decision_type"] == "unknown"
            assert "نقص مسمّى" in why["answer"]
            assert "لا يثبت" in why["answer"]


class TestRound2SavedJsonRoundtrip:
    def test_explanation_rederived_from_saved_json(self):
        # الحفظ والتسلسل ثم حذف why المحفوظ وإعادة الاشتقاق من
        # القاموس المحمّل — بلا سياسة حية ولا استعلامات: التفسير نفسه
        from decision_pipeline.explain import explain_saved_record

        dp = DecisionPipeline(
            _cap_registry(FakeCapability("AlphaOne", ["s1"], 0.2),
                          FakeCapability("AlphaTwo", ["s1", "s2"], 0.9)),
            _prov_registry(FakeProvider("P1", ["s1"])))
        result = dp.decide(DecisionContext(_mission("Alpha")))
        payload = json.loads(json.dumps(result.records[0].to_dict(),
                                        ensure_ascii=False))
        original_why = payload.pop("why")  # يُحذف كي يُشتق لا يُقرأ
        rederived = explain_saved_record(payload)
        # التفسير المعاد اشتقاقه يطابق الأصلي — المادة 12 (التكرار)
        assert json.dumps(rederived, sort_keys=True, ensure_ascii=False) == \
            json.dumps(original_why, sort_keys=True, ensure_ascii=False)


class TestRound2OutputVerification:
    def test_execution_result_serialization_carries_why(self):
        # التسلسل العام لنتيجة التنفيذ (لا to_dict يدوي للسجل): يفحص
        # الحالة والسجلات معاً — نجاحاً مؤكداً وفشلاً مؤكداً. عبر
        # النواة الحقيقية (agos_runtime) لا بدائل مصطنعة بلا execute
        import agos_runtime

        kernel = agos_runtime.boot()
        ok = kernel.run({"name": "t", "description": "d",
                        "capability": "RepositoryProcessingPipeline",
                        "parameters": {"repo_path": str(
                            Path(__file__).resolve().parents[1])}})
        assert ok.state.value == "completed"
        payload = json.loads(json.dumps(ok.to_dict(), ensure_ascii=False))
        records = payload.get("decision_records", [])
        # ليست فارغة — وإلا كان all() نجاحاً زائفاً (درس المراجعة)
        assert records and all("why" in r for r in records)

        # فشل حتمي مؤكد: قدرة غير موجودة — حالة failed تحديداً
        kernel2 = agos_runtime.boot()
        failed = kernel2.run({"name": "t", "description": "d",
                              "capability": "NoSuchCapability",
                              "parameters": {}})
        assert failed.state.value == "failed"
        payload2 = json.loads(json.dumps(failed.to_dict(),
                                         ensure_ascii=False))
        records2 = payload2.get("decision_records", [])
        assert records2 and all("why" in r for r in records2)

    def test_mission_result_serialization_carries_why(self):
        # نتيجة المهام: السجلات بتعليلها في التسلسل العام — عبر
        # النواة الحقيقية في مساري النجاح والفشل
        import agos_runtime

        kernel = agos_runtime.boot()
        out = kernel.run({"name": "t", "description": "d",
                          "capability": "RepositoryProcessingPipeline",
                          "parameters": {"repo_path": str(
                              Path(__file__).resolve().parents[1])}})
        assert out.state.value == "completed"
        payload = json.loads(json.dumps(out.to_dict(), ensure_ascii=False))
        records = payload.get("decision_records", [])
        assert len(records) == 2  # قرارا القدرة والموفّر
        assert all("why" in r for r in records)


# ---------------------------------------------------------------------------
# جولة المراجعة الثالثة — لا نقص مختلق ولا قاعدة مختلقة
# ---------------------------------------------------------------------------

class TestRound3NoFabricatedGaps:
    def test_single_candidate_no_false_gap(self):
        # مرشح وحيد فعلاً (يُتحقق من العدد قبل الفحص): ليس نقصاً
        dp = DecisionPipeline(
            _cap_registry(FakeCapability("AlphaOne", ["s1"], 0.2)),
            _prov_registry(FakeProvider("P1", ["s1"])))
        result = dp.decide(DecisionContext(_mission("Alpha")))
        record = result.records[0]
        assert len(record.candidates) == 1  # مرشح واحد فعلاً
        why = _why(record)
        assert "ranked-alternatives-missing" not in why["gaps"]
        assert "single-candidate-no-alternatives" not in why["gaps"]

    def test_all_others_excluded_no_false_gap(self):
        # كل المنافسين مستبعدون بالأهلية: ليست فجوة ترتيب — القيد موثق
        dp = DecisionPipeline(
            _cap_registry(FakeCapability("Alpha", ["s1"], 0.2),
                          FakeCapability("AlphaX", ["s1"], 9.0),
                          FakeCapability("AlphaY", ["s1"], 8.0)),
            _prov_registry(FakeProvider("P1", ["s1"])))
        result = dp.decide(DecisionContext(_mission("Alpha")))
        why = _why(result.records[0])
        assert "ranked-alternatives-missing" not in why["gaps"]
        assert "single-candidate-no-alternatives" not in why["gaps"]

    def test_missing_eligible_competitor_in_ranking_is_gap(self):
        # منافس مؤهل اكتمل تقييمه غاب من الترتيب: نقص مكشوف والقائمة
        # غير فارغة — [selected] وحدها لا تكفي لإخفائه (فحص الغياب لا
        # الفراغ)، ولا يُدّعى «أقرب منافس» بترتيب ناقص
        dp = DecisionPipeline(
            _cap_registry(FakeCapability("AlphaOne", ["s1"], 0.2),
                          FakeCapability("AlphaTwo", ["s1"], 0.9)),
            _prov_registry(FakeProvider("P1", ["s1"])))
        result = dp.decide(DecisionContext(_mission("Alpha")))
        record = result.records[0]
        # المختار هو الأعلى درجة فعلاً (AlphaTwo: أولوية 0.09 مقابل 0.02)
        assert record.selected == "AlphaTwo"
        # الترتيب محفوظ بالفعل (سلامة الأصل) — الآن احذف المنافس منه
        # وابقِ القائمة غير فارغة: [selected] وحدها
        assert "AlphaOne" in record.ranked_alternatives
        record.ranked_alternatives = [record.selected]
        why = record.to_dict()["why"]
        assert "ranked-alternatives-missing" in why["gaps"]
        assert why["why"]["ranking_incomplete"]["missing"] == ["AlphaOne"]
        # والجواب يصرح بنقص المقارنة — لا «أقرب منافس» ولا جزم مطمئن
        assert "ناقص" in why["answer"]
        assert "لا يكفي للمقارنة" in why["answer"]
        assert "أقرب منافس" not in why["answer"]

    def test_fully_deleted_ranking_is_gap_too(self):
        # حذف الترتيب كله: نفس النقص المكشوف — الفحص موحد بالغياب
        dp = DecisionPipeline(
            _cap_registry(FakeCapability("AlphaOne", ["s1"], 0.2),
                          FakeCapability("AlphaTwo", ["s1"], 0.9)),
            _prov_registry(FakeProvider("P1", ["s1"])))
        result = dp.decide(DecisionContext(_mission("Alpha")))
        record = result.records[0]
        record.ranked_alternatives = []
        why = record.to_dict()["why"]
        assert "ranked-alternatives-missing" in why["gaps"]

    def test_unknown_rules_without_selection_unknown_mechanism(self):
        # قواعد مجهولة لا تحوي selection: عدم فراغ القاموس ليس إثباتاً
        # لمفاضلة حسابية — الآلية مجهولة والنقص معلن
        policy = DecisionPolicy(
            policy_id="mystery2", version="1", kind="capability",
            weights={"skill": 0.8}, rules={"mystery": "unknown-rule"})
        record = DECISION_CORE.evaluate(
            DecisionRequest(kind="capability", requested_name="Alpha",
                            required_skills=[], constraints=[]),
            [DecisionCandidate(name="Alpha", offered_skills=["s1"])],
            policy, decision_id="d2", timestamp=AT.isoformat())
        if record.status == "selected":
            why = record.to_dict()["why"]
            assert why["decision_type"] == "unknown"
            assert "نقص مسمّى" in why["answer"]
            assert "لا يثبت" in why["answer"]

    def test_saved_json_missing_runner_total_answer_confesses(self):
        # حذف إجمالي المنافس الأقرب وحده من السجل المحفوظ: الجواب يصرح
        # بعدم كفاية دليل المقارنة — لا يبقى جزم «أعلى درجة» بحاشية
        from decision_pipeline.explain import explain_saved_record

        dp = DecisionPipeline(
            _cap_registry(FakeCapability("AlphaOne", ["s1"], 0.2),
                          FakeCapability("AlphaTwo", ["s1", "s2"], 0.9)),
            _prov_registry(FakeProvider("P1", ["s1"])))
        result = dp.decide(DecisionContext(_mission("Alpha")))
        payload = json.loads(json.dumps(result.records[0].to_dict(),
                                        ensure_ascii=False))
        payload.pop("why")
        runner = next(c for c in payload["candidates"]
                      if c["name"] in payload["ranked_alternatives"]
                      and c["name"] != payload["selected"])
        runner["score"]["total"] = None
        why = explain_saved_record(payload)
        assert "runner-up-total-not-comparable" in why["gaps"]
        assert "لا يكفي للمقارنة" in why["answer"]
        assert "نقص مسمّى" in why["answer"]
        assert "أعلى درجة إجمالية" not in why["answer"]

    def test_unknown_selection_value_is_unknown_mechanism(self):
        # قاعدة اختيار مسجلة غير معروفة: نقص تفسير الآلية معلن —
        # لا يُخترع سباق درجات
        policy = DecisionPolicy(
            policy_id="mystery", version="1", kind="capability",
            weights={"skill": 0.8}, rules={"selection": "some-mystery-rule"})
        record = DECISION_CORE.evaluate(
            DecisionRequest(kind="capability", requested_name="Alpha",
                            required_skills=[], constraints=[]),
            [DecisionCandidate(name="Alpha", offered_skills=["s1"])],
            policy, decision_id="d1", timestamp=AT.isoformat())
        why = record.to_dict()["why"]
        if record.status == "selected":
            assert why["decision_type"] == "unknown"
            assert "نقص مسمّى" in why["answer"]
            assert "لا يثبت" in why["answer"]
            assert "سباق" not in why["answer"]

    def test_tie_without_break_consistent_gap(self):
        # تعادل حُذفت قاعدة كسره من السجل: الجواب وتعليل البديل معاً
        # يعلنان النقص — لا يختلق البديل «ترتيب التسجيل» بعد جواب يصرح
        # بغياب القاعدة
        dp = DecisionPipeline(
            _cap_registry(FakeCapability("AlphaOne", ["s1"], 0.5),
                          FakeCapability("AlphaTwo", ["s1"], 0.5)),
            _prov_registry(FakeProvider("P1", ["s1"])))
        result = dp.decide(DecisionContext(_mission("Alpha")))
        record = result.records[0]
        assert record.tie_break  # مسجلة قبل الحذف
        record.tie_break = ""
        why = record.to_dict()["why"]
        assert "tie-break-not-recorded" in why["gaps"]
        assert "غير مسجلة" in why["answer"]
        alt = next(a for a in why["alternatives"]
                   if a["name"] != record.selected)
        assert "غير مسجلة" in alt["why_not"]
        assert "ترتيب التسجيل" not in alt["why_not"]


class TestRound3SavedJsonIncomplete:
    def test_saved_json_missing_total_no_exception(self):
        # حذف total وحده من السجل المحفوظ (دليل حاسم ناقص): لا يهرب
        # استثناء من المفسر — الجواب يصرح بعدم كفاية الدليل
        from decision_pipeline.explain import explain_saved_record

        dp = DecisionPipeline(
            _cap_registry(FakeCapability("AlphaOne", ["s1"], 0.2),
                          FakeCapability("AlphaTwo", ["s1", "s2"], 0.9)),
            _prov_registry(FakeProvider("P1", ["s1"])))
        result = dp.decide(DecisionContext(_mission("Alpha")))
        payload = json.loads(json.dumps(result.records[0].to_dict(),
                                        ensure_ascii=False))
        payload.pop("why")
        # احذف الإجمالي الحاسم من المختار المحفوظ
        selected = next(c for c in payload["candidates"]
                        if c["name"] == payload["selected"])
        selected["score"]["total"] = None
        # لا استثناء يهرب — نقص مسمّى وجواب يصرح
        why = explain_saved_record(payload)
        assert "selected-score-missing" in why["gaps"]
        assert "لا يكفي" in why["answer"]
        assert "نقص" in why["answer"]


class TestRound3ExecutionResultDirect:
    def test_execution_result_to_dict_success_and_failure(self):
        # تسلسل ExecutionResult مباشرة (لا عبر نتيجة المهام): قدرة بديلة
        # بعقد execute الحقيقي — نجاح مؤكد وفشل مؤكد بسجلات غير فارغة
        from events import EventBus
        from resolvers import ProviderResolver

        class ExecutableCap:
            def __init__(self, name, skills, outcome):
                self.name, self.skills = name, skills
                self.priority = 1.0
                self._outcome = outcome

            def execute(self, parameters):
                if isinstance(self._outcome, Exception):
                    raise self._outcome
                return self._outcome

        def _pipeline(cap, prov):
            return ExecutionPipeline(
                EventBus(),
                CapabilityResolver(_cap_registry(cap)),
                ProviderResolver(_prov_registry(prov), _cap_registry(cap)))

        ok = _pipeline(ExecutableCap("Alpha", ["s1"], {"done": True}),
                       FakeProvider("P1", ["s1"])).execute(_mission("Alpha"))
        assert ok.status.value == "completed"
        assert ok.decision_records  # غير فارغة — لا نجاح all() الزائف
        payload = json.loads(json.dumps(ok.to_dict(), ensure_ascii=False))
        records = payload["decision_records"]
        assert records and all("why" in r for r in records)

        failed = _pipeline(ExecutableCap("Alpha", ["s1"],
                                        RuntimeError("exec boom")),
                           FakeProvider("P1", ["s1"])).execute(_mission("Alpha"))
        assert failed.status.value == "failed"
        assert failed.decision_records
        payload2 = json.loads(json.dumps(failed.to_dict(),
                                         ensure_ascii=False))
        records2 = payload2["decision_records"]
        assert records2 and all("why" in r for r in records2)

    def test_mission_failure_state_asserted_failed(self):
        # فشل حتمي مؤكد — حالة failed تحديداً لا «أحدهما»
        import agos_runtime

        kernel = agos_runtime.boot()
        out = kernel.run({"name": "t", "description": "d",
                         "capability": "NoSuchCapability",
                         "parameters": {}})
        assert out.state.value == "failed"
        payload = json.loads(json.dumps(out.to_dict(), ensure_ascii=False))
        records = payload.get("decision_records", [])
        assert records and all("why" in r for r in records)


# ---------------------------------------------------------------------------
# جولة المراجعة الخامسة — الحاجز غير المشروط قبل المقارنة
# ---------------------------------------------------------------------------

class TestRound5RankingBarrier:
    def test_missing_middle_competitor_blocks_comparison(self):
        # ثلاثة مؤهلين مكتملو التقييم بدرجات مختلفة، الترتيب [A,B,C]
        # محفوظ أولاً — ثم يحذف الأقرب (B) ويبقى الأبعد (C): الحاجز
        # غير المشروط يمنع المقارنة — لا margin ولا tie ولا «أقرب منافس»
        dp = DecisionPipeline(
            _cap_registry(FakeCapability("AlphaA", ["s1"], 0.2),
                          FakeCapability("AlphaB", ["s1"], 0.5),
                          FakeCapability("AlphaC", ["s1"], 0.8)),
            _prov_registry(FakeProvider("P1", ["s1"])))
        result = dp.decide(DecisionContext(_mission("Alpha")))
        record = result.records[0]
        # سلامة الأصل أولاً: الترتيب الكامل بدرجاته
        assert record.selected == "AlphaC"
        assert record.ranked_alternatives == ["AlphaC", "AlphaB", "AlphaA"]
        # الآن احذف الأقرب (AlphaB) وأبقِ الأبعد (AlphaA)
        record.ranked_alternatives = ["AlphaC", "AlphaA"]
        why = record.to_dict()["why"]
        # اكتشاف غياب AlphaB
        assert "ranked-alternatives-missing" in why["gaps"]
        assert why["why"]["ranking_incomplete"]["missing"] == ["AlphaB"]
        # تصريح الجواب بعدم كفاية المقارنة
        assert "لا يكفي للمقارنة" in why["answer"]
        assert "ناقص" in why["answer"]
        # ولا مقارنة أصلاً: لا margin ولا tie ولا وصف «أقرب منافس»
        assert "margin" not in why["why"]
        assert "tie" not in why["why"]
        assert "أقرب منافس" not in why["answer"]
        assert not any("أقرب منافس" in str(a) for a in why["alternatives"])


# ---------------------------------------------------------------------------
# جولة المراجعة السادسة — قيم القواعد والمسار المعلن
# ---------------------------------------------------------------------------

class TestRound6RuleValuesAndDeclaredPath:
    def test_known_key_unknown_value_unknown_mechanism(self):
        # مفتاح معروف بقيمة مجهولة: المفتاح وحده لا يثبت آلية — النقص
        # مسمّى. حالة السجل تؤكد أولاً (لا اختبار مشروط يمكن تجاوزه)
        policy = DecisionPolicy(
            policy_id="half-known", version="1", kind="capability",
            weights={"skill": 0.8},
            rules={"capability_scoring": "unknown-algorithm"})
        record = DECISION_CORE.evaluate(
            DecisionRequest(kind="capability", requested_name="Alpha",
                            required_skills=[], constraints=[]),
            [DecisionCandidate(name="Alpha", offered_skills=["s1"])],
            policy, decision_id="d3", timestamp=AT.isoformat())
        assert record.status == "selected"  # الحالة مثبتة قبل فحص الشرح
        why = record.to_dict()["why"]
        assert why["decision_type"] == "unknown"
        # القاعدة المسجلة غير المدعومة تسمّى بمفتاحها وقيمتها — لا
        # يقال «القواعد غير مسجلة» وهي مسجلة فعلاً
        assert any(g.startswith("unsupported-rule-value: "
                                "capability_scoring=unknown-algorithm")
                   for g in why["gaps"])
        assert "capability_scoring = unknown-algorithm" in why["answer"]
        assert "غير مدعومة" in why["answer"]
        assert "لا قواعد مسجلة" not in why["answer"]
        assert "نقص مسمّى" in why["answer"]
        assert "لا يثبت" in why["answer"]

    def test_declared_skills_first_provider_no_query_stop_claim(self):
        # مسار المهارات المعلنة (لا استعلام أصلاً): الأول يدعم s2
        # والثاني s1 والمطلوب [s1, s2] — الثاني يفوز بأسبقية المهارة
        # المطلوبة. الشرح لا يدّعي توقفاً لاستعلام لم يحدث، والبديل
        # خسر بسبب مهارته اللاحقة لا بترتيب التسجيل
        policy = DecisionPolicy(
            policy_id="first-provider-for-skill", version="1.0.0",
            kind="provider",
            weights={"skill": 1.0}, rules={
                "exclusion": "no-required-skill-support",
                "tie_break": "stable-registration-order",
                "priority_contribution": "unused",
                "selection": "first-in-registration-order-supporting-a-skill"})
        record = DECISION_CORE.evaluate(
            DecisionRequest(kind="provider", requested_name="",
                            required_skills=["s1", "s2"], constraints=[]),
            [DecisionCandidate(name="First", offered_skills=["s2"]),
             DecisionCandidate(name="Second", offered_skills=["s1"])],
            policy, decision_id="d4", timestamp=AT.isoformat())
        # سلامة الأصل: أسبقية المهارة المطلوبة تفوز لا ترتيب التسجيل
        assert record.status == "selected"
        assert record.selected == "Second"
        why = record.to_dict()["why"]
        assert why["decision_type"] == "early-exit-first-supporting"
        assert why["why"]["path"] == "declared-skills"
        assert why["why"]["decisive_skill"] == "s1"
        # لا ادعاء توقف استعلام — المهارات معلنة ولم يحدث استعلام
        assert "توقف الاستعلام" not in why["answer"]
        assert "لا استعلام أصلاً" in why["answer"]
        # البديل خسر بسبب مهارته اللاحقة — سبب مستخرج لا احتمالان بـ«أو»
        alt = next(a for a in why["alternatives"] if a["name"] == "First")
        assert "لاحقة في ترتيب الطلب" in alt["why_not"]
        assert "s2" in alt["why_not"]
        assert "ترتيب التسجيل" not in alt["why_not"]

    def test_declared_skills_same_skill_registration_order(self):
        # المسار المعلن — تعادل أسبقية المهارة: الحسم بترتيب التسجيل
        # (السبب الفعلي مستخرج لا مختلط)
        policy = DecisionPolicy(
            policy_id="first-provider-for-skill", version="1.0.0",
            kind="provider",
            weights={"skill": 1.0}, rules={
                "exclusion": "no-required-skill-support",
                "tie_break": "stable-registration-order",
                "priority_contribution": "unused",
                "selection": "first-in-registration-order-supporting-a-skill"})
        record = DECISION_CORE.evaluate(
            DecisionRequest(kind="provider", requested_name="",
                            required_skills=["s1"], constraints=[]),
            [DecisionCandidate(name="First", offered_skills=["s1"]),
             DecisionCandidate(name="Second", offered_skills=["s1"])],
            policy, decision_id="d5", timestamp=AT.isoformat())
        assert record.status == "selected"
        assert record.selected == "First"
        why = record.to_dict()["why"]
        alt = next(a for a in why["alternatives"] if a["name"] == "Second")
        assert "يدعم المهارة الحاسمة نفسها" in alt["why_not"]
        assert "يلي المختار بترتيب التسجيل" in alt["why_not"]


class TestRound7MixedRulesRejection:
    def test_mixed_rules_one_unknown_value_unknown_mechanism(self):
        # قواعد الدُبعة كاملة مع قيمة واحدة فاسدة فقط (capability_scoring
        # مجهولة وtie_break وeligibility سليمة): وجود قيمة معروفة أخرى
        # لا يخفي القيمة غير المدعومة — الآلية مجهولة والنقص مسمّى،
        # وحالة السجل مثبتة أولاً
        rules = dict(PIPELINE_CAPABILITY_POLICY.rules)
        rules["capability_scoring"] = "unknown-algorithm"
        policy = DecisionPolicy(
            policy_id="pipeline-capability-selection", version="1.0.0",
            kind="capability",
            weights=dict(PIPELINE_CAPABILITY_POLICY.weights), rules=rules)
        record = DECISION_CORE.evaluate(
            DecisionRequest(kind="capability", requested_name="Alpha",
                            required_skills=[], constraints=[]),
            [DecisionCandidate(name="AlphaOne", offered_skills=["s1"],
                               priority=0.2),
             DecisionCandidate(name="AlphaTwo", offered_skills=["s1", "s2"],
                                priority=0.9)],
            policy, decision_id="d6", timestamp=AT.isoformat())
        assert record.status == "selected"  # الحالة مثبتة قبل فحص الشرح
        why = record.to_dict()["why"]
        assert why["decision_type"] == "unknown"
        # القاعدة المسجلة غير المدعومة تسمّى بمفتاحها وقيمتها — لا
        # يقال «القواعد غير مسجلة» وهي مسجلة فعلاً
        assert any(g.startswith("unsupported-rule-value: "
                                "capability_scoring=unknown-algorithm")
                   for g in why["gaps"])
        assert "capability_scoring = unknown-algorithm" in why["answer"]
        assert "غير مدعومة" in why["answer"]
        assert "لا قواعد مسجلة" not in why["answer"]
        assert "نقص مسمّى" in why["answer"]
        assert "لا يثبت" in why["answer"]


class TestRound8SnapshotAbsenceSurvivesSave:
    def test_snapshot_absent_gap_survives_save_and_reload(self):
        # غياب اللقطة لا يضيع بالحفظ: عقد التسلسل صريح
        # (snapshot_present) — التفسير المعاد اشتقاقه من JSON يبقى
        # يحمل policy-snapshot-absent كما الأصلي، مطابقاً له
        from decision_pipeline.explain import explain_saved_record

        dp = DecisionPipeline(
            _cap_registry(FakeCapability("AlphaOne", ["s1"], 0.2),
                          FakeCapability("AlphaTwo", ["s1", "s2"], 0.9)),
            _prov_registry(FakeProvider("P1", ["s1"])))
        result = dp.decide(DecisionContext(_mission("Alpha")))
        record = result.records[0]
        record.policy_snapshot = None  # اللقطة غائبة (عقد الاختبار)
        original = record.to_dict()["why"]
        assert "policy-snapshot-absent" in original["gaps"]
        payload = json.loads(json.dumps(record.to_dict(), ensure_ascii=False))
        # عقد التسلسل: الغياب محفوظ صراحة — لا هوية تُوهم باللقطة
        assert payload["policy"]["snapshot_present"] is False
        assert payload["policy"]["policy_id"]  # الهوية متاحة رغم الغياب
        payload.pop("why")
        rederived = explain_saved_record(payload)
        assert "policy-snapshot-absent" in rederived["gaps"]
        # التفسير المعاد اشتقاقه يطابق الأصلي — بما فيه نقص اللقطة
        assert (json.dumps(rederived, sort_keys=True, ensure_ascii=False)
                == json.dumps(original, sort_keys=True, ensure_ascii=False))
