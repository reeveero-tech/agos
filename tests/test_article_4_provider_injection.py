"""أدلة تشغيلي — تقليص متبقي المادة 4 من خريطة أدلة ADR-0010 (الشريحة 0100).

منهج المشروع: أحمر أولاً ثم أدنى إصلاح.

المتبقي المعلن في صف المادة 4: «الإنشاء المباشر في foundation_extra وفرع
عدم التمرير في analyze_url لبقية المستدعين». المخالفة: خط المهمة يختار
المزوّد (سجل قرار موثق) لكن القدرات الثماني الباقية لا تعلن عقد تمريره —
فالمزوّد المحلي يُنشأ مباشرة وتُستدعى طرائق الصنف الخرساني (``Walk`` و
``clone_safety.clone`` مباشرة)، والرفض لا يفشل المهمة.

الإصلاح الأدنى (نمط 0097): عقد ``execute_with_provider`` على الثماني،
وعبور بعقود المهارات المعلنة. ضوابط المراجعة المعتمدة قبل التنفيذ:

- **إعلان مهارات صادق:** مهارات القدرة = ما تستخدمه فعلاً (الست: Clone +
  Walk — Read لم تعد تستخدم بعد توحيد المسح؛ وخط المعالجة والجينوم:
  Clone + Read عبر analyze_url). مزوّد يدعم العقد المعلن فقط يجب أن يخدم
  كل مدخلات القدرة.
- **توافق المدخلات:** المستودع الفارغ (بلا commits) كان مقبولاً عبر url —
  الاستنساخ بلا ميتاداتا (``require_metadata=False``) يحفظه؛ والمستودع
  المحلي بلا origin يبقى مقروءاً (مسح بلا ميتاداتا)؛ ودلالة ``branch=None``
  محفوظة (git يختار الافتراضي).
- **ملكية التنظيف:** المستهلك يحذف الجذر المملوك وحده — الوالد (أياً كان
  اسمه أو فراغه) لا يُمس (لا استنتاج ملكية من اسم أو فراغ)؛ والمنتج ينظف
  نسخته غير المسلَّمة عند فشل الميتاداتا.
"""
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
KERNEL = REPO / "agos" / "agos-kernel"

URL_CAPS = [
    "RepositoryProcessingPipeline",
    "CapabilityGenome",
    "SecurityScan",
    "LicenseAnalysis",
    "DocumentationAnalysis",
    "ConfigurationAnalysis",
    "InfrastructureAnalysis",
    "RepositoryDNAGeneration",
]
PATH_CAPS = [
    "SecurityScan",
    "LicenseAnalysis",
    "DocumentationAnalysis",
    "ConfigurationAnalysis",
    "InfrastructureAnalysis",
    "RepositoryDNAGeneration",
]
# مهارات معلنة متوقعة (إعلان صادق — يستخدم ما يعلن ويعلن ما يستخدم)
DECLARED = {
    "RepositoryProcessingPipeline": ["CloneRepository", "ReadRepository"],
    "CapabilityGenome": ["CloneRepository", "ReadRepository"],
    "SecurityScan": ["CloneRepository", "WalkRepository"],
    "LicenseAnalysis": ["CloneRepository", "WalkRepository"],
    "DocumentationAnalysis": ["CloneRepository", "WalkRepository"],
    "ConfigurationAnalysis": ["CloneRepository", "WalkRepository"],
    "InfrastructureAnalysis": ["CloneRepository", "WalkRepository"],
    "RepositoryDNAGeneration": ["CloneRepository", "WalkRepository"],
}
# ما يستخدم فعلاً في مهمة url (بعد الإصلاح)
URL_SKILLS_USED = {c: (DECLARED[c] if c not in
                       ("RepositoryProcessingPipeline", "CapabilityGenome")
                       else ["CloneRepository", "ReadRepository"])
                   for c in URL_CAPS}


def _git_repo(path: Path, default_branch: str = "main",
              commit: bool = True) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    (path / "requirements.txt").write_text("flask\n")
    (path / "app.py").write_text("import flask\nprint('hi')\n")
    env = ["-c", "user.email=t@t", "-c", "user.name=t"]
    cmds = [["git", "init", "-q", "-b", default_branch], ["git", "add", "-A"]]
    if commit:
        cmds.append(["git", *env, "commit", "-qm", "init"])
    for cmd in cmds:
        subprocess.run(cmd, cwd=path, check=True, capture_output=True)
    return path


@pytest.fixture(scope="module")
def sample_repo(tmp_path_factory) -> Path:
    return _git_repo(tmp_path_factory.mktemp("sample") / "sample")


