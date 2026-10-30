"""المادة 12 — قابلية تكرار قرارات مفسر النية عبر الإقلاعات (الشريحة 35).

نقطة قرار إنتاجية **خارج المسارين المفحوصين** (مسار الترخيص وخط المهمة):
مفسر النية المعلن (سجل العمل 0047) — قرار Instant: تفسير الطلب الطبيعي
وبناء مواصفة المهمة. المسار الإنتاجي مثبت من مستدعيه الفعلي
(``_run_instant`` في واجهة الذكاء): ``interpret`` ثم ``registered`` من
سجل القدرات الحي (``list_all``) ثم ``build_mission``.

منهج الأحمر أولاً: المادة 12 توجب قرارات **قابلة للتكرار**، وحد
الشريحة 28 المعلن هو أن التكرار مثبت للحالات المختبرة في السياق
المثبت لا حتمية عامة عبر كل الإقلاعات — فالاختبار هنا يقلع نواة
حقيقية في عمليات مستقلة (بذور تهشئة مختلفة لكل عملية) ويكرر القرار
نفسه عبر الإقلاعات. لو تسرّب ترتيب مجموعة أو تهشئة إلى مخرج القرار
لاختلفت الأحكام بين العمليات وفشل الاختبار بالفجوة الحقيقية؛ وإن
اتفقت الأحكام فهو دليل رصدي على التكرار عند هذا الحد — لا اكتمالاً
للحتمية العامة ولا إثباتاً لكل المدخلات.
"""
import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
KERNEL = REPO / "agos" / "agos-kernel"

#: النصوص المختبرة — تغطي المسار الناجح وتعادل المرشحين والاستفهام
#: والنفي الفعلي (كل قرار هنا إما مواصفة مهمة أو خطأ مسمى — لا تنفيذ)
TEXTS = [
    "حلل اعتماديات وإطارات هذا المستودع /tmp/x",
    "حلل أمن المستودع /tmp/x",
    "ما هي أطر هذا المستودع؟",
    "لا تحلل شيئاً",
    "بصمة DNA للمستودع /tmp/x",
]


def _boot_and_decide() -> str:
    """إقلاع نواة حقيقية ثم القرار عبر مسار الإنتاج نفسه — في عملية
    مستقلة (بذرة تهشئة عشوائية جديدة لكل عملية)."""
    code = textwrap.dedent(f"""
        import json
        import agos_runtime
        from intelligence import intent as intent_module

        k = agos_runtime.boot()
        # الاستخراج الإنتاجي نفسه من _run_instant (واجهة الذكاء):
        # الأنبوب ← المحلل ← سجل القدرات ← list_all
        pipeline = getattr(k.mission_engine.executor, "pipeline", None)
        resolver = getattr(pipeline, "capability_resolver", None)
        registered = [c.name for c in
                      resolver.capability_registry.list_all()]

        decisions = []
        for text in {TEXTS!r}:
            interpretation = intent_module.interpret(text)
            spec, error = intent_module.build_mission(
                interpretation, registered)
            decisions.append({{
                "text": text,
                "required_concepts": interpretation.required_concepts,
                "matched_terms": interpretation.matched_terms,
                "negated_concepts": interpretation.negated_concepts,
                "artifacts": interpretation.artifacts,
                "spec": spec,
                "error": error,
            }})
        print(json.dumps({{
            "registered": registered,
            "decisions": decisions,
        }}, ensure_ascii=False))
    """)
    r = subprocess.run([sys.executable, "-c", code], cwd=KERNEL,
                       capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stderr[-3000:]
    return r.stdout.strip().splitlines()[-1]


@pytest.mark.parametrize("boot_index", range(3))
def test_article_12_intent_decision_declared_semantics_per_independent_boot(
        boot_index):
    """كل إقلاع مستقل ينتج الدلالات المعلنة نفسها — القرار الناجح
    والتعادل والاستفهام والنفي أحكام مسماة لا اتفاق صامت (الشريحة 28:
    التكرار مثبت للحالات المختبرة لا حتمية عامة)."""
    out = json.loads(_boot_and_decide())

    # المسار الإنتاجي نفسه: سجل حقيقي غير فارغ بترتيب تسجيله الفعلي
    assert len(out["registered"]) > 0

    # تثبيت الدلالات المعتمدة — لا اتفاق صامت فقط: القرار الناجح
    # (SecurityScan للنص الأمني) والتعادل والاستفهام والنفي كلها
    # أحكام مسماة معلنة
    by_text = {d["text"]: d for d in out["decisions"]}
    security = by_text["حلل أمن المستودع /tmp/x"]
    assert security["spec"] is not None
    assert security["spec"]["capability"] == "SecurityScan"
    assert security["spec"]["parameters"] == {"url": "/tmp/x"}
    assert security["error"] is None

    tie_deps = by_text["حلل اعتماديات وإطارات هذا المستودع /tmp/x"]
    assert tie_deps["spec"] is None
    assert "تعادل مرشحين" in tie_deps["error"]
    assert "RepositoryAnalysis" in tie_deps["error"]
    assert "RepositoryProcessingPipeline" in tie_deps["error"]

    tie_dna = by_text["بصمة DNA للمستودع /tmp/x"]
    assert tie_dna["spec"] is None
    assert "تعادل مرشحين" in tie_dna["error"]
    assert "RepositoryDNAGeneration" in tie_dna["error"]

    interrogative = by_text["ما هي أطر هذا المستودع؟"]
    assert interrogative["spec"] is None
    assert "طلب استفهامي" in interrogative["error"]

    negation = by_text["لا تحلل شيئاً"]
    assert negation["spec"] is None
    assert "نفي فعلي" in negation["error"]


def test_article_12_intent_decisions_identical_across_independent_boots():
    """الأحمر الكاشر لعدم الحتمية عبر الإقلاعات: ثلاث عمليات مستقلة
    (بذور تهشئة مختلفة وإقلاعات منفصلة) يجب أن تتفق في كل شيء —
    الترتيب الفعلي للتسجيل ومخرجات القرار كاملة (المواصفة أو الخطأ
    المسمى) — أي اختلاف هو مخالفة قابلة للتكرار مثبتة."""
    outs = [json.loads(_boot_and_decide()) for _ in range(3)]
    first = outs[0]
    for i, other in enumerate(outs[1:], start=2):
        assert other == first, (
            f"القرار اختلف بين الإقلاع 1 والإقلاع {i} — عدم حتمية مثبت")
