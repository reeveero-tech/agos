"""R-W2-006 — توحيد ذكاء المستودعات: خط واحد (ADR-0005).

كل المداخل القديمة (قدرة النواة، محلل الحضارة، بصمة الحضارة، محلل
intelligence، خط rie) تفوّض إلى الخدمة المشتركة — هذه الاختبارات تثبت
التفويض الفعلي لا مجرد التوافق: نفس الحقائق المشتركة تظهر بأشكالها
القديمة في كل واجهة، ومصدر واحد يُستدعى فعلاً (تتبّع)، ومصدر path يعمل
بلا شبكة ولا حذف ولا نتائج معلّقة قديمة، والأخطاء ليست نجاحاً فارغاً.
"""
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from agos.kernel.civilization.capabilities.repository_analysis import (
    RepositoryAnalyzer as CivRepositoryAnalyzer)
from agos.kernel.civilization.capabilities.repository_dna import RepositoryDNA
from agos.kernel.capabilities.analysis_service import (
    FileEntry, RepositoryAnalysisService, SharedAnalysis, get_analysis_service)
from agos.kernel.intelligence.repository.analyzer import (
    RepositoryAnalyzer as IntelligenceRepositoryAnalyzer)

REPO = Path(__file__).resolve().parents[1]


def make_local_repo(base: Path) -> Path:
    """مستودع محلي صغير معروف: python أساسي + flask + نقطة دخول + بنية."""
    repo = base / "demo_repo"
    (repo / "pkg").mkdir(parents=True)
    (repo / "pkg" / "__init__.py").write_text("")
    (repo / "pkg" / "main.py").write_text(
        "# entry point\nfrom flask import Flask\n\n\ndef run():\n"
        "    app = Flask(__name__)\n    return app\n\n\nif __name__ == '__main__':\n"
        "    run()\n")
    (repo / "README.md").write_text("# Demo\n")
    (repo / "requirements.txt").write_text("flask>=2.0\nrequests\n")
    return repo


def test_all_interfaces_share_the_same_facts(tmp_path):
    """الخط الواحد: كل الواجهات تعطي نفس الحقائق المشتركة بأشكالها القديمة."""
    repo = make_local_repo(tmp_path)
    shared = get_analysis_service().analyze_path(str(repo))

    # 1. محلل الحضارة — الشكل القديم من نفس المسح
    civ = CivRepositoryAnalyzer().analyze(str(repo))
    assert civ["languages"].get("Python") == 2  # __init__.py + main.py
    assert civ["primary_language"] == "Python"
    assert civ["file_count"] == shared.file_count
    assert civ["size_bytes"] == sum(f.size_bytes for f in shared.files if not f.is_dir)

    # 2. محلل intelligence — نفس الأسطر من نفس المسح
    genome = IntelligenceRepositoryAnalyzer(str(repo)).analyze()
    assert genome.metrics.languages.get("python") == 2
    # أسطر python = أسطر ملفات python في الفهرس المشترك نفسه (عدّ المسح الواحد)
    py_entry = next(f for f in shared.files if f.path == "pkg/main.py")
    assert genome.metrics.language_lines.get("python") == (
        py_entry.lines + shared.contents["pkg/__init__.py"].count("\n"))
    # الأطر من تقرير المكدس المشترك نفسه
    assert "flask" in {f.value for f in genome.frameworks}
    assert "Flask" in shared.stack.frameworks
    # المقاييس من نفس الفهرس
    assert genome.metrics.total_files == shared.file_count

    # 3. بصمة الحضارة — من الفهرس والمحتوى نفسه
    dna = RepositoryDNA().generate(str(repo))
    assert dna["fragments"]["code"] != ""  # هاشات حقيقية لا فراغ
    assert dna["repository"] == repo.name

    # 4. الحقائق نفسها: كشف الاعتماديات من الملفات البيانية المشتركة
    assert shared.manifests["requirements.txt"] == "flask>=2.0\nrequests\n"


def test_each_old_entry_actually_calls_the_service(tmp_path, monkeypatch):
    """تتبّع فعلي: كل مدخل قديم يمر بالخدمة — لا نسخة موازية صامتة."""
    repo = make_local_repo(tmp_path)
    calls = {"n": 0}
    original = RepositoryAnalysisService.analyze_path

    def counting(self, path, policy=None):
        calls["n"] += 1
        return original(self, path, policy=policy)

    monkeypatch.setattr(RepositoryAnalysisService, "analyze_path", counting)

    # كل مدخل path قديم يستدعي الخدمة
    CivRepositoryAnalyzer().analyze(str(repo)); assert calls["n"] == 1
    RepositoryDNA().generate(str(repo)); assert calls["n"] == 2
    IntelligenceRepositoryAnalyzer(str(repo)).analyze(); assert calls["n"] == 3

    # وفشل الخدمة ينتقل — لا نجاح فارغ صامت من مدخل قديم
    def failing(self, path, policy=None):
        raise RuntimeError("service down")
    monkeypatch.setattr(RepositoryAnalysisService, "analyze_path", failing)
    with pytest.raises(RuntimeError, match="service down"):
        CivRepositoryAnalyzer().analyze(str(repo))
    with pytest.raises(RuntimeError, match="service down"):
        IntelligenceRepositoryAnalyzer(str(repo)).analyze()


