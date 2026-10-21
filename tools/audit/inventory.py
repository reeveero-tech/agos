#!/usr/bin/env python3
"""AGOS project inventory & health audit.

Scans every Python file in the repository and produces a machine-readable
(JSON) and human-readable (Markdown) inventory used by ROADMAP.md and
PROJECT_STATE.md.  It is the single source of truth for questions such as
"is this file connected to anything?", "does it import?", "is it a stub?".

Usage:
    python tools/audit/inventory.py            # writes docs/audit/inventory.{json,md}
    python tools/audit/inventory.py --no-import  # skip slow import probing

The tool never modifies source files.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SRC = REPO / "agos"
KERNEL = SRC / "agos-kernel"
OUT_DIR = REPO / "docs" / "audit"
HARDCODED = re.compile(r"/home/runner/|/workspace/All-hand")
SKIP_DIRS = {"__pycache__", ".git", ".venv"}


def iter_py():
    for dirpath, dirnames, filenames in os.walk(SRC):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if fn.endswith(".py"):
                yield Path(dirpath) / fn


def root_for(path: Path) -> Path:
    """The sys.path root a file is written against."""
    return KERNEL if KERNEL in path.parents else SRC


def module_name(path: Path) -> str:
    rel = path.relative_to(root_for(path)).with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def alias_module_name(path: Path) -> str | None:
    """R-F-004: importable name of a file inside a hyphenated dir that has an alias package.

    ``agos-kernel/event-engine/__init__.py`` -> ``event_engine`` when
    ``agos-kernel/event_engine/__init__.py`` declares ``__agos_alias_of__ = "event-engine"``.
    """
    root = root_for(path)
    rel = path.relative_to(root).with_suffix("")
    parts = list(rel.parts)
    if "-" not in parts[0] or any("-" in p for p in parts[1:]):
        return None
    alias = parts[0].replace("-", "_")
    init = root / alias / "__init__.py"
    if not init.is_file() or f'__agos_alias_of__ = "{parts[0]}"' not in init.read_text(encoding="utf-8"):
        return None
    parts[0] = alias
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def is_stub(fn: ast.AST) -> bool:
    """A function whose body does nothing meaningful."""
    body = list(fn.body)
    if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant) \
            and isinstance(body[0].value.value, str):
        body = body[1:]  # strip docstring
    if not body:
        return True
    if len(body) != 1:
        return False
    stmt = body[0]
    if isinstance(stmt, ast.Pass):
        return True
    if isinstance(stmt, ast.Raise) and "NotImplementedError" in ast.unparse(stmt):
        return True
    if isinstance(stmt, ast.Return):
        v = stmt.value
        if v is None or isinstance(v, ast.Constant):
            return True
        if isinstance(v, (ast.List, ast.Dict, ast.Tuple)) and all(
            isinstance(e, ast.Constant) or e is None
            for e in (list(getattr(v, "elts", [])) + list(getattr(v, "keys", [])) + list(getattr(v, "values", [])))
        ):
            return True
    return False


def is_abstract(fn: ast.AST) -> bool:
    return any("abstractmethod" in ast.unparse(d) for d in fn.decorator_list)


def analyse(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="ignore")
    info = {
        "path": str(path.relative_to(REPO)),
        "module": module_name(path),
        "root": "kernel" if root_for(path) == KERNEL else "src",
        "lines": text.count("\n") + 1,
        "syntax_ok": True,
        "classes": 0,
        "functions": 0,
        "stub_functions": 0,
        "abstract_functions": 0,
        "imports": [],
        "hardcoded_paths": len(HARDCODED.findall(text)),
        "importable_package_path": "-" not in str(path.relative_to(root_for(path))),
    }
    alias = alias_module_name(path)
    if alias:
        info["module"], info["alias_of"], info["importable_package_path"] = alias, info["module"], True
    try:
        tree = ast.parse(text)
    except SyntaxError as e:
        info["syntax_ok"] = False
        info["syntax_error"] = f"{e.msg} (line {e.lineno})"
        return info
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            info["classes"] += 1
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            info["functions"] += 1
            if is_abstract(node):
                info["abstract_functions"] += 1
            elif is_stub(node) and node.name not in {"__init__", "__post_init__"}:
                info["stub_functions"] += 1
        elif isinstance(node, ast.Import):
            info["imports"] += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = info["module"].split(".")
                if not path.name == "__init__.py":
                    base = base[:-1]
                base = base[: len(base) - (node.level - 1)] if node.level > 1 else base
                mod = ".".join(base + ([node.module] if node.module else []))
            else:
                mod = node.module or ""
            info["imports"].append(mod)
    return info


PROBE = r"""
import sys, importlib, signal
sys.path.insert(0, sys.argv[1])
signal.alarm(int(sys.argv[3]))
try:
    importlib.import_module(sys.argv[2])
    print("OK")
except BaseException as e:
    print("ERR " + type(e).__name__ + ": " + str(e).splitlines()[0][:200] if str(e) else "ERR " + type(e).__name__)
