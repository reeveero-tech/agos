"""External dependency audit (R-F-011)."""
import json
import subprocess
import sys
import textwrap
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools" / "audit"))
import dependencies  # noqa: E402


def test_committed_report_is_fresh_and_has_no_problems():
    r = subprocess.run([sys.executable, str(REPO / "tools/audit/dependencies.py"), "--check"],
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr


def _fake_repo(tmp: Path, deps: list, files: dict) -> Path:
    (tmp / "agos" / "agos-kernel").mkdir(parents=True)
    (tmp / "tests").mkdir()
    (tmp / "tools").mkdir()
    reqs = ", ".join(f'"{d}"' for d in deps)
    (tmp / "pyproject.toml").write_text(
        f'[project]\nname = "x"\ndependencies = [{reqs}]\n[dependency-groups]\ndev = ["pytest"]\n')
    for rel, code in files.items():
        p = tmp / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(textwrap.dedent(code))
    return tmp


def test_canary_undeclared_runtime_import_is_a_problem(tmp_path):
    repo = _fake_repo(tmp_path, [], {"agos/agos-kernel/m.py": "import leftpad_unknown\nfrom yaml import safe_load\n"})
    problems = dependencies.build_report(repo)["problems"]
    assert any("leftpad_unknown" in p for p in problems)
    assert any("`yaml` (pyyaml)" in p for p in problems)  # import name -> distribution mapping


def test_canary_classification(tmp_path):
    repo = _fake_repo(tmp_path, ["pyyaml>=6", "unused-dist"], {
        "agos/agos-kernel/m.py": "import yaml\ntry:\n    import fancy_opt\nexcept ImportError:\n    fancy_opt = None\n"
                                 "T = '''\\nimport flask\\napp = 1\\n'''\n",
        "agos/agos-kernel/sub/test_x.py": "import pytest\n",
        "tests/test_y.py": "import pytest\nS = '''\\nimport bogus_in_test_data\\n'''\n",
        "agos/agos-kernel/sibling.py": "", "agos/agos-kernel/user.py": "import sibling\nimport m\n",
    })
    rep = dependencies.build_report(repo)
    scopes = {d["import"]: d["scopes"] for d in rep["external_imports"]}
    assert set(scopes["yaml"]) == {"runtime"}
    assert set(scopes["fancy_opt"]) == {"optional"}          # guarded: not required
    assert set(scopes["flask"]) == {"generated"}             # template in platform code: informational
    assert set(scopes["pytest"]) == {"dev"}                  # test files, even under agos/
    assert "bogus_in_test_data" not in scopes and "sibling" not in scopes and "m" not in scopes
    # optional/generated imports are not problems; an unexplained unused declaration is
    assert rep["problems"] == ["declared `unused-dist` is imported nowhere and has no documented reason"]


def test_import_name_maps_agree():
    sys.path.insert(0, str(REPO / "agos" / "agos-kernel" / "core" / "tests"))
    import security_scan
    for k, v in security_scan.IMPORT_TO_DIST.items():
        assert dependencies.IMPORT_TO_DIST[k] == v


def test_clean_environment_report():
    """The committed result of tools/audit/clean_env.py (CI re-runs it with --check)."""
    rep = json.loads((REPO / "docs/audit/clean_env.json").read_text(encoding="utf-8"))
    assert rep["failures"] == []
    assert rep["installed_probe"]["boot_success"] and rep["installed_probe"]["dev_group_absent"]
    assert not rep["installed_probe"]["sys_path_has_repo"]
    assert rep["runtime_modules_ok"] == rep["runtime_modules_probed"] > 0
    installed = {dependencies.normalise(p.split("==")[0]) for p in rep["installed_packages"]}
    assert dependencies.declared(REPO)["runtime"] <= installed
    assert "pytest" not in installed


def test_canary_local_file_cannot_mask_a_declared_dependency(tmp_path):
    repo = _fake_repo(tmp_path, ["pyyaml"], {"tools/yaml.py": "", "agos/agos-kernel/m.py": "import yaml\n"})
    rep = dependencies.build_report(repo)
    assert {d["import"]: set(d["scopes"]) for d in rep["external_imports"]}["yaml"] == {"runtime"}
