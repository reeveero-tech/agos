"""اختبارات توصيف التنفيذ — R-W1-003 (مسح التوصيف على HEAD قبل أي تغيير).

توصّف السلوك القائم كما هو — بما فيه **المزيف الموثّق**: منفذات تدّعي الإكمال
بلا استدعاء عمل (ParallelExecutor.execute، ExecutionFabric، workflow_runtime،
CapabilityExecutor — عُيّنت أسماها صريحة في التوثيق)، ومحرك نووي بمنطق إدارة
حقيقي (مهلة/إعادة/استدعاء كوروتين) بمهارة محاكاة. لا تحكم هذه الاختبارات على
السلوك بل تثبته، ليُبنى التوحيد (ADR-0008) عليها.
"""
import asyncio
import sys
from dataclasses import dataclass, field
from pathlib import Path

_HERE = Path(__file__).resolve()
_KERNEL = _HERE.parent.parent / "agos" / "agos-kernel"
if str(_KERNEL) not in sys.path:
    sys.path.insert(0, str(_KERNEL))

import pytest

# --- مسار النواة الحي (bare) ---
from context import ExecutionContext  # noqa: E402
from events import EventBus, EventType  # noqa: E402
from mission import Mission  # noqa: E402
from pipeline import ExecutionPipeline, ExecutionResult, ExecutionStatus  # noqa: E402
from resolvers import (  # noqa: E402
    CapabilitySelection, ProviderSelection, ResolutionStatus, SelectionScore,
)

# --- عبر الشجرة ---
from agos_kernel.execution.compiler import CompilerStatus, MissionCompiler  # noqa: E402
from agos_kernel.execution.engine import ExecutionEngine, ExecutionEvent  # noqa: E402
from agos_kernel.execution import ParallelExecutor  # noqa: E402
from agos_kernel.execution.parallel import ExecutionTask  # noqa: E402
from agos_kernel.civilization.workflow_runtime.workflow import (  # noqa: E402
    StepType, WorkflowRuntime, WorkflowStep,
)
from agos_kernel.civilization.capability_runtime.runtime import (  # noqa: E402
    CapabilityContext, CapabilityExecutor, CapabilityInstance,
)
from agos.cloud_execution import UniversalExecutionCloud  # noqa: E402
from agos.fabric.execution import ExecutionFabric, ExecutionNode  # noqa: E402
from agos.execution.fabric import UniversalExecutionFabric  # noqa: E402
from agos_kernel.execution.engine import InvocationOutcome as _InvocationOutcome  # noqa: E402


# ---------------------------------------------------------------
# بنّاؤون زائفون حتميون لمسار الأنبوب الحي
# ---------------------------------------------------------------
class _FakeCapability:
    """قدرة زائفة: استدعاء عمل حقيقي واحد قابل للعدّ والفشل."""

    calls: list = []

    def execute(self, parameters):
        type(self).calls.append(dict(parameters))
        if getattr(self, "fail", False):
            raise RuntimeError("boom")
        return {"marker": "REAL-WORK"}


def _selection(capability, name="FakeCap", record="cap-record"):
    return CapabilitySelection(
        capability=capability, capability_name=name, manifest_id="",
        status=ResolutionStatus.SUCCESS, score=SelectionScore(),
        reason="deterministic-fake", record=record)


def _provider_selection(record="prov-record"):
    return ProviderSelection(
        provider=object(), provider_name="FakeProvider",
        status=ResolutionStatus.SUCCESS, score=SelectionScore(),
        reason="deterministic-fake", record=record)


class _FakeCapResolver:
    def __init__(self, capability):
        self._capability = capability

    def resolve(self, mission, context):
        return _selection(self._capability)


class _FakeProvResolver:
    def resolve(self, capability, mission):
        return _provider_selection()


def _pipeline_with(capability):
    return ExecutionPipeline(
        event_bus=EventBus(),
        capability_resolver=_FakeCapResolver(capability),
        provider_resolver=_FakeProvResolver())


# ===============================================================
# 1) المسار الحي: الأنبوب هو الاستدعاء الوحيد للعمل — نجاح
# ===============================================================
def test_live_pipeline_success_invokes_real_work_once():
    """النجاح: استدعاء العمل مرة واحدة بالمعاملات، وخطوات ثلاث، وعقدي القرار."""
    cap = _FakeCapability()
    _FakeCapability.calls = []
    mission = Mission(id="m1", name="nm", capability="FakeCap",
                      parameters={"url": "file:///repo"})
    result = _pipeline_with(cap).execute(mission)

    assert result.status is ExecutionStatus.COMPLETED
    assert result.result == {"marker": "REAL-WORK"}
    assert _FakeCapability.calls == [{"url": "file:///repo"}]  # مرة واحدة فعلاً
    assert [s.step_id for s in result.steps] == [
        "resolve_capability", "resolve_provider", "execute_capability"]
    assert result.decision_records == ["cap-record", "prov-record"]
    assert result.completed_at is not None
    assert result.error is None


def test_live_pipeline_failure_preserves_decision_records():
    """الفشل: الخطأ مسجل، وعقدا القرار محفوظان (R-W1-004) — لا سقوط للدليل."""
    cap = _FakeCapability()
    cap.fail = True
    mission = Mission(id="m2", name="nm", capability="FakeCap", parameters={})
    result = _pipeline_with(cap).execute(mission)

    assert result.status is ExecutionStatus.FAILED
    assert result.error == "boom"
    assert result.decision_records == ["cap-record", "prov-record"]
    assert result.steps[-1].step_id == "error"
    assert result.steps[-1].status is ExecutionStatus.FAILED
    assert result.completed_at is not None


