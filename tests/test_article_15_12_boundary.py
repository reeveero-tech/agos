"""أدلة رصدية — المادة 15 (حد بوابة المنح لمسار k.run) والمادة 12 (تكرار
قرارات خط المهمة) — الشريحة 0102.

منهج الشريحة: أدلة رصدية بحدود معلنة (قرار المراجعة المعتمد — لا اختبار
أحمر مصطنع). النتيجة الحدية الصادقة:
«لم تُرصد استشارة هاتين البوابتين أثناء الحالة المختبرة عبر k.run؛
تغطية هذا المدخل بالترخيص ما تزال مسألة مفتوحة» — لا يُوصف هذا الغياب
بأحكام تتجاوز القياس.

ضوابط المراجعة المطبقة:
- المسجل الشفاف يُركَّب قبل الإقلاع ويفوّض للأصل دون تغيير مدخلاته
  وحكمه، مع تحقق هوية الأصناف الملفوفة (الأسماء المستعارة تتطابق).
- الضابط الإيجابي من نمط المستهلك المعروف: الحالة المستوفية تصل إلى
  الحدين المرصودين معاً (authorize_execution وgrants_verified) والقرار
  «authorized» — استدعاء مباشر يثبت التقاط الراصد.
- نوافذ القياس مفصولة بالكامل بمؤشرات بداية صريحة لكل نافذة (الإقلاع /
  الضابط / كل مهمة) — استدعاءات الضابط تُفحص وحدها بعد مؤشر بدايتها،
  والحمولات تُؤخذ بشرائح مستقلة لكل مهمة مع اشتراط حمولة واحدة بالضبط
  للمهمة المعنية (لا الاعتماد على آخر عنصر).
- عبر k.run: عمل محدود متوقع وأثر معدود (لا «completed» وحدها) ثم صفر
  استشارات للحدود المرصودة في نافذة المهمة.
- المادة 12: نفس المهمة مرتين في السياق المثبت — لقطة عميقة مستقلة
  (نسخ عميق داخل كل تشغيل قبل الذي يليه — لا اشتراك قواميس/قوائم بين
  التشغيلين)؛ والمقارنة تستبعد الحقول التشغيلية في مساراتها الفعلية
  الأربعة حصراً بعد فحص البنية (فحص فروق تشغيلين حصرها): `decision_id`
  و`timestamp` في سطح السجل، و`why.decision_id` و`why.trace.timestamp` —
  يُستبعد كل منها بعد التحقق من تطابقه مع معرف سجله وطابعه الزمني (لا
  حذف أي مفتاح بالاسم أينما ظهر)؛ وحالة تعادل وفق السياسة المعلنة
  (stable-registration-order) بنتيجة متوقعة مستقلة (ترتيب التسجيل معلوم
  من جهة الاختبار) مع فحص الأثر المعدود في التشغيلين.

حدود معلنة: تشغيلان في السياق المثبت يثبتان التكرار للحالات المختبرة —
لا إعادة تشغيل تدقيقية كاملة ولا حتمية عامة عبر كل الإقلاعات؛ وصفر
الاستشارة محصور بالحدين المرصودين في العملية المختبرة.
"""
import copy
import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
KERNEL = REPO / "agos" / "agos-kernel"


def _run_phase(code: str, tmp_dir: Path) -> dict:
    env = {**dict(__import__("os").environ), "TMPDIR": str(tmp_dir)}
    r = subprocess.run([sys.executable, "-c", textwrap.dedent(code)],
                       cwd=KERNEL, capture_output=True, text=True,
                       timeout=600, env=env)
    assert r.returncode == 0, r.stderr[-3000:]
    return json.loads(r.stdout.strip().splitlines()[-1])


