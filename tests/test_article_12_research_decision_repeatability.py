"""المادة 12 — قابلية تكرار قرار المقارنة البحثية عبر الإقلاعات (الشريحة 36).

ثاني نقطة قرار إنتاجية **خارج المسارين المفحوصين** (الترخيص وخط المهمة)
بعد مفسر النية (الشريحة 35): **المقارنة البحثية** — سياسة ``compare_candidates``
المعلنة (ADR-0009: مواءمة حزمة المستودع؛ الدرجة = حجم التقاطع؛ التعادل
يُكسر بترتيب الإدراج بين ذوي مواءمة مثبتة فقط؛ والمرشح بلا تقنيات معلنة
يُستبعد بمسوّغ مسمى). المسار الإنتاجي مثبت من مستدعيه الفعلي
(``_run_research`` في واجهة الذكاء: تفسير سؤال ← تحليل حقيقي للمستودع
الدليلي ← المقارنة في دليل القرار نفسه).

منهج الأحمر أولاً: المادة 12 توجب قرارات **قابلة للتكرار**، وحد الشريحة 35
المعلن هو أن التكرار مثبت للحالات المختبرة عبر إقلاعات مستقلة لمفسر
النية وحده. الاختبار هنا يقلع واجهة الذكاء الحية (إقلاع نواة كامل في كل
عملية مستقلة — بذور تهشئة مختلفة) ويكرر القرار البحثي نفسه عبر
الإقلاعات. لو تسرّب ترتيب مجموعة أو تهشئة أو لاتحتمية في التحليل الحي
إلى مخرج القرار (الدرجات أو الترتيب أو الفائز أو التقنيات المتقاطعة)
لاختلفت الأحكام بين العمليات وفشل الاختبار بالفجوة الحقيقية؛ وإن اتفقت
الأحكام فهو دليل رصدي على التكرار عند هذا الحد — لا اكتمالاً للحتمية
العامة ولا إثباتاً لكل المدخلات.
"""
import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
KERNEL = REPO / "agos" / "agos-kernel"


@pytest.fixture(scope="module")
def git_repo(tmp_path_factory) -> Path:
    repo = tmp_path_factory.mktemp("owner") / "sample"
    repo.mkdir()
    (repo / "requirements.txt").write_text("flask\n")
    (repo / "app.py").write_text("import flask\n")
    env = ["-c", "user.email=t@t", "-c", "user.name=t"]
    for cmd in (["git", "init", "-q", "-b", "main"], ["git", "add", "-A"],
                ["git", *env, "commit", "-qm", "init"]):
        subprocess.run(cmd, cwd=repo, check=True, capture_output=True)
    return repo


