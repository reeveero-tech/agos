"""أدلة تشغيلي — المادة 7 من خريطة أدلة ADR-0010: لا تنفيذ دائم (الشريحة 0097).

منهج المشروع: أحمر أولاً ثم أدنى إصلاح.

القاعدة الدستورية (المادة 7): قوائم التغييرات المسموحة (التجميد) لا تثبت
الاستبدال — الدليل المطلوب: استبدال تنفيذ عبر العقد المدعوم دون تعديل النواة.
العقد المدعوم المعلن: سجل المزودات العام (``k.provider_registry`` —
register/unregister) الذي يغذي محلّل المزوّد في خط أنابيب المهمة.

المخالفة المكتشفة: خط المهمة يختار المزوّد فعلاً عبر السجل (خطوة
resolve_provider بمسار قرار موثق) لكنه لا يمرر الكائن المختار إلى القدرة —
نتيجة الاختيار تُهدر، والقدرة تنشئ المزوّد المحلي مباشرة، فالاستبدال عبر
السجل لا يؤثر على التنفيذ.

الإصلاح الأدنى (قرار المراجعة — خيار تمرير صريح لكل استدعاء): عقد إضافي
اختياري ``execute_with_provider`` على قدرة تحليل المستودع يوصل الخطُّ الكائنَ
المختار نفسه إليه عبر المحرك المشترك، والقدرة تمرره إلى ``analyze_url``
بمعامل صريح فلا إنشاء محلي في هذا المسار — بلا حقن في معاملات المستخدم
وبلا حالة مخزنة، وعند رفض المزوّد المختار لا رجوع إلى الإنشاء المحلي.
"""
import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
KERNEL = REPO / "agos" / "agos-kernel"


@pytest.fixture
def local_git_repo(tmp_path) -> Path:
    repo = tmp_path / "sample"
    repo.mkdir()
    (repo / "requirements.txt").write_text("flask\n")
    (repo / "app.py").write_text("import flask\nprint('hi')\n")
    env = ["-c", "user.email=t@t", "-c", "user.name=t"]
    for cmd in (["git", "init", "-q", "-b", "main"], ["git", "add", "-A"],
                ["git", *env, "commit", "-qm", "init"]):
        subprocess.run(cmd, cwd=repo, check=True, capture_output=True)
    return repo


