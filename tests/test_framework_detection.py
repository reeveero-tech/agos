"""R-W2-001 — frameworks are detected from dependency manifests, never from file text.

Golden tests (ROADMAP acceptance):
  A. A repository that only *mentions* express/flask/vue/react (README, docs, code strings,
     file names such as app.py / manage.py) and has no manifest declaring them  ⇒  no frameworks.
  B. The same text plus a real ``requirements.txt`` declaring flask  ⇒  exactly ``["Flask"]``.

They run against the canonical detector (``agos.kernel.stack_detection``) and end-to-end
through every detector that used to match text or file names: the kernel capability
(main path), RIE, the civilization pipeline stage, the intelligence analyzer, the
technology capability and the repo-discovery slice.

Canaries pin each manifest format and each scope rule so the detector cannot silently
regress to "anything that looks like a name".
"""
import asyncio
import os
import shutil
import subprocess

import pytest

from agos.kernel import stack_detection as sd

# ---------------------------------------------------------------------------
# Fixtures: the "noise" every golden repo contains
# ---------------------------------------------------------------------------
NOISE = {
    "README.md": "# Demo\nWorks great with Express, Flask, Vue, React, Next.js, Django, Spring, "
                 "Rails, Laravel, FastAPI, PyTorch, TensorFlow, LangChain and llama_index.\n",
    "docs/guide.md": "Install express and vue; `from flask import Flask`; import torch\n",
    "app.py": "# not flask\nNAME = 'express vue react angular next spring rails laravel'\n",
    "manage.py": "print('this is not django')\n",
    "settings.py": "FRAMEWORK = 'django'\n",
    "config.ru": "# rails\n",
    "src/index.js": "// const express = require('express'); import React from 'react'\n",
    "examples/demo/requirements.txt": "fastapi\ndjango\n",
    "examples/demo/package.json": '{"dependencies": {"express": "4", "vue": "3"}}',
    "node_modules/react/package.json": '{"name": "react", "dependencies": {"loose-envify": "1"}}',
}


def _git_repo(tmp_path, files):
    repo = tmp_path / "golden"
    for rel, text in files.items():
        p = repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@t", "PATH": os.environ["PATH"]}
    for cmd in (["git", "init", "-q", "-b", "main"], ["git", "add", "-A", "-f"],
                ["git", "commit", "-qm", "init"]):
        subprocess.run(cmd, cwd=repo, check=True, env=env, capture_output=True)
    return repo


GOLDEN_A = dict(NOISE)
GOLDEN_B = dict(NOISE, **{"requirements.txt": "flask>=2.0  # the only real framework\nrequests\n"})

needs_git = pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")


# ---------------------------------------------------------------------------
# Golden tests — canonical detector
# ---------------------------------------------------------------------------
def test_golden_a_text_mentions_only_yield_no_frameworks():
    report = sd.detect_stack(GOLDEN_A)
    assert report.frameworks == []
    # example manifests are read and recorded as evidence, but never counted
    assert report.evidence and not any(e.counted for e in report.evidence)
    assert {e.scope for e in report.evidence} == {"example"}
    # vendored manifests are not even read
    assert not any(m.startswith("node_modules/") for m in report.manifests)


def test_golden_b_real_flask_dependency_yields_exactly_flask():
    report = sd.detect_stack(GOLDEN_B)
    assert report.frameworks == ["Flask"]
    counted = [e for e in report.evidence if e.counted]
    assert [(e.framework, e.dependency, e.manifest, e.scope) for e in counted] == [
        ("Flask", "flask", "requirements.txt", "runtime")]
    assert report.runtimes == ["Python"]


def test_non_manifest_files_are_never_parsed():
    files = {"notes.txt": "flask\ndjango\n", "requirements.md": "flask\n", "package.json.bak": "{}"}
    assert sd.detect_stack(files).manifests == []