def _research_decisions(git_repo: Path) -> str:
    """إقلاع واجهة الذكاء الحية (نواة كاملة) ثم القرار البحثي عبر مسار
    الإنتاج نفسه — في عملية مستقلة (بذرة تهشئة عشوائية جديدة)."""
    code = textwrap.dedent(f"""
        import json
        from intelligence.interface import (
            IntelligenceInterface, IntelligenceRequest, EngineeringCandidate,
            IntelligenceMode)

        def cmp_dict(c):
            return {{"id": c.candidate_id, "score": c.score,
                    "matched": list(c.matched_technologies),
                    "order": c.order,
                    "excluded": getattr(c, "exclusion_reason", None)}}

        iface = IntelligenceInterface()
        # القرار الأول: مواءمة مثبتة وغياب مواءمة واستبعاد مسمّى
        main_req = IntelligenceRequest(
            mode=IntelligenceMode.RESEARCH,
            question="ما أطر هذا المستودع؟",
            evidence_path={str(git_repo)!r},
            candidates=[
                EngineeringCandidate(id="a", name="مرشح أ",
                                     technologies=["flask", "python"]),
                EngineeringCandidate(id="b", name="مرشح ب",
                                     technologies=["django"]),
                EngineeringCandidate(id="c", name="مرشح ج",
                                     technologies=[]),
            ],
        )
        main = iface.run(main_req)
        # القرار الثاني: تعادل مواءمة مثبتة بين مرشحين — كسر التعادل
        # بترتيب الإدراج (سياسة معلنة) يُختبر عبر الإقلاعات
        tie_req = IntelligenceRequest(
            mode=IntelligenceMode.RESEARCH,
            question="ما أطر هذا المستودع؟",
            evidence_path={str(git_repo)!r},
            candidates=[
                EngineeringCandidate(id="x", name="مرشح س",
                                     technologies=["flask"]),
                EngineeringCandidate(id="y", name="مرشح ص",
                                     technologies=["FLASK"]),
            ],
        )
        tie = iface.run(tie_req)

        out = {{"main": {{"status": main.status.value if main.status else None,
                         "error": main.error}},
                "tie": {{"status": tie.status.value if tie.status else None,
                        "error": tie.error}}}}
        for key, res in (("main", main), ("tie", tie)):
            if res.comparison:
                out[key]["best"] = cmp_dict(res.comparison.best)
                out[key]["ranked"] = [cmp_dict(c)
                                      for c in res.comparison.ranked]
            if res.evidence_snapshot:
                out[key]["stack"] = list(
                    res.evidence_snapshot.get("detected_stack", []))
        print(json.dumps(out, ensure_ascii=False))
    """)
    r = subprocess.run([sys.executable, "-c", code], cwd=KERNEL,
                       capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stderr[-3000:]
    return r.stdout.strip().splitlines()[-1]


@pytest.mark.parametrize("boot_index", range(3))
def test_article_12_research_decision_declared_semantics_per_independent_boot(
        git_repo, boot_index):
    """كل إقلاع مستقل ينتج الدلالات المعلنة نفسها — الفائز المسند
    (تقاطع flask المكتشف فعلاً) والاستبعاد المسمى (بلا تقنيات معلنة)
    وكسر التعادل بترتيب الإدراج بين ذوي المواءمة المثبتة فقط."""
    out = json.loads(_research_decisions(git_repo))

    main = out["main"]
    assert main["status"] == "completed"
    # التحليل الحي كشف flask فعلاً — دليل القرار من الخط المعتمد
    assert main["stack"] == ["flask"]
    # الفائز مسند بتقاطع مثبت (لا توصية بلا مواءمة)
    assert main["best"]["id"] == "a"
    assert main["best"]["score"] == 1
    assert main["best"]["matched"] == ["flask"]
    # غير المكتشف ليس فشلاً بل قيمة أدنى؛ والاستبعاد مسمى
    by_id = {c["id"]: c for c in main["ranked"]}
    assert by_id["b"]["score"] == 0
    assert by_id["c"]["excluded"] == "no-declared-technologies"

    # كسر التعادل بترتيب الإدراج — التطبيع (FLASK=flask) لا يحسّن
    # الدرجة، والأول إدراجاً بين المتعادلين ذوي المواءمة يفوز
    tie = out["tie"]
    assert tie["status"] == "completed"
    assert tie["best"]["id"] == "x"
    assert tie["best"]["score"] == 1
    assert all(c["score"] == 1 for c in tie["ranked"])


def test_article_12_research_decisions_identical_across_independent_boots(
        git_repo):
    """الأحمر الكاشر لعدم الحتمية عبر الإقلاعات: ثلاث عمليات مستقلة
    (بذور تهشئة مختلفة وإقلاعات منفصلة، كل منها تحلل المستودع الحي
    وتقارن في دليل القرار نفسه) يجب أن تتفق في كل شيء — الدرجة والترتيب
    والفائز والتقنيات المتقاطعة والحزمة المكتشفة — أي اختلاف هو مخالفة
    قابلة للتكرار مثبتة."""
    outs = [json.loads(_research_decisions(git_repo)) for _ in range(3)]
    first = outs[0]
    for i, other in enumerate(outs[1:], start=2):
        assert other == first, (
            f"القرار البحثي اختلف بين الإقلاع 1 والإقلاع {i} — "
            "عدم حتمية مثبت")
