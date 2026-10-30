"""المادة 12 — قابلية تكرار قرار المسار الهندسي عبر الإقلاعات (الشريحة 37).

ثالث نقطة قرار إنتاجية **خارج المسارين المفحوصين** (مسار الترخيص وخط
المهمة) بعد مفسر النية (الشريحة 35) والمقارنة البحثية (الشريحة 36):
**قرار المسار الهندسي (Engineer)** — الطلب الطبيعي ← تفسير النية ←
مرشحو الإيفاء من جدول الإيفاء المُثبت بالمخرجات ← مقارنة دليل القرار
القائم بسياسته المعلنة (تعادل إيفاء حقيقي يُكسر بقاعدة **ترتيب التسجيل
المستقر** — لا أفضلية درجات) ← المختار ومواصفة المهمة. المسار الإنتاجي
مثبت من مستدعيه الفعلي (``_run_engineer`` في واجهة الذكاء يستدعي
``_interpret_engineer_request`` ثم ``_compare_alternatives`` عبر دليل
القرار القائم) — والاختبار هنا يقلع واجهة الذكاء الحية ويقرر عبر
المدخل الكامل ``run`` (خطة هندسية معروضة للاعتماد) إضافة إلى نقطة
القرار نفسها.

منهج الأحمر أولاً: المادة 12 توجب قرارات **قابلة للتكرار**، وحد
الشريحتين 35 و36 المعلن هو أن التكرار مثبت للحالات المختبرة عبر
إقلاعات مستقلة. لو تسرّب ترتيب مجموعة أو تهشئة أو لاتحتمية في التسجيل
إلى مخرج القرار (المختار أو ترتيب البدائل أو الدرجات أو كسر التعادل
أو مكونات الخطة المعروضة للاعتماد) لاختلفت الأحكام بين العمليات وفشل
الاختبار بالفجوة الحقيقية؛ وإن اتفقت الأحكام فهو دليل رصدي على التكرار
عند هذا الحد — لا اكتمالاً للحتمية العامة ولا إثباتاً لكل المدخلات.
الحقول التشغيلية المسماة (decision_id/timestamp) مستبعدة من المقارنة
كما في الشريحة 28 — هيية السجل لا محتواه القراري.
"""
import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
KERNEL = REPO / "agos" / "agos-kernel"

#: النصوص المختبرة — القرار المفرد (SecurityScan)، وتعادلان حقيقيان
#: يكسرهما ترتيب التسجيل (تحليل المستودع أولاً)، والنفي والاستفهام
#: (كل قرار هنا إما مواصفة مهمة أو خطأ مسمى — لا تنفيذ)
TEXTS = [
    "حلل أمن المستودع /tmp/x",
    "حلل اعتماديات وإطارات هذا المستودع /tmp/x",
    "بصمة DNA للمستودع /tmp/x",
    "لا تحلل شيئاً",
    "ما هي أطر هذا المستودع؟",
]


