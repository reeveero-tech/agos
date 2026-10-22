"""R-W2-008 — الرسم المعرفي يُملأ من التحليل ويُحفظ، والاستعلامات على رسم حقيقي.

معيار القبول (ROADMAP): «استعلامات على رسم حقيقي» — الرسم يُبنى من مخرج تحليل
حقيقي (خط rie أو مسار قدرة النواة الإنتاجي) ويُحفظ إلى قرص، والاستعلامات
تُجاب على الرسم المحمَّل من الملف لا على كائنات مُعدّة يدوياً.

كل غياب دليل يظل فجوة مسمّاة في ``FillReport.gaps`` — لا دليل مُختلق ولا مصدر
مُفترى (المادة 6: لا تنفيذ صامت؛ وADR-0002).
"""
import json
import os
import re
import shutil
import subprocess

import pytest

from agos.kernel.capabilities import RepositoryAnalysisCapability
from agos.rie.application import create_rie_pipeline
from agos.kernel.civilization.knowledge_graph import (
    KnowledgeGraph,
    GraphBuilder,
    NodeType,
    RelationshipType,
)
from agos.kernel.civilization.knowledge_graph.analysis_loader import (
    FillReport,
    fill_and_save,
    fill_graph_from_dna,
)
from agos.kernel.civilization.knowledge_graph.query import QueryEngine

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")

_GIT_ENV = {
    "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
    "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
    "PATH": os.environ["PATH"],
}


def _git_repo(path, files, remote="https://github.com/t/ref.git"):
    """مستودع git محلي حقيقي — تحليل حقيقي لا كائنات مُعدّة يدوياً."""
    path.mkdir(parents=True, exist_ok=True)
    for rel, text in files.items():
        p = path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    for cmd in (["git", "init", "-q", "-b", "main"],
                ["git", "remote", "add", "origin", remote],
                ["git", "add", "-A", "-f"], ["git", "commit", "-qm", "init"]):
        subprocess.run(cmd, cwd=path, check=True, env=_GIT_ENV, capture_output=True)
    return path


SAMPLE_FILES = {
    "main.py": "def main():\n    print('hello')\n\n\nif __name__ == '__main__':\n    main()\n",
    "requirements.txt": "flask\nrequests\n",
}

PYPROJECT_SCRIPTS = """[project]
name = "sample"
version = "0.1.0"
dependencies = ["flask", "requests"]

[project.scripts]
sample-cli = "sample.cli:main"
"""


def _rie_dna(repo):
    return create_rie_pipeline().execute(f"file://{repo}")


def _repo_node(graph):
    nodes = graph.get_nodes_by_type(NodeType.REPOSITORY)
    assert len(nodes) == 1
    return nodes[0]


# ---------------------------------------------------------------------------
# الملء من التحليل — الأدلة والفجوات المسمّاة
# ---------------------------------------------------------------------------

def test_graph_filled_from_rie_analysis_with_evidence(tmp_path):
    repo = _git_repo(tmp_path / "sample", SAMPLE_FILES)
    dna = _rie_dna(repo)

    report = fill_graph_from_dna(dna)
    assert isinstance(report, FillReport)
    assert report.source_kind == "rie"

    repo_node = _repo_node(report.graph)
    assert repo_node.name == "sample"
    # دليل الالتزام موجود فعلاً في DNA‏ rie — لا يُفترى
    assert any(e.startswith("commit:") and len(e.split(":", 1)[1]) == 40
               for e in repo_node.metadata.evidence)

    # الحزم: pypi:flask وpypi:requests — والهوية بالنظام البيئي
    deps = sorted(n.name for n in report.graph.get_nodes_by_type(NodeType.PACKAGE))
    assert deps == ["pypi:flask", "pypi:requests"]
    flask = report.graph.get_nodes_by_name("pypi:flask")[0]
    assert "manifest:requirements.txt" in flask.metadata.evidence

    # الاتجاه: المستودع يعتمد على الحزمة (لا العكس)
    assert {r.target_id for r in report.graph.get_relationships_by_node(repo_node.id)
            if r.type == RelationshipType.DEPENDS_ON} >= {flask.id}

    # نقطة الدخول: ملف (main.py) لا نقطة API — الدور موثق والمسار بهوية المستودع
    entries = report.graph.get_nodes_by_type(NodeType.FILE)
    entry = [n for n in entries if n.metadata.properties.get("role") == "entry_point"]
    assert len(entry) == 1
    assert entry[0].metadata.properties["raw_path"] == "main.py"
    assert entry[0].path.startswith(f"file://{repo}")

    # الفجوة المسمّاة: DNA‏ rie لا يحمل أدلة الأطر — تُعلن ولا تُقنَّع
    assert any("framework_evidence not carried by rie DNA" in g for g in report.gaps)


