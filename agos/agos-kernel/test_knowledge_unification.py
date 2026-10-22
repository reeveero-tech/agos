#!/usr/bin/env python3
"""اختبارات توحيد كائن المعرفة — R-W1-005 / ADR-0002 (المادة 13).

تثبت أن:
- النموذج المعتمد `knowledge.models.Knowledge` يحقق متطلبات المادة 13 (قبول/رفض لكل متطلب).
- الإنشاء عبر واجهات التشغيل الفعلية (النووية والحضارية) يختم الحالة تلقائياً.
- التحويل ذهاباً وإياباً بين الأسر يحفظ الحقول بلا فقد صامت، والنقص يُعلن لا يُختلق.
- هوية النموذج واحدة عبر مسارات الاستيراد المدعومة (قاعدة ADR-0001).
- متطلبات المدقق متطابقة حرفياً مع ثابت الدستور.
"""
# R-F-002 portable paths (see tools/migrate/portable_paths.py)
import os as _agos_os
from pathlib import Path as _AgosPath
_AGOS_ROOT = _AgosPath(_agos_os.environ.get('AGOS_ROOT') or _AgosPath(__file__).resolve().parents[1])
_AGOS_KERNEL = _AGOS_ROOT / 'agos-kernel'
import sys

sys.path.insert(0, str(_AGOS_KERNEL))
import agos_kernel  # R-F-005: مساحة الاسم الموحدة (ADR-0001)

from knowledge.runtime import KnowledgeRuntime as KernelKnowledgeRuntime
from knowledge.models import (
    Knowledge, KnowledgeType, KnowledgeMetadata, Evidence,
)
from knowledge.article13 import (
    ARTICLE_13_REQUIREMENTS, validate_article_13, article13_status,
)
from civilization.knowledge_runtime import (
    KnowledgeRuntime as CivilizationKnowledgeRuntime,
    KnowledgeType as CivilizationKnowledgeType, KnowledgeObject,
)


def _full_kernel_knowledge() -> Knowledge:
    """كائن معرفة مكتمل دستورياً عبر واجهة التشغيل النووية الفعلية."""
    runtime = KernelKnowledgeRuntime()
    return runtime.create_knowledge(
        title="Kernel owns knowledge",
        knowledge_type=KnowledgeType.FACT,
        source="constitution.py",
        evidence=[Evidence(id="ev-1", content="Article 11", source="constitution.py")],
        confidence=0.9,
        lineage=[],                      # جذر معلن صراحة
        version="1.1.0",
    )


def test_article13_acceptance():
    """قبول: كائن مكتمل عبر الواجهة النووية → صفر خرق وختم صالح."""
    runtime = KernelKnowledgeRuntime()
    k = runtime.create_knowledge(
        title="Kernel owns knowledge",
        knowledge_type=KnowledgeType.FACT,
        source="constitution.py",
        evidence=[Evidence(id="ev-1", content="Article 11", source="constitution.py")],
        confidence=0.9,
        lineage=[],
        version="1.1.0",
    )
    # R-W1-001: التحقق يعيد قائمة خرق فارغة لكائن مكتمل
    assert validate_article_13(k) == [], validate_article_13(k)
    status = article13_status(k)
    assert status["valid"] is True, status
    # الختم عند التخزين: حد الاعتماد (ADR-0002)
    assert runtime.article13_index[k.id]["valid"] is True


def test_article13_rejection_each_requirement():
    """رفض: كل متطلب من الستة يُرفض باسمه عند انتهاكه وحده."""
    from datetime import datetime
    base = dict(
        id="k-reject",
        knowledge_type=KnowledgeType.FACT,
        metadata=KnowledgeMetadata(
            title="t", version="1.0.0", sources=["src.py"],
        ),
        source="src.py",
        evidence=[Evidence(id="e", content="c", source="src.py")],
        confidence=0.5,
        lineage=[],
        created_at=datetime(2026, 10, 22, 12, 0),  # طابع صالح — إلا حالة Timestamp
    )
    # Source خاوٍ
    v = validate_article_13(Knowledge(**{**base, "source": ""}))
    assert [x["requirement"] for x in v] == ["Source"], v
    # Source أولي خارج قائمة المصادر (تضارب مصدرين)
    v = validate_article_13(Knowledge(**{**base, "source": "other.md"}))
    assert [x["requirement"] for x in v] == ["Source"], v
    # لا أدلة
    v = validate_article_13(Knowledge(**{**base, "evidence": []}))
    assert [x["requirement"] for x in v] == ["Evidence"], v
    # دليل بلا مصدر
    v = validate_article_13(Knowledge(**{
        **base, "evidence": [Evidence(id="e", content="c", source="")]}))
    assert [x["requirement"] for x in v] == ["Evidence"], v
    # ثقة مجهولة
    v = validate_article_13(Knowledge(**{**base, "confidence": None}))
    assert [x["requirement"] for x in v] == ["Confidence"], v
    # ثقة خارج النطاق
    v = validate_article_13(Knowledge(**{**base, "confidence": 1.5}))
    assert [x["requirement"] for x in v] == ["Confidence"], v
    v = validate_article_13(Knowledge(**{**base, "confidence": -0.1}))
    assert [x["requirement"] for x in v] == ["Confidence"], v
    # إصدار خاوٍ
    v = validate_article_13(Knowledge(**{**base, "metadata": KnowledgeMetadata(title="t", version="")}))
    assert [x["requirement"] for x in v] == ["Version"], v
    # طابع زمني مفقود
    v = validate_article_13(Knowledge(**{**base, "created_at": None}))
    assert [x["requirement"] for x in v] == ["Timestamp"], v
    # نسب مجهول
    v = validate_article_13(Knowledge(**{**base, "lineage": None}))
    assert [x["requirement"] for x in v] == ["Lineage"], v


