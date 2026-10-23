"""R-W1-002 — توحيد المهمة: نموذج مرجعي واحد وربط داخلي في حدود الإنشاء.

المرحلة الأولى (هذا القسم): **توصيف السلوك القائم** قبل أي تعديل — كل تأكيد
هنا يقفل سلوك HEAD الحالي (619e5c0) فلا ينكسر بالتوحيد لاحقاً، ويمنع التغيير
الصامت للمخرجات القائمة (وحدة الهوية عبر مسارات الاستيراد المدعومة سلوك
قائم أيضاً بقاعدة ADR-0001 — يوصَّف هنا لا يستجد).
"""
import asyncio
import json
import subprocess
import sys
import textwrap
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agos" / "agos-kernel"))

from mission import Mission, MissionStatus  # noqa: E402
from mission_engine import MissionParser  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
KERNEL = REPO / "agos" / "agos-kernel"


# -- أ. توصيف القائم ---------------------------------------------------------------

def test_to_dict_omits_result_characterization():
    """to_dict لا يشمل result (سلوك قائم — تغييره يحتاج قرار توافق منفصل)."""
    m = Mission(name="x", result={"k": 1}, error="e")
    d = m.to_dict()
    assert "result" not in d
    assert d["error"] == "e"
    assert d["status"] == "pending"
    assert set(d) == {"id", "name", "description", "capability", "parameters",
                      "status", "created_at", "started_at", "completed_at", "error"}


def test_mission_parser_restores_five_fields_only():
    """parse(dict) يستعيد id/name/description/capability/parameters فقط — ليس واجهة
    استعادة كاملة (status/الأوقات/النتيجة تُفقد). توصيف قائم لا حكم."""
    data = {
        "id": "abc", "name": "n", "description": "d", "capability": "c",
        "parameters": {"p": 1}, "status": "completed",
        "created_at": "2020-01-01T00:00:00", "result": {"done": True}, "error": "x",
    }
    m = MissionParser.parse(data)
    assert m.id == "abc"
    assert m.name == "n"
    assert m.description == "d"
    assert m.capability == "c"
    assert m.parameters == {"p": 1}
    assert m.status is MissionStatus.PENDING  # لا يُستعاد
    assert m.result is None  # لا يُستعاد
    assert m.created_at.year >= 2026  # طابع جديد — الأصل يُفقد


def test_products_platform_fake_result_shape():
    """منصة المنتج: التنفيذ صوري — الكائن يقول «executed» والمخرج يقول «completed»
    (دعويان مختلفتان للحدث نفسه — توصيف قائم)."""
    from agos.products.missions import UniversalMissionPlatform

    p = UniversalMissionPlatform()
    m = p.create_mission("demo", "Analyze")
    assert m.mission_id == "mission_demo_0"
    assert m.status == "pending"
    out = p.execute_mission(m.mission_id)
    assert out == {"id": m.mission_id, "status": "completed"}
    assert m.status == "executed"


def test_slice_get_results_shape():
    """مفاتيح نتيجة الشريحة كما هي — والهوية uuid نصي."""
    from agos.kernel.vertical_slices.repo_discovery.slice import RepositoryDiscoveryMission

    m = RepositoryDiscoveryMission(repo_path="/tmp")
    r = m._get_results()
    assert set(r) == {"status", "dna", "architecture", "dependencies",
                     "knowledge_objects", "report", "trust_score", "evidence", "timeline"}
    assert r["status"] == "pending"
    assert isinstance(m.id, str) and m.id


def test_fabric_mission_positional_signature():
    """ترتيب معاملات fabric.Mission الموضعية القائم (mission_id, mission_type, name)."""
    from agos.fabric.mission import Mission as FabricMission, MissionState, MissionType

    m = FabricMission("mid", MissionType.SINGLE, "name")
    assert m.mission_id == "mid"
    assert m.state is MissionState.PENDING
    assert m.graph == {}


def test_create_mission_returns_stored_dict_reference():
    """القاموس المعاد من create_mission هو المخزن نفسه (مرجع لا نسخة) — وتحديثات
    المستدعي على القاموس المعاد تُرى في المخزن. سلوك قائم يُحفظ."""
    from crossdomain.runtime import LongRunningMissionRuntime

    rt = LongRunningMissionRuntime()
    d = rt.create_mission("m1")
    d["custom"] = 1
    assert rt.missions["m1"]["custom"] == 1  # نفس الكائن
    assert rt.missions["m1"] is d


def test_checkpoint_shallow_copy_semantics_preserved():
    """نقطة الحفظ نسخة سطحية من المستوى الأول — القيم المتداخلة مراجع مشتركة.
    سلوك قائم يُوصَّف لا يُصلح ضمن هذا البند."""
    from crossdomain.runtime import LongRunningMissionRuntime, MissionState

    rt = LongRunningMissionRuntime()
    d = rt.create_mission("m1", initial_state={"nested": {"v": 1}})
    rt.start("m1")
    cid = rt.checkpoint("m1")
    d["state"]["nested"]["v"] = 2  # تعديل عبر القاموس المعاد
    # النسخة السطحية: المستوى الأول منفصل، المتداخل مشترك
    assert rt.missions["m1"]["status"] is MissionState.RUNNING
    assert rt.recover("m1", cid)
    assert rt.missions["m1"]["state"]["nested"]["v"] == 2  # المتداخل بقى مشتركاً


def test_mission_service_dict_shape():
    """خدمة المنتج ترجع قواميس بلا خزن — توصيف الشكل القائم."""
    from agos.products import MissionService

    s = MissionService()
    out = s.create("proj", "demo", "Analyze")
    assert out == {"id": "mission_demo", "project_id": "proj",
                   "name": "demo", "type": "Analyze"}
    assert s.execute("mission_demo") == {"id": "mission_demo", "status": "executed"}


# -- ح. وحدة الصنف عبر مسارات الاستيراد (سلوك قائم بقاعدة ADR-0001) ------------------

def test_reference_class_identity_across_import_paths():
    import agos.kernel.mission as ns_path
    import agos_kernel.mission as pkg_path
    import mission as bare_path

    assert bare_path.Mission is pkg_path.Mission
    assert pkg_path.Mission is ns_path.Mission


def test_reference_class_identity_with_import_order_variation():
    """الهوية واحدة مهما اختلف ترتيب الاستيراد — مفسر جديد لكل ترتيب."""
    orders = [
        "import mission, agos_kernel.mission, agos.kernel.mission",
        "import agos_kernel.mission, agos.kernel.mission, mission",
        "import agos.kernel.mission, mission, agos_kernel.mission",
    ]
    for order in orders:
        r = subprocess.run(
            [sys.executable, "-c", textwrap.dedent(f"""
                import sys
                sys.path.insert(0, {str(KERNEL)!r})
                {order}
                assert mission.Mission is agos_kernel.mission.Mission
                assert agos_kernel.mission.Mission is __import__(
                    'agos.kernel.mission', fromlist=['Mission']).Mission
                print('ok')
            """)],
            cwd=str(REPO), capture_output=True, text=True, timeout=120,
        )
        assert r.returncode == 0, r.stderr[-2000:]
        assert r.stdout.strip() == "ok"


# -- ب. الربط بـ fabric (المرجع المحفوظ والتفويض الفعلي — ADR-0007) -----------------

def test_fabric_creation_establishes_reference_via_spy(monkeypatch):
    """حد الإنشاء القائم نفسه ينشئ المرجع النووي — تجسس على منشئ الصنف المرجعي
    (يفشل إن أُزيل استعمال المرجع من المسار)."""
    import agos_kernel.mission as km
    created = []
    real_init = km.Mission.__init__

    def spy_init(self, *a, **kw):
        created.append(kw.get("id"))
        real_init(self, *a, **kw)

    monkeypatch.setattr(km.Mission, "__init__", spy_init)
    from agos.fabric.mission import Mission as FabricMission, MissionType

    m = FabricMission("mid", MissionType.SINGLE, "nm")
    assert created == ["mid"]  # حد الإنشاء استخدم المرجع فعلياً
    assert m.canonical.id == "mid"