# الوسيط: بديل مسجل في السجل العام يحمل المهارتين ويسجل عبوره بعقدهما
# المعلنة، وينفذ فعلاً (يفوض للتنفيذ الحقيقي عبر الدالة الأصلية المحفوظة
# مباشرة — لا عبر attribute الصنف الملفوف — فلا يُحسب عبوراً للأصل).
MISSION_CODE = """
import json
import providers
from providers import CloneRepositoryInput, ReadRepositoryInput

# راصد الأصل: يلف execute على الصنف نفسه — يسجل العبور عبر الواجهة العامة
# للصنف فقط (استدعاءات مسار الإنتاج)، دون تغيير آلية الاختيار أو السلوك.
ORIGINAL_CALLS = []
_real_execute = providers.LocalRepositoryProvider.execute

def _recording_execute(self, skill_name, input_data):
    ORIGINAL_CALLS.append(skill_name)
    return _real_execute(self, skill_name, input_data)

providers.LocalRepositoryProvider.execute = _recording_execute

SUBSTITUTE_CALLS = []


class SubstituteRepositoryProvider:
    \"\"\"بديل باسم مميز — الاستبدال عبر السجل العام وحده.\"\"\"

    def __init__(self):
        self._inner = providers.LocalRepositoryProvider()
        # تفويض التنفيذ الحقيقي عبر الدالة الأصلية المحفوظة مباشرة —
        # عبور البديل لا يُحسب عبوراً للأصل (الفصل بالهوية لا بالاسم).
        self._inner_exec = _real_execute.__get__(self._inner)

    @property
    def name(self):
        return "SubstituteRepositoryProvider"

    def supports_skill(self, skill_name):
        return skill_name in ["CloneRepository", "ReadRepository"]

    def execute(self, skill_name, input_data):
        entry = {"skill": skill_name, "input_type": type(input_data).__name__}
        if skill_name == "CloneRepository":
            entry["input_ok"] = isinstance(input_data, CloneRepositoryInput)
        elif skill_name == "ReadRepository":
            entry["input_ok"] = isinstance(input_data, ReadRepositoryInput)
        SUBSTITUTE_CALLS.append(entry)
        if REFUSE_CLONE and skill_name == "CloneRepository":
            raise RuntimeError("رفض مقصود للاختبار — البديل هو المنفذ المختار")
        result = self._inner_exec(skill_name, input_data)
        entry["output_type"] = type(result).__name__
        return result


import agos_runtime
k = agos_runtime.boot()
reg = k.provider_registry

WARM_STATE = None
CACHE_FILLED = None
if WARM_FIRST:
    # تشغيل الأصل أولاً — اكتظاظ كاش التحليل فعلاً قبل الاستبدال
    warm_outcome = k.analyze({URL!r}, branch="main")
    WARM_STATE = warm_outcome.state.value
    _caps = [c for c in k.capability_registry.list_all()
             if type(c).__name__ == "RepositoryAnalysisCapability"]
    CACHE_FILLED = bool(_caps and _caps[0].__dict__.get("_dna_cache"))
    ORIGINAL_CALLS.clear()      # الرصد للمرحلة الثانية فقط (بعد الاستبدال)

assert reg.exists("LocalRepositoryProvider"), "الأصل غير مسجل في السجل العام"
if EQUAL_PROVIDER:
    # مزوّد «متساوٍ بالقيمة»: عقد السجل لا يشترط هوية تجزئة/مساواة —
    # بديل مختلف الكائن لكن __eq__/__hash__ يجعلانه مطابقاً للأصل في
    # مفاتيح القواميس (dataclass-like): متساوٍ **ومتطابق التجزئة** فعلاً
    # مع الأصل المسجل. هوية المنفّذ وحدها يجب أن تفصل بينهما.
    _orig = reg.get("LocalRepositoryProvider")
    SubstituteRepositoryProvider.__eq__ = (
        lambda self, other: isinstance(
            other, (SubstituteRepositoryProvider,
                    providers.LocalRepositoryProvider)))
    SubstituteRepositoryProvider.__hash__ = lambda self: hash(_orig)
reg.unregister("LocalRepositoryProvider")
reg.register(SubstituteRepositoryProvider())
substitute = reg.get("SubstituteRepositoryProvider")
assert substitute is not None, "البديل لم يثبت في السجل العام"

outcome = k.analyze({URL!r}, branch="main")
from contracts import RepositoryDNA
dna = getattr(outcome, "result", None)
selected = None
for r in (getattr(outcome, "decision_records", None) or []):
    if getattr(r, "kind", None) == "provider":
        selected = r.selected
print(json.dumps({
    "state": outcome.state.value,
    "error": getattr(outcome, "error", None),
    "warm_state": WARM_STATE,
    "cache_filled": CACHE_FILLED,
    "substitute_calls": SUBSTITUTE_CALLS,
    "original_calls": ORIGINAL_CALLS,
    "selected_provider": selected,
    "registry_names": [p.name for p in reg.list_all()],
    "dna_type_ok": isinstance(dna, RepositoryDNA),
    "dna_name": getattr(dna, "name", None) if dna is not None else None,
    "dna_languages": (getattr(dna, "languages", None) or [])[:5] if dna is not None else None,
}))
"""