def test_kernel_capability_and_rie_project_from_the_url_service(monkeypatch):
    """مصدر URL: قدرة النواة وخط rie يسقطان من حقائق الخدمة — بلا شبكة
    (حقائق مُصنَّعة تُمرَّر عبر الخدمة نفسها)."""
    from agos.kernel.capabilities import RepositoryAnalysisCapability

    shared = SharedAnalysis(
        source_url="https://github.com/example/demo", source_branch="main",
        source_commit="abc123def",
        meta={"name": "demo", "url": "https://github.com/example/demo",
              "owner": "example"},
        files=[
            FileEntry(path="main.py", size_bytes=40, extension=".py", lines=2),
            FileEntry(path="requirements.txt", size_bytes=15, extension=".txt", lines=1),
            FileEntry(path="pkg", is_dir=True),
        ],
        contents={"main.py": "from flask import Flask\n\n",
                  "requirements.txt": "flask>=2.0\n"},
        manifests={"requirements.txt": "flask>=2.0\n"},
        stack=None,
    )
    # تقرير مكدس حقيقي فوق الملفات البيانية المشتركة
    from agos.kernel import stack_detection
    shared.stack = stack_detection.detect_stack(shared.manifests)
    shared.code_languages = stack_detection.language_weights(dict(shared.contents))

    def fake_analyze_url(self, url, branch="main"):
        return shared
    monkeypatch.setattr(RepositoryAnalysisService, "analyze_url", fake_analyze_url)

    # قدرة النواة: إسقاط DNA من حقائق الخدمة
    cap = RepositoryAnalysisCapability()
    dna = cap.execute({"url": "https://github.com/example/demo",
                       "branch": "main", "cache": False})
    assert dna.name == "demo"
    assert dna.owner == "example"
    assert "Flask" in dna.frameworks
    assert "Python" in dna.languages
    assert dna.primary_language == "Python"
    assert dna.dependencies  # flask من الملف البياني المشترك

    # خط rie: normalized من نفس الحقائق
    from agos.rie.application import RepositoryIntelligencePipeline
    pipeline = RepositoryIntelligencePipeline()
    normalized = pipeline._normalized_from_shared(
        shared, "https://github.com/example/demo", "main")
    assert normalized["commit"] == "abc123def"
    assert normalized["total_files"] == 2
    assert normalized["owner"] == "example"
    assert normalized["files"]["requirements.txt"]["has_content"] is True


def test_path_source_no_network_no_deletion_no_stale_results(tmp_path):
    """مصدر path: بلا شبكة، لا حذف لمجلد المستخدم، ولا نتائج معلّقة قديمة."""
    repo = make_local_repo(tmp_path)

    before = CivRepositoryAnalyzer().analyze(str(repo))
    assert repo.exists() and (repo / "pkg" / "main.py").exists()

    # تغيّر الملف → النتيجة الجديدة تعكسه (لا تخزين مؤقت لمصدر path)
    main_py = repo / "pkg" / "main.py"
    main_py.write_text(main_py.read_text() + "\n# extra line\n")
    after = CivRepositoryAnalyzer().analyze(str(repo))
    assert after["size_bytes"] > before["size_bytes"]
    genome = IntelligenceRepositoryAnalyzer(str(repo)).analyze()
    assert genome.metrics.total_lines > 0

    # المجلد لم يُمسح (خلافاً لمصدر URL الذي يُنظَّف مستنسخه)
    assert repo.exists()


def test_non_git_folder_and_nonexistent_path(tmp_path):
    """مجلد بلا git يعمل؛ والمسار غير الموجود خطأ صريح لا نجاح فارغ."""
    repo = make_local_repo(tmp_path)  # لا .git هنا أصلاً
    info = CivRepositoryAnalyzer().analyze(str(repo))
    assert info["file_count"] > 0

    with pytest.raises(ValueError, match="does not exist"):
        get_analysis_service().analyze_path(str(tmp_path / "missing"))

    # مجلد بلا أي ملفات شيفرة — إسقاط صادق لا انفجار
    empty = tmp_path / "empty_repo"
    empty.mkdir()
    genome = IntelligenceRepositoryAnalyzer(str(empty)).analyze()
    assert genome.metrics.total_files == 0


def test_large_and_binary_files_are_not_empty(tmp_path):
    """الملف الكبير/الثنائي ليس ملفاً فارغاً — سبب عدم القراءة موثق."""
    repo = tmp_path / "mixed"
    repo.mkdir()
    (repo / "big.txt").write_text("x" * 2_000_000)  # فوق حد القراءة
    (repo / "blob.bin").write_bytes(b"\x00\x01\x02")  # ثنائي
    (repo / "ok.py").write_text("print(1)\n")

    shared = get_analysis_service().analyze_path(str(repo))
    assert shared.unread["big.txt"] == "too_large"
    assert shared.unread["blob.bin"] == "binary"
    assert shared.contents["ok.py"] == "print(1)\n"
    # والفهرس يشمل الجميع — الكبير ليس ملفاً فارغاً
    assert any(f.path == "big.txt" and f.size_bytes == 2_000_000 for f in shared.files)


def test_old_shapes_preserved_exactly(tmp_path):
    """حقول كل عقدة قديمة محفوظة — لا قوائم فارغة متساوية بالصدفة."""
    repo = make_local_repo(tmp_path)

    # محلل الحضارة: مفاتيح الشكل القديم بالضبط
    civ = CivRepositoryAnalyzer().analyze(str(repo))
    assert set(civ) == {"name", "path", "size_bytes", "size_mb",
                        "file_count", "directory_count", "languages",
                        "primary_language", "structure", "timestamp"}
    assert civ["structure"]["name"] == repo.name
    assert civ["structure"]["children"], "بنية حقيقية لا فراغ"
    assert {c["name"] for c in civ["structure"]["children"]} == {"pkg", "README.md",
                                                                 "requirements.txt"}

    # بصمة الحضارة: الحقول القديمة بالضبط
    dna = RepositoryDNA().generate(str(repo))
    assert set(dna) == {"version", "repository", "path", "generated_at",
                        "fragments", "dna", "signature"}
    assert set(dna["fragments"]) == {"structure", "code", "config", "dependency"}
    assert dna["fragments"]["dependency"] != "NO_DEPS"  # requirements موجودة

    # genome: المقاييس الحقيقية
    genome = IntelligenceRepositoryAnalyzer(str(repo)).analyze()
    assert genome.metrics.code_lines > 0
    assert genome.metrics.language_lines.get("python") > 0
    assert genome.metrics.largest_files  # أكبر الملفات محسوب