def test_fabric_held_reference_reflects_execute_transition():
    """المرجع المحتفظ به يتسق بعد تحديث مدعوم عبر الواجهة القديمة (execute)."""
    from agos.fabric.mission import MissionRuntime, MissionType

    rt = MissionRuntime()
    m = rt.create("mid", MissionType.SINGLE, "nm")
    ref = m.canonical
    assert m.canonical is ref  # إعادة الوصول تعيد المرجع نفسه — لا مهمة أخرى
    assert rt.execute("mid") is True
    assert ref.status is MissionStatus.RUNNING  # الملخص انعكس
    assert ref.started_at is not None  # البدء خُتم مرة
    assert ref.lifecycle.fine_state == "running"  # الحالة الدقيقة على الرابط
    assert ref.lifecycle.domain == "fabric"


def test_fabric_shared_field_writes_reach_reference():
    """الكتابة عبر أسماء الحقول القديمة (واجهات توافق) تصل إلى المرجع، والقراءة منه."""
    from agos.fabric.mission import Mission as FabricMission, MissionType

    m = FabricMission("mid", MissionType.SINGLE, "nm")
    ref = m.canonical
    assert m.created_at is ref.created_at  # الطابع الأصلي نفسه — لا توليد جديد
    m.name = "renamed"
    assert ref.name == "renamed"
    assert m.name == "renamed"
    m.mission_id = "mid2"
    assert ref.id == "mid2"
    assert m.mission_id == "mid2"


def test_fabric_specialized_fields_stay_on_family():
    from agos.fabric.mission import Mission as FabricMission, MissionState, MissionType

    m = FabricMission("mid", MissionType.SINGLE, "nm", graph={"n": 1})
    ref = m.canonical
    assert m.mission_type is MissionType.SINGLE  # متخصص يبقى
    assert m.graph == {"n": 1}
    assert m.state is MissionState.PENDING
    assert ref.capability == ""  # لا استنتاج capability
    assert ref.parameters == {}  # لا حشر في parameters


def test_fabric_cancelled_after_running_keeps_last_phase():
    """الإلغاء يُحمل ولا يُختلق له مقابل: آخر طور فعلي معلوم يبقى، والحمل صريح."""
    from agos.fabric.mission import Mission as FabricMission, MissionState, MissionType

    m = FabricMission("mid", MissionType.SINGLE, "nm")
    m.state = MissionState.RUNNING  # حقل عام قابل للكتابة — واجهة قديمة
    m.state = MissionState.CANCELLED
    ref = m.canonical
    assert ref.status is MissionStatus.RUNNING  # آخر طور فعلي
    assert ref.lifecycle.fine_state == "cancelled"
    assert ref.lifecycle.summary_known is True


def test_fabric_fresh_cancelled_claims_no_execution_history():
    """مهمة تُنشأ CANCELLED مباشرة: يُحمل الإلغاء دون اختلاق تاريخ تنفيذي."""
    from agos.fabric.mission import Mission as FabricMission, MissionState, MissionType

    m = FabricMission("mid", MissionType.SINGLE, "nm", state=MissionState.CANCELLED)
    ref = m.canonical
    assert ref.lifecycle.fine_state == "cancelled"
    assert ref.lifecycle.summary_known is False  # PENDING الافتراضي ليس ادعاءً
    assert ref.status is MissionStatus.PENDING
    # إعادة إسناد الإلغاء لا تختلق معلومية: الكتابة التمهيدية للملخص لم تعد
    # تمر قبل الحدّ فيستخدمها اشتقاقاً لحاملٍ بمعلومية مختلقة
    m.state = MissionState.CANCELLED
    assert ref.lifecycle.fine_state == "cancelled"
    assert ref.lifecycle.summary_known is False
    assert ref.status is MissionStatus.PENDING


def test_fabric_paused_summary_running_with_carry():
    from agos.fabric.mission import Mission as FabricMission, MissionState, MissionType

    m = FabricMission("mid", MissionType.SINGLE, "nm")
    m.state = MissionState.PAUSED
    ref = m.canonical
    assert ref.status is MissionStatus.RUNNING  # في مجرى التنفيذ
    assert ref.lifecycle.fine_state == "paused"


def test_carry_lifecycle_unknown_state_raises():
    import agos_kernel.mission as km

    with pytest.raises(ValueError):
        km.carry_lifecycle("fabric", "zombified")


def test_carry_lifecycle_product_states_claim_no_execution_summary():
    import agos_kernel.mission as km

    summary, carrier = km.carry_lifecycle("product", "executed", execution_states=False)
    assert summary is MissionStatus.PENDING  # القيمة القديمة للتوافق
    assert carrier.fine_state == "executed"
    assert carrier.summary_known is False  # لا ادعاء ملخص تنفيذي
    summary2, carrier2 = km.carry_lifecycle("planning", None, execution_states=False)
    assert carrier2.fine_state is None  # غياب صريح لحالة تنفيذ
    assert carrier2.summary_known is False


# -- تصحيحات المراجع على التوصيف ----------------------------------------------------

def test_checkpoint_first_level_separation():
    """النسخة سطحية: المستوى الأول منفصل (يُستعاد)، المتداخل مشترك (يبقى مرئياً)."""
    from crossdomain.runtime import LongRunningMissionRuntime, MissionState

    rt = LongRunningMissionRuntime()
    d = rt.create_mission("m1", initial_state={"top": 1, "nested": {"v": 1}})
    rt.start("m1")
    cid = rt.checkpoint("m1")
    d["state"]["top"] = 99  # قيمة سطحية تُغير بعد الحفظ
    d["state"]["nested"]["v"] = 2  # قيمة متداخلة
    assert rt.recover("m1", cid)
    assert rt.missions["m1"]["state"]["top"] == 1  # استُعيدت (المستوى الأول منفصل)
    assert rt.missions["m1"]["state"]["nested"]["v"] == 2  # بقيت (المتداخل مشترك)
    assert rt.missions["m1"]["status"] is MissionState.RUNNING


def test_platform_execute_unregistered_id_behavior():
    """تنفيذ بمعرّف غير مسجل: لا استثناء — سلوك قائم يقفل قبل أي تخزين جديد."""
    from agos.products.missions import UniversalMissionPlatform

    p = UniversalMissionPlatform()
    out = p.execute_mission("nonexistent")
    assert out == {"id": "nonexistent", "status": "completed"}


def test_mission_service_execute_unregistered_id():
    from agos.products import MissionService

    s = MissionService()
    assert s.execute("anything") == {"id": "anything", "status": "executed"}


def test_mission_service_repeated_create_same_id():
    """تكرار create بالاسم نفسه يعيد القاموس نفسه الشكل — خدمة بلا تفرد معرفات."""
    from agos.products import MissionService

    s = MissionService()
    a = s.create("proj", "demo", "Analyze")
    b = s.create("proj", "demo", "Analyze")
    assert a == b  # تساوي السلسلة لا يبرر دمج مراجع — يوثق السلوك القائم


# -- تصحيحات المراجع على العقد والتفويض ---------------------------------------------

def test_carry_lifecycle_explicit_absence_without_previous():
    """الغياب الصريح (None) جزء من العقد — لا KeyError ولا ادعاء ملخص."""
    import agos_kernel.mission as km

    summary, carrier = km.carry_lifecycle("planning", None)
    assert summary is MissionStatus.PENDING
    assert carrier.fine_state is None
    assert carrier.summary_known is False