def _run_mission(local_git_repo: Path, refuse_clone: bool = False,
                warm_first: bool = False, equal_value: bool = False) -> dict:
    """يستبدل المزوّد عبر السجل العام وحده ثم يشغل المهمة الحقيقية من
    المدخل العام — لا تعديل على النواة ولا على رمز الصنف (الراصد يسجل
    فقط). ``warm_first``: تشغيل الأصل أولاً حتى اكتظاظ الكاش فعلاً قبل
    الاستبدال (المستودع والمراجعة نفسهما في المرحلتين)."""
    code = ("REFUSE_CLONE = True\n" if refuse_clone else "REFUSE_CLONE = False\n") \
        + ("WARM_FIRST = True\n" if warm_first else "WARM_FIRST = False\n") \
        + ("EQUAL_PROVIDER = True\n" if equal_value else "EQUAL_PROVIDER = False\n") \
        + MISSION_CODE.replace("{URL!r}", repr(str(local_git_repo)))
    r = subprocess.run([sys.executable, "-c", textwrap.dedent(code)], cwd=KERNEL,
                       capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stderr[-2000:]
    return json.loads(r.stdout.strip().splitlines()[-1])


def test_article7_replacement_via_public_registry_is_honored(local_git_repo):
    """الأحمر أولاً: الاستبدال عبر العقد المدعوم (السجل العام) يجب أن يُحترم
    في التنفيذ — قرار اختيار المزوّد يخص البديل (دليل القرار)، والبديل
    يتلقى المهارتين بعقود مدخلهما المعلنة، والأصل لا ينفذ (راصد الواجهة
    العامة للصنف فارغ)، والمهمة تنتج تحليلاً فعلياً لا مجرد اكتمال."""
    out = _run_mission(local_git_repo)
    assert out["state"] == "completed"
    assert out["selected_provider"] == "SubstituteRepositoryProvider", (
        f"قرار الاختيار لا يخص البديل: {out['selected_provider']}")
    skills = [c["skill"] for c in out["substitute_calls"]]
    assert skills == ["CloneRepository", "ReadRepository"], (
        f"البديل لم يتلق التنفيذ عبر عقديه: {out['substitute_calls']}")
    assert all(c.get("input_ok") is True for c in out["substitute_calls"]), (
        f"العبور ليس بعقود المدخل المعلنة: {out['substitute_calls']}")
    assert out["original_calls"] == [], (
        f"الأصل نفذ رغم الاستبدال عبر السجل: {out['original_calls']}")
    assert out["dna_type_ok"] is True
    assert out["dna_name"] == "sample"
    assert out["dna_languages"], "لا لغات مكتشفة — ناتج فارغ"


def test_article7_refusal_has_no_fallback_to_original(local_git_repo):
    """رفض البديل المختار يفشل المهمة بمسببه المعلل — لا رجوع إلى الإنشاء
    المحلي للأصل (راصد الأصل فارغ)، ومحاولة العبور مسجلة قبل الرفض."""
    out = _run_mission(local_git_repo, refuse_clone=True)
    assert out["state"] == "failed"
    assert out["error"] and "رفض مقصود" in out["error"]
    assert out["selected_provider"] == "SubstituteRepositoryProvider"
    assert any(c["skill"] == "CloneRepository" for c in out["substitute_calls"]), (
        "لم تُسجل محاولة العبور عبر البديل قبل الرفض")
    assert out["original_calls"] == [], (
        f"رجوع إلى الأصل بعد رفض المختار: {out['original_calls']}")


def test_article7_warm_cache_does_not_mask_replacement(local_git_repo):
    """الكاش الدافئ لا يحجب الاستبدال: تشغيل الأصل حتى اكتظاظ الكاش فعلاً
    (مثبت بالفحص لا بالافتراض)، ثم الاستبدال عبر السجل العام وإعادة المهمة
    على المستودع والمراجعة نفسيهما — التنفيذ يجب أن يصل إلى البديل لا أن
    يُعلن اكتمالاً بناتج التنفيذ السابق."""
    out = _run_mission(local_git_repo, warm_first=True)
    assert out["warm_state"] == "completed"
    assert out["cache_filled"] is True, "الكاش لم يمتلئ فعلاً — التوكيد بلا أساس"
    assert out["state"] == "completed"
    skills = [c["skill"] for c in out["substitute_calls"]]
    assert skills == ["CloneRepository", "ReadRepository"], (
        f"الكاش الدافئ حجب الاستبدال — البديل لم ينفذ: {out['substitute_calls']}")


def test_article7_warm_cache_refusal_still_fails(local_git_repo):
    """رفض البديل بعد كاش دافئ يفشل المهمة — لا يُعلن اكتمال اعتماداً على
    ناتج التنفيذ السابق (نفس المستودع والمراجعة)."""
    out = _run_mission(local_git_repo, refuse_clone=True, warm_first=True)
    assert out["warm_state"] == "completed"
    assert out["cache_filled"] is True
    assert out["state"] == "failed"
    assert out["error"] and "رفض مقصود" in out["error"], out["error"]
    assert out["original_calls"] == []


GATE_CODE = """
import json
import providers

SUBSTITUTE_CALLS = []


class SubstituteRepositoryProvider:
    # بديل ناجح (يسجل ويُفوض) — الطفرة تغيّر المزوّد وحده بعد الاعتماد
    def __init__(self):
        self._inner = providers.LocalRepositoryProvider()

    @property
    def name(self):
        return "SubstituteRepositoryProvider"

    def supports_skill(self, skill_name):
        return skill_name in ["CloneRepository", "ReadRepository"]

    def execute(self, skill_name, input_data):
        SUBSTITUTE_CALLS.append(skill_name)
        return self._inner.execute(skill_name, input_data)


from intelligence.interface import (IntelligenceInterface, IntelligenceMode,
                                    IntelligenceRequest, IntelligenceStatus)
iface = IntelligenceInterface()      # الإقلاع الحي الكامل (أنبوب حقيقي)
mission = {{"name": "تحليل", "description": "وصف", "capability": "RepositoryAnalysis",
           "parameters": {{"url": {URL!r}, "branch": "main"}}}}
awaiting = iface.run(IntelligenceRequest(
    mode=IntelligenceMode.ENGINEER, mission=mission))
assert awaiting.status is IntelligenceStatus.AWAITING_APPROVAL
iface.approve(awaiting.approval_id, approver="مالك")
# الطفرة: تغيير المزوّد وحده بعد الاعتماد — الصاحب والدالة ومعاملات
# المستخدم كما اعتمدت؛ الاستبدال عبر العقد المدعوم (السجل العام)
reg = iface._kernel_runtime.provider_registry
reg.unregister("LocalRepositoryProvider")
reg.register(SubstituteRepositoryProvider())
result = iface.execute_approved(awaiting.approval_id)
print(json.dumps({{
    "status": result.status.value,
    "error": result.error,
    "substitute_calls": SUBSTITUTE_CALLS,
}}))
"""


def test_article7_provider_mutation_refused_at_approval_boundary(local_git_repo):
    """طفرة المزوّد وحده بعد الاعتماد (الصاحب والدالة والمعاملات كما هي)
    يُرفض عند حد الاستدعاء **قبل** تنفيذ المزوّد البديل — وسيط المزوّد
    (kwargs) جزء من العمل الموافق عليه لا يمر بلا تحقق (ADR-0009)."""
    code = GATE_CODE.replace("{URL!r}", repr(str(local_git_repo))) \
        .replace("{{", "{").replace("}}", "}")
    r = subprocess.run([sys.executable, "-c", textwrap.dedent(code)], cwd=KERNEL,
                       capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stderr[-2000:]
    out = json.loads(r.stdout.strip().splitlines()[-1])
    assert out["status"] == "failed", (
        f"المزوّد المبدَّل نُفذ — الحد لم يحمِ وسيط المزوّد: {out}")
    assert out["error"] and "لم يُعتمد" in out["error"], out["error"]
    assert out["substitute_calls"] == [], (
        f"البديل نفذ قبل الرفض أو رغمه: {out['substitute_calls']}")


def test_article7_equal_value_providers_do_not_share_cache(local_git_repo):
    """مزوّدان مختلفان «متساويان بالقيمة» (``__eq__``/``__hash__`` — عقد
    السجل لا يشترط هوية التجزئة): البديل الرافض بعد كاش دافئ يجب أن يفشل
    المهمة — تطابق القيمة في مفتاح الكاش لا يُعلن اكتمالاً بناتج تنفيذ
    سابق؛ الفصل بين المنفّذين بالهوية (``is``) لا بالمساواة."""
    out = _run_mission(local_git_repo, refuse_clone=True, warm_first=True,
                       equal_value=True)
    assert out["warm_state"] == "completed"
    assert out["cache_filled"] is True
    assert out["state"] == "failed", (
        f"الكاش الدافئ قبل البديل «المتساوي بالقيمة» — ناتج سابق عُلن "
        f"اكتمالاً: {out}")
    assert out["error"] and "رفض مقصود" in out["error"], out["error"]
    assert out["original_calls"] == []
