#!/usr/bin/env python3
"""R-F-011 — prove the declared runtime dependencies are sufficient, in a clean environment.

1. Create a fresh virtualenv (``uv venv``, Python 3.12) with **only** the locked runtime
   dependencies (``uv export --frozen --no-dev``) and the ``agos`` wheel (``--no-deps``).
   The dev group (pytest, …) is deliberately absent; the run asserts that.
2. **Installed probe** — from a neutral directory (repository not on ``sys.path``):
   import ``agos``, ``agos_kernel``, ``agos.cli``, boot the kernel through
   ``agos.kernel.agos_runtime`` and run ``agos-analyze --help``-free smoke (import only).
3. **Module probe** — import every *runtime* module of the source tree (the files the
   inventory knows, test files excluded) with the clean interpreter, using the same probe
   as ``tools/audit/inventory.py``.

Failures (exit 1):
* any ``ModuleNotFoundError`` for a module that is not first-party (a missing external
  package — the acceptance criterion of R-F-011);
* any module that imports in the development environment (``docs/audit/inventory.json``
  ``import_status == OK``) but not in the clean one;
* the installed probe failing.

    .venv/bin/python tools/audit/clean_env.py           # run, write docs/audit/clean_env.json
    .venv/bin/python tools/audit/clean_env.py --check   # run, exit 1 on failure (CI), no write
    .venv/bin/python tools/audit/clean_env.py --without=psutil   # canary: must FAIL (exit 1)
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import dependencies  # noqa: E402  (sibling tool)
import inventory  # noqa: E402  (sibling tool: probe_import)

OUT = REPO / "docs" / "audit" / "clean_env.json"

INSTALLED_PROBE = r"""
import json, sys, importlib
out = {"sys_path_has_repo": any(p and __REPO__ in p for p in sys.path)}
import agos, agos_kernel, agos.cli
out["agos_version"] = agos.__version__
out["agos_kernel_version"] = getattr(agos_kernel, "__version__", None)
rt = importlib.import_module("agos.kernel.agos_runtime")
k = rt.boot()
out["boot_success"] = bool(k.result.success)
out["capabilities"] = sorted(c.name for c in k.capability_registry.list_all())
out["providers"] = sorted(p.name for p in k.provider_registry.list_all())
try:
    import pytest  # noqa
    out["dev_group_absent"] = False
except ModuleNotFoundError:
    out["dev_group_absent"] = True
print(json.dumps(out))
"""

MISSING = re.compile(r"ModuleNotFoundError: No module named '([^']+)'")


def run(cmd, **kw) -> str:
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode != 0:
        raise RuntimeError(f"{' '.join(map(str, cmd))} failed:\n{r.stdout}\n{r.stderr}")
    return r.stdout


def make_env(tmp: Path, without: tuple = ()) -> Path:
    venv = tmp / "venv"
    run(["uv", "venv", "--python", "3.12", "--quiet", str(venv)], cwd=tmp)
    py = venv / "bin" / "python"
    req = tmp / "requirements.txt"
    run(["uv", "export", "--frozen", "--no-dev", "--no-hashes", "--no-emit-project",
         "--quiet", "-o", str(req)], cwd=REPO)
    if without:  # canary mode: leave packages out to prove the probe notices
        drop = {dependencies.normalise(w) for w in without}
        lines = req.read_text().splitlines()
        req.write_text("\n".join(l for l in lines
                                 if dependencies.normalise(l.split("==")[0].strip()) not in drop) + "\n")
    # --no-deps: the export is the complete locked closure; nothing may be pulled in implicitly
    run(["uv", "pip", "install", "--quiet", "--no-deps", "--python", str(py), "-r", str(req)], cwd=tmp)
    run(["uv", "pip", "install", "--quiet", "--python", str(py), "--no-deps", str(REPO)], cwd=tmp)
    return py


def installed_probe(py: Path, tmp: Path) -> dict:
    code = INSTALLED_PROBE.replace("__REPO__", repr(str(REPO)))
    out = run([str(py), "-I", "-c", code], cwd=tmp, timeout=300)
    return json.loads(out.strip().splitlines()[-1])


def runtime_modules() -> list[dict]:
    data = json.loads((REPO / "docs" / "audit" / "inventory.json").read_text(encoding="utf-8"))
    return [f for f in data["files"]
            if f.get("module") and dependencies.scope_of(Path(f["path"])) == "runtime"]


def module_probe(py: Path) -> list[dict]:
    files = runtime_modules()
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda f: inventory.probe_import(f, str(py)), files))
    return [{"path": f["path"], "dev_status": f.get("import_status", ""), "clean_status": r}
            for f, r in zip(files, results)]


def evaluate(installed: dict, modules: list[dict]) -> list[str]:
    fp = dependencies.first_party(REPO)
    failures: list[str] = []
    for key in ("boot_success", "dev_group_absent"):
        if not installed.get(key):
            failures.append(f"installed probe: {key} is {installed.get(key)!r}")
    if installed.get("sys_path_has_repo"):
        failures.append("installed probe: repository leaked onto sys.path (not a clean probe)")
    for m in modules:
        status = m["clean_status"]
        miss = MISSING.search(status)
        if miss and miss.group(1).split(".")[0] not in fp:
            failures.append(f"{m['path']}: missing external package `{miss.group(1)}`")
        elif m["dev_status"] == "OK" and status != "OK":
            failures.append(f"{m['path']}: OK in the dev env, `{status}` in the clean env")
    return failures


def main() -> int:
    without = tuple(a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--without="))
    with tempfile.TemporaryDirectory(prefix="agos-clean-") as t:
        tmp = Path(t)
        py = make_env(tmp, without)
        freeze = sorted(l for l in run(["uv", "pip", "freeze", "--python", str(py)]).splitlines()
                        if l and not l.startswith("agos"))
        installed = installed_probe(py, tmp)
        modules = module_probe(py)
    failures = evaluate(installed, modules)
    ok = sum(1 for m in modules if m["clean_status"] == "OK")
    report = {
        "generated_by": "tools/audit/clean_env.py",
        "python": "3.12",
        "environment": "uv venv + `uv export --frozen --no-dev` + agos wheel (--no-deps)",
        "installed_packages": freeze,
        "installed_probe": installed,
        "runtime_modules_probed": len(modules),
        "runtime_modules_ok": ok,
        "not_ok_in_both_envs": sorted(m["path"] for m in modules
                                      if m["clean_status"] != "OK" and m["dev_status"] != "OK"),
        "failures": failures,
    }
    print(f"clean env: {ok}/{len(modules)} runtime modules import; "
          f"boot={installed.get('boot_success')}; failures={len(failures)}")
    for f in failures:
        print("failure:", f)
    if "--check" not in sys.argv and not without:
        OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"wrote {OUT.relative_to(REPO)}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