def test_live_pipeline_publishes_lifecycle_events():
    """الأحداث المنشورة عبر المسار الحي: اختيار القدرة والموفّر وبداية/اكتمال التنفيذ."""
    cap = _FakeCapability()
    mission = Mission(id="m3", name="nm", capability="FakeCap", parameters={})
    bus = EventBus()
    ExecutionPipeline(bus, _FakeCapResolver(cap), _FakeProvResolver()).execute(mission)

    published = [e.type for e in bus._events]
    assert EventType.CAPABILITY_SELECTED in published
    assert EventType.PROVIDER_SELECTED in published
    assert EventType.EXECUTION_STARTED in published
    assert EventType.EXECUTION_COMPLETED in published


# ===============================================================
# 2) محرك النواة: منطق إدارة حقيقي (كوروتين/مهلة/إعادة) بمهارة محاكاة
# ===============================================================
def test_kernel_engine_executes_real_coroutine_distinctly():
    """المحرك النووي يستدعي كوروتيناً حقيقياً: النتيجة المميزة تعود كما هي —
    منطق الاستدعاء والمهلة والإعادة حقيقي (المهارة وحدها محاكاة)."""
    async def real_skill(context):
        return {"marker": "REAL-COROUTINE"}

    engine = ExecutionEngine()
    engine._skill_logic = real_skill
    result = asyncio.run(engine.execute("cap", "skill", "provider", {"x": 1}))

    assert result.status.value == "completed"
    assert result.output == {"marker": "REAL-COROUTINE"}
    assert engine.get_completed_count() == 1
    assert engine.get_active_count() == 0


def test_kernel_engine_failure_retries_then_fails_with_count():
    """الفشل: إعادة المحاولة بعدّ حتمي (2 إعادة لمحاولات 3) ثم FAILED بالخطأ."""
    attempts = []

    async def failing_skill(context):
        attempts.append(1)
        raise ValueError("always-fails")

    engine = ExecutionEngine()
    engine._skill_logic = failing_skill
    retries = []
    engine.on_event(ExecutionEvent.RETRY,
                    lambda context, data: retries.append(data))
    engine.create_policy("t", max_retries=2, retry_delay_seconds=0)

    result = asyncio.run(engine.execute("cap", "skill", "prov", {}, policy_name="t"))

    assert result.status.value == "failed"
    assert result.error == "always-fails"
    assert len(attempts) == 3           # المحاولة الأولى + إعادتان
    assert len(retries) == 2           # حدثا RETRY
    assert engine.get_completed_count() == 1  # النتيجة المسجلة (فاشلة)


def test_kernel_engine_timeout_is_deterministic():
    """المهلة: كوروتين أبطأ من المهلة → FAILED بخطأ المهلة (سياسة حقيقية)."""
    async def slow_skill(context):
        await asyncio.sleep(1.0)
        return {}

    engine = ExecutionEngine()
    engine._skill_logic = slow_skill
    engine.create_policy("fast", timeout_seconds=0.05, max_retries=0,
                         retry_delay_seconds=0)

    result = asyncio.run(engine.execute("cap", "skill", "prov", {},
                                        policy_name="fast"))
    assert result.status.value == "failed"
    assert "timed out" in result.error


# ===============================================================
# 3) ParallelExecutor: التوصيف الدقيق للمزيف — func لا يُستدعى أبداً
# ===============================================================
def _counting_tasks():
    calls = []

    def work(tag):
        calls.append(tag)
        return f"done-{tag}"

    tasks = [
        ExecutionTask(id="t0", name="T0", func=work, args=("t0",)),
        ExecutionTask(id="t1", name="T1", func=work, args=("t1",),
                     dependencies=["t0"]),
        ExecutionTask(id="t2", name="T2", func=work, args=("t2",),
                     dependencies=["t1"]),
    ]
    return tasks, calls


def test_parallel_executor_invokes_originals_with_args_and_kwargs():
    """بعد التصحيح (ADR-0008): العمل يُستدعى فعلياً عبر النواة مرة لكل مهمة
    **أصلية** — args/kwargs تصلا، والنتيجة تُكتب على الأصلية نفسها. (السلوك
    القديم المزيف موثّق في سجل العمل: الدفعات كانت تعلّم نسخاً بلا func)."""
    calls = []

    def work(tag, *, kw=None):
        calls.append((tag, kw))
        return f"done-{tag}"

    tasks = [
        ExecutionTask(id="t0", name="T0", func=work, args=("t0",),
                      kwargs={"kw": "a"}),
        ExecutionTask(id="t1", name="T1", func=work, args=("t1",),
                      kwargs={"kw": "b"}, dependencies=["t0"]),
    ]
    results = ParallelExecutor(max_workers=5).execute(tasks)

    assert set(results) == {"t0", "t1"}
    assert all(s.value == "completed" for s in results.values())
    assert calls == [("t0", "a"), ("t1", "b")]      # args/kwargs وصلت
    by_id = {t.id: t for t in tasks}
    assert by_id["t0"].result == "done-t0"           # النتيجة على الأصلية
    assert by_id["t1"].result == "done-t1"
    assert by_id["t0"].completed_at is not None


