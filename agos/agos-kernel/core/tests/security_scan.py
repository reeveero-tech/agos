"""AST-based source scanners for the kernel golden tests (R-Q-009).

The golden security/compatibility tests used to match raw text (``'eval(' in line``,
case-insensitive ``f".*SELECT.*{"``, ``line.startswith('import ')`` against a 22-name
"stdlib" list…). That was simultaneously too loose and too weak:

* false positives — the word "Selected" was "SQL", ``inspect``/``io``/``subprocess`` were
  "third-party", the test's own pattern strings were "eval usage", vulnerable sample code
  held *as data* by the security-scan skill was a "hardcoded secret";
* false negatives — ``eval (x)``, ``from requests import get``, a secret in a dict literal
  (``{"password": "…"}``), SQL built with ``%``/``.format``/``+`` were all invisible.

These scanners inspect the syntax tree instead, so they see what the code *does*.
``tests/test_security_scanners.py`` holds canaries proving each scanner still catches
the real pattern (and every pattern the old text test caught as real code).
"""
from __future__ import annotations

import ast
import re
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Set, Tuple

__all__ = [
    "Finding", "iter_sources", "find_dynamic_code_calls", "find_hardcoded_secrets",
    "find_sql_string_building", "find_unsafe_dynamic_imports", "find_undeclared_imports",
    "allowed_import_roots",
]


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    detail: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: {self.detail}"


def iter_sources(root: Path) -> Iterator[Tuple[Path, ast.AST]]:
    """Every parseable ``*.py`` under ``root`` (``__pycache__`` excluded)."""
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        try:
            yield path, ast.parse(path.read_text(encoding="utf-8"), str(path))
        except SyntaxError:
            continue  # syntax health is measured by tools/audit/inventory.py


def _call_name(func: ast.AST) -> Optional[str]:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        base = _call_name(func.value)
        return f"{base}.{func.attr}" if base else func.attr
    return None


# --------------------------------------------------------------------------- eval / exec
def find_dynamic_code_calls(path: Path, tree: ast.AST, names: Iterable[str]) -> List[Finding]:
    """Calls to the builtins in ``names`` (e.g. ``eval``), also via ``builtins.X`` or
    ``getattr(builtins, "X")``."""
    wanted = set(names)
    found: List[Finding] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _call_name(node.func)
        if name in wanted or (name and name.startswith(("builtins.", "__builtins__."))
                              and name.split(".", 1)[1] in wanted):
            found.append(Finding(str(path), node.lineno, f"calls {name}()"))
        elif (isinstance(node.func, ast.Call) and _call_name(node.func.func) == "getattr"
              and len(node.func.args) >= 2 and isinstance(node.func.args[1], ast.Constant)
              and node.func.args[1].value in wanted):
            found.append(Finding(str(path), node.lineno, f"calls getattr(..., {node.func.args[1].value!r})()"))
    return found


# --------------------------------------------------------------------------- secrets
SECRET_NAME = re.compile(r"(?:^|_)(password|passwd|pwd|api_?key|secret|secret_key|token|"
                         r"access_token|auth_token|private_key|access_key|client_secret)$", re.I)
PLACEHOLDER = re.compile(r"^(?:test|dummy|fake|mock|sample|example|placeholder|changeme|xxx+|"
                         r"your[_-]|<|\$\{|\{)", re.I)
PLACEHOLDER_WORDS = ("example", "placeholder", "your_", "changeme")  # the original exemptions


def _is_secret_value(name: str, value: object) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    low = value.lower()
    if PLACEHOLDER.match(value) or any(w in low for w in PLACEHOLDER_WORDS):
        return False
    # enum/field labels such as ``API_KEY = "api_key"`` name a credential, they are not one
    if low.replace("-", "_") == name.lower() or low.replace("-", "_") == name.lower().split(".")[-1]:
        return False
    return True