def test_structure_and_depth_parity(tmp_path):
    """بنية intelligence من الفهرس: عقدة الجذر "."، Module للبياني المتداخل،
    وmetrics.depth يعكس العمق الفعلي (كان معيّناً في القديم — سطر 222)."""
    from agos.kernel.intelligence.repository.analyzer import (
        RepositoryAnalyzer as IA)

    repo = tmp_path / "depth_repo"
    (repo / "a" / "b").mkdir(parents=True)
    (repo / "a" / "b" / "deep.py").write_text("x = 1\n")
    (repo / "a" / "package.json").write_text('{"name": "d"}\n')

    genome = IA(str(repo)).analyze()
    # عقدة الجذر موجودة (المسار ".") كما في القديم
    assert any(d.path == "." and d.depth == 0 for d in genome.directories)
    # المجلدات بأعماقها
    assert {d.path for d in genome.directories} >= {".", "a", str(Path("a") / "b")}
    # البياني المتداخل Module بالاسم أيا كان موقعه (كما في القديم)
    assert any(m.name == "package.json" for m in genome.modules)
    # العمق الفعلي: a/b = عمق 2
    assert genome.metrics.depth == 2


def test_uppercase_extension_counted_by_civ_analyzer(tmp_path):
    """الامتداد الكبير (.PY) يُصنّف كما في القديم (suffix.lower())."""
    repo = tmp_path / "case_repo"
    repo.mkdir()
    (repo / "MAIN.PY").write_text("print(1)\n")
    civ = CivRepositoryAnalyzer().analyze(str(repo))
    assert civ["languages"].get("Python") == 1
    assert civ["primary_language"] == "Python"


def test_large_file_changes_reflect_in_fingerprint(tmp_path):
    """الهاش التدفقي أثناء المسح: تعديل ملف كبير (>1MB) يغيّر البصمة —
    البصمة لم تفقد وظيفتها لملف فوق حد القراءة."""
    repo = tmp_path / "fingerprint_repo"
    repo.mkdir()
    (repo / "big.py").write_text("x = 1\n" + "y = 2\n" * 400_000)  # ~1.6MB
    before = RepositoryDNA().generate(str(repo))

    (repo / "big.py").write_text("x = 1\n" + "y = 9\n" * 400_000)  # محتوى مختلف
    after = RepositoryDNA().generate(str(repo))
    assert after["fragments"]["code"] != before["fragments"]["code"]
    assert after["dna"] != before["dna"]


def test_big_only_code_file_repo_languages_consistent(tmp_path):
    """مستودع شيفرته كلها ملف واحد كبير: الملف يُحصى (فهرس كامل مع None
    للمحتوى) — لا تختفي اللغة لمجرد أن الملف لم يُقرأ في contents."""
    repo = tmp_path / "bigonly_repo"
    repo.mkdir()
    (repo / "huge.py").write_text("x = 1\n" * 300_000)  # ~1.8MB
    shared = get_analysis_service().analyze_path(str(repo))
    assert "huge.py" not in shared.contents          # فوق حد القراءة
    assert "Python" in shared.code_languages            # لكنه محصى في الفهرس
    assert shared.code_languages["Python"].files == 1
    # المقاييس: أسطره مصنّفة تدفقياً في سياسة intelligence (classify_big —
    # كما كانت مقاييس القديم تقرأ بلا حد)؛ وسياسة الحضارة الافتراضية لا
    # تصنّف الكبير (سلوكها القديم) فتظل غير مصنّفة
    genome = IntelligenceRepositoryAnalyzer(str(repo)).analyze()
    assert genome.metrics.total_lines == 300_000


def test_intelligence_analyzer_fresh_facts_and_single_scan(tmp_path, monkeypatch):
    """لقطة جديدة لكل analyze() — لا كاش دائم؛ ومسار نسبي = مسح واحد لكل
    تحليل (حل المسار لا يعيد المسح)."""
    repo = tmp_path / "fresh_repo"
    repo.mkdir()
    (repo / "m.py").write_text("x = 1\n")

    analyzer = IntelligenceRepositoryAnalyzer(str(repo))
    first = analyzer.analyze()
    assert first.metrics.total_lines == 1

    # تعديل على القرص → التحليل الثاني يعكسه (نفس الكائن)
    (repo / "m.py").write_text("x = 1\ny = 2\nz = 3\n")
    second = analyzer.analyze()
    assert second.metrics.total_lines == 3

    # مسار نسبي: استدعاء خدمة واحد لكل تحليل (الحل لا يكرر المسح)
    calls = {"n": 0}
    original = RepositoryAnalysisService.analyze_path

    def counting(self, path, policy=None):
        calls["n"] += 1
        return original(self, path, policy=policy)
    monkeypatch.setattr(RepositoryAnalysisService, "analyze_path", counting)

    import os
    rel_repo = os.path.relpath(repo, os.getcwd())
    analyzer2 = IntelligenceRepositoryAnalyzer(rel_repo)
    analyzer2.analyze()
    assert calls["n"] == 1, "resolved path must not trigger a second scan"
    analyzer2.analyze()
    assert calls["n"] == 2, "each analysis = exactly one scan"


def test_scan_access_errors_are_named_not_silent(tmp_path):
    """فشل الوصول أثناء المسح نفسه: نقص مسمى في scan_errors — لا نجاح فارغ."""
    repo = tmp_path / "locked_repo"
    repo.mkdir()
    (repo / "ok.py").write_text("x = 1\n")
    locked = repo / "locked"
    locked.mkdir()
    (locked / "secret.py").write_text("y = 2\n")
    locked.chmod(0o000)

    try:
        shared = get_analysis_service().analyze_path(str(repo))
        # الملف المقروء موجود والفهرس سليم
        assert "ok.py" in shared.contents
        # والخطأ مسمى لا مبتلع
        assert shared.scan_errors, "access error must be named, not silent"
        assert any("locked" in p for p in shared.scan_errors)
    finally:
        locked.chmod(0o755)  # تنظيف


