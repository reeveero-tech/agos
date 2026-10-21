"""R-W2-003 — languages are weighted by lines and files, and the primary is correct.

Acceptance (ROADMAP): "وزن اللغات بعدد الأسطر/الملفات؛ اللغة الرئيسية الصحيحة" على
"مستودعات مرجعية متعدد اللغات".

* Unit: ``language_weights`` / ``primary_language`` / ``read_code_files`` — lines are the
  weight (a thousand-line module outweighs ten one-line scripts), ties break by file count
  then name, vendored directories (node_modules, …) never count, and unreadable content
  still counts as a file.
* Offline multilingual reference repositories with exact expected weights and primary.
* Online reference repositories pinned to release tags — the primary language of each is
  a public, independently verifiable fact (the language of the project itself).
* End-to-end: every path that detects languages now goes through
  ``agos.kernel.stack_detection`` — the kernel capability (main path), RIE, the civilization
  RepositoryAnalyzer and LanguageDetectionStage, the intelligence analyzer/ProjectDNA and
  the repo-discovery slice.
"""
import asyncio
import json
import os
import shutil
import subprocess

import pytest

from agos.kernel import stack_detection as sd


def _write(root, files):
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    return root


def _git_repo(tmp_path, files):
    repo = _write(tmp_path / "ref", files)
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@t", "PATH": os.environ["PATH"]}
    for cmd in (["git", "init", "-q", "-b", "main"], ["git", "add", "-A", "-f"],
                ["git", "commit", "-qm", "init"]):
        subprocess.run(cmd, cwd=repo, check=True, env=env, capture_output=True)
    return repo


needs_git = pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")


def _reachable(url):
    try:
        subprocess.run(["git", "ls-remote", url, "HEAD"], check=True,
                       capture_output=True, timeout=20)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Unit: the weight is lines, the primary is the one with the most lines
# ---------------------------------------------------------------------------
def test_lines_are_the_weight_not_file_count():
    files = {f"script{i}.js": "x\n" for i in range(10)}  # 10 files, 1 line each
    files["app.py"] = "x\n" * 1000                        # 1 file, 1000 lines
    weights = sd.language_weights(files)
    assert sd.primary_language(weights) == "Python"
    assert list(weights) == ["Python", "JavaScript"]
    assert weights["JavaScript"].files == 10 and weights["JavaScript"].lines == 10
    assert weights["Python"].files == 1 and weights["Python"].lines == 1000


def test_tie_on_lines_breaks_on_files_then_name():
    weights = sd.language_weights({"a.py": "x\nx\n", "b.js": "x\nx\n", "c.go": "x\nx\n"})
    assert sd.primary_language(weights) == "Go"  # same lines & files → alphabetically first
    weights = sd.language_weights({"a.py": "x\nx\n", "b.js": "x\nx\n", "c.go": "x\n"})
    assert sd.primary_language(weights) == "JavaScript"  # more files breaks the tie
    # A genuine file-count tie-break: 2 JS files of 1 line each vs 1 Python file of
    # 2 lines — same line weight, JavaScript wins by file count.
    weights = sd.language_weights({"one.js": "x\n", "two.js": "x\n", "app.py": "x\nx\n"})
    assert sd.primary_language(weights) == "JavaScript"


def test_manifests_are_not_languages():
    files = {"package.json": '{"dependencies": {}}', "go.mod": "module x\n",
             "requirements.txt": "flask\n", "Cargo.toml": "[package]\n", "README.md": "hi\n"}
    assert sd.language_weights(files) == {}


def test_vendored_directories_never_count():
    files = {"node_modules/left-pad/index.js": "x\n" * 50, "app.py": "x\n"}
    weights = sd.language_weights(files)
    assert list(weights) == ["Python"]
    assert weights["Python"].lines == 1


def test_unreadable_content_still_counts_as_a_file():
    weights = sd.language_weights({"a.py": None, "b.py": "x\n"})
    assert weights["Python"].files == 2 and weights["Python"].lines == 1


def test_no_trailing_newline_is_still_a_line():
    assert sd.language_weights({"a.py": "x\ny"}).values().__iter__().__next__().lines == 2


def test_empty_repo_has_no_languages():
    assert sd.language_weights({"README.md": "hi\n"}) == {}
    assert sd.primary_language({}) == ""


def test_uppercase_r_extension():
    weights = sd.language_weights({"stats.R": "x\n"})
    assert list(weights) == ["R"]


