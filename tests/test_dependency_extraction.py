"""R-W2-002 — dependencies are extracted from manifests and match reference repositories.

Acceptance (ROADMAP): ``dependencies`` is not empty and matches reference repositories.

* Offline reference repositories (one per ecosystem + a polyglot monorepo) with exact
  expected ``dependencies`` (direct runtime/peer names), package managers and specifiers.
* Online reference repositories pinned to release tags (deterministic). Their expected
  lists were checked against the upstream files with independent tools (tomllib/json/grep/awk),
  not with this parser; see docs/worklog/0018-R-W2-002.md.
* End-to-end: every place that extracts dependencies now goes through
  ``agos.kernel.stack_detection`` — kernel capability (main path), RIE, the civilization
  DependencyAnalyzer and DependencyResolutionStage, the intelligence analyzer/ProjectDNA and
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

# ---------------------------------------------------------------------------
# Offline reference repositories: files → (dependencies, package managers)
# ---------------------------------------------------------------------------
REFERENCE = {
    "pip": ({
        "requirements.txt": "Django>=4.2,<5  # web\npsycopg[binary]==3.1.18\n-r requirements/base.txt\n"
                            "--index-url https://pypi.org/simple\ncelery @ https://x/celery.whl\n",
        "requirements/base.txt": "redis>=5\n",
        "requirements-dev.txt": "pytest\nblack\n",
        "requirements/build.txt": "build==1.2.1\npackaging==24.0\n",
    }, ["celery", "django", "psycopg", "redis"], ["pip"]),
    "pyproject-pep621": ({
        "pyproject.toml": '[build-system]\nrequires=["hatchling"]\n[project]\nname="x"\n'
                          'dependencies=["httpx>=0.27", "pydantic[email]>=2 ; python_version>=\'3.9\'"]\n'
                          '[project.optional-dependencies]\nfast=["orjson"]\n'
                          '[dependency-groups]\ndev=["ruff"]\n',
        "uv.lock": "version = 1\n",
    }, ["httpx", "pydantic"], ["pip", "uv"]),
    "poetry": ({
        "pyproject.toml": '[tool.poetry]\nname="x"\n[tool.poetry.dependencies]\npython="^3.11"\n'
                          'fastapi="^0.110"\nsqlalchemy={version="^2.0", extras=["asyncio"]}\n'
                          'mylib={path="libs/mylib", develop=true}\n'
                          '[tool.poetry.group.dev.dependencies]\npytest="^8"\n',
        "poetry.lock": "",
    }, ["fastapi", "sqlalchemy"], ["poetry"]),
    "setuptools": ({
        "setup.py": "from setuptools import setup\nREQS = ['numpy>=1.26', 'scipy']\n"
                    "setup(name='x', install_requires=REQS, extras_require={'plot': ['matplotlib']},"
                    " tests_require=['pytest'])\n",
        "setup.cfg": "[options]\ninstall_requires =\n    pandas>=2\n",
    }, ["numpy", "pandas", "scipy"], ["pip"]),
    "pipenv": ({
        "Pipfile": '[packages]\nrequests = "*"\nflask = {version = ">=3"}\n[dev-packages]\npytest = "*"\n',
        "Pipfile.lock": "{}",
    }, ["flask", "requests"], ["pipenv"]),
    "npm": ({
        "package.json": json.dumps({
            "name": "web", "dependencies": {"react": "^18.2.0", "axios": "1.6.0", "ui": "workspace:*"},
            "peerDependencies": {"react-dom": "^18"}, "devDependencies": {"vite": "^5"},
            "optionalDependencies": {"fsevents": "2"}}),
        "yarn.lock": "",
        "node_modules/axios/package.json": json.dumps({"dependencies": {"follow-redirects": "1"}}),
    }, ["axios", "react", "react-dom"], ["npm", "yarn"]),
    "go": ({
        "go.mod": "module example.com/x\n\ngo 1.22\n\nrequire (\n\tgithub.com/gin-gonic/gin v1.9.1\n"
                  "\tgolang.org/x/net v0.20.0 // indirect\n)\n\nrequire github.com/stretchr/testify v1.8.4\n\n"
                  "replace example.com/y => ../y\n",
        "go.sum": "",
    }, ["github.com/gin-gonic/gin", "github.com/stretchr/testify"], ["go"]),
    "cargo": ({
        "Cargo.toml": '[package]\nname="x"\n[dependencies]\ntokio = { version = "1", features = ["full"] }\n'
                      'serde = "1.0"\nlocal = { path = "crates/local" }\nfast = { version = "1", optional = true }\n'
                      '[dev-dependencies]\ncriterion = "0.5"\n[build-dependencies]\ncc = "1"\n'
                      "[target.'cfg(unix)'.dependencies]\nnix = \"0.27\"\n",
        "Cargo.lock": "",
    }, ["nix", "serde", "tokio"], ["cargo"]),
    "bundler-app": ({
        "Gemfile": "source 'https://rubygems.org'\ngem 'rails', '~> 7.1'\ngem 'pg'\n"
                   "group :development, :test do\n  gem 'rspec-rails'\nend\ngem 'engine', path: 'engines/engine'\n",
        "Gemfile.lock": "",
    }, ["pg", "rails"], ["bundler"]),
    "bundler-library": ({
        "Gemfile": "source 'https://rubygems.org'\ngemspec\ngem 'rake'\ngem 'minitest', '~> 5.0'\n",
        "mylib.gemspec": "Gem::Specification.new do |spec|\n  spec.name = 'mylib'\n"
                         "  spec.add_dependency 'rack', '>= 3.0', '< 4'\n"
                         "  spec.add_runtime_dependency(%q<tilt>, ['~> 2.0'])\n"
                         "  spec.add_development_dependency 'rspec'\nend\n",
    }, ["rack", "tilt"], ["bundler"]),
    "composer": ({
        "composer.json": json.dumps({"require": {"php": "^8.2", "ext-json": "*", "laravel/framework": "^11.0",
                                                 "guzzlehttp/guzzle": "^7.2"},
                                     "require-dev": {"phpunit/phpunit": "^10"}}),
        "composer.lock": "{}",
    }, ["guzzlehttp/guzzle", "laravel/framework"], ["composer"]),
    "maven": ({
        "pom.xml": '<project xmlns="http://maven.apache.org/POM/4.0.0"><parent><groupId>org.springframework.boot'
                   '</groupId><artifactId>spring-boot-starter-parent</artifactId><version>3.2.0</version></parent>'
                   '<dependencies><dependency><groupId>org.springframework.boot</groupId>'
                   '<artifactId>spring-boot-starter-web</artifactId></dependency><dependency>'
                   '<groupId>com.h2database</groupId><artifactId>h2</artifactId><version>2.2.224</version></dependency>'
                   '<dependency><groupId>org.junit.jupiter</groupId><artifactId>junit-jupiter</artifactId>'
                   '<scope>test</scope></dependency></dependencies>'
                   '<dependencyManagement><dependencies><dependency><groupId>x</groupId><artifactId>bom</artifactId>'
                   '</dependency></dependencies></dependencyManagement></project>',
    }, ["com.h2database:h2", "org.springframework.boot:spring-boot-starter-web"], ["maven"]),
    "gradle": ({
        "build.gradle.kts": 'plugins {\n  id("org.springframework.boot") version "3.2.0"\n}\n'
                            'dependencies {\n  implementation("org.springframework.boot:spring-boot-starter-web")\n'
                            '  runtimeOnly("org.postgresql:postgresql:42.7.1")\n'
                            '  implementation(project(":core"))\n'
                            '  testImplementation("org.junit.jupiter:junit-jupiter:5.10.0")\n}\n',
    }, ["org.postgresql:postgresql", "org.springframework.boot:spring-boot-starter-web"], ["gradle"]),
    "pub": ({
        "pubspec.yaml": "name: app\ndependencies:\n  flutter:\n    sdk: flutter\n  http: ^1.1.0\n"
                        "dev_dependencies:\n  flutter_test:\n    sdk: flutter\n",
        "pubspec.lock": "",
    }, ["flutter", "http"], ["pub"]),
    "polyglot-monorepo": ({
        "backend/pyproject.toml": '[project]\nname="api"\ndependencies=["fastapi", "uvicorn[standard]"]\n',
        "frontend/package.json": json.dumps({"dependencies": {"vue": "^3.4"}, "devDependencies": {"vite": "5"}}),
        "frontend/pnpm-lock.yaml": "",
        "services/worker/go.mod": "module w\nrequire github.com/redis/go-redis/v9 v9.4.0\n",
        "docs/package.json": json.dumps({"dependencies": {"docusaurus": "3"}}),
        "examples/demo/requirements.txt": "flask\n",
    }, ["fastapi", "github.com/redis/go-redis/v9", "uvicorn", "vue"], ["go", "npm", "pip", "pnpm"]),
}


@pytest.mark.parametrize("name", sorted(REFERENCE))
def test_offline_reference_repository(tmp_path, name):
    files, expected_deps, expected_pms = REFERENCE[name]
    root = _write(tmp_path / name, files)
    report = sd.detect_stack(sd.read_manifests(root))
    assert report.errors == {}
    assert sd.project_dependencies(report) == expected_deps
    assert sd.detect_package_managers_at(root) == expected_pms
    # every direct dependency also appears, with its manifest, in the full records
    records = sd.dependency_records(report)
    assert {r["name"] for r in records if r["scope"] in sd.COUNTED_SCOPES} == set(expected_deps)
    assert all(r["manifest"] in report.manifests for r in records)


def test_records_keep_non_runtime_scopes_and_specifiers(tmp_path):
    files, _, _ = REFERENCE["cargo"]
    report = sd.detect_stack(sd.read_manifests(_write(tmp_path, files)))
    by_name = {r["name"]: r for r in sd.dependency_records(report)}
    assert by_name["tokio"]["specifier"] == "1" and by_name["tokio"]["scope"] == "runtime"
    assert by_name["serde"]["specifier"] == "1.0"
    assert by_name["local"]["scope"] == "local"
    assert by_name["fast"]["scope"] == "optional"
    assert by_name["criterion"]["scope"] == "dev"
    assert by_name["cc"]["scope"] == "build"


@pytest.mark.parametrize("path,text,name,specifier", [
    ("requirements.txt", "Django>=4.2,<5  # c\n", "django", ">=4.2,<5"),
    ("requirements.txt", "psycopg[binary]==3.1.18 ; sys_platform=='linux'\n", "psycopg", "==3.1.18"),
    ("requirements.txt", "celery @ https://x/c.whl\n", "celery", "@ https://x/c.whl"),
    ("pyproject.toml", '[project]\nname="x"\ndependencies=["httpx (>=0.27)"]\n', "httpx", ">=0.27"),
    ("pyproject.toml", '[tool.poetry.dependencies]\nsqlalchemy={version="^2.0"}\n', "sqlalchemy", "^2.0"),
    ("package.json", '{"dependencies": {"react": "^18.2.0"}}', "react", "^18.2.0"),
    ("Gemfile", "gem 'rails', '~> 7.1', '>= 7.1.2', require: false\n", "rails", "~> 7.1, >= 7.1.2"),
    ("x.gemspec", "s.add_dependency 'rack', '>= 3.0', '< 4'\n", "rack", ">= 3.0, < 4"),
    ("composer.json", '{"require": {"guzzlehttp/guzzle": "^7.2"}}', "guzzlehttp/guzzle", "^7.2"),
    ("pom.xml", "<project><dependencies><dependency><groupId>g</groupId><artifactId>a</artifactId>"
                "<version>${a.version}</version></dependency></dependencies></project>", "g:a", "${a.version}"),
    ("build.gradle", "implementation 'org.postgresql:postgresql:42.7.1'\n", "org.postgresql:postgresql", "42.7.1"),
    ("go.mod", "module x\nrequire github.com/gin-gonic/gin v1.9.1\n", "github.com/gin-gonic/gin", "v1.9.1"),
    ("Cargo.toml", '[dependencies]\ntokio = { version = "1.35" }\n', "tokio", "1.35"),
    ("pubspec.yaml", "name: a\ndependencies:\n  http: ^1.1.0\n", "http", "^1.1.0"),
])
def test_specifier_is_kept_as_written(path, text, name, specifier):
    report = sd.detect_stack({path: text})
    recs = [r for r in sd.dependency_records(report) if r["name"] == name]
    assert recs and recs[0]["specifier"] == specifier


@pytest.mark.parametrize("path,text,scope", [
    ("requirements/build.txt", "build==1.2\n", "build"),
    ("requirements-build.txt", "build==1.2\n", "build"),
    ("Gemfile", "gemspec\ngem 'rake'\n", "dev"),
    ("Gemfile", "gem 'engine', path: 'engines/engine'\n", "local"),
    ("Gemfile", "gem 'engine', :path => 'engines/engine'\n", "local"),
    ("package.json", '{"dependencies": {"ui": "workspace:*"}}', "local"),
    ("package.json", '{"dependencies": {"ui": "file:../ui"}}', "local"),
    ("pyproject.toml", '[tool.poetry.dependencies]\nlib={path="../lib"}\n', "local"),
    ("Cargo.toml", '[dependencies]\ncore = { version = "0.1", path = "crates/core" }\n', "local"),
    ("pom.xml", "<project><parent><groupId>org.springframework.boot</groupId>"
                "<artifactId>spring-boot-starter-parent</artifactId></parent></project>", "parent"),
    ("build.gradle", "plugins { id 'org.springframework.boot' version '3' }\n", "plugin"),
])
def test_scopes_that_are_not_direct_dependencies(path, text, scope):
    report = sd.detect_stack({path: text})
    assert [d.scope for d in report.dependencies] == [scope]
    assert sd.project_dependencies(report) == []


def test_parent_and_plugin_are_framework_evidence_but_not_dependencies():
    pom = ("<project><parent><groupId>org.springframework.boot</groupId>"
           "<artifactId>spring-boot-starter-parent</artifactId></parent></project>")
    for files in ({"pom.xml": pom}, {"build.gradle": "plugins { id 'org.springframework.boot' }\n"}):
        report = sd.detect_stack(files)
        assert report.frameworks == ["Spring"]
        assert sd.project_dependencies(report) == []


def test_custom_scope_selection():
    files, _, _ = REFERENCE["npm"]
    report = sd.detect_stack(files)
    assert sd.project_dependencies(report, scopes=("dev",)) == ["vite"]
    assert sd.project_dependencies(report, scopes=("optional",)) == ["fsevents"]


def test_package_managers_ignore_vendored_and_example_dirs():
    paths = ["node_modules/x/package.json", "vendor/y/composer.json", "examples/a/Gemfile",
             "docs/package.json", ".venv/lib/pyproject.toml"]
    assert sd.detect_package_managers(paths) == []


def test_pyproject_package_manager_flavours():
    assert sd.detect_package_managers(["pyproject.toml"], {"pyproject.toml": "[project]\n"}) == ["pip"]
    assert sd.detect_package_managers(["pyproject.toml"], {"pyproject.toml": "[tool.poetry]\n"}) == ["poetry"]
    assert sd.detect_package_managers(["pyproject.toml"], {"pyproject.toml": "[tool.pdm]\n"}) == ["pdm"]


# ---------------------------------------------------------------------------
# End-to-end through every dependency extractor
# ---------------------------------------------------------------------------
POLY_FILES, POLY_DEPS, POLY_PMS = REFERENCE["polyglot-monorepo"]


@needs_git
def test_kernel_capability_fills_dependencies(tmp_path):
    from agos.kernel.capabilities import RepositoryAnalysisCapability

    repo = _git_repo(tmp_path, POLY_FILES)
    dna = RepositoryAnalysisCapability().execute({"url": f"file://{repo}", "branch": "main", "cache": False})
    assert dna.dependencies == POLY_DEPS
    assert dna.package_managers == POLY_PMS
    assert {r["name"] for r in dna.dependency_details} >= set(POLY_DEPS) | {"vite", "docusaurus", "flask"}
    d = dna.to_dict()
    assert d["dependencies"] == POLY_DEPS and d["dependency_details"] == dna.dependency_details
    json.dumps(d)


@needs_git
def test_kernel_capability_empty_repo_has_no_invented_dependencies(tmp_path):
    from agos.kernel.capabilities import RepositoryAnalysisCapability

    repo = _git_repo(tmp_path, {"README.md": "uses flask and react\n", "app.py": "import flask\n"})
    dna = RepositoryAnalysisCapability().execute({"url": f"file://{repo}", "branch": "main", "cache": False})
    assert dna.dependencies == [] and dna.dependency_details == [] and dna.package_managers == []


@needs_git
def test_rie_pipeline_fills_dependencies(tmp_path):
    from agos.rie.application import create_rie_pipeline

    repo = _git_repo(tmp_path, POLY_FILES)
    dna = create_rie_pipeline().execute(f"file://{repo}")
    assert sorted(dna.dependencies) == POLY_DEPS
    assert sorted(dna.package_managers) == POLY_PMS
    assert {r["name"] for r in dna.dependency_details} >= set(POLY_DEPS)
    assert "dependency_details" in dna.to_dict()


def test_civilization_dependency_analyzer(tmp_path):
    from agos.kernel.civilization.capabilities.dependency_analysis import DependencyAnalyzer

    result = DependencyAnalyzer().analyze(str(_write(tmp_path, POLY_FILES)))
    assert result["direct_dependencies"] == POLY_DEPS
    assert result["metrics"]["direct_deps"] == len(POLY_DEPS)
    names = {d["name"] for d in result["dependencies"]}
    assert "vite" in names and "follow-redirects" not in names
    assert {s["file"] for s in result["dependency_sources"]} == set(POLY_FILES) - {"frontend/pnpm-lock.yaml"}
    assert result["manifest_errors"] == {}


def test_civilization_dependency_resolution_stage(tmp_path):
    from agos.kernel.civilization.intelligence_pipeline.stages import DependencyResolutionStage

    result = DependencyResolutionStage().process(str(_write(tmp_path, POLY_FILES)), {})
    assert result.success
    assert result.data["direct"] == POLY_DEPS
    assert result.data["dev"] == ["vite"]
    assert result.data["total"] == len(POLY_DEPS) + 1


def test_intelligence_analyzer_and_project_dna(tmp_path):
    from agos.kernel.intelligence.dna import ProjectDNAGenerator
    from agos.kernel.intelligence.repository.analyzer import RepositoryAnalyzer

    root = _write(tmp_path, POLY_FILES)
    genome = RepositoryAnalyzer(str(root)).analyze()
    assert genome.dependencies == POLY_DEPS
    assert genome.package_managers == set(POLY_PMS)
    assert genome.to_dict()["dependencies"] == POLY_DEPS
    dna = ProjectDNAGenerator(str(root)).generate(repo_genome=genome)
    assert dna.external_dependencies == POLY_DEPS


def test_repo_discovery_slice(tmp_path):
    from agos.kernel.vertical_slices.repo_discovery.slice import RepositoryDiscoveryMission

    root = _write(tmp_path, POLY_FILES)
    graph = asyncio.run(RepositoryDiscoveryMission(str(root))._analyze_dependencies(str(root)))
    assert sorted(d["name"] for d in graph.dependencies) == POLY_DEPS
    assert [d["name"] for d in graph.dev_dependencies] == ["vite"]
    assert {d["scope"] for d in graph.other_dependencies} == {"example"}


# ---------------------------------------------------------------------------
# Online reference repositories, pinned to release tags
# ---------------------------------------------------------------------------
ONLINE = {
    "psf/requests@v2.32.3": ["certifi", "charset-normalizer", "idna", "urllib3"],
    "pallets/flask@3.0.3": ["blinker", "click", "importlib-metadata", "itsdangerous", "jinja2", "werkzeug"],
    "gin-gonic/gin@v1.9.1": [
        "github.com/bytedance/sonic", "github.com/gin-contrib/sse", "github.com/go-playground/validator/v10",
        "github.com/goccy/go-json", "github.com/json-iterator/go", "github.com/mattn/go-isatty",
        "github.com/pelletier/go-toml/v2", "github.com/stretchr/testify", "github.com/ugorji/go/codec",
        "golang.org/x/net", "google.golang.org/protobuf", "gopkg.in/yaml.v3"],
    "sinatra/sinatra@v4.0.0": ["base64", "multi_json", "mustermann", "rack", "rack-protection", "rack-session",
                               "sinatra", "tilt"],
    "laravel/laravel@v11.0.0": ["laravel/framework", "laravel/tinker"],
    "BurntSushi/ripgrep@14.1.0": [
        "aho-corasick", "anyhow", "bstr", "crossbeam-deque", "encoding_rs", "encoding_rs_io", "jemallocator",
        "lexopt", "libc", "log", "memchr", "memmap2", "pcre2", "regex-automata", "regex-syntax", "same-file",
        "serde_json", "termcolor", "textwrap", "walkdir", "winapi-util"],
    "expressjs/express@4.19.2": None,  # oracle: the keys of package.json "dependencies" (31)
}


def _reachable():
    if shutil.which("git") is None:
        return False
    try:
        return subprocess.run(["git", "ls-remote", "https://github.com/psf/requests", "HEAD"],
                              capture_output=True, timeout=30).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


@pytest.mark.skipif(not _reachable(), reason="network/GitHub unreachable")
@pytest.mark.parametrize("ref", sorted(ONLINE))
def test_online_reference_repository(tmp_path, ref):
    slug, tag = ref.split("@")
    dest = tmp_path / "repo"
    subprocess.run(["git", "clone", "-q", "--depth", "1", "--branch", tag, f"https://github.com/{slug}", str(dest)],
                   check=True, capture_output=True, timeout=300)
    report = sd.detect_stack(sd.read_manifests(dest))
    deps = sd.project_dependencies(report)
    expected = ONLINE[ref]
    if expected is None:
        expected = sorted(json.loads((dest / "package.json").read_text())["dependencies"])
        assert len(expected) == 31
    assert deps == expected
    assert report.errors == {}
