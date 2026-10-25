"""أدلة تشغيلي — تشخيص فشل مستمعي أحداث المحرك (الشريحة 0101).

منهج المشروع: أحمر أولاً ثم أدنى إصلاح.

النقص المعلن المشترك في صفّي المادتين 6 و14 من خريطة أدلة ADR-0010:
«ابتلاع `_emit_event` (محرك التنفيذ) استثناءات المستمعين بصمت نقص تشخيص
مفتوح». العزل نفسه مقصود وسليم (المستمع الفاشل لا يكسر التنفيذ ولا يغير
دلالة الإلغاء) — **الصمت** هو المخالفة: فشل مستمع لا يترك أي أثر (المادة 6:
تشخيص لكل فشل).

الإصلاح الأدنى: أثر مسمى في قناة التشخيص القياسية (مسجل الوحدة — نفس
قناة `providers/implementation.py`) يحمل التنفيذ والحدث وهوية المستمع
(اسماً مستقراً لا عنوان ذاكرة) والاستثناء بتتبعه — دون تغيير دلالات
العزل أو الإلغاء، ودون إصدار عبر `_emit_event` نفسه (لا عودية).

الحد المعلن: استثناءات مستمعي أحداث **هذا المحرك** لم تعد تُبتلع بصمت في
المسارات المختبرة — لا يعني ذلك اتصالاً بمجرى أحداث خارجي ولا سجلاً
دائماً ولا اكتمال Observable؛ الصفان 6 و14 يبقيان جزئيين.
"""
import asyncio
import logging
import sys
from pathlib import Path

_HERE = Path(__file__).resolve()
_KERNEL = _HERE.parent.parent / "agos" / "agos-kernel"
if str(_KERNEL) not in sys.path:
    sys.path.insert(0, str(_KERNEL))

import pytest  # noqa: E402

import agos_kernel.execution.engine as _engine_module  # noqa: E402
from agos_kernel.execution.engine import (  # noqa: E402
    ExecutionEngine, ExecutionEvent,
)

# اسم قناة التشخيص كما هو في الوحدة فعلاً (بلا افتراض اسم الاستيراد —
# آلية الاسم المستعار تعيد تسمية الحزمة)؛ ودفاعي ضد نسخة بلا مسجل بعد —
# الأحمر حينها سلوكي (غياب السجل المتوقع) لا خطأ سمة
_module_logger = getattr(_engine_module, "logger", None)
ENGINE_LOGGER = (_module_logger.name if _module_logger is not None
                 else _engine_module.__name__)


def _listener_name(handler):
    return getattr(handler, "__qualname__", None) or type(handler).__qualname__


def _diagnosis_records(caplog):
    return [r for r in caplog.records
            if r.name == ENGINE_LOGGER and r.levelno == logging.ERROR]


def _assert_one_diagnosis(caplog, execution_id, event, listener, message):
    """توكيد سجل واحد مسمى: التنفيذ والحدث وهوية المستمع والسبب — لا
    مجرد وجود نص عام."""
    records = _diagnosis_records(caplog)
    assert len(records) == 1, (
        f"عدد سجلات التشخيص {len(records)} — المتوقع سجل واحد")
    record = records[0]
    msg = record.getMessage()
    # مطابقة الحقول نفسها — لا كلمة سابحة قد تظهر في سبب الاستثناء أو
    # اسم الاختبار فتنجح للسبب الخطأ
    assert f"execution_id={execution_id}" in msg, msg
    assert f"event={event.name}" in msg, msg
    assert f"listener={_listener_name(listener)}" in msg, msg
    assert f"error=ValueError: {message}" in msg, msg
    assert record.exc_info is not None, "بلا استثناء مرفق بالتتبع"
    assert record.exc_info[0] is ValueError, record.exc_info[0]


def test_listener_failure_diagnosis_instrument_control(caplog):
    """ضابط إيجابي للأداة: الراصد يلتقط قناة التشخيص المختارة (مسجل وحدة
    المحرك بمستوى ERROR) — بلا هذا الضابط قد يكون «غياب السجل» عجزاً في
    الراصد لا في السلوك."""
    caplog.set_level(logging.ERROR, logger=ENGINE_LOGGER)
    logging.getLogger(ENGINE_LOGGER).error("probe-instrument")
    assert any("probe-instrument" in r.getMessage() for r in caplog.records)


def test_failing_listener_diagnosed_execution_completes(caplog):
    """الأحمر أولاً (غياب السجل المتوقع لا غياب سمة): مستمع STARTED يفشل
    ثم مستمع سليم بعده — التنفيذ الحقيقي يكتمل بمخرجه المتوقع والمستمع
    اللاحق يعمل، ويعقب الفشل سجل تشخيصي واحد مسمى (التنفيذ والحدث وهوية
    المستمع والسبب بتتبعه) لا صمت."""
    caplog.set_level(logging.ERROR, logger=ENGINE_LOGGER)

    async def ok_skill(context):
        return {"marker": "REAL-WORK"}

    def failing_listener(context, data):
        raise ValueError("listener-boom-started")

    healthy = []

    def healthy_listener(context, data):
        healthy.append(context.execution_id)

    engine = ExecutionEngine()
    engine._skill_logic = ok_skill
    engine.on_event(ExecutionEvent.STARTED, failing_listener)
    engine.on_event(ExecutionEvent.STARTED, healthy_listener)

    result = asyncio.run(engine.execute("cap", "skill", "prov", {}))

    assert result.status.value == "completed", result.error
    assert result.output == {"marker": "REAL-WORK"}
    assert healthy == [result.execution_id], "المستمع اللاحق لم يعمل"
    _assert_one_diagnosis(caplog, result.execution_id, ExecutionEvent.STARTED,
                          failing_listener, "listener-boom-started")