def test_url_branch_fallback_reflected_in_facts(tmp_path, monkeypatch):
    """مصدر URL: بعد تراجع clone_safety إلى الفرع الافتراضي تعكس الحقائق
    الفرع الفعلي ("trunk") لا المعامل المطلوب ("main")."""
    import subprocess as sp
    src = tmp_path / "src_repo"
    src.mkdir()
    (src / "app.py").write_text("print('hi')\n")
    sp.run(["git", "init", "-b", "trunk"], cwd=src, capture_output=True)
    sp.run(["git", "remote", "add", "origin", "https://github.com/example/x.git"],
           cwd=src, capture_output=True)
    sp.run(["git", "add", "-A"], cwd=src, capture_output=True)
    sp.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-m", "c"],
           cwd=src, capture_output=True)

    # مزوّد مزيف: الاستنساخ = نسخ محلي بالفرع الفعلي trunk (كما يفعل
    # clone_safety بعد التراجع) — والقراءة من المزوّد الحقيقي
    from agos.kernel.capabilities import RepositoryAnalysisInput
    from providers import LocalRepositoryProvider, ReadRepositoryInput

    def fake_clone(self, input_data):
        class R:  # noqa: N801
            path = str(src)
        return R()
    monkeypatch.setattr(LocalRepositoryProvider, "_clone", fake_clone)

    # حماية: التنظيف داخل analyze_url يزيل والد المسار — لا نسمح بمسح tmp_path
    import shutil as _shutil
    monkeypatch.setattr(_shutil, "rmtree", lambda *a, **k: None)

    shared = get_analysis_service().analyze_url(
        "https://github.com/example/x", "main")  # المطلوب main — الفعلي trunk
    assert shared.source_branch == "trunk", \
        "facts must reflect the actual branch after fallback, not the parameter"
    assert shared.source_commit  # commit حقيقي من المستودع
    assert shared.contents["app.py"] == "print('hi')\n"


def test_rie_pipeline_and_normalizer_actually_delegate(tmp_path, monkeypatch):
    """خط rie فعليًا: execute() يمر بالخدمة (لا الجلب المستقل)، والمنظّم
    نفسه صار واجهة فوق الخدمة — والفشل ينتقل من الاثنين."""
    from agos.rie.application import RepositoryIntelligencePipeline
    from agos.rie.infrastructure import RepositoryNormalizer

    repo = make_local_repo(tmp_path)

    # 1. المنظّم يفوّض للخدمة (تتبّع)
    calls = {"n": 0}
    original = RepositoryAnalysisService.analyze_path

    def counting(self, path, policy=None):
        calls["n"] += 1
        return original(self, path, policy=policy)
    monkeypatch.setattr(RepositoryAnalysisService, "analyze_path", counting)

    # منظم بمجلوب مملوك: الجلب مزيف يرجع مسار المستودع المحلي
    class FakeFetcher:
        def fetch(self, url, branch):
            return str(repo)

        def get_metadata(self, repo_path):
            return {"url": "u", "name": repo.name, "owner": "example",
                    "branch": "main", "commit": "c1"}

        def cleanup(self, repo_path):
            pass
    normalizer = RepositoryNormalizer.__new__(RepositoryNormalizer)
    normalizer.fetcher = FakeFetcher()
    normalized = normalizer.normalize("u", "main")
    assert calls["n"] == 1, "normalizer must delegate to the service"
    assert normalized["commit"] == "c1"
    assert normalized["total_files"] == 4
    assert normalized["files"]["requirements.txt"]["has_content"] is True

    # 2. فشل الخدمة ينتقل إلى المنظّم — لا نجاح فارغ
    def failing(self, path, policy=None):
        raise RuntimeError("service down")
    monkeypatch.setattr(RepositoryAnalysisService, "analyze_path", failing)
    with pytest.raises(RuntimeError, match="service down"):
        normalizer.normalize("u", "main")

    # 3. execute() يمر بالخدمة لا بالجلب: الجلب معطّل والخدمة مُصنّعة
    from agos_kernel.capabilities.analysis_service import SharedAnalysis
    monkeypatch.setattr(RepositoryAnalysisService, "analyze_path", original)

    fabricated = SharedAnalysis(
        source_url="u", source_branch="main", source_commit="c9",
        meta={"name": repo.name, "url": "u", "owner": "example"},
        files=[
            FileEntry(path="requirements.txt", size_bytes=20,
                      extension=".txt", lines=2),
            FileEntry(path="app.py", size_bytes=10, extension=".py", lines=1),
        ],
        contents={"requirements.txt": "flask>=2.0\n", "app.py": "print(1)\n"},
        manifests={"requirements.txt": "flask>=2.0\n"},
    )
    fabricated.stack = stack_detection.detect_stack(fabricated.manifests)

    def fake_url(self, url, branch="main"):
        return fabricated
    monkeypatch.setattr(RepositoryAnalysisService, "analyze_url", fake_url)

    class ExplodingFetcher:
        def fetch(self, *a, **k):
            raise AssertionError("pipeline must go through the service, not fetch")
    pipeline = RepositoryIntelligencePipeline()
    pipeline.fetcher = ExplodingFetcher()  # الجلب المستقل معطّل
    dna = pipeline.execute("u", "main")
    assert dna.commit == "c9"
    assert dna.total_files == 2


from agos.kernel import stack_detection  # noqa: E402  (مستخدم في الاختبار أعلاه)


def test_big_file_hash_and_metrics_match_old_exactly(tmp_path):
    """تطابق القيم القديمة نفسها لملف كبير: الهاش من قراءة نصية صارمة
    بتوطين الأسطر (CRLF)، والتصنيف فوق فك ignore — لا مجرد وجود هاش."""
    import hashlib
    from agos_kernel.capabilities.analysis_service import ScanPolicy

    repo = tmp_path / "parity_repo"
    repo.mkdir()
    # ملف كبير بأسطر CRLF — الهاش القديم كان يقرأه نصاً (يُطبّع CRLF) ويهشّ النص
    body = "x = 1\r\ny = 2\r\n" * 120_000  # ~1.4MB
    (repo / "crlf.py").write_bytes(body.encode())

    policy = ScanPolicy(hash_predicate=lambda n: n.endswith(".py"), classify_big=True)
    shared = get_analysis_service().analyze_path(str(repo), policy=policy)
    entry = next(f for f in shared.files if f.path == "crlf.py")

    # القيمة القديمة نفسها: قراءة نصية صارمة + هاش النص المُعاد ترميزه
    with open(repo / "crlf.py", "r", encoding="utf-8") as fh:
        old_text = fh.read()
    assert entry.sha256 == hashlib.sha256(old_text.encode()).hexdigest()[:8]

    # القياس القديم نفسه: قراءة errors=ignore + عدّ الأسطر
    with open(repo / "crlf.py", "r", errors="ignore") as fh:
        old_lines = sum(1 for _ in fh)
    assert entry.metric_lines == old_lines