"""


def probe_import(info: dict, python: str, timeout: int = 15) -> str:
    root = KERNEL if info["root"] == "kernel" else SRC
    if not info["importable_package_path"]:
        return "ERR NotAPackagePath: directory name contains '-'"
    if not info["module"]:
        return "SKIP"
    try:
        r = subprocess.run([python, "-c", PROBE, str(root), info["module"], str(timeout)],
                           capture_output=True, text=True, timeout=timeout + 5, cwd=str(root))
        out = (r.stdout.strip().splitlines() or [""])[-1]
        if not out:
            err = (r.stderr.strip().splitlines() or ["no output"])[-1]
            return ("ERR " + err[:200]).replace(str(REPO), "<repo>")
        return out.replace(str(REPO), "<repo>")
    except subprocess.TimeoutExpired:
        return "ERR Timeout"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-import", action="store_true")
    ap.add_argument("--python", default=sys.executable)
    args = ap.parse_args()

    files = sorted(iter_py())
    infos = [analyse(p) for p in files]
    for i in infos:
        i["id"] = ("K:" if i["root"] == "kernel" else "S:") + i["module"]
    by_id = {i["id"]: i for i in infos}

    def resolve(i: dict, imp: str):
        """Resolve an import string to a module id, preferring the importer's own root."""
        if imp.startswith("agos_kernel."):
            candidates = ["K:" + imp[len("agos_kernel."):]]
        elif imp.startswith("agos.kernel."):
            candidates = ["K:" + imp[len("agos.kernel."):]]
        elif imp.startswith("agos."):
            candidates = ["S:" + imp[len("agos."):]]
        else:
            own = "K:" if i["root"] == "kernel" else "S:"
            other = "S:" if own == "K:" else "K:"
            top = i["module"].split(".")[0]
            candidates = []
            if own == "S:" and top:
                candidates.append("S:" + top + "." + imp)  # package-local absolute imports (e.g. rie)
            candidates += [own + imp, other + imp]
        for c in candidates:
            parts = c.split(".")
            for k in range(len(parts), 0, -1):
                cand = ".".join(parts[:k])
                if cand in by_id and cand != i["id"]:
                    return cand
        return None

    importers = defaultdict(set)
    for i in infos:
        i["resolved_imports"] = sorted({r for r in (resolve(i, imp) for imp in i["imports"]) if r})
        for r in i["resolved_imports"]:
            importers[r].add(i["id"])
    for i in infos:
        i["imported_by"] = sorted(importers.get(i["id"], []))

    if not args.no_import:
        for n, i in enumerate(infos, 1):
            i["import_status"] = probe_import(i, args.python)
            if n % 50 == 0:
                print(f"  probed {n}/{len(infos)}", file=sys.stderr)

    # package level aggregation
    pkgs = defaultdict(lambda: defaultdict(int))
    for i in infos:
        rel = Path(i["path"]).relative_to("agos")
        key = "/".join(rel.parts[:2]) if rel.parts[0] == "agos-kernel" and len(rel.parts) > 2 else rel.parts[0]
        p = pkgs[key]
        p["files"] += 1
        p["lines"] += i["lines"]
        p["functions"] += i["functions"]
        p["stub_functions"] += i["stub_functions"]
        p["hardcoded_paths"] += i["hardcoded_paths"]
        p["syntax_errors"] += 0 if i["syntax_ok"] else 1
        p["not_imported_by_others"] += 0 if i["imported_by"] else 1
        if "import_status" in i:
            p["import_ok"] += 1 if i["import_status"] == "OK" else 0
            p["import_fail"] += 0 if i["import_status"] in ("OK", "SKIP") else 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    totals = defaultdict(int)
    for p in pkgs.values():
        for k, v in p.items():
            totals[k] += v
    (OUT_DIR / "inventory.json").write_text(json.dumps(
        {"totals": totals, "packages": pkgs, "files": infos}, indent=1, ensure_ascii=False, default=dict))

    md = ["# AGOS — Automated Inventory",
          "",
          "> Generated by `tools/audit/inventory.py`. Do not edit by hand — regenerate.",
          "",
          "## Totals", ""]
    for k, v in sorted(totals.items()):
        md.append(f"- **{k}**: {v}")
    md += ["", "## Packages", "",
           "| package | files | lines | functions | stub fns | hardcoded paths | import ok | import fail | orphan files |",
           "|---|---|---|---|---|---|---|---|---|"]
    for k in sorted(pkgs):
        p = pkgs[k]
        md.append(f"| `{k}` | {p['files']} | {p['lines']} | {p['functions']} | {p['stub_functions']} | "
                  f"{p['hardcoded_paths']} | {p.get('import_ok', '-')} | {p.get('import_fail', '-')} | "
                  f"{p['not_imported_by_others']} |")
    fails = [i for i in infos if i.get("import_status", "OK") not in ("OK", "SKIP")]
    md += ["", f"## Import failures ({len(fails)})", ""]
    reasons = defaultdict(list)
    for i in fails:
        reasons[i["import_status"].split(":")[0]].append(i)
    for r, items in sorted(reasons.items(), key=lambda x: -len(x[1])):
        md.append(f"### {r} — {len(items)}")
        md.append("")
        for i in items:
            md.append(f"- `{i['path']}` — {i['import_status']}")
        md.append("")
    syn = [i for i in infos if not i["syntax_ok"]]
    md += [f"## Syntax errors ({len(syn)})", ""] + [f"- `{i['path']}` — {i['syntax_error']}" for i in syn]
    (OUT_DIR / "inventory.md").write_text("\n".join(md) + "\n")
    print(json.dumps(totals))


if __name__ == "__main__":
    main()
