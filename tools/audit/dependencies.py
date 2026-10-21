#!/usr/bin/env python3
"""R-F-011 — audit of the external (third-party) dependencies actually used by AGOS.

Every ``*.py`` under ``agos/``, ``tests/`` and ``tools/`` is parsed (AST, nothing is
executed) and each import whose root is neither stdlib nor first-party is classified:

* scope ``runtime``  — platform code (``agos/`` outside test files);
* scope ``dev``      — test code (``tests/``, ``test_*.py``, ``conftest.py``, ``*/tests/*``);
* scope ``tooling``  — repository tools (``tools/``);
* scope ``generated``— imports that only appear inside code *templates* in platform code
  (string literals the platform emits or analyses, e.g. the generated Python SDK). They
  are informational: they are dependencies of the generated/analysed code, not of AGOS.
  Strings in tests and tools are test data and are ignored;
* ``optional``       — the import is guarded by ``try/except ImportError``.

The result is compared with ``pyproject.toml`` (``[project].dependencies`` and the ``dev``
dependency group) and ``uv.lock``. Problems (exit 1 with ``--check``):

* a runtime import whose distribution is not a declared runtime dependency;
* a dev/tooling import declared nowhere;
* a declared dependency missing from ``uv.lock``;
* a declared dependency no code imports, unless ``DECLARED_REASONS`` explains why it is
  kept (GOVERNANCE G2 forbids silently dropping it — the reason is documented instead).

    .venv/bin/python tools/audit/dependencies.py          # write docs/audit/dependencies.{json,md}
    .venv/bin/python tools/audit/dependencies.py --check  # exit 1 on problems or stale report
"""
from __future__ import annotations

import ast
import json
import re
import sys
import textwrap
import tomllib
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Set, Tuple

REPO = Path(__file__).resolve().parents[2]
SCAN_ROOTS = ("agos", "tests", "tools")
OUT_JSON = REPO / "docs" / "audit" / "dependencies.json"
OUT_MD = REPO / "docs" / "audit" / "dependencies.md"

# import name -> distribution name, where they differ.
IMPORT_TO_DIST: Dict[str, str] = {
    "yaml": "pyyaml",
    "memory_profiler": "memory-profiler",
    "pytest_asyncio": "pytest-asyncio",
}

# Declared dependencies that are kept although no real ``import`` uses them (G2: never
# drop silently — say why). Each reason is shown in the report.
DECLARED_REASONS: Dict[str, str] = {
    "requests": ("used by the code the platform generates: the Python SDK/client templates "
                 "in agos-kernel sdk/, laboratory/ and certification/ runtime.py emit "
                 "`import requests`; kept so generated clients run in the same environment"),
    "pytest-asyncio": "pytest plugin, loaded by pytest through `asyncio_mode = \"auto\"` (R-F-009), never imported",
}

SUBPROCESS_FUNCS = {"run", "Popen", "call", "check_call", "check_output"}


def normalise(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def dist_of(import_root: str) -> str:
    return normalise(IMPORT_TO_DIST.get(import_root, import_root))


def _req_name(req: str) -> str:
    return normalise(re.split(r"[\s<>=!~;\[(]", req.strip(), 1)[0])


def declared(repo: Path = REPO) -> Dict[str, Set[str]]:
    data = tomllib.loads((repo / "pyproject.toml").read_text(encoding="utf-8"))
    runtime = {_req_name(r) for r in data.get("project", {}).get("dependencies", [])}
    groups = data.get("dependency-groups", {})
    dev = {_req_name(r) for r in groups.get("dev", []) if isinstance(r, str)}
    build = {_req_name(r) for r in data.get("build-system", {}).get("requires", [])}
    return {"runtime": runtime, "dev": dev, "build": build}


def locked(repo: Path = REPO) -> Dict[str, str]:
    lock = repo / "uv.lock"
    if not lock.exists():
        return {}
    data = tomllib.loads(lock.read_text(encoding="utf-8"))
    return {normalise(p["name"]): str(p.get("version", "")) for p in data.get("package", [])}


def first_party(repo: Path = REPO) -> Set[str]:
    """Import roots provided by the repository itself: the package roots of ``agos/`` and
    the kernel, plus every module/directory name under the scanned roots (tests and tools
    load siblings by path, e.g. ``security_scan``, ``module_map``). A name that is also a
    declared dependency's import name is never treated as local, so a stray local file
    cannot mask a real external package."""
    names = {"agos", "agos_kernel"}
    for base in (repo / "agos", repo / "agos" / "agos-kernel"):
        for child in base.iterdir():
            if child.name.startswith((".", "__")):
                continue
            if child.is_dir():
                names.add(child.name.replace("-", "_"))
            elif child.suffix == ".py":
                names.add(child.stem)
    for path in iter_files(repo):
        names.add(path.stem)
        names.update(part.replace("-", "_") for part in path.relative_to(repo).parts[:-1])
    decl = declared(repo)
    declared_dists = decl["runtime"] | decl["dev"]
    return {n for n in names if dist_of(n) not in declared_dists and n != "__init__"}


def scope_of(rel: Path) -> str:
    parts = rel.parts
    if parts[0] == "tools":
        return "tooling"
    if parts[0] == "tests" or "tests" in parts[1:-1] or rel.name == "conftest.py" \
            or rel.name.startswith("test_"):
        return "dev"
    return "runtime"


def _optional_nodes(tree: ast.AST) -> Set[int]:
    guarded: Set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Try):
            continue
        names: Set[str] = set()
        for h in node.handlers:
            t = h.type
            for e in (t.elts if isinstance(t, ast.Tuple) else [t]):
                if isinstance(e, ast.Name):
                    names.add(e.id)
                elif isinstance(e, ast.Attribute):
                    names.add(e.attr)
        if names & {"ImportError", "ModuleNotFoundError", "Exception", "BaseException"}:
            for stmt in node.body:
                for sub in ast.walk(stmt):
                    if isinstance(sub, (ast.Import, ast.ImportFrom)):
                        guarded.add(id(sub))
    return guarded