def test_saved_graph_answers_queries_from_disk(tmp_path):
    """«ويُحفظ»: الرسم المحفوظ على القرص يجيب الاستعلامات نفسها بعد إعادة التحميل."""
    repo = _git_repo(tmp_path / "sample", SAMPLE_FILES)
    dna = _rie_dna(repo)

    graph_path = tmp_path / "graphs" / "sample.json"
    report = fill_and_save(dna, str(graph_path))
    assert graph_path.exists()
    persisted = json.loads(graph_path.read_text())
    assert persisted["name"] == "sample"
    assert len(persisted["nodes"]) == len(report.graph._nodes)  # الحفظ كامل لا ناقص

    loaded = KnowledgeGraph.load(str(graph_path))
    # الاستعلامات تُجاب على الرسم المحمَّل من القرص
    loaded_repo = _repo_node(loaded)
    loaded_flask = loaded.get_nodes_by_name("pypi:flask")
    assert loaded_flask, "the saved graph must answer dependency queries after reload"
    assert "manifest:requirements.txt" in loaded_flask[0].metadata.evidence

    query = QueryEngine(loaded)
    found = query.find_nodes(node_type=NodeType.REPOSITORY, repository="sample")
    assert [n.name for n in found] == ["sample"]
    assert query.find_node(name="pypi:requests", node_type=NodeType.PACKAGE) is not None

    # علاقة الاعتماد نجت من الحفظ والتحميل
    deps = loaded.get_dependencies(loaded_repo.id)
    assert sorted(n.name for n in deps) == ["pypi:flask", "pypi:requests"]

    # كل عُقد الرسم المحفوظ موجودة بعد التحميل (لا فقد صامت في الحفظ)
    assert len(loaded) == len(report.graph)
    assert (loaded.get_statistics().total_relationships
            == report.graph.get_statistics().total_relationships)


def test_refill_same_dna_is_idempotent(tmp_path):
    repo = _git_repo(tmp_path / "sample", SAMPLE_FILES)
    dna = _rie_dna(repo)

    first = fill_graph_from_dna(dna)
    node_count = len(first.graph)
    rel_count = first.graph.get_statistics().total_relationships
    again = fill_graph_from_dna(dna, graph=first.graph)
    assert (again.nodes_added, again.relationships_added) == (0, 0)
    assert len(first.graph) == node_count
    assert first.graph.get_statistics().total_relationships == rel_count

    # التصحيح 0029: الثبات بالمحتوى لا بالعدد فقط — إعادة ملء نفس التحليل
    # (نفس المستودع ونفس الالتزام) لا تكرر الظهورات ولا تغير شيئا في اللقطة
    import copy
    multi = _git_repo(tmp_path / "sample2", {
        "requirements.txt": "flask\n", "pyproject.toml":
        '[project]\nname = "sample"\ndependencies = ["flask"]\n'})
    first = fill_graph_from_dna(_rie_dna(multi))
    snapshot = copy.deepcopy(first.graph.to_dict())
    fill_graph_from_dna(_rie_dna(multi), graph=first.graph)
    assert first.graph.to_dict() == snapshot, \
        "refill must not change anything, occurrence records included"
    flask = first.graph.get_nodes_by_name("pypi:flask")[0]
    assert len(flask.metadata.properties["occurrences"]) == 2  # ملفان لا أربعة