@pytest.fixture(scope="module")
def trunk_repo(tmp_path_factory) -> Path:
    """فرعه الافتراضي ليس main — يثبت وصول branch=None وسلوكه المحفوظ."""
    return _git_repo(tmp_path_factory.mktemp("trunk") / "trunk",
                     default_branch="trunk")


@pytest.fixture(scope="module")
def empty_repo(tmp_path_factory) -> Path:
    """مستودع بلا أي commit — مدخل مقبول قبل التحويل يجب أن يبقى مقبولاً."""
    return _git_repo(tmp_path_factory.mktemp("empty") / "empty", commit=False)


@pytest.fixture(scope="module")
def no_origin_repo(tmp_path_factory) -> Path:
    """مستودع ملتزم بلا remote إطلاقاً — قراءته لا تشترط origin."""
    return _git_repo(tmp_path_factory.mktemp("noorigin") / "bare-local")


# ---------------------------------------------------------------------------
# العملية الفرعية أ: مهام url (الثماني) + الرفض + الملفات/اللقطة (عدّادات
# منفصلة) + ضوابط التوافق (فارغ، branch=None) + استنساخ ينجح ثم مسح يرفض
# ---------------------------------------------------------------------------
URL_PHASE_CODE = """
import json
import os
import sys
import providers
from providers import CloneRepositoryInput, ReadRepositoryInput

try:
    from providers import WalkRepositoryInput
except ImportError:
    WalkRepositoryInput = None

ORIGINAL_CALLS = []
_real_execute = providers.LocalRepositoryProvider.execute

def _recording_execute(self, skill_name, input_data):
    ORIGINAL_CALLS.append(skill_name)
    return _real_execute(self, skill_name, input_data)

providers.LocalRepositoryProvider.execute = _recording_execute

CONSTRUCTIONS = []
_real_init = providers.LocalRepositoryProvider.__init__

def _counting_init(self, *a, **kw):
    # اسم المتصل المباشر: «__init__» = بناء بديل يفوض (مشروع)،
    # غيره = إنشاء محلي مباشر خارج قرار المهمة (مخالف)
    CONSTRUCTIONS.append(sys._getframe(1).f_code.co_name)
    return _real_init(self, *a, **kw)

providers.LocalRepositoryProvider.__init__ = _counting_init

REFUSING = False
REFUSE_AFTER_CLONE = False
SUBSTITUTE_CALLS = []
LAST_CLONE = {}


class SubstituteRepositoryProvider:
    \"\"\"بديل باسم مميز — الاستبدال عبر السجل العام وحده (لا تعديل نواة).\"\"\"

    def __init__(self):
        self._inner = providers.LocalRepositoryProvider()
        # تفويض التنفيذ الحقيقي عبر الدالة الأصلية المحفوظة مباشرة —
        # عبور البديل لا يُحسب عبوراً للأصل (الفصل بالهوية لا بالاسم)
        self._inner_exec = _real_execute.__get__(self._inner)

    @property
    def name(self):
        return "SubstituteRepositoryProvider"

    def supports_skill(self, skill_name):
        return skill_name in ["CloneRepository", "ReadRepository",
                              "WalkRepository"]

    def execute(self, skill_name, input_data):
        entry = {"skill": skill_name, "input_type": type(input_data).__name__}
        known = {"CloneRepository": CloneRepositoryInput,
                 "ReadRepository": ReadRepositoryInput,
                 "WalkRepository": WalkRepositoryInput}
        if skill_name in known:
            entry["input_ok"] = (known[skill_name] is not None
                                 and isinstance(input_data, known[skill_name]))
        if skill_name == "CloneRepository":
            entry["branch"] = getattr(input_data, "branch", "unset")
        SUBSTITUTE_CALLS.append(entry)
        if skill_name == "CloneRepository" and REFUSING:
            raise RuntimeError("رفض مقصود للاختبار — البديل هو المنفذ المختار")
        result = self._inner_exec(skill_name, input_data)
        if skill_name == "CloneRepository" and REFUSE_AFTER_CLONE:
            # استنساخ ناجح بجار غير مملوك بجانب الجذر — المسح هو من سيرفض
            parent = os.path.dirname(result.path)
            neighbor = os.path.join(parent, "neighbor.txt")
            with open(neighbor, "w") as fh:
                fh.write("جار غير مملوك")
            LAST_CLONE["path"] = result.path
            LAST_CLONE["neighbor"] = neighbor
            return result
        if skill_name == "WalkRepository" and REFUSE_AFTER_CLONE:
            raise RuntimeError("رفض المسح بعد استنساخ ناجح — للاختبار")
        entry["output_type"] = type(result).__name__
        return result


import agos_runtime
k = agos_runtime.boot()
reg = k.provider_registry
assert reg.exists("LocalRepositoryProvider"), "الأصل غير مسجل في السجل العام"
reg.unregister("LocalRepositoryProvider")
reg.register(SubstituteRepositoryProvider())


def run_mission(cap, params):
    outcome = k.run({"name": "مهمة " + cap, "description": "وصف",
                     "capability": cap, "parameters": params})
    sel_cap = sel_prov = None
    for r in (getattr(outcome, "decision_records", None) or []):
        kind = getattr(r, "kind", None)
        if kind == "capability":
            sel_cap = getattr(r, "selected", None)
        elif kind == "provider":
            sel_prov = getattr(r, "selected", None)
    res = getattr(outcome, "result", None)
    facts = {}
    if isinstance(res, dict):
        if cap == "SecurityScan":
            facts = {"secrets_found": res.get("secrets_found"),
                     "scanned_files": res.get("scanned_files")}
        elif cap == "LicenseAnalysis":
            facts = {"license": res.get("license")}
        elif cap == "DocumentationAnalysis":
            facts = {"has_readme": res.get("has_readme")}
        elif cap == "ConfigurationAnalysis":
            facts = {"config_files": res.get("config_files")}
        elif cap == "InfrastructureAnalysis":
            facts = {"has_docker": res.get("has_docker")}
        elif cap == "RepositoryDNAGeneration":
            facts = {"primary_language": res.get("primary_language"),
                     "languages": res.get("languages")}
        elif cap == "RepositoryProcessingPipeline":
            uro = res.get("universal_repository_object") or {}
            facts = {
                "uro_files": sorted(f.get("path") for f in uro.get("files", [])),
                "uro_branch": uro.get("branch"),
                "uro_language": uro.get("primary_language"),
            }
        elif cap == "CapabilityGenome":
            facts = {"repository": res.get("repository")}
    return {
        "capability": cap,
        "state": outcome.state.value,
        "error": (str(getattr(outcome, "error", None))
                  if getattr(outcome, "error", None) is not None else None),
        "selected_capability": sel_cap,
        "selected_provider": sel_prov,
        "facts": facts,
        "substitute_calls": [e["skill"] for e in SUBSTITUTE_CALLS],
        "substitute_input_ok": [e.get("input_ok") for e in SUBSTITUTE_CALLS],
        "substitute_branches": [e.get("branch") for e in SUBSTITUTE_CALLS
                                if "branch" in e],
        "original_calls": list(ORIGINAL_CALLS),
    }


URL = {URL!r}
CAPS = {CAPS!r}
SKILLS_USED = {SKILLS_USED!r}

url_results = []
for cap in CAPS:
    SUBSTITUTE_CALLS.clear()
    ORIGINAL_CALLS.clear()
    url_results.append(run_mission(cap, {"url": URL, "branch": "main"}))

# طور الرفض: البديل الرافض هو المختار — الفشل بمسببه دون رجوع للمحلي
REFUSING = True
refusal_results = []
for cap in CAPS:
    SUBSTITUTE_CALLS.clear()
    ORIGINAL_CALLS.clear()
    refusal_results.append(run_mission(cap, {"url": URL, "branch": "main"}))
REFUSING = False

# الملفات واللقطة: عدّادات منفصلة لكل حالة — لا استدعاء ولا إنشاء قبل الحاجة
SUBSTITUTE_CALLS.clear()
ORIGINAL_CALLS.clear()
CONSTRUCTIONS.clear()
files_out = run_mission("SecurityScan", {
    "files": {"app.py": "import flask\\nprint('hi')\\n",
              "requirements.txt": "flask\\n"}})
files_constructions = len(CONSTRUCTIONS)
files_calls = list(SUBSTITUTE_CALLS)
files_original = list(ORIGINAL_CALLS)
SUBSTITUTE_CALLS.clear()
ORIGINAL_CALLS.clear()
CONSTRUCTIONS.clear()
snapshot_out = run_mission("SecurityScan", {
    "snapshot": {"root_path": None,
                 "files": {"app.py": "import flask\\nprint('hi')\\n"}}})
snapshot_constructions = len(CONSTRUCTIONS)
snapshot_calls = list(SUBSTITUTE_CALLS)
snapshot_original = list(ORIGINAL_CALLS)

# ضابط توافق: مستودع فارغ بلا commits — مقبول قبل التحويل يجب أن يبقى
SUBSTITUTE_CALLS.clear()
ORIGINAL_CALLS.clear()
empty_out = run_mission("SecurityScan", {"url": {EMPTY_URL!r}})

# ضابط توافق: branch=None يصل كما هو — فرع افتراضي ليس main يعمل
SUBSTITUTE_CALLS.clear()
ORIGINAL_CALLS.clear()
trunk_out = run_mission("SecurityScan", {"url": {TRUNK_URL!r}})

# استنساخ ينجح ثم المسح يرفض: تنظيف الجذر وبقاء الجار بلا رجوع للمحلي
REFUSE_AFTER_CLONE = True
SUBSTITUTE_CALLS.clear()
ORIGINAL_CALLS.clear()
clone_then_refuse = run_mission("SecurityScan", {"url": URL, "branch": "main"})
REFUSE_AFTER_CLONE = False
clone_refuse_report = {
    "state": clone_then_refuse["state"],
    "error": clone_then_refuse["error"],
    "clone_calls": [e["skill"] for e in SUBSTITUTE_CALLS],
    "root_cleaned": (LAST_CLONE.get("path") is not None
                     and not os.path.isdir(LAST_CLONE["path"])),
    "neighbor_survives": (LAST_CLONE.get("neighbor") is not None
                         and os.path.exists(LAST_CLONE["neighbor"])),
    "original_calls": list(ORIGINAL_CALLS),
}

print(json.dumps({
    "url": url_results,
    "refusal": refusal_results,
    "files": {"out": files_out, "constructions": files_constructions,
              "calls": [e["skill"] for e in files_calls],
              "original": files_original},
    "snapshot": {"out": snapshot_out, "constructions": snapshot_constructions,
                 "calls": [e["skill"] for e in snapshot_calls],
                 "original": snapshot_original},
    "empty": empty_out,
    "trunk": trunk_out,
    "clone_refuse": clone_refuse_report,
    "skills_used": SKILLS_USED,
}, ensure_ascii=False, default=str))
"""


