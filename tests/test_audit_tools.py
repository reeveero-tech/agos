"""Audit tooling (R-Q-010): tests under tests/ are visible to the module register."""
import importlib.util
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, REPO / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_external_references_cover_subprocess_code_and_scripts(tmp_path):
    inv = load("agos_inventory", "tools/audit/inventory.py")
    sample = tmp_path / "test_sample.py"
    sample.write_text(
        "import json\n"
        "from pathlib import Path\n"
        "def test_a(x):\n"
        "    run('''\n        import agos_runtime\n        from registry.provider import ProviderRegistry\n    ''')\n"
        "    run(f'''\n        from core import AGOSKernel\n        k = AGOSKernel({x!r})\n    ''')\n"
        "    script = Path('k') / 'main.py'\n"
        "    other = 'not_a_kernel_file.py'\n")
    ref = inv.external_test_references(sample)
    assert {"json", "pathlib", "agos_runtime", "registry.provider", "core"} <= set(ref["imports"])
    assert ref["scripts"] == ["main"]


def test_inventory_records_external_tests_and_register_uses_them():
    data = json.loads((REPO / "docs/audit/inventory.json").read_text())
    paths = {t["path"] for t in data.get("external_tests", [])}
    assert "tests/test_bootstrap.py" in paths
    by_id = {f["id"]: f for f in data["files"]}
    assert "tests/test_bootstrap.py" in by_id["K:agos_runtime"].get("tested_by_external", [])
    register = (REPO / "docs/architecture/MODULE_REGISTER.md").read_text()
    row = next(line for line in register.splitlines() if "`agos-kernel/agos_runtime`" in line)
    assert row.split("|")[-3].strip() == "L4"