def test_big_file_invalid_byte_classification_matches_old(tmp_path):
    """بايت غير صالح قبل #: تصنيف التدفق فوق فك ignore يطابق حساب القديم
    نفسه (بايت غير صالح يُسقط فتبدأ السطر بـ# → تعليق)."""
    from agos_kernel.capabilities.analysis_service import ScanPolicy
    from agos_kernel.capabilities.analysis_service import _classify_lines

    repo = tmp_path / "invalid_repo"
    repo.mkdir()
    # بايت غير صالح ثم # في أول سطرين — ثم حشوة كبيرة
    head = b"\xff# comment\n\xfe# another\n"
    body = head + b"x = 1\n" * 200_000  # ~1MB+
    (repo / "weird.py").write_bytes(body)

    policy = ScanPolicy(hash_predicate=lambda n: n.endswith(".py"), classify_big=True)
    shared = get_analysis_service().analyze_path(str(repo), policy=policy)
    entry = next(f for f in shared.files if f.path == "weird.py")

    # القيمة القديمة نفسها: قراءة errors=ignore ثم تصنيف القديم
    with open(repo / "weird.py", "r", errors="ignore") as fh:
        old_text = fh.read()
    old_lines, old_comment, old_blank = _classify_lines(old_text)
    assert (entry.metric_lines, entry.comment_lines, entry.blank_lines) == (
        old_lines, old_comment, old_blank)
    # والهاش مرفوض (فاقد الترميز — كما كانت البصمة تتخطاه)
    assert entry.sha256 == ""


def test_symlink_py_not_read_for_detection(tmp_path):
    """رابط رمزي .py يشير خارج الجذر لا يُقرأ حتى لكشف قواعد البيانات
    (R-W2-005) — المسح يسمه symlink والكشف يحترمه."""
    from agos.kernel.intelligence.repository.analyzer import Database

    repo = tmp_path / "symlink_repo"
    repo.mkdir()
    (repo / "app.py").write_text("x = 1\n")
    # هدف خارج الجذر فيه كلمة postgres — يجب ألا يُقرأ عبر الرابط
    outside = tmp_path / "outside.py"
    outside.write_text("import psycopg2\nconn = psycopg2.connect('postgres://x')\n")
    (repo / "link.py").symlink_to(outside)

    genome = IntelligenceRepositoryAnalyzer(str(repo)).analyze()
    # الرابط مُوسم من المسح
    shared = genome and IntelligenceRepositoryAnalyzer(str(repo))._shared
    assert shared.unread.get("link.py") == "symlink"
    # وكلمة postgres فيه لم تُقرأ — لا اكتشاف عبر الرابط
    assert Database("postgresql") not in genome.databases


def test_scan_gaps_declared_from_all_interfaces(tmp_path):
    """إعلان النقص من نقطة مشتركة (الخدمة): كل مدخل فوق analyze_path يرث
    التحذير المسمى — محلل الحضارة، بصمتها، والمنظّم — لا intelligence وحده."""
    import warnings as _warnings
    from agos.kernel.civilization.capabilities.repository_analysis import (
        RepositoryAnalyzer as CivAnalyzer)
    from agos.kernel.civilization.capabilities.repository_dna import RepositoryDNA
    from agos.rie.infrastructure import RepositoryNormalizer

    repo = tmp_path / "locked_all"
    repo.mkdir()
    (repo / "ok.py").write_text("x = 1\n")
    locked = repo / "locked"
    locked.mkdir()
    (locked / "secret.py").write_text("y = 2\n")
    locked.chmod(0o000)

    class FakeFetcher:
        def fetch(self, url, branch):
            return str(repo)

        def get_metadata(self, repo_path):
            return {"url": "u", "name": "n", "owner": "o",
                    "branch": "b", "commit": "c"}

        def cleanup(self, repo_path):
            pass

    def gap_warnings_of(fn):
        with _warnings.catch_warnings(record=True) as caught:
            _warnings.simplefilter("always")
            fn()
        return [w for w in caught if "scan gaps" in str(w.message)]

    try:
        # كل مدخل يعلن النقص — والنتيجة الجزئية سليمة
        assert gap_warnings_of(lambda: CivAnalyzer().analyze(str(repo)))
        assert gap_warnings_of(lambda: RepositoryDNA().generate(str(repo)))
        normalizer = RepositoryNormalizer.__new__(RepositoryNormalizer)
        normalizer.fetcher = FakeFetcher()
        assert gap_warnings_of(
            lambda: normalizer.normalize("u", "main", repo_path=str(repo)))
    finally:
        locked.chmod(0o755)


def test_cr_only_big_file_metrics_parity(tmp_path):
    """ملف كبير بأسطر CR وحيدة: القديم يقرأ نصاً (توطين CR → سطر) —
    التصنيف التدفقي يطابق عدّه (لا تجميع السطر الكل في سطر واحد)."""
    from agos_kernel.capabilities.analysis_service import ScanPolicy

    repo = tmp_path / "cr_only_repo"
    repo.mkdir()
    (repo / "big.py").write_bytes(b"x = 1\r" * 200_000)  # ~1.2MB

    policy = ScanPolicy(hash_predicate=lambda n: n.endswith(".py"),
                        classify_big=True)
    shared = get_analysis_service().analyze_path(str(repo), policy=policy)
    entry = next(f for f in shared.files if f.path == "big.py")

    # القيمة القديمة نفسها: قراءة نصية (توطين CR) ثم readlines
    with open(repo / "big.py", "r", errors="ignore") as fh:
        old_lines = len(fh.readlines())
    assert entry.metric_lines == old_lines
    assert old_lines == 200_000   # توثيق حجم الحالة