def test_confidence_and_lineage_semantics():
    """دلالات ADR-0002: الثقة 0.0 معلنة مقبولة، والجذر الصريح [] نسب صالح."""
    k = _full_kernel_knowledge()
    k.confidence = 0.0
    v = validate_article_13(k)
    assert not [x for x in v if x["requirement"] == "Confidence"], v
    k.confidence = None
    v = validate_article_13(k)
    assert [x for x in v if x["requirement"] == "Confidence"], v


def test_kernel_runtime_report_and_stamping():
    """حد الاعتماد النووي: الختم عند التخزين والتقرير يجمع المكتمل والناقص."""
    runtime = KernelKnowledgeRuntime()
    runtime.create_knowledge(
        title="complete", knowledge_type=KnowledgeType.FACT, source="s.py",
        evidence=[Evidence(id="e", content="c", source="s.py")],
        confidence=0.8, lineage=[], version="1.0.0",
    )
    runtime.create_knowledge(title="gap", knowledge_type=KnowledgeType.RULE)  # نداء قديم ناقص
    report = runtime.article13_report()
    # R-W1-001: تقرير يطابق ما خُزن فعلاً — مكتمل واحد وناقص واحد
    assert report["total"] == 2, report
    assert report["constitutionally_complete"] == 1, report
    assert report["incomplete"] == 1, report
    assert report["by_requirement"]["Source"] == 1, report
    assert report["by_requirement"]["Lineage"] == 1, report


def test_civilization_runtime_wiring():
    """الأسرة الحضارية: الإنشاء الفعلي يختم المادة 13 — الكامل مقبول والناقص معلن."""
    runtime = CivilizationKnowledgeRuntime()
    complete = runtime.create_knowledge(
        CivilizationKnowledgeType.FACT, "The kernel owns knowledge",
        source="constitution.py", confidence=0.9, version="1.1.0",
        evidence=[{"source": "constitution.py", "content": "Article 11"}],
        lineage=[],
    )
    # R-W1-001: كائن مكتمل عبر واجهة التشغيل الحضارية → ختم صالح
    # (زمن الإنشاء حقيقي يُختم مرة عند الإنشاء — والثقة معلنة والنسب جذر صريح)
    assert complete.article13["valid"] is True, complete.article13
    assert complete.article13["violations"] == []
    # الثقة المجهولة لا تُختلق 1.0 — تعلن نقصاً باسمها
    unknown_conf = runtime.create_knowledge(
        CivilizationKnowledgeType.FACT, "unknown confidence", source="s.py",
        confidence=None, version="1.0.0",
        evidence=[{"source": "s.py", "content": "proof"}], lineage=[],
    )
    v = [x for x in unknown_conf.article13["violations"] if x["requirement"] == "Confidence"]
    assert v, unknown_conf.article13
    # النداء القديم (ناقص) يعمل كما كان والنقص معلن باسمه
    legacy = runtime.create_knowledge(CivilizationKnowledgeType.RULE, "old call")
    gaps = {v["requirement"] for v in legacy.article13["violations"]}
    assert gaps == {"Source", "Evidence", "Lineage"}, gaps


