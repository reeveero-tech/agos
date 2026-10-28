# -*- coding: utf-8 -*-
"""الشريحة 33 (سجل العمل 0107) — المادة 14: استقلال نقاط التحقق.

عقد نقطة التحقق القائم: «Create a checkpoint» و«Pause an execution» —
النقطة تحفظ اللحظة، والاستعادة تعيد قيمها. العيب المثبت بالأحمر:
اللقطة كانت نسخة سطحية تشارك الكائنات المتداخلة مع السياق الحي،
والاستعادة كانت تربط السياق بكائنات النقطة المخزنة نفسها — فتعديل
العمل الجاري بعد الالتقاط يلوث النقطة، وتعديل السياق بعد الاستعادة
يفسد النقطة نفسها (نفس صنف عيب لقطة الإعادة — سجل العمل 0106).

حدود معلنة (أدلة رصدية لا متطلبات أُنجزت): «pause» يلتقط نقطة ويصدر
أحداثاً ولا يعلّق العمل (العمل يكتمل بعده)؛ و«resume» يستعيد بيانات
السياق لا موضع coroutine؛ و«rollback» يصدر حدثاً ولا يعكس آثاراً —
التعليق/الاستئناف/العكس الفعلي آليات غير متوفرة في هذا المسار
(Recoverable مفتوحة).
"""
import asyncio

import pytest

from agos.agos_kernel.execution.engine import (
    ExecutionEngine,
    ExecutionEvent,
    ExecutionStatus,
)


class _UnDeepcopyable:
    """كائن يرفض النسخ العميق — لإثبات صراحة فشل اللقطة."""

    def __deepcopy__(self, memo):
        raise RuntimeError("deepcopy is not supported here")


def _make_engine(skill):
    engine = ExecutionEngine()
    engine._skill_logic = skill
    engine.create_policy("t", max_retries=0, retry_delay_seconds=0)
    return engine


def test_checkpoint_captures_independent_state_and_parameters():
    """نقطة التحقق تحفظ اللحظة: تعديل السياق الحي بعد الالتقاط لا
    يلوث قيم النقطة المخزنة (معاملات وحالة متداخلة)."""

    async def main():
        started, release, mutated, finish = (
            asyncio.Event(), asyncio.Event(), asyncio.Event(), asyncio.Event())

        async def skill(context):
            started.set()
            await release.wait()
            context.parameters["nested"]["x"] = 999
            context.state["nested"]["y"] = 999
            mutated.set()
            await finish.wait()
            return {"ok": True}

        shared = {"v": 1}
        engine = _make_engine(skill)
        task = asyncio.ensure_future(engine.execute(
            "cap", "skill", "prov",
            {"nested": {"x": 1}, "shared_ref": shared}, policy_name="t"))
        await started.wait()

        eid = next(iter(engine.active_executions))
        context = engine.active_executions[eid]
        context.state["nested"] = {"y": 2}
        context.state["shared_ref"] = shared
        cp = engine.checkpoint(eid)
        assert cp is not None

        release.set()
        await mutated.wait()
        # النقطة تحفظ قيم اللحظة لا قيم ما بعد التعديل — للحقلين
        assert cp["parameters"]["nested"]["x"] == 1
        assert cp["state"]["nested"]["y"] == 2
        # العلاقة المشتركة محفوظة داخل اللقطة ومستقلة عن المصدر الحي
        assert cp["parameters"]["shared_ref"] is cp["state"]["shared_ref"]
        assert cp["parameters"]["shared_ref"] is not shared

        finish.set()
        result = await task
        assert result.status == ExecutionStatus.COMPLETED

    asyncio.run(main())