# ---------------------------------------------------------------------------
# العملية الفرعية ب: مهام repo_path (الست) + بلا origin + مزوّد العقد المعلن
# ---------------------------------------------------------------------------
PATH_PHASE_CODE = """
import json
import providers

try:
    from providers import WalkRepositoryInput
except ImportError:
    WalkRepositoryInput = None

ORIGINAL_CALLS = []
_real_execute = providers.LocalRepositoryProvider.execute

def _recording_execute(self, skill_name, input_data):
    ORIGINAL_CALLS.append(skill_name)
    return _real_execute(self, skill_name, input_data)

providers.LocalRepositoryProvider.execute = _recording_execute

SUBSTITUTE_CALLS = []
DECLARED_CALLS = []


class SubstituteRepositoryProvider:
    def __init__(self):
        self._inner = providers.LocalRepositoryProvider()
        self._inner_exec = _real_execute.__get__(self._inner)

    @property
    def name(self):
        return "SubstituteRepositoryProvider"

    def supports_skill(self, skill_name):
        return skill_name in ["CloneRepository", "ReadRepository",
                              "WalkRepository"]

    def execute(self, skill_name, input_data):
        entry = {"skill": skill_name, "input_type": type(input_data).__name__}
        if skill_name == "WalkRepository":
            entry["input_ok"] = (WalkRepositoryInput is not None
                                 and isinstance(input_data, WalkRepositoryInput))
        SUBSTITUTE_CALLS.append(entry)
        return self._inner_exec(skill_name, input_data)


import agos_runtime
k = agos_runtime.boot()
reg = k.provider_registry

# إعلان المهارات كما هو في السجل (القدرات الثماني) — توكيد صدق الإعلان
declared = {}
for c in k.capability_registry.list_all():
    if c.name in {ALL_CAPS!r}:
        declared[c.name] = list(c.skills)

reg.unregister("LocalRepositoryProvider")
reg.register(SubstituteRepositoryProvider())


def run_mission(cap, params):
    outcome = k.run({"name": "مهمة " + cap, "description": "وصف",
                     "capability": cap, "parameters": params})
    sel_cap = sel_prov = None
    for r in (getattr(outcome, "decision_records", None) or []):
        kind = getattr(r, "kind", None)
        if kind == "capability":
            sel_cap = getattr(r, "selected", None)
        elif kind == "provider":
            sel_prov = getattr(r, "selected", None)
    res = getattr(outcome, "result", None)
    facts = {}
    if isinstance(res, dict):
        if cap == "SecurityScan":
            facts = {"secrets_found": res.get("secrets_found"),
                     "scanned_files": res.get("scanned_files")}
        elif cap == "LicenseAnalysis":
            facts = {"license": res.get("license")}
        elif cap == "DocumentationAnalysis":
            facts = {"has_readme": res.get("has_readme")}
        elif cap == "ConfigurationAnalysis":
            facts = {"config_files": res.get("config_files")}
        elif cap == "InfrastructureAnalysis":
            facts = {"has_docker": res.get("has_docker")}
        elif cap == "RepositoryDNAGeneration":
            facts = {"primary_language": res.get("primary_language"),
                     "languages": res.get("languages")}
    return {
        "capability": cap,
        "state": outcome.state.value,
        "error": (str(getattr(outcome, "error", None))
                  if getattr(outcome, "error", None) is not None else None),
        "selected_capability": sel_cap,
        "selected_provider": sel_prov,
        "facts": facts,
        "substitute_calls": [e["skill"] for e in SUBSTITUTE_CALLS],
        "substitute_input_ok": [e.get("input_ok") for e in SUBSTITUTE_CALLS],
        "original_calls": list(ORIGINAL_CALLS),
    }


PATH = {PATH!r}
PATH_CAPS = {PATH_CAPS!r}

path_results = []
for cap in PATH_CAPS:
    SUBSTITUTE_CALLS.clear()
    ORIGINAL_CALLS.clear()
    path_results.append(run_mission(cap, {"repo_path": PATH}))

# ضابط التوافق: مستودع ملتزم بلا origin — مدخل مقبول يجب أن يبقى مقروءاً
SUBSTITUTE_CALLS.clear()
ORIGINAL_CALLS.clear()
no_origin_out = run_mission("SecurityScan", {"repo_path": {NO_ORIGIN!r}})


# مزوّد يدعم العقد المعلن فقط: يخدم كل مدخلات القدرة (مسار وurl)
class DeclaredSkillsProvider:
    def __init__(self):
        self._inner = providers.LocalRepositoryProvider()
        self._inner_exec = _real_execute.__get__(self._inner)
        self._skills = list(declared["SecurityScan"])

    @property
    def name(self):
        return "DeclaredSkillsProvider"

    def supports_skill(self, skill_name):
        return skill_name in self._skills

    def execute(self, skill_name, input_data):
        DECLARED_CALLS.append(skill_name)
        return self._inner_exec(skill_name, input_data)


reg.unregister("SubstituteRepositoryProvider")
reg.register(DeclaredSkillsProvider())
declared_path_out = run_mission("SecurityScan", {"repo_path": PATH})
declared_url_out = run_mission("SecurityScan", {"url": PATH, "branch": "main"})

print(json.dumps({
    "declared": declared,
    "path": path_results,
    "no_origin": no_origin_out,
    "declared_only": {"path": declared_path_out, "url": declared_url_out,
                      "calls": list(DECLARED_CALLS)},
}, ensure_ascii=False, default=str))
"""