def test_carry_lifecycle_product_update_keeps_known_summary():
    """تحديث حالة منتج مع ملخص تنفيذي معلوم سابقاً: القيمة ومعلوميّته معاً
    تُحفظان ولا تُمحوان."""
    import agos_kernel.mission as km

    summary, carrier = km.carry_lifecycle(
        "product", "executed", execution_states=False,
        previous_summary=MissionStatus.COMPLETED,
    )
    assert summary is MissionStatus.COMPLETED  # القيمة بقيت
    assert carrier.summary_known is True  # ومعلوميّتها بقيت
    assert carrier.fine_state == "executed"


def test_fabric_paused_alone_does_not_fabricate_start_time():
    """حمل PAUSED وحده لا يختلق وقت بدء — الختم عند حد البدء الفعلي فقط."""
    from agos.fabric.mission import Mission as FabricMission, MissionState, MissionType

    m = FabricMission("mid", MissionType.SINGLE, "nm")
    m.state = MissionState.PAUSED
    assert m.canonical.status is MissionStatus.RUNNING
    assert m.canonical.lifecycle.fine_state == "paused"
    assert m.canonical.started_at is None  # لا اختلاق وقت بدء


def test_fabric_execute_stamps_start_once_and_does_not_replace():
    from agos.fabric.mission import MissionRuntime, MissionType

    rt = MissionRuntime()
    m = rt.create("mid", MissionType.SINGLE, "nm")
    ref = m.canonical
    assert rt.execute("mid") is True
    first = ref.started_at
    assert first is not None
    assert rt.execute("mid") is True  # تكرار التنفيذ
    assert ref.started_at is first  # الختم الأول لا يُستبدل


def test_fabric_unacceptable_state_write_rejected_without_mutation():
    """القيمة غير المقبولة تُرفض قبل التغيير: لا تتغير الحالة ولا الحامل."""
    from agos.fabric.mission import Mission as FabricMission, MissionState, MissionType

    m = FabricMission("mid", MissionType.SINGLE, "nm")
    ref = m.canonical
    before_state = m.state
    before_carrier = ref.lifecycle
    with pytest.raises(ValueError):
        m.state = "zombified"  # قيمة غير مقبولة — عبر الواجهة القديمة نفسها
    assert m.state is before_state  # لم تتغير
    assert ref.lifecycle is before_carrier  # والحامل لم يتغير


def test_fabric_constructor_timestamp_preserved_by_reference():
    """طابع المنشئ الصريح يُحفظ كما هو على المرجع (نفس الكائن)، والكتابة عبر
    الاسم القديم تصل."""
    from agos.fabric.mission import Mission as FabricMission, MissionType

    at = datetime(2026, 10, 23, 12, 0, tzinfo=timezone.utc)
    m = FabricMission("mid", MissionType.SINGLE, "nm", created_at=at)
    ref = m.canonical
    assert ref.created_at is at  # نفس الكائن — لا توليد ولا استبدال
    assert m.created_at is at
    at2 = datetime(2026, 10, 23, 13, 0, tzinfo=timezone.utc)
    m.created_at = at2
    assert ref.created_at is at2


def test_fabric_registration_reads_from_reference_identity():
    """التسجيل يقرأ الهوية من المرجع: تعديل المرجع مباشرة تنعكس قراءات الأسماء
    القديمة عليه، ومفتاح التسجيل يأتي من الهوية المرجعية."""
    from agos.fabric.mission import MissionGraph, Mission as FabricMission, MissionType

    m = FabricMission("mid", MissionType.SINGLE, "nm")
    ref = m.canonical
    ref.id = "re-id"
    ref.name = "re-name"
    assert m.mission_id == "re-id"  # الاسم القديم يقرأ من المرجع
    assert m.name == "re-name"
    graph = MissionGraph()
    graph.add(m)  # التسجيل عبر الواجهة القائمة
    assert graph.get("re-id") is m  # المفتاح من الهوية المرجعية


# -- ج. الربط بـ products (المنصة والخدمة — ADR-0007) -------------------------------

def test_products_creation_establishes_reference_via_spy(monkeypatch):
    """حد الإنشاء القائم (منشئ مهمة المنتج) ينشئ المرجع النووي — تجسس يفشل إن أُزيل."""
    import agos_kernel.mission as km
    created = []
    real_init = km.Mission.__init__

    def spy_init(self, *a, **kw):
        created.append(kw.get("id"))
        real_init(self, *a, **kw)

    monkeypatch.setattr(km.Mission, "__init__", spy_init)
    from agos.products.missions import Mission as ProductMission

    m = ProductMission("mid", "nm", "Analyze")
    assert created == ["mid"]
    assert m.canonical.id == "mid"


def test_products_registration_reads_from_reference():
    """التسجيل عبر الواجهة القائمة يقرأ الهوية من المرجع."""
    from agos.products.missions import MissionRegistry, Mission as ProductMission

    m = ProductMission("mid", "nm", "Analyze")
    ref = m.canonical
    ref.id = "re-id"
    assert m.mission_id == "re-id"  # الاسم القديم يقرأ من المرجع
    registry = MissionRegistry()
    registry.register(m)  # حد التسجيل القائم
    assert registry.get("re-id") is m  # المفتاح من الهوية المرجعية
    assert registry.list_all() == [m]


def test_products_execute_carries_product_state_without_execution_claim():
    from agos.products.missions import UniversalMissionPlatform

    p = UniversalMissionPlatform()
    m = p.create_mission("demo", "Analyze")
    ref = m.canonical
    out = p.execute_mission(m.mission_id)
    assert out == {"id": m.mission_id, "status": "completed"}  # المخرج كما هو حرفياً
    assert m.status == "executed"  # حالة المنتج على الكائن
    assert ref.status is MissionStatus.PENDING  # لا ادعاء تنفيذياً
    assert ref.lifecycle.fine_state == "executed"
    assert ref.lifecycle.summary_known is False


def test_products_shared_field_writes_reach_reference():
    from agos.products.missions import Mission as ProductMission

    m = ProductMission("mid", "nm", "Analyze")
    ref = m.canonical
    m.name = "renamed"
    assert ref.name == "renamed"
    m.mission_id = "mid2"
    assert ref.id == "mid2"
    at = datetime(2026, 10, 23, 12, 0, tzinfo=timezone.utc)
    m2 = ProductMission("x", "y", "Build", created_at=at)
    assert m2.canonical.created_at is at  # طابع المنشئ نفسه


def test_products_unacceptable_status_rejected_without_mutation():
    from agos.products.missions import Mission as ProductMission

    m = ProductMission("mid", "nm", "Analyze")
    ref = m.canonical
    before = m.status
    before_carrier = ref.lifecycle
    with pytest.raises(ValueError):
        m.status = "zombified"  # غير معروفة — عبر الواجهة القديمة نفسها
    assert m.status == before
    assert ref.lifecycle is before_carrier


def test_products_type_stays_specialized():
    from agos.products.missions import Mission as ProductMission

    m = ProductMission("mid", "nm", "Analyze")
    ref = m.canonical
    assert m.type == "Analyze"  # نوع المنتج متخصص يبقى
    assert ref.capability == ""  # لا استنتاج capability من نوع المنتج
    assert ref.parameters == {}


def test_mission_service_canonical_and_repeated_create_replaces():
    """التكرار بالمعرّف نفسه يستبدل المرجع المخزن — والمرجع المحتفظ به من الإنشاء
    الأول لا يُعدّل لمجرد تساوي السلاسل."""
    from agos.products import MissionService

    s = MissionService()
    s.create("proj", "demo", "Analyze")
    first = s.canonical("mission_demo")
    out2 = s.create("proj", "demo", "Analyze")
    assert out2 == {"id": "mission_demo", "project_id": "proj",
                   "name": "demo", "type": "Analyze"}
    second = s.canonical("mission_demo")
    assert second is not first  # استبدال — لا دمج
    assert first.id == "mission_demo" and first.name == "demo"  # الأول لم يُعدّل
    assert s.canonical("mission_demo") is second  # المسترجِع يعيد الأحدث