def test_failing_completed_listener_keeps_success_diagnosed(caplog):
    """فشل مستمع عند اكتمال التنفيذ: النجاح لا يتحول إلى فشل بسببه،
    والاستثناء لا يُبتلع — سجل تشخيصي واحد مسمى."""
    caplog.set_level(logging.ERROR, logger=ENGINE_LOGGER)

    async def ok_skill(context):
        return {"done": True}

    def failing_listener(context, data):
        raise ValueError("listener-boom-completed")

    engine = ExecutionEngine()
    engine._skill_logic = ok_skill
    engine.on_event(ExecutionEvent.COMPLETED, failing_listener)

    result = asyncio.run(engine.execute("cap", "skill", "prov", {}))

    assert result.status.value == "completed", result.error
    assert result.output == {"done": True}
    _assert_one_diagnosis(caplog, result.execution_id, ExecutionEvent.COMPLETED,
                          failing_listener, "listener-boom-completed")


def test_failing_failed_listener_keeps_original_cause(caplog):
    """فشل المهارة نفسها مع فشل مستمع FAILED: النتيجة تحمل سبب فشل المهارة
    الأصلي كما هو، واستثناء المستمع يظهر تشخيصاً منفصلاً — لا بديلاً عنه."""
    caplog.set_level(logging.ERROR, logger=ENGINE_LOGGER)

    async def failing_skill(context):
        raise ValueError("skill-always-fails")

    def failing_listener(context, data):
        raise ValueError("listener-boom-failed")

    engine = ExecutionEngine()
    engine._skill_logic = failing_skill
    engine.on_event(ExecutionEvent.FAILED, failing_listener)

    result = asyncio.run(engine.execute("cap", "skill", "prov", {}))

    assert result.status.value == "failed"
    assert result.error == "skill-always-fails", (
        "سبب فشل المهارة الأصلي استُبدل أو ضاع")
    _assert_one_diagnosis(caplog, result.execution_id, ExecutionEvent.FAILED,
                          failing_listener, "listener-boom-failed")


def test_cancel_with_failing_listener_still_cancels(caplog):
    """إلغاء حي مع مستمع CANCELLED يفشل: دلالة الإلغاء محفوظة (العمل يتوقف
    فعلاً عند نقطة الانتظار — الأثر الثاني لا يُنتج — ونتيجة إلغاء صريحة)
    وفشل المستمع يُشخَّص لا يُبتلع — بمزامنة إشارة دخول المهارة نفسها لا
    اقتراصاً زمنياً."""
    caplog.set_level(logging.ERROR, logger=ENGINE_LOGGER)

    async def working_skill(context):
        effects.append("effect-1")          # أثر قبل الانتظار
        entered.set()                        # وصلت نقطة الانتظار فعلياً
        await release.wait()                 # انتظار إشارة — لا زمن تخميني
        effects.append("effect-2")           # أثر بعد الانتظار — لا يُنتج
        return {"done": True}

    def failing_cancel_listener(context, data):
        raise ValueError("listener-boom-cancelled")

    engine = ExecutionEngine()
    effects, entered, release = [], asyncio.Event(), asyncio.Event()
    cancelled_ids = []
    engine._skill_logic = working_skill
    engine.on_event(ExecutionEvent.CANCELLED, failing_cancel_listener)
    engine.on_event(ExecutionEvent.CANCELLED,
                    lambda ctx, d: cancelled_ids.append(ctx.execution_id))

    # المزامنة عبر مستمع STARTED صحيح يسجل المعرف — والاختبار ينتظره
    started_ids = []
    engine.on_event(ExecutionEvent.STARTED,
                    lambda ctx, d: started_ids.append(ctx.execution_id))

    async def scenario():
        task = asyncio.create_task(engine.execute("cap", "skill", "prov", {}))
        await entered.wait()
        exec_id = started_ids[0]
        accepted = engine.cancel(exec_id)
        release.set()
        result = await task
        return exec_id, accepted, result

    exec_id, accepted, result = asyncio.run(scenario())
    assert accepted is True
    assert effects == ["effect-1"], "الأثر الثاني أُنتج — الإلغاء لم يتوقف"
    assert result.status.value == "cancelled"
    assert result.execution_id == exec_id
    assert cancelled_ids == [exec_id], "حدث الإلغاء ضاع بمستمع فاشل قبله"
    _assert_one_diagnosis(caplog, exec_id, ExecutionEvent.CANCELLED,
                          failing_cancel_listener, "listener-boom-cancelled")
