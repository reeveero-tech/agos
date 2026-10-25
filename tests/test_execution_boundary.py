"""حدود التنفيذ — المادة 15: «لا تنفيذ خارج Mission Runtime» (تصحيح سجل
العمل 0089 لادعاءات سجل العمل 0088).

الدليل تجريبي محدود الحدود لا إثبات سالب عام:
- المسجل الشفاف يُركَّب على النواة المشتركة (get_engine — كائن عالمي واحد)
  **قبل الإقلاع**، فيرصد كل استدعاء عمل يعبرها أثناء الإقلاع والتشغيل معاً
  — وما لم يرصده ليس دليل غيابه (عمل قد يجري خارج النواة المشتركة أصلاً؛
  الحصر الأثري لمنافذ الاستدعاء مسند في سجل العمل 0088/0089 بمسارات مقروءة
  مسماة، لا إثباتاً شاملاً).
- لا بديل اختباري: المسجل يفوّض كل عمل إلى الدالة الأصلية نفسها على الكائن
  الحقيقي نفسه.
- الحد المعتمد (ADR-0008): سلطة استدعاء العمل المشتركة هي النواة
  (invoke_sync)، والمسار الحي المعتمد هو الأنبوب (ExecutionPipeline) —
  عبور المنافذ الجانبية النواة المشتركة لا يجعلها داخل Mission Runtime:
  لا سجل مهمة لها (مثبت أدناه)، فهي تجاوز للحد إن استُدعيت إنتاجياً.
"""
import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
KERNEL = REPO / "agos" / "agos-kernel"


def run(code: str, cwd: Path = KERNEL) -> str:
    r = subprocess.run([sys.executable, "-c", textwrap.dedent(code)], cwd=cwd,
                       capture_output=True, text=True, timeout=180)
    assert r.returncode == 0, r.stderr[-2000:]
    return r.stdout.strip().splitlines()[-1]


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


def test_real_mission_work_executes_only_through_mission_runtime(git_repo):
    """المسار الحي كاملاً عبر المدخل العام (KernelRuntime.run): استدعاء العمل
    يعبر النواة المشتركة بهوية مقارَنة كاملة داخل العملية نفسها، وترتيبه
    بين حدثي بدء/اكتمال التنفيذ، والمهمة تُلحق بسجل المهام في
    KernelRuntime.run نفسه (موضع الإلحاق موثق في الشيفرة — agos_runtime:95).
    المقياس محدود: ما رُصد عبر النواة المشتركة فقط (المسجل يغطي الإقلاع
    والتشغيل معاً)؛ لا ادعاء عن عمل قد يجري خارجها."""
    out = json.loads(run(f"""
        import json
        from agos_kernel.execution.engine import get_engine

        # المسجل يُركَّب قبل الإقلاع — النواة المشتركة كائن عالمي واحد
        # يستهلكه المُقلِع نفسه، فيرصد الإقلاع والتشغيل معاً
        engine = get_engine()
        real_invoke = engine.invoke_sync
        calls = []
        k_bus = None  # يُربط بعد الإقلاع — أثناء الإقلاع لا ناقل بعد

        def recording_invoke(func, *args, **kwargs):
            events = ([e.type.value for e in k_bus.get_events()]
                      if k_bus is not None else [])
            calls.append({{
                "func": func,
                "args": args,
                "events_so_far": events,
            }})
            return real_invoke(func, *args, **kwargs)

        engine.invoke_sync = recording_invoke
        import agos_runtime
        k = agos_runtime.boot()
        k_bus = k.event_bus
        boot_calls = len(calls)  # ما عبر النواة أثناء الإقلاع نفسه
        r = k.analyze({str(git_repo)!r}, branch="main")

        # مقارنة الهوية كاملة داخل العملية: المستدعى هو تنفيذ القدرة
        # الحقيقية المسجلة نفسها (الكائن من السجل) بمعاملات المهمة كما هي
        registered = [c for c in k.capability_registry.list_all()
                      if type(c).__name__ == "RepositoryAnalysisCapability"]
        identity_ok = (len(calls) - boot_calls == 1
                       and calls[-1]["func"].__name__ == "execute"
                       and registered and calls[-1]["func"].__self__ is registered[0]
                       and calls[-1]["args"] == ({{"url": {str(git_repo)!r},
                                                  "branch": "main"}},))
        print(json.dumps({{
            "state": r.state.value,
            "mission_id": r.mission_id,
            "boot_calls": boot_calls,
            "run_calls": len(calls) - boot_calls,
            "identity_ok": identity_ok,
            "events_at_call": calls[-1]["events_so_far"] if calls else [],
            "ledger_len": len(k.missions),
            "ledger_last_id": k.missions[-1].mission_id,
        }}))
    """))
    assert out["state"] == "completed"
    # ما رُصد عبر النواة المشتركة أثناء التشغيل: استدعاء واحد — لا أكثر
    # (الادعاء محدود بما عبر النواة المشتركة المرصودة، لا إثبات سالب عام)
    assert out["boot_calls"] >= 0
    assert out["run_calls"] == 1
    # المقارنة الكاملة نجحت داخل العملية (هوية الكائن من السجل + المعاملات)
    assert out["identity_ok"] is True
    # الترتيب: الاستدعاء وقع بعد حدث بدء التنفيذ وقبل حدث اكتماله
    assert "execution_started" in out["events_at_call"]
    assert "execution_completed" not in out["events_at_call"]
    # السجل: المهمة أُلحقت في KernelRuntime.run (الموضع الموثق في الشيفرة)
    assert out["ledger_len"] >= 1
    assert out["ledger_last_id"] == out["mission_id"]


