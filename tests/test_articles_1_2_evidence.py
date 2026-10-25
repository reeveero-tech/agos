"""أدلة تشغيلية — المادتان 1 و2 من خريطة أدلة ADR-0010 (الشريحة 0095).

منهج المشروع: أدلة أمينة لا حقول مختلقة ولا أحمر مصطنع لسلوك صحيح.

- المادة 1 (إعلان الهوية): إعلان موقف لا مادة قابلة للفحص الشكلي —
  المختبر: عقد نشر الإعلان (مصدر واحد معرف مرة، مكشوف حرفياً عبر الواجهة
  العامة AGOSConstitution.get_identity)؛ لا ادعاء امتثال سلوكياً.
- المادة 2 (خصائص النواة): الخاصية المثبتة هنا **قابلية النقل** بهذا المدخل
  وهذا السيناريو: لقطة مستقلة (git archive لمراجعة ملتزمة) تُشغَّل من مجلد
  عمل مختلف دون الاعتماد على التثبيت القابل للتحرير للمستودع الأصلي —
  الوحدات تُستورد من النسخة (متحقق من مساراتها)، والمهمة المحلية الحقيقية
  تُنفَّذ عبر المدخل العام (agos_runtime.boot ثم analyze)، ومسار AGOS_ROOT
  يُحترم من النسخة المنقولة. بقية الخصائص مسماة بحدودها في ADR-0010
  (Small بلا عتبة مختلقة؛ Vendor/Domain/AI Independent قرائن بنيوية لا
  إثبات؛ Deterministic وObservable بأدلتها الجزئية في نطاقها).
"""
import json
import os
import subprocess
import sys
import tarfile
import textwrap
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
KERNEL = REPO / "agos" / "agos-kernel"
IDENTITY_TEXT = "AGOS IS NOT AN AI AGENT"


def test_article1_identity_published_from_single_source():
    """المادة 1 — عقد نشر إعلان الهوية: التعريف موجود مرة واحدة (constitution.py)
    والواجهة العامة تعيده حرفياً. هذا نشر إعلان لا إثبات هوية سلوكياً —
    طبيعة المادة إعلانية (تصنيف خريطة الأدلة) وليس لها معيار امتثال سلوكي
    مستقل."""
    out = json.loads(subprocess.run(
        [sys.executable, "-c", textwrap.dedent(f"""
            import json
            from agos.constitution.constitution import AGOSConstitution, IDENTITY_STATEMENT
            print(json.dumps({{
                "verbatim": AGOSConstitution().get_identity() == IDENTITY_STATEMENT,
                "has_statement": {IDENTITY_TEXT!r} in IDENTITY_STATEMENT,
                "os_sentence": "OPERATING SYSTEM FOR AUTONOMOUS EXECUTION" in IDENTITY_STATEMENT,
            }}))
        """)], cwd=REPO, capture_output=True, text=True, timeout=60).stdout)
    assert out["verbatim"] is True
    assert out["has_statement"] is True
    assert out["os_sentence"] is True
    # مصدر واحد للتعريف في الشيفرة المُصدَّرة (شجرة agos/): النص التعريفي لا
    # يظهر في ملفات بايثون داخلها إلا في constitution.py (خارج الشجرة المُصدَّرة:
    # التوثيق والاختبارات تقتبسه ولا تعرّفه)
    definers = [p for p in (REPO / "agos").rglob("*.py")
                if "__pycache__" not in p.parts and IDENTITY_TEXT in p.read_text(encoding="utf-8", errors="ignore")]
    assert definers == [REPO / "agos" / "constitution" / "constitution.py"]


@pytest.fixture(scope="module")
def relocated_copy(tmp_path_factory) -> Path:
    """لقطة مستقلة من المراجعة الملتزمة — طريقة المشروع المدعومة (git archive):
    محتوى المراجعة نفسه بمعزل عن أي تغييرات محلية في الشجرة الحية."""
    copy = tmp_path_factory.mktemp("relocated") / "copy"
    copy.mkdir()
    r = subprocess.run(["git", "archive", "HEAD"], cwd=REPO, capture_output=True)
    assert r.returncode == 0, r.stderr.decode()[-500:]
    with tarfile.open(fileobj=__import__("io").BytesIO(r.stdout)) as tf:
        tf.extractall(copy)
    return copy