def _boot_and_decide() -> str:
    """إقلاع واجهة الذكاء الحية (نواة كاملة) ثم قرار المسار الهندسي عبر
    مسار الإنتاج نفسه — في عملية مستقلة (بذرة تهشئة عشوائية جديدة)."""
    code = textwrap.dedent(f"""
        import json
        from intelligence.interface import (
            IntelligenceInterface, IntelligenceRequest, IntelligenceMode)

        def strip(o):
            # الحقول التشغيلية المسماة (هوية السجل وطابعه الزمني) لا تدخل
            # المقارنة — محتوى القرار فقط (نمط الشريحة 28)
            if isinstance(o, dict):
                return {{k: strip(v) for k, v in o.items()
                         if k not in ("decision_id", "timestamp")}}
            if isinstance(o, list):
                return [strip(x) for x in o]
            return o

        iface = IntelligenceInterface()
        decisions = []
        for text in {TEXTS!r}:
            spec, ctx, error = iface._interpret_engineer_request(text)
            row = {{"text": text, "error": error}}
            if ctx is not None:
                comparison = ctx["comparison"]
                projected = comparison.to_dict()
                row["selected"] = ctx["selected"]
                row["alternatives"] = list(ctx["alternatives"])
                row["required_skills"] = list(ctx["required_skills"])
                row["spec"] = spec
                row["closed_gaps"] = list(ctx["closed_gaps"])
                row["comparison"] = strip(projected)
            decisions.append(row)

        # القرار عبر المدخل الكامل: خطة هندسية معروضة للاعتماد — نفس
        # المسار الذي يقرر فيه الطلب الطبيعي حقيقةً (run → _run_engineer)
        full = iface.run(IntelligenceRequest(
            mode=IntelligenceMode.ENGINEER,
            natural_text="حلل اعتماديات وإطارات هذا المستودع /tmp/x"))
        full_row = {{"status": full.status.value if full.status else None,
                    "gaps": list(full.gaps or []),
                    "engineering_plan": strip(full.engineering_plan)}}

        print(json.dumps({{"decisions": decisions, "full": full_row}},
                         ensure_ascii=False))
    """)
    r = subprocess.run([sys.executable, "-c", code], cwd=KERNEL,
                       capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stderr[-3000:]
    return r.stdout.strip().splitlines()[-1]


@pytest.mark.parametrize("boot_index", range(3))
def test_article_12_engineer_decision_declared_semantics_per_independent_boot(
        boot_index):
    """كل إقلاع مستقل ينتج الدلالات المعلنة نفسها — القرار المفرد والتعادل
    المكسور بترتيب التسجيل والنفي والاستفهام أحكام مسماة، والمدخل
    الكامل يعرض خطة معتمدة بمحتوى قرار كامل (الشريحة 28: التكرار مثبت
    للحالات المختبرة لا حتمية عامة)."""
    out = json.loads(_boot_and_decide())

    by_text = {d["text"]: d for d in out["decisions"]}

    # القرار المفرد: SecurityScan بمعامل المصدر المستخرج نصياً
    security = by_text["حلل أمن المستودع /tmp/x"]
    assert security["error"] is None
    assert security["selected"] == "SecurityScan"
    assert security["alternatives"] == ["SecurityScan"]
    assert security["spec"]["capability"] == "SecurityScan"
    assert security["spec"]["parameters"] == {"url": "/tmp/x"}
    assert security["comparison"]["status"] == "selected"

    # التعادل الأول: تحليل المستودع ضد خط المعالجة — درجات متساوية
    # (تعادل إيفاء حقيقي) والكسر بقاعدة ترتيب التسجيل المعلنة
    tie = by_text["حلل اعتماديات وإطارات هذا المستودع /tmp/x"]
    assert tie["error"] is None
    assert tie["alternatives"] == [
        "RepositoryAnalysis", "RepositoryProcessingPipeline"]
    assert tie["selected"] == "RepositoryAnalysis"
    assert tie["comparison"]["tie_break"] == "stable-registration-order"
    scores = {c["name"]: c["score"]["total"]
              for c in tie["comparison"]["candidates"]}
    assert scores == {"RepositoryAnalysis": 1.0,
                      "RepositoryProcessingPipeline": 1.0}

    # التعادل الثاني: تحليل المستودع ضد توليد البصمة — القاعدة نفسها
    dna = by_text["بصمة DNA للمستودع /tmp/x"]
    assert dna["error"] is None
    assert dna["alternatives"] == [
        "RepositoryAnalysis", "RepositoryDNAGeneration"]
    assert dna["selected"] == "RepositoryAnalysis"
    assert dna["comparison"]["tie_break"] == "stable-registration-order"

    # النفي والاستفهام: أحكام مسماة لا تنفيذ صامت
    negation = by_text["لا تحلل شيئاً"]
    assert negation["error"] is not None
    assert "نفي فعلي" in negation["error"]
    interrogative = by_text["ما هي أطر هذا المستودع؟"]
    assert interrogative["error"] is not None
    assert "طلب استفهامي" in interrogative["error"]

    # المدخل الكامل: خطة معروضة للاعتماد بمحتوى قرار حتمي المبنى
    full = out["full"]
    assert full["status"] == "awaiting_approval"
    selection = full["engineering_plan"]["alternatives"]["selection"]
    assert selection["selected"] == "RepositoryAnalysis"
    assert selection["tie_break"] == "stable-registration-order"
    assert selection["policy_id"] == "design-alternatives-fulfillment-tie"
    # فجوة التكلفة المقيسة تبقى مسماة (لا قياس سابق لهذا المدخل)
    assert full["gaps"] == ["engineering-plan-cost-estimate"]


def test_article_12_engineer_decisions_identical_across_independent_boots():
    """الأحمر الكاشر لعدم الحتمية عبر الإقلاعات: ثلاث عمليات مستقلة
    (بذور تهشئة مختلفة وإقلاعات منفصلة، كل منها تقلع واجهة الذكاء
    وتقرر عبر مسار الإنتاج) يجب أن تتفق في كل شيء — المختار وترتيب
    البدائل والدرجات وكسر التعادل ومواصفة المهمة ومكونات الخطة
    المعروضة للاعتماد — أي اختلاف هو مخالفة قابلة للتكرار مثبتة."""
    outs = [json.loads(_boot_and_decide()) for _ in range(3)]
    first = outs[0]
    for i, other in enumerate(outs[1:], start=2):
        assert other == first, (
            f"قرار المسار الهندسي اختلف بين الإقلاع 1 والإقلاع {i} — "
            "عدم حتمية مثبت")