def test_failed_resolution_executes_no_work_via_real_entry():
    """مدخل حقيقي مرفوض: مهمة بقدرة غير مسجلة تفشل في التحديد قبل أي استدعاء
    عمل عبر النواة المشتركة — أثر معدوم (صفر استدعاء) والمهمة الفاشلة
    مسجلة في سجل المهام بفشلها الصريح."""
    out = json.loads(run("""
        import json
        from agos_kernel.execution.engine import get_engine
        engine = get_engine()
        real_invoke = engine.invoke_sync
        calls = []

        def recording_invoke(func, *args, **kwargs):
            calls.append(getattr(func, "__name__", "?"))
            return real_invoke(func, *args, **kwargs)

        engine.invoke_sync = recording_invoke
        import agos_runtime
        k = agos_runtime.boot()
        r = k.run({"name": "رفض", "capability": "NonexistentCapability_XYZ",
                   "parameters": {}})
        print(json.dumps({
            "state": r.state.value,
            "work_calls": len(calls),
            "ledger_len": len(k.missions),
            "ledger_last_state": k.missions[-1].state.value,
        }))
    """))
    assert out["state"] == "failed"
    # أثر معدوم: صفر استدعاء عمل عبر النواة المشتركة عند فشل التحديد
    assert out["work_calls"] == 0
    # الفشل مسجل صراحة لا مبتلع
    assert out["ledger_len"] >= 1
    assert out["ledger_last_state"] == "failed"


def test_pipeline_uses_the_single_shared_kernel_engine():
    """قناة واحدة: أنابيب المهمة تستدعي العمل عبر النواة المشتركة العالمية
    نفسها (get_engine) — لا نواة ثانية موازية تُستدعم."""
    out = run("""
        import agos_runtime
        from agos_kernel.execution.engine import get_engine
        k = agos_runtime.boot()
        pipeline = k.mission_engine.executor.pipeline
        print(pipeline.execution_engine is get_engine())
    """)
    assert out == "True"


def test_side_outlets_cross_the_shared_kernel_not_a_second_engine():
    """المنافذ الجانبية (منفذ القدرات الحضاري والمنفذ المتوازي): عملها
    الحقيقي يعبر النواة المشتركة نفسها (أثر مستقل معدود لكل منفذ)، لكنها
    **لا تُلحق شيئاً بسجل المهام** (rt.missions) — عبور النواة المشتركة لا
    يجعلها داخل Mission Runtime؛ فهي تجاوز للحد المعتمد (ADR-0008: المسار
    الحي هو الأنبوب) إن استُدعيت إنتاجياً. اليوم لا مستدعي إنتاجياً لها
    (حصر سجل العمل 0088 — مسارات مقروءة مسماة، لا إثبات شامل)."""
    out = json.loads(run("""
        import json
        from agos_kernel.execution.engine import get_engine
        from agos_kernel.execution.parallel import ParallelExecutor, ExecutionTask
        engine = get_engine()
        real_invoke = engine.invoke_sync
        seen = []

        def recording_invoke(func, *args, **kwargs):
            seen.append(getattr(func, "__name__", "?"))
            return real_invoke(func, *args, **kwargs)

        engine.invoke_sync = recording_invoke
        import agos_runtime
        k = agos_runtime.boot()
        ledger_before = len(k.missions)

        # عدّاد أثر مستقل لكل منفذ — لا قيمة منطقية واحدة مشتركة
        effects = {"capability": 0, "parallel": 0}

        class CapHolder:
            def handler(self, ctx=None):
                effects["capability"] += 1
                return {"worked": True}

        class ParHolder:
            def handler(self, ctx=None):
                effects["parallel"] += 1
                return {"worked": True}

        # منفذ القدرات الحضاري: حامل حقيقي قابل للاستدعاء (لا نجاح وهمي)
        from agos_kernel.civilization.capability_runtime.runtime import (
            CapabilityExecutor, CapabilityInstance, CapabilityContext)
        instance = CapabilityInstance(contract=None, handler=CapHolder().handler)
        cap_result = CapabilityExecutor().execute(instance, CapabilityContext())
        # المنفذ المتوازي: مهمة حقيقية بحامل حقيقي
        task = ExecutionTask(id="t1", name="t", func=ParHolder().handler)
        par_result = ParallelExecutor().execute([task])
        print(json.dumps({
            "cap_success": cap_result.success,
            "cap_outputs": cap_result.outputs,
            "par_status": par_result["t1"].value,
            "effects": effects,
            "seen": seen,
            "ledger_before": ledger_before,
            "ledger_after": len(k.missions),
        }))
    """))
    # أثر مستقل معدود لكل منفذ: كل حامل نُفذ مرة واحدة فعلاً
    assert out["effects"] == {"capability": 1, "parallel": 1}
    assert out["cap_success"] is True and out["cap_outputs"] == {"worked": True}
    assert out["par_status"] == "completed"
    # العمل عبر النواة المشتركة نفسها — لا محركاً موازياً
    assert out["seen"] == ["handler", "handler"]
    # الحد: لا إلحاق بسجل المهام من المنافذ الجانبية — تجاوز معلن للحد
    assert out["ledger_after"] == out["ledger_before"]