# ---------------------------------------------------------------------------
# Canaries — every manifest format
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("path,text,expected", [
    ("requirements.txt", "Django==4.2\n", ["Django"]),
    ("requirements/base.txt", "fastapi[all]>=0.100 ; python_version>'3.8'\n", ["FastAPI"]),
    ("requirements.txt", "-e git+https://x/y.git#egg=Flask\n", ["Flask"]),
    ("requirements.txt", "torch @ https://download.pytorch.org/x.whl\n", ["PyTorch"]),
    ("pyproject.toml", '[project]\nname="x"\ndependencies=["langchain-core>=0.1", "requests"]\n',
     ["LangChain"]),
    ("pyproject.toml", '[tool.poetry.dependencies]\npython="^3.11"\nllama-index="*"\n', ["LlamaIndex"]),
    ("setup.cfg", "[options]\ninstall_requires =\n    tensorflow>=2\n    numpy\n", ["TensorFlow"]),
    ("setup.py", "from setuptools import setup\nREQ = ['django>=4']\nsetup(name='x', install_requires=REQ)\n",
     ["Django"]),
    ("Pipfile", '[packages]\nflask = "*"\n[dev-packages]\npytest = "*"\n', ["Flask"]),
    ("package.json", '{"dependencies": {"next": "14", "react": "18", "react-dom": "18"}}',
     ["Next.js", "React"]),
    ("package.json", '{"dependencies": {"@angular/core": "17", "express": "4"}}', ["Angular", "Express"]),
    ("package.json", '{"dependencies": {"@nestjs/core": "10", "fastify": "4"}}', ["Fastify", "NestJS"]),
    ("Gemfile", "source 'https://rubygems.org'\ngem 'rails', '~> 7.0'\n", ["Rails"]),
    ("composer.json", '{"require": {"php": "^8.1", "laravel/framework": "^10"}}', ["Laravel"]),
    ("pom.xml", '<project xmlns="http://maven.apache.org/POM/4.0.0"><dependencies><dependency>'
                '<groupId>org.springframework</groupId><artifactId>spring-web</artifactId>'
                '</dependency></dependencies></project>', ["Spring"]),
    ("build.gradle", "plugins { id 'org.springframework.boot' version '3.2.0' }\n", ["Spring"]),
    ("build.gradle.kts", 'dependencies {\n  implementation("org.springframework.boot:spring-boot-starter-web")\n}\n',
     ["Spring"]),
    ("go.mod", "module x\n\ngo 1.22\n\nrequire github.com/gin-gonic/gin v1.9.1\n", ["Gin"]),
    ("go.mod", "module x\nrequire (\n\tgithub.com/gofiber/fiber/v2 v2.52.0\n)\n", ["Fiber"]),
    ("Cargo.toml", '[dependencies]\naxum = "0.7"\nweb = { package = "actix-web", version = "4" }\n',
     ["Actix Web", "Axum"]),
    ("pubspec.yaml", "name: app\ndependencies:\n  flutter:\n    sdk: flutter\n", ["Flutter"]),
])
def test_each_manifest_format_is_parsed(path, text, expected):
    report = sd.detect_stack({path: text})
    assert report.frameworks == expected, report.to_dict()
    assert report.errors == {}


# ---------------------------------------------------------------------------
# Canaries — scope rules (recorded as evidence, not counted)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("path,text,scope", [
    ("requirements-dev.txt", "django\n", "dev"),
    ("requirements/test.txt", "flask\n", "dev"),
    ("requirements_docs.txt", "flask\n", "dev"),
    ("package.json", '{"devDependencies": {"react": "18"}}', "dev"),
    ("package.json", '{"optionalDependencies": {"vue": "3"}}', "optional"),
    ("pyproject.toml", '[project]\nname="x"\n[project.optional-dependencies]\nweb=["flask"]\n', "optional"),
    ("pyproject.toml", '[dependency-groups]\ndev=["django"]\n', "dev"),
    ("pyproject.toml", '[tool.poetry.group.dev.dependencies]\nflask="*"\n', "dev"),
    ("Gemfile", "group :development, :test do\n  gem 'rails'\nend\n", "dev"),
    ("composer.json", '{"require-dev": {"laravel/framework": "10"}}', "dev"),
    ("pom.xml", "<project><dependencies><dependency><groupId>org.springframework</groupId>"
                "<artifactId>spring-test</artifactId><scope>test</scope></dependency></dependencies></project>",
     "dev"),
    ("build.gradle", "dependencies {\n  testImplementation 'org.springframework:spring-test:6'\n}\n", "dev"),
    ("go.mod", "module x\nrequire github.com/gin-gonic/gin v1.9.1 // indirect\n", "indirect"),
    ("Cargo.toml", '[dev-dependencies]\naxum = "0.7"\n', "dev"),
    ("tests/fixtures/requirements.txt", "flask\n", "example"),
    ("docs/package.json", '{"dependencies": {"react": "18"}}', "example"),
])
def test_non_runtime_scopes_are_evidence_only(path, text, scope):
    report = sd.detect_stack({path: text})
    assert report.frameworks == []
    assert [e.scope for e in report.evidence] == [scope]
    assert report.evidence[0].counted is False