def _run_phase(code: str, tmp_dir: Path, **subs: str) -> dict:
    for key, val in subs.items():
        code = code.replace("{" + key + "!r}", repr(val))
    env = {**os.environ, "TMPDIR": str(tmp_dir)}
    r = subprocess.run([sys.executable, "-c", textwrap.dedent(code)],
                       cwd=KERNEL, capture_output=True, text=True,
                       timeout=600, env=env)
    assert r.returncode == 0, r.stderr[-3000:]
    return json.loads(r.stdout.strip().splitlines()[-1])


@pytest.fixture(scope="module")
def url_phase(sample_repo, empty_repo, trunk_repo, tmp_path_factory):
    return _run_phase(URL_PHASE_CODE, tmp_path_factory.mktemp("phase-url"),
                      URL=str(sample_repo),
                      EMPTY_URL=str(empty_repo), TRUNK_URL=str(trunk_repo),
                      CAPS=URL_CAPS, SKILLS_USED=URL_SKILLS_USED)


@pytest.fixture(scope="module")
def path_phase(sample_repo, no_origin_repo, tmp_path_factory):
    return _run_phase(PATH_PHASE_CODE, tmp_path_factory.mktemp("phase-path"),
                      PATH=str(sample_repo),
                      NO_ORIGIN=str(no_origin_repo), PATH_CAPS=PATH_CAPS,
                      ALL_CAPS=URL_CAPS)