def test_parallel_executor_cycle_detection_fails_all():
    """التحليل الحقيقي: دورة تبعيات → كل المهام FAILED (فرع الدورات يعمل)."""
    tasks = [
        ExecutionTask(id="a", name="A", func=None, dependencies=["b"]),
        ExecutionTask(id="b", name="B", func=None, dependencies=["a"]),
    ]
    results = ParallelExecutor().execute(tasks)
    assert set(results) == {"a", "b"}
    assert all(s.value == "failed" for s in results.values())


def test_parallel_executor_ghost_dependency_is_explicit_failure():
    """بعد التصحيح (ADR-0008): التبعية غير المتاحة فشل صريح مُعلن — لا صمت
    (القديم: نتائج فارغة والمهمة تظل PENDING بلا مخرج)."""
    tasks = [ExecutionTask(id="g", name="G", func=None, dependencies=["ghost"])]
    results = ParallelExecutor().execute(tasks)
    assert set(results) == {"g"}
    assert results["g"].value == "failed"
    assert "غير متاحة" in tasks[0].error


# ===============================================================
# 4) فصل الادعاءات: تنفيذ صوري / اكتمال ترجمة / قبول طابور
# ===============================================================
def test_fabric_execution_is_explicitly_not_executed():
    """بعد التصحيح (ADR-0008): عدم تنفيذ صريح مع السبب — لا «executed» ولا
    عدّ عقد (القديم الموثّق: executed + nodes_completed بلا أي عمل)."""
    fabric = ExecutionFabric()
    fabric.create_graph("g1")
    fabric.add_node("g1", ExecutionNode(node_id="n1", capability_id="c1"))
    out = fabric.execute("g1")
    assert out["status"] == "not_executed"
    assert out["graph_id"] == "g1"
    assert "ADR-0008" in out["reason"]


def test_agos_execution_fabric_is_explicitly_not_executed():
    """بعد التصحيح (ADR-0008): وحدة غير منفّذة مع السبب في الأدلة — لا «completed»
    صورية (القديم الموثّق: status=completed بلا أي عمل)."""
    unit = UniversalExecutionFabric().execute("m", "intent", ["g1"])
    assert unit.status == "not_executed"
    assert unit.pipeline_step == "Execution Units"
    assert any("ADR-0008" in e for e in unit.evidence)


def test_workflow_runtime_is_explicitly_not_executed():
    """بعد التصحيح (ADR-0008): عدم تنفيذ صريح والحالة لا تُمس — لا ادعاء
    اكتمال (القديم الموثّق: completed بعد «# Simulate execution» مع تغيير
    الحالة صورياً)."""
    from agos_kernel.civilization.workflow_runtime.workflow import WorkflowState
    runtime = WorkflowRuntime()
    workflow = runtime.create_workflow(
        "demo", [WorkflowStep(name="s1", step_type=StepType.TASK)])
    before = workflow.state
    out = runtime.execute_workflow(workflow.workflow_id)
    assert out == {"workflow_id": workflow.workflow_id, "status": "not_executed"}
    assert workflow.state is before  # الحالة لم تتغير


def test_compiler_completes_translation_not_execution():
    """اكتمال الترجمة ≠ اكتمال تنفيذ: المترجم يعيد ExecutableMission بحالة
    COMPLETED وثقة مثبتة 0.8 وعشر مراحل وبنية تنفيذ — بلا أي استدعاء عمل."""
    compiled = MissionCompiler().compile("intent-text")
    assert compiled.status is CompilerStatus.COMPLETED
    assert compiled.intent.confidence == 0.8  # مثبتة في النية لا مُشتقة
    assert len(compiled.phases) == 10
    assert compiled.execution_graph is not None
    assert compiled.metadata  # البيانات الوصفية تُملأ (توصيف الشكل)


def test_cloud_execution_acceptance_is_queued_not_completed():
    """قبول الوظيفة ≠ اكتمالها: الطابور السحابي يعيد queued صادقاً — لا ادعاء
    تنفيذ (scaffolding موثّق لا محرك)."""
    job = UniversalExecutionCloud().submit_job("m1", "Container")
    assert job.status == "queued"
    assert job.job_id == "job_m1"


def test_capability_executor_without_handler_fails_explicitly():
    """بعد التصحيح (ADR-0008): غياب الحامل فشل صريح — لا mock بـ«executed»
    (القديم الموثّق: نتيجة mock بـ«status: executed»)."""
    instance = CapabilityInstance(contract=_SimpleContract())
    context = CapabilityContext(mission_id="m1", capability_id="c1")
    result = CapabilityExecutor().execute(instance, context)

    assert result.success is False
    assert "handler" in result.error


def test_capability_executor_with_handler_routes_through_core():
    """الحامل الصالح يُستدعى عبر النواة المشتركة ونتيجته تعود صادقة (تكييف
    مؤقت: لا مواضع إسناد تثبت توقيع handler — الغياب هو المسار المثبت وحده)."""
    received = []

    def handler(context):
        received.append(context.capability_id)
        return {"ran": True}

    instance = CapabilityInstance(contract=_SimpleContract(), handler=handler)
    context = CapabilityContext(mission_id="m1", capability_id="c1")
    result = CapabilityExecutor().execute(instance, context)

    assert result.success is True
    assert result.outputs == {"ran": True}
    assert received == ["c1"]