@pytest.fixture(scope="module")
def local_git_repo(tmp_path_factory) -> Path:
    repo = tmp_path_factory.mktemp("owner") / "sample"
    repo.mkdir()
    (repo / "requirements.txt").write_text("flask\n")
    (repo / "app.py").write_text("import flask\n")
    env = ["-c", "user.email=t@t", "-c", "user.name=t"]
    for cmd in (["git", "init", "-q", "-b", "main"], ["git", "add", "-A"],
                ["git", *env, "commit", "-qm", "init"]):
        subprocess.run(cmd, cwd=repo, check=True, capture_output=True)
    return repo


def _run_in_copy(code: str, copy: Path, extra_env: dict | None = None):
    env = {k: v for k, v in os.environ.items() if k != "AGOS_ROOT"}
    env["PYTHONPATH"] = ""  # لا اعتماد على مسارات إضافية — cwd وحده
    if extra_env:
        env.update(extra_env)
    return subprocess.run([sys.executable, "-c", textwrap.dedent(code)],
                          cwd=copy / "agos" / "agos-kernel",
                          capture_output=True, text=True, timeout=300, env=env)


def test_article2_kernel_boots_and_runs_mission_from_relocated_copy(
        relocated_copy, local_git_repo):
    """المادة 2 (قابلية النقل — الاكتشاف الافتراضي): النواة تقلع وتنفذ المهمة
    المحلية الحقيقية من النسخة المنقولة بتحديد المسارات من موقع النسخة
    نفسها (لا متغير بيئة) — والوحدات المستوردة من النسخة لا من الأصل خفيةً
    (متحقق من مسارات الملفات)."""
    r = _run_in_copy(f"""
        import json
        import agos_runtime
        from agos_kernel.execution.engine import get_engine
        from providers.filesystem import FilesystemProvider
        k = agos_runtime.boot()
        outcome = k.analyze({str(local_git_repo)!r}, branch="main")
        print(json.dumps({{
            "ready": k.ready,
            "state": outcome.state.value,
            "runtime_file": agos_runtime.__file__,
            "engine_file": get_engine.__module__ and __import__("agos_kernel.execution.engine", fromlist=["x"]).__file__,
            "provider_file": __import__("inspect").getfile(FilesystemProvider),
            "copy_root": {str(relocated_copy)!r},
        }}))
    """, relocated_copy)
    assert r.returncode == 0, r.stderr[-2000:]
    out = json.loads(r.stdout.strip().splitlines()[-1])
    assert out["ready"] is True
    assert out["state"] == "completed"
    copy_root = str(relocated_copy)
    # الوحدات من النسخة المنقولة — لا نجاح خفي عبر الأصل
    for key in ("runtime_file", "engine_file", "provider_file"):
        assert out[key].startswith(copy_root), f"{key} resolved outside the copy: {out[key]}"


def test_article2_agos_root_env_honored_from_relocated_copy(relocated_copy):
    """المادة 2 (قابلية النقل — مسار AGOS_ROOT): السكربت التشغيلي من النسخة
    المنقولة يحترم AGOS_ROOT فيكتب مخرجاته تحت جذر النسخة لا تحت الأصل."""
    agos_root = relocated_copy / "agos"
    r = subprocess.run(
        [sys.executable, str(relocated_copy / "agos" / "agos-kernel" / "civilization" / "engineering_brain" / "run_brain.py")],
        cwd=relocated_copy / "agos" / "agos-kernel",
        capture_output=True, text=True, timeout=300,
        env={**{k: v for k, v in os.environ.items()}, "AGOS_ROOT": str(agos_root)})
    assert r.returncode == 0, (r.stdout + r.stderr)[-2000:]
    results_file = agos_root / "output" / "brain_test_results.json"
    assert results_file.exists(), "المخرجات لم تُكتب تحت جذر النسخة المنقولة"
    data = json.loads(results_file.read_text(encoding="utf-8"))
    assert isinstance(data, dict) and data  # ناتج فعلي لا ملف فارغ