def test_pause_checkpoint_independent_of_live_mutation():
    """pause يلتقط نقطة مستقلة: استمرار العمل وتعديله للمعاملات
    المتداخلة لا يلوث النقطة المخزنة (حد معلن: لا تعليق للعمل)."""

    async def main():
        started, release, mutated, finish = (
            asyncio.Event(), asyncio.Event(), asyncio.Event(), asyncio.Event())

        async def skill(context):
            started.set()
            await release.wait()
            context.parameters["nested"]["x"] = 999
            context.state["nested"]["y"] = 999
            mutated.set()
            await finish.wait()
            return {"ok": True}

        engine = _make_engine(skill)
        task = asyncio.ensure_future(engine.execute(
            "cap", "skill", "prov",
            {"nested": {"x": 1}}, policy_name="t"))
        await started.wait()

        eid = next(iter(engine.active_executions))
        context = engine.active_executions[eid]
        context.state["nested"] = {"y": 2}
        assert engine.pause(eid) is True

        release.set()
        await mutated.wait()
        stored = context.checkpoints[-1]
        assert stored["parameters"]["nested"]["x"] == 1
        assert stored["state"]["nested"]["y"] == 2

        # دليل رصدي للحد المعلن: العمل يكتمل بعد «الإيقاف المؤقت»
        finish.set()
        result = await task
        assert result.status == ExecutionStatus.COMPLETED

    asyncio.run(main())


def test_resume_restores_independent_copies_repeatedly():
    """الاستعادة تمنح نسخاً مستقلة: النقطة نفسها تظل قابلة
    للاستعادة مراراً رغم تعديل السياق بعد كل استعادة."""

    async def main():
        started, release, mutated, finish = (
            asyncio.Event(), asyncio.Event(), asyncio.Event(), asyncio.Event())

        async def skill(context):
            started.set()
            await release.wait()
            context.parameters["nested"]["x"] = 999
            context.state["nested"]["y"] = 999
            mutated.set()
            await finish.wait()
            return {"ok": True}

        shared = {"v": 1}
        engine = _make_engine(skill)
        task = asyncio.ensure_future(engine.execute(
            "cap", "skill", "prov",
            {"nested": {"x": 1}, "shared_ref": shared}, policy_name="t"))
        await started.wait()

        eid = next(iter(engine.active_executions))
        context = engine.active_executions[eid]
        context.state["nested"] = {"y": 2}
        context.state["shared_ref"] = shared
        assert engine.pause(eid) is True

        release.set()
        await mutated.wait()
        assert engine.resume(eid) is True
        assert context.parameters["nested"]["x"] == 1
        assert context.state["nested"]["y"] == 2

        # العلاقة المشتركة محفوظة داخل السياق المستعاد ومستقلة عن
        # النقطة المخزنة (فلا تفسدها التعديلات اللاحقة)
        assert context.parameters["shared_ref"] is context.state["shared_ref"]
        stored = context.checkpoints[-1]
        assert context.parameters["shared_ref"] is not stored["parameters"]["shared_ref"]

        # تعديل السياق المستعاد لا يفسد النقطة المخزنة — في الحقلين
        context.parameters["nested"]["x"] = 555
        context.state["nested"]["y"] = 555
        assert engine.resume(eid) is True
        assert context.parameters["nested"]["x"] == 1
        assert context.state["nested"]["y"] == 2

        finish.set()
        result = await task
        assert result.status == ExecutionStatus.COMPLETED

    asyncio.run(main())


