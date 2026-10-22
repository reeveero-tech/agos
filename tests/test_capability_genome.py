"""R-W2-012 — جينوم القدرات CGP: تقرير قدرات لمستودع حقيقي.

كل تأكيد فعلي (R-Q-001): الحالات المميِّزة للمستخرج الثابت — الإيجابية بأدلة
مسماة (ملف/سطر/رمز محيط)، والسلبية (ذِكر README/تعليق/نصّ/اسم محجوب لا يُعد
دليلاً)، والمصرَّح به فقط لا يُدّعى تنفيذاً، والتركيب لا يُعلن verified إلا
بأدلة إنتاج داخل رمز واحد، والفجوات تُسمّى (غير المقروء/لغة بلا مستخرج/
مقاييس غير مقيسة)، والقبول على مستودع حقيقي (AGOS نفسه) بحقائق ملموسة.
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agos" / "agos-kernel"))

from capabilities.analysis_service import get_analysis_service  # noqa: E402
from capabilities.genome import (  # noqa: E402
    CapabilityGenomeCapability,
    build_capability_genome,
)

GENOME_AT = datetime(2026, 10, 22, 12, 0, tzinfo=timezone.utc)
REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_repo(path, files):
    path.mkdir(parents=True, exist_ok=True)
    for rel, text in files.items():
        p = path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return path


def _genome_of(path):
    shared = get_analysis_service().analyze_path(str(path))
    return build_capability_genome(shared, generated_at=GENOME_AT)


# ---------------------------------------------------------------------------
# الإيجابية: استدعاء فعلي في إنتاج ⇒ statically_supported بأدلة مسماة
# ---------------------------------------------------------------------------

class TestPositiveEvidence:
    def test_real_calls_are_statically_supported_with_named_evidence(self, tmp_path):
        repo = _write_repo(tmp_path / "src", {
            "app.py": (
                "import json\n"
                "import requests\n"
                "\n"
                "def fetch_config(url):\n"
                "    resp = requests.get(url)\n"
                "    data = json.loads(resp.text)\n"
                "    return data\n"
            ),
            "requirements.txt": "requests>=2.0\n",
        })
        out = _genome_of(repo)
        http = out["skills"]["http_request"]
        assert http["status"] == "statically_supported"
        # الدليل مسمّى: ملف/سطر/رمز محيط — لا مجرد وجود المفتاح
        assert http["findings"] == [{
            "file": "app.py", "line": 5, "symbol": "fetch_config",
            "rule": "attr:requests.get", "context": "production",
        }]
        assert out["skills"]["parse_json"]["status"] == "statically_supported"

    def test_aliases_and_multiline_calls_are_followed(self, tmp_path):
        repo = _write_repo(tmp_path / "src", {
            "client.py": (
                "import requests as rq\n"
                "\n"
                "def ping(base):\n"
                "    return rq.get(\n"
                "        base + \"/health\",\n"
                "    )\n"
            ),
        })
        out = _genome_of(repo)
        findings = out["skills"]["http_request"]["findings"]
        assert findings[0]["rule"] == "attr:requests.get"
        assert findings[0]["line"] == 4
        assert findings[0]["symbol"] == "ping"

    def test_composed_capability_verified_in_one_symbol(self, tmp_path):
        repo = _write_repo(tmp_path / "src", {
            "app.py": (
                "import json\n"
                "import requests\n"
                "\n"
                "def fetch_config(url):\n"
                "    resp = requests.get(url)\n"
                "    return json.loads(resp.text)\n"
            ),
        })
        out = _genome_of(repo)
        cap = out["capabilities"]["HttpJsonClient"]
        assert cap["status"] == "verified"
        assert cap["composed_in"] == [{"file": "app.py", "symbol": "fetch_config"}]
        assert cap["missing_skills"] == []


# ---------------------------------------------------------------------------
# السلبية: ما ليس دليلاً لا يُحسب — ذِكر نصّي ليس تنفيذاً
# ---------------------------------------------------------------------------

class TestNegativeEvidence:
    def test_readme_mentions_are_not_evidence(self, tmp_path):
        repo = _write_repo(tmp_path / "src", {
            "README.md": "We use requests.get(url) and json.loads everywhere!\n",
            "main.py": "x = 1\n",
        })
        out = _genome_of(repo)
        assert out["skills"]["http_request"]["status"] == "not_detected"
        assert out["skills"]["parse_json"]["status"] == "not_detected"

    def test_strings_and_docstrings_are_not_evidence(self, tmp_path):
        repo = _write_repo(tmp_path / "src", {
            "main.py": (
                "\"\"\"Module docs: call requests.get(url) then json.loads.\"\"\"\n"
                "\n"
                "def describe():\n"
                "    return \"we run subprocess.run(['git', 'status']) here\"\n"
            ),
        })
        out = _genome_of(repo)
        assert out["skills"]["http_request"]["status"] == "not_detected"
        assert out["skills"]["parse_json"]["status"] == "not_detected"
        assert out["skills"]["git_operations"]["status"] == "not_detected"

    def test_shadowed_rebound_names_are_not_evidence(self, tmp_path):
        # الاسم المعاد ربطه محجوب كلياً — لا يُبنى دليل فوق رابط مشكوك
        repo = _write_repo(tmp_path / "src", {
            "odd.py": (
                "import json\n"
                "json = {'loads': lambda x: x}\n"
                "def parse(text):\n"
                "    return json.loads(text)\n"
            ),
        })
        out = _genome_of(repo)
        assert out["skills"]["parse_json"]["status"] == "not_detected"

    def test_declared_dependency_alone_is_not_implementation(self, tmp_path):
        repo = _write_repo(tmp_path / "src", {
            "pyproject.toml": (
                "[project]\nname = \"x\"\nversion = \"0\"\n"
                "[dependency-groups]\ndev = [\"pytest>=8\"]\n"
            ),
            "main.py": "x = 1\n",
        })
        out = _genome_of(repo)
        run_tests = out["skills"]["run_tests"]
        assert run_tests["status"] == "declared"
        assert run_tests["declared_in"] == ["pytest@pypi"]
        assert run_tests["findings"] == []
        # والمصرَّح به وحده قدرة «declared» لا verified — والناقص مسمّى
        cap = out["capabilities"]["TestExecution"]
        assert cap["status"] == "declared"
        assert cap["composed_in"] == []
        assert cap["missing_skills"] == []

    def test_test_file_evidence_is_test_only_not_production(self, tmp_path):
        repo = _write_repo(tmp_path / "src", {
            "tests/test_web.py": (
                "import requests\n"
                "def test_get():\n"
                "    assert requests.get('http://x').status_code == 200\n"
            ),
            "main.py": "x = 1\n",
        })
        out = _genome_of(repo)
        http = out["skills"]["http_request"]
        assert http["status"] == "test_only"
        assert http["findings"][0]["context"] == "test"
        # أدلة الاختبار لا تُثبت قدرة إنتاج — ولا تركيباً موثقاً
        assert out["capabilities"]["HttpJsonClient"]["status"] == "absent"

    def test_unrelated_skills_in_separate_symbols_do_not_compose(self, tmp_path):
        repo = _write_repo(tmp_path / "src", {
            "split.py": (
                "import json\n"
                "import requests\n"
                "def parse(text):\n"
                "    return json.loads(text)\n"
                "def fetch(url):\n"
                "    return requests.get(url)\n"
            ),
        })
        out = _genome_of(repo)
        cap = out["capabilities"]["HttpJsonClient"]
        # المهارتان موجودتان لكن لا في رمز واحد ⇒ candidate لا verified
        assert cap["status"] == "candidate"
        assert cap["composed_in"] == []


# ---------------------------------------------------------------------------
# الفجوات المسمّاة — النقص يُعلن لا يُخفى (ADR-0002)
# ---------------------------------------------------------------------------

class TestNamedGaps:
    def test_unread_python_file_is_a_named_gap(self, tmp_path):
        repo = _write_repo(tmp_path / "src", {"main.py": "x = 1\n"})
        # ملف بيثون كبير فوق حد القراءة (1MB) — غير مقروء لا مُفترى عليه
        big = repo / "big.py"
        big.write_text("# padding\n" + "y = 0\n" * 300_000, encoding="utf-8")
        out = _genome_of(repo)
        assert any(g.startswith("python-files-unread: 1") for g in out["gaps"])
        assert out["coverage"]["python_files_unread"] == 1

    def test_unsupported_language_is_a_named_gap(self, tmp_path):
        repo = _write_repo(tmp_path / "src", {
            "main.go": "package main\nfunc main() {}\n",
            "main.py": "x = 1\n",
        })
        out = _genome_of(repo)
        assert any("no-static-extractor-for-languages" in g and "Go" in g
                   for g in out["gaps"])

    def test_local_path_commit_gap_is_named(self, tmp_path):
        repo = _write_repo(tmp_path / "src", {"main.py": "x = 1\n"})
        out = _genome_of(repo)
        assert any(g.startswith("commit-unknown") for g in out["gaps"])
        assert out["repository"]["commit"] == ""

    def test_performance_metrics_are_never_fabricated(self, tmp_path):
        repo = _write_repo(tmp_path / "src", {"main.py": "x = 1\n"})
        out = _genome_of(repo)
        assert any(g.startswith("performance-metrics-unmeasured") for g in out["gaps"])
        flat = json.dumps(out)
        assert "accuracy" not in flat.replace(
            "performance-metrics-unmeasured: accuracy/cost/duration/success-rate", "")
        assert "success_rate" not in flat.replace(
            "performance-metrics-unmeasured: accuracy/cost/duration/success-rate", "")

    def test_scan_errors_propagate_as_named_gaps(self, tmp_path):
        repo = _write_repo(tmp_path / "src", {"main.py": "x = 1\n"})
        # مجلد غير قابل للإدراج ⇒ خطأ وصول أثناء المسح نفسه — يُعلن لا يُبلع
        locked_dir = repo / "locked_dir"
        locked_dir.mkdir()
        (locked_dir / "secret.py").write_text("z = 2\n", encoding="utf-8")
        os.chmod(locked_dir, 0)
        try:
            out = _genome_of(repo)
        finally:
            os.chmod(locked_dir, 0o755)
        assert any(g.startswith("scan-error:") and "locked_dir" in g
                   for g in out["gaps"])


# ---------------------------------------------------------------------------
# الحتمية والإصدار — البناء صرف فوق الحقائق (لا مسح جديد)
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_same_facts_same_genome(self, tmp_path):
        repo = _write_repo(tmp_path / "src", {
            "app.py": "import json\njson.loads('{}')\n",
        })
        shared = get_analysis_service().analyze_path(str(repo))
        first = build_capability_genome(shared, generated_at=GENOME_AT)
        second = build_capability_genome(shared, generated_at=GENOME_AT)
        assert first == second

    def test_versions_and_catalog_counters_separated(self, tmp_path):
        repo = _write_repo(tmp_path / "src", {"main.py": "x = 1\n"})
        out = _genome_of(repo)
        assert out["genome_schema_version"] == "cgp-1.0"
        assert out["rules_version"] == "python-ast-2"
        assert out["generated_at"] == GENOME_AT.isoformat()
        # عدادات الكتالوج مفصولة عن نتائج هذا المستودع — الكتالوج لا يُحسب
        # كأنه مكتشف: مستودع بلا شيفرة لا يدّعي قدرات
        assert out["catalog_skill_count"] == len(out["skills"])
        assert out["catalog_capability_count"] == len(out["capabilities"])
        assert out["supported_skill_count"] == 0
        assert out["verified_capability_count"] == 0

    def test_generated_at_is_required(self, tmp_path):
        repo = _write_repo(tmp_path / "src", {"main.py": "x = 1\n"})
        shared = get_analysis_service().analyze_path(str(repo))
        with pytest.raises(TypeError):
            build_capability_genome(shared)


# ---------------------------------------------------------------------------
# القدرة — مدخل واحد فوق الخط الموحد، حل بالاسم عبر المسار الحقيقي
# ---------------------------------------------------------------------------

class TestCapabilityEntry:
    def test_execute_via_repo_path_uses_unified_line(self, tmp_path, monkeypatch):
        repo = _write_repo(tmp_path / "src", {"main.py": "x = 1\n"})
        calls = {"n": 0}
        original = type(get_analysis_service()).analyze_path

        def counting(self, path, policy=None):
            calls["n"] += 1
            return original(self, path, policy)

        monkeypatch.setattr(type(get_analysis_service()), "analyze_path", counting)
        out = CapabilityGenomeCapability().execute({"repo_path": str(repo)})
        assert calls["n"] == 1          # مسح واحد عبر الخط الموحد لا خط خاص
        assert out["capability"] == "CapabilityGenome"
        assert out["repository"]["name"] == "src"

    def test_url_flow_records_commit_from_provider(self, tmp_path, monkeypatch):
        import shutil

        src = _write_repo(tmp_path / "src", {
            "app.py": "import json\ndef p(t):\n    return json.loads(t)\n"})
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=src,
                       capture_output=True, check=True)
        subprocess.run(["git", "remote", "add", "origin",
                        "https://github.com/example/x.git"], cwd=src,
                       capture_output=True, check=True)
        subprocess.run(["git", "add", "-A"], cwd=src, capture_output=True, check=True)
        subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t",
                        "commit", "-qm", "c"], cwd=src, capture_output=True,
                       check=True)
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=src,
                             capture_output=True, text=True, check=True).stdout.strip()

        from providers import LocalRepositoryProvider

        def fake_clone(self, input_data):
            class R:
                path = str(src)
            return R()

        monkeypatch.setattr(LocalRepositoryProvider, "_clone", fake_clone)
        monkeypatch.setattr(shutil, "rmtree", lambda *a, **k: None)

        out = CapabilityGenomeCapability().execute(
            {"url": "https://github.com/example/x", "branch": "main"})
        assert out["repository"]["commit"] == head
        assert out["repository"]["branch"] == "main"
        assert out["skills"]["parse_json"]["status"] == "statically_supported"

    def test_bad_inputs_raise(self):
        cap = CapabilityGenomeCapability()
        with pytest.raises(ValueError):
            cap.execute({"url": "u", "repo_path": "p"})
        with pytest.raises(ValueError):
            cap.execute({})
        with pytest.raises(ValueError):
            cap.execute("not a dict")

    def test_mission_resolves_by_name_and_executes(self, tmp_path):
        from agos.kernel import agos_runtime
        repo = _write_repo(tmp_path / "src", {"main.py": "x = 1\n"})
        k = agos_runtime.boot()
        outcome = k.run({
            "name": "Genome", "description": "capability genome",
            "capability": "CapabilityGenome",
            "parameters": {"repo_path": str(repo)},
        })
        assert outcome.state.value == "completed"
        assert outcome.result["capability"] == "CapabilityGenome"
        events = k.event_bus.get_events(outcome.mission_id)
        selected = [e.data for e in events if e.type.value == "capability_selected"]
        assert any(d.get("capability") == "CapabilityGenome"
                   for d in selected if isinstance(d, dict))


# ---------------------------------------------------------------------------
# القبول — تقرير قدرات لمستودع حقيقي: AGOS نفسه بحقائق ملموسة
# ---------------------------------------------------------------------------

class TestRealRepositoryAcceptance:
    """معيار القبول (الخارطة): «تقرير قدرات لمستودع حقيقي».

    المستودع الحقيقي هو مستودع AGOS نفسه عند جذر الاختبارات — شيفرة إنتاج
    حقيقية ووثائق CI حقيقية وملفات اعتماديات حقيقية، والحقائق ملموسة لا مُفتراة.
    """

    @pytest.fixture(scope="class")
    def agos_genome(self):
        shared = get_analysis_service().analyze_path(str(REPO_ROOT))
        return build_capability_genome(shared, generated_at=GENOME_AT)

    def test_report_is_complete_and_serializable(self, agos_genome):
        flat = json.dumps(agos_genome, ensure_ascii=False)
        assert len(flat) > 1000
        assert agos_genome["repository"]["name"] == "agos"
        assert agos_genome["coverage"]["python_files"] > 500
        assert agos_genome["coverage"]["files_read"] == agos_genome["coverage"]["files_total"]

    def test_production_skills_with_real_files(self, agos_genome):
        # run_command: أدوات الجودة تستدعي subprocess.run فعلياً (إنتاج)
        run_command = agos_genome["skills"]["run_command"]
        assert run_command["status"] == "statically_supported"
        assert any(f["file"] == "tools/quality/run_tests.py"
                   and f["rule"] == "attr:subprocess.run"
                   for f in run_command["findings"])
        # parse_yaml: خط rie يقرأ yaml فعلياً
        parse_yaml = agos_genome["skills"]["parse_yaml"]
        assert parse_yaml["status"] == "statically_supported"
        assert any(f["file"] == "agos/rie/application/dna_generator.py"
                   for f in parse_yaml["findings"])

    def test_git_automation_verified_with_composition(self, agos_genome):
        # git_operations: استدعاءات git صريحة عبر مدير العمليات — والقدرة
        # verified بتركيب داخل رمز واحد
        git = agos_genome["skills"]["git_operations"]
        assert git["status"] == "statically_supported"
        assert any(f["rule"].startswith("git-arg:") for f in git["findings"])
        cap = agos_genome["capabilities"]["GitAutomation"]
        assert cap["status"] == "verified"
        assert cap["composed_in"]

    def test_declared_and_absent_are_honest(self, agos_genome):
        # pytest معلن (dev) لكن لا استدعاء pytest.main في الإنتاج ولا أمر اختبار
        # مباشر في CI (CI يشغّل عدّاداً خاصاً) ⇒ declared لا أكثر
        assert agos_genome["skills"]["run_tests"]["status"] == "declared"
        assert agos_genome["capabilities"]["TestExecution"]["status"] == "declared"
        # HTTP فعلي في الإنتاج: urllib.request.urlopen (فاحص OSV ومزوّد GitHub)
        # — وطلبات requests الوحيدة داخل قوالب نصية مولّدة لا تُحسب
        assert agos_genome["skills"]["http_request"]["status"] == "statically_supported"
        assert any(f["file"] == "agos/agos-kernel/capabilities/foundation_extra.py"
                   and f["symbol"] == "osv_query_batch"
                   for f in agos_genome["skills"]["http_request"]["findings"])
        # والتركيب حقيقي: فاحص OSV يجلب JSON عبر urllib ويحلله في الدالة نفسها
        cap = agos_genome["capabilities"]["HttpJsonClient"]
        assert cap["status"] == "verified"
        assert {"file": "agos/agos-kernel/capabilities/foundation_extra.py",
                "symbol": "osv_query_batch"} in cap["composed_in"]

    def test_gaps_are_named_for_the_real_repo(self, agos_genome):
        gaps = agos_genome["gaps"]
        # المقاييس غير المقيسة معلنة — والالتزام غير معروف لمسار محلي بلا git
        assert any(g.startswith("performance-metrics-unmeasured") for g in gaps)
        assert any(g.startswith("commit-unknown") for g in gaps)


# ---------------------------------------------------------------------------
# النطاقات المعجمية وصدق التقرير — تصحيحات المدقق النهائي
# ---------------------------------------------------------------------------

class TestLexicalScopesAndHonesty:
    def test_function_local_import_does_not_bind_other_functions(self, tmp_path):
        # استيراد داخل دالة لا يصير رابطاً في دالة شقيقة — نطاق معجمي
        repo = _write_repo(tmp_path / "src", {
            "app.py": (
                "def a():\n"
                "    import requests\n"
                "    return requests.get('http://x')\n"
                "\n"
                "def b(url):\n"
                "    return requests.get(url)\n"   # NameError وقت التشغيل — لا رابط
            ),
        })
        out = _genome_of(repo)
        http = out["skills"]["http_request"]
        # استدعاء الدالة a وحده معروف؛ استدعاء b فوق اسم غير مربوط لا يُحسب
        assert [f["symbol"] for f in http["findings"]] == ["a"]

    def test_qualified_symbols_do_not_collide(self, tmp_path):
        # دالتان بالاسم نفسه في صنفين — الهوية مؤهلة فلا يُدّعى تركيب مزيف
        repo = _write_repo(tmp_path / "src", {
            "app.py": (
                "import json\n"
                "import requests\n"
                "class A:\n"
                "    def run(self, url):\n"
                "        return requests.get(url)\n"
                "class B:\n"
                "    def run(self, text):\n"
                "        return json.loads(text)\n"
            ),
        })
        out = _genome_of(repo)
        cap = out["capabilities"]["HttpJsonClient"]
        assert cap["status"] == "candidate"
        assert cap["composed_in"] == []

    def test_composition_verified_within_one_qualified_symbol(self, tmp_path):
        repo = _write_repo(tmp_path / "src", {
            "app.py": (
                "import json\n"
                "import requests\n"
                "class Client:\n"
                "    def fetch(self, url):\n"
                "        return json.loads(requests.get(url).text)\n"
            ),
        })
        out = _genome_of(repo)
        cap = out["capabilities"]["HttpJsonClient"]
        assert cap["status"] == "verified"
        assert cap["composed_in"] == [{"file": "app.py", "symbol": "Client.fetch"}]

    def test_dotted_stdlib_module_resolves_once(self, tmp_path):
        # import urllib.request يربط urllib ⇒ urlopen يُحل بلا ازدواج request
        repo = _write_repo(tmp_path / "src", {
            "app.py": (
                "import urllib.request\n"
                "def ping(url):\n"
                "    return urllib.request.urlopen(url)\n"
            ),
        })
        out = _genome_of(repo)
        findings = out["skills"]["http_request"]["findings"]
        assert findings == [{
            "file": "app.py", "line": 3, "symbol": "ping",
            "rule": "attr:urllib.request.urlopen", "context": "production",
        }]

    def test_pathlib_receiver_counted_unknown_receiver_not(self, tmp_path):
        # Path(...).read_text دليل (المستقبل معروف)؛ x.read_text على مستقبل
        # مجهول ليس دليلاً — والدالة الفارغة لا تنجو من القاعدة نفسها
        repo = _write_repo(tmp_path / "src", {
            "app.py": (
                "from pathlib import Path\n"
                "def load(p):\n"
                "    return Path(p).read_text()\n"
                "def mystery(x):\n"
                "    return x.read_text()\n"
            ),
        })
        out = _genome_of(repo)
        findings = out["skills"]["file_read"]["findings"]
        assert [f["symbol"] for f in findings] == ["load"]
        assert findings[0]["rule"] == "attr:pathlib.Path.read_text"

    def test_redefined_open_and_dynamic_mode_are_not_evidence(self, tmp_path):
        repo = _write_repo(tmp_path / "src", {
            "app.py": (
                "def open(name, mode):\n"       # تعريف المستخدم — محجوب
                "    return None\n"
                "def w(name, mode):\n"
                "    return open(name, mode)\n"
            ),
        })
        out = _genome_of(repo)
        assert out["skills"]["file_read"]["status"] == "not_detected"
        assert out["skills"]["file_write"]["status"] == "not_detected"

    def test_ci_command_matching_is_token_based(self, tmp_path):
        repo = _write_repo(tmp_path / "src", {
            ".github/workflows/ci.yml": (
                "on: [push]\n"
                "jobs:\n"
                "  build:\n"
                "    runs-on: ubuntu-latest\n"
                "    steps:\n"
                "      - run: pip install pytest\n"     # ذِكر لا تشغيل
                "      - run: echo pytest\n"            # ذِكر لا تشغيل
                "      - run: pytest tests/\n"          # تشغيل فعلي
            ),
            "main.py": "x = 1\n",
        })
        out = _genome_of(repo)
        findings = out["skills"]["run_tests"]["findings"]
        assert len(findings) == 1
        assert findings[0]["rule"] == "ci-run:pytest"
        # موقع حقيقي (سطر الخطوة) ورمز job/step — لا سطر صفر افتراضي
        assert findings[0]["line"] == 8
        assert findings[0]["symbol"] == "jobs.build.steps[2].run"
        assert out["capabilities"]["TestExecution"]["status"] == "verified"

    def test_invalid_ci_workflow_is_a_named_gap(self, tmp_path):
        repo = _write_repo(tmp_path / "src", {
            ".github/workflows/broken.yml": "jobs: [unclosed\n",
            "main.py": "x = 1\n",
        })
        out = _genome_of(repo)
        assert any(g.startswith("ci-workflow-parse-errors: 1")
                   and "broken.yml" in g for g in out["gaps"])

    def test_parse_error_details_are_reported_not_just_counted(self, tmp_path):
        repo = _write_repo(tmp_path / "src", {
            "bad.py": "def f(:\n",
            "main.py": "x = 1\n",
        })
        out = _genome_of(repo)
        assert out["python_parse_errors"] == ["bad.py: SyntaxError: line 1"]
        assert any("bad.py: SyntaxError" in g for g in out["gaps"])

    def test_unread_files_listed_with_reasons(self, tmp_path):
        repo = _write_repo(tmp_path / "src", {"main.py": "x = 1\n"})
        big = repo / "big.py"
        big.write_text("# padding\n" + "y = 0\n" * 300_000, encoding="utf-8")
        out = _genome_of(repo)
        assert out["unread_python_files"] == {"big.py": "too_large"}

    def test_dependency_records_failure_is_a_named_gap(self, tmp_path, monkeypatch):
        repo = _write_repo(tmp_path / "src", {"main.py": "x = 1\n"})
        import stack_detection
        def boom(report):
            raise RuntimeError("records unavailable")
        monkeypatch.setattr(stack_detection, "dependency_records", boom)
        out = _genome_of(repo)
        assert any(g.startswith("dependency-records-unavailable:")
                   for g in out["gaps"])


# ---------------------------------------------------------------------------
# تصحيحات المراجعة الثانية — نطاق الصنف وسلاسل الصفات وCI
# ---------------------------------------------------------------------------

class TestSecondReviewCorrections:
    def test_class_body_import_does_not_bind_methods(self, tmp_path):
        # جسم الصنف ليس نطاقاً معجمياً لطرقه: الاستيراد داخل الصنف لا تراه
        # الطريقة وقت التشغيل (NameError) فلا يكون دليلاً
        repo = _write_repo(tmp_path / "src", {
            "app.py": (
                "class C:\n"
                "    import requests\n"
                "    def run(self, url):\n"
                "        return requests.get(url)\n"
            ),
        })
        out = _genome_of(repo)
        assert out["skills"]["http_request"]["status"] == "not_detected"

    def test_rebound_root_name_blocks_whole_attribute_chain(self, tmp_path):
        # urllib = None ثم urllib.request.urlopen: الجذر المعاد ربطه يحجب
        # السلسلة كلها — فحص المستقبل المباشر فقط لا يكفي
        repo = _write_repo(tmp_path / "src", {
            "app.py": (
                "import urllib.request\n"
                "urllib = None\n"
                "def f(u):\n"
                "    return urllib.request.urlopen(u)\n"
            ),
        })
        out = _genome_of(repo)
        assert out["skills"]["http_request"]["status"] == "not_detected"

    def test_aliased_dotted_import_resolves_submodule(self, tmp_path):
        # import urllib.request as req: req.urlopen هو urllib.request.urlopen
        repo = _write_repo(tmp_path / "src", {
            "app.py": (
                "import urllib.request as req\n"
                "def f(u):\n"
                "    return req.urlopen(u)\n"
            ),
        })
        out = _genome_of(repo)
        findings = out["skills"]["http_request"]["findings"]
        assert findings == [{
            "file": "app.py", "line": 3, "symbol": "f",
            "rule": "attr:urllib.request.urlopen", "context": "production",
        }]

    def test_steps_run_outside_jobs_key_is_not_ci_evidence(self, tmp_path):
        # بنية steps/run تحت مفتاح جذر آخر ليست وظيفة CI — لا تُحسب
        repo = _write_repo(tmp_path / "src", {
            ".github/workflows/odd.yml": (
                "defaults:\n"
                "  steps:\n"
                "    - run: pytest tests/\n"
            ),
            "main.py": "x = 1\n",
        })
        out = _genome_of(repo)
        assert out["skills"]["run_tests"]["status"] == "not_detected"

    def test_heredoc_step_is_unsupported_named_gap_not_evidence(self, tmp_path):
        # سطر داخل heredoc قد يكون محتوى مكتوباً لملف — لا يُستنتج منه
        # دليل؛ صيغة غير مدعومة معلنة كفجوة
        repo = _write_repo(tmp_path / "src", {
            ".github/workflows/ci.yml": (
                "jobs:\n"
                "  build:\n"
                "    steps:\n"
                "      - run: |\n"
                "          cat <<'EOF' > config.txt\n"
                "          pytest\n"
                "          EOF\n"
            ),
            "main.py": "x = 1\n",
        })
        out = _genome_of(repo)
        assert out["skills"]["run_tests"]["status"] == "not_detected"
        assert any(g.startswith("ci-run-unsupported-forms: 1")
                   and "(heredoc)" in g for g in out["gaps"])

    def test_snapshot_identity_is_embedded_verbatim(self, tmp_path):
        repo = _write_repo(tmp_path / "src", {"main.py": "x = 1\n"})
        shared = get_analysis_service().analyze_path(str(repo))
        snap = {"base_commit": "abc123", "input_fingerprint": "deadbeef"}
        out = build_capability_genome(shared, generated_at=GENOME_AT,
                                      snapshot=snap)
        assert out["analysis_snapshot"] == snap
