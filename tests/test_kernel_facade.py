"""AGOSKernel facade, MissionManager, KernelHealthService and the analysis cache (R-F-008).

Offline: missions run against local git repositories created per test.
"""
import json
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
KERNEL = REPO / "agos" / "agos-kernel"
GIT = ["git", "-c", "user.email=t@t", "-c", "user.name=t"]


def run(code: str, cwd: Path = KERNEL) -> str:
    r = subprocess.run([sys.executable, "-c", textwrap.dedent(code)], cwd=cwd,
                       capture_output=True, text=True, timeout=180)
    assert r.returncode == 0, r.stderr[-2000:]
    return r.stdout


def last(out: str) -> str:
    return out.strip().splitlines()[-1]


@pytest.fixture
def git_repo(tmp_path) -> Path:
    repo = tmp_path / "owner" / "sample"
    repo.mkdir(parents=True)
    (repo / "requirements.txt").write_text("flask\n")
    (repo / "app.py").write_text("import flask\n")
    for cmd in (["git", "init", "-q", "-b", "main"], ["git", "add", "-A"], [*GIT, "commit", "-qm", "init"]):
        subprocess.run(cmd, cwd=repo, check=True, capture_output=True)
    return repo


def test_lifecycle_and_registries():
    out = json.loads(last(run("""
        import json
        from core import AGOSKernel, KernelState
        k = AGOSKernel()
        before = (k.state.value, k.capability_registry)
        with k:
            during = (k.state.value, [c.name for c in k.capability_registry.list_all()],
                      [p.name for p in k.provider_registry.list_all()], k.running)
        k.shutdown()  # idempotent
        print(json.dumps({"before": [before[0], before[1] is None], "during": during,
                          "after": k.state.value}))
    """)))
    assert out["before"] == ["created", True]
    # R-W2-007: السبع الحقيقية مسجلة مع RepositoryAnalysis (اكتشاف الجذر يقبل المُعاد تصديره)
    expected_caps = sorted(["RepositoryAnalysis", "SecurityScan", "LicenseAnalysis",
                            "DocumentationAnalysis", "ConfigurationAnalysis",
                            "InfrastructureAnalysis", "RepositoryDNAGeneration",
                            "EngineeringKnowledgeExtraction"])
    assert out["during"] == ["running", expected_caps, ["LocalRepositoryProvider"], True]
    assert out["after"] == "stopped"


def test_mission_success_updates_mission_object(git_repo):
    out = json.loads(last(run(f"""
        import json
        from core import AGOSKernel
        from mission import Mission
        k = AGOSKernel().start()
        m = Mission(name="A", capability="RepositoryAnalysis", parameters={{"url": {str(git_repo)!r}}})
        r = k.mission_manager.execute(m)
        print(json.dumps({{"ok": r.is_success, "lang": r.data.primary_language, "status": m.status.value,
            "same_id": r.mission_id == m.id, "result_is_data": m.result is r.data,
            "timed": bool(m.started_at and m.completed_at), "history": len(k.mission_manager.history),
            "steps": [e["step"] for e in r.execution.events]}}))
    """)))
    assert out == {"ok": True, "lang": "Python", "status": "completed", "same_id": True,
                   "result_is_data": True, "timed": True, "history": 1,
                   "steps": ["Resolve Capability", "Resolve Provider", "Execute Capability"]}


def test_mission_failure_is_a_result_not_an_exception(tmp_path):
    out = last(run(f"""
        from core import AGOSKernel
        from mission import Mission
        k = AGOSKernel().start()
        m = Mission(name="F", capability="RepositoryAnalysis", parameters={{"url": {str(tmp_path / "nope")!r}}})
        r = k.mission_manager.execute(m)
        print(r.is_success, m.status.value, bool(r.error), m.error == r.error)
    """))
    assert out == "False failed True True"


def test_stopped_kernel_rejects_missions():
    out = last(run("""
        from core import AGOSKernel
        from mission import Mission
        k = AGOSKernel().start(); k.shutdown()
        m = Mission(name="X", capability="RepositoryAnalysis")
        r = k.mission_manager.execute(m)
        print(r.is_success, m.status.value, "not running" in r.error)
    """))
    assert out == "False failed True"


def test_start_failure_raises_boot_error(tmp_path):
    out = last(run(f"""
        import agos_runtime
        from core import AGOSKernel
        k = AGOSKernel({str(tmp_path)!r})
        try:
            k.start(); print("no-raise")
        except agos_runtime.BootError as e:
            print(k.state.value, "No capabilities loaded" in str(e))
    """))
    assert out == "failed True"


def test_health_report_is_truthful():
    out = json.loads(last(run("""
        import json
        from core import AGOSKernel
        from diagnostics import KernelHealthService, KernelHealthReport
        from registry.capability import CapabilityRegistry
        from registry.provider import ProviderRegistry
        k = AGOSKernel().start()
        rep = k.health()
        empty = KernelHealthService().generate_report(CapabilityRegistry(), CapabilityRegistry(), ProviderRegistry())
        print(json.dumps({"type": isinstance(rep, KernelHealthReport), "report": rep.to_dict(),
                          "empty": empty.status.value}))
    """)))
    assert out["type"] is True
    checks = {c["name"]: c for c in out["report"]["checks"]}
    assert checks["capabilities_loaded"]["status"] == "healthy"
    assert checks["providers_loaded"]["status"] == "healthy"
    assert checks["contracts"]["status"] == "healthy"
    # GenerateDNA is performed inline by RepositoryAnalysis; no provider offers it (R-W3-003)
    assert checks["skill_coverage"]["details"]["uncovered"] == {"RepositoryAnalysis": ["GenerateDNA"]}
    assert out["report"]["status"] == "degraded"
    assert out["empty"] == "unhealthy"


def test_analysis_cache_is_keyed_by_commit(git_repo):
    out = run(f"""
        import agos_runtime
        k = agos_runtime.boot()
        url = {str(git_repo)!r}
        a = k.analyze(url); b = k.analyze(url)
        print("MARK", a.result is not b.result, a.result.to_dict() == b.result.to_dict())
        import pathlib, subprocess
        pathlib.Path(url, "main.go").write_text("package main\\n")
        subprocess.run({GIT!r} + ["add", "-A"], cwd=url, check=True)
        subprocess.run({GIT!r} + ["commit", "-qm", "go"], cwd=url, check=True)
        c = k.analyze(url)
        print("MARK", "Go" in c.result.languages)
        d = k.run({{"name": "n", "capability": "RepositoryAnalysis", "parameters": {{"url": url, "cache": False}}}})
        print("MARK", d.state.value)
    """)
    marks = [line for line in out.splitlines() if line.startswith("MARK")]
    assert marks == ["MARK True True", "MARK True", "MARK completed"]
    # clones: first analysis, after the new commit, and the cache-disabled run — not the repeat
    assert out.count("[CAPABILITY] Cloning") == 3
    assert out.count("[CAPABILITY] Reusing DNA") == 1


def test_strict_return_hook_fails_false_returning_validation(tmp_path):
    shutil.copy(KERNEL / "conftest.py", tmp_path / "conftest.py")
    (tmp_path / "test_validation.py").write_text(
        "def test_ok():\n    return True\n\ndef test_bad():\n    return False\n")
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(tmp_path)],
                       cwd=tmp_path, capture_output=True, text=True, timeout=120)
    assert "1 failed, 1 passed" in r.stdout, r.stdout[-1500:]
    assert "returned False" in r.stdout