def test_civilization_roundtrip_no_silent_loss():
    """ذهاب وإياب (الحضارة): حفظ كامل بلا فقد — نوع غير FACT، مصدران، دليل كامل
    الحقول، علاقات، بيانات مجال، وزمن أصل معلن."""
    from datetime import datetime
    created = datetime(2025, 3, 10, 8, 30)
    ko = KnowledgeObject(
        ko_id="rt-1",
        knowledge_type=CivilizationKnowledgeType.RULE,
        content="structured deployment rule with details",
        source="primary.py", confidence=0.7, version="2.3.0",
        relationships=["ko-a", "ko-b"],
        metadata={"team": "platform", "review_cycle": 3,
                  "canonical_metadata": {"sources": ["primary.py", "secondary.md"],
                                         "title": "t", "description": "d"}},
        evidence=[{"source": "primary.py", "content": "proof", "source_url": "http://x/1",
                   "quality": "high", "verified": True, "verified_by": "auditor",
                   "metadata": {"line": 42}}],
        lineage=["parent-1", "parent-2"],
        created_at=created,
    )
    canonical = ko.to_canonical()
    # R-W1-001: كل الحقول الأساسية تصل المعتمد كما هي — النوع والثقة والإصدار
    assert canonical.id == ko.ko_id
    assert canonical.summary == ko.content
    assert canonical.source == "primary.py"
    assert canonical.confidence == 0.7
    assert canonical.metadata.version == "2.3.0"
    # المصدران محفوظان معاً — لا اختزال إلى الأولي
    assert canonical.metadata.sources == ["primary.py", "secondary.md"]
    # الدليل كامل الحقول — المعرف والجودة والرابط والتحقق والبيانات
    ev = canonical.evidence[0]
    assert ev.source == "primary.py" and ev.source_url == "http://x/1"
    assert ev.quality.value == "high" and ev.verified is True
    assert ev.verified_by == "auditor" and ev.metadata == {"line": 42}
    assert canonical.related_to == ["ko-a", "ko-b"]      # العلاقات بقيت علاقات
    assert canonical.lineage == ["parent-1", "parent-2"]
    assert canonical.origin == "imported" and canonical.imported_at is not None
    assert canonical.created_at == created                # زمن الأصل محفوظ كما هو
    assert canonical.domain_extras == {"team": "platform", "review_cycle": 3}
    # العودة تحفظ كل شيء بلا فقد صامت
    back = KnowledgeObject.from_canonical(canonical)
    assert back.ko_id == ko.ko_id
    assert back.knowledge_type == CivilizationKnowledgeType.RULE   # النوع يعود كما كان
    assert back.content == ko.content
    assert back.source == ko.source
    assert back.confidence == ko.confidence
    assert back.version == ko.version
    assert back.relationships == ko.relationships
    assert back.lineage == ko.lineage
    assert back.created_at == created                     # الزمن يعود كما هو
    # الدليل يعود كامل الحقول
    bev = back.evidence[0]
    assert bev["source"] == "primary.py" and bev["source_url"] == "http://x/1"
    assert bev["quality"] == "high" and bev["verified"] is True
    assert bev["verified_by"] == "auditor" and bev["metadata"] == {"line": 42}
    # بيانات المجال تعود كما هي
    assert back.metadata["team"] == "platform" and back.metadata["review_cycle"] == 3
    assert back.metadata["canonical_metadata"]["sources"] == ["primary.py", "secondary.md"]


def test_civilization_relationships_are_not_lineage():
    """العلاقات لا تصبح نسباً (ADR-0002): تبقى محفوظة بعلاقاتها والنسب مستقل عنها."""
    ko = KnowledgeObject(content="c", source="s", relationships=["other-ko"], lineage=[])
    canonical = ko.to_canonical()
    # R-W1-001: العلاقة محفوظة كعلاقة (related_to) — والنسب مستقل عنها
    assert canonical.related_to == ["other-ko"]
    assert canonical.lineage == []
    v = validate_article_13(canonical)
    assert not [x for x in v if x["requirement"] == "Lineage"], v


def test_fabric_roundtrip_preserves_original_timestamp():
    """أسرة fabric: الطابع الأصلي محفوظ (ليس وقت التحويل) والذهاب والإياب بلا فقد —
    شاملاً embeddings وrank وحقول provenance غير المشتركة."""
    from datetime import datetime, timezone
    from agos.fabric.knowledge import KnowledgeObject as FabricObject, KnowledgeFabric
    original_time = datetime(2025, 6, 15, 12, 0, tzinfo=timezone.utc)
    fo = FabricObject(
        id="fab-1", source="docs/spec.md", content="Fabric knowledge",
        embeddings=[0.1, 0.2, 0.3], rank=4.5,
        provenance={
            "lineage": [], "version": "3.0.0", "confidence": 0.6,
            "evidence": [{"source": "docs/spec.md", "content": "section 2"}],
            "region": "eu-1",   # حقل مجال غير مشترك
        },
        created_at=original_time,
    )
    canonical = fo.to_canonical()
    # R-W1-001: الطابع الزمني الأصلي يصل كما هو — لا يُستبدل بوقت التحويل
    assert canonical.created_at == original_time, canonical.created_at
    assert canonical.source == "docs/spec.md"
    assert canonical.confidence == 0.6
    assert canonical.metadata.version == "3.0.0"
    assert canonical.lineage == []
    assert canonical.origin == "imported"
    # حقول المجال غير المشتركة محفوظة في domain_extras — لا فقد
    assert canonical.domain_extras["embeddings"] == [0.1, 0.2, 0.3]
    assert canonical.domain_extras["rank"] == 4.5
    assert canonical.domain_extras["provenance_extras"] == {"region": "eu-1"}
    back = FabricObject.from_canonical(canonical)
    assert back.created_at == original_time
    assert back.source == fo.source
    assert back.provenance["version"] == "3.0.0"
    assert back.provenance["lineage"] == []
    assert back.provenance["confidence"] == 0.6
    assert back.provenance["region"] == "eu-1"           # حقل المجال عاد كما هو
    assert back.embeddings == [0.1, 0.2, 0.3]           # والـembeddings عادت
    assert back.rank == 4.5                              # والترتيب عاد
    # الربط الفعلي: النسيج يقبل ويقرأ بالمعتمد (البابان الجديدان)
    fabric = KnowledgeFabric()
    fabric.add_canonical(canonical)
    fetched = fabric.get_canonical("fab-1")
    assert fetched.id == "fab-1"
    assert fetched.created_at == original_time
    assert fetched.domain_extras["rank"] == 4.5


