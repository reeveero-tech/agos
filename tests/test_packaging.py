"""Packaging guarantees (R-F-001)."""
import ast
import sys
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
AGOS = REPO / "agos"

# import name -> distribution name
IMPORT_TO_DIST = {"yaml": "pyyaml", "memory_profiler": "memory-profiler"}
TEST_ONLY = {"pytest"}


def _local_names() -> set[str]:
    names = {"agos", "agos_kernel"}
    for p in AGOS.rglob("*"):
        if "__pycache__" in p.parts:
            continue
        names.add(p.stem if p.suffix == ".py" else p.name)
        names.add(p.name.replace("-", "_"))
    return names


def _third_party_imports() -> dict[str, set[str]]:
    local, found = _local_names(), {}
    for f in AGOS.rglob("*.py"):
        if "__pycache__" in f.parts:
            continue
        try:
            tree = ast.parse(f.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        for n in ast.walk(tree):
            mods = [a.name for a in n.names] if isinstance(n, ast.Import) else \
                [n.module] if isinstance(n, ast.ImportFrom) and n.level == 0 and n.module else []
            for m in mods:
                top = m.split(".")[0]
                if top not in sys.stdlib_module_names and top not in local:
                    found.setdefault(top, set()).add(str(f.relative_to(REPO)))
    return found


def _declared() -> tuple[set[str], set[str]]:
    data = tomllib.loads((REPO / "pyproject.toml").read_text())
    norm = lambda req: req.split(";")[0].split("[")[0].split(">")[0].split("=")[0].split("<")[0].strip().lower()
    runtime = {norm(r) for r in data["project"]["dependencies"]}
    dev = {norm(r) for group in data.get("dependency-groups", {}).values() for r in group if isinstance(r, str)}
    return runtime, dev


def test_project_metadata():
    data = tomllib.loads((REPO / "pyproject.toml").read_text())
    assert data["project"]["name"] == "agos"
    assert data["build-system"]["build-backend"] == "hatchling.build"
    import agos
    assert data["project"]["version"] == agos.__version__


def test_every_third_party_import_is_declared():
    runtime, dev = _declared()
    missing = {}
    for mod, files in _third_party_imports().items():
        dist = IMPORT_TO_DIST.get(mod, mod).lower()
        pool = dev if mod in TEST_ONLY else runtime
        if dist not in pool:
            missing[mod] = sorted(files)[:3]
    assert not missing, f"undeclared third-party imports: {missing}"


def test_console_script_target_exists():
    from agos.cli import main
    assert callable(main)