def _old_classifier_counts(text: str) -> tuple:
    """المصنّف القديم المستقل (من شيفرة eece754 نفسها) — للمقارنة لا للاستخدام."""
    norm = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = norm.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    comment = blank = code = 0
    in_block = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            blank += 1
        elif stripped.startswith('#') or stripped.startswith('//'):
            comment += 1
        elif stripped.startswith('/*') or stripped.startswith('\"\"\"'):
            comment += 1
            in_block = True
        elif in_block:
            comment += 1
            if '\"\"\"' in stripped or '*/' in stripped:
                in_block = False
        else:
            code += 1
    return len(lines), comment, blank


def test_accumulative_classifier_matches_old_independently():
    """المصنّف التراكمي يطابق المصنّف القديم المستقل (من شيفرة eece754 نفسها)
    — لا _classify_lines الجديدة — في الحالات الحرجة."""
    from agos.kernel.capabilities.analysis_service import _MetricsClassifier

    # 1. حالة الكتلة: الافتتاح لا يغلق، والسطر داخل الكتلة يغلقها أياً كانت
    # بدايته — القديم: تعليقان وسطر شيفرة
    case1 = "/*\nbody */\nx = 1\n"
    mc = _MetricsClassifier()
    mc.feed(case1)
    mc.close()
    assert (mc.count, mc.state["comment"], mc.state["blank"]) == (
        _old_classifier_counts(case1))
    assert mc.state["comment"] == 2 and mc.state["code"] == 1

    # 2. علامة الإغلاق عبر حدود الدفعات (تغذية بالأجزاء لا بالنص كاملاً)
    case2 = "/*\nbody */\nx = 1\n" + "# c\n" * 10
    mc = _MetricsClassifier()
    for i in range(0, len(case2), 3):   # أجزاء من 3 محارف — حدود مصطنعة
        mc.feed(case2[i:i + 3])
    mc.close()
    assert (mc.count, mc.state["comment"], mc.state["blank"]) == (
        _old_classifier_counts(case2))

    # 3. الإغلاق في نفس الجزء الذي اتُّخذ فيه القرار (خطأ التصفير السابق)
    case3 = "/*\nbody */ tail\ny = 2\n"
    mc = _MetricsClassifier()
    mc.feed(case3)
    mc.close()
    assert (mc.count, mc.state["comment"], mc.state["blank"]) == (
        _old_classifier_counts(case3))
    assert mc.state["code"] == 1

    # 4. سطر عملاق: 5MB مسافات ثم x — القديم يعدّه شيفرة (لا فراغاً)
    giant = " " * (5 << 20) + "x\n"
    mc = _MetricsClassifier()
    for i in range(0, len(giant), 1 << 16):
        mc.feed(giant[i:i + (1 << 16)])
    mc.close()
    assert mc.state["code"] == 1 and mc.count == 1
    assert (mc.count, mc.state["comment"], mc.state["blank"]) == (
        _old_classifier_counts(giant))


    # 5. حالة المراجع: السطر داخل الكتلة يبدأ بعلامة الإغلاق نفسها —
    # «*/» — القديم: 3 أسطر، تعليقان، وسطر شيفرة
    case5 = "/*\n*/\nx = 1\n"
    mc = _MetricsClassifier()
    mc.feed(case5)
    mc.close()
    assert (mc.count, mc.state["comment"], mc.state["blank"]) == (
        _old_classifier_counts(case5))
    assert mc.state["comment"] == 2 and mc.state["code"] == 1

    # 6. والعلامة نفسها منقسمة بين دفعتين: «*» ثم «/» — الإغلاق يُلتقط عبر الحد
    mc = _MetricsClassifier()
    mc.feed("/*\n*")
    mc.feed("/\nx = 1\n")
    mc.close()
    assert (mc.count, mc.state["comment"], mc.state["blank"]) == (
        _old_classifier_counts(case5))
    assert mc.state["code"] == 1


def test_invalid_byte_py_language_lines_direct(tmp_path):
    """b"\xff": أسطر اللغة من المحتوى (1) مؤكدة في إسقاط intelligence مباشرة
    (language_lines لا عدد الملفات)."""
    repo = tmp_path / "invalid_small2"
    repo.mkdir()
    (repo / "only.py").write_bytes(b"\xff")

    genome = IntelligenceRepositoryAnalyzer(str(repo)).analyze()
    assert genome.metrics.languages.get("python") == 1
    assert genome.metrics.language_lines.get("python") == 1


def test_keyword_search_no_false_match_on_split_multibyte(tmp_path):
    """النفي: «postégres» (بـé منقسم عند حد الدفعة) لا يطابق postgres —
    المفكّك المعيب كان سيسقط é فيولّد تطابقاً كاذباً؛ التزايدي يمنعه."""
    from agos.kernel.capabilities.analysis_service import search_keywords

    d = tmp_path / "negative"
    d.mkdir()
    # «é» ينقسم عند حد 65536: b"\xc3" آخر الدفعة الأولى وb"\xa9" أول الثانية.
    # المفكّك المعيب كان يسقط é فيجعل «postégres» تبدو «postgres» (تطابق كاذب)؛
    # التزايدي يحفظ é فلا تطابق
    (d / "f.txt").write_bytes(
        b"x" * (65536 - 5) + b"post\xc3" + b"\xa9gres")
    # «postégres» — لا يحتوي «postgres»
    assert "postgresql" not in search_keywords(
        str(d / "f.txt"), {"postgresql": ("postgres",)})


