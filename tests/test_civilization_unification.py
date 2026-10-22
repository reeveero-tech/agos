"""R-W1-009 — نقطة الدخول الحضارية الواحدة (ADR-0004).

المسارات الخمسة المتبيانة توحدت بالتفويض إلى `agos_kernel.civilization`:
الوصول من أي مسار يعيد الحضارة المعتمدة نفسها (هوية `is`)، والمنصة/v2
تركيبان فوقها بلا نسخ موازية، ودورة الحياة لا تنشر نسخة فاشلة ولا تمحو
حالة قائمة، والحزم محتوى يُتاح كتالوغه عبر الواجهة المعتمدة بلا ادعاء
تفعيل. (G2: المنشئات والطرق القديمة كلها تعمل كما هي.)
"""
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from agos.kernel.civilization import get_civilization, list_civilization_packs
from agos.kernel.platform_runtime import get_platform
from agos.kernel.v2 import get_platform_v2

REPO = Path(__file__).resolve().parents[1]

# الحقول المشتركة التي كانت المنصة تنسخها (حالة مزدوجة) — الآن تفوّض
SHARED_SUBSYSTEMS = [
    "knowledge", "memory", "brain", "core", "compiler", "graph_runtime",
    "parallel_executor", "verification", "approval", "governance",
    "collaboration", "organization", "trust",
]


def test_all_five_paths_reach_the_same_canonical_civilization():
    """هوية واحدة عبر المسارات الخمسة — لا حضارة موازية."""
    import agos.civilization as platform_civ

    canonical = get_civilization()
    assert get_civilization() is canonical            # النواة (singleton)
    assert get_platform().civilization is canonical    # platform_runtime
    assert get_platform_v2().platform.civilization is canonical  # v2
    assert platform_civ.get_civilization() is canonical  # حزمة المنصة agos.civilization
    # وحزمة الحزم محتوى — تُتاح عبر الواجهة المعتمدة نفسها (أدناه)


def test_platform_subsystems_delegate_to_the_civilization():
    """حقول الأنظمة المشتركة في المنصة هي أنظمة الحضارة نفسها — لا حالة مزدوجة."""
    civilization = get_civilization()
    platform = get_platform()
    for name in SHARED_SUBSYSTEMS:
        assert getattr(platform, name) is getattr(civilization, name), name


def test_operation_through_one_path_is_visible_through_another():
    """عمل حقيقي عبر واجهة يظهر أثره عبر الأخرى — التفويض حالة واحدة فعلية."""
    from agos_kernel.organization.runtime import OrganizationType

    civilization = get_civilization()
    platform = get_platform()

    org = platform.organization.create_organization(
        "unified-org", OrganizationType.BUSINESS_UNIT, "created via the platform path")
    # المنظمة التي أنشئت عبر المنصة مرئية عبر الحضارة المعتمدة مباشرة
    assert org.id in civilization.organization.organizations
    assert civilization.organization.organizations[org.id].name == "unified-org"

    # والمقاييس حضارية واحدة: ترجمة مهمة عبر المنصة تُحصى في الحضارة
    before = civilization.metrics.missions_compiled
    mission = platform.civilization.compile_mission("unify the civilization paths")
    assert mission is not None
    assert civilization.metrics.missions_compiled == before + 1


def test_v2_wraps_the_canonical_platform_singleton():
    """v2 غلاف فوق المنصة المعتمدة نفسها — لا منصة موازية."""
    assert get_platform_v2().platform is get_platform()


def test_inner_core_failure_blocks_publication_and_retry_works(monkeypatch):
    """فشل النواة الداخلية فشل للحضارة: لا ختم ولا نشر — والمحاولة بعد
    زوال السبب تنجح. (لا يُستبدل initialize كاملة — يُفشل النواة من الداخل.)"""
    import agos.kernel.civilization.runtime as civ_runtime
    import agos.kernel.core.autonomous as core_module

    published = civ_runtime._civilization
    original_core_init = core_module.AutonomousCore.initialize
    monkeypatch.setattr(civ_runtime, "_civilization", None)

    # النواة تفشل من الداخل → initialize يرجع False بلا ختم
    monkeypatch.setattr(
        core_module.AutonomousCore, "initialize",
        lambda self: False, raising=True)
    assert civ_runtime.CivilizationRuntime().initialize() is False

    with pytest.raises(RuntimeError, match="initialize\\(\\) failed"):
        get_civilization()
    assert civ_runtime._civilization is None, "broken civilization must not be published"

    # زوال السبب → النشر ينجح
    monkeypatch.setattr(
        core_module.AutonomousCore, "initialize",
        original_core_init, raising=True)
    retried = get_civilization()
    assert civ_runtime._civilization is retried
    assert retried._initialized is True

    monkeypatch.setattr(civ_runtime, "_civilization", published)  # استعادة