def _find(rows, cap):
    for r in rows:
        if r["capability"] == cap:
            return r
    raise KeyError(cap)


def _assert_facts(cap, facts):
    """توكيد ملموس على حقيقة متوقعة من المستودع الصغير — لا مجرد وجود مخرج."""
    if cap == "SecurityScan":
        assert facts["secrets_found"] == 0, facts
        assert facts["scanned_files"] == 2, facts
    elif cap == "LicenseAnalysis":
        assert facts["license"] == "unknown", facts
    elif cap == "DocumentationAnalysis":
        assert facts["has_readme"] is False, facts
    elif cap == "ConfigurationAnalysis":
        assert facts["config_files"] == ["requirements.txt"], facts
    elif cap == "InfrastructureAnalysis":
        assert facts["has_docker"] is False, facts
    elif cap == "RepositoryDNAGeneration":
        assert facts["primary_language"] == "Python", facts
        assert facts["languages"] == ["Python"], facts
    elif cap == "RepositoryProcessingPipeline":
        assert facts["uro_files"] == ["app.py", "requirements.txt"], facts
        assert facts["uro_branch"] == "main", facts
        assert facts["uro_language"] == "Python", facts
    elif cap == "CapabilityGenome":
        assert facts["repository"]["name"] == "sample", facts
        assert facts["repository"]["branch"] == "main", facts