def test_read_code_files_walks_and_skips(tmp_path):
    root = _write(tmp_path, {
        "app.py": "print('hi')\n",
        "node_modules/pkg/index.js": "x\n" * 10,
        "vendor/lib.rb": "puts 1\n",
        "notes.txt": "not code\n",
    })
    files = sd.read_code_files(root)
    assert set(files) == {"app.py"}
    assert sd.language_weights(files)["Python"].lines == 1


# ---------------------------------------------------------------------------
# Offline reference repositories: exact expected weights and primary
# ---------------------------------------------------------------------------
# {language: (files, lines)} — expected weights are literal, hand-computed.
REFERENCE = {
    "python-heavy": ({
        "main.py": "import sys\n" * 40,                       # 40 lines
        "lib/utils.py": "x = 1\n" * 10,                        # 10 lines
        "web/static/app.js": "console.log(1);\n",              # 1 line
        "web/static/util.js": "console.log(2);\n",             # 1 line
    }, {"Python": (2, 50), "JavaScript": (2, 2)}, "Python"),
    "polyglot-monorepo": ({
        "backend/api.py": "def handler():\n    pass\n",        # 2 lines
        "backend/worker.py": "import os\n",                    # 1 line
        "frontend/src/main.ts": "const x = 1;\n" * 30,         # 30 lines
        "frontend/src/app.tsx": "export default 1;\n",        # 1 line
        "cli/main.go": "package main\nfunc main() {}\n",       # 2 lines
        "cli/util.go": "package main\n",                       # 1 line
        "tools/setup.sh": "echo hi\n",                        # not a language
    }, {"TypeScript": (2, 31), "Go": (2, 3), "Python": (2, 3)}, "TypeScript"),
    "vendored-ignored": ({
        "app.py": "print(1)\n",
        "node_modules/pkg/index.js": "x\n" * 100,
        "vendor/lib.rb": "puts 1\n" * 100,
    }, {"Python": (1, 1)}, "Python"),
    "many-scripts-vs-one-module": ({
        **{f"s{i}.js": "console.log(1);\n" for i in range(20)},  # 20 files, 20 lines
        "core.py": "x = 1\n" * 200,                              # 1 file, 200 lines
    }, {"Python": (1, 200), "JavaScript": (20, 20)}, "Python"),
    "tie-by-files": ({
        "a.py": "x\nx\n",     # 2 lines
        "b.js": "x\nx\n",     # 2 lines, same files → name breaks the tie
    }, {"JavaScript": (1, 2), "Python": (1, 2)}, "JavaScript"),
}


@pytest.mark.parametrize("name", sorted(REFERENCE))
def test_offline_reference_repository(tmp_path, name):
    files, expected, primary = REFERENCE[name]
    weights = sd.language_weights(files)
    assert {lang: (stat.files, stat.lines) for lang, stat in weights.items()} == expected
    assert sd.primary_language(weights) == primary
    assert sd.language_breakdown(files) == {
        lang: {"files": f, "lines": l} for lang, (f, l) in expected.items()}


# ---------------------------------------------------------------------------
# End-to-end: every language-detecting path goes through the kernel unit
# ---------------------------------------------------------------------------
@needs_git
def test_kernel_capability_weights_languages(tmp_path):
    from agos.kernel.capabilities import RepositoryAnalysisCapability

    repo = _git_repo(tmp_path, REFERENCE["polyglot-monorepo"][0])
    dna = RepositoryAnalysisCapability().execute({"url": f"file://{repo}", "branch": "main", "cache": False})
    assert dna.primary_language == "TypeScript"
    assert dna.languages == ["TypeScript", "Go", "Python"]  # ordered by weight
    assert dna.language_stats == {"TypeScript": {"files": 2, "lines": 31},
                                  "Go": {"files": 2, "lines": 3},
                                  "Python": {"files": 2, "lines": 3}}
    d = dna.to_dict()
    assert d["primary_language"] == "TypeScript" and d["language_stats"] == dna.language_stats
    json.dumps(d)


@needs_git
def test_kernel_capability_empty_repo_has_no_invented_languages(tmp_path):
    from agos.kernel.capabilities import RepositoryAnalysisCapability

    repo = _git_repo(tmp_path, {"README.md": "python and go and rust\n"})
    dna = RepositoryAnalysisCapability().execute({"url": f"file://{repo}", "branch": "main", "cache": False})
    assert dna.languages == [] and dna.primary_language == "" and dna.language_stats == {}


