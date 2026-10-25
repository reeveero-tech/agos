"""أدلة رصدية — المادة 6: أحداث الأفعال خارج مسار الترخيص (الشريحة 31 /
سجل العمل 0105).

البند المتبقي المسماة في خريطة أدلة ADR-0010: «أحداث الأفعال خارج هذا
المسار (مسار الترخيص الموحد) — لم يُتتبّع بعد». المنهج المعتمد لسابقه
(الشريحة 28 / سجل العمل 0102): أدلة رصدية بحدود معلنة — لا اختبار أحمر
مصطنع ما دام الخلل غير مثبت؛ والعنصر الحاسم اقتران الأحداث بالفعل
الحقيقي وترتيبها حوله، لا مجرد وجود أسماء الأحداث في القائمة.

المسار المفحوص: k.run → MissionEngine → ExecutionPipeline → النواة
المشتركة (invoke_sync) — لم تُرصد استشارة لبوابة الترخيص في نافذة
المهمة المختبرة (الشريحة 28)، وتغطية المدخل بالترخيص مسألة مفتوحة.
تُقرأ أحداث النافذة الخام من الناقل نفسه (`EventBus.get_events`) قبل
أي ترشيح: موضع بداية النافذة (طول الناقل قبل المهمة) يفصل نافذة كل
مهمة، ثم تُفحص هويات أحداث النافذة الخام كلها وتسلسلها — فاكتشاف أي
حدث دخيل أو بلا هوية المهمة الصحيحة يفشل الاختبار (لا فحص يدور في
حلقة مغلقة بترشيح الهوية نفسها).

الحالات الثلاث:
1. نجاح حي: مهمة حقيقية عبر المدخل العام — كل خطوة فعل تترك حدثاً
   واحداً بالترتيب (اختيار القدرة → اختيار المزوّد → بدء التنفيذ →
   اكتماله) وكلها بهوية المهمة الصحيحة، مع إثبات وقوع الاستدعاء
   الفعلي بين حدثي البدء والاكتمال (استدعاء واحد معدود).
2. فشل العمل بعد البدء: عطل محقون معروف الهوية عند حد الاستدعاء
   نفسه (استبدال تنفيذ قدرة حقيقية من السجل بدالة ترفع استثناءً
   معروفاً) — الأحداث تُلتقط داخل الدالة المحقونة لحظة الرفع فيثبت
   أن البدء سُبق والفشل لم يُسجَّل بعد، ثم حدث فشل واحد يحمل السبب
   ولا حدث اكتمال. الحالة المحقونة مميزة عن النجاح الحي صراحة.
3. رفض قبل العمل: قدرة غير مسجلة — صفر استدعاءات عمل، وحدث وحيد
   (فشل) بهوية المهمة، لا بدء ولا اكتمال ولا اختيار.

حدود معلنة: الأدلة عند حد تنفيذ خط المهمة المختبر (k.run) — لا إثبات
أحداث لكل استدعاء داخلي ولا لأحداث الفعل في المنافذ غير المفحوصة؛
والأحداث في الذاكرة (الناقل بلا مشتركين ولا تخزين دائم — قناة القراءة
الوحيدة get_events، والاتصال بمجرى أحداث خارجي بند متبقٍ مستقل لم
يُثبت)؛ وأحداث MISSION_*/SKILL_* معرّفة ولا يوجد ناشر إنتاجي لها
(معلن لا مُصلَح — ليست مخالفة مثبتة لوجب «حدث لكل فعل» عند هذا الحد)؛
والأحداث تحمل هوية المهمة لا سياق قرار الترخيص (مسألة المادة 15
المفتوحة).
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
                       capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stderr[-3000:]
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


def test_article_6_live_success_full_event_sequence_with_mission_identity(git_repo):
    """نجاح حي عبر المدخل العام: كل خطوة فعل تترك حدثاً واحداً بالترتيب
    وبهوية المهمة، والاستدعاء الفعلي يقع بين حدثي البدء والاكتمال —
    فحص النافذة الخام من الناقل نفسه قبل أي ترشيح، لا مخرجات الطباعة."""
    out = json.loads(run(f"""
        import json
        from agos_kernel.execution.engine import get_engine

        engine = get_engine()
        real_invoke = engine.invoke_sync
        calls = []
        k_bus = None
        window_start = [0]  # موضع بداية النافذة — يُضبط بعد الإقلاع

        def recording_invoke(func, *args, **kwargs):
            events = ([e.type.value for e in k_bus.get_events()[window_start[0]:]]
                      if k_bus is not None else [])
            calls.append({{"func": getattr(func, "__name__", "?"),
                           "events_so_far": events}})
            return real_invoke(func, *args, **kwargs)

        engine.invoke_sync = recording_invoke
        import agos_runtime
        k = agos_runtime.boot()
        k_bus = k.event_bus
        window_start[0] = len(k_bus.get_events())  # بداية نافذة المهمة
        r = k.analyze({str(git_repo)!r}, branch="main")

        # أحداث النافذة الخام قبل أي ترشيح — فحص الهوية عليها لا بعد ترشيحها
        window = k_bus.get_events()[window_start[0]:]
        identity_ok = all(e.mission_id == r.mission_id for e in window)
        print(json.dumps({{
            "state": r.state.value,
            "mission_id": r.mission_id,
            "window_len": len(window),
            "run_calls": len(calls),
            "mission_events": [e.type.value for e in window],
            "identity_ok": identity_ok,
            "events_at_call": calls[-1]["events_so_far"] if calls else [],
            "ledger_last_id": k.missions[-1].mission_id,
        }}))
    """))
    assert out["state"] == "completed"
    # أثر معدود: استدعاء عمل واحد عبر النواة المشتركة في نافذة المهمة
    assert out["run_calls"] == 1
    # التسلسل الكامل لخطوات الفعل — كل خطوة حدثاً واحداً بالترتيب
    assert out["mission_events"] == [
        "capability_selected", "provider_selected",
        "execution_started", "execution_completed"]
    # كل أحداث النافذة الخام تحمل هوية المهمة نفسها — لا دخيل ولا مجهول
    assert out["identity_ok"] is True
    assert out["window_len"] == 4
    # الاستدعاء الفعلي وقع بعد البدء وقبل الاكتمال: أحداث ما قبل
    # الاستدعاء هي الثلاثة الأولى من تسلسل المهمة تحديداً — لا غيرها
    assert out["events_at_call"] == out["mission_events"][:3]
    assert out["ledger_last_id"] == out["mission_id"]


def test_article_6_work_failure_after_start_emits_single_failure_event(git_repo):
    """فشل العمل الفعلي بعد البدء (حالة محقونة مميزة عن النجاح الحي):
    قدرة حقيقية من السجل يُستبدل تنفيذها عند حد الاستدعاء نفسه بدالة
    معروفة الهوية ترفع استثناءً معروفاً — تُلتقط الأحداث داخلها لحظة
    الرفع فيثبت أن البدء سُبق، ثم حدث فشل واحد يحمل السبب ولا حدث
    اكتمال، والاستدعاء الفاشل معدود."""
    out = json.loads(run(f"""
        import json
        import agos_runtime

        k = agos_runtime.boot()
        k_bus = k.event_bus
        window_start = len(k_bus.get_events())  # بداية نافذة المهمة

        # العطل المحقون: قدرة حقيقية من السجل، تنفيذها مستبدل عند حد
        # الاستدعاء — لا نجاح وهمي ولا قدرة مصطنعى خارج السجل
        ra = k.capability_registry.get("RepositoryAnalysis")
        injected_calls = []
        events_at_failure = []
        def injected_execute(*args, **kwargs):
            injected_calls.append(1)
            events_at_failure.append(
                [e.type.value for e in k_bus.get_events()[window_start:]])
            raise RuntimeError("عطل محقون معروف للشريحة 31")
        ra.execute = injected_execute
        ra.execute_with_provider = injected_execute

        r = k.run({{"name": "فشل بعد البدء", "capability": "RepositoryAnalysis",
                   "parameters": {{"url": {str(git_repo)!r}, "branch": "main"}}}})

        # أحداث النافذة الخام قبل أي ترشيح — فحص الهوية عليها
        window = k_bus.get_events()[window_start:]
        identity_ok = all(e.mission_id == r.mission_id for e in window)
        failed = [e for e in window if e.type.value == "execution_failed"]
        print(json.dumps({{
            "state": r.state.value,
            "injected_calls": len(injected_calls),
            "mission_events": [e.type.value for e in window],
            "identity_ok": identity_ok,
            "events_at_failure": events_at_failure[0] if events_at_failure else [],
            "failure_cause": failed[0].data.get("error") if failed else None,
            "ledger_last_state": k.missions[-1].state.value,
        }}))
    """))
    assert out["state"] == "failed"
    # العمل بدأ فعلاً ثم فشل: استدعاء واحد للعطل المحقون عند حد الاستدعاء
    assert out["injected_calls"] == 1
    # توقيت الفشل مثبت لحظة الرفع: البدء سُبق ولم يُسجَّل فشل ولا اكتمال بعد
    assert out["events_at_failure"] == [
        "capability_selected", "provider_selected", "execution_started"]
    # اختياران وبدء ثم فشل واحد — ولا اكتمال
    assert out["mission_events"] == [
        "capability_selected", "provider_selected",
        "execution_started", "execution_failed"]
    assert "execution_completed" not in out["mission_events"]
    # كل أحداث النافذة الخام بهوية المهمة — وحدث الفشل الوحيد يحمل السبب المحقون
    assert out["identity_ok"] is True
    assert out["failure_cause"] == "عطل محقون معروف للشريحة 31"
    # الفشل مسجل صراحة لا مبتلع
    assert out["ledger_last_state"] == "failed"


def test_article_6_rejection_before_work_emits_only_failure_event():
    """رفض قبل العمل: قدرة غير مسجلة تفشل في التحديد قبل أي استدعاء
    عمل — صفر استدعاءات، وحدث وحيد (فشل) بهوية المهمة يحمل سبب
    الرفض، ولا بدء ولا اكتمال ولا اختيار."""
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
        k_bus = k.event_bus
        window_start = len(k_bus.get_events())  # بداية نافذة المهمة
        r = k.run({"name": "رفض قبل العمل", "capability": "NonexistentCapability_XYZ",
                   "parameters": {}})
        # أحداث النافذة الخام قبل أي ترشيح — فحص الهوية عليها
        window = k_bus.get_events()[window_start:]
        identity_ok = all(e.mission_id == r.mission_id for e in window)
        failed = [e for e in window if e.type.value == "execution_failed"]
        print(json.dumps({
            "state": r.state.value,
            "work_calls": len(calls),
            "mission_events": [e.type.value for e in window],
            "identity_ok": identity_ok,
            "failure_cause": failed[0].data.get("error") if failed else None,
            "ledger_last_state": k.missions[-1].state.value,
        }))
    """))
    assert out["state"] == "failed"
    # أثر معدوم: صفر استدعاء عمل عبر النواة المشتركة عند فشل التحديد
    assert out["work_calls"] == 0
    # حدث وحيد بهوية المهمة: الفشل — لا بدء ولا اكتمال ولا اختيار
    assert out["mission_events"] == ["execution_failed"]
    assert out["identity_ok"] is True
    assert out["failure_cause"].startswith("Capability resolution failed")
    assert out["ledger_last_state"] == "failed"