@dataclass
class _SimpleContract:
    name: str = "FakeCap"
    version: str = "1.0"
    description: str = ""
    inputs: list = field(default_factory=list)
    outputs: list = field(default_factory=list)

    def to_dict(self):
        return {"name": self.name}


# ===============================================================
# ADR-0008 — النواة المشتركة: عقد invoke_sync والربط عبر الأنبوب
# ===============================================================
def test_invoke_sync_contract_falsy_values_are_successes():
    """النجاح خلوّ الخطأ لا صدق القيمة: None/False/0 نتائج مشروعة."""
    from agos_kernel.execution.engine import get_engine
    core = get_engine()
    for falsy in (None, False, 0, "", []):
        outcome = core.invoke_sync(lambda: falsy)
        assert outcome.ok is True
        assert outcome.error is None
        assert outcome.value == falsy


def test_invoke_sync_catches_exception_only():
    """أخطاء العمل العادية تُلتقط؛ استثناءات التحكم (KeyboardInterrupt) تمر كما هي."""
    from agos_kernel.execution.engine import get_engine
    core = get_engine()

    def broken():
        raise RuntimeError("work-error")

    outcome = core.invoke_sync(broken)
    assert outcome.ok is False
    assert isinstance(outcome.error, RuntimeError)

    def interrupted():
        raise KeyboardInterrupt()

    with pytest.raises(KeyboardInterrupt):
        core.invoke_sync(interrupted)


def test_invoke_sync_rejects_async_work_without_running_it():
    """الدوال غير المتزامنة والكوروتينات غير المنفّذة مرفوضة صراحةً دون تشغيل."""
    from agos_kernel.execution.engine import get_engine
    core = get_engine()
    ran = []

    async def coro_fn():
        ran.append(1)  # لا يجوز أن يعمل

    outcome = core.invoke_sync(coro_fn)
    assert outcome.ok is False
    assert isinstance(outcome.error, TypeError)
    assert ran == []

    def returns_coroutine():
        async def inner():
            ran.append(2)  # لا يجوز أن يعمل

        return inner()

    outcome = core.invoke_sync(returns_coroutine)
    assert outcome.ok is False
    assert isinstance(outcome.error, TypeError)
    assert ran == []


def test_invoke_sync_works_inside_running_event_loop():
    """الواجهة المتزامنة تعمل داخل حلقة أحداث قائمة — لا حلقة أخرى ولا جسر."""
    from agos_kernel.execution.engine import get_engine

    async def main():
        outcome = get_engine().invoke_sync(lambda: "sync-value")
        assert outcome.ok is True
        assert outcome.value == "sync-value"

    asyncio.run(main())


class _FakeCore:
    """نواة زائفة حتمية: تختبر عقد InvocationOutcome نفسه — لا رفع مباشراً."""

    def __init__(self):
        self.calls = []
        self.fail = False

    def invoke_sync(self, func, *args, **kwargs):
        self.calls.append((func, args, kwargs))
        if self.fail:
            return _InvocationOutcome(error=RuntimeError("core-failure"))
        return _InvocationOutcome(value={"marker": "CORE-ROUTED"})


class _GuardCapability:
    """حارس: أي استدعاء خارج النواة يفشل الاختبار."""

    def execute(self, parameters):
        raise AssertionError("القدرة استُدعيت خارج النواة (ADR-0008)")


def _pipeline_with_core(core, capability):
    return ExecutionPipeline(
        event_bus=EventBus(),
        capability_resolver=_FakeCapResolver(capability),
        provider_resolver=_FakeProvResolver(),
        execution_engine=core)


def test_pipeline_routes_invocation_through_core_marker_then_failure():
    """اختبار القبول المميّز (ADR-0008): النواة الزائفة تعيد علامة مميزة ثم تفشل
    بعقد InvocationOutcome نفسه — الأنبوب يتبع النتيجتين، والأدلة محفوظة، والقدرة
    لا تُستدعى خارج النواة (الحارس) ولا تُستدعى النواة إلا مرة."""
    core = _FakeCore()
    guard = _GuardCapability()
    mission = Mission(id="m9", name="nm", capability="Guard", parameters={"x": 1})
    pipeline = _pipeline_with_core(core, guard)

    # النجاح: العلامة المميزة من النواة تتبع، والقدرة (الحارس) لم تُستدع
    result = pipeline.execute(mission)
    assert result.status is ExecutionStatus.COMPLETED
    assert result.result == {"marker": "CORE-ROUTED"}
    assert result.decision_records == ["cap-record", "prov-record"]
    assert len(core.calls) == 1
    assert core.calls[0][0] == guard.execute     # الدالة نفسها
    assert core.calls[0][1] == ({"x": 1},)        # المعاملات الصحيحة
    assert core.calls[0][2] == {}                 # لا kwargs زائدة

    # الفشل: عقد النتيجة نفسه (error داخل المخرج لا رفع من النواة الزائفة)
    core.fail = True
    result = pipeline.execute(mission)
    assert result.status is ExecutionStatus.FAILED
    assert result.error == "core-failure"
    assert result.decision_records == ["cap-record", "prov-record"]
    assert len(core.calls) == 2  # استدعاء ثانٍ لعملية ثانية — لا تكرار ضمن الواحدة
    assert core.calls[1][0] == guard.execute     # الدالة نفسها في الفشل أيضاً
    assert core.calls[1][1] == ({"x": 1},)
    assert core.calls[1][2] == {}


