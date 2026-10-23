"""R-W2-013 — RPP: خط معالجة المستودعات وفق وثيقته.

كل تأكيد فعلي (R-Q-001): المراحل الثماني موثقة مطابقةً — الموحّد إسقاط فوق
الخط الموحد بلا مسح جديد، والكواشف بواجهة الوثيقة حرفياً وبأدلة مسماة
وثقة تُحسب من الأدلة المنشورة نفسها، والرسم يحدث الحالة الفعالة (الزائل
يزول)، والتشابه (Jaccard + cosine) يعمل داخل الخط واعياً بالقيم (تصحيح
موثق لمثال الوثيقة)، والتطور يقارن التزامين مختلفين فعلاً، والطابور أهليته
بالقيم وفقدانها يحدث الطابور، والتسليم إلى ARI معلن مؤجل لا مُدّعى.
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agos" / "agos-kernel"))

from capabilities.analysis_service import get_analysis_service  # noqa: E402
from capabilities.rpp import (  # noqa: E402
    BenchmarkQueue, ConfidenceEngine, EvolutionTracker, Feature,
    FeatureSet, RPPDetectorRegistry, RPPKnowledgeBase, RPPPipeline,
    RepositoryProcessingPipelineCapability, SimilarityEngine,
    UniversalNormalizer, create_default_registry, extract_features,
    get_knowledge_base,
)

AT = datetime(2026, 10, 22, 16, 0, tzinfo=timezone.utc)
REPO_ROOT = Path(__file__).resolve().parents[1]


def _repo(path, files):
    path.mkdir(parents=True, exist_ok=True)
    for rel, text in files.items():
        p = path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return path


def _shared(path):
    return get_analysis_service().analyze_path(str(path))


def _kb():
    return RPPKnowledgeBase()


def _process(kb, path, **kw):
    return RPPPipeline(knowledge_base=kb).process(_shared(path), **kw)


def _fs(repo, features, gaps=None):
    """FeatureSet مباشر لاختبار المكونات بمعزل عن المسح."""
    return FeatureSet(repository=repo, features=features,
                     detected_at=AT.isoformat(), gaps=gaps or [])


# ---------------------------------------------------------------------------
# M1 — الموحّد
# ---------------------------------------------------------------------------

class TestUniversalNormalizer:
    def test_uro_is_a_projection_of_shared_facts(self, tmp_path):
        repo = _repo(tmp_path / "src", {
            "app.py": "import json\nx = 1\n",
            "requirements.txt": "flask>=2.0\n",
            "README.md": "# Demo\n",
        })
        uro = UniversalNormalizer().normalize(_shared(repo), normalized_at=AT)
        assert uro.name == "src"
        assert uro.primary_language == "Python"
        assert uro.all_languages == ["Python"]
        assert uro.path and not uro.url and not uro.commit
        assert sorted(f["path"] for f in uro.files) == [
            "README.md", "app.py", "requirements.txt"]
        # القرارات من المصدر الواحد: الاعتماديات والنقاط من stack_detection
        assert [d["name"] for d in uro.dependencies] == ["flask"]
        assert uro.config_files == ["requirements.txt"]
        # configs يحمل نتائج التحليل الفعلية — عدد الاعتماديات المحلولة
        results = uro.configs["manifest_results"]["requirements.txt"]
        assert results == {"analyzed": True, "dependencies": 1}
        # github_data غير مُخترع
        assert uro.github_data is None

    def test_malformed_manifest_is_a_named_error_not_success(self, tmp_path):
        repo = _repo(tmp_path / "src", {"pyproject.toml": "[not valid tom"})
        uro = UniversalNormalizer().normalize(_shared(repo), normalized_at=AT)
        result = uro.configs["manifest_results"]["pyproject.toml"]
        assert result["analyzed"] is False
        assert "error" in result
        assert uro.manifest_errors["pyproject.toml"] == result["error"]

    def test_language_stats_from_unified_facts_not_read_content(self, tmp_path):
        repo = _repo(tmp_path / "src", {"app.py": "x = 1\n"})
        shared = _shared(repo)
        uro = UniversalNormalizer().normalize(shared, normalized_at=AT)
        # الإحصاءات من حقائق الخط الموحد نفسها (code_languages) — تطابقها
        assert uro.language_stats == {
            stat.language: {"files": stat.files, "lines": stat.lines}
            for stat in shared.code_languages.values()}

    def test_uro_fingerprint_is_reproducible(self, tmp_path):
        repo = _repo(tmp_path / "src", {"app.py": "x = 1\n"})
        first = UniversalNormalizer().normalize(
            _shared(repo), normalized_at=AT)
        second = UniversalNormalizer().normalize(
            _shared(repo), normalized_at=AT)
        assert first.input_fingerprint == second.input_fingerprint
        # والتعديل يغير البصمة (لقطة قابلة للإعادة حقيقةً)
        (repo / "app.py").write_text("x = 2\n", encoding="utf-8")
        third = UniversalNormalizer().normalize(
            _shared(repo), normalized_at=AT)
        assert third.input_fingerprint != first.input_fingerprint

    def test_scan_gaps_flow_into_uro(self, tmp_path):
        repo = _repo(tmp_path / "src", {"app.py": "x = 1\n"})
        big = repo / "big.py"
        big.write_text("y = 0\n" * 300_000, encoding="utf-8")
        uro = UniversalNormalizer().normalize(_shared(repo), normalized_at=AT)
        assert uro.unread == {"big.py": "too_large"}


# ---------------------------------------------------------------------------
# M2/M3 — السوق والاستخراج
# ---------------------------------------------------------------------------

class TestDetectorMarketplaceAndExtraction:
    def test_plugin_interface_matches_spec_literally(self, tmp_path):
        # واجهة الوثيقة حرفياً: detect(uro) وconfidence(feature)
        repo = _repo(tmp_path / "src", {"app.py": "x = 1\n"})
        uro = UniversalNormalizer().normalize(_shared(repo), normalized_at=AT)
        for plugin in create_default_registry().list_all():
            assert plugin.name and plugin.version and plugin.category
            features = plugin.detect(uro)      # معامل واحد: uro فقط
            for feature in features:
                assert isinstance(feature, Feature)
                assert 0 < plugin.confidence(feature) <= 1.0

    def test_features_carry_named_evidence_and_confidence(self, tmp_path):
        repo = _repo(tmp_path / "src", {
            "app.py": "import flask\n",
            "requirements.txt": "flask>=2.0\npytest>=8\n",
            "Dockerfile": "FROM python:3.12\n",
            ".github/workflows/ci.yml": "on: [push]\njobs: {b: {steps: []}}\n",
        })
        kb = _kb()
        out = _process(kb, repo)
        features = out["feature_set"]["features"]
        # الدليل مسمّى: إطار الاختبار مصرّح به من ملف الاعتماديات
        testing = features["testing_frameworks_declared"]
        assert testing["value"] == ["pytest"]
        assert "config:pytest@pypi" in testing["evidence"]
        # ووجود Dockerfile «تعريف حاوية» — لا ادعاء بناء
        assert features["container_definition_present"]["value"] == ["Dockerfile"]
        assert "file:Dockerfile" in features["container_definition_present"]["evidence"]
        # وworkflow «تعريف CI» — لا ادعاء اختبارات تعمل
        assert features["ci_workflow_definitions_present"]["value"] == [
            ".github/workflows/ci.yml"]

    def test_confidence_comes_from_published_evidence(self, tmp_path):
        # لكل سمة: الدرجة المنشورة = حساب المحرك على الأدلة المنشورة نفسها
        repo = _repo(tmp_path / "src", {
            "app.py": "x = 1\n", "requirements.txt": "flask\npytest\n"})
        kb = _kb()
        out = _process(kb, repo)
        engine = ConfidenceEngine()
        for name, feature in out["feature_set"]["features"].items():
            assert feature["confidence"] == pytest.approx(
                engine.calculate(feature["evidence"])), name
        # وعلى مستوى الكائنات (الرسم) كذلك — الحافة تحمل درجة سمحتها
        for edge in kb.graph.edges.values():
            assert edge["confidence"] == pytest.approx(
                engine.calculate(edge["evidence"]))

    def test_merge_is_order_independent(self, tmp_path):
        repo = _repo(tmp_path / "src", {"app.py": "x = 1\n"})
        uro = UniversalNormalizer().normalize(_shared(repo), normalized_at=AT)

        class Dup:
            name, version, category = "Dup", "1.0.0", "test"

            def confidence(self, feature):
                return 0.5

            def detect(self, uro):
                return [Feature(name="languages", value=["Go"], source="Dup",
                                evidence=["file:x"])]

        # التسجيل المقلوب يعطي الناتج نفسه — الحتمية لا ترتيب التسجيل
        kb_first = _kb()
        kb_first.registry.register(Dup())
        first = extract_features(uro, kb_first.registry,
                                 detected_at=AT.isoformat())

        class DefaultRegistryOrdered(RPPDetectorRegistry):
            def __init__(self):
                super().__init__()
                self.register(Dup())
                for plugin in create_default_registry().list_all():
                    self.register(plugin)

        second = extract_features(uro, DefaultRegistryOrdered(),
                                  detected_at=AT.isoformat())
        assert first.features["languages"].value == \
            second.features["languages"].value
        assert sorted(first.features["languages"].evidence) == \
            sorted(second.features["languages"].evidence)
        # المتعارض موثق بمصادره كلها — لا يستبدل بعضه ببعض
        assert "inference:conflicting-values" in " ".join(
            first.features["languages"].evidence)

    def test_confidence_is_asked_from_the_plugin_interface(self, tmp_path):
        # الثقة تُطلب من كاشف سمحتها عبر الواجهة الموثقة — لا افتراض داخلي
        repo = _repo(tmp_path / "src", {"app.py": "import json\nx = json.loads('{}')\n"})
        uro = UniversalNormalizer().normalize(_shared(repo), normalized_at=AT)
        asked = []

        class Spy:
            name, version, category = "Spy", "1.0.0", "test"

            def confidence(self, feature):
                asked.append(feature.name)
                return 0.42

            def detect(self, uro):
                return [Feature(name="spy_feature", value=[1], source="Spy",
                                evidence=["file:x"])]

        kb = _kb()
        kb.registry.register(Spy())
        fs = extract_features(uro, kb.registry, detected_at=AT.isoformat())
        assert asked == ["spy_feature"]
        assert fs.features["spy_feature"].confidence == 0.42

    def test_agreeing_claims_recompute_from_merged_evidence(self, tmp_path):
        # كاشفان اتفقا على القيمة بأدلة مختلفة: الدرجة من الأدلة المدموجة
        # كلها (قاعدة M7 واحدة باتساق) لا درجة الفائز وحده
        repo = _repo(tmp_path / "src", {"app.py": "x = 1\n"})
        uro = UniversalNormalizer().normalize(_shared(repo), normalized_at=AT)

        class Second:
            name, version, category = "Aa", "1.0.0", "test"

            confidence = staticmethod(
                lambda feature: ConfidenceEngine().calculate(feature.evidence))

            def detect(self, uro):
                return [Feature(name="languages", value=["Python"],
                                source="Aa", evidence=["config:manifest"])]
        kb = _kb()
        kb.registry.register(Second())   # يوافق LanguageDetector بالقيمة
        fs = extract_features(uro, kb.registry, detected_at=AT.isoformat())
        languages = fs.features["languages"]
        assert languages.value == ["Python"]
        assert not languages.is_contested
        engine = ConfidenceEngine()
        assert languages.confidence == pytest.approx(
            engine.calculate(languages.evidence))

    def test_confidence_failure_is_a_named_gap_not_silent(self, tmp_path):
        # كاشف ينجح استخراجه ثم يفشل حساب ثقته — فجوة مسماة والبقية تستمر
        repo = _repo(tmp_path / "src", {"app.py": "x = 1\n"})
        uro = UniversalNormalizer().normalize(_shared(repo), normalized_at=AT)

        class HalfBroken:
            name, version, category = "HalfBroken", "1.0.0", "test"

            def confidence(self, feature):
                raise RuntimeError("confidence down")

            def detect(self, uro):
                return [Feature(name="hb_feature", value=[1],
                                source="HalfBroken", evidence=["file:x"])]

        kb = _kb()
        kb.registry.register(HalfBroken())
        fs = extract_features(uro, kb.registry, detected_at=AT.isoformat())
        # فشل واجهة الثقة فجوة مسماة — والكواشف الأخرى أُنتجت سماتها
        assert any(g.startswith("HalfBroken: RuntimeError: confidence down")
                   for g in fs.gaps)
        assert "hb_feature" not in fs.features
        assert "languages" in fs.features

    def test_contested_features_are_structured_not_silent(self, tmp_path):
        repo = _repo(tmp_path / "src", {"app.py": "x = 1\n"})
        uro = UniversalNormalizer().normalize(_shared(repo), normalized_at=AT)

        class Dup:
            name, version, category = "Dup", "1.0.0", "test"

            def confidence(self, feature):
                return 0.5

            def detect(self, uro):
                return [Feature(name="languages", value=["Go"], source="Dup",
                                evidence=["file:x"])]

        kb = _kb()
        kb.registry.register(Dup())
        fs = extract_features(uro, kb.registry, detected_at=AT.isoformat())
        languages = fs.features["languages"]
        # التعارض بنية موثقة: كل ادعاء بمصدره وقيمته وأدلته
        assert len(languages.conflicts) == 2
        assert {c["source"] for c in languages.conflicts} == {
            "Dup", "LanguageDetector"}
        assert languages.is_contested

    def test_contested_value_does_not_grant_eligibility(self):
        # قيمة متنازع عليها ليست حقيقة مؤسسة — لا تمنح أهلية قياس
        contested = Feature("production_capability_usage", ["parse_json"],
                            source="A", evidence=["code:x"],
                            conflicts=[{"source": "A", "value": ["parse_json"],
                                        "evidence": ["code:x"]},
                                       {"source": "B", "value": [],
                                        "evidence": ["file:y"]}])
        fs = _fs(("r", "", "v1"), {
            "production_capability_usage": contested,
            "ci_workflow_definitions_present": Feature(
                "ci_workflow_definitions_present", [".github/workflows/ci.yml"]),
            "testing_frameworks_declared": Feature(
                "testing_frameworks_declared", ["pytest"])})
        eligible, reasons = BenchmarkQueue().should_benchmark(fs)
        assert not eligible
        assert "no-detected-capabilities" in reasons

    def test_detector_failure_is_a_named_gap_not_silent(self, tmp_path, monkeypatch):
        repo = _repo(tmp_path / "src", {"app.py": "x = 1\n"})
        kb = _kb()
        plugin = kb.registry.list_all()[0]

        def boom(uro):
            raise RuntimeError("detector down")

        monkeypatch.setattr(type(plugin), "detect", staticmethod(boom))
        monkeypatch.setattr(type(plugin), "confidence",
                            staticmethod(lambda feature: 0.5))
        uro = UniversalNormalizer().normalize(_shared(repo), normalized_at=AT)
        fs = extract_features(uro, kb.registry, detected_at=AT.isoformat())
        assert any(g.startswith(f"{plugin.name}: RuntimeError: detector down")
                   for g in fs.gaps)


# ---------------------------------------------------------------------------
# M7 — الثقة (المصدر الواحد للكواشف والدمج والحواف)
# ---------------------------------------------------------------------------

class TestConfidenceEngine:
    def test_documented_weights_exact(self):
        engine = ConfidenceEngine()
        assert engine.calculate(["import:x"]) == 1.0
        assert engine.calculate(["config:x"]) == 0.95
        assert engine.calculate(["file:x"]) == 0.90
        assert engine.calculate(["documentation:x"]) == 0.80
        assert engine.calculate(["code:x"]) == 0.85
        assert engine.calculate(["inference:x"]) == 0.50
        # مجهول النوع 0.5
        assert engine.calculate(["mystery:x"]) == 0.5

    def test_boost_and_penalty_per_spec(self):
        engine = ConfidenceEngine()
        # أكثر من ثلاثة أدلة: تعزيز ×1.1 — يظهر حيث الوزن أقل من 1
        assert engine.calculate(["config:1", "config:2", "config:3",
                                "config:4"]) == pytest.approx(0.95 ** 4 * 1.1)
        # لا أدلة: عقوبة ×0.1
        assert engine.calculate([]) == pytest.approx(0.1)
        # والسقف 1.0 — أدلة وزن 1 لا ترتفع فوق اليقين
        assert engine.calculate(["import:1", "import:2", "import:3",
                                "import:4"]) == 1.0

    def test_filter_by_confidence(self, tmp_path):
        repo = _repo(tmp_path / "src", {"app.py": "x = 1\n"})
        kb = _kb()
        uro = UniversalNormalizer().normalize(_shared(repo), normalized_at=AT)
        fs = extract_features(uro, kb.registry, detected_at=AT.isoformat())
        filtered = kb.confidence.filter_by_confidence(fs, threshold=0.95)
        # فلترة فوق 0.95: سمات import فقط (نسخة — لا يعدل الأصل)
        assert all(f.confidence >= 0.95 for f in filtered.features.values())
        assert len(fs.features) >= len(filtered.features)


# ---------------------------------------------------------------------------
# M4 — الرسم المعرفي
# ---------------------------------------------------------------------------

class TestKnowledgeGraph:
    def test_evidence_flows_to_edges(self, tmp_path):
        repo = _repo(tmp_path / "src", {
            "app.py": "x = 1\n", "requirements.txt": "flask\n"})
        kb = _kb()
        _process(kb, repo)
        fs_edge = [e for (r, n), e in kb.graph.edges.items()
                   if n == "frameworks"][0]
        assert fs_edge["value"] == ["Flask"]
        assert fs_edge["confidence"] > 0
        assert any(ev.startswith("config:") for ev in fs_edge["evidence"])

    def test_two_repos_coexist_and_query(self, tmp_path):
        kb = _kb()
        a = _repo(tmp_path / "a", {"app.py": "x = 1\n", "requirements.txt": "flask\n"})
        b = _repo(tmp_path / "b", {"main.js": "x = 1\n", "package.json": '{"deps": {}}\n'})
        _process(kb, a)
        _process(kb, b)
        assert len(kb.graph.repositories) == 2
        flask_repos = kb.graph.query("frameworks", value=["Flask"])
        assert len(flask_repos) == 1
        assert flask_repos[0][0].endswith("/a")

    def test_vanished_features_leave_the_graph(self, tmp_path):
        # الحالة الفعالة تتحدث: إزالة السمة تزيل الحافة — لا يكذب الرسم
        repo = _repo(tmp_path / "src", {"app.py": "x = 1\n",
                                        "requirements.txt": "flask\n"})
        kb = _kb()
        _process(kb, repo)
        assert kb.graph.query("frameworks", value=["Flask"])
        (repo / "requirements.txt").write_text("pytest\n", encoding="utf-8")
        _process(kb, repo)
        assert kb.graph.query("frameworks", value=["Flask"]) == []
        # العقدة تبقى (التاريخ) لكن بلا مستودعات حالية
        assert kb.graph.features["frameworks"]["repositories"] == []

    def test_reprocessing_does_not_duplicate_nodes(self, tmp_path):
        repo = _repo(tmp_path / "src", {
            "app.py": "import json\nx = json.loads('{}')\n",
            "requirements.txt": "flask\npytest\n",
            ".github/workflows/ci.yml": "on: [push]\njobs: {b: {steps: []}}\n"})
        kb = _kb()
        _process(kb, repo)
        _process(kb, repo)
        _process(kb, repo)
        assert len(kb.graph.repositories) == 1
        assert len(kb.evolution.snapshots) == 1
        assert len(kb.evolution.events) == 0
        assert len(kb.queue.queue) == 1


# ---------------------------------------------------------------------------
# M5 — التشابه (Jaccard + cosine)
# ---------------------------------------------------------------------------

class TestSimilarityEngine:
    def test_identical_repos_similarity_is_one(self):
        sim, common, diffs = SimilarityEngine()._compare(
            {"frameworks": {"value": ["Flask"]}},
            {"frameworks": {"value": ["Flask"]}})
        assert sim == pytest.approx(1.0)
        assert common == ["frameworks"]
        assert diffs == []

    def test_disjoint_repos_similarity_is_zero(self):
        sim, _, _ = SimilarityEngine()._compare(
            {"frameworks": {"value": ["Flask"]}},
            {"languages": {"value": ["Go"]}})
        assert sim == 0.0

    def test_value_aware_not_truthiness(self):
        # تصحيح موثق لمثال الوثيقة: صدق القيم كان يعطي cosine كاملاً هنا
        # (Python=Go) — cosine فوق عناصر (مفتاح، قيمة) يعطي صفراً للقيم
        # المختلفة، والمتوسط 0.5 (مفتاح مشترك بلا قيمة مشتركة)
        sim, _, diffs = SimilarityEngine()._compare(
            {"languages": {"value": ["Python"]}},
            {"languages": {"value": ["Go"]}})
        assert sim == 0.5
        assert diffs == ["languages: ['Python'] != ['Go']"]

    def test_empty_values_do_not_inflate_similarity(self):
        sim, common, _ = SimilarityEngine()._compare(
            {"x": {"value": []}}, {"x": {"value": []}})
        assert sim == 0.0 and common == []
        sim, _, _ = SimilarityEngine()._compare(
            {"x": {"value": False}}, {"x": {"value": False}})
        assert sim == 0.0

    def test_differences_are_bidirectional(self):
        _, _, diffs = SimilarityEngine()._compare(
            {"a": {"value": [1]}, "b": {"value": [1]}},
            {"a": {"value": [1]}, "c": {"value": [2]}})
        assert "b: موجود في الأول دون الثاني" in diffs
        assert "c: موجود في الثاني دون الأول" in diffs

    def test_type_aware_value_comparison(self):
        # True لا تساوي 1 و[1] لا تساوي ["1"] — النوع جزء من القيمة
        assert not SimilarityEngine()._compare(
            {"x": {"value": True}}, {"x": {"value": 1}})[2] == []
        sim, _, diffs = SimilarityEngine()._compare(
            {"x": {"value": [1]}}, {"x": {"value": ["1"]}})
        assert sim == 0.5 and diffs

    def test_similarity_runs_inside_the_pipeline(self, tmp_path):
        # M5 داخل الخط: نتيجة process() تحمل التشابه — لا استدعاء منفرداً فقط
        kb = _kb()
        a = _repo(tmp_path / "a", {"requirements.txt": "flask\n"})
        b = _repo(tmp_path / "b", {"requirements.txt": "flask\n"})
        c = _repo(tmp_path / "c", {"main.go": "package main\n"})
        out_a = _process(kb, a)
        assert out_a["similar"] == []          # أول مستودع: لا جيران بعد
        out_b = _process(kb, b)
        similar_b = {tuple(s["repository"]): s["similarity"]
                    for s in out_b["similar"]}
        assert similar_b[(str(a), "")] == pytest.approx(1.0)
        out_c = _process(kb, c)
        similar_c = {tuple(s["repository"]): s["similarity"]
                     for s in out_c["similar"]}
        assert similar_c[(str(a), "")] == 0.0
        assert similar_c[(str(b), "")] == 0.0

    def test_find_similar_orders_and_limits(self, tmp_path):
        kb = _kb()
        a = _repo(tmp_path / "a", {"requirements.txt": "flask\n"})
        b = _repo(tmp_path / "b", {"requirements.txt": "flask\n"})
        _process(kb, a)
        _process(kb, b)
        engine = SimilarityEngine()
        similar = engine.find_similar(kb.graph, next(
            iter(kb.graph.repositories)))
        assert similar[0]["similarity"] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# M6 — التطور
# ---------------------------------------------------------------------------

class TestEvolutionTracker:
    def test_changes_between_two_commits(self):
        # التطور يقارن التزامين مختلفين فعلاً — لا لقطة أولى صامتة
        tracker = EvolutionTracker()
        base = {"languages": ["Python"], "frameworks": ["Flask"]}
        first = _fs(("r", "main", "aaa"), {
            "languages": Feature("languages", ["Python"]),
            "frameworks": Feature("frameworks", ["Flask"])})
        assert tracker.track(first) == []
        second = _fs(("r", "main", "bbb"), {
            "languages": Feature("languages", ["Python"]),
            "frameworks": Feature("frameworks", ["Django"])})
        changes = tracker.track(second)
        types = {(c["type"], c["feature"]) for c in changes}
        assert ("CHANGED_FEATURE", "frameworks") in types
        assert len(tracker.events) == 1
        # إعادة معالجة الالتزام الثاني: لا أحداث جديدة ولا تكرار لقطات
        assert tracker.track(_fs(("r", "main", "bbb"), {
            "languages": Feature("languages", ["Python"]),
            "frameworks": Feature("frameworks", ["Django"])})) == []
        assert len(tracker.events) == 1
        assert len(tracker.snapshots) == 2

    def test_changes_between_two_versions_of_local_repo(self, tmp_path):
        repo = _repo(tmp_path / "src", {
            "app.py": "x = 1\n", "requirements.txt": "flask\n"})
        kb = _kb()
        first = _process(kb, repo)
        assert first["evolution_changes"] == []   # أول تحليل: لقطة بلا أحداث
        # نسخة جديدة: إطار اختبار يُضاف وflask يُزال
        (repo / "requirements.txt").write_text("pytest\n", encoding="utf-8")
        second = _process(kb, repo)
        changes = second["evolution_changes"]
        types = {(c["type"], c["feature"]) for c in changes}
        assert ("NEW_FEATURE", "testing_frameworks_declared") in types
        assert ("REMOVED_FEATURE", "frameworks") in types
        # حدث واحد مسجل لا تكرار
        assert len(kb.evolution.events) == 1

    def test_same_version_reprocessing_records_no_events(self, tmp_path):
        repo = _repo(tmp_path / "src", {"app.py": "x = 1\n"})
        kb = _kb()
        _process(kb, repo)
        _process(kb, repo)
        assert kb.evolution.events == []
        assert len(kb.evolution.snapshots) == 1

    def test_false_to_true_is_a_change_not_new(self):
        # الوجود بالمفتاح: السمة بقيمة False ثم True — تغيّر موثق لا ظهور
        tracker = EvolutionTracker()
        tracker.track(_fs(("r", "main", "v1"), {
            "x": Feature("x", False, source="s", evidence=["file:x"])}))
        changes = tracker.track(_fs(("r", "main", "v2"), {
            "x": Feature("x", True, source="s", evidence=["file:x"])}))
        assert [(c["type"], c["feature"]) for c in changes] == \
            [("CHANGED_FEATURE", "x")]

    def test_local_versions_distinguished_by_fingerprint(self, tmp_path):
        # النسخ المحلية بلا التزام تُميَّز ببصمة مدخلاتها — لا تُستبدل
        repo = _repo(tmp_path / "src", {"app.py": "x = 1\n"})
        kb = _kb()
        _process(kb, repo)
        (repo / "app.py").write_text("x = 2\n", encoding="utf-8")
        _process(kb, repo)
        assert len(kb.evolution.snapshots) == 2   # نسختان لا استبدال

    def test_new_commit_replaces_state_and_loses_lost_features(self, tmp_path):
        # هويتا التزام مختلفتان عبر process(): الرسم والطابور بمفتاح
        # المستودع (مصدر+فرع) — النسخة الجديدة تستبدل الحالة الفعالة:
        # ما فقدته النسخة B يزول من الرسم والطابور، والتطور يسجل الانتقال
        repo = _repo(tmp_path / "src", {
            "app.py": "import json\nx = json.loads('{}')\n",
            "requirements.txt": "pytest\n",
            ".github/workflows/ci.yml": "on: [push]\njobs: {b: {steps: []}}\n"})
        kb = _kb()
        shared_a = _shared(repo)
        shared_a.source_commit = "aaa"
        first = RPPPipeline(knowledge_base=kb).process(shared_a, generated_at=AT)
        assert first["benchmark_queue"]["enqueued"] is True
        assert len(kb.queue.queue) == 1
        assert kb.graph.query("ci_workflow_definitions_present")

        # النسخة B (التزام bbb) فقدت ملف CI — تفقد الأهلية والسمة
        (repo / ".github/workflows/ci.yml").unlink()
        shared_b = _shared(repo)
        shared_b.source_commit = "bbb"
        second = RPPPipeline(knowledge_base=kb).process(
            shared_b, generated_at=AT)
        # الحافة زالت من الرسم والطابور فقد العنصر — لا تكذيب للحالة
        assert kb.graph.query("ci_workflow_definitions_present") == []
        assert kb.queue.queue == {}
        assert second["benchmark_queue"]["removed_no_longer_eligible"] is True
        # والتطور سجل الانتقال (لا لقطة أولى صامتة)
        types = {(c["type"], c["feature"])
                 for c in second["evolution_changes"]}
        assert ("REMOVED_FEATURE", "ci_workflow_definitions_present") in types
        assert len(kb.evolution.events) == 1
        # وإعادة معالجة النسخة نفسها لا تكرر الأحداث
        RPPPipeline(knowledge_base=kb).process(shared_b, generated_at=AT)
        assert len(kb.evolution.events) == 1

    def test_significance_rule(self):
        tracker = EvolutionTracker()
        assert not tracker.is_significant(
            [{"type": "CHANGED_FEATURE", "feature": "x"}])
        assert tracker.is_significant(
            [{"type": "NEW_FEATURE", "feature": "x"}])
        assert tracker.is_significant([
            {"type": "CHANGED_FEATURE", "feature": "a"},
            {"type": "CHANGED_FEATURE", "feature": "b"},
            {"type": "CHANGED_FEATURE", "feature": "c"}])


# ---------------------------------------------------------------------------
# M8 — طابور القياس
# ---------------------------------------------------------------------------

class TestBenchmarkQueue:
    def test_eligibility_requires_capabilities_not_any_feature(self, tmp_path):
        # الحالة السلبية: لغة وpytest وCI — لكن «قدرتها» نقطة اصطلاحية فقط
        # (app.py) لا تصريحاً ⇒ غير مؤهل
        repo = _repo(tmp_path / "bare", {
            "app.py": "x = 1\n",
            "requirements.txt": "pytest\n",
            ".github/workflows/ci.yml": "on: [push]\njobs: {b: {steps: []}}\n"})
        kb = _kb()
        out = _process(kb, repo)
        assert out["benchmark_queue"]["enqueued"] is False
        assert out["benchmark_queue"]["reasons"] == ["no-detected-capabilities"]

    def test_eligibility_conditions_check_values_not_keys(self):
        # مفاتيح موجودة بقيم فارغة ليست أهلية — الشرط بالقيمة لا بالمفتاح
        fs = _fs(("r", "", ""), {
            "entry_points": Feature("entry_points", []),
            "ci_workflow_definitions_present": Feature(
                "ci_workflow_definitions_present", []),
            "testing_frameworks_declared": Feature(
                "testing_frameworks_declared", [])})
        eligible, reasons = BenchmarkQueue().should_benchmark(fs)
        assert not eligible
        assert set(reasons) == {"no-detected-capabilities",
                                "no-ci-workflow-definition",
                                "no-testing-framework-declared"}

    def test_eligible_repo_enqueued(self, tmp_path):
        repo = _repo(tmp_path / "full", {
            "app.py": "import json\nx = json.loads('{}')\n",
            "requirements.txt": "pytest\n",
            ".github/workflows/ci.yml": "on: [push]\njobs: {b: {steps: []}}\n"})
        kb = _kb()
        out = _process(kb, repo)
        assert out["benchmark_queue"]["enqueued"] is True
        assert out["benchmark_queue"]["item"]["status"] == "PENDING"
        # القدرة المكتشفة: استخدام فعلي موثق بالدليل (CGP — ملف/سطر/رمز)
        usage = out["feature_set"]["features"]["production_capability_usage"]
        assert usage["value"] == ["parse_json"]
        assert any(ev.startswith("code:parse_json:app.py:")
                   for ev in usage["evidence"])

    def test_lost_eligibility_updates_the_queue(self, tmp_path):
        # فقدان الأهلية يزيل العنصر — لا يبقى طابور يكذب على الحالة
        repo = _repo(tmp_path / "full", {
            "app.py": "import json\nx = json.loads('{}')\n",
            "requirements.txt": "pytest\n",
            ".github/workflows/ci.yml": "on: [push]\njobs: {b: {steps: []}}\n"})
        kb = _kb()
        first = _process(kb, repo)
        assert first["benchmark_queue"]["enqueued"] is True
        assert len(kb.queue.queue) == 1
        # إزالة CI: المستودع يفقد الأهلية والطابور يتحدث
        (repo / ".github/workflows/ci.yml").unlink()
        second = _process(kb, repo)
        assert second["benchmark_queue"]["enqueued"] is False
        assert second["benchmark_queue"]["removed_no_longer_eligible"] is True
        assert kb.queue.queue == {}

    def test_unknown_stars_are_not_zero(self):
        queue = BenchmarkQueue()
        priority, known = queue.priority_for(None)
        assert priority == "UNKNOWN" and known is False
        priority, known = queue.priority_for({"stars": 50000})
        assert priority == "HIGH" and known
        priority, known = queue.priority_for({"stars": 5000})
        assert priority == "MEDIUM" and known
        priority, known = queue.priority_for({"stars": 500})
        assert priority == "LOW" and known
        # الحدود كما وردت: فوق 1000 بقليل MEDIUM وفوق 10000 بقليل HIGH
        assert queue.priority_for({"stars": 1001})[0] == "MEDIUM"
        assert queue.priority_for({"stars": 10001})[0] == "HIGH"
        assert queue.priority_for({"stars": 1000})[0] == "LOW"
        assert queue.priority_for({"stars": 10000})[0] == "MEDIUM"

    def test_enqueue_is_idempotent(self, tmp_path):
        repo = _repo(tmp_path / "full", {
            "app.py": "import json\nx = json.loads('{}')\n",
            "requirements.txt": "pytest\n",
            ".github/workflows/ci.yml": "on: [push]\njobs: {b: {steps: []}}\n"})
        kb = _kb()
        _process(kb, repo)
        _process(kb, repo)
        assert len(kb.queue.queue) == 1

    def test_marketplace_cli_gap_is_named(self, tmp_path):
        repo = _repo(tmp_path / "src", {"app.py": "x = 1\n"})
        out = _process(_kb(), repo)
        assert any(g.startswith("marketplace-cli-unavailable")
                   for g in out["gaps"])

    def test_ari_delivery_is_a_named_deferred_gap(self, tmp_path):
        repo = _repo(tmp_path / "src", {"app.py": "x = 1\n"})
        out = _process(_kb(), repo)
        assert any(g.startswith("ari-delivery-unavailable") for g in out["gaps"])

    def test_production_capability_evidence_excludes_test_findings(self, tmp_path):
        # مهارة مستخدمة في الإنتاج وفي الاختبار معاً: دليل القدرة الإنتاجية
        # من نتائج الإنتاج فقط — نتيجة اختبار لا تثبت قدرة إنتاجية
        repo = _repo(tmp_path / "src", {
            "app.py": "import json\nx = json.loads('{}')\n",
            "tests/test_app.py": "import json\n"
                                "def test_x():\n"
                                "    assert json.loads('{}') == {}\n"})
        kb = _kb()
        out = _process(kb, repo)
        usage = out["feature_set"]["features"]["production_capability_usage"]
        assert usage["value"] == ["parse_json"]
        # كل دليل منسي من ملف إنتاج — لا من ملف اختبار
        assert usage["evidence"]
        for ev in usage["evidence"]:
            assert ev.startswith("code:parse_json:app.py:")
        assert not any("test_app" in ev for ev in usage["evidence"])

    def test_non_python_repo_capability_gap_is_named(self, tmp_path):
        repo = _repo(tmp_path / "go", {"main.go": "package main\n"})
        out = _process(_kb(), repo)
        assert any(g.startswith("capability-genome-python-only")
                   for g in out["gaps"])


# ---------------------------------------------------------------------------
# السلسلة والقبول
# ---------------------------------------------------------------------------

class TestPipelineChain:
    def test_deterministic_output_for_same_input(self, tmp_path):
        repo = _repo(tmp_path / "src", {
            "app.py": "x = 1\n", "requirements.txt": "flask\n"})
        first = _process(_kb(), repo, generated_at=AT)
        second = _process(_kb(), repo, generated_at=AT)
        assert first == second

    def test_bad_inputs_raise(self):
        cap = RepositoryProcessingPipelineCapability()
        with pytest.raises(ValueError):
            cap.execute({"url": "u", "repo_path": "p"})
        with pytest.raises(ValueError):
            cap.execute({})
        with pytest.raises(ValueError):
            cap.execute("not a dict")

    def test_mission_resolves_by_name_and_executes(self, tmp_path):
        from agos.kernel import agos_runtime
        repo = _repo(tmp_path / "src", {"app.py": "x = 1\n"})
        k = agos_runtime.boot()
        outcome = k.run({
            "name": "RPP", "description": "repository processing",
            "capability": "RepositoryProcessingPipeline",
            "parameters": {"repo_path": str(repo)},
        })
        assert outcome.state.value == "completed"
        assert outcome.result["capability"] == "RPP"
        assert outcome.result["rpp_schema_version"] == "rpp-1.0"


class TestRealRepositoryAcceptance:
    """القبول: «تنفيذ مطابق للمراحل الموثقة» — على مستودع حقيقي (AGOS نفسه)."""

    @pytest.fixture(scope="class")
    def agos_result(self):
        kb = RPPKnowledgeBase()   # قاعدة معزولة للاختبار — لا تلوث الافتراضية
        return RPPPipeline(knowledge_base=kb).process(
            get_analysis_service().analyze_path(str(REPO_ROOT)),
            generated_at=AT)

    def test_all_eight_stages_ran(self, agos_result):
        out = agos_result
        # M1: URO كامل بهوية وبصمة
        uro = out["universal_repository_object"]
        assert uro["name"] == "agos"
        assert uro["primary_language"] == "Python"
        assert uro["input_fingerprint"].startswith("sha256:")
        assert len(uro["files"]) > 500
        # M2/M3: سمات بأدلة
        features = out["feature_set"]["features"]
        assert features["languages"]["value"][0] == "Python"
        assert "config:pytest@pypi" in \
            features["testing_frameworks_declared"]["evidence"]
        assert any(p.replace("\\", "/").startswith(".github/workflows/")
                   for p in features["ci_workflow_definitions_present"]["value"])
        # M5: التشابه داخل الخط (أول مستودع في قاعدة معزولة — لا جيران)
        assert out["similar"] == []
        # M6: أول تحليل — لقطة بلا أحداث
        assert out["evolution_changes"] == []
        # M8: الأهلية بالشروط الثلاثة (لدى AGOS نقاط دخول مصرّحة: agos-analyze)
        assert out["benchmark_queue"]["enqueued"] is True
        # النقص مسمّى: github وARI
        assert any(g.startswith("github-data-unavailable")
                   for g in out["gaps"])
        assert any(g.startswith("ari-delivery-unavailable")
                   for g in out["gaps"])

    def test_second_processing_of_same_tree_no_duplicates(self, agos_result):
        kb = RPPKnowledgeBase()
        shared = get_analysis_service().analyze_path(str(REPO_ROOT))
        pipeline = RPPPipeline(knowledge_base=kb)
        pipeline.process(shared, generated_at=AT)
        second = pipeline.process(shared, generated_at=AT)
        assert second["evolution_changes"] == []
        assert len(kb.graph.repositories) == 1
        assert len(kb.queue.queue) == 1
