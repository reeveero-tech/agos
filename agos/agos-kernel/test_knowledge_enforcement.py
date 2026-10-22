#!/usr/bin/env python3
"""اختبارات فرض متطلبات كائن المعرفة — R-W2-014.

تثبت أن الفحص الآلي للمادة 13 يطبق على كل كائن معرفة — لا مساراً موازياً
ضعيفاً يستطيع إظهار الناقص مكتملًا:
- التحقق النووي (validate_knowledge): VERIFIED لا تُمنح إلا لمكتمل دستورياً.
- بوابة الجودة (quality_gates): تتحقق من المتطلبات الستة على كل كائن يمر بها.
"""
# R-F-002 portable paths (see tools/migrate/portable_paths.py)
import os as _agos_os
from pathlib import Path as _AgosPath
_AGOS_ROOT = _AgosPath(_agos_os.environ.get('AGOS_ROOT') or _AgosPath(__file__).resolve().parents[1])
_AGOS_KERNEL = _AGOS_ROOT / 'agos-kernel'
import sys

sys.path.insert(0, str(_AGOS_KERNEL))
import agos_kernel  # R-F-005: مساحة الاسم الموحدة (ADR-0001)

from knowledge.runtime import KnowledgeRuntime
from knowledge.models import Knowledge, KnowledgeType, KnowledgeMetadata, Evidence, KnowledgeStatus
from knowledge.article13 import validate_article_13, ARTICLE_13_REQUIREMENTS


def _complete_knowledge(runtime: KnowledgeRuntime) -> Knowledge:
    return runtime.create_knowledge(
        title="Complete object",
        knowledge_type=KnowledgeType.FACT,
        source="src.py",
        evidence=[Evidence(id="e1", content="proof", source="src.py")],
        confidence=0.9,
        lineage=[],
        version="1.0.0",
    )


def test_validate_knowledge_requires_article13():
    """التحقق النووي: VERIFIED لا تُمنح إلا لكائن مكتمل دستورياً —
    والناقص يوثق نقصه باسمه في سجل التحقق."""
    runtime = KnowledgeRuntime()
    k = _complete_knowledge(runtime)
    # R-W1-001: المكتمل يتحقق ويُعلَّم VERIFIED
    assert runtime.validate_knowledge(k.id, "auditor") is True
    assert k.status.value == "verified"
    # الناقص (دليل بلا مصدر/ثقة/إصدار/نسب): لا VERIFIED والنقص باسمه
    broken = runtime.create_knowledge(
        title="Broken", knowledge_type=KnowledgeType.FACT,
        source="", evidence=[Evidence(id="e2", content="x", source="")],
        confidence=None, lineage=None, version="",
    )
    result = runtime.validate_knowledge(broken.id, "auditor")
    assert result is False, "الناقص دستورياً لا يُعلَّم VERIFIED"
    assert broken.status.value != "verified"
    # R-W1-001: النقص موثق باسمه في سجل التحقق نفسه — لا يختفى
    last = broken.validations[-1]
    gaps = {v for v in last.warnings if "Article 13" in v}
    assert gaps, last.warnings
    assert any(req in w for req in ("Source", "Confidence", "Version", "Lineage") for w in last.warnings)


def test_validate_knowledge_each_requirement_blocks_verified():
    """كل متطلب من الستة: انتهاكه وحده يمنع VERIFIED — لا يكفي وجود دليل."""
    runtime = KnowledgeRuntime()
    cases = {
        "Source": dict(source=""),
        "Evidence": dict(evidence=[]),
        "Confidence": dict(confidence=None),
        "Version": dict(version=""),
        "Lineage": dict(lineage=None),
    }
    for requirement, mutation in cases.items():
        base = dict(
            title=f"case-{requirement}", knowledge_type=KnowledgeType.FACT,
            source="src.py",
            evidence=[Evidence(id="e", content="c", source="src.py")],
            confidence=0.9, lineage=[], version="1.0.0",
        )
        k = runtime.create_knowledge(**{**base, **mutation})
        # R-W1-001: انتهاك المتطلب الواحد يمنع التحقق الدستوري
        assert runtime.validate_knowledge(k.id, "auditor") is False, requirement
        assert k.status.value != "verified", requirement


def test_validate_knowledge_semantics_preserved():
    """دلالات ADR-0002 باقية: 0.0 مقبولة، [] جذر معلن — والكائن يتحقق."""
    runtime = KnowledgeRuntime()
    k = runtime.create_knowledge(
        title="Zero confidence", knowledge_type=KnowledgeType.FACT, source="s.py",
        evidence=[Evidence(id="e", content="c", source="s.py")],
        confidence=0.0, lineage=[], version="1.0.0",
    )
    assert runtime.validate_knowledge(k.id, "auditor") is True
    assert k.status.value == "verified"


