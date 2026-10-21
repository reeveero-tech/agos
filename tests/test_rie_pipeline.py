"""RIE end-to-end smoke test (R-F-006): the pipeline runs on a real local git repository.

Detection *quality* (frameworks, dependencies, entry points) is covered by the W2 items
(R-W2-001..), not here; this test only pins that the five previously-dead rie modules are
alive and wired: fetch -> normalize -> detect -> aggregate -> DNA.
"""
import shutil
import subprocess

import pytest

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")


@pytest.fixture()
def local_repo(tmp_path):
    repo = tmp_path / "sample"
    repo.mkdir()
    (repo / "app.py").write_text("print('hello')\n")
    (repo / "requirements.txt").write_text("requests\n")
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@t", "PATH": __import__("os").environ["PATH"]}
    for cmd in (["git", "init", "-q", "-b", "main"], ["git", "add", "-A"], ["git", "commit", "-qm", "init"]):
        subprocess.run(cmd, cwd=repo, check=True, env=env)
    return repo


def test_rie_pipeline_produces_repository_dna(local_repo):
    from agos.rie.adapters import RepositoryDNA
    from agos.rie.application import create_rie_pipeline

    dna = create_rie_pipeline().execute(f"file://{local_repo}")
    assert isinstance(dna, RepositoryDNA)
    assert dna.name == "sample"
    assert dna.primary_language == "Python"
    assert "pip" in dna.package_managers
    assert "requirements.txt" in dna.config_files
    assert dna.total_files == 2
    assert len(dna.commit) == 40
