"""المادة 14 — Replayable: عقد «إعادة تشغيل بنفس المعاملات» (الشريحة 32 /
سجل العمل 0106).

الأحمر أولاً: ``ExecutionEngine.replay`` عقدُه الموثق في الكود نفسه
«إعادة تشغيل بنفس المعاملات» («Re-run with same parameters») — لكن
التنفيذ الحالي يعيد النتيجة المخزنة بلا أي تنفيذ، والتعليق في الكود
يقر بذلك صراحة («In production, would re-execute»): ادعاء تنفيذ وهمي
مخالف لعقد الطريقة القائم ولوجوب Replayable (المادة 14) — النمط نفسه
الذي أصلحه سجل العمل 0082 للإلغاء (إدارة سجل فقط والعمل لا يوقف).

الإصلاح الأدنى: عند اكتمال المسار تُخزَّن معاملات الإعادة مع النتيجة
(لقطة عميقة — نمط سجل العمل 0081: تعديل المعاملات لاحقاً لا يغيّر
الإعادة)، ثم ``replay`` يعيد التنفيذ فعلياً عبر ``execute`` نفسها
بتنفيذ جديد ومعرّف جديد — والنتيجة الأصلية المخزنة تبقى مستقلة،
والمجهول يبقى ``ValueError`` كما كان (لا مستدعي قائماً للتوقيع القديم
في الشجرة كلها — حُصر بالفحص).

حد معلن: الإعادة على هذا المسار (``execute`` غير المتزامن) — الإلغاء
(Cancelable) مغطى سابقاً بستة اختبارات حية؛ وIdempotent وRecoverable
وObservable في هذا المسار بمتبقياتها المعلنة في خريطة أدلة ADR-0010.
"""
import asyncio
import inspect

import pytest

from agos_kernel.execution.engine import ExecutionEngine, ExecutionEvent


def _run(engine, execution_id):
    """تكيّف مرحلة الأحمر: قبل الإصلاح يعيد ``replay`` النتيجة المخزنة
    مباشرة (ليست كوروتيناً) فيفشل التأكيد على إعادة التنفيذ تحديداً —
    وبعد الإصلاح يعيد كوروتيناً يُنتظر."""
    raw = engine.replay(execution_id)
    if inspect.iscoroutine(raw):
        return asyncio.run(raw)
    return raw


def test_replay_reexecutes_work_with_same_parameters():
    """عقد replay: «إعادة تشغيل بنفس المعاملات» — العمل يجب أن يجري
    ثانية بتنفيذ جديد ومعرّف جديد ونتيجة جديدة، وأحداث الاكتمال تثبت
    التنفيذين، والنتيجة الأصلية المخزنة تبقى كما هي."""
    runs = []

    async def skill(context):
        runs.append(dict(context.parameters))
        return {"run": len(runs)}

    engine = ExecutionEngine()
    engine._skill_logic = skill
    engine.create_policy("t", max_retries=0, retry_delay_seconds=0)
    completions = []
    engine.on_event(ExecutionEvent.COMPLETED,
                    lambda context, data: completions.append(context.execution_id))

    first = asyncio.run(engine.execute("cap", "skill", "prov",
                                       {"x": 1}, policy_name="t"))
    assert first.status.value == "completed"
    assert runs == [{"x": 1}]
    assert len(completions) == 1

    replayed = _run(engine, first.execution_id)

    # العمل أُعيد فعلاً — المحاولة الثانية بنفس المعاملات
    assert runs == [{"x": 1}, {"x": 1}]
    # تنفيذ جديد بمعرّف جديد ونتيجة جديدة — لا النتيجة المخزنة نفسها
    assert replayed.execution_id != first.execution_id
    assert replayed.status.value == "completed"
    assert replayed.output == {"run": 2}
    # حدثا اكتمال لتنفيذين مختلفين — الأحداث تثبت أن التنفيذ جرى مرتين
    assert len(completions) == 2
    assert completions[0] != completions[1]
    # النتيجة الأصلية المخزنة باقية مستقلة (نمط 0081)
    assert engine.completed_executions[first.execution_id] is first
    assert engine.get_completed_count() == 2


def test_replay_uses_parameter_snapshot_not_later_mutation():
    """لقطة المعاملات (نمط 0081): تعديل قاموس المعاملات بعد التنفيذ لا
    يغيّر معاملات الإعادة — الإعادة بالمعاملات الأصلية كما نفذت."""
    runs = []

    async def skill(context):
        runs.append(dict(context.parameters))
        return {"ok": True}

    engine = ExecutionEngine()
    engine._skill_logic = skill
    engine.create_policy("t", max_retries=0, retry_delay_seconds=0)

    params = {"x": 1}
    first = asyncio.run(engine.execute("cap", "skill", "prov",
                                       params, policy_name="t"))
    assert first.status.value == "completed"
    params["x"] = 999                      # تعديل لاحق

    replayed = _run(engine, first.execution_id)

    assert replayed.status.value == "completed"
    assert runs == [{"x": 1}, {"x": 1}]    # الإعادة بالأصلية لا المعدلة


