# -*- coding: utf-8 -*-
"""المادة 6 (سجل العمل 0104) — الاستثناء الخارج من بوابات الترخيص قبل
رجوعها لا يهرب من التدقيق.

الفجوة المعلنة في ADR-0010 (بعد سجل العمل 0081): «الاستثناء الخارج من
_evaluate_authorization قبل رجوعها لا يسجّله الغلاف الحالي» — كل بوابات
القرار قد ترمي (المفوّض، محدد القواعد، المقيم، بوابة المنح، السلامة،
الموافقة) فإذا رمى شيء منها عاد الاستثناء للمستدعي ولم يترك الطلبُ أثراً
أيَّ أثر في سجل التدقيق. منهج الأحمر أولاً: هذه الاختبارات تُكتب وتُشغَّل
على الكود قبل الإصلاح فتفشل (السجل يبقى فارغاً)، ثم الإصلاح الأدنى في
الغلاف نفسه (authorize_execution): تسجيل أثر واحد للطلب قبل إعادة رمي
الاستثناء كما هو — لا ابتلاع ولا تغيير دلالة الرفض.
"""
import pytest

from agos_kernel.civilization.autonomous_engineering.autonomous_batch import (
    GovernanceRuntime as AutoGovRuntime)

MISSION = {"type": "mission", "mission": {"id": "m1", "version": "1.0"}}


def test_exception_at_first_gate_is_audited_before_reraise():
    """أحمر أولاً: استثناء يخرج من أول البوابات (المفوّض) قبل رجوعها —
    الطلب يجب أن يترك أثراً واحداً في سجل التدقيق (authorized=False بسببه
    المسمى) والاستثناء يعود للمستدعي كما هو (لا ابتلاع)."""
    rt = AutoGovRuntime()

    def _raise(action):
        raise RuntimeError("فشل عرضي في بوابة التفويض")

    rt.authorizer.authorize = _raise
    with pytest.raises(RuntimeError, match="فشل عرضي في بوابة التفويض"):
        rt.authorize_execution(dict(MISSION))

    # الأثر: طلب واحد = سجل واحد — مرتبط بالطلب نفسه بحكمه وسببه
    assert len(rt.auditor.audit_log) == 1
    entry = rt.auditor.audit_log[-1]
    assert entry["authorized"] is False
    assert entry["action"] == MISSION
    assert "RuntimeError" in entry["reason"]
    assert "فشل عرضي في بوابة التفويض" in entry["reason"]
    # الأثر يحمل الاستثناء بتتبعه (نمط تشخيص مستمعي المحرك — سجل العمل 0101)
    assert entry["error"]["type"] == "RuntimeError"
    assert entry["error"]["message"] == "فشل عرضي في بوابة التفويض"
    assert "raise RuntimeError" in entry["error"]["traceback"]


def test_exception_at_late_gate_is_audited_too():
    """البوابة المتأخرة كذلك: استثناء من فاحص السلامة بعد نجاح السياسات
    والمنح — الأثر يُسجَّل والاستثناء يعود كما هو. حد معلن: أثر الاستثناء
    لا يحمل نتائج السياسات المستشارة (انقطع المسار قبل الرجوع — لا يُختلق
    دليل سياسة من آخر نتيجة عامة قد تعود لطلب سابق)."""
    rt = AutoGovRuntime()
    safety = rt.safety

    def _raise(action):
        raise ValueError("خلل عرضي في فاحص السلامة")

    safety.validate = _raise
    with pytest.raises(ValueError, match="خلل عرضي في فاحص السلامة"):
        rt.authorize_execution(dict(MISSION))

    assert len(rt.auditor.audit_log) == 1
    entry = rt.auditor.audit_log[-1]
    assert entry["authorized"] is False
    assert entry["action"] == MISSION
    assert "ValueError" in entry["reason"]
    assert entry["error"]["type"] == "ValueError"
    assert entry["error"]["message"] == "خلل عرضي في فاحص السلامة"


def test_exception_audit_entry_is_independent_snapshot():
    """الأثر لقطة مستقلة (نمط سجل العمل 0081): تعديل الطلب بعد الاستثناء
    لا يغير الأثر التاريخي — والأثر لا يكرر ولا يتضاعف: قرار طبيعي لاحق
    يسجل أثراً واحداً كما كان، لا أثراً إضافياً للقرار نفسه."""
    rt = AutoGovRuntime()
    request = {"type": "mission", "mission": {"id": "m2", "version": "1.0"}}

    def _raise(action):
        raise RuntimeError("انقطاع قبل رجوع البوابات")

    rt.authorizer.authorize = _raise
    with pytest.raises(RuntimeError):
        rt.authorize_execution(request)

    # تعديل الطلب بعد الاستثناء لا يمس الأثر (نسخة عميقة عند الالتقاط)
    request["mission"]["id"] = "m2-mutated"
    entry = rt.auditor.audit_log[-1]
    assert entry["action"] == {"type": "mission",
                               "mission": {"id": "m2", "version": "1.0"}}

    # قرار طبيعي لاحق: أثر واحد له كما كان — الاستثناء لم يترك بقايا
    rt.authorizer.authorize = lambda action: True
    res = rt.authorize_execution(dict(MISSION))
    assert res["authorized"] is True
    assert len(rt.auditor.audit_log) == 2


def test_control_exceptions_pass_through_unaudited():
    """استثناءات التحكم ليست قراراً: تمر كما هي ولا تُسجَّل أثراً في سجل
    قرارات الترخيص (الالتقاط لـException فقط — نمط محرك التنفيذ ADR-0008،
    واستثناءات التحكم مثل الإلغاء تمر ولا تبتلع)."""
    rt = AutoGovRuntime()

    def _raise(action):
        raise KeyboardInterrupt("إيقاف تشغيلي")

    rt.authorizer.authorize = _raise
    with pytest.raises(KeyboardInterrupt):
        rt.authorize_execution(dict(MISSION))
    assert rt.auditor.audit_log == []