# ---------------------------------------------------------------------------
# url: البديل المختار يتلقى ما تستخدمه القدرة فعلاً — والأصل لا ينفذ
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("cap", URL_CAPS)
def test_article4_url_mission_uses_chosen_provider(cap, url_phase):
    """الأحمر أولاً: الاستبدال عبر السجل العام يجب أن يُحترم في تنفيذ القدرات
    الثماني — البديل يتلقى المهارات التي تستخدمها القدرة فعلاً بعقود مدخلهما
    المعلنة، والأصل لا ينفذ، والمهمة تكتمل بحقيقة متوقعة من المستودع."""
    r = _find(url_phase["url"], cap)
    assert r["state"] == "completed", r["error"]
    assert r["selected_provider"] == "SubstituteRepositoryProvider", (
        f"قرار الاختيار لا يخص البديل: {r['selected_provider']}")
    assert r["selected_capability"] == cap, (
        f"القدرة المختارة ليست المقصودة: {r['selected_capability']}")
    assert r["substitute_calls"] == url_phase["skills_used"][cap], (
        f"البديل لم يتلق ما تستخدمه القدرة: {r['substitute_calls']}")
    assert all(ok is True for ok in r["substitute_input_ok"]), r
    assert r["original_calls"] == [], (
        f"الأصل نفذ رغم الاستبدال عبر السجل: {r['original_calls']}")
    _assert_facts(cap, r["facts"])


# ---------------------------------------------------------------------------
# الرفض: فشل المهمة بمسببه دون رجوع إلى الإنشاء المحلي
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("cap", URL_CAPS)
def test_article4_refusal_has_no_local_fallback(cap, url_phase):
    """رفض البديل المختار يفشل المهمة بمسببه المعلل — لا رجوع إلى الإنشاء
    المحلي (راصد الأصل فارغ)، ومحاولة العبور مسجلة قبل الرفض."""
    r = _find(url_phase["refusal"], cap)
    assert r["state"] == "failed", (
        f"الرفض لم يفشل المهمة — رجوع للمحلي: {r}")
    assert r["error"] and "رفض مقصود" in r["error"], r["error"]
    assert r["selected_provider"] == "SubstituteRepositoryProvider"
    assert "CloneRepository" in r["substitute_calls"], (
        "لم تُسجل محاولة العبور عبر البديل قبل الرفض")
    assert r["original_calls"] == [], (
        f"رجوع إلى الأصل بعد رفض المختار: {r['original_calls']}")


# ---------------------------------------------------------------------------
# الملفات/اللقطة: عدّادات منفصلة — لا استدعاء ولا إنشاء قبل الحاجة
# ---------------------------------------------------------------------------
def test_article4_files_and_snapshot_skip_provider(url_phase):
    """مدخلات الملفات واللقطة لا تحتاج اكتساباً — لكل حالة عدّادها: لا
    استدعاء للمزوّد (البديل والأصل معاً) ولا إنشاء احتياطي قبل الحاجة."""
    for case in ("files", "snapshot"):
        block = url_phase[case]
        assert block["out"]["state"] == "completed", block["out"]["error"]
        assert block["calls"] == [], block["calls"]
        assert block["original"] == [], block["original"]
        assert block["constructions"] == 0, (
            f"إنشاء مزوّد (أي كان المتصل) في حالة {case} قبل معرفة أن "
            f"المدخل يحتاجه")
        facts = block["out"]["facts"]
        assert facts["secrets_found"] == 0, facts
        # عدّ مقيس لكل حالة: files تُقدم ملفين وsnapshot ملفاً واحداً
        expected = 2 if case == "files" else 1
        assert facts["scanned_files"] == expected, facts


