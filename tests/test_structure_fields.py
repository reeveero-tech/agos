"""R-W2-004 — entry points, adjustable-depth directory tree, relevant hidden files.

Acceptance (ROADMAP): «نقاط الدخول، شجرة مجلدات بعمق قابل للضبط، ضم الملفات المخفية
ذات الصلة (.github, .env.example)» — «حقول DNA مملوءة ومختبرة».

* Unit: ``detect_entry_points`` (conventional + manifest-declared), ``directory_tree``
  (adjustable depth, vendored excluded, dotfile dirs kept when declared), ``is_relevant_hidden``
  and ``detect_config_files`` (suffix/exact-name, never substring).
* End-to-end: the kernel capability and the RIE pipeline fill ``entry_points``,
  ``directory_tree`` and ``config_files`` from the same source, and hidden files
  (``.github/workflows/ci.yml``, ``.env.example``, ``.gitignore``) reach the DNA.
"""
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
    for cmd in (["git", "init", "-q", "-b", "main"], ["git", "remote", "add", "origin",
                 "https://github.com/t/ref.git"], ["git", "add", "-A", "-f"],
                ["git", "commit", "-qm", "init"]):
        subprocess.run(cmd, cwd=repo, check=True, env=env, capture_output=True)
    return repo


needs_git = pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------
def test_conventional_entry_points():
    paths = ["main.py", "src/index.ts", "cmd/server/main.go", "src/main.rs",
             "src/bin/tool.rs", "scripts/run.py", "bin/index.js",
             "docs/main.py",           # parent "docs" — not an entry dir
             "deep/nested/main.py"]     # parent "nested" — not an entry dir
    assert sd.detect_entry_points(paths) == [
        "bin/index.js", "cmd/server/main.go", "main.py", "scripts/run.py",
        "src/bin/tool.rs", "src/index.ts", "src/main.rs"]


def test_manifest_declared_entry_points():
    pyproject = '[project]\nname = "x"\n[project.scripts]\ncli = "x.cli:main"\nweb = "x.web:app"\n'
    package_json = json.dumps({"main": "dist/index.js", "bin": {"tool": "bin/tool.js"}})
    out = sd.detect_entry_points(["app.py"], {"pyproject.toml": pyproject,
                                             "package.json": package_json})
    assert out == ["app.py", "package.json:bin:tool", "package.json:main:dist/index.js",
                   "pyproject.toml:scripts:cli", "pyproject.toml:scripts:web"]


def test_manifest_entry_points_keep_their_manifest_path():
    # Two manifests with the same script name must not merge — the declaration
    # carries the path of the file that declares it.
    pyproject = '[project.scripts]\ncli = "x.cli:main"\n'
    out = sd.detect_entry_points([], {"pyproject.toml": pyproject,
                                      "backend/pyproject.toml": pyproject})
    assert out == ["backend/pyproject.toml:scripts:cli", "pyproject.toml:scripts:cli"]


def test_malformed_manifests_never_break_the_analysis():
    # A broken JSON/TOML or an unexpected shape is skipped, not fatal.
    out = sd.detect_entry_points([], {
        "package.json": "[1, 2, 3]",             # valid JSON, not an object
        "broken.json": "{not json at all",          # not even valid JSON — not a manifest name anyway
        "package.json": None,                     # replaced below by the dict variant
    } | {"package.json": json.dumps({"main": 42, "bin": [1, 2]})})  # wrong types
    assert out == []


def test_vendored_code_is_not_an_entry_point():
    paths = ["main.py", "node_modules/pkg/main.py", "node_modules/pkg/index.js"]
    assert sd.detect_entry_points(paths) == ["main.py"]


def test_no_entry_points_in_empty_repo():
    assert sd.detect_entry_points(["README.md", "docs/guide.rst"]) == []


# ---------------------------------------------------------------------------
# Directory tree — adjustable depth
# ---------------------------------------------------------------------------
def test_directory_tree_depth_is_adjustable():
    paths = ["a/b/c/d.py", "a/b/e.py", "top.py"]
    dirs = ["a", "a/b", "a/b/c"]
    assert sd.directory_tree(paths, max_depth=1, dir_paths=dirs) == ["a"]
    assert sd.directory_tree(paths, max_depth=2, dir_paths=dirs) == ["a", "a/b"]
    assert sd.directory_tree(paths, max_depth=3, dir_paths=dirs) == ["a", "a/b", "a/b/c"]
    assert sd.directory_tree(paths, max_depth=0) == []
    # depth 4 adds nothing new — the tree only has three levels.
    assert sd.directory_tree(paths, max_depth=4, dir_paths=dirs) == ["a", "a/b", "a/b/c"]


def test_directory_tree_excludes_vendored_and_keeps_dotfile_dirs():
    paths = ["app.py", ".github/workflows/ci.yml", "node_modules/pkg/index.js"]
    dirs = [".github", ".github/workflows", "node_modules", "node_modules/pkg"]
    assert sd.directory_tree(paths, max_depth=3, dir_paths=dirs) == [".github", ".github/workflows"]


def test_directory_tree_infers_dirs_without_explicit_list():
    # No guessing from the name: "Makefile" has no suffix and no dot, but it is a
    # file — without ``dir_paths`` it is treated as one, so only its parent dirs
    # enter the tree. The live paths always pass ``dir_paths`` explicitly.
    assert sd.directory_tree(["src/app.py", "Makefile"], max_depth=3) == ["src"]