def test_checkpoint_copy_failure_is_explicit():
    """فشل النسخ صريح: لا نقطة تُنشأ ولا أحداث نجاح تُصدر — هنا
    اللقطة جوهر العملية لا ميزة اختيارية."""

    async def main():
        started, release, finish = (
            asyncio.Event(), asyncio.Event(), asyncio.Event())

        async def skill(context):
            started.set()
            await release.wait()
            return {"ok": True}

        engine = _make_engine(skill)
        task = asyncio.ensure_future(engine.execute(
            "cap", "skill", "prov",
            {"bad": _UnDeepcopyable()}, policy_name="t"))
        await started.wait()

        eid = next(iter(engine.active_executions))
        context = engine.active_executions[eid]
        emitted = []
        engine.on_event(
            ExecutionEvent.CHECKPOINT, lambda c, d: emitted.append("checkpoint"))
        engine.on_event(
            ExecutionEvent.PAUSED, lambda c, d: emitted.append("paused"))

        with pytest.raises(RuntimeError):
            engine.checkpoint(eid)
        assert context.checkpoints == []
        with pytest.raises(RuntimeError):
            engine.pause(eid)
        assert context.checkpoints == []
        assert emitted == []

        release.set()
        finish.set()
        result = await task
        assert result.status == ExecutionStatus.COMPLETED

    asyncio.run(main())


def test_resume_copy_failure_leaves_context_unchanged():
    """فشل نسخ الاستعادة يترك السياق كاملاً دون تغيير — لا استعادة
    نصفية (النسختان تُجهَّزان قبل تعديل أي حقل)."""

    async def main():
        started, release, finish = (
            asyncio.Event(), asyncio.Event(), asyncio.Event())

        async def skill(context):
            started.set()
            await release.wait()
            return {"ok": True}

        engine = _make_engine(skill)
        task = asyncio.ensure_future(engine.execute(
            "cap", "skill", "prov", {"x": 1}, policy_name="t"))
        await started.wait()

        eid = next(iter(engine.active_executions))
        context = engine.active_executions[eid]
        context.state["k"] = "original"
        state_before = context.state
        params_before = context.parameters
        context.checkpoints.append({
            "execution_id": eid,
            "state": {"k": _UnDeepcopyable()},
            "parameters": {"x": 1},
            "timestamp": "2026-01-01T00:00:00",
        })

        with pytest.raises(RuntimeError):
            engine.resume(eid)
        # لا استعادة نصفية: الحقلان كما كانا (الهوية نفسها)
        assert context.state is state_before
        assert context.parameters is params_before

        release.set()
        finish.set()
        result = await task
        assert result.status == ExecutionStatus.COMPLETED

    asyncio.run(main())


def test_resume_failure_in_parameters_leaves_both_fields_unchanged():
    """الرافض داخل المعاملات والحالة قابلة للنسخ مختلفة عن الحية:
    تنفيذ خاطئ ينسخ الحالة ويسندها ثم يفشل في المعاملات يترك أثراً —
    هنا يُكشف: الاستثناء ينتشر والحقلان بهويتهما وقيمتيهما ولا
    RESUMED يصدر."""

    async def main():
        started, release, finish = (
            asyncio.Event(), asyncio.Event(), asyncio.Event())

        async def skill(context):
            started.set()
            await release.wait()
            return {"ok": True}

        engine = _make_engine(skill)
        task = asyncio.ensure_future(engine.execute(
            "cap", "skill", "prov", {"x": 1}, policy_name="t"))
        await started.wait()

        eid = next(iter(engine.active_executions))
        context = engine.active_executions[eid]
        context.state["k"] = "live"
        state_before = context.state
        params_before = context.parameters
        context.checkpoints.append({
            "execution_id": eid,
            "state": {"k": "checkpoint"},          # قابلة للنسخ ومختلفة
            "parameters": {"x": _UnDeepcopyable()},  # الرافض هنا
            "timestamp": "2026-01-01T00:00:00",
        })
        emitted = []
        engine.on_event(
            ExecutionEvent.RESUMED, lambda c, d: emitted.append("resumed"))

        with pytest.raises(RuntimeError):
            engine.resume(eid)
        # لا استعادة نصفية: الحقلان كما كانا — الهوية والقيمة
        assert context.state is state_before
        assert context.parameters is params_before
        assert context.state["k"] == "live"
        assert context.parameters == {"x": 1}
        assert emitted == []

        release.set()
        finish.set()
        result = await task
        assert result.status == ExecutionStatus.COMPLETED

    asyncio.run(main())
