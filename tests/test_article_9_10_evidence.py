"""أدلة تشغيلي — المادتان 9 و10 من خريطة أدلة ADR-0010: الذكاء الخارجي
(الشريحة 0099).

منهج المشروع: أحمر أولاً ثم أدنى إصلاح — وهذه الشريحة **أدلة بلا أحمر
مصطنع**: لم يُعثر على خرق عقد قائم ولم يُعثر على استدعاء ذكاء خارجي ضمن
المسارات المحصورة؛ القائمتان (منع المادة 9 وسماح المادة 10) معلنتان في
الدستور، وإنفاذهما على تكامل خارجي فعلي غير متحقق.

النص الحاكم (constitution.py): المادة 9 — الذكاء الخارجي ممنوع من
(Plan, Reason, Govern, Remember, Own Context, Own Knowledge, Own
Missions)؛ والمادة 10 — مسموح لثمانية أفعال (Execute, Generate,
Transform, Analyze, Summarize, Translate, Review, Evaluate).

حد الإثبات المعلن لهذه الشريحة (لا استنتاج نفي شامل):
- المشاهدات فقط لا ادعاءات سلطات: الاختبارات تسجل ما رُصد (اكتمال
  المهمة، سجلات قرار داخلية، محتويات السجل الحي، محاولات socket) —
  ولا تثبت ممارسة Plan أو Reason أو بقية سلطات المادة 9.
- الحاجز الشبكي يرصد إنشاء ``socket.socket`` داخل عملية بايثون نفسها
  فقط — لا يعزل عمليات git الفرعية ولا يثبت انعدام كل اتصال.
- فحص الاستيرادات محصور بمسار المهمة الحي (المجلدات المسماة أدناه)
  وبأنماط استيراد معلنة — لا فحص شامل للشجرة.
"""
import ast
import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
KERNEL = REPO / "agos" / "agos-kernel"

#: وحدات أصناف الذكاء الاصطناعي المسماة (محلية — كعبات/محاكيات/منشئات
#: وصفية): يُفحص ألا يستوردها مسار المهمة الحي. الدستور يقيّد **السلطة**
#: لا الاستيراد نفسه — الفحص قرينة نطاق لا حكم امتثال.
AI_MODULES = ("providers.implementation", "providers.ai",
             "adapters.ai", "adapters.implementation")
#: مجلدات مسار المهمة الحي — بأسمائها الفعلية على القرص (لا تبديل شرطات).
LIVE_PATH_DIRS = ("capabilities", "pipeline", "mission-engine",
                  "intelligence", "bootstrapper", "discovery",
                  "agos_runtime")


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


