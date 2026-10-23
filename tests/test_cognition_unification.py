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