def test_fabric_unknown_fields_are_declared_not_invented():
    """نقص fabric يُعلن ولا يُختلق: بلا إصدار/ثقة في provenance → خرق معلن."""
    from agos.fabric.knowledge import KnowledgeObject as FabricObject
    fo = FabricObject(id="fab-2", source="s", content="c", provenance={})
    canonical = fo.to_canonical()
    # R-W1-001: الإصدار المجهول يبقى خاوياً — لا يُختلق 1.0.0
    assert canonical.metadata.version == "", canonical.metadata.version
    v = validate_article_13(canonical)
    reqs = {x["requirement"] for x in v}
    assert {"Version", "Confidence", "Evidence", "Lineage"} <= reqs, reqs


def test_model_identity_single_object():
    """هوية واحدة (ADR-0001): النموذج لا يُحمَّل مرتين نوعين عبر مساري الاستيراد."""
    import knowledge.models as plain
    import agos_kernel.knowledge.models as namespaced
    # R-W1-001: نفس كائن الوحدة — لا نسختين تتباعدان
    assert plain is namespaced, (plain, namespaced)
    assert plain.Knowledge is namespaced.Knowledge


def test_constitution_sync():
    """المزامنة مع الدستور: متطلبات المدقق مطابقة حرفياً لثابت المادة 13."""
    import importlib.util
    repo = _AgosPath(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location(
        "agos_constitution_for_sync", repo / "agos" / "constitution" / "constitution.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    # R-W1-001: أي تعديل دستوري لاحق يكسر هذه المساواة فوراً
    assert ARTICLE_13_REQUIREMENTS == mod.KNOWLEDGE_OBJECT_REQUIREMENTS


def test_version_property_delegates_to_metadata():
    """خاصية الإصدار تفوّض إلى metadata.version — مصدر حقيقة واحد (قراءة وتحديث)."""
    k = _full_kernel_knowledge()
    assert k.version == "1.1.0"
    k.version = "2.0.0"
    # R-W1-001: التحديث عبر الخاصية يعدل مصدر الحقيقة الوحيد
    assert k.metadata.version == "2.0.0"
    # asdict لا يضم الخصائص — الإصدار يُسلسل عبر metadata فقط (ADR-0002)
    import dataclasses
    d = dataclasses.asdict(k)
    assert "version" not in d, sorted(d)
    assert d["metadata"]["version"] == "2.0.0"


def test_old_constructors_still_work():
    """توافق المنشئات القديمة: الإنشاء بالحقول القديمة فقط يعمل والنقص معلن."""
    metadata = KnowledgeMetadata(title="legacy")
    k = Knowledge(id="legacy-1", knowledge_type=KnowledgeType.CONCEPT, metadata=metadata)
    # R-W1-001: المنشئ القديم لم ينكسر — والحقول الجديدة بقيمها الصادقة
    assert k.source == "" and k.confidence is None and k.lineage is None
    assert k.origin == "native" and k.imported_at is None
    v = validate_article_13(k)
    reqs = {x["requirement"] for x in v}
    assert reqs == {"Source", "Evidence", "Confidence", "Lineage"}, reqs


def test_stale_status_detected_not_hidden():
    """انحدار الحالة المبيتة: تعديل الكائن يظهر فوراً في الحالة والتقارير (لا صلاحية قديمة)."""
    runtime = KernelKnowledgeRuntime()
    k = runtime.create_knowledge(
        title="then broken", knowledge_type=KnowledgeType.FACT, source="s.py",
        evidence=[Evidence(id="e", content="c", source="s.py")],
        confidence=0.8, lineage=[], version="1.0.0",
    )
    assert runtime.article13_report()["constitutionally_complete"] == 1
    # R-W1-001: بعد تعطيل المصدر — التقرير الحي يكشف الخلل فوراً لا يعرض القديم
    k.source = ""
    report = runtime.article13_report()
    assert report["constitutionally_complete"] == 0, report
    assert report["by_requirement"]["Source"] == 1, report
    # والأسرة الحضارية: خاصية article13 حية — لا تبيت بعد التعديل
    civ = CivilizationKnowledgeRuntime()
    ko = civ.create_knowledge(CivilizationKnowledgeType.FACT, "then broken", source="s.py",
                              confidence=0.8, version="1.0.0",
                              evidence=[{"source": "s.py", "content": "c"}], lineage=[])
    assert ko.article13["valid"] is True
    ko.confidence = None
    # R-W1-001: التعديل ينعكس فوراً على الحالة المحسوبة
    assert ko.article13["valid"] is False
    assert [v["requirement"] for v in ko.article13["violations"]] == ["Confidence"]


def test_validator_rejects_empty_string_forms():
    """رفض الصيغ الشكلية: سلسلة خاوية ليست طابعاً زمنياً وليست نسباً."""
    from datetime import datetime
    base = dict(
        id="k-str", knowledge_type=KnowledgeType.FACT,
        metadata=KnowledgeMetadata(title="t", version="1.0.0", sources=["s"]),
        source="s", evidence=[Evidence(id="e", content="c", source="s")],
        confidence=0.5, created_at=datetime(2026, 10, 22),
    )
    v = validate_article_13(Knowledge(**{**base, "lineage": ""}))
    assert [x["requirement"] for x in v] == ["Lineage"], v
    v = validate_article_13(Knowledge(**{**base, "lineage": [], "created_at": ""}))
    assert [x["requirement"] for x in v] == ["Timestamp"], v


def test_timestamp_stable_across_repeated_conversions():
    """ثبات الزمن: التحويل المتكرر لا يولد طوابع جديدة — الأصل يبقى هو المرجع."""
    ko = KnowledgeObject(content="c", source="s", lineage=[], created_at=None)
    civ_runtime = CivilizationKnowledgeRuntime()
    created = civ_runtime.create_knowledge(CivilizationKnowledgeType.FACT, "x", source="s")
    assert created.created_at is not None
    c1 = created.to_canonical()
    c2 = created.to_canonical()
    # R-W1-001: نفس زمن الأصل في كل تحويل — لا طابع جديد لكل استدعاء
    assert c1.created_at == created.created_at == c2.created_at
    # وكائن بلا زمن أصل معلوم يبقى مجهول الزمن (نقص معلن لا مختلق)
    assert ko.to_canonical().created_at is None


def test_unknown_confidence_survives_full_roundtrip():
    """انحدار اختلاق الثقة: None تذهب وتعود كما هي — لا تتحول 1.0 في أي اتجاه."""
    ko = KnowledgeObject(content="c", source="s", confidence=None, lineage=[])
    canonical = ko.to_canonical()
    assert canonical.confidence is None
    back = KnowledgeObject.from_canonical(canonical)
    # R-W1-001: المجهولة تعود مجهولة — بلا قيمة مختلقة وبلا راية تُقرأ
    assert back.confidence is None
    again = back.to_canonical()
    assert again.confidence is None


def test_kernel_roundtrip_through_civilization_family():
    """معتمد → حضارة → معتمد: النوع والمحتوى والمصدر والثقة والإصدار والنسب والأدلة تعود كاملة."""
    runtime = KernelKnowledgeRuntime()
    k = runtime.create_knowledge(
        title="full kernel knowledge", knowledge_type=KnowledgeType.RULE,
        source="src.py",
        evidence=[Evidence(id="e1", content="proof", source="src.py")],
        confidence=0.85, lineage=["root-a"], version="4.2.0",
    )
    via_family = KnowledgeObject.from_canonical(k)
    # R-W1-001: النوع RULE عاد RULE — لا سقوطاً إلى FACT
    assert via_family.knowledge_type == CivilizationKnowledgeType.RULE
    assert via_family.source == "src.py"
    assert via_family.confidence == 0.85
    assert via_family.version == "4.2.0"
    assert via_family.lineage == ["root-a"]
    assert via_family.evidence[0]["source"] == "src.py"
    back = via_family.to_canonical()
    assert back.id == k.id
    assert back.knowledge_type == KnowledgeType.RULE
    assert back.source == "src.py" and back.confidence == 0.85
    assert back.metadata.version == "4.2.0"
    assert back.lineage == ["root-a"]
    assert back.evidence[0].source == "src.py"
    assert back.created_at == k.created_at          # زمن الأصل عبر الرحلة كاملة


def test_civilization_registry_reads_through_canonical():
    """الربط الفعلي: السجل يقرأ بالمعتمد — التسجيل والقراءة والتحديث عبر الواجهات القائمة."""
    runtime = CivilizationKnowledgeRuntime()
    ko = runtime.create_knowledge(
        CivilizationKnowledgeType.PATTERN, "observed pattern", source="analysis.py",
        confidence=0.9, version="1.0.0",
        evidence=[{"source": "analysis.py", "content": "found"}], lineage=[],
    )
    canonical_view = runtime.registry.get_canonical(ko.ko_id)
    # R-W1-001: القراءة بالمعتمد تعطي ما سُجل فعلاً
    assert canonical_view.id == ko.ko_id
    assert canonical_view.source == "analysis.py"
    # التحديث عبر الواجهة القائمة (relate) يظهر في التمثيل المعتمد فوراً
    other = runtime.create_knowledge(CivilizationKnowledgeType.FACT, "related",
                                    source="analysis.py", confidence=0.9,
                                    evidence=[{"source": "analysis.py", "content": "f"}],
                                    lineage=[])
    runtime.relate(ko.ko_id, other.ko_id)
    updated_view = runtime.registry.get_canonical(ko.ko_id)
    # R-W1-001: العلاقة الجديدة ظهرت كعلاقة — لا كنسب
    assert other.ko_id in (updated_view.related_to or [])
    assert updated_view.lineage == []


def test_model_identity_both_import_orders():
    """هوية النموذج في الترتيبين: مفسّران جديدان — كل ترتيب تحميل يعطي كائناً واحداً."""
    import subprocess, sys, json
    repo = str(_AgosPath(__file__).resolve().parents[2])
    kernel = str(_AGOS_KERNEL)
    code_a = ("import sys, json; sys.path.insert(0, %r); import agos_kernel, "
              "knowledge.models as plain, agos_kernel.knowledge.models as ns; "
              "print(json.dumps(plain is ns))" % kernel)
    code_b = ("import sys, json; sys.path.insert(0, %r); import agos_kernel, "
              "agos_kernel.knowledge.models as ns, knowledge.models; "
              "print(json.dumps(ns is knowledge.models))" % kernel)
    # R-W1-001: كلا ترتيبَي الاستيراد يعطي نفس كائن الوحدة — لا نسختين
    for code in (code_a, code_b):
        r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                           cwd=repo, timeout=60)
        assert r.returncode == 0, r.stderr
        assert json.loads(r.stdout.strip()) is True, (code, r.stdout, r.stderr)


def _rich_canonical():
    """كائن معرفي غني: نوع غير مشترك، محتوى منظم، عنوان ووصف مميزان، مصدران،
    دليل كامل بزمن قديم ثابت، وبيانات مجال إضافية."""
    from datetime import datetime
    runtime = KernelKnowledgeRuntime()
    k = runtime.create_knowledge(
        title="Data retention policy", knowledge_type=KnowledgeType.POLICY,
        content={"raw": "retention rule", "structured": {"days": 90, "regions": ["eu", "me"]}},
        source="docs/policy.md",
        evidence=[Evidence(id="ev-rt", content="retention clause", source="docs/policy.md",
                           collected_at=datetime(2024, 5, 4, 9, 15))],
        confidence=0.95, lineage=[], version="5.1.0",
    )
    k.metadata.title = "Data retention policy"
    k.metadata.description = "how long we keep data"
    k.metadata.sources = ["docs/policy.md", "docs/legal.md"]
    k.domain_extras = {"region": "eu-1", "review_cycle": 7}
    return k


def test_evidence_collected_at_preserved_exactly():
    """انحدار زمن الدليل: الزمن القديم الثابت يعود كما هو — لا يُستبدل بزمن التحويل،
    والمجهول يبقى مجهولاً معلناً (لا يُختلق now())."""
    from datetime import datetime
    old_time = datetime(2024, 5, 4, 9, 15)
    ko = KnowledgeObject(
        ko_id="ev-rt", content="c", source="s", lineage=[],
        evidence=[{"source": "s", "content": "proof",
                   "collected_at": old_time.isoformat()}],
    )
    canonical = ko.to_canonical()
    ev = canonical.evidence[0]
    # R-W1-001: الزمن القديم الثابت وصل كما هو — لا زمن تحويل مختلق
    assert ev.collected_at == old_time, (ev.collected_at, old_time)
    # والعودة تسلسله كما هو (صورة ISO مطابقة)
    back_dict = KnowledgeObject.from_canonical(canonical).evidence[0]
    assert back_dict["collected_at"] == old_time.isoformat(), back_dict
    # والمجهول يبقى مجهولاً — لا now() مختلقة
    ko2 = KnowledgeObject(ko_id="ev-rt2", content="c", source="s", lineage=[],
                          evidence=[{"source": "s", "content": "proof"}])
    c2 = ko2.to_canonical()
    assert c2.evidence[0].collected_at is None, c2.evidence[0].collected_at


def test_rich_canonical_through_civilization_family():
    """معتمد غني → حضارة → معتمد: كل الحقول تعود — النوع غير المشترك (POLICY)،
    المحتوى المنظم، العنوان والوصف، المصدران، زمن الدليل، بيانات المجال."""
    k = _rich_canonical()
    via_family = KnowledgeObject.from_canonical(k)
    back = via_family.to_canonical()
    # R-W1-001: النوع غير المشترك يعود كما هو — لا سقوطاً إلى أقرب معنى
    assert back.knowledge_type == KnowledgeType.POLICY, back.knowledge_type
    # المحتوى المنظم كاملاً — لا اختزالاً إلى raw
    assert back.content == {"raw": "retention rule",
                            "structured": {"days": 90, "regions": ["eu", "me"]}}, back.content
    # العنوان والوصف المميزان يعودان
    assert back.metadata.title == "Data retention policy"
    assert back.metadata.description == "how long we keep data"
    # المصدران يعودان معاً
    assert back.metadata.sources == ["docs/policy.md", "docs/legal.md"]
    # زمن الدليل القديم يعود كما هو
    assert back.evidence[0].collected_at == k.evidence[0].collected_at
    # بيانات المجال تعود كما هي
    assert back.domain_extras == {"region": "eu-1", "review_cycle": 7}


def test_rich_canonical_through_fabric_family():
    """معتمد غني → fabric → معتمد: النوع غير FACT والمصدر الثاني والمفاتيح العامة
    لبيانات المجال تعود — لا يُسقط ما لا يعرفه fabric صامتاً."""
    from agos.fabric.knowledge import KnowledgeObject as FabricObject
    k = _rich_canonical()
    via_family = FabricObject.from_canonical(k)
    back = via_family.to_canonical()
    # R-W1-001: النوع غير FACT يعود كما هو
    assert back.knowledge_type == KnowledgeType.POLICY, back.knowledge_type
    # المصدران يعودان — لا اختزال إلى المصدر الأولي
    assert back.metadata.sources == ["docs/policy.md", "docs/legal.md"]
    # المفاتيح العامة لبيانات المجال تعود كما هي (لا المفاتيح المعروفة فقط)
    assert back.domain_extras["region"] == "eu-1"
    assert back.domain_extras["review_cycle"] == 7
    assert back.domain_extras["embeddings"] == []
    assert back.domain_extras["rank"] == 0.0


def test_registration_enforces_article13_automatically():
    """حد الاعتماد إلزامي في الواجهات القديمة نفسها — لا يتذكر المستهلك استدعاء الفحص:
    تسجيل الحضارة يختم التدقيق، وإضافة fabric القديمة تختمه، والتقارير حية."""
    civ = CivilizationKnowledgeRuntime()
    legacy = civ.create_knowledge(CivilizationKnowledgeType.RULE, "old call")
    # R-W1-001: التسجيل ختم التدقيق تلقائياً — النقص مسجل باسمه في سجل التسجيل
    audit = civ.registry.article13_audit.get(legacy.ko_id)
    assert audit is not None, civ.registry.article13_audit
    assert audit["valid"] is False
    assert {v["requirement"] for v in audit["violations"]} == {"Source", "Evidence", "Lineage"}
    # والتقرير الحي على مستوى السجل يجمع الكل
    report = civ.registry.article13_report()
    assert report["incomplete"] >= 1 and report["by_requirement"]["Source"] >= 1
    from agos.fabric.knowledge import KnowledgeObject as FabricObject, KnowledgeFabric
    fabric = KnowledgeFabric()
    fo = FabricObject(id="fab-audit", source="s", content="c")  # ناقص
    fabric.add(fo)
    # R-W1-001: الإضافة عبر المسار القديم نفسه ختمت التدقيق تلقائياً
    stamped = fabric.article13_log.get("fab-audit")
    assert stamped is not None, fabric.article13_log
    assert stamped["valid"] is False
    assert {v["requirement"] for v in stamped["violations"]} == {
        "Version", "Confidence", "Evidence", "Lineage"}


def test_validator_rejects_wrong_types():
    """رفض الأنواع: السلسلة غير التاريخية ليست طابعاً، ومعرف مفرد ليس قائمة نسب،
    والرقم ليس قائمة."""
    from datetime import datetime
    base = dict(
        id="k-typed", knowledge_type=KnowledgeType.FACT,
        metadata=KnowledgeMetadata(title="t", version="1.0.0", sources=["s"]),
        source="s", evidence=[Evidence(id="e", content="c", source="s")],
        confidence=0.5, lineage=[], created_at=datetime(2026, 10, 22),
    )
    # R-W1-001: السلسلة غير التاريخية ترفض — ليست "خاوية" فحسب
    v = validate_article_13(Knowledge(**{**base, "created_at": "ليس تاريخاً"}))
    assert [x["requirement"] for x in v] == ["Timestamp"], v
    # معرف مفرد (سلسلة) ليس قائمة نسب
    v = validate_article_13(Knowledge(**{**base, "lineage": "parent-1"}))
    assert [x["requirement"] for x in v] == ["Lineage"], v
    # رقم ليس قائمة نسب
    v = validate_article_13(Knowledge(**{**base, "lineage": 123}))
    assert [x["requirement"] for x in v] == ["Lineage"], v


def test_fabric_rich_roundtrip_full_fields():
    """انحدار فقد fabric: المحتوى المنظم والعنوان والوصف وزمن الدليل تعود كما هي."""
    from agos.fabric.knowledge import KnowledgeObject as FabricObject
    k = _rich_canonical()
    via_family = FabricObject.from_canonical(k)
    back = via_family.to_canonical()
    # R-W1-001: المحتوى المنظم كاملاً يعود — لا اختزالاً إلى raw
    assert back.content == k.content, (back.content, k.content)
    # العنوان والوصف المميزان يعودان — لا اشتقاقاً من المحتوى
    assert back.metadata.title == k.metadata.title, back.metadata.title
    assert back.metadata.description == k.metadata.description
    # زمن الدليل القديم يعود كما هو
    assert back.evidence[0].collected_at == k.evidence[0].collected_at


def test_civilization_extension_does_not_override_updates():
    """امتداد التوافق يحفظ ما لا تمثله الأسرة — لكنه لا يلغي تحديثاً لحقل علبي:
    تعديل النوع أو المحتوى بعد from_canonical يظهر في التمثيل المعتمد."""
    k = _rich_canonical()
    ko = KnowledgeObject.from_canonical(k)
    # تعديل النوع العلبي بعد التحويل
    ko.knowledge_type = CivilizationKnowledgeType.PATTERN
    back = ko.to_canonical()
    # R-W1-001: النوع الحالي يسود — الامتداد القديم لا يلغي تحديثاً حياً
    assert back.knowledge_type == KnowledgeType.PATTERN, back.knowledge_type
    # وتعديل المحتوى العلبي يظهر في raw — لا ظلاً قديماً
    ko2 = KnowledgeObject.from_canonical(k)
    ko2.content = "updated live content"
    back2 = ko2.to_canonical()
    assert back2.content["raw"] == "updated live content", back2.content
    # والجزء المنظم المحفظ يبقى (ما لا تمثله الأسرة)
    assert back2.content["structured"] == {"days": 90, "regions": ["eu", "me"]}


def test_evidence_collected_at_unconvertible_preserved():
    """قيمة زمن غير قابلة للتحويل (رقم): تُحفظ خاماً ويعلن الزمن مجهولاً — لا فقداً صامتاً."""
    ko = KnowledgeObject(
        ko_id="ev-raw", content="c", source="s", lineage=[],
        evidence=[{"source": "s", "content": "proof", "collected_at": 123}],
    )
    canonical = ko.to_canonical()
    ev = canonical.evidence[0]
    # R-W1-001: الزمن مجهول معلن والقيمة الخام محفوظة — لا فقد صامت
    assert ev.collected_at is None
    assert ev.metadata.get("collected_at_raw") == 123, ev.metadata
    back = KnowledgeObject.from_canonical(canonical).evidence[0]
    assert back.get("collected_at") is None
    assert back["metadata"]["collected_at_raw"] == 123


def _rich_canonical_divergent_summary():
    """كائن معرفي بملخص مستقل عن المحتوى الخام — يكشف استبدال raw بالملخص."""
    from datetime import datetime
    runtime = KernelKnowledgeRuntime()
    k = runtime.create_knowledge(
        title="Divergent", knowledge_type=KnowledgeType.POLICY,
        content={"raw": "النص الأصلي الكامل", "structured": {"days": 90}},
        source="docs/policy.md",
        evidence=[Evidence(id="ev-d", content="clause", source="docs/policy.md",
                           collected_at=datetime(2024, 5, 4, 9, 15))],
        confidence=0.95, lineage=[], version="5.1.0",
    )
    k.summary = "ملخص مستقل"
    return k


def test_civilization_roundtrip_no_modification_preserves_verbatim():
    """مجرد إعادة التحويل ليس تعديلاً: ملخص مستقل عن raw يعودان معاً كما هما —
    لا يستبدل raw بالملخص، ولا يضاف مفتاح raw لم يكن موجوداً."""
    k = _rich_canonical_divergent_summary()
    ko = KnowledgeObject.from_canonical(k)
    back = ko.to_canonical()
    # R-W1-001: الملخص المستقل والمحتوى الخام كلاهما يعود كما هو — بلا استبدال
    assert back.summary == "ملخص مستقل", back.summary
    assert back.content == {"raw": "النص الأصلي الكامل", "structured": {"days": 90}}, back.content
    # ومحتوى منظم بلا مفتاح raw أصلاً: يعود كما هو — لا يضاف raw مصطنع
    k2 = _rich_canonical_divergent_summary()
    k2.content = {"structured": {"days": 90}}
    ko2 = KnowledgeObject.from_canonical(k2)
    back2 = ko2.to_canonical()
    assert back2.content == {"structured": {"days": 90}}, back2.content
    assert back2.summary == "ملخص مستقل"


def test_fabric_roundtrip_no_modification_preserves_verbatim():
    """fabric: مجرد إعادة التحويل ليس تعديلاً — والتعديل الحي ينعكس في raw."""
    from agos.fabric.knowledge import KnowledgeObject as FabricObject
    k = _rich_canonical_divergent_summary()
    fo = FabricObject.from_canonical(k)
    back = fo.to_canonical()
    # R-W1-001: الملخص المستقل والمحتوى الخام كلاهما يعود كما هو
    assert back.summary == "ملخص مستقل", back.summary
    assert back.content == {"raw": "النص الأصلي الكامل", "structured": {"days": 90}}, back.content
    # والتعديل الحي للحقل العلبي ينعكس في raw — لا ظلاً قديماً
    fo.content = "محتوى محدث حياً"
    back_updated = fo.to_canonical()
    assert back_updated.content["raw"] == "محتوى محدث حياً", back_updated.content
    assert back_updated.content["structured"] == {"days": 90}
    assert back_updated.summary == "محتوى محدث حياً"


def _canonical_with_content(summary, content):
    runtime = KernelKnowledgeRuntime()
    k = runtime.create_knowledge(
        title="Edge", knowledge_type=KnowledgeType.POLICY,
        content=content, source="s.py",
        evidence=[Evidence(id="e", content="c", source="s.py")],
        confidence=0.9, lineage=[], version="1.0.0",
    )
    k.summary = summary
    return k


def test_empty_content_dict_is_not_absence():
    """القاموس الفارغ ليس غياباً: content={} يُستعاد كما هو عند عدم التعديل —
    لا يُستبدل بـ {"raw": ...} — عبر الأسرتين."""
    from agos.fabric.knowledge import KnowledgeObject as FabricObject
    cases = [
        ("ملخص مستقل", {"structured": {"days": 90}}),   # بلا raw مع ملخص مستقل
        ("", {}),                                        # قاموس فارغ وملخص فارغ
        ("ملخص غير فارغ", {}),                           # قاموس فارغ وملخص غير فارغ
    ]
    for family_name, conv in (("civilization", lambda k: (KnowledgeObject.from_canonical(k), lambda ko: ko.to_canonical())),
                              ("fabric", lambda k: (FabricObject.from_canonical(k), lambda fo: fo.to_canonical()))):
        for summary, content in cases:
            original = _canonical_with_content(summary, content)
            via, back_call = conv(original)
            back = back_call(via)   # بلا أي تعديل للكائن الوسيط
            # R-W1-001: الاستعادة الحرفية — القاموس الفارغ ليس غياباً
            assert back.summary == original.summary, (family_name, summary, back.summary)
            assert back.content == original.content, (family_name, summary, back.content)