def test_mission_service_execute_unregistered_keeps_output_and_no_reference():
    from agos.products import MissionService

    s = MissionService()
    out = s.execute("nonexistent")
    assert out == {"id": "nonexistent", "status": "executed"}  # المخرج كما هو
    assert s.canonical("nonexistent") is None  # لا مرجع لما لم يُنشأ


# -- د. اختبار التكامل الحاسم: تنفيذ حي ثم تحديث منتج لا يمحو الملخص ---------------

def _git_repo(tmp_path):
    repo = tmp_path / "owner" / "sample"
    repo.mkdir(parents=True)
    (repo / "requirements.txt").write_text("flask\n")
    (repo / "app.py").write_text("import flask\n")
    for cmd in (["git", "init", "-q", "-b", "main"], ["git", "add", "-A"],
                ["git", "-c", "user.email=t@t", "-c", "user.name=t",
                 "commit", "-qm", "init"]):
        subprocess.run(cmd, cwd=repo, check=True, capture_output=True)
    return repo


def _live_execution_then_product_update(tmp_path, product_wiring):
    """السيناريو المانع (مراجعة ADR-0007) عبر MissionManager القائم ببدائل
    حتمية: المعلومية تُفحص بعد التنفيذ الحي مباشرة ثم بعد تحديث المنتج."""
    repo = _git_repo(tmp_path)
    wiring = textwrap.indent(textwrap.dedent(product_wiring), "        ")
    code = textwrap.dedent(f"""
        import json, sys
        sys.path.insert(0, {str(KERNEL)!r})
        from core import AGOSKernel
        from mission import MissionStatus
        {wiring}
        iface, ref = create_product_mission()
        before_known = ref.lifecycle.summary_known
        ref.capability = "RepositoryAnalysis"
        ref.parameters = {{"url": "file://" + {str(repo)!r}}}
        k = AGOSKernel()
        with k:
            result = k.mission_manager.execute(ref)
        after_exec_ok = (result.status.value == "success"
                        and ref.status is MissionStatus.COMPLETED)
        after_exec_known = ref.lifecycle.summary_known  # قبل تحديث المنتج
        update_product_state(iface)  # تحديث حالة المنتج — الواجهة القديمة
        print(json.dumps({{
            "before_known": before_known,
            "after_exec_ok": after_exec_ok,
            "after_exec_known": after_exec_known,
            "after_update_status": ref.status.value,
            "after_update_known": ref.lifecycle.summary_known,
            "after_update_fine": ref.lifecycle.fine_state,
        }}))
    """)
    r = subprocess.run([sys.executable, "-c", code], cwd=str(REPO),
                       capture_output=True, text=True, timeout=180)
    assert r.returncode == 0, r.stderr[-2000:]
    return json.loads(r.stdout.strip().splitlines()[-1])


def _assert_live_flow(out):
    assert out["before_known"] is False  # حالة منتج بلا ادعاء قبل التنفيذ
    assert out["after_exec_ok"] is True  # التنفيذ الحي نجح والمرجع اكتمل
    assert out["after_exec_known"] is True  # المالك التنفيذي أثبت المعلومية (قبل التحديث)
    assert out["after_update_status"] == "completed"  # الملخص بقي صحيحاً
    assert out["after_update_known"] is True  # ومعلوميّته لم تُمحَ بالتحديث
    assert out["after_update_fine"] == "executed"  # وحالة المنتج محمولة


def test_platform_reference_live_execution_then_product_update(tmp_path):
    wiring = textwrap.dedent("""
        from agos.products.missions import UniversalMissionPlatform
        def create_product_mission():
            p = UniversalMissionPlatform()
            m = p.create_mission("demo", "Analyze")
            return p, m.canonical
        def update_product_state(p):
            p.execute_mission("mission_demo_0")
    """)
    _assert_live_flow(_live_execution_then_product_update(tmp_path, wiring))


def test_mission_service_reference_live_execution_then_product_update(tmp_path):
    wiring = textwrap.dedent("""
        from agos.products import MissionService
        def create_product_mission():
            s = MissionService()
            s.create("proj", "demo", "Analyze")
            return s, s.canonical("mission_demo")
        def update_product_state(s):
            s.execute("mission_demo")
    """)
    _assert_live_flow(_live_execution_then_product_update(tmp_path, wiring))


def test_mission_service_create_reads_shared_fields_from_reference():
    """القاموس المعاد حقوله المشتركة من المرجع المخزن نفسه (لا كائن جانبي)،
    ومفتاح التخزين هو هوية المرجع، والقراءة حية."""
    from agos.products import MissionService

    s = MissionService()
    out = s.create("proj", "demo", "Analyze")
    ref = s.canonical(out["id"])
    assert ref is not None
    assert out["id"] == ref.id
    assert out["name"] == ref.name
    assert s._references[out["id"]] is ref  # مفتاح التخزين = هوية المرجع
    ref.name = "live-name"
    assert s.canonical("mission_demo").name == "live-name"  # قراءة حية


def test_mission_service_execute_updates_reference_carrier():
    """حمل حالة المنتج على المرجع مثبت سلوكياً: حذف كتلة التحديث يُفشل الاختبار."""
    from agos.products import MissionService

    s = MissionService()
    s.create("proj", "demo", "Analyze")
    ref = s.canonical("mission_demo")
    out = s.execute("mission_demo")
    assert out == {"id": "mission_demo", "status": "executed"}  # المخرج كما هو
    assert s.canonical("mission_demo") is ref  # نفس المرجع — لا استبدال عند التنفيذ
    assert ref.lifecycle.fine_state == "executed"  # الحمل حدث فعلاً
    assert ref.lifecycle.summary_known is False  # بلا ادعاء تنفيذي
    assert ref.status is MissionStatus.PENDING  # لا اختلاق نجاح
    assert ref.started_at is None and ref.completed_at is None  # لا اختلاق أوقات


def test_mission_service_create_dict_comes_from_reference_spy(monkeypatch):
    """تجسس يغيّر id/name على المرجع أثناء إنشائه إلى قيمتين مميزتين — القاموس
    المعاد يحملهما (مقروء من المرجع لا من المتغيرات المحلية)، والاسترجاع بالمعرّف
    المعدّل يعيد المرجع الملتقط، والمعرّف المحلي ليس مفتاح التخزين."""
    import agos_kernel.mission as km
    captured = []
    real_init = km.Mission.__init__

    def mutating_init(self, *a, **kw):
        real_init(self, *a, **kw)
        self.id = "spy-id"
        self.name = "spy-name"
        captured.append(self)

    monkeypatch.setattr(km.Mission, "__init__", mutating_init)
    from agos.products import MissionService

    s = MissionService()
    out = s.create("proj", "demo", "Analyze")
    assert out["id"] == "spy-id"
    assert out["name"] == "spy-name"
    assert s.canonical("spy-id") is captured[-1]
    assert s.canonical("mission_demo") is None  # المعرّف المحلي ليس مفتاح التخزين
    assert "mission_demo" not in s._references


# -- هـ. الربط بـ mission_planner (طلب التخطيط — ADR-0007) ---------------------------

def test_planner_creation_establishes_reference_via_spy(monkeypatch):
    import agos_kernel.mission as km
    created = []
    real_init = km.Mission.__init__

    def spy_init(self, *a, **kw):
        created.append(kw.get("id"))
        real_init(self, *a, **kw)

    monkeypatch.setattr(km.Mission, "__init__", spy_init)
    from civilization.mission_planner.planner import Mission as PlannerMission

    m = PlannerMission()
    assert created == [m.canonical.id]  # حد الإنشاء أنشأ المرجع