def test_bare_dependencies_fallback_scoped_by_identity():
    """التصحيح 0029: احتياط dependencies المجردة لهوية المستودع الكاملة أيضاً —
    مستودعان بنفس الاسم وdependency_details فارغة لا يتصادمان في رسم واحد."""
    from agos.rie.contracts import RepositoryDNA as RieDNA
    a = RieDNA(name="sample", url="https://github.com/two/sample",
               dependencies=["flask"], dependency_details=[])
    b = RieDNA(name="sample", url="https://github.com/other/sample",
               dependencies=["flask"], dependency_details=[])
    shared = KnowledgeGraph(name="shared")
    fill_graph_from_dna(a, graph=shared)
    fill_graph_from_dna(b, graph=shared)

    assert len(shared.get_nodes_by_type(NodeType.REPOSITORY)) == 2
    flasks = shared.get_nodes_by_name("flask")
    assert len(flasks) == 2, "bare dependencies must stay scoped per repository"
    assert {f.metadata.properties.get("ecosystem", "") for f in flasks} == {""}
    # الفجوة المسمّاة (لا تفاصيل) معلنة لكل مستودع
    for repo_node in shared.get_nodes_by_type(NodeType.REPOSITORY):
        assert any("dependency_details empty" in g for g in
                   repo_node.metadata.properties["analysis_gaps"])


def test_framework_multiple_records_aggregate_in_both_orders():
    """التصحيح 0029: سجلات دليل متعددة لإطار واحد (تشغيلي + مستبعد) — كلها
    تبقى بأي ترتيب، والاستعمال مشتق من السجلات فلا يمحو استبعادٌ لاحقٌ استعمالاً
    موثَقًا، والسجلات تنجو من الحفظ/التحميل."""
    from agos.kernel.contracts import RepositoryDNA as KernelDNA

    def make(ordered):
        dna = KernelDNA(name="sample", url="https://github.com/t/sample")
        dna.framework_evidence = list(ordered)
        return dna

    runtime = {"framework": "Flask", "dependency": "flask", "manifest": "requirements.txt",
              "ecosystem": "pypi", "scope": "runtime", "counted": True}
    dev_excluded = {"framework": "Flask", "dependency": "flask",
                    "manifest": "requirements-dev.txt", "ecosystem": "pypi",
                    "scope": "dev", "counted": False}

    for ordered in ([runtime, dev_excluded], [dev_excluded, runtime]):
        report = fill_graph_from_dna(make(ordered))
        flasks = report.graph.get_nodes_by_name("Flask")
        assert len(flasks) == 1
        flask = flasks[0]
        # السجلان كلاهما — لا يستبدل أحدهما الآخر
        assert len(flask.metadata.properties["occurrences"]) == 2
        assert flask.metadata.properties["counted"] is True
        assert {"manifest:requirements.txt", "manifest:requirements-dev.txt"} <= \
            set(flask.metadata.evidence)
        assert "excluded:not counted as part of the project" in flask.metadata.evidence
        # الاستعمال موجود لأن سجلا موثَقًا يقوله — مهما جاء الاستبعاد بعده
        repo_node = _repo_node(report.graph)
        uses = [r for r in report.graph.get_relationships_by_node(repo_node.id)
                if r.type == RelationshipType.USES]
        assert len(uses) == 1
        assert report.graph.get_node(uses[0].target_id).name == "Flask"

    # والسجلات تنجو من الحفظ/التحميل (الادعاء في التوصيف مختبر لا مُفترى)
    import tempfile, os
    report = fill_graph_from_dna(make([runtime, dev_excluded]))
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "fw.json")
        report.graph.save(p)
        reloaded = KnowledgeGraph.load(p)
        flask = reloaded.get_nodes_by_name("Flask")[0]
        assert len(flask.metadata.properties["occurrences"]) == 2
        assert flask.metadata.properties["counted"] is True
        assert "manifest:requirements-dev.txt" in flask.metadata.evidence


