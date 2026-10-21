#!/usr/bin/env python3
"""R-F-002 — rewrite hardcoded '/home/runner/workspace/agos' paths into portable ones.

Each rewritten module gets a small header (after its docstring / __future__ imports):

    _AGOS_ROOT  = AGOS_ROOT env var  or  <the agos/ directory computed from __file__>
    _AGOS_KERNEL = _AGOS_ROOT / "agos-kernel"

and every string literal that contained the old absolute path is rewritten to use
those values. Comments are updated to the placeholder <AGOS_ROOT>. Idempotent.
Usage: python tools/migrate/portable_paths.py [--check]
"""
from __future__ import annotations

import ast
import io
import sys
import tokenize
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
AGOS = REPO / "agos"
OLD_K = "/home/runner/workspace/agos/agos-kernel"
OLD_R = "/home/runner/workspace/agos"
MARK = "# R-F-002 portable paths"


def header(depth: int) -> str:
    return (
        f"{MARK} (see tools/migrate/portable_paths.py)\n"
        "import os as _agos_os\n"
        "from pathlib import Path as _AgosPath\n"
        f"_AGOS_ROOT = _AgosPath(_agos_os.environ.get('AGOS_ROOT') or _AgosPath(__file__).resolve().parents[{depth}])\n"
        "_AGOS_KERNEL = _AGOS_ROOT / 'agos-kernel'\n"
    )


def path_expr(path: str) -> str:
    """Python expression (str) equivalent to an old absolute path."""
    for old, var in ((OLD_K, "_AGOS_KERNEL"), (OLD_R, "_AGOS_ROOT")):
        if path == old or path.startswith(old + "/"):
            rest = path[len(old):].strip("/")
            trail = "/" if path.endswith("/") and rest else ""
            if not rest:
                return f"str({var})"
            e = f"str({var} / {rest!r})"
            return e + (" + '/'" if trail else "")
    raise ValueError(path)


def rewrite_string(tok: str) -> str | None:
    if OLD_R not in tok:
        return None
    i = 0
    while tok[i].isalpha():
        i += 1
    prefix, body = tok[:i], tok[i:]
    if "f" in prefix.lower() or "b" in prefix.lower():
        raise ValueError(f"unsupported literal: {tok[:60]}")
    q = body[:3] if body[:3] in ('"""', "'''") else body[0]
    inner = body[len(q):-len(q)]
    # whole literal is a path
    if inner.startswith(OLD_R) and all(c not in inner for c in " ;\"'()"):
        return path_expr(inner)
    # embedded: split around each occurrence of a path
    parts, pos = [], 0
    while True:
        j = inner.find(OLD_R, pos)
        if j < 0:
            break
        k = j
        while k < len(inner) and inner[k] not in " ;\"'(),":
            k += 1
        parts.append(f"{prefix}{q}{inner[pos:j]}{q}")
        parts.append(path_expr(inner[j:k]))
        pos = k
    parts.append(f"{prefix}{q}{inner[pos:]}{q}")
    return "(" + " + ".join(p for p in parts if p not in (f"{prefix}{q}{q}",)) + ")"


def insertion_line(src: str) -> int:
    tree = ast.parse(src)
    line = 0
    for i, node in enumerate(tree.body):
        if i == 0 and isinstance(node, ast.Expr) and isinstance(getattr(node, "value", None), ast.Constant) \
                and isinstance(node.value.value, str):
            line = node.end_lineno
        elif isinstance(node, ast.ImportFrom) and node.module == "__future__":
            line = node.end_lineno
        else:
            break
    return line


def process(p: Path) -> bool:
    src = p.read_text(encoding="utf-8")
    if OLD_R not in src:
        return False
    lines = src.splitlines(keepends=True)
    offs = [0]
    for ln in lines:
        offs.append(offs[-1] + len(ln))
    edits = []
    for t in tokenize.generate_tokens(io.StringIO(src).readline):
        new = None
        if t.type == tokenize.STRING:
            new = rewrite_string(t.string)
        elif t.type == tokenize.COMMENT and OLD_R in t.string:
            new = t.string.replace(OLD_K, "<AGOS_ROOT>/agos-kernel").replace(OLD_R, "<AGOS_ROOT>")
        if new is not None:
            a = offs[t.start[0] - 1] + t.start[1]
            b = offs[t.end[0] - 1] + t.end[1]
            edits.append((a, b, new))
    for a, b, new in sorted(edits, reverse=True):
        src = src[:a] + new + src[b:]
    if MARK not in src:
        depth = len(p.relative_to(AGOS).parts) - 1
        ins = insertion_line(src)
        ls = src.splitlines(keepends=True)
        if ins and not ls[ins - 1].endswith("\n"):
            ls[ins - 1] += "\n"
        ls.insert(ins, header(depth))
        src = "".join(ls)
    ast.parse(src)  # must remain valid
    p.write_text(src, encoding="utf-8")
    return True


def main() -> int:
    check = "--check" in sys.argv
    files = [p for p in AGOS.rglob("*.py") if ".venv" not in p.parts]
    hits = [p for p in files if OLD_R in p.read_text(encoding="utf-8", errors="replace")]
    if check:
        for p in hits:
            print(p.relative_to(REPO))
        return 1 if hits else 0
    n = sum(process(p) for p in hits)
    print(f"rewrote {n} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
