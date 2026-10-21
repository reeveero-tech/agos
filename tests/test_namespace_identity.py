"""Namespace & single-identity guarantees (R-F-003, R-F-004, R-F-005; ADR-0001).

Each scenario runs in a fresh interpreter so ``sys.modules`` state cannot leak between
cases and import *order* is exercised explicitly.
"""
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
AGOS = REPO / "agos"
KERNEL = AGOS / "agos-kernel"


def run(code: str, cwd: Path = REPO) -> str:
    r = subprocess.run([sys.executable, "-c", textwrap.dedent(code)], cwd=cwd,
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr[-2000:]
    return r.stdout.strip()


def test_agos_kernel_alias_is_same_object_as_kernel_module():
    out = run("""
        import agos_kernel, core.seal as a
        import agos_kernel.core.seal as b
        print(a is b, agos_kernel.__version__)
    """, cwd=KERNEL)
    assert out == "True 2.0.0"


def test_agos_kernel_importable_from_agos_dir():
    out = run("""
        from agos_kernel.civilization.knowledge_graph import KnowledgeGraph, GraphBuilder
        print(GraphBuilder().graph.__class__ is KnowledgeGraph)
    """, cwd=AGOS)
    assert out == "True"


def test_agos_kernel_does_not_shadow_platform_package_with_same_name():
    # From agos/, bare `civilization` is the platform package; the kernel one stays agos_kernel.*
    out = run("""
        import agos_kernel.civilization as k
        import civilization as outer
        print(k is not outer, 'agos-kernel' in k.__file__, 'agos-kernel' not in outer.__file__)
    """, cwd=AGOS)
    assert out == "True True True"


@pytest.mark.parametrize("alias,src", [
    ("event_engine", "event-engine"), ("mission_engine", "mission-engine"),
    ("skill_engine", "skill-engine"), ("decision_pipeline", "decision-pipeline"),
    ("execution_context", "execution-context"), ("resource_manager", "resource-manager"),
    ("state_store", "state-store"),
])
def test_hyphenated_dirs_importable_via_alias(alias, src):
    out = run(f"import {alias} as m; print(m.__agos_alias_of__, m.__file__.split('/')[-2])", cwd=KERNEL)
    assert out == f"{src} {src}"


def test_bootstrapper_importable():
    assert run("from bootstrapper import Bootstrapper; print(Bootstrapper.__name__)", cwd=KERNEL) == "Bootstrapper"


def test_agos_kernel_namespace_is_same_kernel():
    out = run("""
        import agos, agos_kernel
        import agos.kernel as k
        import agos.kernel.core.seal as a
        import agos_kernel.core.seal as b
        from agos.kernel.bootstrapper import Bootstrapper
        import bootstrapper
        print(k is agos_kernel, a is b, Bootstrapper is bootstrapper.Bootstrapper)
    """)
    assert out == "True True True"


@pytest.mark.parametrize("order", ["bare_first", "namespaced_first"])
def test_platform_package_single_identity_regardless_of_order(order):
    first, second = ("cognitive", "agos.cognitive") if order == "bare_first" else ("agos.cognitive", "cognitive")
    out = run(f"""
        import sys, importlib
        sys.path.insert(0, {str(AGOS)!r})
        import agos
        a = importlib.import_module({first!r})
        b = importlib.import_module({second!r})
        print(a is b)
    """)
    assert out == "True"


def test_colliding_names_stay_separate_under_agos_prefix():
    out = run("""
        import agos
        import agos.civilization as outer
        import agos.kernel.civilization as kern
        print(outer is not kern, 'agos-kernel' in kern.__file__, 'agos-kernel' not in outer.__file__)
    """)
    assert out == "True True True"


def test_relative_imports_in_cloud_and_seos():
    out = run("""
        import agos.cloud.integration as ci, agos.seos.execution as se
        print(ci.__name__, se.__name__)
    """)
    assert out == "agos.cloud.integration agos.seos.execution"


def test_keyword_named_module_has_importable_alias():
    out = run("""
        import importlib
        import agos.ecosystem.global_ecosystem as g
        print(g is importlib.import_module('agos.ecosystem.global'))
    """)
    assert out == "True"


def test_platform_packages_listed():
    out = run("import agos; p = agos.platform_packages(); print('cognitive' in p, 'agos_kernel' in p)")
    assert out == "True False"


# Modules that may still fail under agos.* — each tied to an open roadmap item.
# R-F-006 empties this set; it must only ever shrink.
KNOWN_NAMESPACE_FAILURES = {
    "agos.rie.adapters", "agos.rie.application", "agos.rie.application.dna_generator",
    "agos.rie.application.scoring", "agos.rie.infrastructure",  # R-F-006
}


def test_every_platform_module_importable_under_agos_namespace_with_kernel():
    """R-F-005 acceptance: all of agos/ imports as agos.<name> in ONE process with the kernel."""
    out = run(r"""
        import importlib, pathlib, json
        import agos
        from agos.kernel.bootstrapper import Bootstrapper
        import agos.kernel.civilization.knowledge_graph
        A = pathlib.Path(agos.__file__).parent
        mods = []
        for f in sorted(A.rglob('*.py')):
            rel = f.relative_to(A)
            if rel.parts[0] in ('agos-kernel', 'agos_kernel') or '__pycache__' in rel.parts:
                continue
            parts = list(rel.with_suffix('').parts)
            if parts[-1] == '__init__':
                parts = parts[:-1]
            if not parts or not all(p.isidentifier() for p in parts):
                continue
            mods.append('agos.' + '.'.join(parts))
        fails = []
        for m in mods:
            try:
                importlib.import_module(m)
            except BaseException as e:
                fails.append(m)
        print(json.dumps({"total": len(mods), "fails": fails}))
    """)
    import json
    res = json.loads(out.splitlines()[-1])
    assert res["total"] > 100
    assert set(res["fails"]) <= KNOWN_NAMESPACE_FAILURES, set(res["fails"]) - KNOWN_NAMESPACE_FAILURES