def test_pipeline_default_binding_real_core_single_invocation():
    """الربط الافتراضي بالنواة الحقيقية: القدرة تُستدعى مرة واحدة، ونتيجتها تعود،
    وعند الفشال لا إعادة محاولة (سياسة الاستدعاء الواحد محفوظة)."""
    cap = _FakeCapability()
    _FakeCapability.calls = []
    mission = Mission(id="m10", name="nm", capability="FakeCap", parameters={"y": 2})
    pipeline = ExecutionPipeline(
        event_bus=EventBus(),
        capability_resolver=_FakeCapResolver(cap),
        provider_resolver=_FakeProvResolver())  # بلا حقن — الربط الافتراضي

    result = pipeline.execute(mission)
    assert result.status is ExecutionStatus.COMPLETED
    assert result.result == {"marker": "REAL-WORK"}
    assert _FakeCapability.calls == [{"y": 2}]  # مرة واحدة

    # الفشل: استدعاء واحد فقط — لا إعادة (invoke_sync بلا مهلة/إعادة)
    cap.fail = True
    _FakeCapability.calls = []
    result = pipeline.execute(mission)
    assert result.status is ExecutionStatus.FAILED
    assert result.error == "boom"
    assert _FakeCapability.calls == [{"y": 2}]  # مرة واحدة رغم الفشل — لا إعادة


# ===============================================================
# ADR-0008 — التوسعة: منفذ التوازي الصادق (الطريقتان) وعقد الإغلاق
# ===============================================================
def test_parallel_executor_dependent_not_run_after_ancestor_failure():
    """لا تعمل التابعة بعد فشل سابقتها: فشل t0 يمنع t1 وt2 — كلها FAILED
    بسبب معلوم، والعمل الأصلي لا يُستدعى للتابعات."""
    ran = []

    def work(tag):
        ran.append(tag)
        if tag == "t0":
            raise RuntimeError("t0-failure")
        return tag

    tasks = [
        ExecutionTask(id="t0", name="T0", func=work, args=("t0",)),
        ExecutionTask(id="t1", name="T1", func=work, args=("t1",),
                     dependencies=["t0"]),
        ExecutionTask(id="t2", name="T2", func=work, args=("t2",),
                     dependencies=["t1"]),
    ]
    results = ParallelExecutor().execute(tasks)

    assert ran == ["t0"]                       # التابعتان لم تُستدعيا
    assert set(results) == {"t0", "t1", "t2"}
    assert all(s.value == "failed" for s in results.values())
    by_id = {t.id: t for t in tasks}
    assert "t0-failure" in by_id["t0"].error
    assert "تبعية فاشلة" in by_id["t1"].error   # السبب معلوم ومصرّح


def test_parallel_executor_missing_func_is_explicit_failure():
    """غياب func فشل صريح لا نجاح (القديم الموثّق: COMPLETED بلا عمل)."""
    tasks = [ExecutionTask(id="nf", name="NF", func=None)]
    results = ParallelExecutor().execute(tasks)
    assert set(results) == {"nf"}
    assert results["nf"].value == "failed"
    assert "func" in tasks[0].error


def test_parallel_executor_pipeline_mode_is_honest():
    """وضع الأنبوب (execute_pipeline) صادق أيضاً: عمل حقيقي عبر النواة على
    الأصلية، والتبعية الفاشلة تمنع التابعة (القديم: إكمال بلا استدعاء)."""
    ran = []

    def work(tag):
        ran.append(tag)
        if tag == "a":
            raise RuntimeError("a-failure")
        return tag

    tasks = [
        ExecutionTask(id="a", name="A", func=work, args=("a",)),
        ExecutionTask(id="b", name="B", func=work, args=("b",),
                     dependencies=["a"]),
    ]
    results = ParallelExecutor().execute_pipeline(tasks)

    assert ran == ["a"]
    assert set(results) == {"a", "b"}
    assert all(s.value == "failed" for s in results.values())
    assert "a-failure" in tasks[0].error
    assert tasks[1].error is not None          # التابعة منعت صراحةً


def test_invoke_sync_close_error_stays_in_outcome_contract():
    """خطأ الإغلاق العادي يبقى داخل عقد المخرج — لا تسريب (المراجعة المانعة).
    awaitable ليس كوروتيناً لا يُغلق أصلاً (لا دلالة إغلاق موحدة) ويُرفض بوضوح؛
    والكوروتين الفعلي الذي يرفع إغلاقه يعيد الخطأ داخل المخرج لا استثناء مسرباً."""
    from agos_kernel.execution.engine import ExecutionEngine

    class AwaitableWithClose:
        def __await__(self):
            yield

        def close(self):
            raise RuntimeError("cleanup-failure")

    # مثال المراجعة: رفض بلا إغلاق اعتباطي — لا تسريب لاستثناء الإغلاق
    outcome = ExecutionEngine().invoke_sync(lambda: AwaitableWithClose())
    assert outcome.error is not None
    assert isinstance(outcome.error, TypeError)

    # الكوروتين الفعلي المعلق عند نقطة انتظار: إغلاقه يرفع GeneratorExit
    # فيرفع RuntimeError — والخطأ يبقى داخل عقد المخرج لا استثناء مسرباً
    async def stubborn():
        try:
            await asyncio.sleep(10)
        except GeneratorExit:
            raise RuntimeError("cleanup-failure")

    coro = stubborn()

    async def suspend():
        coro.send(None)  # يبدأ حتى أول انتظار فيعلق هناك

    asyncio.run(suspend())
    outcome = ExecutionEngine().invoke_sync(lambda: coro)
    assert outcome.error is not None
    assert isinstance(outcome.error, RuntimeError)
    assert outcome.error.args == ("cleanup-failure",)


