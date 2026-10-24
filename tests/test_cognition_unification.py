# -*- coding: utf-8 -*-
"""اختبارات إدراك — إصلاح عيبي ADR-0012 المعاد إنتاجهما (سجل العمل 0076):
- RelationshipEngine كان يرفع AttributeError بكل استدعاء عام (يقرأ _edges
  غير الموجودة عليه).
- فجوة توصيل سجل المهارات: النسيج كان يبني سجلين مستقلين فلا يجد compose
  مهارة سُجلت عبر الواجهة العامة.
الإصلاحات إضافات وتحسينات أجسام فقط (G2) — لا رمز حُذف ولا توقيع تغيّر.
"""


def test_relationship_engine_public_call_no_attribute_error():
    """العيْب الأول (ADR-0012): كان كل استدعاء عام لـfind_relationships يرفع
    AttributeError (self._edges غير موجودة على المحرك) — الآن يقرأ حواف
    الرسم المقيّد إن رُبط به، وبلا رسم لا حواف تُبحث فالناتج فارغ صادق."""
    from agos.cognition.model import RelationshipEngine, WorldGraph
    # بلا رسم مقيّد: لا AttributeError — قائمة فارغة صادقة (لا حواف تُبحث)
    engine = RelationshipEngine()
    assert engine.find_relationships("x") == []
    # برسم مقيّد: العلاقات تُحل من حوافه عبر الإفصاح العام edges()
    graph = WorldGraph()
    graph.add_edge("a", "b", "uses")
    graph.add_edge("c", "a", "depends_on")
    bound = RelationshipEngine(graph)
    assert bound.find_relationships("a") == [
        ("a", "b", "uses"), ("c", "a", "depends_on")]
    assert bound.find_relationships("b") == [("a", "b", "uses")]
    assert bound.find_relationships("missing") == []
    # الإفصاح العام يرجع نسخة (لا يكشف الحقل الخاص للتغيير من خارجه)
    assert graph.edges() == [("a", "b", "uses"), ("c", "a", "depends_on")]
    snapshot = graph.edges()
    snapshot.append(("tamper", "x", "y"))
    assert graph.edges() == [("a", "b", "uses"), ("c", "a", "depends_on")]


def test_skill_fabric_single_registry_compose_finds_public_registrations():
    """العيْب الثاني (ADR-0012): كان النسيج يبني سجلين مستقلين (سجل التسجيل
    وسجل المؤلف) فكانت compose ترجع [] لمهارة سُجلت عبر الواجهة العامة —
    الآن سجل واحد يُشاركه التسجيل والمؤلف، والمهارة المجهولة تبقى غير
    موجودة (لا إيجابية كاذبة)."""
    from agos.cognition.skill import UniversalSkillFabric
    fabric = UniversalSkillFabric()
    # سجل واحد لا سجلين — التوصيل الفعلي مثبت بالهوية
    assert fabric.registry is fabric.composer._registry
    # مهارة سُجلت عبر الواجهة العامة يجدها compose الآن (كانت [])
    skill = fabric.register_skill("demo", "1.0")
    assert skill.skill_id == "skill_demo"
    composed = fabric.composer.compose(["skill_demo"])
    assert len(composed) == 1
    assert composed[0].skill_id == "skill_demo"
    # المجهولة تبقى غير موجودة — لا إيجابية كاذبة
    assert fabric.composer.compose(["skill_missing"]) == []
    # سجل النسيج نفسه يجيب عليها (المسار العام كما كان)
    assert fabric.registry.get("skill_demo").name == "demo"