# ---------------------------------------------------------------------------
# الطور أ — المادة 15: حد بوابة المنح لمسار k.run (رصدي بضابط إيجابي)
# ---------------------------------------------------------------------------
A15_PHASE_CODE = """
import json
from agos_kernel.civilization.autonomous_engineering.autonomous_batch import (
    GovernanceRuntime, AuthorizationGrantGate)

GATE_CALLS = []
_real_auth = GovernanceRuntime.authorize_execution
_real_gv = AuthorizationGrantGate.grants_verified


def _rec_auth(self, action):
    atype = action.get("type") if isinstance(action, dict) else None
    GATE_CALLS.append(["authorize_execution", atype])
    return _real_auth(self, action)


def _rec_gv(self, action, policy_outcome=None):
    atype = action.get("type") if isinstance(action, dict) else None
    GATE_CALLS.append(["grants_verified", atype])
    return _real_gv(self, action, policy_outcome)


GovernanceRuntime.authorize_execution = _rec_auth
AuthorizationGrantGate.grants_verified = _rec_gv

# تحقق الهوية: الصنفان الملفوفان هما صنفا الوحدة المستخدمة فعلاً
# (مسارا الاستيراد المستعار والصريح يتطابقان — نفس كائن الوحدة)
import civilization.autonomous_engineering.autonomous_batch as _ab
assert _ab.GovernanceRuntime is GovernanceRuntime
assert _ab.AuthorizationGrantGate is AuthorizationGrantGate

# التقاط الحمولة عند حد التنفيذ الفعلي — المهمة كما تمر بالأنبوب فعلاً
from pipeline import ExecutionPipeline
PAYLOADS = []
_real_exec = ExecutionPipeline.execute


def _rec_exec(self, mission):
    PAYLOADS.append({
        "id": getattr(mission, "id", None),
        "has_version": hasattr(mission, "version"),
        "version": getattr(mission, "version", None),
    })
    return _real_exec(self, mission)


ExecutionPipeline.execute = _rec_exec

import agos_runtime
k = agos_runtime.boot()
boot_calls = list(GATE_CALLS)
boot_payloads = len(PAYLOADS)

# الضابط الإيجابي: الحالة المستوفية تصل الحدين المرصودين معاً — نافذته
# مفصولة بمؤشر بداية صريح فاستدعاءاته تُفحص وحدها (لا تشمل ما قبلها)
control_start = len(GATE_CALLS)
gr = GovernanceRuntime()
control = gr.authorize_execution({
    "type": "mission",
    "mission": {"id": "ctl-boundary-1", "version": "1.0.0"}})
control_calls = list(GATE_CALLS[control_start:])

# مهمة حية عبر المدخل العام: عمل محدود متوقع وأثر معدود — حمولتها بشرائح
# مستقلة (واحدة بالضبط للمهمة المعنية، لا آخر عنصر)
m1_start = len(GATE_CALLS)
m1_payload_start = len(PAYLOADS)
m1 = k.run({"name": "مهمة حد البوابة", "description": "وصف",
            "capability": "SecurityScan",
            "parameters": {"files": {"app.py": "import flask\\n",
                                     "requirements.txt": "flask\\n"}}})
m1_calls = list(GATE_CALLS[m1_start:])
m1_payloads = list(PAYLOADS[m1_payload_start:])
m1_res = getattr(m1, "result", None)
m1_facts = {}
if isinstance(m1_res, dict):
    m1_facts = {"secrets_found": m1_res.get("secrets_found"),
                "scanned_files": m1_res.get("scanned_files")}

# مهمة بقاموس خام يحمل إصداراً مميزاً — يُسجل ما يصل حد التنفيذ فعلاً
m2_start = len(GATE_CALLS)
m2_payload_start = len(PAYLOADS)
m2 = k.run({"name": "مهمة إصدار مميز", "description": "وصف",
            "version": "9.9.9-rc1",
            "capability": "SecurityScan",
            "parameters": {"files": {"app.py": "import flask\\n"}}})
m2_calls = list(GATE_CALLS[m2_start:])
m2_payloads = list(PAYLOADS[m2_payload_start:])
m2_res = getattr(m2, "result", None)
m2_facts = {"secrets_found": m2_res.get("secrets_found")} if isinstance(
    m2_res, dict) else {}

print(json.dumps({
    "boot_calls": boot_calls,
    "boot_payloads": boot_payloads,
    "control": {"decision": control, "captured": control_calls},
    "m1": {"state": m1.state.value, "error": str(getattr(m1, "error", None)),
           "facts": m1_facts, "gate_calls_during": m1_calls,
           "payload_count": len(m1_payloads), "payloads": m1_payloads},
    "m2": {"state": m2.state.value, "facts": m2_facts,
           "gate_calls_during": m2_calls,
           "payload_count": len(m2_payloads), "payloads": m2_payloads,
           "dict_version": "9.9.9-rc1"},
}, ensure_ascii=False, default=str))
"""