@needs_git
def test_rie_pipeline_weights_languages(tmp_path):
    from agos.rie.application import create_rie_pipeline

    repo = _git_repo(tmp_path, REFERENCE["polyglot-monorepo"][0])
    dna = create_rie_pipeline().execute(f"file://{repo}")
    assert dna.primary_language == "TypeScript"
    assert dna.language_stats["TypeScript"] == {"files": 2, "lines": 31}
    assert dna.language_stats["Go"]["lines"] == 3
    assert "language_stats" in dna.to_dict()
    # Weight-ordered: TypeScript first — 31 of the 37 code lines are TypeScript.
    assert dna.languages == ["TypeScript", "Go", "Python"]


def test_civilization_repository_analyzer(tmp_path):
    from agos.kernel.civilization.capabilities.repository_analysis import RepositoryAnalyzer

    root = _write(tmp_path, REFERENCE["many-scripts-vs-one-module"][0])
    result = RepositoryAnalyzer().analyze(str(root))
    # 20 one-line JS scripts never outweigh the 200-line Python module.
    assert result["primary_language"] == "Python"
    assert result["languages"]["JavaScript"] == 20


def test_civilization_language_detection_stage(tmp_path):
    from agos.kernel.civilization.intelligence_pipeline.stages import LanguageDetectionStage

    root = _write(tmp_path, REFERENCE["polyglot-monorepo"][0])
    result = LanguageDetectionStage().process(str(root), {})
    assert result.success
    assert result.data["primary_language"] == "TypeScript"
    assert result.data["language_stats"]["TypeScript"] == {"files": 2, "lines": 31}
    assert result.data["languages"]["TypeScript"] == pytest.approx(31 / 37 * 100, abs=0.01)


def test_intelligence_analyzer_and_project_dna(tmp_path):
    from agos.kernel.intelligence.dna import ProjectDNAGenerator
    from agos.kernel.intelligence.repository.analyzer import RepositoryAnalyzer

    root = _write(tmp_path, REFERENCE["polyglot-monorepo"][0])
    genome = RepositoryAnalyzer(str(root)).analyze()
    # .sh is SHELL in this analyzer's map — the stage delegates to the kernel unit
    # for the weights, but this analyzer keeps its own lowercase Language enum names.
    assert genome.metrics.language_lines == {"typescript": 31, "go": 3, "python": 3, "shell": 1}
    dna = ProjectDNAGenerator(str(root)).generate(repo_genome=genome)
    # Weight-ordered, so the primary is typescript — not the alphabetically first entry.
    assert dna.languages[0] == "typescript"
    assert dna.to_signature()["primary_language"] == "typescript"


def test_repo_discovery_slice(tmp_path):
    from agos.kernel.vertical_slices.repo_discovery.slice import RepositoryDiscoveryMission

    root = _write(tmp_path, REFERENCE["polyglot-monorepo"][0])
    techs = asyncio.run(RepositoryDiscoveryMission(str(root))._detect_technologies(str(root)))
    assert techs["languages"] == ["TypeScript", "Go", "Python"]


# ---------------------------------------------------------------------------
# Online reference repositories, pinned to release tags
# ---------------------------------------------------------------------------
# The primary language of each project is a public, independently verifiable
# fact (the language the project is written in — not measured with this parser).
ONLINE = {
    "psf/requests@v2.32.3": ("Python", "main"),
    "gin-gonic/gin@v1.9.1": ("Go", "master"),
    "expressjs/express@4.19.2": ("JavaScript", "master"),
    "sinatra/sinatra@v4.0.0": ("Ruby", "main"),
    "BurntSushi/ripgrep@14.1.0": ("Rust", "master"),
}


@pytest.mark.parametrize("ref", sorted(ONLINE))
@pytest.mark.skipif(not _reachable("https://github.com/psf/requests"),
                    reason="network/GitHub unreachable")
def test_online_reference_repository(tmp_path, ref):
    expected_primary, branch = ONLINE[ref]
    name, tag = ref.split("@")
    repo = tmp_path / name.replace("/", "-")
    subprocess.run(["git", "clone", "--depth", "1", "--branch", tag,
                    f"https://github.com/{name}", str(repo)],
                   check=True, capture_output=True, timeout=300)
    files = sd.read_code_files(repo)
    weights = sd.language_weights(files)
    assert sd.primary_language(weights) == expected_primary
    assert weights  # the clone must have produced code files