def test_unsubstantiated_claims_removed_declare_not_executed():
    """العمل 1 في ADR-0012: الادعاءات الثابتة المحددة بالأدلة صارت تصريحاً
    صادقاً بعدم التنفيذ بمسوغ مسمّى — والعمل المنفذ يبقى بنتيجته (فحص الفراغ
    والتسجيلات والصدى الحرفي)."""
    from agos.cognitive import (constraint, deliberation, evaluation,
                                planning, reasoning, strategy)
    from agos.cognition import composition, core, foundation, model
    from agos.cognition import skill as cog_skill

    # حل القيود: لا يُدَّعى حل — والعدد المعلن يعاد حرفياً
    r = constraint.ConstraintSolver().solve(["c1", "c2"])
    assert r["solved"] is False and r["constraints"] == 2
    assert "غير منفذ" in r["reason"]
    # تحقق القيد: False عدم ثبوت لا مخالفة مثبتة
    c = constraint.Constraint(constraint_id="c1", constraint_type="Time",
                              name="t", value=1)
    assert constraint.ConstraintValidator().validate(c) is False
    # التقييم: لا درجات مقيسة تُختلق — المقياس المطلوب يعاد None
    ev = evaluation.EvaluationEngine().evaluate("x", ["Quality", "Risk"])
    assert ev == {"Quality": None, "Risk": None}
    # الاستراتيجية: صدى النوع بلا ادعاء اختيار
    sel = strategy.StrategySelector().select("Fastest", {})
    assert sel["strategy"] == "Fastest" and sel["selected"] is None
    assert "غير منفذ" in sel["reason"]
    # محاكاة الخطة: لا نجاح يُدَّعى — وفحص الفراغ المنفذ يبقى بنتيجته
    plan = planning.MissionPlan(plan_id="p", steps=[{"s": 1}])
    sim = planning.PlanSimulator().simulate(plan)
    assert sim["simulated"] is False and sim["outcome"] is None
    assert "غير منفذة" in sim["reason"]
    assert planning.PlanValidator().validate(plan) is True          # منفذ يبقى
    assert planning.PlanValidator().validate(
        planning.MissionPlan(plan_id="e", steps=[])) is False      # منفذ يبقى
    # الاستنتاجات: لا نصوص تُختلق — والنوع المجهول لا يُدَّعى له استنتاج
    assert reasoning.DeductiveReasoner().reason(["a"]) is None
    assert reasoning.InductiveReasoner().reason(["a"]) is None
    assert reasoning.AbductiveReasoner().reason(["a"]) is None
    rt = reasoning.UniversalReasoningRuntime()
    assert rt.reason("deductive", ["a"]) is None
    assert rt.reason("unknown-type", ["a"]) is None
    # المداولة: لا بدائل تُختلق ولا اكتمال يُدَّعى
    assert deliberation.AlternativeGenerator().generate({}) == []
    d = deliberation.UniversalDeliberationEngine().deliberate({})
    assert d.status == "not_executed" and d.alternatives == []
    # core: تقييم وتحقق بلا ادعاء
    cev = core.EvaluationEngine().evaluate("x", {})
    assert cev["score"] is None and cev["approved"] is None
    cvr = core.VerificationEngine().verify("x")
    assert cvr["verified"] is False and cvr["valid"] is None
    assert "غير منفذ" in cvr["reason"]
    # foundation: لا تحقق ولا قفل يُدَّعى
    fv = foundation.VerificationEngine().verify("Kernel")
    assert fv["verified"] is False and "غير منفذ" in fv["reason"]
    assert all(v is False for v in foundation.AbsoluteFoundation().verify_all().values())
    rel = foundation.AbsoluteFoundation().release()
    assert rel["status"] == "not_locked"
    assert rel["architecture_locked"] is False
    assert rel["kernel_locked"] is False
    assert rel["contracts_locked"] is False
    # model: حالة/تنبؤ لا يُختلقان
    assert model.StateEngine().get_state("x")["status"] is None
    pr = model.PredictionEngine().predict("x")
    assert pr["prediction"] is None and pr["confidence"] is None
    # composition: تحقق/محاكاة لا يُدَّعيان — والحكم الصادق محمول مع التركيب
    comp = composition.UniversalCompositionEngine().compose("n", ["a"])
    assert comp["name"] == "n" and comp["components"] == ["a"]  # التخزين المنفذ يبقى
    assert comp["validated"] is False
    assert "غير منفذ" in comp["validation_reason"]
    assert composition.CompositionSimulator().simulate(comp)["status"] == "not_simulated"
    # skill: قياس لا يُختلق
    bm = cog_skill.SkillBenchmark().benchmark("s")
    assert bm["skill_id"] == "s" and bm["latency_ms"] is None and bm["cost"] is None


def test_intent_registry_distinct_ids_preserve_independent_intents():
    """العمل 3 في ADR-0012: كان معرّف النية الثابت يستبدل السابق (total=1
    لنيتين) — الآن معرّفات مميزة تحفظ السجل نوايا مستقلة."""
    from agos.cognitive.intent import UniversalIntentEngine
    eng = UniversalIntentEngine()
    i1 = eng.create_intent("أول نية")
    i2 = eng.create_intent("نية ثانية")
    assert i1.intent_id != i2.intent_id                     # مميزة
    assert eng.get_statistics()["total_intents"] == 2       # كانت 1
    # الأولى لم تُستبدل — التسجيل يحفظ نوايا مستقلة
    assert eng.registry.get(i1.intent_id).description == "أول نية"
    assert eng.registry.get(i2.intent_id).description == "نية ثانية"


def test_class_docstrings_distinguish_implemented_from_promises():
    """العمل 4 في ADR-0012: وصف الصنف لا يعد بما لا ينفذ — الوعود غير
    المنفذة متميزة صراحة عن المنفذ."""
    from agos.cognitive.decision import UniversalDecisionPlatform
    from agos.cognitive.intent import UniversalIntentEngine
    for cls in (UniversalDecisionPlatform, UniversalIntentEngine):
        doc = cls.__doc__
        assert "غير منفذ" in doc        # الوعود مُيّزت صراحة
        assert "منفذ فعلاً" in doc      # والمنفذ موصوف بحدوده