def test_validate_knowledge_invalid_values_reported_not_raised():
    """القيم غير الصالحة ترفض بأسمائها — لا نجاحاً زائفاً ولا استثناءً غير مقصود."""
    runtime = KnowledgeRuntime()
    k = runtime.create_knowledge(
        title="Bad types", knowledge_type=KnowledgeType.FACT, source="s.py",
        evidence=[Evidence(id="e", content="c", source="s.py")],
        confidence=1.5,   # خارج النطاق
        lineage="parent-1",   # ليس قائمة
        version="1.0.0",
    )
    # R-W1-001: الرفض بقيمة مرجعة وخرق مسمى — لا انهياراً
    assert runtime.validate_knowledge(k.id, "auditor") is False
    reqs = {v["requirement"] for v in validate_article_13(k)}
    assert {"Confidence", "Lineage"} <= reqs, reqs


def test_quality_gate_checks_six_requirements():
    """بوابة الجودة: تتحقق من المتطلبات الستة على كل كائن يمر بها —
    عبر المدقق المشترك نفسه، لا نسخة ضعيفة موازية."""
    import asyncio
    from quality_gates.pipeline import QualityGatesPipeline

    async def run_gate(knowledge_list):
        pipeline = QualityGatesPipeline()
        return await pipeline.validate_knowledge(knowledge_list)

    # كائن مكتمل يمر
    complete = {
        "name": "complete", "content": "c",
        "source": "s.py", "evidence": [{"source": "s.py", "content": "proof"}],
        "confidence": 0.9, "version": "1.0.0", "lineage": [],
        "created_at": "2026-10-22T10:00:00",
    }
    result = asyncio.run(run_gate([complete]))
    assert result.status.value == "passed", result.message

    # انتهاك كل متطلب وحده يمنع المرور — باسم المتطلب
    mutations = {
        "Source": {"source": ""},
        "Evidence": {"evidence": []},
        "Confidence": {"confidence": None},
        "Version": {"version": ""},
        "Lineage": {"lineage": None},
        "Timestamp": {"created_at": None},
    }
    for requirement, mutation in mutations.items():
        ko = {**complete, **mutation}
        result = asyncio.run(run_gate([ko]))
        # R-W1-001: البوابة تحجب الناقص باسم متطلبه — لا «معرفة صالحة» زائفة
        assert result.status.value == "blocked", (requirement, result.message)
        assert requirement in result.message, (requirement, result.message)


def test_quality_gate_evidence_semantics():
    """بوابة الجودة: الدليل الخاوٍ المصدر يرفض كما في المدقق المشترك."""
    import asyncio
    from quality_gates.pipeline import QualityGatesPipeline

    async def run_gate(knowledge_list):
        pipeline = QualityGatesPipeline()
        return await pipeline.validate_knowledge(knowledge_list)

    ko = {
        "name": "bad-evidence", "content": "c", "source": "s.py",
        "evidence": [{"source": "", "content": "proof"}],
        "confidence": 0.9, "version": "1.0.0", "lineage": [],
        "created_at": "2026-10-22T10:00:00",
    }
    result = asyncio.run(run_gate([ko]))
    assert result.status.value == "blocked"
    assert "Evidence" in result.message, result.message


def test_quality_gate_uses_shared_checker():
    """البوابة تعيد استخدام المدقق المشترك: انتهاكاتها أسماؤها مطابقة
    لمتطلبات المادة 13 لا مفردات خاصة بها."""
    import asyncio
    from quality_gates.pipeline import QualityGatesPipeline

    async def run_gate(knowledge_list):
        pipeline = QualityGatesPipeline()
        return await pipeline.validate_knowledge(knowledge_list)

    ko = {"name": "empty", "content": "c"}   # كائن بلا شيء
    result = asyncio.run(run_gate([ko]))
    # R-W1-001: أسماء المتطلبات الدستورية نفسها في رسالة الحجب
    for req in ARTICLE_13_REQUIREMENTS:
        assert req in result.message, (req, result.message)


