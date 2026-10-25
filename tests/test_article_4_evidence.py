"""أدلة تشغيلي — المادة 4 من خريطة أدلة ADR-0010: العقود (الشريحة 0096).

منهج المشروع: أحمر أولاً ثم أدنى إصلاح.

القاعدة الدستورية (CONTRACT_RULES): لا تبعيات مباشرة، لا تبعيات خفية، لا
اختصارات تشغيلي. المخالفة المكتشفة: مسار المهمة الحي (تحليل المستودع)
يستدعي من القدرة ميثودات المزوّد **الخاص** (``_clone``/``_read``) متجاوزاً
واجهة المهارات العامة ``execute`` القائمة لهذا التبادل — اختصار تشغيلي.
الإصلاح الأدنى: العبور عبر ``execute`` بعقود المدخل المعلنة
(CloneRepositoryInput/ReadRepositoryInput لا أنواع القدرة).

الأدلة: النداءات عند حد المزوّد تُرصد بالكامل (المهارة، نوع المدخل، نوع
المخرج، نوع اللقطة) — العبور بالترتيب عبر المهارتين بعقودهما المعلنة،
والبوابة مستخدمة فعلاً (رفض مقصود لـexecute يفشل المهمة بلا رجوع للنداء
الخاص). الإنشاء المباشر للمزوّد داخل القدرات متبقٍ صريح للمادة 4.
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


PROXY_CODE = """
import json
import providers
from providers import (CloneRepositoryInput, CloneRepositoryOutput,
                        ReadRepositoryInput, ReadRepositoryOutput)
from contracts import RepositorySnapshot

# الوسيط: يسجل كل محاولة نداء **قبل** التفويض (رجوع لنداء خاص يُرصد ولو أثار
# استثناء)، ثم يكملها بالمخرج عند النجاح، ويتحقق بالأنواع المعلنة الفعلية
# (isinstance لا الأسماء — الأسماء للتشخيص فقط). نداء execute الداخلي إلى
# self._clone داخل الكائن الحقيقي مشروع ولا يُرصد.
CALLS = []


def _record_attempt(name, args):
    entry = {"name": name, "attempted": True}
    if name == "execute" and args:
        entry["skill"] = args[0]
        if len(args) > 1:
            entry["input_type"] = type(args[1]).__name__
            if args[0] == "CloneRepository":
                entry["input_ok"] = isinstance(args[1], CloneRepositoryInput)
            elif args[0] == "ReadRepository":
                entry["input_ok"] = isinstance(args[1], ReadRepositoryInput)
    CALLS.append(entry)
    return entry


def _record_result(entry, result):
    if result is not None:
        entry["output_type"] = type(result).__name__
        if entry.get("skill") == "CloneRepository":
            entry["output_ok"] = isinstance(result, CloneRepositoryOutput)
        elif entry.get("skill") == "ReadRepository":
            entry["output_ok"] = isinstance(result, ReadRepositoryOutput)
        snap = getattr(result, "snapshot", None)
        if snap is not None:
            entry["snapshot_type"] = type(snap).__name__
            entry["snapshot_ok"] = isinstance(snap, RepositorySnapshot)
    return result


class RecordingProvider:
    def __init__(self, inner):
        self._inner = inner

    def __getattr__(self, name):
        attr = getattr(self._inner, name)
        if callable(attr):
            def rec(*a, **kw):
                entry = _record_attempt(name, a)
                result = attr(*a, **kw)
                return _record_result(entry, result)
            return rec
        return attr


REAL_PROVIDER = providers.LocalRepositoryProvider
recording_factory = lambda: RecordingProvider(REAL_PROVIDER())  # noqa: E731
"""


def _run_mission(local_git_repo: Path, refuse_clone: bool = False) -> dict:
    """يشغل المهمة الحقيقية عبر المدخل العام مع تثبيت الوسيط مكان المصنع
    (بعد الإقلاع — قبلَه يفشل تحقق عقود الإقلاع)."""
    refuse = """
class RefusingProvider:
    def __init__(self, inner):
        self._inner = inner

    def __getattr__(self, name):
        attr = getattr(self._inner, name)
        if name == "execute":
            def refuse(skill, data):
                # تسجيل المحاولة قبل الرفض — إثبات الوصول إلى البوابة نفسها
                _record_attempt("execute", (skill, data))
                if skill == "CloneRepository":
                    raise RuntimeError("رفض مقصود للاختبار — بوابة execute مستخدمة فعلاً")
                result = attr(skill, data)
                return _record_result(CALLS[-1], result)
            return refuse
        if callable(attr):
            def rec(*a, **kw):
                entry = _record_attempt(name, a)
                result = attr(*a, **kw)
                return _record_result(entry, result)
            return rec
        return attr