# ---------------------------------------------------------------------------
# الطور ب — المادة 12: تكرار قرارات خط المهمة (حالة واضحة + تعادل معلن)
# ---------------------------------------------------------------------------
A12_PHASE_CODE = """
import copy
import json
import agos_runtime
import providers

k = agos_runtime.boot()

MISSION = {"name": "مهمة تكرار", "description": "وصف",
           "capability": "SecurityScan",
           "parameters": {"files": {"app.py": "import flask\\n",
                                    "requirements.txt": "flask\\n"}}}


def run_once():
    o = k.run(dict(MISSION))
    res = getattr(o, "result", None)
    facts = {}
    if isinstance(res, dict):
        facts = {"secrets_found": res.get("secrets_found"),
                 "scanned_files": res.get("scanned_files")}
    # لقطة عميقة مستقلة داخل التشغيل نفسه — لا اشتراك قواميس/قوائم بين
    # تشغيلين ولا انتظار التحويل النهائي بعد الجميع
    records = [copy.deepcopy(r.to_dict())
               for r in getattr(o, "decision_records", [])]
    return {
        "state": o.state.value,
        "facts": facts,
        "records": records,
    }


first = run_once()
second = run_once()

# حالة التعادل وفق السياسة المعلنة: مزوّد توأم بنفس المهارات — التسجيل
# الأول (LocalRepositoryProvider وقت الإقلاع) هو المتوقع فائزاً، وهذا
# معلوم من جهة الاختبار لا مشتق من المحرك نفسه
class TwinProvider:
    def __init__(self):
        self._inner = providers.LocalRepositoryProvider()

    @property
    def name(self):
        return "TwinProvider"

    def supports_skill(self, skill_name):
        return skill_name in ["CloneRepository", "ReadRepository",
                              "WalkRepository"]

    def execute(self, skill_name, input_data):
        raise RuntimeError("لن يُستدعى — التعادل يكسره ترتيب التسجيل")


reg = k.provider_registry
registered_before = [p.name for p in reg.list_all()]
reg.register(TwinProvider())
registered_after = [p.name for p in reg.list_all()]

tie_first = run_once()
tie_second = run_once()

print(json.dumps({
    "clear": {"first": first, "second": second},
    "tie": {"first": tie_first, "second": tie_second},
    "registration": {"before": registered_before,
                     "after": registered_after},
}, ensure_ascii=False, default=str))
"""


@pytest.fixture(scope="module")
def a15_phase(tmp_path_factory):
    return _run_phase(A15_PHASE_CODE, tmp_path_factory.mktemp("a15"))


@pytest.fixture(scope="module")
def a12_phase(tmp_path_factory):
    return _run_phase(A12_PHASE_CODE, tmp_path_factory.mktemp("a12"))


# ---------------------------------------------------------------------------
# المادة 15: الضابط الإيجابي — الراصد يلتقط الحدين عند الحالة المستوفية
# ---------------------------------------------------------------------------
def test_article_15_positive_control_instrument_captures_gate(a15_phase):
    """ضابط إيجابي بأداة الرصد: استدعاء مباشر للحوكمة بحالة مستوفية
    (حمولة mission بهوية وإصدار) يُلتقط عند الحدين المرصودين معاً
    (authorize_execution ثم grants_verified داخلها) والقرار «authorized» —
    نافذة الضابط مفصولة بمؤشر بداية صريح فاستدعاءاته تُفحص وحدها."""
    control = a15_phase["control"]
    assert control["decision"] == {"authorized": True}, control["decision"]
    assert control["captured"] == [["authorize_execution", "mission"],
                                   ["grants_verified", "mission"]], (
        control["captured"])