def test_invoke_sync_non_coroutine_awaitable_rejected_without_close():
    """awaitable ليس كوروتيناً: يُرفض بوضوح دون إغلاق اعتباطي (لا دلالة إغلاق
    موحدة) ودون تشغيله."""
    from agos_kernel.execution.engine import ExecutionEngine

    class WeirdAwaitable:
        def __await__(self):
            yield

    outcome = ExecutionEngine().invoke_sync(lambda: WeirdAwaitable())
    assert outcome.error is not None
    assert isinstance(outcome.error, TypeError)


# ===============================================================
# مراجعة التوسعة — جاهزية إيجابية وإعادة استخدام وضبط حقول المحاولة
# ===============================================================
def test_pipeline_mode_dependent_before_ancestor_does_not_run():
    """وضع الأنبوب: تمرير التابعة قبل سابقتها — التحقق الإيجابي يمنع عملها
    قبل اكتمال تبعيتها في نطاق هذا الاستدعاء (حتى لو فشلت السابقة بعدها)."""
    ran = []

    def work(tag):
        ran.append(tag)
        if tag == "a":
            raise RuntimeError("a-failure")
        return tag

    b = ExecutionTask(id="b", name="B", func=work, args=("b",),
                     dependencies=["a"])
    a = ExecutionTask(id="a", name="A", func=work, args=("a",))
    results = ParallelExecutor().execute_pipeline([b, a])  # التابعة أولاً

    assert "b" not in ran                    # لم تعمل قبل سابقتها
    assert set(results) == {"a", "b"}
    assert results["a"].value == "failed"
    assert results["b"].value == "failed"
    assert "a-failure" in a.error
    assert b.error is not None               # منعت صراحةً


def test_executor_reuse_does_not_run_dependent_on_stale_log():
    """إعادة استخدام المنفذ: سابقة تفشل في استدعاء، ثم تُرسل تابعتها وحدها في
    الاستدعاء التالي — لا تعمل بصمت اعتماداً على سجل المجدول القديم."""
    ran = []

    def work(tag):
        ran.append(tag)
        if tag == "a":
            raise RuntimeError("a-failure")
        return tag

    executor = ParallelExecutor()
    a = ExecutionTask(id="a", name="A", func=work, args=("a",))
    first = executor.execute([a])
    assert first["a"].value == "failed"

    b = ExecutionTask(id="b", name="B", func=work, args=("b",),
                      dependencies=["a"])
    second = executor.execute([b])           # التابعة وحدها — استدعاء جديد

    assert ran == ["a"]                      # b لم تعمل
    assert set(second) == {"b"}
    assert second["b"].value == "failed"    # فشل صريح لا صمت
    assert "غير متاحة" in b.error


def test_task_reuse_success_then_failure_clears_stale_fields():
    """إعادة استخدام المهمة نفسها (نجاح ثم فشل): لا تبقى نتيجة ولا طابع إكمال
    من المحاولة السابقة على المهمة الأصلية."""
    fail_now = []
    outcomes = []

    def work():
        if fail_now:
            raise RuntimeError("late-failure")
        return "early-success"

    task = ExecutionTask(id="r", name="R", func=work)
    executor = ParallelExecutor()

    first = executor.execute([task])
    assert first["r"].value == "completed"
    assert task.result == "early-success"
    assert task.completed_at is not None

    fail_now.append(1)
    second = executor.execute([task])       # المهمة نفسها — محاولة جديدة
    assert second["r"].value == "failed"
    assert task.result is None               # لا نتيجة قديمة
    assert task.completed_at is None         # لا طابع إكمال قديم
    assert "late-failure" in task.error


def test_task_reuse_failure_then_success_clears_stale_error():
    """والعكس: فشل ثم نجاح — لا تبقى رسالة الخطأ القديمة مع النجاح الجديد."""
    succeed_now = []
    outcomes = []

    def work():
        if not succeed_now:
            raise RuntimeError("early-failure")
        return "late-success"

    task = ExecutionTask(id="r2", name="R2", func=work)
    executor = ParallelExecutor()

    first = executor.execute([task])
    assert first["r2"].value == "failed"
    assert "early-failure" in task.error

    succeed_now.append(1)
    second = executor.execute([task])
    assert second["r2"].value == "completed"
    assert task.error is None                # لا خطأ قديم مع النجاح
    assert task.result == "late-success"


class _RecordingCore:
    """نواة زائفة تسجل الدالة والمعاملات وتعيد مخرجاً حتمياً — لإثبات المرور
    بالنواة في كل واجهة (حارس يرفض أي استدعاء خارجها)."""

    def __init__(self, marker="CORE-MARKER"):
        self.calls = []
        self.marker = marker

    def invoke_sync(self, func, *args, **kwargs):
        self.calls.append((func, args, kwargs))
        return _InvocationOutcome(value={"marker": self.marker})