def test_core_initialized_once_across_all_wrappers(monkeypatch):
    """تهيئة النواة المشتركة مرة واحدة عبر كل المسارات: حضارة ثم منصة
    ثم v2 ثم غلاف منصة جديد فوق حضارة مهيأة — الختم المشترك يمنع
    إعادة التهيئة (لا استدعاءً مباشراً للنواة من المنصة بعد ADR-0004)."""
    import agos.kernel.core.autonomous as core_module
    from agos.kernel.platform_runtime import CivilizationPlatform

    calls = {"n": 0}
    original = core_module.AutonomousCore.initialize

    def counting(self):
        calls["n"] += 1
        return original(self)
    monkeypatch.setattr(core_module.AutonomousCore, "initialize", counting)

    # خط أساس بعد التهيئة الأولية (إن لم تكن قد حدثت في اختبار سابق)
    civilization = get_civilization()
    before = calls["n"]

    civilization.initialize()                    # idempotent — لا استدعاء جديد
    assert calls["n"] == before

    platform = get_platform()                   # فوق الحضارة المعتمدة
    platform.initialize()
    assert calls["n"] == before, "platform init must go through the civilization stamp"

    v2 = get_platform_v2()                      # غلاف فوق المنصة المعتمدة
    assert calls["n"] == before

    fresh_wrapper = CivilizationPlatform()       # غلاف جديد فوق حضارة مهيأة
    fresh_wrapper.initialize()
    assert calls["n"] == before, "a new wrapper must not re-initialize the shared core"

    # وحضارة معزولة صريحة تُهيئ نواتها الخاصة (استدعاء إضافي واحد — لا مشاركة)
    from agos.kernel.civilization.runtime import CivilizationRuntime
    isolated = CivilizationRuntime()
    assert isolated.initialize() is True
    assert calls["n"] == before + 1


def test_get_platform_failure_not_published_and_retry_works(monkeypatch):
    """المنصة أيضاً: لا نشر غلاف فاشل — تشخيص باسم الفشل وإعادة محاولة."""
    import agos.kernel.platform_runtime.runtime as platform_runtime

    published = platform_runtime._platform
    monkeypatch.setattr(platform_runtime, "_platform", None)

    monkeypatch.setattr(
        platform_runtime.CivilizationPlatform, "initialize",
        lambda self: False, raising=True)
    with pytest.raises(RuntimeError, match="initialize\\(\\) failed"):
        platform_runtime.get_platform()
    assert platform_runtime._platform is None

    monkeypatch.setattr(
        platform_runtime.CivilizationPlatform, "initialize",
        lambda self: True, raising=True)
    retried = platform_runtime.get_platform()
    assert platform_runtime._platform is retried

    monkeypatch.setattr(platform_runtime, "_platform", published)  # استعادة


def test_v2_wrapper_rejects_failed_platform(monkeypatch):
    """فشل تهيئة المنصة ينتقل صراحة — لا يُبنى غلاف v2 فوق منصة فاشلة."""
    import agos.kernel.platform_runtime.runtime as platform_runtime
    from agos.kernel.v2 import CivilizationPlatformV2

    broken = platform_runtime.CivilizationPlatform()
    monkeypatch.setattr(
        platform_runtime.CivilizationPlatform, "initialize",
        lambda self: False, raising=True)
    with pytest.raises(RuntimeError, match="initialize\\(\\) failed"):
        CivilizationPlatformV2(platform=broken)


def test_repeated_initialization_does_not_wipe_state():
    """التهيئة المتكررة (idempotent) لا تمحو حالة قائمة."""
    civilization = get_civilization()
    assert civilization.initialize() is True  # أولى
    marker = civilization.metrics.missions_compiled
    assert civilization.initialize() is True  # ثانية — تعود فوراً
    assert civilization.metrics.missions_compiled == marker

    platform = get_platform()
    assert platform.initialize() is True
    org_ids = set(civilization.organization.organizations)
    assert platform.initialize() is True  # غلاف v2 لا يعيد التشغيل
    assert set(civilization.organization.organizations) == org_ids