def test_update_knowledge_demotes_stale_verified():
    """لا حالة VERIFIED قديمة: التحديث الذي ينقص الكائن يخفض الحالة فوراً —
    والانتقال مكتمل → ناقص → إصلاح → إعادة تحقق ينعكس على الحالة."""
    runtime = KnowledgeRuntime()
    k = _complete_knowledge(runtime)
    assert runtime.validate_knowledge(k.id, "auditor") is True
    assert k.status.value == "verified"
    # R-W1-001: التحديث المنقّص يخفض VERIFIED فوراً إلى ما يعكس نتيجة المدقق
    runtime.update_knowledge(k.id, source="")
    assert k.status.value != "verified", k.status.value
    assert k.status.value == "invalid", k.status.value   # متسق مع التحقق المباشر
    # الإصلاح وإعادة التحقق تعيدان VERIFIED
    runtime.update_knowledge(k.id, source="src.py")
    assert runtime.validate_knowledge(k.id, "auditor") is True
    assert k.status.value == "verified"


def test_direct_validate_consistent_with_shared_check():
    """التحقق المباشر (Knowledge.validate) متسق مع الفحص المشترك: الناقص
    ولوت كان له دليل لا ينجح — القيمة المرجعة وسجل التحقق والحالة كلها متفقة."""
    runtime = KnowledgeRuntime()
    k = _complete_knowledge(runtime)
    assert k.validate("direct") is True
    assert k.validations[-1].is_valid is True
    # ناقص لكن له دليل: التحقق المباشر يفشل والسجل والحالة متسقة
    k.source = ""
    k.confidence = None
    assert k.validate("direct") is False
    last = k.validations[-1]
    assert last.is_valid is False, "سجل التحقق يوثق الفشل لا النجاح"
    assert k.status.value == "invalid", k.status.value
    gaps = {w for w in last.warnings if "Article 13" in w}
    assert gaps, last.warnings
    # والواجهة الخارجية متسقة معه
    runtime.knowledge_store[k.id] = k
    assert runtime.validate_knowledge(k.id, "via-runtime") is False


def test_kernel_timestamp_requirement_blocks_verified():
    """المتطلب السادس (Timestamp): انتهاكه وحده يمنع VERIFIED عبر الواجهة النووية."""
    runtime = KnowledgeRuntime()
    k = _complete_knowledge(runtime)
    runtime.update_knowledge(k.id, created_at=None)
    # R-W1-001: فقد الطابع الزمني يمنع التحقق الدستوري
    assert runtime.validate_knowledge(k.id, "auditor") is False
    assert k.status.value != "verified"


def test_quality_gate_bad_types_blocked_not_crashed():
    """القيم الفاسدة النوع تُحجب البوابة بخرق مسمى — لا استثناء ولا اجتيازاً."""
    import asyncio
    from quality_gates.pipeline import QualityGatesPipeline

    async def run_gate(knowledge_list):
        pipeline = QualityGatesPipeline()
        return await pipeline.validate_knowledge(knowledge_list)

    base = {
        "name": "bad", "content": "c", "source": "s.py",
        "confidence": 0.9, "version": "1.0.0", "lineage": [],
        "created_at": "2026-10-22T10:00:00",
    }
    # ثقة سلسلة نصية: مقارنة عددية كانت ستنهار — الآن خرق مسمى
    result = asyncio.run(run_gate([{**base, "confidence": "غير رقم"}]))
    assert result.status.value == "blocked", result.message
    assert "Confidence" in result.message, result.message
    # دليل رقم: تعداد رقم كان سينهار — الآن خرق مسمى
    result = asyncio.run(run_gate([{**base, "evidence": 123}]))
    assert result.status.value == "blocked", result.message
    assert "Evidence" in result.message, result.message


def test_malformed_input_cannot_appear_valid():
    """القيم الفاسدة لا تصير نصاً يبدو صالحاً: دليل مصدره None لا يصير "None"،
    ومصدر رقمي لا يصير "123" — كلها تُحجب باسم المتطلب لا تجتاز الفحص."""
    import asyncio
    from quality_gates.pipeline import QualityGatesPipeline

    async def run_gate(knowledge_list):
        pipeline = QualityGatesPipeline()
        return await pipeline.validate_knowledge(knowledge_list)

    base = {
        "name": "malformed", "content": "c", "source": "s.py",
        "evidence": [{"source": "s.py", "content": "proof"}],
        "confidence": 0.9, "version": "1.0.0", "lineage": [],
        "created_at": "2026-10-22T10:00:00",
    }
    # دليل مصدره None: لا يتحول إلى النص "None" فيجتاز — بل خرق Evidence
    result = asyncio.run(run_gate([{**base, "evidence": [{"source": None, "content": "proof"}]}]))
    assert result.status.value == "blocked", result.message
    assert "Evidence" in result.message, result.message
    # مصدر أولي رقمي: لا يتحول إلى "123" — بل خرق Source
    result = asyncio.run(run_gate([{**base, "source": 123}]))
    assert result.status.value == "blocked", result.message
    assert "Source" in result.message, result.message