def find_hardcoded_secrets(path: Path, tree: ast.AST) -> List[Finding]:
    """String literals bound to credential-like names: assignments, annotated assignments,
    attribute assignments, keyword arguments and dict-literal entries."""
    found: List[Finding] = []

    def check(name: Optional[str], value: ast.AST, line: int) -> None:
        if name and SECRET_NAME.search(name) and isinstance(value, ast.Constant) \
                and _is_secret_value(name, value.value):
            found.append(Finding(str(path), line, f"{name} = {str(value.value)[:12]!r}…"))

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                check(target.id if isinstance(target, ast.Name) else
                      target.attr if isinstance(target, ast.Attribute) else None, node.value, node.lineno)
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            target = node.target
            check(target.id if isinstance(target, ast.Name) else
                  target.attr if isinstance(target, ast.Attribute) else None, node.value, node.lineno)
        elif isinstance(node, ast.keyword) and node.arg:
            check(node.arg, node.value, getattr(node.value, "lineno", 0))
        elif isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    check(key.value, value, getattr(value, "lineno", 0))
    return found


# --------------------------------------------------------------------------- SQL
SQL = re.compile(r"\bSELECT\b[\s\S]*\bFROM\b|\bINSERT\s+INTO\b|\bUPDATE\s+\w+\s+SET\b|"
                 r"\bDELETE\s+FROM\b|\bDROP\s+TABLE\b", re.I)


def _literal_text(node: ast.AST) -> Optional[str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(v.value if isinstance(v, ast.Constant) else "{}" for v in node.values)
    return None


def find_sql_string_building(path: Path, tree: ast.AST) -> List[Finding]:
    """SQL statements assembled from runtime values: f-strings with interpolations,
    ``"…" % x``, ``"…".format(x)`` and ``"…" + x``."""
    found: List[Finding] = []
    for node in ast.walk(tree):
        text, how = None, None
        if isinstance(node, ast.JoinedStr) and any(isinstance(v, ast.FormattedValue) for v in node.values):
            text, how = _literal_text(node), "f-string"
        elif isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Mod, ast.Add)):
            text = _literal_text(node.left) or _literal_text(node.right)
            how = "% formatting" if isinstance(node.op, ast.Mod) else "concatenation"
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "format":
            text, how = _literal_text(node.func.value), ".format()"
        if text and SQL.search(text):
            found.append(Finding(str(path), node.lineno, f"SQL built by {how}: {text[:40]!r}"))
    return found


# --------------------------------------------------------------------------- dynamic imports
_IMPORTERS = {"__import__", "importlib.import_module", "import_module", "importlib.__import__"}


def _bindings(scope: ast.AST) -> Dict[str, List[ast.AST]]:
    """name -> expressions bound to it in ``scope`` (assignments; ``for`` targets are
    recorded as ``Starred(iterable)`` meaning "an element of")."""
    out: Dict[str, List[ast.AST]] = {}
    for node in ast.walk(scope):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    out.setdefault(target.id, []).append(node.value)
        elif isinstance(node, (ast.For, ast.AsyncFor)) and isinstance(node.target, ast.Name):
            out.setdefault(node.target.id, []).append(ast.Starred(value=node.iter))
    return out


def _confined(expr: ast.AST, bindings: Dict[str, List[ast.AST]], depth: int = 0) -> bool:
    """True when the module name is fixed in the source or confined to a fixed package:
    a string literal, an f-string with a literal ``"package."`` prefix, an element of a
    literal collection, or a local name bound only to such values."""
    if depth > 6:
        return False
    if isinstance(expr, ast.Constant):
        return isinstance(expr.value, str)
    if isinstance(expr, ast.JoinedStr):
        head = expr.values[0] if expr.values else None
        return (isinstance(head, ast.Constant) and isinstance(head.value, str)
                and len(head.value) > 1 and head.value.endswith("."))
    if isinstance(expr, ast.Starred):  # an element of an iterable
        coll = expr.value
        if isinstance(coll, (ast.List, ast.Tuple, ast.Set)):
            return all(_confined(e, bindings, depth + 1) for e in coll.elts)
        if isinstance(coll, ast.Name) and bindings.get(coll.id):
            return all(isinstance(v, (ast.List, ast.Tuple, ast.Set))
                       and all(_confined(e, bindings, depth + 1) for e in v.elts)
                       for v in bindings[coll.id])
        return False
    if isinstance(expr, ast.Name):
        values = bindings.get(expr.id)
        return bool(values) and all(_confined(v, bindings, depth + 1) for v in values)
    return False