# ---------------------------------------------------------------------------
# المادة 15: مهمة k.run — عمل معدود وصفر استشارة للحدود المرصودة
# ---------------------------------------------------------------------------
def test_article_15_krun_mission_effect_without_gate_consultation(a15_phase):
    """مهمة حقيقية عبر المدخل العام: عمل محدود متوقع بأثر معدود (لا
    «completed» وحدها)، وصفر استشارة للحدين المرصودين في نافذة المهمة
    (مفصولة بمؤشر بداية صريح). النتيجة الحدية: لم تُرصد استشارة هاتين
    البوابتين أثناء الحالة المختبرة عبر k.run؛ تغطية هذا المدخل بالترخيص
    ما تزال مسألة مفتوحة."""
    m1 = a15_phase["m1"]
    assert m1["state"] == "completed", m1
    # الأثر المعدود: مسح ملفين بلا أسرار — حقيقة متوقعة من المدخل
    assert m1["facts"]["secrets_found"] == 0, m1["facts"]
    assert m1["facts"]["scanned_files"] == 2, m1["facts"]
    assert m1["gate_calls_during"] == [], m1["gate_calls_during"]
    # حمولة واحدة بالضبط تعبر حد التنفيذ لهذه المهمة (شرائح مستقلة)
    assert m1["payload_count"] == 1, m1["payload_count"]


def test_article_15_mission_payload_at_execution_boundary(a15_phase):
    """الحمولة كما تمر حد التنفيذ فعلاً (التقاط عند pipeline.execute لا
    تحليل موازٍ): المهمة تحمل هوية (id) — ولا حقل version على نموذج مهمة
    خط المهمة أصلاً؛ وقاموس خام يحمل إصداراً مميزاً (9.9.9-rc1) يصل الحد
    بلا إصدار — المحلل لا يمرره. توثيق حقيقة لا حكم: قابلية الواجب ليست
    مثبتة بمجرد حقول في نموذج آخر."""
    m1 = a15_phase["m1"]
    payload = m1["payloads"][0]
    assert payload["id"], payload
    assert payload["has_version"] is False, payload
    m2 = a15_phase["m2"]
    assert m2["state"] == "completed", m2
    assert m2["payload_count"] == 1, m2["payload_count"]
    assert m2["payloads"][0]["has_version"] is False, (
        "الإصدار المميز في القاموس الخام وصل حد التنفيذ — لم يُسقط")
    assert m2["facts"]["secrets_found"] == 0, m2["facts"]
    assert m2["gate_calls_during"] == [], m2["gate_calls_during"]


def test_article_15_boot_window_measured(a15_phase):
    """نافذة الإقلاع مقيسة لا مفترضة: لا مهمة تعبر الأنبوب أثناء الإقلاع
    (صفر حمولات)، واستشارات الحدين المرصودين أثناءه تُطبع كما رُصدت —
    قياس لا حد عام."""
    assert a15_phase["boot_payloads"] == 0, a15_phase["boot_payloads"]
    assert isinstance(a15_phase["boot_calls"], list)


# ---------------------------------------------------------------------------
# المادة 12: تكرار قرار خط المهمة — الحالة الواضحة
# ---------------------------------------------------------------------------
def _records_of(run):
    return [dict(r) for r in run["records"]]


def _normalized_records(run):
    """تطبيع محصور بالمسارات التشغيلية الفعلية الأربعة بعد فحص البنية
    (فحص فروق تشغيلين فعلي حصرها): سطح السجل يحمل decision_id وtimestamp؛
    وwhy يحمل decision_id مضمّناً وtrace.timestamp — يُستبعدان بعد التحقق
    من تطابقهما مع معرف سجله وطابعه الزمني (لا حذف أي مفتاح بالاسم
    أينما ظهر — كي لا يُسقط حقل من السياسة أو الأدلة)."""
    normalized = []
    for record in _records_of(run):
        d = copy.deepcopy(record)
        rec_id = d.get("decision_id")
        rec_ts = d.get("timestamp")
        d.pop("decision_id", None)
        d.pop("timestamp", None)
        why = d.get("why")
        if isinstance(why, dict):
            if "decision_id" in why:
                assert why["decision_id"] == rec_id, (
                    "decision_id داخل why لا يطابق معرف سجله — المسار مختلف")
                del why["decision_id"]
            trace = why.get("trace")
            if isinstance(trace, dict) and "timestamp" in trace:
                assert trace["timestamp"] == rec_ts, (
                    "timestamp داخل trace لا يطابق طابع سجله — المسار مختلف")
                del trace["timestamp"]
        normalized.append(d)
    return normalized