def test_mixed_source_fills_stay_consistent_both_directions():
    """التصحيح 0031: تعبئة مختلطة المصادر (rie ثم kernel — وبالعكس) لنفس
    المستودع والإطار: توكيدا كل مصدر سجلان صريحان يُجمَعان، وقرار الاستعمال
    من العقدة المخزنة المدمجة، فلا تناقض التعبئةُ نفسَها ولا علاقتها،
    والفجوات المسمّاة تتراكم لا يحل محلها آخر تحليل — وبعد الحفظ/التحميل."""
    from agos.rie.contracts import RepositoryDNA as RieDNA
    from agos.kernel.contracts import RepositoryDNA as KernelDNA
    import tempfile, os

    URL = "https://github.com/t/sample"
    excluded = {"framework": "Flask", "dependency": "flask",
                "manifest": "requirements-dev.txt", "ecosystem": "pypi",
                "scope": "dev", "counted": False}

    def rie_dna():
        return RieDNA(name="sample", url=URL, frameworks=["Flask"])

    def kernel_dna():
        dna = KernelDNA(name="sample", url=URL)
        dna.framework_evidence = [dict(excluded)]
        return dna

    for first, second in ((rie_dna, kernel_dna), (kernel_dna, rie_dna)):
        graph = KnowledgeGraph(name="mixed")
        fill_graph_from_dna(first(), graph=graph)
        fill_graph_from_dna(second(), graph=graph)

        flask = graph.get_nodes_by_name("Flask")[0]
        # توكيدا المصدرين كلاهما — لا يستبدل أحدهما الآخر
        assert len(flask.metadata.properties["occurrences"]) == 2
        sources = {o["source"] for o in flask.metadata.properties["occurrences"]}
        assert sources == {"rie", "kernel"}
        # توكيد rie للاستعمال قائم → المشتق من المجمّع يقول مستعمل
        assert flask.metadata.properties["counted"] is True
        repo_node = _repo_node(graph)
        uses = [r for r in graph.get_relationships_by_node(repo_node.id)
                if r.type == RelationshipType.USES
                and graph.get_node(r.target_id).name == "Flask"]
        assert uses, "the rie usage assertion must survive the kernel exclusion"
        # العقدة لا تناقض علاقتها
        assert flask.metadata.properties["counted"] is True
        # فجوة rie المسمّاة محفوظة — لا يحل محلها آخر تحليل — واستبعاد kernel
        # موثق في أدلة العقدة نفسها
        gaps = repo_node.metadata.properties["analysis_gaps"]
        assert any("framework_evidence not carried by rie DNA" in g for g in gaps)
        assert "excluded:not counted as part of the project" in flask.metadata.evidence
        assert "manifest:requirements-dev.txt" in flask.metadata.evidence

        # وبعد الحفظ/التحميل يبقى الاتساق
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "mixed.json")
            graph.save(p)
            reloaded = KnowledgeGraph.load(p)
            flask = reloaded.get_nodes_by_name("Flask")[0]
            assert len(flask.metadata.properties["occurrences"]) == 2
            assert {o["source"] for o in flask.metadata.properties["occurrences"]} == {"rie", "kernel"}
            assert flask.metadata.properties["counted"] is True
            reloaded_repo = _repo_node(reloaded)
            reloaded_gaps = reloaded_repo.metadata.properties["analysis_gaps"]
            assert any("framework_evidence not carried by rie DNA" in g
                      for g in reloaded_gaps)
            assert "excluded:not counted as part of the project" in flask.metadata.evidence
            uses = [r for r in reloaded.get_relationships_by_node(reloaded_repo.id)
                    if r.type == RelationshipType.USES
                    and reloaded.get_node(r.target_id).name == "Flask"]
            assert uses


