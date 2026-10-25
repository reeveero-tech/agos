"""أدلة تشغيلي — المادتان 8 و11 من خريطة أدلة ADR-0010: الملكية ودورة
الحياة (الشريحة 0098).

منهج المشروع: أحمر أولاً ثم أدنى إصلاح.

النص الحاكم: المادة 8 «لا مكوّن يملك النظام؛ كل مكوّن خادم للنواة»،
والمادة 11 تعداد ملكية النواة (النية، الأهداف، السياق، التخطيط،
الاستدلال، السياسات، المعرفة، مخطط التنفيذ، حالة المهمة).

التتبع المكتمل (من ينشئ/يحمل/يُجيز/يُنهي): Bootstrapper وحده يبني
الحاوية والسجلات والمحرك عبر ``agos_runtime.boot()``، و``KernelRuntime``
مقبض رفيع (كل سماته كائنات Bootstrapper نفسها) — وعقد الإنهاء المعلن
لواجهة دورة الحياة ``AGOSKernel.shutdown``: «إيقاف قبول المهام».

الخرق المكتشف (قبل أي إصلاح): فحص حالة القبول موجود في
``MissionManager`` وحده، بينما المدخل العام الذي يُرجعه الإقلاع نفسه
(``KernelRuntime.run`` — ويمر عبره المسار الحي المعتمد لواجهة الذكاء)
لا يفحص شيئاً: بعد ``shutdown()`` تُقبل المهمة وتكتمل — «إيقاف قبول
المهام» قشرة لا سلطة.

الإصلاح الأدنى المعتمد: حالة قبول صريحة يملكها المقبض نفسه —
``KernelRuntime`` يبدأ قبولاً للمهام، و``stop()`` (رمز عام جديد) توقف
القبول، و``run()`` ترفض بعد الإيقاف باستثناء دورة حياة صريح
(``KernelNotRunning`` الموجود — لا ``BootError``: نجاح الإقلاع منفصل عن
حالة القبول) قبل الوصول إلى المحرك؛ ``AGOSKernel.shutdown`` يفوّض إلى
``runtime.stop()`` ويبقى idempotent. حارس واحد يغطي المدخلين المباشر
والمسار الحي للواجهة (كلاهما عبر ``KernelRuntime.run``).
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
    (repo / "app.py").write_text("import flask\n")
    env = ["-c", "user.email=t@t", "-c", "user.name=t"]
    for cmd in (["git", "init", "-q", "-b", "main"], ["git", "add", "-A"],
                ["git", *env, "commit", "-qm", "init"]):
        subprocess.run(cmd, cwd=repo, check=True, capture_output=True)
    return repo


def _mission_dict(repo: Path) -> dict:
    return {"name": "تحليل", "capability": "RepositoryAnalysis",
            "parameters": {"url": str(repo), "branch": "main"}}


def _run_kernel(code: str) -> dict:
    r = subprocess.run([sys.executable, "-c", textwrap.dedent(code)], cwd=KERNEL,
                       capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stderr[-2000:]
    return json.loads(r.stdout.strip().splitlines()[-1])


def test_article8_11_shutdown_stops_acceptance_at_runtime_entry(local_git_repo):
    """الأحمر أولاً: إيقاف النواة يجب أن يوقف قبول المهام عند المدخل العام
    الذي يُرجعه الإقلاع نفسه — لا في غلاف الواجهة وحده. الدليل الأساسي
    قبولُ المهمة واكتمالها بعد الإيقاف (قبل الإصلاح)؛ وبعده: مهمة تنجح
    قبل الإيقاف بعدّاد نداءات موجب عند **المزوّد** نفسه (واجهة المهارات
    العامة execute — لا مدخل القدرة الذي قد يعيد نتيجة من الكاش دون
    استدعاء المزوّد)، ثم الطلب عبر المرجع المحتفَظ به بعد ``shutdown()``
    يُرفض باستثناء دورة حياة صريح بلا أي نداء إضافي، ويبقى الرفض بعد
    إيقاف ثانٍ (idempotent)."""
    code = f'''
    import json
    from core.kernel import AGOSKernel, KernelNotRunning

    # الراصد: تنفيذ المزوّد نفسه (واجهة المهارات العامة execute على صنف
    # المزوّد) — لا مدخل القدرة الذي قد يعيد نتيجة من الكاش دون استدعاء
    # المزوّد؛ تسجيل فقط لا تغيير سلوك.
    PROVIDER_CALLS = []
    import providers
    _real_exec = providers.LocalRepositoryProvider.execute
    def _rec_exec(self, skill_name, input_data):
        PROVIDER_CALLS.append(skill_name)
        return _real_exec(self, skill_name, input_data)
    providers.LocalRepositoryProvider.execute = _rec_exec

    k = AGOSKernel()
    k.start()
    runtime = k.runtime                      # المرجع المحتفَظ به قبل الإيقاف
    m1 = k.mission_manager.execute({_mission_dict(local_git_repo)!r})
    before = {{"status": m1.status.name, "provider_calls": len(PROVIDER_CALLS)}}

    k.shutdown()
    refused = None
    refusal_error = None
    completed_state = None
    try:
        out = runtime.run({_mission_dict(local_git_repo)!r})
        completed_state = out.state.value    # خرق: قبل الإصلاح يكتمل هنا
    except KernelNotRunning as exc:
        refused = True
        refusal_error = str(exc)
    except Exception as exc:                   # أي استثناء آخر ليس الرفض المعتمد
        refused = False
        refusal_error = f"{{type(exc).__name__}}: {{exc}}"
    calls_after_first = len(PROVIDER_CALLS)

    k.shutdown()                               # الإيقاف الثاني — idempotent
    refused_after_second = None
    try:
        runtime.run({_mission_dict(local_git_repo)!r})
        refused_after_second = False
    except KernelNotRunning:
        refused_after_second = True

    print(json.dumps({{
        "before": before,
        "refused": refused,
        "refusal_error": refusal_error,
        "completed_state": completed_state,
        "calls_after_first": calls_after_first,
        "refused_after_second": refused_after_second,
        "final_calls": len(PROVIDER_CALLS),
    }}))
    '''
    out = _run_kernel(code)
    assert out["before"]["status"] == "SUCCESS", out
    assert out["before"]["provider_calls"] >= 1, (
        f"عدّاد نداءات المزوّد ليس موجباً — التوكيد بلا أساس: {out}")
    assert out["refused"] is True and out["refusal_error"], (
        f"المهمة قُبلت ونُفذت بعد الإيقاف عبر المدخل العام — الإيقاف قشرة: {out}")
    assert out["calls_after_first"] == out["before"]["provider_calls"], (
        f"نداءات إضافية بعد الإيقاف: {out}")
    assert out["refused_after_second"] is True, (
        f"الرفض لم يبقَ بعد إيقاف ثانٍ: {out}")
    assert out["final_calls"] == out["before"]["provider_calls"], out


def test_article8_11_interface_live_path_shares_the_guard(local_git_repo):
    """المسار الحي المعتمد لواجهة الذكاء يمر عبر ``KernelRuntime.run`` —
    حارس القبول واحد يغطيه: بعد ``k.shutdown()`` (العقد القائم المُصلَح —
    الإيقاف يفوّض للمقبض نفسه)، تنفيذ معتمد جديد يُرفض بالاستثناء الصريح
    نفسه بلا أي نداء إضافي عند المزوّد."""
    code = f'''
    import json
    from core.kernel import AGOSKernel, KernelNotRunning
    from intelligence.interface import (IntelligenceInterface,
                                        IntelligenceMode, IntelligenceRequest,
                                        IntelligenceStatus)

    PROVIDER_CALLS = []
    import providers
    _real_exec = providers.LocalRepositoryProvider.execute
    def _rec_exec(self, skill_name, input_data):
        PROVIDER_CALLS.append(skill_name)
        return _real_exec(self, skill_name, input_data)
    providers.LocalRepositoryProvider.execute = _rec_exec

    k = AGOSKernel()
    k.start()
    runtime = k.runtime
    iface = IntelligenceInterface(kernel_runtime=runtime)

    mission = {{"name": "تحليل", "description": "وصف",
               "capability": "RepositoryAnalysis",
               "parameters": {{"url": {str(local_git_repo)!r}, "branch": "main"}}}}
    awaiting = iface.run(IntelligenceRequest(mode=IntelligenceMode.ENGINEER,
                                             mission=mission))
    assert awaiting.status is IntelligenceStatus.AWAITING_APPROVAL
    iface.approve(awaiting.approval_id, approver="مالك")
    result = iface.execute_approved(awaiting.approval_id)
    before = {{"status": result.status.value, "provider_calls": len(PROVIDER_CALLS)}}

    k.shutdown()   # العقد القائم المُصلَح — الإيقاف يفوّض للمقبض نفسه
    refused = None
    refusal_error = None
    m2 = {{"name": "تحليل 2", "description": "وصف",
           "capability": "RepositoryAnalysis",
           "parameters": {{"url": {str(local_git_repo)!r}, "branch": "main"}}}}
    a2 = iface.run(IntelligenceRequest(mode=IntelligenceMode.ENGINEER,
                                        mission=m2))
    iface.approve(a2.approval_id, approver="مالك")
    try:
        iface.execute_approved(a2.approval_id)
        refused = False
    except KernelNotRunning as exc:
        refused = True
        refusal_error = str(exc)
    print(json.dumps({{"before": before, "refused": refused,
                       "refusal_error": refusal_error,
                       "final_calls": len(PROVIDER_CALLS)}}))
    '''
    out = _run_kernel(code)
    assert out["before"]["status"] == "completed", out
    assert out["before"]["provider_calls"] >= 1, out
    assert out["refused"] is True and out["refusal_error"], (
        f"المسار الحي للواجهة نفّذ بعد إيقاف النواة: {out}")
    assert out["final_calls"] == out["before"]["provider_calls"], out