def test_direct_validate_malformed_evidence_no_crash():
    """دليل غير قائمة (رقم): التحقق المباشر يعيد فشلاً وخرقاً مسمى — لا TypeError."""
    runtime = KnowledgeRuntime()
    k = _complete_knowledge(runtime)
    k.evidence = 123
    # R-W1-001: لا انهياراً — فشل موثق بخرق مسمى من الفحص المشترك
    assert k.validate("direct") is False
    last = k.validations[-1]
    assert last.is_valid is False
    assert any("Evidence" in w for w in last.warnings), last.warnings


def test_non_string_version_and_evidence_source_reported():
    """الإصدار غير النصي ومصدر الدليل غير النصي: خرق مسمى — لا انهياراً في strip."""
    runtime = KnowledgeRuntime()
    k = _complete_knowledge(runtime)
    k.metadata.version = 123          # إصدار رقمي
    k.evidence[0].source = None       # مصدر دليل None
    violations = validate_article_13(k)
    reqs = {v["requirement"] for v in violations}
    # R-W1-001: كلاهما خرق مسمى لا استثناء
    assert {"Version", "Evidence"} <= reqs, reqs
    assert k.validate("direct") is False


def test_update_knowledge_invalidates_valid_too():
    """إبطال كل حالات نجاح التحقق: VALID (وليس VERIFIED فقط) تُخفض عند فشل
    المدقق — ولا تعود حالة النجاح إلا بإعادة تحقق ناجحة (لا استعادة تلقائية)."""
    runtime = KnowledgeRuntime()
    k = _complete_knowledge(runtime)
    # تحقق مباشر ناجح → VALID (ليس VERIFIED — الترقية عبر الواجهة النووية فقط)
    assert k.validate("direct") is True
    assert k.status.value == "valid"
    # R-W1-001: التحديث المنقّص يبطل VALID أيضاً — متسقة مع المدقق
    runtime.update_knowledge(k.id, source="")
    assert k.status.value == "invalid", k.status.value
    # إصلاح البيانات لا يستعيد حالة النجاح تلقائياً
    runtime.update_knowledge(k.id, source="src.py")
    assert k.status.value == "invalid", "لا استعادة تلقائية — إعادة التحقق لازمة"
    # إعادة التحقق الناجحة تعيد النجاح (VALID من التحقق المباشر)
    assert k.validate("direct") is True
    assert k.status.value == "valid"


def test_quality_gate_numeric_version_blocked():
    """الإصدار الرقمي لا يتحول إلى "123" فيجتاز — بل خرق Version مسمى."""
    import asyncio
    from quality_gates.pipeline import QualityGatesPipeline

    async def run_gate(knowledge_list):
        pipeline = QualityGatesPipeline()
        return await pipeline.validate_knowledge(knowledge_list)

    base = {
        "name": "num-version", "content": "c", "source": "s.py",
        "evidence": [{"source": "s.py", "content": "proof"}],
        "confidence": 0.9, "version": "1.0.0", "lineage": [],
        "created_at": "2026-10-22T10:00:00",
    }
    result = asyncio.run(run_gate([{**base, "version": 123}]))
    # R-W1-001: رقم لا يصير نصاً صالحاً — خرق Version يحجب
    assert result.status.value == "blocked", result.message
    assert "Version" in result.message, result.message


def test_add_evidence_invalidates_stale_success():
    """إضافة دليل بلا مصدر تجعل الكائن ناقصاً دستورياً — وتبطل كل حالة نجاح
    قديمة (VALID وVERIFIED) عبر الواجهة الفعلية، ولا تعود إلا بإعادة تحقق."""
    runtime = KnowledgeRuntime()
    k = _complete_knowledge(runtime)
    assert runtime.validate_knowledge(k.id, "auditor") is True
    assert k.status.value == "verified"
    # R-W1-001: دليل بلا مصدر ينقص الكائن — الحالة القديمة تُبطل فوراً
    runtime.add_evidence(k.id, Evidence(id="bad", content="proof", source=""))
    fetched = runtime.get_knowledge(k.id)
    assert fetched.status == KnowledgeStatus.INVALID, fetched.status.value
    # والتحقق المباشر بعد نجاح: إضافة دليل ناقص تبطل VALID أيضاً
    k2 = _complete_knowledge(runtime)
    assert k2.validate("direct") is True
    assert k2.status.value == "valid"
    runtime.knowledge_store[k2.id] = k2
    runtime.add_evidence(k2.id, Evidence(id="bad2", content="proof", source=""))
    assert k2.status.value == "invalid", k2.status.value