def test_successive_fills_keep_usage_consistent_with_merged_records():
    """التصحيح 0030: تعبئات متعاقبة في نفس الرسم — الاستعمال مشتق من السجلات
    المجمّعة لا من آخر تعبئة، فلا يناقض الإطارُ علاقتَه الموثقة ولا سجلاته.

    تعبئة أولى بسجل تشغيلي (counted=True) ثم ثانية بسجل استبعاد (counted=False)
    للإطار نفسه — وبالعكس — فيبقى counted=True والاستعمال قائما لأن السجلات
    المجمّعة تقوله، ويُختبر ذلك بعد الحفظ/التحميل أيضاً.
    """
    from agos.kernel.contracts import RepositoryDNA as KernelDNA
    import tempfile, os

    def make(evidence):
        dna = KernelDNA(name="sample", url="https://github.com/t/sample")
        dna.framework_evidence = [evidence]
        return dna

    runtime = {"framework": "Flask", "dependency": "flask", "manifest": "requirements.txt",
              "ecosystem": "pypi", "scope": "runtime", "counted": True}
    dev_excluded = {"framework": "Flask", "dependency": "flask",
                    "manifest": "requirements-dev.txt", "ecosystem": "pypi",
                    "scope": "dev", "counted": False}

    for first_ev, second_ev in ((runtime, dev_excluded), (dev_excluded, runtime)):
        graph = KnowledgeGraph(name="successive")
        fill_graph_from_dna(make(first_ev), graph=graph)
        fill_graph_from_dna(make(second_ev), graph=graph)

        flask = graph.get_nodes_by_name("Flask")[0]
        assert len(flask.metadata.properties["occurrences"]) == 2
        # الاستعمال مشتق من السجلات المجمّعة — لا من آخر تعبئة
        assert flask.metadata.properties["counted"] is True
        repo_node = _repo_node(graph)
        uses = [r for r in graph.get_relationships_by_node(repo_node.id)
                if r.type == RelationshipType.USES
                and graph.get_node(r.target_id).name == "Flask"]
        assert uses, "a documented use must survive a later exclusion fill"
        assert flask.metadata.properties["counted"] is True  # العقدة لا تناقض علاقتها

        # وبعد الحفظ/التحميل يبقى الاشتقاق متسقاً
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "s.json")
            graph.save(p)
            reloaded = KnowledgeGraph.load(p)
            flask = reloaded.get_nodes_by_name("Flask")[0]
            assert len(flask.metadata.properties["occurrences"]) == 2
            assert flask.metadata.properties["counted"] is True
            reloaded_repo = _repo_node(reloaded)
            uses = [r for r in reloaded.get_relationships_by_node(reloaded_repo.id)
                    if r.type == RelationshipType.USES
                    and reloaded.get_node(r.target_id).name == "Flask"]
            assert uses


def test_changed_analysis_fresh_graph_exactly_reflects_it(tmp_path):
    """تحليل متغيّر = رسم جديد بمقاييسه بدقة — لا بقايا من تحليل سابق ولا فقد."""
    repo_v1 = _git_repo(tmp_path / "sample", {"main.py": SAMPLE_FILES["main.py"],
                                              "requirements.txt": "flask\n"})
    repo_v2 = _git_repo(tmp_path / "sample2", {"main.py": SAMPLE_FILES["main.py"],
                                               "requirements.txt": "flask\nrequests\n"})
    dna_v1, dna_v2 = _rie_dna(repo_v1), _rie_dna(repo_v2)

    g1 = fill_graph_from_dna(dna_v1).graph
    g2 = fill_graph_from_dna(dna_v2).graph
    deps1 = {n.name for n in g1.get_nodes_by_type(NodeType.PACKAGE)}
    deps2 = {n.name for n in g2.get_nodes_by_type(NodeType.PACKAGE)}
    assert deps1 == {"pypi:flask"}
    assert deps2 == {"pypi:flask", "pypi:requests"}
    assert g1.get_statistics().total_relationships + 1 \
        == g2.get_statistics().total_relationships