# ---------------------------------------------------------------------------
# المسار المحلي: المسح عبر عقد WalkRepository — والأصل لا ينفذ
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("cap", PATH_CAPS)
def test_article4_local_path_walks_via_contract(cap, path_phase):
    """مسار repo_path يقرأ عبر عقد المسح المعلن بالمزوّد المختار — لا
    استدعاء لطريقة الصنف الخرساني مباشرة، والأصل لا ينفذ، والمخرج حقيقة
    متوقعة من المستودع."""
    r = _find(path_phase["path"], cap)
    assert r["state"] == "completed", r["error"]
    assert r["selected_capability"] == cap, r["selected_capability"]
    assert r["selected_provider"] == "SubstituteRepositoryProvider"
    assert r["substitute_calls"] == ["WalkRepository"], (
        f"المسح لم يمر عبر عقد المسح بالمختار: {r['substitute_calls']}")
    assert r["substitute_input_ok"] == [True], r["substitute_input_ok"]
    assert r["original_calls"] == [], r["original_calls"]
    _assert_facts(cap, r["facts"])


# ---------------------------------------------------------------------------
# إعلان مهارات صادق: مزوّد العقد المعلن فقط يخدم كل المدخلات
# ---------------------------------------------------------------------------
def test_article4_declared_skills_are_accurate(path_phase):
    """مهارات القدرة = ما تستخدمه فعلاً (إعلان صادق) — ومزوّد يدعم العقد
    المعلن فقط يخدم مدخلي repo_path وurl معاً دون طلب مهارة غير معلنة."""
    declared = path_phase["declared"]
    for cap, expected in DECLARED.items():
        assert declared.get(cap) == expected, (
            f"إعلان مهارات {cap} غير صادق: {declared.get(cap)}")
    block = path_phase["declared_only"]
    for case in ("path", "url"):
        out = block[case]
        assert out["state"] == "completed", out["error"]
        assert out["selected_provider"] == "DeclaredSkillsProvider"
        assert out["original_calls"] == [], out["original_calls"]
    allowed = set(DECLARED["SecurityScan"])
    assert set(block["calls"]) <= allowed, (
        f"طلبت مهارة غير معلنة: {block['calls']}")
    assert block["calls"], "مزوّد العقد المعلن لم يستدعَ إطلاقاً"


# ---------------------------------------------------------------------------
# ضوابط التوافق: المدخلات المقبولة قبل التحويل تبقى مقبولة بعده
# ---------------------------------------------------------------------------
def test_article4_empty_repo_url_still_accepted(url_phase):
    """مستودع فارغ بلا commits عبر url — مقبول قبل التحويل (الاستنساخ وحده
    لا يشترط HEAD) يجب أن يبقى مقبولاً: الاستنساخ بلا ميتاداتا يحفظه."""
    r = url_phase["empty"]
    assert r["state"] == "completed", r["error"]
    assert r["selected_provider"] == "SubstituteRepositoryProvider"
    assert r["substitute_calls"] == ["CloneRepository", "WalkRepository"], (
        r["substitute_calls"])
    assert r["facts"]["secrets_found"] == 0, r["facts"]


def test_article4_default_branch_none_arrives(url_phase):
    """دلالة branch=None محفوظة: مستودع فرعه الافتراضي ليس main، مهمة url
    بلا معامل branch — None يصل إلى عقد الاستنساخ كما هو وgit يختار
    الافتراضي فتكتمل المهمة على محتوى المستودع فعلاً."""
    r = url_phase["trunk"]
    assert r["state"] == "completed", r["error"]
    assert r["substitute_branches"] == [None], (
        f"branch=None لم يصل كما هو: {r['substitute_branches']}")
    assert r["substitute_calls"] == ["CloneRepository", "WalkRepository"], (
        r["substitute_calls"])
    assert r["facts"]["scanned_files"] == 2, r["facts"]


def test_article4_no_origin_local_repo_still_analyzed(path_phase):
    """مستودع ملتزم بلا remote — مدخل مقبول قبل التحويل يجب أن يبقى مقروءاً
    بعده: عقد المسح لا يشترط ميتاداتا (ولا origin)."""
    r = path_phase["no_origin"]
    assert r["state"] == "completed", r["error"]
    assert r["selected_provider"] == "SubstituteRepositoryProvider"
    assert r["substitute_calls"] == ["WalkRepository"], r["substitute_calls"]
    assert r["facts"]["secrets_found"] == 0, r["facts"]