def test_invalid_byte_py_language_lines_parity(tmp_path):
    """ملف .py محتواه بايت غير صالح فقط: عدّ أسطر اللغات من المحتوى المقروء
    (replace — القديم يعدّه سطراً) لا من مقاييس التصنيف (ignore — يعدّه فارغاً).
    العدّان مفصولان ومؤكدان مباشرة وكلاهما بدلالة قارئه القديم."""
    repo = tmp_path / "invalid_small"
    repo.mkdir()
    (repo / "only.py").write_bytes(b"\xff")

    shared = get_analysis_service().analyze_path(str(repo))
    entry = next(f for f in shared.files if f.path == "only.py")
    # أسطر المحتوى (replace): 1 — كما في معادلة القديم
    assert entry.lines == 1
    # مقاييس التصنيف (ignore): النص فارغ — 0 أسطر
    assert entry.metric_lines == 0

    # والمستهلك (محلل الحضارة) يعدّه للغات من المحتوى: 1 سطر
    civ = CivRepositoryAnalyzer().analyze(str(repo))
    assert civ["languages"].get("Python") == 1
    # وعدّ أسطر اللغة مباشرة من الإسقاط (المحتوى لا المقاييس)
    analyzer = CivRepositoryAnalyzer()
    info = analyzer.analyze(str(repo))
    # primary_language من أسطر اللغات — اللغة الوحيدة هي الرئيسية
    assert info["primary_language"] == "Python"
    # ومحلل intelligence كذلك: الملف محسوب للغة
    genome = IntelligenceRepositoryAnalyzer(str(repo)).analyze()
    assert genome.metrics.languages.get("python") == 1


def test_contents_newline_normalized_parity(tmp_path):
    """المحتوى المخزّن مُطبّع الأسطر كما كانت القراءة النصية القديمة
    (CRLF/CR → LF) — لا CRLF خاماً يصل الكاشفين؛ والحقائق تطابق الحساب
    القديم لملف صغير ذي أسطر CR وحدها."""
    repo = tmp_path / "cr_small"
    repo.mkdir()
    body = b"x = 1\r" * 40 + b"y = 2\r"
    (repo / "small.py").write_bytes(body)

    shared = get_analysis_service().analyze_path(str(repo))
    # القديم: قراءة نصية — توطين CR → LF
    with open(repo / "small.py", "r", encoding="utf-8", errors="replace") as fh:
        old_text = fh.read()
    assert shared.contents["small.py"] == old_text   # مطبّع — لا CR خام
    assert "\r" not in shared.contents["small.py"]
    entry = next(f for f in shared.files if f.path == "small.py")
    assert entry.lines == 41   # معادلة القديم على النص المُوطّن
    # والمقاييس (ignore) كذلك
    assert entry.metric_lines == 41


def test_keyword_search_service_direct_and_production(tmp_path):
    """اختبار خدمة البحث مباشرة: كلمة عبر حد دفعة 64KB ومحرف UTF-8 صحيح
    منقسم بين دفعتين (مفكّك تزايدي لا يسقطه)؛ ومسار إنتاجي بملف كبير وحيد
    — لا ملف صغير ينجّي النتيجة."""
    from agos.kernel.capabilities.analysis_service import search_keywords
    from agos.kernel.intelligence.repository.analyzer import Database

    # 1. مباشرة: الكلمة تبدأ قبل حد 65536 وتنتهي بعده
    d = tmp_path / "direct"
    d.mkdir()
    (d / "f.txt").write_bytes(b"x" * (65536 - 4) + b"postgres")
    assert "postgresql" in search_keywords(
        str(d / "f.txt"), {"postgresql": ("postgres",)})

    # 2. مباشرة: محرف متعدد البايتات منقسم عند الحد لا يُسقط ولا يفوّت الكلمة بعده
    # «é» = b"\xc3\xa9" — ينقسم عند الحد؛ الكلمة بعده مباشرة
    (d / "mb.txt").write_bytes(
        b"x" * 65535 + b"\xc3" + b"\xa9postgres")
    assert "postgresql" in search_keywords(
        str(d / "mb.txt"), {"postgresql": ("postgres",)})

    # 3. مسار إنتاجي: مستودع بملف كبير وحيد — الكشف من البحث التدفقي حصراً
    repo = tmp_path / "big_only"
    repo.mkdir()
    (repo / "huge.py").write_bytes(b"z = 1\n" * 2_500_000 + b"# postgres\n")
    genome = IntelligenceRepositoryAnalyzer(str(repo)).analyze()
    assert Database("postgresql") in genome.databases





def test_hashed_big_file_also_classified(tmp_path):
    """الملف الكبير المُهشّ: الهاش والتصنيف معاً (مرور واحد) — لا أن يفقد
    المقاييس لمجرد أنه مُهشّ (سياستان تجتمعان في ملف واحد)."""
    from agos_kernel.capabilities.analysis_service import ScanPolicy

    repo = tmp_path / "hash_metrics_repo"
    repo.mkdir()
    body = "x = 1\n" * 300_000  # ~1.8MB .py
    (repo / "big.py").write_text(body)

    # سياسة تجمع الهاش (DNA الحضارة) والمقاييس (classify_big)
    policy = ScanPolicy(hash_predicate=lambda n: n.endswith(".py"),
                        classify_big=True)
    shared = get_analysis_service().analyze_path(str(repo), policy=policy)
    entry = next(f for f in shared.files if f.path == "big.py")
    assert entry.sha256, "big hashed file must be hashed (streaming)"
    assert entry.metric_lines == 300_000, "hashed big file must ALSO be classified"
    assert "big.py" in shared.unread and shared.unread["big.py"] == "too_large"


