"""حدود التنفيذ — المادة 15: «لا تنفيذ خارج Mission Runtime».

الدليل هنا تجريبي لا حقلي: مسار عام حقيقي (``boot`` → ``analyze``) يُدار
بكامل سلسلته، ويُقاس عدد استدعاءات العمل التي عبرت النواة المشتركة فعلاً،
وهوية المستدعى، وترتيبه بين أحداث دورة الحياة، وسجل المهمة في
``rt.missions`` — لا بديل اختباري يحل محل مكون حقيقي: المسجل شفاف يفوّض
العمل كله إلى الدالة الأصلية نفسها على الكائن الحقيقي نفسه.
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
    """المسار الحي كاملاً: عمل المهمة يعبر محرك المهمة إلى النواة المشتركة —
    استدعاء واحد بهوية معلومة وبين حدثي بدء/اكتمال التنفيذ، والمهمة مسجلة
    في سجل المهام (المالك القائم) — لا قناة موازية تتجاوز السجل."""
    out = json.loads(run(f"""
        import json, agos_runtime
        k = agos_runtime.boot()
        pipeline = k.mission_engine.executor.pipeline
        engine = pipeline.execution_engine
        real_invoke = engine.invoke_sync
        calls = []

        def recording_invoke(func, *args, **kwargs):
            # تسجيل الهوية والمعاملات وترتيب الحدث — ثم تفويض كامل للدالة
            # الأصلية على الكائن الحقيقي (لا بديل اختباري)
            calls.append({{
                "name": getattr(func, "__name__", "?"),
                "owner": type(getattr(func, "__self__", None) or object()).__name__,
                "args": [repr(a)[:80] for a in args],
                "events_so_far": [e.type.value for e in k.event_bus.get_events()],
            }})
            return real_invoke(func, *args, **kwargs)

        engine.invoke_sync = recording_invoke
        r = k.analyze({str(git_repo)!r}, branch="main")
        ledger = k.missions
        print(json.dumps({{
            "state": r.state.value,
            "mission_id": r.mission_id,
            "calls": calls,
            "ledger_len": len(ledger),
            "ledger_ids": [getattr(m, "mission_id", None) for m in ledger],
            "events": [e.type.value for e in k.event_bus.get_events(r.mission_id)],
        }}))
    """))
    # المهمة اكتملت عبر المسار الحي وسُجلت في سجل المهام (rt.missions)
    assert out["state"] == "completed"
    assert out["ledger_len"] == 1
    assert out["ledger_ids"] == [out["mission_id"]]
    # أثر معدود: استدعاء عمل واحد فقط عبر النواة المشتركة في كل الإقلاع
    # والتشغيل — لا منفذ جانبي أطلق عملاً خفياً
    assert len(out["calls"]) == 1
    call = out["calls"][0]
    # هوية الاستدعاء: تنفيذ القدرة الحقيقية المسجلة للمهمة بمعاملاتها
    assert call["name"] == "execute"
    assert call["owner"] == "RepositoryAnalysisCapability"
    assert call["args"] == [repr({"url": str(git_repo), "branch": "main"})[:80]]
    # الترتيب: الاستدعاء وقع بعد حدث بدء التنفيذ وقبل حدث اكتماله
    assert "execution_started" in call["events_so_far"]
    assert "execution_completed" not in call["events_so_far"]
    # دورة حياة المهمة كاملة على الناقل الحي بهوية المهمة نفسها
    assert out["events"] == ["capability_selected", "provider_selected",
                             "execution_started", "execution_completed"]


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
    """المنافذ الجانبية (منفذ القدرات الحضاري والمنفذ المتوازي) — إن استُدعت
    فعملها يعبر النواة المشتركة العالمية نفسها، لا محركاً موازياً؛ حد
    معلن: عبورها النواة المشتركة لا يعني مرورها بمحرك المهمة (انظر سجل
    العمل 0088 — تعداد المنافذ)."""
    out = run("""
        import json, agos_runtime
        from agos_kernel.execution.engine import get_engine
        from agos_kernel.execution.parallel import ParallelExecutor, ExecutionTask
        k = agos_runtime.boot()
        engine = get_engine()
        real_invoke = engine.invoke_sync
        seen = []

        def recording_invoke(func, *args, **kwargs):
            seen.append(getattr(func, "__name__", "?"))
            return real_invoke(func, *args, **kwargs)

        engine.invoke_sync = recording_invoke

        class Holder:
            def __init__(self):
                self.done = False

            def handler(self, ctx=None):
                self.done = True
                return {"worked": True}

        holder = Holder()
        # منفذ القدرات الحضاري: حامل حقيقي قابل للاستدعاء (لا نجاح وهمي)
        from agos_kernel.civilization.capability_runtime.runtime import (
            CapabilityExecutor, CapabilityInstance, CapabilityContext)

        instance = CapabilityInstance(contract=None, handler=holder.handler)
        cap_result = CapabilityExecutor().execute(instance, CapabilityContext())
        # المنفذ المتوازي: مهمة حقيقية بحامل حقيقي
        task = ExecutionTask(id="t1", name="t", func=holder.handler)
        par_result = ParallelExecutor().execute([task])
        print(json.dumps({
            "cap_success": cap_result.success,
            "cap_outputs": cap_result.outputs,
            "holder_done": holder.done,
            "par_status": par_result["t1"].value,
            "seen": seen,
        }))
    """)
    import json as _json
    out = _json.loads(out)
    # العبرة: العمل في المنفذين عبر النواة المشتركة العالمية فعلاً —
    # الاستدعاءان رُصدا على المحرك العالمي نفسه ولا محرك ثانياً
    assert out["seen"] == ["handler", "handler"]
    assert out["cap_success"] is True and out["cap_outputs"] == {"worked": True}
    assert out["holder_done"] is True
    assert out["par_status"] == "completed"