def test_planner_mission_delegates_shared_fields():
    from civilization.mission_planner.planner import Mission as PlannerMission

    m = PlannerMission(objective="obj", description="d")
    ref = m.canonical
    assert m.mission_id == ref.id
    assert m.description == ref.description
    assert m.created_at is ref.created_at  # طابع الإنشاء نفسه — لا توليد
    assert ref.name == ""  # الـobjective لا يُحوَّل اسماً
    assert ref.capability == ""  # ولا capability
    assert m.objective == "obj"  # متخصص يبقى
    assert m.constraints == [] and m.priority == "medium"
    assert m.deadline == "" and m.metadata == {}


def test_planner_request_execution_state_explicit_absence():
    """طلب التخطيط لا يحمل حالة تنفيذ: غياب صريح مميز بنيوياً — لا ادعاء PENDING
    ولا أوقات تنفيذ مختلقة."""
    from civilization.mission_planner.planner import Mission as PlannerMission

    m = PlannerMission()
    ref = m.canonical
    assert ref.lifecycle.domain == "planning"
    assert ref.lifecycle.fine_state is None
    assert ref.lifecycle.summary_known is False
    assert ref.status is MissionStatus.PENDING  # القيمة الافتراضية — لا ادعاءً
    assert ref.started_at is None and ref.completed_at is None


def test_planner_plan_link_follows_reference():
    """إثبات MissionPlanner.plan نفسه: تعديل هوية المرجع قبل التخطيط — رابط الخطة
    ومعرّفات المهمة على واجباتها تتبع المرجع."""
    from civilization.mission_planner.planner import Mission as PlannerMission, MissionPlanner

    m = PlannerMission(objective="obj")
    ref = m.canonical
    ref.id = "re-planned"
    plan = MissionPlanner().plan(m, {"team": "x"})
    assert plan.mission_id == "re-planned"
    assert plan.tasks  # لا ينجح الدليل على قائمة فارغة
    assert all(t.mission_id == "re-planned" for t in plan.tasks)


def test_planning_does_not_touch_execution_state():
    """إنشاء الخطة ليس تنفيذ المهمة: حالة تنفيذ معلومة سابقة لا تُمحى بالتخطيط،
    وحالات Task تبقى حالات واجبات فرعية."""
    from civilization.mission_planner.planner import Mission as PlannerMission, MissionPlanner

    m = PlannerMission(objective="obj")
    ref = m.canonical
    ref.status = MissionStatus.COMPLETED  # مالك تنفيذي كتب الملخص
    assert ref.lifecycle.summary_known is True
    MissionPlanner().plan(m, {})  # التخطيط لا ينفّذ المهمة
    assert ref.status is MissionStatus.COMPLETED  # لم يُمحَ
    assert ref.lifecycle.summary_known is True  # ولا معلوميّته
    assert ref.lifecycle.fine_state is None  # غياب حالة التخطيط كما هو


# -- و. الربط بالشريحة (RepositoryDiscoveryMission — ADR-0007) -----------------------

def test_slice_creation_establishes_reference_via_spy(monkeypatch):
    import agos_kernel.mission as km
    created = []
    real_init = km.Mission.__init__

    def spy_init(self, *a, **kw):
        created.append(kw.get("id"))
        real_init(self, *a, **kw)

    monkeypatch.setattr(km.Mission, "__init__", spy_init)
    from agos.kernel.vertical_slices.repo_discovery.slice import RepositoryDiscoveryMission

    m = RepositoryDiscoveryMission(repo_path="/tmp")
    assert created == [m.id]  # حد الإنشاء أنشأ المرجع


def test_slice_delegates_shared_fields_and_keeps_specialized():
    from agos.kernel.vertical_slices.repo_discovery.slice import RepositoryDiscoveryMission

    m = RepositoryDiscoveryMission(repo_path="/tmp", repo_url="u")
    ref = m.canonical
    assert m.id == ref.id
    assert m.created_at is ref.created_at  # طابع الإنشاء نفسه
    assert m.repo_path == "/tmp"  # متخصص يبقى
    assert m.repo_url == "u"
    assert ref.lifecycle.domain == "slice"
    assert ref.lifecycle.fine_state == "pending"
    assert ref.lifecycle.summary_known is True  # مجال تنفيذي
    assert ref.capability == "" and ref.parameters == {}  # لا استنتاج ولا حشر
    assert m.canonical is ref  # إعادة الوصول تعيد نفسه


def test_slice_unacceptable_status_rejected_without_mutation():
    from agos.kernel.vertical_slices.repo_discovery.slice import RepositoryDiscoveryMission

    m = RepositoryDiscoveryMission(repo_path="/tmp")
    ref = m.canonical
    before_carrier = ref.lifecycle
    with pytest.raises(ValueError):
        m.status = "zombified"
    assert m.status == "pending"  # لم تتغير
    assert ref.lifecycle is before_carrier


def _fake_step(name, value):
    async def step(*a, **kw):
        return value
    return step


def test_slice_execute_success_updates_reference(monkeypatch):
    """execute() كاملة بالنجاح مع بدائل حتمية: المرجع المحتفظ به قبل الاستدعاء
    يعكس النتيجة والحالة والأوقات عند الأحداث الفعلية."""
    from dataclasses import dataclass, field as dc_field

    from agos.kernel.vertical_slices.repo_discovery.slice import RepositoryDiscoveryMission

    @dataclass
    class _FakeDNA:
        technology_stack: list = dc_field(default=None)

    @dataclass
    class _FakeDeps:
        dependencies: list = dc_field(default_factory=list)

    @dataclass
    class _FakeArch:
        patterns: list = dc_field(default_factory=list)

    @dataclass
    class _FakeTrust:
        overall: float = 0.9

    m = RepositoryDiscoveryMission(repo_path="/tmp/fake")
    ref = m.canonical
    for name, value in [
        ("_clone_repository", "/tmp/fake"),
        ("_fingerprint_repository", _FakeDNA()),
        ("_detect_technologies", []),
        ("_analyze_dependencies", _FakeDeps()),
        ("_extract_architecture", _FakeArch()),
        ("_extract_knowledge", []),
        ("_generate_report", None),
        ("_calculate_trust_score", _FakeTrust()),
        ("_generate_evidence", None),
    ]:
        monkeypatch.setattr(m, name, _fake_step(name, value))
    result = asyncio.run(m.execute())
    assert result["status"] == "completed"  # شكل النتيجة كما هو
    assert set(result) == {"status", "dna", "architecture", "dependencies",
                           "knowledge_objects", "report", "trust_score",
                           "evidence", "timeline"}
    assert ref.status is MissionStatus.COMPLETED
    assert ref.lifecycle.fine_state == "completed"
    assert ref.started_at is not None  # ختم عند حدث البدء الفعلي
    assert ref.completed_at is not None  # وعند الاكتمال الفعلي
    assert ref.result is result  # النتيجة على المرجع


def test_slice_execute_failure_updates_reference_and_raises(monkeypatch):
    """execute() بالفشل: المرجع يُحدَّث (اكتمال + خطأ) مع استمرار رفع الاستثناء الأصلي."""
    from agos.kernel.vertical_slices.repo_discovery.slice import RepositoryDiscoveryMission

    m = RepositoryDiscoveryMission(repo_path="/tmp/fake")
    ref = m.canonical

    async def _boom(*a, **kw):
        raise RuntimeError("boom")

    async def _clone(*a, **kw):
        return "/tmp/fake"

    monkeypatch.setattr(m, "_clone_repository", _clone)
    monkeypatch.setattr(m, "_fingerprint_repository", _boom)
    with pytest.raises(RuntimeError, match="boom"):  # الاستثناء الأصلي يُرفع
        asyncio.run(m.execute())
    assert m.status == "failed"
    assert ref.status is MissionStatus.FAILED
    assert ref.lifecycle.fine_state == "failed"
    assert ref.error == "boom"  # الخطأ على المرجع
    assert ref.completed_at is not None  # الاكتمال (انتهاء) خُتم
    assert any(s["status"] == "failed" for s in m.timeline.steps)  # خطوة الخطأ كما هي