def test_article9_10_live_mission_observations(local_git_repo):
    """مشاهدات مسار حي مختبر (إقلاع + مهمة تحليل مستودع عبر المدخل
    العام): الحاجز الشبكي يرصد إنشاء socket داخل عملية بايثون نفسها —
    بمُختبِر ضبط يثبت عمل الرصد قبل الإقلاع — ولا يُرصد أي إنشاء أثناء
    الإقلاع والمهمة؛ والمهمة تكتمل، وسجل الحياة يحوي LocalRepositoryProvider
    وحدها (لا مزوّد ذكاء مسجلاً)، وتظهر سجلات قرار داخلية (قدرة ومزوّد)
    ومهمة واحدة في rt.missions. هذه مشاهدات مسجلة — لا إثباتاً لممارسة
    سلطات المادة 9 ولا استنتاج انعدام ذكاء خارجي شامل."""
    code = f'''
    import json
    import socket

    # رصد إنشاء socket داخل عملية بايثون هذه فقط (لا عزل لعمليات git
    # الفرعية): كل إنشاء يُسجل ويُرفض — يُثبت عمله مُختبِرُ ضبط قبل
    # الإقلاع (محاولة اتصال تتوقع الرفض)، ثم يُفحص أن الإقلاع والمهمة
    # لم ينشئا أي socket أصلاً.
    NET_ATTEMPTS = []

    class _BlockedSocket(socket.socket):
        def __init__(self, *args, **kwargs):
            NET_ATTEMPTS.append("socket")
            raise RuntimeError("رصد الشبكة — لا إنشاء socket مسموح في هذا الفحص")

    socket.socket = _BlockedSocket
    barrier_control_ok = False
    try:
        socket.create_connection(("127.0.0.1", 1), timeout=1)
    except Exception:
        barrier_control_ok = True      # الرصد يعمل — المحاولة رُفضت وسُجلت
    control_attempts = len(NET_ATTEMPTS)
    NET_ATTEMPTS.clear()               # العد من الإقلاع فصاعداً

    import agos_runtime
    k = agos_runtime.boot()
    out = k.analyze({str(local_git_repo)!r}, branch="main")

    kinds = {{}}
    for r in (getattr(out, "decision_records", None) or []):
        kinds[getattr(r, "kind", "?")] = kinds.get(getattr(r, "kind", "?"), 0) + 1

    print(json.dumps({{
        "barrier_control_ok": barrier_control_ok,
        "control_attempts": control_attempts,
        "socket_creations_during_boot_and_mission": len(NET_ATTEMPTS),
        "state": out.state.value,
        "decision_kinds": kinds,
        "missions": len(k.missions),
        "providers": sorted(p.name for p in k.provider_registry.list_all()),
    }}))
    '''
    r = subprocess.run([sys.executable, "-c", textwrap.dedent(code)], cwd=KERNEL,
                       capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stderr[-2000:]
    out = json.loads(r.stdout.strip().splitlines()[-1])
    assert out["barrier_control_ok"] is True, "مُختبِر الضبط لم يثبت عمل الرصد"
    assert out["control_attempts"] >= 1, "محاولة الضبط لم تُسجل — الرصد غير مثبت"
    assert out["socket_creations_during_boot_and_mission"] == 0, (
        f"إنشاء socket داخل عملية بايثون أثناء الإقلاع والمهمة: {out}")
    assert out["state"] == "completed", out
    # مشاهدات مسجلة (لا ادعاء سلطات): سجلات قرار داخلية ومهمة واحدة
    # في المالك القائم، والسجل الحي لا يحوي مزوّد ذكاء مسجلاً.
    assert out["decision_kinds"].get("capability") == 1, out
    assert out["decision_kinds"].get("provider") == 1, out
    assert out["missions"] == 1, out
    assert out["providers"] == ["LocalRepositoryProvider"], out


def _resolved_import_names(rel_parts, node):
    """حل أسماء الاستيراد النسبي من موقع الملف: الصعود بمقدار
    ``level - 1`` من حزمة الملف — المستوى الأول يبقى داخل حزمة الملف
    نفسها (``from .helpers`` في ``pkg/sub/x.py`` = ``pkg.sub.helpers``)."""
    anchor = list(rel_parts)
    base = node.module or ""
    if node.level > 0:
        keep = len(anchor) - (node.level - 1)
        prefix = ".".join(anchor[:max(keep, 0)])
        base = (prefix + "." + base) if base else prefix
    names = [base] if base else []
    names += [f"{base}.{a.name}" for a in node.names]
    return names


def test_article9_10_relative_resolution_control():
    """ضبط حساب الاستيراد النسبي (أحمر أولاً): المستوى الأول يبقى داخل
    حزمة الملف، والثاني يصعد حزمة واحدة — هذا الضبط هو ما يضمن أن فحص
    الحصر يحل الأسماء كما تفسرها بايثون فعلاً."""
    import ast as _ast
    node_l1 = _ast.parse("from .helpers import X").body[0]
    assert _resolved_import_names(("intelligence", "sub"), node_l1) == [
        "intelligence.sub.helpers", "intelligence.sub.helpers.X"]
    node_l2 = _ast.parse("from ..helpers import X").body[0]
    assert _resolved_import_names(("intelligence", "sub"), node_l2) == [
        "intelligence.helpers", "intelligence.helpers.X"]
    node_l1_nomod = _ast.parse("from . import helpers").body[0]
    assert _resolved_import_names(("intelligence", "sub"), node_l1_nomod) == [
        "intelligence.sub", "intelligence.sub.helpers"]


def test_article9_10_live_path_modules_do_not_import_ai_classes():
    """فحص استيرادي محصور: ملفات مجلدات مسار المهمة الحي (بأسمائها
    الفعلية — ويُثبت وجود كل مجلد) لا تستورد وحدات أصناف الذكاء المسماة
    (استيراد مطلق أو ``from X import Y`` أو نسبي محسوب من موقع الملف) —
    قرينة نطاق على أن أصناف الذكاء المحلية لا تصل إلى المسار الحي؛
    الفحص لا يشمل بقية الشجرة ولا يعد حكم امتثال."""
    offenders = []
    for pkg in LIVE_PATH_DIRS:
        pkg_dir = KERNEL / pkg
        assert pkg_dir.is_dir(), f"مجلد مسار المهمة الحي غير موجود: {pkg_dir}"
        for py in pkg_dir.rglob("*.py"):
            rel_parts = py.relative_to(KERNEL).parts[:-1]
            tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
            for node in ast.walk(tree):
                candidates = []
                if isinstance(node, ast.Import):
                    candidates = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom):
                    if node.level > 0:  # نسبي — يُحل بموقع الملف (الضبط أعلاه)
                        candidates = _resolved_import_names(rel_parts, node)
                    else:
                        base = node.module or ""
                        # from X import Y → قد يكون Y وحدة (implementation)
                        candidates = ([base] if base else []) + [
                            f"{base}.{a.name}" if base else a.name
                            for a in node.names]
                for name in candidates:
                    if any(name == m or name.startswith(m + ".")
                           for m in AI_MODULES):
                        offenders.append(f"{py.relative_to(KERNEL)}: {name}")
    assert offenders == [], (
        f"مسار المهمة الحي يستورد وحدات أصناف الذكاء: {offenders}")