def test_old_constructors_keep_working():
    """G2: المنشئات والطرق العامة القديمة تعمل كما هي بلا تغيير أنواع."""
    from agos.kernel.platform_runtime import CivilizationPlatform
    from agos.kernel.v2 import CivilizationPlatformV2
    import agos.civilization as platform_civ

    platform = CivilizationPlatform()  # بلا معامل — كما كان
    assert platform.civilization is get_civilization()
    v2 = CivilizationPlatformV2()  # بلا معامل — كما كان
    assert v2.version == "2.0.0"

    # النموذج التنظيمي القديم لحزمة المنصة يعمل — وصوله للمعتمد عبر canonical
    org_civ = platform_civ.CivilizationRuntime()
    org = org_civ.create_default_organization("legacy-org", "Legacy Org")
    assert org_civ.get_organization("legacy-org") is org
    assert org.departments[0].name == "Architecture"
    assert org_civ.canonical is get_civilization()


def test_isolated_construction_with_explicit_civilization():
    """التركيب المعزول الصريح: منصة فوق حضارة خاصة — للاستخدام المعزول في الاختبارات."""
    from agos.kernel.civilization.runtime import CivilizationRuntime
    from agos.kernel.platform_runtime import CivilizationPlatform

    isolated_civ = CivilizationRuntime()
    isolated_platform = CivilizationPlatform(civilization=isolated_civ)
    # التفويض يعمل مع المعزولة أيضاً — أنظمتها هي أنظمة تلك الحضارة
    assert isolated_platform.civilization is isolated_civ
    assert isolated_platform.knowledge is isolated_civ.knowledge
    assert isolated_platform.organization is isolated_civ.organization
    # والمعزولة لا تنشر شيئاً في التجميع المعتمد
    assert isolated_civ is not get_civilization()


def test_pack_catalog_available_via_canonical_entry_no_activation_claim():
    """الحزم محتوى: الكتالوج متاح عبر الواجهة المعتمدة — بلا ادعاء تفعيل."""
    from agos_kernel.civilization_packs.library import get_pack_catalog

    packs = list_civilization_packs()
    assert len(packs) >= 1
    names = {p["name"] for p in packs}
    assert any("Software Engineering" in n for n in names)
    for pack in packs:
        assert set(pack) == {"id", "name", "version", "description", "domains"}
        assert pack["version"]  # بيانات وصفية حقيقية لا فراغ
    # الكتالوجان متطابقان (الواجهة المعتمدة والحزم — مصدر واحد)
    catalog = get_pack_catalog()
    assert len(catalog) == len(packs)
    assert {p["name"] for p in packs} == {p.metadata.name for p in catalog.values()}


def test_identity_across_paths_in_fresh_interpreters():
    """مفسّرات جديدة بترتيبات استيراد مختلفة — الهوية لا تعتمد على الترتيب."""
    for order in (
        "import agos.civilization as pc\n"
        "from agos.kernel.civilization import get_civilization as k\n"
        "print(pc.get_civilization() is k())",
        "from agos.kernel.v2 import get_platform_v2\n"
        "from agos.kernel.platform_runtime import get_platform\n"
        "print(get_platform_v2().platform.civilization is get_platform().civilization)",
        "from agos.kernel.platform_runtime import get_platform\n"
        "import agos.civilization as pc\n"
        "print(get_platform().civilization is pc.get_civilization())",
    ):
        result = subprocess.run(
            [sys.executable, "-c", textwrap.dedent(order)],
            capture_output=True, text=True, timeout=120, cwd=str(REPO))
        assert result.returncode == 0, result.stderr[-800:]
        assert result.stdout.strip() == "True", order


def test_separate_kernel_and_platform_civilization_packages_stay_distinct():
    """ADR-0001: الفصل المقصود بين حزمتي الحضارة يبقى — التوحيد بالتفويض لا بالطمس."""
    import agos.civilization as platform_civ
    import agos.kernel.civilization as kernel_civ

    assert platform_civ is not kernel_civ
    assert "agos-kernel" in kernel_civ.__file__
    assert "agos-kernel" not in platform_civ.__file__
    # لكن الوصول من الاثنين يعيد الحضارة المعتمدة نفسها
    assert platform_civ.get_civilization() is kernel_civ.get_civilization()