# -- ز. الربط بالطويلة (crossdomain — ADR-0007) -------------------------------------

def test_longrunning_creation_establishes_reference_via_spy(monkeypatch):
    import agos_kernel.mission as km
    created = []
    real_init = km.Mission.__init__

    def spy_init(self, *a, **kw):
        created.append(kw.get("id"))
        real_init(self, *a, **kw)

    monkeypatch.setattr(km.Mission, "__init__", spy_init)
    from crossdomain.runtime import LongRunningMissionRuntime

    rt = LongRunningMissionRuntime()
    d = rt.create_mission("m1")
    assert created == ["m1"]
    assert rt.canonical_mission("m1").id == "m1"
    assert rt.canonical_mission("m1") is d.canonical


def test_longrunning_record_is_stored_dict_and_old_types_preserved():
    """السجل المعاد هو المخزن نفسه (مرجع لا نسخة) وأنواع الواجهة القديمة محفوظة:
    تعدادات وحالات نصية ISO ساذجة (لا منطقة زمنية تُلصق)."""
    from crossdomain.runtime import LongRunningMissionRuntime, MissionState

    rt = LongRunningMissionRuntime()
    d = rt.create_mission("m1")
    assert rt.missions["m1"] is d  # السلوك القائم
    assert isinstance(d["status"], MissionState)  # تعداد كما كان
    assert isinstance(d["created_at"], str) and "+" not in d["created_at"]  # ساذج
    ref = rt.canonical_mission("m1")
    assert ref.created_at.tzinfo is None  # حُفظ ساذجاً على المرجع — لا UTC تُلصق
    assert d["created_at"] == ref.created_at.isoformat()  # نفس القيمة المكتوبة فعلاً


def test_longrunning_held_reference_consistent_via_runtime_methods(monkeypatch):
    """المرجع المحتفظ به يتسق عبر مناهج التشغيل: start يختم البدء بالطابع الذي
    كتبته العملية نفسها (لا قراءة ثانية للساعة)."""
    from crossdomain.runtime import LongRunningMissionRuntime, MissionState

    rt = LongRunningMissionRuntime()
    d = rt.create_mission("m1")
    ref = rt.canonical_mission("m1")
    from crossdomain import runtime as crossdomain_runtime

    # ساعة حتمية متتابعة القيم: القراءة الأولى t1 (started_at)، والتالية t2
    # (حدث الخط الزمني — قراءة مشروعة). المرجع يجب أن يحمل t1 — ختم مستقل
    # ثانٍ (t2) يكشفه الاختبار فوراً.
    ticks = iter(datetime(2026, 10, 23, 10, 0, i) for i in range(20))

    class _SeqClock:
        @staticmethod
        def now():
            return next(ticks)

        @staticmethod
        def fromisoformat(s):
            return datetime.fromisoformat(s)

    monkeypatch.setattr(crossdomain_runtime, "datetime", _SeqClock)
    assert rt.start("m1") is True
    assert ref.status is MissionStatus.RUNNING
    assert ref.lifecycle.fine_state == "running"
    written = dict.__getitem__(d, "started_at")
    assert written == "2026-10-23T10:00:00"  # t1 — القراءة الأولى للساعة
    assert ref.started_at == datetime.fromisoformat(written)  # المرجع من t1 لا t2
    rt.pause("m1")
    assert ref.status is MissionStatus.RUNNING  # في مجرى التنفيذ
    assert ref.lifecycle.fine_state == "paused"
    rt.resume("m1")
    assert ref.lifecycle.fine_state == "running"


def test_longrunning_held_reference_consistent_via_returned_record_writes():
    """الكتابة عبر السجل المعاد نفسه تصل المرجع — كل نقاط الكتابة القاموسية
    (__setitem__ وحدها لا تكفي: update/setdefault/الدمج تتجاوزها قاموسياً)."""
    from crossdomain.runtime import LongRunningMissionRuntime, MissionState

    rt = LongRunningMissionRuntime()
    d = rt.create_mission("m1")
    ref = rt.canonical_mission("m1")
    # __setitem__
    d["status"] = MissionState.PAUSED
    assert ref.lifecycle.fine_state == "paused"
    # update
    d.update({"status": MissionState.RUNNING, "started_at": "2026-10-23T10:00:00"})
    assert ref.lifecycle.fine_state == "running"
    assert ref.started_at.isoformat() == "2026-10-23T10:00:00"
    # setdefault (المفتاح موجود — لا كتابة)
    before = ref.lifecycle.fine_state
    d.setdefault("status", MissionState.COMPLETED)
    assert ref.lifecycle.fine_state == before  # لم تُستبدل
    # مسار كتابة setdefault لمفتاح مرتبط: احذفه ثم أعده بقيمة مختلفة — يتغير
    # الحمل والملخص معاً (يفشل إن تجاوزت الكتابة المرجع)
    del d["status"]
    d.setdefault("status", MissionState.FAILED)
    assert ref.lifecycle.fine_state == "failed"
    assert ref.status is MissionStatus.FAILED
    # setdefault لمفتاح جديد
    d.setdefault("custom", {"k": 1})
    assert d["custom"] == {"k": 1}
    # الدمج |=
    d |= {"status": MissionState.COMPLETED}
    assert ref.lifecycle.fine_state == "completed"
    assert ref.status is MissionStatus.COMPLETED
    # الهوية عبر السجل
    d["id"] = "re-id"
    assert ref.id == "re-id"
    assert d["id"] == "re-id"


def test_longrunning_unacceptable_status_rejected_without_mutation():
    from crossdomain.runtime import LongRunningMissionRuntime, MissionState

    rt = LongRunningMissionRuntime()
    d = rt.create_mission("m1")
    ref = rt.canonical_mission("m1")
    before = d["status"]
    before_carrier = ref.lifecycle
    with pytest.raises(ValueError):
        d["status"] = "zombified"
    assert d["status"] is before  # لم تتغير
    assert ref.lifecycle is before_carrier


def test_longrunning_deletion_keeps_reference_and_old_dict_behavior():
    """حذف مفتاح مشترك: قراءته ترفع KeyError كما في القاموس القديم — والمرجع
    لا يُعدّل (هوية المهمة تبقى)."""
    from crossdomain.runtime import LongRunningMissionRuntime

    rt = LongRunningMissionRuntime()
    d = rt.create_mission("m1")
    ref = rt.canonical_mission("m1")
    del d["id"]
    with pytest.raises(KeyError):
        d["id"]  # noqa: B018 — قراءة مقصودة للتحقق
    assert "id" not in d  # كما في القاموس القديم
    assert ref.id == "m1"  # المرجع لم يُمس


def test_longrunning_recovery_stays_payload_only():
    """الاستعادة الحالية تستعيد الحمولة بنسخ سطحي فقط — لا استعادة دورة حياة
    ولا اختلاق انتقال جديد (حد التوحيد)."""
    from crossdomain.runtime import LongRunningMissionRuntime, MissionState

    rt = LongRunningMissionRuntime()
    d = rt.create_mission("m1", initial_state={"top": 1, "nested": {"v": 1}})
    rt.start("m1")
    cid = rt.checkpoint("m1")
    d["status"] = MissionState.PAUSED  # تغيّرت الدورة بعد الحفظ
    assert rt.recover("m1", cid)
    assert rt.missions["m1"]["state"]["top"] == 1  # الحمولة استُعيدت
    assert rt.missions["m1"]["status"] is MissionState.PAUSED  # الدورة لم تُستعد
    ref = rt.canonical_mission("m1")
    assert ref.lifecycle.fine_state == "paused"  # ولا انتقال مختلق