def test_article_12_clear_selection_repeats(a12_phase):
    """نفس المهمة مرتين في السياق المثبت: قرار القدرة وقرار المزوّد
    يتكرران بتطابق كامل للسجل (الاختيار والترتيب والدرجات والأسباب
    ولقطة السياسة والحالة) بعد استبعاد الحقول التشغيلية في مساراتها
    الفعلية فقط — والمهمة تكتمل بأثر معدود في التشغيلين (لقطات عميقة
    مستقلة مأخوذة داخل كل تشغيل قبل الذي يليه)."""
    first = a12_phase["clear"]["first"]
    second = a12_phase["clear"]["second"]
    for run in (first, second):
        assert run["state"] == "completed"
        assert run["facts"]["secrets_found"] == 0
        assert run["facts"]["scanned_files"] == 2
    kinds = {r["kind"]: r["selected"] for r in _records_of(first)}
    assert kinds == {"capability": "SecurityScan",
                     "provider": "LocalRepositoryProvider"}, kinds
    assert _normalized_records(first) == _normalized_records(second), (
        "قرار خط المهمة لم يتكرر بتطابق كامل بين تشغيلين للمهمة نفسها")


# ---------------------------------------------------------------------------
# المادة 12: حالة التعادل وفق السياسة المعلنة — نتيجة متوقعة مستقلة
# ---------------------------------------------------------------------------
def test_article_12_declared_tie_break_repeats(a12_phase):
    """تعادل درجات مزوّدين متطابقين في المهارات: الفائز هو المسجل أولاً
    (LocalRepositoryProvider وقت الإقلاع) — متوقع من جهة الاختبار لأن
    ترتيب التسجيل معلوم، لا مشتق من المحرك — وسياسة كسر التعادل مسجلة
    بالسجل (stable-registration-order)؛ والقرار يتكرر بتطابق كامل بين
    تشغيلين، والأثر المعدود مفحوص في التشغيلين. تشغيلان يثبتان التكرار
    للحالات المختبرة لا حتمية عامة."""
    before = a12_phase["registration"]["before"]
    after = a12_phase["registration"]["after"]
    assert "LocalRepositoryProvider" in before and "TwinProvider" not in before
    assert after.index("LocalRepositoryProvider") < after.index("TwinProvider")

    for run in (a12_phase["tie"]["first"], a12_phase["tie"]["second"]):
        assert run["state"] == "completed"
        assert run["facts"]["secrets_found"] == 0, run["facts"]
        assert run["facts"]["scanned_files"] == 2, run["facts"]
        records = _records_of(run)
        kinds = {r["kind"]: r for r in records}
        assert kinds["capability"]["selected"] == "SecurityScan"
        provider = kinds["provider"]
        # المتوقع المستقل: المسجل أولاً يفوز — والتعادل مسجل بسياسته
        assert provider["selected"] == "LocalRepositoryProvider", provider
        assert provider["tie_break"] == "stable-registration-order", provider
        assert provider["ranked_alternatives"] == [
            "LocalRepositoryProvider", "TwinProvider"], provider
        scores = {c["name"]: c["score"]["total"]
                  for c in provider["candidates"]}
        assert scores["LocalRepositoryProvider"] == scores["TwinProvider"], (
            "ليس تعادلاً — فرضية الحالة غير متحققة")
    assert _normalized_records(a12_phase["tie"]["first"]) == \
        _normalized_records(a12_phase["tie"]["second"]), (
            "قرار التعادل لم يتكرر بتطابق كامل بين تشغيلين للمهمة نفسها")