def test_normalizer_injected_path_survives(tmp_path, monkeypatch):
    """ملكية التنظيف: المسار المحقون ملك مستدعيه — ينجو من النجاح والفشل
    معاً، وما جلبه المنظّم بنفسه يُنظّف."""
    from agos.rie.infrastructure import RepositoryNormalizer

    repo = make_local_repo(tmp_path)
    cleaned = []

    class FakeFetcher:
        def fetch(self, url, branch):
            return str(tmp_path / "fetched_by_normalizer")  # مسار وهمي

        def get_metadata(self, repo_path):
            return {"url": "u", "name": "n", "owner": "o",
                    "branch": "b", "commit": "c"}

        def cleanup(self, repo_path):
            cleaned.append(repo_path)
    normalizer = RepositoryNormalizer.__new__(RepositoryNormalizer)
    normalizer.fetcher = FakeFetcher()

    # 1. المسار المحقون ينجو (النجاح)
    result = normalizer.normalize("u", "main", repo_path=str(repo))
    assert result["total_files"] == 4
    assert not any(str(repo) == c for c in cleaned), "injected path must survive"

    # 2. والمسار المحقون ينجو حتى عند فشل الخدمة (لا تنظيف لمسار الغير)
    def failing(self, path, policy=None):
        raise RuntimeError("service down")
    original = RepositoryAnalysisService.analyze_path
    monkeypatch.setattr(RepositoryAnalysisService, "analyze_path", failing)
    with pytest.raises(RuntimeError, match="service down"):
        normalizer.normalize("u", "main", repo_path=str(repo))
    assert not any(str(repo) == c for c in cleaned), "injected path must survive failures"
    monkeypatch.setattr(RepositoryAnalysisService, "analyze_path", original)

    # 3. وما جلبه المنظّم بنفسه يُنظّف (الملكية صحيحة)
    own = tmp_path / "fetched_by_normalizer"
    own.mkdir()
    (own / "f.py").write_text("x = 1\n")
    normalizer.normalize("u", "main")
    assert any(str(own) == c for c in cleaned), "own fetch must be cleaned"


def test_rie_branch_reflects_actual_facts(tmp_path, monkeypatch):
    """فرع rie من الحقائق (الفرع الفعلي بعد التراجع) لا من المعامل —
    خط execute كاملاً عبر الخدمة بمستودع محلي بفرع trunk (المطلوب main)."""
    import subprocess as sp
    import shutil as _shutil
    from agos.rie.application import RepositoryIntelligencePipeline
    from providers import LocalRepositoryProvider

    src = tmp_path / "src_repo"
    src.mkdir()
    (src / "app.py").write_text("print('hi')\n")
    (src / "requirements.txt").write_text("flask>=2.0\n")
    sp.run(["git", "init", "-b", "trunk"], cwd=src, capture_output=True)
    sp.run(["git", "remote", "add", "origin", "https://github.com/example/x.git"],
           cwd=src, capture_output=True)
    sp.run(["git", "add", "-A"], cwd=src, capture_output=True)
    sp.run(["git", "-c", "user.email=t@t", "-c", "user.name=t",
           "commit", "-m", "c"], cwd=src, capture_output=True)

    # الاستنساخ مزيف: يعيد المستودع المحلي (بفرعه الفعلي trunk) —
    # والقراءة من المزوّد الحقيقي فوقه
    def fake_clone(self, input_data):
        class R:  # noqa: N801
            path = str(src)
        return R()
    monkeypatch.setattr(LocalRepositoryProvider, "_clone", fake_clone)
    monkeypatch.setattr(_shutil, "rmtree", lambda *a, **k: None)  # حماية tmp_path

    # المطلوب main — الفعلي trunk: الحقائق تعكس trunk
    dna = RepositoryIntelligencePipeline().execute(
        "https://github.com/example/x", "main")
    assert dna.branch == "trunk", "branch must come from actual facts, not the parameter"


def test_scan_gaps_declared_not_silent_in_intelligence(tmp_path):
    """أخطاء الوصول أثناء المسح تُعلن (تحذير مسمى بالمسارات) في واجهات
    intelligence — لا نتيجة جزئية صامتة."""
    import warnings as _warnings

    repo = tmp_path / "gapped_repo"
    repo.mkdir()
    (repo / "ok.py").write_text("x = 1\n")
    locked = repo / "locked"
    locked.mkdir()
    (locked / "secret.py").write_text("y = 2\n")
    locked.chmod(0o000)

    try:
        with _warnings.catch_warnings(record=True) as caught:
            _warnings.simplefilter("always")
            genome = IntelligenceRepositoryAnalyzer(str(repo)).analyze()
        # النتيجة الجزئية سليمة
        assert genome.metrics.total_files == 1
        # والنقص معلن لا مبتلع
        gap_warnings = [w for w in caught if "scan gaps" in str(w.message)]
        assert gap_warnings, "access errors must be declared, not silent"
        assert "locked" in str(gap_warnings[0].message)
    finally:
        locked.chmod(0o755)


def test_databases_detected_in_big_file(tmp_path):
    """كشف قواعد البيانات في ملف كبير (>1MB) — بحث تدفقي من القرص كما
    كان القديم يقرأ بلا حد (المحتوى المقروء الصغير وحده لا يكفي)."""
    from agos.kernel.intelligence.repository.analyzer import Database

    repo = tmp_path / "bigdb_repo"
    repo.mkdir()
    (repo / "big.py").write_text(
        "import psycopg2\nconn = psycopg2.connect('postgres://localhost/db')\n"
        + "x = 1\n" * 300_000)  # ~1.8MB

    genome = IntelligenceRepositoryAnalyzer(str(repo)).analyze()
    assert Database("postgresql") in genome.databases, \
        "database keywords in a big file must be detected (streaming search)"


def test_import_orders_in_fresh_interpreters():
    """مفسّرات جديدة بترتيبات استيراد مختلفة — التفويض لا يعتمد على الترتيب."""
    for order in (
        "from agos.kernel.capabilities.analysis_service import get_analysis_service\n"
        "from agos.kernel.civilization.capabilities.repository_analysis "
        "import RepositoryAnalyzer\n"
        "print('OK')",
        "from agos.kernel.intelligence.repository.analyzer import RepositoryAnalyzer\n"
        "from agos.rie.application import RepositoryIntelligencePipeline\n"
        "print('OK')",
    ):
        result = subprocess.run(
            [sys.executable, "-c", textwrap.dedent(order)],
            capture_output=True, text=True, timeout=120, cwd=str(REPO))
        assert result.returncode == 0, result.stderr[-800:]
        assert result.stdout.strip() == "OK"