def test_longrunning_all_read_paths_follow_reference():
    """الاختبار المميّز (مراجعة ADR-0007): مصدر الاتساق هو المخزن نفسه (إشعار
    المزامنة عند حد كتابة المرجع) — فكل مسارات قراءة القاموس، الموروثة منها
    والمسار C المباشر (dict())، ترى قيم المرجع، والنص يُعاد كما كُتب حرفياً."""
    from crossdomain.runtime import LongRunningMissionRuntime, MissionState

    rt = LongRunningMissionRuntime()
    d = rt.create_mission("m1")
    ref = rt.canonical_mission("m1")
    ref.id = "re-id"  # تعديل مباشر على المرجع
    assert d["id"] == "re-id"
    assert d.get("id") == "re-id"
    assert dict(d.items())["id"] == "re-id"
    assert d.copy()["id"] == "re-id"
    assert dict(d)["id"] == "re-id"  # المسار C المباشر
    assert dict.__getitem__(d, "id") == "re-id"  # قراءة المخزن الفعلي
    # الطوابع: كتابة مباشرة على المرجع تتبعها كل القراءات
    ref.started_at = datetime(2026, 10, 23, 10, 0)
    assert d["started_at"] == "2026-10-23T10:00:00"
    assert d.get("started_at") == d["started_at"]
    assert dict(d.items())["started_at"] == d["started_at"]
    assert d.copy()["started_at"] == d["started_at"]
    assert dict(d)["started_at"] == d["started_at"]
    assert dict.__getitem__(d, "started_at") == d["started_at"]
    # والنص كما كُتب حرفياً (لا إعادة تمثيل بعد التحليل)
    d["started_at"] = "2026-10-23T10:00:00.000000"
    assert d["started_at"] == "2026-10-23T10:00:00.000000"
    assert d.get("started_at") == "2026-10-23T10:00:00.000000"
    assert dict(d.items())["started_at"] == "2026-10-23T10:00:00.000000"
    assert d.copy()["started_at"] == "2026-10-23T10:00:00.000000"
    assert dict(d)["started_at"] == "2026-10-23T10:00:00.000000"
    assert dict.__getitem__(d, "started_at") == "2026-10-23T10:00:00.000000"
    # items عرض حي كما في عقد القاموس الأصلي — لا لقطة
    view = d.items()
    d["probe"] = 1
    assert ("probe", 1) in view
    # pop يرد القيمة ويزيل المحلي — والمرجع يبقى
    popped = d.pop("id")
    assert popped == "re-id"
    assert ref.id == "re-id"
    with pytest.raises(KeyError):
        d["id"]  # noqa: B018
    # المساواة على المخزن المتسق
    d2 = rt.create_mission("m2")
    assert d2 == dict(d2.items())


def test_slice_reexecution_fail_then_success(monkeypatch):
    """تسلسل فشل→نجاح على المرجع نفسه: خطأ التشغيل السابق يُمسح ولا يبقى سجلاً."""
    from dataclasses import dataclass, field as dc_field

    from agos.kernel.vertical_slices.repo_discovery.slice import RepositoryDiscoveryMission

    @dataclass
    class _FakeDNA:
        technology_stack: list = dc_field(default=None)

    @dataclass
    class _FakeDeps:
        dependencies: list = dc_field(default_factory=list)

    @dataclass
    class _FakeArch:
        patterns: list = dc_field(default_factory=list)

    @dataclass
    class _FakeTrust:
        overall: float = 0.9

    m = RepositoryDiscoveryMission(repo_path="/tmp/fake")
    ref = m.canonical

    async def _boom(*a, **kw):
        raise RuntimeError("boom")

    async def _clone(*a, **kw):
        return "/tmp/fake"

    monkeypatch.setattr(m, "_clone_repository", _clone)
    monkeypatch.setattr(m, "_fingerprint_repository", _boom)
    with pytest.raises(RuntimeError, match="boom"):
        asyncio.run(m.execute())
    assert ref.error == "boom" and ref.result is None
    # ثم النجاح على المرجع نفسه
    for name, value in [
        ("_fingerprint_repository", _FakeDNA()),
        ("_detect_technologies", []),
        ("_analyze_dependencies", _FakeDeps()),
        ("_extract_architecture", _FakeArch()),
        ("_extract_knowledge", []),
        ("_generate_report", None),
        ("_calculate_trust_score", _FakeTrust()),
        ("_generate_evidence", None),
    ]:
        monkeypatch.setattr(m, name, _fake_step(name, value))
    result = asyncio.run(m.execute())
    assert ref.status is MissionStatus.COMPLETED
    assert ref.error is None  # خطأ التشغيل السابق مُسح
    assert ref.result is result  # نتيجة التنفيذ الحالي
    assert ref.completed_at is not None


def test_slice_reexecution_success_then_fail(monkeypatch):
    """تسلسل نجاح→فشل على المرجع نفسه: نتيجة التشغيل السابق تُمسح عند الفشل."""
    from dataclasses import dataclass, field as dc_field

    from agos.kernel.vertical_slices.repo_discovery.slice import RepositoryDiscoveryMission

    @dataclass
    class _FakeDNA:
        technology_stack: list = dc_field(default=None)

    @dataclass
    class _FakeDeps:
        dependencies: list = dc_field(default_factory=list)

    @dataclass
    class _FakeArch:
        patterns: list = dc_field(default_factory=list)

    @dataclass
    class _FakeTrust:
        overall: float = 0.9

    m = RepositoryDiscoveryMission(repo_path="/tmp/fake")
    ref = m.canonical
    for name, value in [
        ("_clone_repository", "/tmp/fake"),
        ("_fingerprint_repository", _FakeDNA()),
        ("_detect_technologies", []),
        ("_analyze_dependencies", _FakeDeps()),
        ("_extract_architecture", _FakeArch()),
        ("_extract_knowledge", []),
        ("_generate_report", None),
        ("_calculate_trust_score", _FakeTrust()),
        ("_generate_evidence", None),
    ]:
        monkeypatch.setattr(m, name, _fake_step(name, value))
    result = asyncio.run(m.execute())
    assert ref.result is result

    async def _boom(*a, **kw):
        raise RuntimeError("second-boom")

    monkeypatch.setattr(m, "_fingerprint_repository", _boom)
    with pytest.raises(RuntimeError, match="second-boom"):
        asyncio.run(m.execute())
    assert ref.status is MissionStatus.FAILED
    assert ref.result is None  # نتيجة التشغيل السابق مُسحت
    assert ref.error == "second-boom"


def test_longrunning_summary_write_does_not_erase_fine_state():
    """كتابة الملخص (حتى إعادة كتابته نفسه) لا تمحو الحالة الدقيقة: للحالة
    الدقيقة مصدر واحد — الحامل، لا الاستنتاج العكسي من الملخص."""
    from crossdomain.runtime import LongRunningMissionRuntime, MissionState

    rt = LongRunningMissionRuntime()
    d = rt.create_mission("m1")
    ref = rt.canonical_mission("m1")
    d["status"] = MissionState.PAUSED
    ref.status = ref.status  # إعادة كتابة الملخص نفسه فقط
    assert ref.lifecycle.fine_state == "paused"
    assert d["status"] is MissionState.PAUSED
    assert dict(d)["status"] is MissionState.PAUSED
    assert ref.lifecycle.summary_known is True  # المعلومية ثبتت