def test_same_name_repos_and_cross_ecosystem_packages_stay_distinct(tmp_path):
    """الاسم وحده لا يعرّف: مستودعان بنفس الاسم وحزمة واحدة عبر نظامين بيئيين."""
    a = _git_repo(tmp_path / "a" / "sample", SAMPLE_FILES,
                  remote="https://github.com/two/sample.git")
    b = _git_repo(tmp_path / "b" / "sample", SAMPLE_FILES,
                  remote="https://github.com/other/sample.git")
    ga = fill_graph_from_dna(_rie_dna(a)).graph
    gb = fill_graph_from_dna(_rie_dna(b)).graph
    assert ga is not gb
    id_a = _repo_node(ga).id
    id_b = _repo_node(gb).id
    assert id_a != id_b  # الهوية بالرابط لا بالاسم المشترك

    py_repo = _git_repo(tmp_path / "py" / "sample", SAMPLE_FILES)
    js_repo = _git_repo(tmp_path / "js" / "sample", {
        "main.js": "console.log('hi')\n",
        "package.json": json.dumps({
            "name": "sample", "main": "main.js",
            "dependencies": {"requests": "^2.0.0"},
        }),
    })
    gpy = fill_graph_from_dna(_rie_dna(py_repo)).graph
    gjs = fill_graph_from_dna(_rie_dna(js_repo)).graph
    py_pkgs = {n.name for n in gpy.get_nodes_by_type(NodeType.PACKAGE)}
    js_pkgs = {n.name for n in gjs.get_nodes_by_type(NodeType.PACKAGE)}
    assert "pypi:requests" in py_pkgs
    assert "npm:requests" in js_pkgs
    assert {n.id for n in gpy.get_nodes_by_type(NodeType.PACKAGE)}.isdisjoint(
        {n.id for n in gjs.get_nodes_by_type(NodeType.PACKAGE)})


def test_same_name_repos_in_one_shared_graph_do_not_collide(tmp_path):
    """التصحيح 0028: رسمان لمستودعين بنفس الاسم في رسم واحد — لا تصادم أبناء.

    لو كانت هوية الأبناء بالاسم المشترك لتصادما (آخر ملف يكسب) — الهوية الكاملة
    (الرابط) تفصل حقائق كل مستودع عن الآخر.
    """
    a = _git_repo(tmp_path / "a" / "sample", {"requirements.txt": "flask>=2.0\n"},
                  remote="https://github.com/two/sample.git")
    b = _git_repo(tmp_path / "b" / "sample", {"requirements.txt": "flask<3\n"},
                  remote="https://github.com/other/sample.git")
    shared = KnowledgeGraph(name="shared")
    fill_graph_from_dna(_rie_dna(a), graph=shared)
    fill_graph_from_dna(_rie_dna(b), graph=shared)

    assert len(shared.get_nodes_by_type(NodeType.REPOSITORY)) == 2
    flasks = shared.get_nodes_by_name("pypi:flask")
    assert len(flasks) == 2, "each same-named repository keeps its own package node"
    # حقائق كل مستودع على عقدته — لا استبدال صامت (القيد في ظهوراته)
    specs = {f.metadata.properties["occurrences"][0]["specifier"]
             for f in flasks}
    assert specs == {">=2.0", "<3"}


def test_repeated_dependency_declarations_aggregate_not_replace(tmp_path):
    """التصحيح 0028: الحزمة المصرَّح بها في ملفين — كل الظهورات تبقى لا آخرها فقط."""
    repo = _git_repo(tmp_path / "sample", {
        "requirements.txt": "flask\n",
        "pyproject.toml": '[project]\nname = "sample"\ndependencies = ["flask"]\n',
    })
    dna = _rie_dna(repo)
    manifests = [d.get("manifest") for d in dna.dependency_details
                 if d.get("name") == "flask"]
    assert len(manifests) >= 2, "stack detection must see both declarations"

    report = fill_graph_from_dna(dna)
    flasks = report.graph.get_nodes_by_name("pypi:flask")
    assert len(flasks) == 1  # عقدة واحدة — لا تكرار
    flask = flasks[0]
    # كل الملفات شاهدة — لا يفوز آخرها على أوله
    assert {f"manifest:{m}" for m in manifests if m} <= set(flask.metadata.evidence)
    occurrences = flask.metadata.properties["occurrences"]
    assert {o["manifest"] for o in occurrences} == {m for m in manifests if m}
    # وعلى العلاقة نفسها
    rel = [r for r in report.graph.get_relationships_by_node(_repo_node(report.graph).id)
           if r.type == RelationshipType.DEPENDS_ON
           and report.graph.get_node(r.target_id).name == "pypi:flask"][0]
    assert {f"manifest:{m}" for m in manifests if m} <= set(rel.metadata.evidence)