def test_snapshot_is_original_input_even_if_work_mutates_parameters():
    """اللقطة تُلتقط قبل العمل لا بعده: عمل يعدّل معامله المتداخل لا يجعل
    الإعادة ترى الحالة النهائية المعدّلة، وإعادتان من المعرّف الأصلي
    نفسه ترى كلتاهما المدخل الابتدائي نفسه (لا تلوث متبادل عبر
    اللقطة المخزنة — كل إعادة نسخة مستقلة)."""
    runs = []

    async def skill(context):
        runs.append({"x": context.parameters["nested"]["x"]})
        context.parameters["nested"]["x"] = 999      # العمل يعدّل معامله
        return {"ok": True}

    engine = ExecutionEngine()
    engine._skill_logic = skill
    engine.create_policy("t", max_retries=0, retry_delay_seconds=0)

    first = asyncio.run(engine.execute(
        "cap", "skill", "prov",
        {"nested": {"x": 1}}, policy_name="t"))
    assert first.status.value == "completed"

    r1 = _run(engine, first.execution_id)
    r2 = _run(engine, first.execution_id)

    assert r1.status.value == "completed"
    assert r2.status.value == "completed"
    # المحاولات الثلاث رأت المدخل الابتدائي نفسه — العمل الأصلي عدّل
    # ولا إعادة تلوث أخرى ولا الحالة النهائية تسري
    assert runs == [{"x": 1}, {"x": 1}, {"x": 1}]


class _UnDeepcopyable:
    """كائن يرفض النسخ العميق — لفحص أن فشل اللقطة لا يكسر التنفيذ."""

    def __deepcopy__(self, memo):
        raise RuntimeError("لا يمكن نسخ هذا الكائن — فحص لقطة الإعادة")


def test_snapshot_failure_does_not_break_execution_or_cleanup():
    """فشل التقاط لقطة المعاملات لا يغيّر نتيجة ``execute`` القائمة ولا
    يمنع تنظيف فهارسها — والإعادة عندئذ خطأ صريح عند الطلب لا نجاح
    وهمي ولا تحويل نجاح إلى استثناء (المادة 6: لا تنفيذ مكسور بصمت)."""
    async def skill(context):
        return {"ok": True}

    engine = ExecutionEngine()
    engine._skill_logic = skill
    engine.create_policy("t", max_retries=0, retry_delay_seconds=0)

    result = asyncio.run(engine.execute(
        "cap", "skill", "prov",
        {"bad": _UnDeepcopyable()}, policy_name="t"))

    # التنفيذ نفسه سليم: نتيجة مكتملة وتنظيف كامل للفهارس
    assert result.status.value == "completed"
    assert result.output == {"ok": True}
    assert engine.get_active_count() == 0
    assert engine.get_completed_count() == 1
    # الإعادة خطأ صريح عند الطلب — الكائن غير قابل للقطة الإعادة
    with pytest.raises(ValueError):
        asyncio.run(engine.replay(result.execution_id))


def test_replay_unknown_id_still_raises_value_error():
    """عقد قائم محفوظ: المجهول يبقى ``ValueError`` كما كان قبل الإصلاح
    وبعده (الاستثناء يصعد سواء رُفع عند النداء أو عند الانتظار)."""
    engine = ExecutionEngine()
    with pytest.raises(ValueError):
        asyncio.run(engine.replay("unknown-id-xyz"))

def test_canceled_deepcopy_propagates_and_still_cleans_up():
    """استثناء تحكم (asyncio.CancelledError) أثناء التقاط اللقطة ينتشر ولا
    يُستدعى العمل وتُنظَّف فهارس الإتمام — الالتقاط لا يجوز أن يتجاوز التنظيف."""
    engine = ExecutionEngine()

    class _CancelDeepcopy:
        def __deepcopy__(self, memo):
            raise asyncio.CancelledError("raced during snapshotting")

    called = []

    async def skill(context):
        called.append(True)
        return {"ok": True}

    engine._skill_logic = skill
    engine.create_policy("t", max_retries=0, retry_delay_seconds=0)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(engine.execute(
            "cap", "skill", "prov", _CancelDeepcopy(), policy_name="t"))
    assert not called
    assert engine.get_active_count() == 0
    assert engine.get_completed_count() == 0