def test_longrunning_carrier_is_immutable_replaced_at_boundaries():
    """الحامل غير قابل للتعديل الموضعي (يُرفض دون تغيير)؛ الاستبدال عبر حد
    الكتابة المعلن يحدث إشعار المزامنة فيبقى المرجع ومخزن السجل متسقين."""
    from dataclasses import replace

    from crossdomain.runtime import LongRunningMissionRuntime, MissionState

    rt = LongRunningMissionRuntime()
    d = rt.create_mission("m1")
    ref = rt.canonical_mission("m1")
    d["status"] = MissionState.PAUSED
    # التعديل الموضعي مرفوض دون تغيير
    with pytest.raises(AttributeError):  # FrozenInstanceError
        ref.lifecycle.fine_state = "waiting_for_input"
    assert ref.lifecycle.fine_state == "paused"
    assert d["status"] is MissionState.PAUSED
    # الاستبدال عبر حد الكتابة — يخطر السجل فيتبعه المخزن
    ref.lifecycle = replace(ref.lifecycle, fine_state="waiting_for_input")
    assert d["status"] is MissionState.WAITING_FOR_INPUT
    assert dict(d)["status"] is MissionState.WAITING_FOR_INPUT
    assert dict.__getitem__(d, "status") is MissionState.WAITING_FOR_INPUT


def test_longrunning_carrier_replacement_updates_summary_one_direction():
    """حدّ استبدال الحامل يطبّق الاتجاه الصحيح: الحالة الدقيقة التنفيذية →
    الملخص وفق مجالها وقواعد الحمل — استبدال الحامل يحدّث السجل والملخص معاً."""
    from dataclasses import replace

    from crossdomain.runtime import LongRunningMissionRuntime, MissionState

    rt = LongRunningMissionRuntime()
    d = rt.create_mission("m1")
    ref = rt.canonical_mission("m1")
    d["status"] = MissionState.PAUSED
    # استبدال بحالة تغيّر ملخصها فعلاً (كلتا الحالتين السابقتين تقابلان RUNNING)
    ref.lifecycle = replace(ref.lifecycle, fine_state="failed")

    assert ref.lifecycle.fine_state == "failed"
    assert d["status"] is MissionState.FAILED
    assert dict(d)["status"] is MissionState.FAILED
    assert ref.status is MissionStatus.FAILED
    assert ref.lifecycle.summary_known is True


def test_longrunning_invalid_carrier_replacement_rejected_without_change():
    """الاستبدال غير الصالح يُرفض قبل أي تغيير — لا رفعٌ من الإشعار بعد الحفظ
    ولا ابتلاع للفشل: المرجع والسجل يبقيان كما كانا."""
    from dataclasses import replace

    from crossdomain.runtime import LongRunningMissionRuntime, MissionState

    rt = LongRunningMissionRuntime()
    d = rt.create_mission("m1")
    ref = rt.canonical_mission("m1")
    d["status"] = MissionState.PAUSED
    ref.lifecycle = replace(ref.lifecycle, fine_state="failed")
    before = ref.lifecycle

    # حالة مجهولة — يرفضها عقد الحمل قبل أي كتابة
    with pytest.raises(ValueError):
        ref.lifecycle = replace(before, fine_state="zombified")
    assert ref.lifecycle is before
    assert d["status"] is MissionState.FAILED
    assert dict(d)["status"] is MissionState.FAILED

    # حالة منتج معروفة للحمل لكنها غير قابلة للتمثيل بتعداد الطويلة —
    # اعتراض السجل القبلي قبل الحفظ
    with pytest.raises(ValueError):
        ref.lifecycle = replace(before, fine_state="executed")
    assert ref.lifecycle is before
    assert d["status"] is MissionState.FAILED


def test_longrunning_absent_fine_state_rejected_for_record_linked():
    """استبدال حامل الطويلة بحالة غائبة (أو إزالة الحامل) مرفوض لمهمة مرتبطة
    بسجل — لا تُترك حالة السجل قديمة صامتة؛ والغياب يبقى مشروعاً للتخطيط."""
    from dataclasses import replace

    from crossdomain.runtime import LongRunningMissionRuntime, MissionState

    rt = LongRunningMissionRuntime()
    d = rt.create_mission("m1")
    ref = rt.canonical_mission("m1")
    d["status"] = MissionState.PAUSED

    with pytest.raises(ValueError):
        ref.lifecycle = None  # إزالة الحامل
    with pytest.raises(ValueError):
        ref.lifecycle = replace(ref.lifecycle, fine_state=None)  # غياب صريح
    assert ref.lifecycle.fine_state == "paused"  # لم يتغير
    assert d["status"] is MissionState.PAUSED


def test_longrunning_carry_rejection_leaves_no_half_transition():
    """كاتب السجل يعتمد الحامل عبر حدّ الاستبدال مرة واحدة — لا كتابة ملخص قبله:
    القيمة المعروفة لقواعد الحمل العامة لكنها ليست ضمن تعداد الطويلة يرفضها
    اعتراض السجل القبلي قبل أي كتابة، فيبقى المرجع والملخص والسجل كما كانوا."""
    from crossdomain.runtime import LongRunningMissionRuntime, MissionState

    rt = LongRunningMissionRuntime()
    d = rt.create_mission("m1")
    ref = rt.canonical_mission("m1")
    d["status"] = MissionState.FAILED
    before = ref.lifecycle

    # "created" معروفة لقواعد الحمل العامة، لكنها ليست ضمن تعداد الطويلة
    with pytest.raises(ValueError):
        d["status"] = "created"

    assert ref.lifecycle is before
    assert ref.status is MissionStatus.FAILED
    assert d["status"] is MissionState.FAILED
    assert dict(d)["status"] is MissionState.FAILED


def test_product_recarry_with_stale_snapshot_keeps_proven_knownness():
    """حدّ الاستبدال يعتمد الحامل المشتق لكل المجالات: إعادة حمل حالة منتج
    بلقطة حامل قديمة لا تمحو معلومية تنفيذ مثبتة — المعلومية من قواعد الحمل
    وحدّ الكتابة التنفيذي، لا من قيمة قديمة في الحامل المدخل."""
    from dataclasses import replace

    from agos_kernel.mission import Mission, MissionStatus, carry_lifecycle

    _, initial = carry_lifecycle("product", "pending", execution_states=False)
    ref = Mission(lifecycle=initial)
    old_carrier = ref.lifecycle
    assert old_carrier.summary_known is False

    # كتابة مستقلة من المالك التنفيذي: تثبت الملخص ومعلوميته
    ref.status = MissionStatus.COMPLETED
    assert ref.lifecycle.summary_known is True

    # إعادة حمل حالة منتج باستخدام لقطة الحامل السابقة
    ref.lifecycle = replace(old_carrier, fine_state="executed")

    assert ref.status is MissionStatus.COMPLETED
    assert ref.lifecycle.fine_state == "executed"
    assert ref.lifecycle.summary_known is True


def test_planning_absence_recarry_with_stale_snapshot_keeps_proven_knownness():
    """الغياب الصريح يمر بقواعد الحمل والمسار العادي: إعادة حمل الغياب بلقطة
    حامل قديمة لا تمحو معلومية تنفيذ مثبتة، والغياب الطازج بلا تنفيذ سابق يبقى
    غير معلوم (لا يصير الغياب معلوماً تلقائياً)."""
    from dataclasses import replace

    from agos_kernel.mission import Mission, MissionStatus, carry_lifecycle

    _, initial = carry_lifecycle("planning", None, execution_states=False)
    ref = Mission(lifecycle=initial)
    old_carrier = ref.lifecycle
    assert old_carrier.summary_known is False  # الغياب الطازج غير معلوم

    ref.status = MissionStatus.COMPLETED
    assert ref.lifecycle.summary_known is True

    # إعادة حمل الغياب الصريح بلقطة قديمة
    ref.lifecycle = replace(old_carrier)

    assert ref.status is MissionStatus.COMPLETED
    assert ref.lifecycle.fine_state is None
    assert ref.lifecycle.summary_known is True