def _import_roots(tree: ast.AST) -> Iterator[Tuple[ast.AST, str]]:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                yield node, a.name.split(".")[0]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            yield node, node.module.split(".")[0]


def _template_imports(tree: ast.AST) -> Set[str]:
    roots: Set[str] = set()
    for node in ast.walk(tree):
        text: Optional[str] = None
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            text = node.value
        elif isinstance(node, ast.JoinedStr):
            text = "".join(v.value if isinstance(v, ast.Constant) and isinstance(v.value, str)
                           else "None" for v in node.values)
        if not text or "import" not in text or "\n" not in text:
            continue
        try:
            sub = ast.parse(textwrap.dedent(text))
        except SyntaxError:
            continue
        roots.update(r for _, r in _import_roots(sub))
    return roots


def _system_tools(tree: ast.AST) -> Set[str]:
    tools: Set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        name = f.attr if isinstance(f, ast.Attribute) else f.id if isinstance(f, ast.Name) else ""
        base = f.value.id if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) else ""
        if not node.args:
            continue
        first = node.args[0]
        if base == "shutil" and name == "which" and isinstance(first, ast.Constant):
            tools.add(str(first.value))
        elif base in ("subprocess", "asyncio") and (name in SUBPROCESS_FUNCS or name.startswith("create_subprocess")):
            if isinstance(first, (ast.List, ast.Tuple)) and first.elts and \
                    isinstance(first.elts[0], ast.Constant) and isinstance(first.elts[0].value, str):
                tools.add(first.elts[0].value)
            elif name == "create_subprocess_exec" and isinstance(first, ast.Constant):
                tools.add(str(first.value))
            elif isinstance(first, ast.Constant) and isinstance(first.value, str) and first.value.strip():
                tools.add(first.value.split()[0])
    return {t for t in tools if t and not t.startswith(("-", "/", "{"))}


def iter_files(repo: Path, roots: Iterable[str] = SCAN_ROOTS) -> Iterator[Path]:
    for r in roots:
        for p in sorted((repo / r).rglob("*.py")):
            if "__pycache__" not in p.parts and ".venv" not in p.parts:
                yield p


def scan(repo: Path = REPO, roots: Iterable[str] = SCAN_ROOTS) -> Dict:
    stdlib = set(sys.stdlib_module_names) | {"__future__"}
    fp = first_party(repo)
    uses: Dict[str, Dict[str, Set[str]]] = defaultdict(lambda: defaultdict(set))
    system: Dict[str, Set[str]] = defaultdict(set)
    for path in iter_files(repo, roots):
        rel = path.relative_to(repo)
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        siblings = {p.stem for p in path.parent.glob("*.py")} | \
                   {p.name for p in path.parent.iterdir() if p.is_dir()}
        local = fp | siblings

        def external(root: str) -> bool:
            return root not in stdlib and root not in local

        guarded = _optional_nodes(tree)
        scope = scope_of(rel)
        real: Set[str] = set()
        for node, root in _import_roots(tree):
            if external(root):
                key = "optional" if id(node) in guarded else scope
                uses[root][key].add(str(rel))
                real.add(root)
        # code templates only count in platform code; in tests/tools they are test data
        for root in (_template_imports(tree) - real if scope == "runtime" else ()):
            if external(root):
                uses[root]["generated"].add(str(rel))
        for tool in _system_tools(tree):
            system[tool].add(str(rel))
    return {"uses": uses, "system": system}