def find_unsafe_dynamic_imports(path: Path, tree: ast.AST) -> List[Finding]:
    """``__import__``/``importlib.import_module`` whose module name is not fixed or
    confined in the source (i.e. could be steered by runtime data). Names are resolved
    in the innermost enclosing function, falling back to module level."""
    module_bindings = _bindings(tree)
    found: List[Finding] = []

    def visit(node: ast.AST, bindings: Dict[str, List[ast.AST]]) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                local = {**bindings, **_bindings(child)}
                visit(child, local)
                continue
            if isinstance(child, ast.Call) and _call_name(child.func) in _IMPORTERS:
                arg = child.args[0] if child.args else None
                if arg is None or not _confined(arg, bindings):
                    found.append(Finding(str(path), child.lineno,
                                         f"{_call_name(child.func)}() with a runtime module name"))
            visit(child, bindings)

    visit(tree, module_bindings)
    return found


# --------------------------------------------------------------------------- dependencies
IMPORT_TO_DIST = {"yaml": "pyyaml", "memory_profiler": "memory-profiler", "pytest_asyncio": "pytest-asyncio"}


def _normalise(req: str) -> str:
    return re.split(r"[\s;\[<>=!~]", req.strip(), maxsplit=1)[0].lower()


def allowed_import_roots(repo: Path) -> Set[str]:
    """stdlib ∪ first-party names (``agos/…``) ∪ dependencies declared in pyproject."""
    allowed: Set[str] = set(sys.stdlib_module_names) | {"agos", "agos_kernel", "__future__"}
    for p in (repo / "agos").rglob("*"):
        if "__pycache__" in p.parts:
            continue
        allowed.add(p.stem if p.suffix == ".py" else p.name)
        allowed.add(p.name.replace("-", "_"))
    data = tomllib.loads((repo / "pyproject.toml").read_text(encoding="utf-8"))
    declared = {_normalise(r) for r in data["project"].get("dependencies", [])}
    declared |= {_normalise(r) for group in data.get("dependency-groups", {}).values()
                 for r in group if isinstance(r, str)}
    dist_to_import = {v: k for k, v in IMPORT_TO_DIST.items()}
    allowed |= {dist_to_import.get(d, d.replace("-", "_")) for d in declared}
    return allowed


def _optional_import_nodes(tree: ast.AST) -> Set[int]:
    """Imports guarded by ``try: … except ImportError/ModuleNotFoundError``."""
    guarded: Set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Try) and any(
                _call_name(h.type) in {"ImportError", "ModuleNotFoundError", "Exception"}
                or (isinstance(h.type, ast.Tuple) and any(_call_name(e) in {"ImportError", "ModuleNotFoundError"}
                                                         for e in h.type.elts))
                for h in node.handlers if h.type is not None):
            for stmt in node.body:
                for inner in ast.walk(stmt):
                    if isinstance(inner, (ast.Import, ast.ImportFrom)):
                        guarded.add(id(inner))
    return guarded


def find_undeclared_imports(path: Path, tree: ast.AST, allowed: Set[str]) -> List[Finding]:
    """``import x`` / ``from x import y`` of a root that is neither stdlib, first-party
    nor declared — unless guarded as optional (``try/except ImportError``)."""
    optional = _optional_import_nodes(tree)
    found: List[Finding] = []
    for node in ast.walk(tree):
        roots: List[str] = []
        if isinstance(node, ast.Import):
            roots = [a.name.split(".")[0] for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots = [node.module.split(".")[0]]
        for root in roots:
            if root not in allowed and id(node) not in optional:
                found.append(Finding(str(path), node.lineno, f"imports undeclared {root!r}"))
    return found