def test_excluded_framework_evidence_is_not_a_use():
    """التصحيح 0028: دليل النواة المستبعد (counted=False) لا يُدّعى استعمالاً.

    العقدة تبقى شاهدة الاستبعاد (لا حذف — G2) لكن لا USES للمستبعد.
    """
    from agos.kernel.contracts import RepositoryDNA as KernelDNA
    dna = KernelDNA(name="sample", url="https://github.com/t/sample")
    dna.framework_evidence = [{
        "framework": "Flask", "dependency": "flask",
        "manifest": "requirements-dev.txt", "ecosystem": "pypi",
        "scope": "dev", "counted": False,
    }, {
        "framework": "Django", "dependency": "django",
        "manifest": "requirements.txt", "ecosystem": "pypi",
        "scope": "runtime", "counted": True,
    }]
    report = fill_graph_from_dna(dna)
    repo_node = _repo_node(report.graph)
    uses = {report.graph.get_node(r.target_id).name
            for r in report.graph.get_relationships_by_node(repo_node.id)
            if r.type == RelationshipType.USES}
    assert "Django" in uses
    assert "Flask" not in uses, "an excluded framework must not appear as a use"
    flask = report.graph.get_nodes_by_name("Flask")[0]
    assert flask.metadata.properties["counted"] is False
    assert "excluded:not counted as part of the project" in flask.metadata.evidence


def test_named_gaps_survive_save_and_load(tmp_path):
    """التصحيح 0028: الفجوات المسمّاة لا تضيع بين الذاكرة والقرص."""
    repo = _git_repo(tmp_path / "sample", SAMPLE_FILES)
    dna = _rie_dna(repo)
    expected_gap = [g for g in fill_graph_from_dna(dna).gaps]
    assert any("framework_evidence not carried by rie DNA" in g for g in expected_gap)

    graph_path = tmp_path / "gaps.json"
    fill_and_save(dna, str(graph_path))
    loaded = KnowledgeGraph.load(str(graph_path))
    stored = _repo_node(loaded).metadata.properties.get("analysis_gaps")
    assert stored == expected_gap, "named gaps must survive save and load verbatim"


def test_update_node_refreshes_indexes():
    """التصحيح 0028: تعديل العقدة كان لا ينعش الفهارس — البحث بالقيمة الجديدة
    كان يعجز والقديمة تكذب. الآن الفهارس تتبع القيم الجديدة."""
    graph = KnowledgeGraph(name="idx")
    from agos.kernel.civilization.knowledge_graph.nodes.base import create_node
    n = create_node(NodeType.PACKAGE, "old-name", path="pkg:old", repository="r")
    graph.add_node(n)
    assert graph.get_nodes_by_name("old-name")
    assert not graph.get_nodes_by_name("new-name")

    assert graph.update_node(n.id, {"name": "new-name", "path": "pkg:new"}) is True
    assert graph.get_nodes_by_name("new-name"), "new value must be findable"
    assert not graph.get_nodes_by_name("old-name"), "old value must not be found"
    assert n.id in graph._node_path_index["pkg:new"]
    assert n.id not in graph._node_path_index.get("pkg:old", set())
    # والفهرس الحالي للعقدة صحيح: العقدة الواحدة لا تُدَعّل مرتين
    assert len(graph._node_name_index["new-name"]) == 1


def test_unsupported_dna_shape_is_rejected_by_name():
    class NotADna:
        pass
    with pytest.raises(ValueError, match="Unsupported DNA shape"):
        fill_graph_from_dna(NotADna())