def test_peer_dependency_counts():
    report = sd.detect_stack({"package.json": '{"peerDependencies": {"vue": "^3"}}'})
    assert report.frameworks == ["Vue"]


def test_exact_name_match_extensions_and_lookalikes_do_not_count():
    text = "Flask-Login\nflask_sqlalchemy\ndjango-environ\nfastapi-users\ntorchvision\nexpressive\n"
    report = sd.detect_stack({"requirements.txt": text,
                              "package.json": '{"dependencies": {"express-session": "1", "nextjs-x": "1"}}'})
    assert report.frameworks == []
    assert report.evidence == []


def test_comments_and_options_in_requirements_are_ignored():
    text = "# flask\n--index-url https://x/simple\n-r base.txt\n-c constraints.txt\n  # django\nrequests\n"
    report = sd.detect_stack({"requirements.txt": text})
    assert report.frameworks == []
    assert [d.name for d in report.dependencies] == ["requests"]


def test_vendored_directories_are_skipped():
    files = {f"{d}/x/requirements.txt": "flask\n" for d in ("node_modules", "vendor", ".venv", "venv",
                                                              "site-packages", "dist", "build")}
    report = sd.detect_stack(files)
    assert report.manifests == [] and report.frameworks == []


def test_malformed_manifest_is_reported_not_guessed():
    report = sd.detect_stack({"package.json": "{ not json: flask, express }",
                              "pyproject.toml": "[project\ndependencies = ['django']"})
    assert report.frameworks == []
    assert set(report.errors) == {"package.json", "pyproject.toml"}


def test_setup_py_is_analysed_without_being_executed(tmp_path):
    marker = tmp_path / "executed"
    text = f"open({str(marker)!r}, 'w').write('x')\nfrom setuptools import setup\nsetup(install_requires=['flask'])\n"
    assert sd.detect_stack({"setup.py": text}).frameworks == ["Flask"]
    assert not marker.exists()


def test_report_is_serialisable_and_deterministic():
    import json
    a = sd.detect_stack(GOLDEN_B).to_dict()
    b = sd.detect_stack(dict(reversed(list(GOLDEN_B.items())))).to_dict()
    assert a == b
    json.dumps(a)


def test_read_manifests_reads_only_manifests_and_skips_vendored(tmp_path):
    for rel, text in GOLDEN_B.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    got = sd.read_manifests(tmp_path)
    assert set(got) == {"requirements.txt", "examples/demo/requirements.txt", "examples/demo/package.json"}
    assert sd.detect_stack(got).frameworks == ["Flask"]


# ---------------------------------------------------------------------------
# End-to-end: every detector that used to match text/file names
# ---------------------------------------------------------------------------
@needs_git
@pytest.mark.parametrize("files,expected", [(GOLDEN_A, []), (GOLDEN_B, ["Flask"])], ids=["A", "B"])
def test_kernel_capability_main_path(tmp_path, files, expected):
    from agos.kernel.capabilities import RepositoryAnalysisCapability

    repo = _git_repo(tmp_path, files)
    dna = RepositoryAnalysisCapability().execute({"url": f"file://{repo}", "branch": "main", "cache": False})
    assert dna.frameworks == expected
    assert "Python" not in dna.frameworks and "Node.js" not in dna.frameworks
    assert "Python" in dna.runtimes or not expected
    assert [e["framework"] for e in dna.framework_evidence if e["counted"]] == expected
    d = dna.to_dict()
    assert d["frameworks"] == expected and "framework_evidence" in d and "runtimes" in d