def test_parallel_executor_routes_through_core_with_identity():
    """إثبات مميّز (execute): العمل لا يُستدعى إلا عبر النواة — الدالة نفسها
    وargs/kwargs تصلان للنواة، والنتيجة تعود للأصلية."""
    core = _RecordingCore()

    def guard(tag, *, kw=None):
        raise AssertionError("استُدعي العمل خارج النواة")

    task = ExecutionTask(id="c1", name="C1", func=guard, args=("x",),
                         kwargs={"kw": "y"})
    import agos_kernel.execution.engine as engine_mod
    saved = engine_mod.get_engine
    engine_mod.get_engine = lambda: core
    try:
        results = ParallelExecutor().execute([task])
    finally:
        engine_mod.get_engine = saved

    assert results["c1"].value == "completed"
    assert len(core.calls) == 1
    assert core.calls[0][0] is guard
    assert core.calls[0][1] == ("x",)
    assert core.calls[0][2] == {"kw": "y"}
    assert task.result == {"marker": "CORE-MARKER"}


def test_parallel_executor_pipeline_routes_through_core():
    """إثبات مميّز (execute_pipeline): المرور بالنواة نفسه — الدالة والمعاملات."""
    core = _RecordingCore()

    def guard(tag):
        raise AssertionError("استُدعي العمل خارج النواة")

    task = ExecutionTask(id="c2", name="C2", func=guard, args=("z",),
                         kwargs={"k": "v"})
    import agos_kernel.execution.engine as engine_mod
    saved = engine_mod.get_engine
    engine_mod.get_engine = lambda: core
    try:
        results = ParallelExecutor().execute_pipeline([task])
    finally:
        engine_mod.get_engine = saved

    assert results["c2"].value == "completed"
    assert len(core.calls) == 1
    func, args, kwargs = core.calls[0]
    assert func is guard
    assert args == ("z",)
    assert kwargs == {"k": "v"}            # الاسمية تصل كما هي لا تُسقط
    assert task.result == {"marker": "CORE-MARKER"}


def test_capability_executor_routes_through_core_distinctively():
    """إثبات مميّز (CapabilityExecutor): الحارس لا يُستدعى إلا عبر النواة —
    الدالة (handler) والسياق يصلان، والنتيجة تعود عبر عقد المخرج."""
    from agos_kernel.civilization.capability_runtime.runtime import (
        CapabilityExecutor as CapExec, CapabilityInstance as CapInst)

    core = _RecordingCore()

    def guard_handler(context):
        raise AssertionError("استُدعي الحامل خارج النواة")

    instance = CapInst(contract=_SimpleContract(), handler=guard_handler)
    context = CapabilityContext(mission_id="m1", capability_id="c1")

    original_init = CapExec.__init__
    executor = CapExec()
    # حقن النواة: المنفذ يستخدم get_engine — نستبدله مؤقتاً بالنواة الزائفة
    import agos_kernel.civilization.capability_runtime.runtime as cap_mod
    import agos_kernel.execution.engine as engine_mod
    saved = engine_mod.get_engine
    engine_mod.get_engine = lambda: core
    try:
        # get_engine مُستورد داخل الدالة — يُستدعى من وحدة المحرك مباشرة
        result = executor.execute(instance, context)
    finally:
        engine_mod.get_engine = saved

    assert result.success is True
    assert result.outputs == {"marker": "CORE-MARKER"}
    func, args, kwargs = core.calls[0]
    assert func is guard_handler
    assert len(args) == 1
    assert args[0] is context            # هوية السياق نفسه لا مساواته
    assert kwargs == {}


# ===============================================================
# مراجعة إعادة الضبط الموحد + عقد الفشل عبر النواة في كل واجهة
# ===============================================================
def test_success_then_cycle_clears_all_attempt_fields():
    """نجاح حقيقي ثم دورة تبعيات: الفشل الجديد لا يرث شيئاً من المحاولة
    السابقة — لا نتيجة ولا طوابع بدء/إكمال، والإحصاءات تعكس المحاولة الأخيرة."""
    task = ExecutionTask(id="cy", name="CY",
                        func=lambda: "success-once")
    executor = ParallelExecutor()

    first = executor.execute([task])
    assert first["cy"].value == "completed"
    assert task.result == "success-once"
    assert task.completed_at is not None

    task.dependencies = [task.id]           # دورة تبعيات — رفض مبكر
    second = executor.execute([task])

    assert second["cy"].value == "failed"
    assert task.status.value == "failed"
    assert task.result is None
    assert task.started_at is None
    assert task.completed_at is None
    assert "دورة" in task.error
    scheduled = executor.scheduler.tasks[task.id]   # النسخة نفسها لا العدادات فقط
    assert scheduled.status is task.status
    assert scheduled.result is None
    assert scheduled.error == task.error
    assert scheduled.started_at is None
    assert scheduled.completed_at is None
    stats = executor.get_stats()
    assert stats["completed_tasks"] == 0    # لا نجاح قديم في الإحصاءات
    assert stats["failed_tasks"] == 1


def test_success_then_missing_func_clears_all_attempt_fields():
    """نجاح ثم غياب func (إعادة استخدام المهمة): فشل صريح بلا بقايا."""
    task = ExecutionTask(id="mf", name="MF", func=lambda: "ok-once")
    executor = ParallelExecutor()

    first = executor.execute([task])
    assert first["mf"].value == "completed"

    task.func = None
    second = executor.execute([task])

    assert second["mf"].value == "failed"
    assert task.result is None
    assert task.started_at is None
    assert task.completed_at is None
    assert "func" in task.error
    scheduled = executor.scheduler.tasks[task.id]
    assert scheduled.status is task.status
    assert scheduled.result is None
    assert scheduled.error == task.error
    assert scheduled.started_at is None
    assert scheduled.completed_at is None
    assert executor.get_stats()["failed_tasks"] == 1