def refusing_factory():
    return RefusingProvider(REAL_PROVIDER())
""" if refuse_clone else ""
    code = PROXY_CODE + refuse + f"""
import agos_runtime
k = agos_runtime.boot()
providers.LocalRepositoryProvider = {("refusing_factory" if refuse_clone else "recording_factory")}
outcome = k.analyze({str(local_git_repo)!r}, branch="main")
from contracts import RepositoryDNA
dna = getattr(outcome, "result", None)
print(json.dumps({{
    "state": outcome.state.value,
    "error": getattr(outcome, "error", None),
    "calls": CALLS,
    "dna_type_ok": isinstance(dna, RepositoryDNA),
    "dna_name": getattr(dna, "name", None) if dna is not None else None,
    "dna_languages": (getattr(dna, "languages", None) or [])[:5] if dna is not None else None,
}}))
"""
    r = subprocess.run([sys.executable, "-c", textwrap.dedent(code)], cwd=KERNEL,
                       capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stderr[-2000:]
    return json.loads(r.stdout.strip().splitlines()[-1])


def _execute_calls(out: dict) -> list:
    return [c for c in out["calls"] if c["name"] == "execute"]


def test_article4_mission_crosses_via_public_skill_interface(local_git_repo):
    """الأحمر أولاً: مسار المهمة الحي كان يعبر من القدرة إلى ميثودات المزوّد
    الخاص (رُصد _clone و_read قبل الإصلاح) — يجب أن يعبر عبر واجهة المهارات
    العامة فلا يظهر في النداءات المرصودة أي اسم يبدأ بشرطة سفلية، وبالترتيب
    عبر المهارتين."""
    out = _run_mission(local_git_repo)
    assert out["state"] == "completed"
    private_calls = [c["name"] for c in out["calls"] if c["name"].startswith("_")]
    assert private_calls == [], f"اختصار تشغيلي: نداءات خاصة على المزوّد: {private_calls}"
    assert [c.get("skill") for c in _execute_calls(out)] == ["CloneRepository", "ReadRepository"]


def test_article4_crossing_objects_are_contracts(local_git_repo):
    """دليل الحدود بالكامل: كل عملية عبر execute بمدخلها ومخرجها المعلنين —
    التحقق بالأنواع الفعلية (isinstance داخل العملية الحية بالأصناف المعلنة،
    لا الأسماء): CloneRepositoryInput→CloneRepositoryOutput ثم
    ReadRepositoryInput→ReadRepositoryOutput وsnapshot عقد RepositorySnapshot؛
    والناتج النهائي RepositoryDNA بحقيقة متوقعة من المستودع المصغر (اسمه
    ولغاته الفعلية) — لا مجرد حالة مكتملة."""
    out = _run_mission(local_git_repo)
    assert out["state"] == "completed"
    calls = _execute_calls(out)
    assert len(calls) == 2
    assert [c.get("skill") for c in calls] == ["CloneRepository", "ReadRepository"]
    assert calls[0]["input_ok"] is True
    assert calls[0]["output_ok"] is True
    assert calls[1]["input_ok"] is True
    assert calls[1]["output_ok"] is True
    assert calls[1]["snapshot_ok"] is True
    assert out["dna_type_ok"] is True
    assert out["dna_name"] == "sample"
    assert out["dna_languages"], "لا لغات مكتشفة في المستودع — ناتج فارغ"


def test_article4_public_interface_is_the_actual_gate(local_git_repo):
    """البوابة مستخدمة فعلاً لا شكلياً: رفض مقصود لمهارة CloneRepository عبر
    execute — تسجل المحاولة قبل الرفض (إثبات الوصول إلى البوابة) — يفشل
    المهمة (state فاشل وسبب الرفض في الناتج) ولا ترجع القدرة إلى النداء
    الخاص لتجاوز الرفض (كل المحاولات مسجلة قبل التفويض — رجوع مهيأ للاستثناء
    يُرصد أيضاً)."""
    out = _run_mission(local_git_repo, refuse_clone=True)
    assert out["state"] == "failed"
    assert out["error"] and "رفض مقصود" in out["error"]
    attempts = [c for c in out["calls"] if c["name"] == "execute" and c.get("skill") == "CloneRepository"]
    assert attempts, "لم تُسجل محاولة الوصول إلى البوابة المرفوضة"
    private_attempts = [c["name"] for c in out["calls"] if c["name"].startswith("_")]
    assert private_attempts == [], f"رجوع إلى النداء الخاص لتجاوز الرفض: {private_attempts}"