# ---------------------------------------------------------------------------
# Relevant hidden files
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("path,expected", [
    (".github/workflows/ci.yml", True), (".github", True), (".gitlab-ci.yml", False),
    (".gitignore", True), (".env.example", True), (".env", False), (".git", False),
    (".github/.env", False), (".idea/config.xml", False), ("src/.gitignore", True),
    (".DS_Store", False),
])
def test_is_relevant_hidden(path, expected):
    assert sd.is_relevant_hidden(path) is expected


def test_detect_config_files_no_substring_matching():
    paths = ["docs/package.json.md",        # substring ≠ name — not a config file
            "package.json", "app.yaml", ".env.example", ".gitignore",
            "node_modules/pkg/package.json", "Makefile", "Procfile".lower()]
    assert sd.detect_config_files(paths) == [".env.example", ".gitignore", "Makefile",
                                             "app.yaml", "package.json", "procfile"]


# ---------------------------------------------------------------------------
# End-to-end: the DNA fields are filled, hidden files included
# ---------------------------------------------------------------------------
REPO = {
    "main.py": "print('hi')\n",
    "app/settings.yaml": "debug: true\n",
    ".github/workflows/ci.yml": "on: push\n",
    ".env.example": "API_KEY=\n",
    ".gitignore": "__pycache__/\n",
    ".idea/workspace.xml": "<x/>\n",        # irrelevant hidden — must stay out
}


@needs_git
def test_kernel_capability_fills_structure_fields(tmp_path):
    from agos.kernel.capabilities import RepositoryAnalysisCapability

    repo = _git_repo(tmp_path, REPO)
    dna = RepositoryAnalysisCapability().execute({"url": f"file://{repo}", "branch": "main", "cache": False})
    # Entry points: conventional + manifest-declared; hidden files reach the DNA.
    assert "main.py" in dna.entry_points
    assert ".env.example" in dna.config_files
    assert ".gitignore" in dna.config_files
    assert ".github/workflows/ci.yml" in dna.config_files
    assert "app/settings.yaml" in dna.config_files
    # Tree at the default depth 3: .github and its workflows, plus app/.
    assert dna.directory_tree == [".github", ".github/workflows", "app"]
    # The irrelevant hidden file never reaches the snapshot.
    assert all(".idea" not in f for f in dna.config_files + dna.directory_tree)
    d = dna.to_dict()
    assert d["entry_points"] == dna.entry_points and d["directory_tree"] == dna.directory_tree


@needs_git
def test_kernel_capability_tree_depth_is_adjustable(tmp_path):
    from agos.kernel.capabilities import RepositoryAnalysisCapability

    repo = _git_repo(tmp_path, {"deep/er/still/file.py": "x\n", "main.py": "y\n"})
    cap = RepositoryAnalysisCapability()
    from providers import ReadRepositoryInput
    provider = cap._provider() if hasattr(cap, "_provider") else None
    if provider is None:  # same construction as ``analyze`` uses
        from providers import LocalRepositoryProvider
        provider = LocalRepositoryProvider()
    snapshot = provider._read(ReadRepositoryInput(str(repo))).snapshot
    languages = cap._detect_languages(snapshot)
    dna1 = cap._generate_dna(snapshot, languages, [], tree_depth=1)
    dna3 = cap._generate_dna(snapshot, languages, [], tree_depth=3)
    assert dna1.directory_tree == ["deep"]
    assert dna3.directory_tree == ["deep", "deep/er", "deep/er/still"]


@needs_git
def test_rie_pipeline_fills_structure_fields(tmp_path):
    from agos.rie.application import create_rie_pipeline

    repo = _git_repo(tmp_path, REPO)
    dna = create_rie_pipeline().execute(f"file://{repo}")
    assert "main.py" in dna.entry_points
    assert ".env.example" in dna.config_files
    assert ".github/workflows/ci.yml" in dna.config_files
    assert ".github" in dna.directory_tree
    assert all(".idea" not in str(x) for x in dna.config_files + dna.directory_tree)
    assert "entry_points" in dna.to_dict()


@needs_git
def test_tree_depth_reachable_via_execute_and_cache_distinguishes_it(tmp_path):
    from agos.kernel.capabilities import RepositoryAnalysisCapability

    repo = _git_repo(tmp_path, {"deep/er/still/file.py": "x\n", "main.py": "y\n"})
    url = f"file://{repo}"
    cap = RepositoryAnalysisCapability()
    dna_default = cap.execute({"url": url, "branch": "main", "cache": True})
    assert dna_default.directory_tree == ["deep", "deep/er", "deep/er/still"]
    # Same commit, different depth: the cache must not serve the first DNA.
    dna1 = cap.execute({"url": url, "branch": "main", "cache": True, "tree_depth": 1})
    assert dna1.directory_tree == ["deep"]
    assert dna1 != dna_default or dna1.directory_tree != dna_default.directory_tree


@needs_git
def test_secret_hidden_files_never_reach_the_dna(tmp_path):
    from agos.kernel.capabilities import RepositoryAnalysisCapability

    repo = _git_repo(tmp_path, {"main.py": "x\n", ".env": "SECRET=1\n",
                                 ".github/.env": "TOKEN=2\n", ".env.example": "A=\n"})
    dna = RepositoryAnalysisCapability().execute({"url": f"file://{repo}", "branch": "main", "cache": False})
    assert ".env.example" in dna.config_files
    assert all(".env" != c for c in dna.config_files)
    assert all(not c.startswith(".env/") and c != ".env" for c in dna.config_files)
    assert all(".github/.env" not in c for c in dna.config_files)
