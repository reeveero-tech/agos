"""The single boot path (R-W3-001): agos_runtime.boot() -> Bootstrapper -> MissionEngine.

Every scenario runs in a fresh interpreter (no ``sys.modules`` leakage) and missions run
against a local git repository, so the tests need no network.
"""
import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
KERNEL = REPO / "agos" / "agos-kernel"


def run(code: str, cwd: Path = KERNEL) -> str:
    r = subprocess.run([sys.executable, "-c", textwrap.dedent(code)], cwd=cwd,
                       capture_output=True, text=True, timeout=180)
    assert r.returncode == 0, r.stderr[-2000:]
    return r.stdout.strip().splitlines()[-1]


@pytest.fixture(scope="module")
def git_repo(tmp_path_factory) -> Path:
    repo = tmp_path_factory.mktemp("owner") / "sample"
    repo.mkdir()
    (repo / "requirements.txt").write_text("flask\n")
    (repo / "app.py").write_text("import flask\n")
    env = ["-c", "user.email=t@t", "-c", "user.name=t"]
    for cmd in (["git", "init", "-q", "-b", "main"], ["git", "add", "-A"],
                ["git", *env, "commit", "-qm", "init"]):
        subprocess.run(cmd, cwd=repo, check=True, capture_output=True)
    return repo


def test_default_boot_discovers_and_validates_real_components():
    out = json.loads(run("""
        import json, agos_runtime
        k = agos_runtime.boot()
        print(json.dumps({**k.summary(),
            "contracts": sorted(r.contract_id for t in k.contract_engine.registry._contracts
                                for r in k.contract_engine.registry.list_all(t)),
            "bus": k.event_bus is not None, "engine": k.mission_engine is not None}))
    """))
    assert out["ready"] is True and out["errors"] == []
    assert "RepositoryAnalysis" in out["capabilities"]
    assert "LocalRepositoryProvider" in out["providers"]
    assert {"RepositoryAnalysis", "LocalRepositoryProvider"} <= set(out["contracts"])
    assert out["bus"] and out["engine"]


def test_bootstrapper_default_base_path_is_kernel_root():
    out = run("""
        import os
        from bootstrapper import Bootstrapper
        from discovery import AutoDiscovery, kernel_root
        print(Bootstrapper().base_path == kernel_root() == AutoDiscovery().base_path
              == os.path.abspath("."))
    """)
    assert out == "True"


def test_discovery_keeps_class_identity():
    out = run("""
        import providers, capabilities, agos_runtime
        before = providers.LocalRepositoryProvider, capabilities.RepositoryAnalysisCapability
        k = agos_runtime.boot()
        p = k.provider_registry.get("LocalRepositoryProvider")
        c = k.capability_registry.get("RepositoryAnalysis")
        print(isinstance(p, before[0]), isinstance(c, before[1]),
              providers.LocalRepositoryProvider is before[0])
    """)
    assert out == "True True True"


def test_mission_runs_end_to_end_through_pipeline(git_repo):
    out = json.loads(run(f"""
        import json, agos_runtime
        k = agos_runtime.boot()
        r = k.analyze({str(git_repo)!r}, branch="main")
        evs = [e.type.value for e in k.event_bus.get_events(r.mission_id)]
        print(json.dumps({{"state": r.state.value, "id": r.mission_id,
            "dna": type(r.result).__name__, "lang": r.result.primary_language,
            "steps": [e["step"] for e in r.events], "events": evs}}))
    """))
    assert out["state"] == "completed" and out["id"]
    assert out["dna"] == "RepositoryDNA" and out["lang"] == "Python"
    assert out["steps"] == ["Resolve Capability", "Resolve Provider", "Execute Capability"]
    assert out["events"] == ["capability_selected", "provider_selected",
                             "execution_started", "execution_completed"]


def test_failed_mission_is_reported_not_raised(tmp_path):
    out = run(f"""
        import agos_runtime
        r = agos_runtime.boot().analyze({str(tmp_path / "missing")!r})
        print(r.state.value, bool(r.error))
    """)
    assert out == "failed True"


def test_dict_missions_get_unique_ids():
    out = run("""
        from mission_engine import MissionParser
        a = MissionParser.parse({"name": "x", "capability": "X"})
        b = MissionParser.parse({"name": "x", "capability": "X"})
        c = MissionParser.parse({"id": "fixed", "name": "x", "capability": "X"})
        print(bool(a.id) and a.id != b.id and c.id == "fixed")
    """)
    assert out == "True"


def test_provider_resolver_reports_selected_providers_skills():
    out = run("""
        from interfaces import IProvider
        from registry.capability import CapabilityRegistry
        from registry.provider import ProviderRegistry
        from resolvers import ProviderResolver

        class Full(IProvider):
            name = "Full"
            def supports_skill(self, s): return True
            def execute(self, s, i): return None

        class Half(IProvider):
            name = "Half"
            def supports_skill(self, s): return s == "A"
            def execute(self, s, i): return None

        class Cap:
            skills = ["A", "B"]

        reg = ProviderRegistry(); reg.register(Full()); reg.register(Half())
        sel = ProviderResolver(reg, CapabilityRegistry()).resolve(Cap())
        print(sel.provider_name, sel.supported_skills)
    """)
    assert out == "Full ['A', 'B']"


def test_boot_failure_is_explicit(tmp_path):
    out = run(f"""
        import agos_runtime
        k = agos_runtime.boot({str(tmp_path)!r})
        try:
            k.require_ready(); raised = False
        except agos_runtime.BootError:
            raised = True
        print(k.ready, "No capabilities loaded" in k.errors, raised)
    """)
    assert out == "False True True"


def test_runtime_reachable_through_unified_namespace():
    out = run("""
        import agos
        import agos_kernel.agos_runtime as a
        import agos.kernel.agos_runtime as b
        print(a is b, a.boot().ready)
    """, cwd=REPO)
    assert out == "True True"


def test_main_boots_through_bootstrapper(git_repo, tmp_path):
    r = subprocess.run([sys.executable, str(KERNEL / "main.py"), str(git_repo)], cwd=tmp_path,
                       capture_output=True, text=True, timeout=180)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
    assert "[AGOS] Booted via Bootstrapper:" in r.stdout
    assert "Resolve Capability -> Resolve Provider -> Execute Capability" in r.stdout
    dna = json.loads((tmp_path / "RepositoryDNA.json").read_text())
    assert dna["primary_language"] == "Python"

    bad = subprocess.run([sys.executable, str(KERNEL / "main.py"), str(tmp_path / "missing")],
                         cwd=tmp_path, capture_output=True, text=True, timeout=180)
    assert bad.returncode == 1 and "[FAILURE] Mission failed" in bad.stdout
