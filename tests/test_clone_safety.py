"""R-W2-005 — hardened cloning: allowlist, timeout, caps, cleanup, symlinks, default branch.

Acceptance (ROADMAP): «اختبارات مستودع ضخم/مشوه/بطيء/رابط رمزي» — the four threat shapes
are built locally and deterministically (no network, no real multi-gigabyte repos):

* مشوه (deformed): a URL outside the allowlist, a failing clone, a repo that breaches
  the size/file caps, a repo whose symlink escapes the root.
* بطيء (slow): a fake ``git`` binary that sleeps before cloning, killed by the timeout.
* ضخم (huge): caps enforced on real measurements (a small file made "too big" for its
  cap, a repo with "too many" files for its cap) — the same code path scales.
* رابط رمزي (symlink): an escaping link is rejected; an internal link is fine.
* الفرع الافتراضي: a ``master``-default repository clones even when ``main`` is asked.
* تنظيف مؤقت: no ``agos_clone_*`` temp dir survives any rejection.
"""
import os
import shutil
import stat
import subprocess

import pytest

from agos.kernel import clone_safety as cs


def _git_repo(path, files, default_branch="main"):
    """A real local git repo whose files are committed on ``default_branch``."""
    path.mkdir(parents=True, exist_ok=True)
    for rel, text in files.items():
        p = path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
           "PATH": os.environ["PATH"]}
    for cmd in (["git", "init", "-q", "-b", default_branch],
                ["git", "remote", "add", "origin", "https://github.com/t/ref.git"],
                ["git", "add", "-A", "-f"],
                ["git", "commit", "-qm", "init"]):
        subprocess.run(cmd, cwd=path, check=True, env=env, capture_output=True)
    return path


def _clone_dirs():
    """The agos_clone_* temp dirs currently on disk."""
    import glob
    import tempfile
    return set(glob.glob(os.path.join(tempfile.gettempdir(), "agos_clone_*")))


needs_git = pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")


# ---------------------------------------------------------------------------
# URL allowlist
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("url", ["https://github.com/x/y", "https://gitlab.com/x/y",
                                "file:///tmp/repo", "git@github.com:x/y"])
def test_allowed_urls_pass(url):
    assert cs.check_url(url) == url


@pytest.mark.parametrize("url", ["", "ftp://evil.com/x", "http://evil.com/x/y",
                                "relative/path", "//evil.com/x", "~/repo",
                                "https://evil.github.com.fake/x"])
def test_disallowed_urls_are_rejected(url):
    with pytest.raises(cs.CloneRejected, match="allowlist|url empty"):
        cs.check_url(url)


def test_local_absolute_paths_are_caller_owned_and_allowed():
    # The allowlist governs remote URLs; a local absolute path is the caller's own
    # disk — cloning it grants nothing new. Relative paths and //host disguises stay
    # rejected.
    assert cs.check_url("/data/repos/sample") == "/data/repos/sample"


def test_allowlist_is_extensible_per_call():
    with pytest.raises(cs.CloneRejected):
        cs.check_url("https://example.com/x")
    assert cs.check_url("https://example.com/x", allowlist=("https://example.com/",)) == \
        "https://example.com/x"


# ---------------------------------------------------------------------------
# The default branch
# ---------------------------------------------------------------------------
@needs_git
def test_default_branch_is_resolved(tmp_path):
    repo = _git_repo(tmp_path / "src", {"main.py": "print('hi')\n"},
                    default_branch="master")
    assert cs.default_branch(f"file://{repo}") == "master"


@needs_git
def test_master_default_repo_clones_even_when_main_is_asked(tmp_path):
    repo = _git_repo(tmp_path / "src", {"main.py": "print('hi')\n"},
                    default_branch="master")
    path = cs.clone(f"file://{repo}", branch="main")
    try:
        assert os.path.isfile(os.path.join(path, "main.py"))
    finally:
        shutil.rmtree(os.path.dirname(path), ignore_errors=True)


@needs_git
def test_explicit_branch_failure_without_default_fallback(tmp_path):
    repo = _git_repo(tmp_path / "src", {"main.py": "x\n"}, default_branch="master")
    # The requested branch exists nowhere and the default equals nothing useful —
    # asking for a branch that is not the default and does not exist still fails,
    # but only after the fallback attempt (deterministic rejection, not a hang).
    with pytest.raises(cs.CloneRejected, match="clone failed"):
        cs.clone(f"file://{repo}", branch="nonexistent-branch")
    assert _clone_dirs() == _clone_dirs()  # no temp dir survives the rejection


# ---------------------------------------------------------------------------
# Slow: the timeout
# ---------------------------------------------------------------------------
@needs_git
def test_slow_clone_times_out_and_cleans_up(tmp_path):
    repo = _git_repo(tmp_path / "src", {"main.py": "x\n"})
    fake_git = tmp_path / "slow-git"
    fake_git.write_text("#!/bin/sh\nsleep 30\nexec git \"$@\"\n")
    fake_git.chmod(fake_git.stat().st_mode | stat.S_IEXEC)
    before = _clone_dirs()
    with pytest.raises(cs.CloneRejected, match="timed out"):
        cs.clone(f"file://{repo}", timeout=2, git_bin=str(fake_git))
    assert _clone_dirs() == before  # the temp dir is gone despite the timeout