@needs_git
@pytest.mark.parametrize("files,expected", [(GOLDEN_A, []), (GOLDEN_B, ["Flask"])], ids=["A", "B"])
def test_rie_pipeline(tmp_path, files, expected):
    from agos.rie.application import create_rie_pipeline

    repo = _git_repo(tmp_path, files)
    dna = create_rie_pipeline().execute(f"file://{repo}")
    assert sorted(dna.frameworks) == expected


@needs_git
def test_rie_context_exposes_manifest_contents_only(tmp_path):
    from agos.rie.infrastructure import FileSystemReader, GitFetcher, RepositoryNormalizer

    repo = _git_repo(tmp_path, GOLDEN_B)
    normalized = RepositoryNormalizer(GitFetcher(), FileSystemReader()).normalize(f"file://{repo}")
    assert "requirements.txt" in normalized["_content"]
    assert "README.md" not in normalized["_content"]


@pytest.mark.parametrize("files,expected", [(GOLDEN_A, []), (GOLDEN_B, ["Flask"])], ids=["A", "B"])
def test_civilization_technology_stage(tmp_path, files, expected):
    from agos.kernel.civilization.intelligence_pipeline.stages import TechnologyDetectionStage

    for rel, text in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    result = TechnologyDetectionStage().process(str(tmp_path), {})
    assert result.data["frameworks"] == expected


@pytest.mark.parametrize("files,expected", [(GOLDEN_A, set()), (GOLDEN_B, {"flask"})], ids=["A", "B"])
def test_intelligence_repository_analyzer(tmp_path, files, expected):
    from agos.kernel.intelligence.repository.analyzer import RepositoryAnalyzer

    for rel, text in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    analyzer = RepositoryAnalyzer(str(tmp_path))
    analyzer._detect_frameworks()
    assert {f.value for f in analyzer.genome.frameworks} == expected


def test_technology_capability_needs_manifest_contents():
    from agos.kernel.capabilities.technology.detection import TechnologyDetectionCapability

    paths = list(GOLDEN_B)
    cap = TechnologyDetectionCapability()
    assert cap.execute(paths).frameworks == []                     # paths alone are not evidence
    assert cap.execute(paths, contents=GOLDEN_A).frameworks == []  # golden A
    assert cap.execute(paths, contents=GOLDEN_B).frameworks == ["Flask"]  # golden B


@pytest.mark.parametrize("files,expected", [(GOLDEN_A, []), (GOLDEN_B, ["Flask"])], ids=["A", "B"])
def test_repo_discovery_slice(tmp_path, files, expected):
    from agos.kernel.vertical_slices.repo_discovery.slice import RepositoryDiscoveryMission

    for rel, text in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    techs = asyncio.run(RepositoryDiscoveryMission(str(tmp_path))._detect_technologies(str(tmp_path)))
    assert techs["frameworks"] == expected
    assert "Node.js" in techs["runtimes"]  # golden repos contain package.json files


# ---------------------------------------------------------------------------
# Real repository: the false positive recorded by the audit (AUDIT-2026-10-21 §3.6)
# ---------------------------------------------------------------------------
REQUESTS_URL = "https://github.com/psf/requests"


def _reachable(url):
    if shutil.which("git") is None:
        return False
    try:
        return subprocess.run(["git", "ls-remote", url, "HEAD"], capture_output=True,
                              timeout=30).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


@pytest.mark.skipif(not _reachable(REQUESTS_URL), reason="network/GitHub unreachable")
def test_psf_requests_has_no_frameworks():
    """The audit measured ``Express, Flask, Next.js, Vue`` for psf/requests (text matches)."""
    from agos.kernel.capabilities import RepositoryAnalysisCapability

    dna = RepositoryAnalysisCapability().execute({"url": REQUESTS_URL, "branch": "main", "cache": False})
    assert dna.frameworks == []
    assert dna.runtimes == ["Python"]