def test_execute_success_then_execute_pipeline_failure_same_task():
    """execute ناجحاً ثم execute_pipeline فاشلاً للمهمة نفسها: الأصل ونسخة
    المجدول معاً يعكسان المحاولة الأخيرة (لا نجاح قديم في الإحصاءات)."""
    task = ExecutionTask(id="mix", name="MIX", func=None)
    task.func = lambda: "ok-via-execute"
    executor = ParallelExecutor()

    first = executor.execute([task])
    assert first["mix"].value == "completed"
    assert executor.get_stats()["completed_tasks"] == 1

    # المحاولة الجديدة عبر الطريقة الأخرى — فاشلة (تبعية غير متاحة)
    task.func = None
    task.dependencies = ["ghost"]
    second = executor.execute_pipeline([task])

    assert second["mix"].value == "failed"
    assert task.result is None
    assert task.started_at is None
    assert task.completed_at is None
    scheduled = executor.scheduler.tasks[task.id]   # النسخة تابعة للمحاولة الأخيرة
    assert scheduled.status is task.status
    assert scheduled.result is None
    assert scheduled.error == task.error
    assert scheduled.started_at is None
    assert scheduled.completed_at is None
    stats = executor.get_stats()
    assert stats["completed_tasks"] == 0
    assert stats["failed_tasks"] == 1


class _FailingCore:
    """نواة زائفة تختبر عقد الفشل نفسه: InvocationOutcome(error=...) — الحارس
    لا يُستدعى، والخطأ يُترجم فشلاً على المخرج/المهمة الأصلية."""

    def __init__(self):
        self.calls = []

    def invoke_sync(self, func, *args, **kwargs):
        self.calls.append((func, args, kwargs))
        return _InvocationOutcome(error=RuntimeError("core-failure"))


def test_parallel_execute_failure_contract_through_fake_core():
    """عقد الفشل عبر execute: الحارس لا يُستدعى، النواة استُدعيت مرة بالدالة
    والمعاملات الصحيحة، والخطأ ترجم فشلاً على المهمة الأصلية."""
    core = _FailingCore()

    def guard(tag):
        raise AssertionError("استُدعي العمل خارج النواة")

    task = ExecutionTask(id="fc1", name="FC1", func=guard, args=("p",),
                         kwargs={"k": "v"})
    import agos_kernel.execution.engine as engine_mod
    saved = engine_mod.get_engine
    engine_mod.get_engine = lambda: core
    try:
        results = ParallelExecutor().execute([task])
    finally:
        engine_mod.get_engine = saved

    assert results["fc1"].value == "failed"
    assert "core-failure" in task.error
    assert len(core.calls) == 1
    assert core.calls[0][0] is guard
    assert core.calls[0][1] == ("p",)
    assert core.calls[0][2] == {"k": "v"}


def test_parallel_pipeline_failure_contract_through_fake_core():
    """عقد الفشل عبر execute_pipeline: نفس الإثبات — الحارس لا يُستدعى والخطأ
    يصل المهمة الأصلية."""
    core = _FailingCore()

    def guard(tag):
        raise AssertionError("استُدعي العمل خارج النواة")

    task = ExecutionTask(id="fc2", name="FC2", func=guard, args=("q",),
                         kwargs={"k": "v"})
    import agos_kernel.execution.engine as engine_mod
    saved = engine_mod.get_engine
    engine_mod.get_engine = lambda: core
    try:
        results = ParallelExecutor().execute_pipeline([task])
    finally:
        engine_mod.get_engine = saved

    assert results["fc2"].value == "failed"
    assert "core-failure" in task.error
    assert len(core.calls) == 1
    func, args, kwargs = core.calls[0]
    assert func is guard
    assert args == ("q",)
    assert kwargs == {"k": "v"}           # الاسمية تصل كما هي حتى في الفشل


def test_capability_executor_failure_contract_through_fake_core():
    """عقد الفشل عبر CapabilityExecutor: الحارس (الحامل) لا يُستدعى، النواة
    استُدعيت بهوية الحامل والسياق **نفسه**، والخطأ ترجم فشلاً صريحاً."""
    from agos_kernel.civilization.capability_runtime.runtime import (
        CapabilityExecutor as CapExec, CapabilityInstance as CapInst)

    core = _FailingCore()

    def guard_handler(context):
        raise AssertionError("استُدعي الحامل خارج النواة")

    instance = CapInst(contract=_SimpleContract(), handler=guard_handler)
    context = CapabilityContext(mission_id="m1", capability_id="c1")

    import agos_kernel.execution.engine as engine_mod
    saved = engine_mod.get_engine
    engine_mod.get_engine = lambda: core
    try:
        result = CapExec().execute(instance, context)
    finally:
        engine_mod.get_engine = saved

    assert result.success is False
    assert "core-failure" in result.error
    func, args, kwargs = core.calls[0]
    assert func is guard_handler
    assert len(args) == 1
    assert args[0] is context            # هوية السياق نفسه لا مساواته
    assert kwargs == {}