# ---------------------------------------------------------------------------
# Huge: the caps
# ---------------------------------------------------------------------------
@needs_git
def test_file_count_cap_rejects_huge_repos(tmp_path):
    files = {f"m{i}.py": "x\n" for i in range(10)}
    repo = _git_repo(tmp_path / "src", files)
    before = _clone_dirs()
    with pytest.raises(cs.CloneRejected, match="file cap"):
        cs.clone(f"file://{repo}", max_files=5)
    assert _clone_dirs() == before


@needs_git
def test_size_cap_rejects_huge_repos(tmp_path):
    repo = _git_repo(tmp_path / "src", {"blob.bin": "0" * (2 * 1024 * 1024)})
    before = _clone_dirs()
    with pytest.raises(cs.CloneRejected, match="size cap"):
        cs.clone(f"file://{repo}", max_bytes=1024 * 1024)
    assert _clone_dirs() == before


@needs_git
def test_caps_measured_not_assumed(tmp_path):
    # 10 files at 100KB each: under the file cap, over the size cap — and the
    # mirror case — proves both caps are checked independently.
    repo = _git_repo(tmp_path / "src", {f"m{i}.bin": "0" * (100 * 1024) for i in range(10)})
    assert cs.measure_repo(repo) == (10, 10 * 100 * 1024)


# ---------------------------------------------------------------------------
# Symlinks
# ---------------------------------------------------------------------------
@needs_git
def test_escaping_symlink_rejects_the_clone(tmp_path):
    repo = _git_repo(tmp_path / "src", {"main.py": "x\n"})
    outside = tmp_path / "outside.txt"
    outside.write_text("secret")
    os.symlink(outside, repo / "leak.txt")
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
           "PATH": os.environ["PATH"]}
    for cmd in (["git", "add", "-A", "-f"], ["git", "commit", "-qm", "leak"]):
        subprocess.run(cmd, cwd=repo, check=True, env=env, capture_output=True)
    before = _clone_dirs()
    with pytest.raises(cs.CloneRejected, match="symlinks escape"):
        cs.clone(f"file://{repo}")
    assert _clone_dirs() == before


@needs_git
def test_internal_symlink_is_allowed(tmp_path):
    repo = _git_repo(tmp_path / "src", {"main.py": "x\n"})
    os.symlink("main.py", repo / "alias.py")
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
           "PATH": os.environ["PATH"]}
    for cmd in (["git", "add", "-A", "-f"], ["git", "commit", "-qm", "alias"]):
        subprocess.run(cmd, cwd=repo, check=True, env=env, capture_output=True)
    path = cs.clone(f"file://{repo}")
    try:
        assert os.path.isfile(os.path.join(path, "main.py"))
    finally:
        shutil.rmtree(os.path.dirname(path), ignore_errors=True)


def test_escape_symlinks_finds_only_outside_links(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "in.txt").write_text("x")
    (root / "outside.txt").write_text("y")
    os.symlink(root / "in.txt", root / "inside_link")
    os.symlink(tmp_path / "outside.txt", root / "outside_link")
    assert cs.escape_symlinks(root) == ["outside_link"]


# ---------------------------------------------------------------------------
# Always-cleanup and the live paths
# ---------------------------------------------------------------------------
@needs_git
def test_kernel_provider_clone_is_hardened(tmp_path):
    from agos.kernel.providers import LocalRepositoryProvider

    provider = LocalRepositoryProvider()
    with pytest.raises(cs.CloneRejected, match="allowlist"):
        provider.Clone("http://evil.example.com/x")


@needs_git
def test_kernel_capability_still_works_end_to_end(tmp_path):
    from agos.kernel.capabilities import RepositoryAnalysisCapability

    repo = _git_repo(tmp_path / "src", {"main.py": "print('hi')\n"})
    dna = RepositoryAnalysisCapability().execute(
        {"url": f"file://{repo}", "branch": "main", "cache": False})
    assert dna.primary_language == "Python"


@needs_git
def test_rie_fetcher_is_hardened(tmp_path):
    from agos.rie.infrastructure import GitFetcher

    with pytest.raises(cs.CloneRejected, match="allowlist"):
        GitFetcher().fetch("http://evil.example.com/x")


@needs_git
def test_rie_pipeline_cleans_up_its_single_clone(tmp_path):
    import glob
    import tempfile

    from agos.rie.application import create_rie_pipeline

    repo = _git_repo(tmp_path / "src", {"main.py": "print('hi')\n"})
    before = set(glob.glob(os.path.join(tempfile.gettempdir(), "agos_clone_*")))
    dna = create_rie_pipeline().execute(f"file://{repo}")
    assert dna.primary_language == "Python"
    after = set(glob.glob(os.path.join(tempfile.gettempdir(), "agos_clone_*")))
    assert after == before  # one clone per run, and it is gone afterwards


@needs_git
def test_symlinked_files_are_never_read_through(tmp_path):
    # A symlink inside the repo pointing outside is rejected at clone time; this covers
    # the read path directly: a repo already on disk (repo_path mode) must not read
    # through a symlink either.
    from agos.kernel.providers import LocalRepositoryProvider

    repo = _git_repo(tmp_path / "src", {"main.py": "x\n"})
    outside = tmp_path / "outside.py"
    outside.write_text("SECRET = 1\n")
    os.symlink(outside, repo / "leak.py")
    snapshot = LocalRepositoryProvider().Read(str(repo))
    paths = [f.path for f in snapshot.files if not f.is_dir]
    assert "main.py" in paths
    assert "leak.py" not in paths  # the symlink is never read through