# ---------------------------------------------------------------------------
# الاستنساخ ينجح ثم المسح يرفض: تنظيف الجذر وبقاء الجار بلا رجوع للمحلي
# ---------------------------------------------------------------------------
def test_article4_clone_success_then_walk_refusal(url_phase):
    """استنساخ ناجح (بجار غير مملوك بجانب الجذر) ثم رفض المسح: المهمة تفشل
    بمسببه، والجذر المستنسخ يُنظف، والجار يبقى، ولا رجوع للمحلي."""
    r = url_phase["clone_refuse"]
    assert r["state"] == "failed", r
    assert r["error"] and "رفض المسح" in r["error"], r["error"]
    assert r["clone_calls"] == ["CloneRepository", "WalkRepository"], (
        r["clone_calls"])
    assert r["root_cleaned"] is True, "الجذر المستنسخ لم يُنظف بعد الرفض"
    assert r["neighbor_survives"] is True, "الجار غير المملوك حُذف مع التنظيف"
    assert r["original_calls"] == [], (
        f"رجوع إلى الأصل بعد رفض المختار: {r['original_calls']}")


# ---------------------------------------------------------------------------
# ملكية التنظيف: الجذر المملوك وحده — الوالد لا يُمس (مباشران)
# ---------------------------------------------------------------------------
def test_article4_cleanup_spares_unowned_neighbor(tmp_path):
    """الأحمر أولاً: تنظيف المسار المستنسخ يشمل الجذر المملوك وحده — حذف
    الوالد كاملاً يعدو على ملفات جار غير مملوكة (كان يُحذف فعلاً قبل
    الإصلاح)."""
    from agos.kernel.capabilities.foundation_extra import _Repo

    parent = tmp_path / "wrap"
    parent.mkdir()
    repo = parent / "repo"
    repo.mkdir()
    (repo / "x.txt").write_text("x")
    neighbor = parent / "neighbor.txt"
    neighbor.write_text("ملف جار غير مملوك")

    _Repo(str(repo), [], owns_root=True).cleanup()

    assert not repo.exists(), "الجذر المملوك لم يُنظف"
    assert neighbor.exists(), "تنظيف المسار حذف ملفاً جاراً غير مملوك"


@pytest.mark.parametrize("root_name", ["repo", "anyname"])
def test_article4_cleanup_spares_unowned_empty_parent(tmp_path, root_name):
    """الوالد الفارغ غير المملوك لا يُحذف — لا استنتاج ملكية من الاسم
    («repo» هو الاسم الذي كان يُستنتج منه سابقاً) أو من الفراغ: عقد
    الاستنساخ يسلم ملكية المسار لا أصله."""
    from agos.kernel.capabilities.foundation_extra import _Repo

    parent = tmp_path / "wrap"
    parent.mkdir()
    repo = parent / root_name
    repo.mkdir()
    (repo / "x.txt").write_text("x")

    _Repo(str(repo), [], owns_root=True).cleanup()

    assert not repo.exists(), "الجذر المملوك لم يُنظف"
    assert parent.exists(), "الوالد الفارغ غير المملوك حُذف"


# ---------------------------------------------------------------------------
# تسرب فشل الميتاداتا: لا مستودع مؤقت متروك (مباشر — تنظيف المنتج)
# ---------------------------------------------------------------------------
def test_article4_clone_metadata_failure_leaves_no_temp(tmp_path_factory):
    """الأحمر أولاً: فشل قراءة الميتاداتا داخل _clone بعد نجاح الاستنساخ
    وقبل تسليم المسار كان يتسرب بمستودع مؤقت لا يملكه أحد — المنتج ينظف
    نسخته غير المسلَّمة ثم يعيد رفع السبب (الاختبار مباشر لا عبر مدخل
    المهمة — 4 حالات اختبار مباشرة في الشريحة و28 عبر مدخل
    المهمة)."""
    import glob
    import os
    import shutil
    import tempfile

    from agos.kernel.providers import (CloneRepositoryInput,
                                       LocalRepositoryProvider)

    repo = _git_repo(tmp_path_factory.mktemp("metafail") / "sample")
    pattern = os.path.join(tempfile.gettempdir(), "agos_clone_*")
    before = set(glob.glob(pattern))
    leaked = []

    real_metadata = LocalRepositoryProvider.Metadata

    def _raising_metadata(self, path):
        raise RuntimeError("فشل مقصود للميتاداتا")

    LocalRepositoryProvider.Metadata = _raising_metadata
    leaked = set()
    try:
        with pytest.raises(RuntimeError, match="فشل مقصود"):
            LocalRepositoryProvider().execute(
                "CloneRepository",
                CloneRepositoryInput(str(repo), "main"))
    finally:
        # الحساب قبل التنظيف دائماً — لا يبطل التوكيدَ تنظيفٌ مبكر
        leaked = set(glob.glob(pattern)) - before
        LocalRepositoryProvider.Metadata = real_metadata
        for extra in leaked:
            shutil.rmtree(extra, ignore_errors=True)

    assert not leaked, f"مستودع مؤقت متسرب بعد فشل الميتاداتا: {leaked}"