def build_report(repo: Path = REPO, roots: Iterable[str] = SCAN_ROOTS) -> Dict:
    found = scan(repo, roots)
    decl = declared(repo)
    lock = locked(repo)
    deps: List[Dict] = []
    problems: List[str] = []
    imported_dists: Set[str] = set()
    for root in sorted(found["uses"]):
        scopes = {k: sorted(v) for k, v in sorted(found["uses"][root].items())}
        dist = dist_of(root)
        where = [k for k in ("runtime", "dev", "build") if dist in decl[k]]
        if set(scopes) - {"generated"}:
            imported_dists.add(dist)
        entry = {"import": root, "distribution": dist, "scopes": scopes, "declared_in": where,
                 "locked_version": lock.get(dist)}
        deps.append(entry)
        if "runtime" in scopes and "runtime" not in where:
            problems.append(f"runtime import `{root}` ({dist}) is not in [project].dependencies")
        for s in ("dev", "tooling"):
            if s in scopes and not where:
                problems.append(f"{s} import `{root}` ({dist}) is declared nowhere")
    declared_rows: List[Dict] = []
    for kind in ("runtime", "dev"):
        for dist in sorted(decl[kind]):
            reason = DECLARED_REASONS.get(dist, "")
            used = dist in imported_dists
            declared_rows.append({"distribution": dist, "group": kind, "imported": used,
                                  "locked_version": lock.get(dist), "reason_if_not_imported": reason})
            if lock and dist not in lock:
                problems.append(f"declared `{dist}` is missing from uv.lock")
            if not used and not reason:
                problems.append(f"declared `{dist}` is imported nowhere and has no documented reason")
    return {
        "generated_by": "tools/audit/dependencies.py",
        "scanned_roots": list(roots),
        "files_scanned": sum(1 for _ in iter_files(repo, roots)),
        "external_imports": deps,
        "declared": declared_rows,
        "system_tools": {k: sorted(v) for k, v in sorted(found["system"].items())},
        "problems": problems,
    }


def render_md(rep: Dict) -> str:
    out = ["# تدقيق التبعيات الخارجية (R-F-011)", "",
           "> مُولَّد بـ`tools/audit/dependencies.py`، فلا يُحرَّر يدوياً. `--check` يُفشل CI إن تقادم التقرير أو ظهرت مشكلة.", "",
           f"الملفات المفحوصة: **{rep['files_scanned']}** (`agos/` و`tests/` و`tools/`) · المشاكل: **{len(rep['problems'])}**", "",
           "## الاستيرادات الخارجية الفعلية", "",
           "| الاستيراد | التوزيعة | النطاقات (عدد الملفات) | مُعلن في | الإصدار المقفل |",
           "|---|---|---|---|---|"]
    for d in rep["external_imports"]:
        scopes = "، ".join(f"{k} ({len(v)})" for k, v in d["scopes"].items())
        out.append(f"| `{d['import']}` | `{d['distribution']}` | {scopes} | {', '.join(d['declared_in']) or '—'} | {d['locked_version'] or '—'} |")
    out += ["", "## التبعيات المعلنة", "", "| التوزيعة | المجموعة | مستورَدة | الإصدار المقفل | سبب الإبقاء إن لم تُستورد |", "|---|---|---|---|---|"]
    for d in rep["declared"]:
        out.append(f"| `{d['distribution']}` | {d['group']} | {'نعم' if d['imported'] else 'لا'} | {d['locked_version'] or '—'} | {d['reason_if_not_imported'] or '—'} |")
    out += ["", "## أدوات النظام المستدعاة (ليست حزم بايثون)", "", "| الأداة | الملفات |", "|---|---|"]
    for tool, files in rep["system_tools"].items():
        out.append(f"| `{tool}` | {len(files)}: " + ", ".join(f"`{f}`" for f in files[:4]) + (" …" if len(files) > 4 else "") + " |")
    out += ["", "## المشاكل", ""]
    out += [f"- {p}" for p in rep["problems"]] or ["لا توجد."]
    return "\n".join(out) + "\n"


def main() -> int:
    rep = build_report()
    js = json.dumps(rep, indent=2, ensure_ascii=False) + "\n"
    md = render_md(rep)
    if "--check" in sys.argv:
        stale = [p.relative_to(REPO) for p, c in ((OUT_JSON, js), (OUT_MD, md))
                 if not p.exists() or p.read_text(encoding="utf-8") != c]
        for s in stale:
            print(f"stale: {s} — run tools/audit/dependencies.py")
        for p in rep["problems"]:
            print("problem:", p)
        if stale or rep["problems"]:
            return 1
        print(f"dependencies OK: {len(rep['external_imports'])} external imports, 0 problems")
        return 0
    OUT_JSON.write_text(js, encoding="utf-8")
    OUT_MD.write_text(md, encoding="utf-8")
    print(f"wrote {OUT_JSON.relative_to(REPO)} and {OUT_MD.relative_to(REPO)}; problems: {len(rep['problems'])}")
    for p in rep["problems"]:
        print("problem:", p)
    return 1 if rep["problems"] else 0


if __name__ == "__main__":
    sys.exit(main())