# ---------------------------------------------------------------------------
# المسار الإنتاجي: قدرة تحليل المستودع تحفظ الرسم عند طلبه (طازجاً ومن الكاش)
# ---------------------------------------------------------------------------

def _capability_dna(repo, graph_path, cache=True):
    cap = RepositoryAnalysisCapability()
    dna = cap.execute({"url": f"file://{repo}", "branch": "main",
                       "knowledge_graph_path": str(graph_path), "cache": cache})
    return dna


def test_kernel_capability_saves_graph_on_analysis_path(tmp_path):
    repo = _git_repo(tmp_path / "sample", dict(SAMPLE_FILES, **{"pyproject.toml": PYPROJECT_SCRIPTS}))
    out = tmp_path / "out"
    dna = _capability_dna(repo, out / "sample.json")

    assert dna.framework_evidence, "kernel DNA carries framework evidence"
    saved = out / "sample.json"
    assert saved.exists()
    loaded = KnowledgeGraph.load(str(saved))

    repo_node = _repo_node(loaded)
    assert repo_node.name == "sample"
    # أطر بأدلة صريحة من مسار النواة (لا فجوة هنا)
    uses = [r for r in loaded.get_relationships_by_node(repo_node.id)
            if r.type == RelationshipType.USES]
    assert uses, "the production path must fill framework relationships"
    assert all(r.metadata.evidence for r in uses)

    # نقطة الدخول المعلنة في pyproject تصل الرسم بوصفها تصريحاً لا ملف API
    entries = [n for n in loaded.get_nodes_by_type(NodeType.FILE)
               if n.metadata.properties.get("role") == "entry_point"]
    assert any("pyproject.toml" in n.path for n in entries)

    # استعلام من الرسم المحفوظ من المسار الإنتاجي
    query = QueryEngine(loaded)
    assert query.find_node(node_type=NodeType.PACKAGE, name="pypi:flask") is not None


def test_kernel_capability_saves_graph_on_cache_hit(tmp_path, capsys, monkeypatch):
    repo = _git_repo(tmp_path / "sample", SAMPLE_FILES)
    out = tmp_path / "out"
    cap = RepositoryAnalysisCapability()
    args = {"url": f"file://{repo}", "branch": "main", "cache": True}

    cap.execute(dict(args, knowledge_graph_path=str(out / "fresh.json")))
    capsys.readouterr()  # نرمي مخرجات التحليل الأول

    # إثبات قاطع: تعطيل الاستنساخ نفسه — إن لم يكن الكاش هو المسار لدُهِقَ الاختبار
    from providers import LocalRepositoryProvider

    def _no_clone(*a, **kw):
        raise AssertionError("cache hit must not clone the repository")
    monkeypatch.setattr(LocalRepositoryProvider, "_clone", _no_clone)

    cap.execute(dict(args, knowledge_graph_path=str(out / "cached.json")))
    second_out = capsys.readouterr().out
    assert "Reusing DNA" in second_out, "the second call must be a cache hit"
    assert (out / "fresh.json").exists() and (out / "cached.json").exists()
    fresh = KnowledgeGraph.load(str(out / "fresh.json"))
    cached = KnowledgeGraph.load(str(out / "cached.json"))
    # إعادة الاستخدام من الكاش تُنتج الرسم نفسه — لا مساراً موازياً ضعيفاً
    assert (len(fresh), fresh.get_statistics().total_relationships) == \
        (len(cached), cached.get_statistics().total_relationships)
    assert {n.name for n in fresh.get_nodes_by_type(NodeType.PACKAGE)} == \
        {n.name for n in cached.get_nodes_by_type(NodeType.PACKAGE)}


# ---------------------------------------------------------------------------
# إصلاح مُصاحب (R-W2-008): باني الرسم يحفظ الرسم الفارغ المُمرَّر
# ---------------------------------------------------------------------------

def test_graph_builder_keeps_supplied_empty_graph():
    empty = KnowledgeGraph(name="kept")
    builder = GraphBuilder(graph=empty)
    assert builder.graph is empty, "an empty supplied graph must not be silently replaced"
    assert len(builder.graph) == 0
