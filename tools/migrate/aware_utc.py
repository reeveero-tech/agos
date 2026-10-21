#!/usr/bin/env python3
"""R-F-012 — replace the deprecated naive ``datetime.utcnow()`` with aware UTC time.

``datetime.utcnow()`` is deprecated since Python 3.12 and returns a *naive* datetime
that silently means "UTC". Calling ``.timestamp()`` on it interprets it as **local** time,
so on any host whose zone is not UTC every epoch derived from it is wrong (Asia/Riyadh:
off by 10 800 s). The replacement keeps the same instant but makes the zone explicit:

    datetime.utcnow()                      ->  datetime.now(timezone.utc)
    field(default_factory=datetime.utcnow) ->  field(default_factory=lambda: datetime.now(timezone.utc))
    any other bare ``datetime.utcnow``     ->  (lambda: datetime.now(timezone.utc))
    from datetime import datetime[, …]     ->  from datetime import datetime[, …], timezone

Only code is rewritten (AST positions, f-string expressions included); comments and
string literals that merely mention ``utcnow`` are left untouched. Idempotent.

    python tools/migrate/aware_utc.py           # rewrite agos/, tests/, tools/
    python tools/migrate/aware_utc.py --check   # exit 1 if any call site remains
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple

REPO = Path(__file__).resolve().parents[2]
ROOTS = ("agos", "tests", "tools")
NEW_CALL = "datetime.now(timezone.utc)"
SELF = Path(__file__).resolve()


def iter_files(repo: Path = REPO) -> Iterator[Path]:
    for root in ROOTS:
        for p in sorted((repo / root).rglob("*.py")):
            if "__pycache__" not in p.parts and p.resolve() != SELF:
                yield p


def _is_utcnow(node: ast.AST) -> bool:
    return (isinstance(node, ast.Attribute) and node.attr == "utcnow"
            and isinstance(node.value, ast.Name) and node.value.id == "datetime")


def _offsets(text: str) -> List[int]:
    """Character offset of the start of each (1-based) line."""
    starts, pos = [0, 0], 0
    for line in text.splitlines(keepends=True):
        pos += len(line)
        starts.append(pos)
    return starts


def _char(text_lines: List[str], starts: List[int], lineno: int, col_bytes: int) -> int:
    """AST col offsets are UTF-8 byte offsets; convert to a character index in ``text``."""
    line = text_lines[lineno - 1]
    return starts[lineno] + len(line.encode("utf-8")[:col_bytes].decode("utf-8", errors="ignore"))


def plan(text: str) -> Tuple[List[Tuple[int, int, str]], int]:
    """Edits (start, end, replacement) for one module, and the number of call sites."""
    tree = ast.parse(text)
    parents: Dict[int, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[id(child)] = node
    lines = text.splitlines(keepends=True)
    starts = _offsets(text)
    pos = lambda lineno, col: _char(lines, starts, lineno, col)  # noqa: E731
    edits: List[Tuple[int, int, str]] = []
    sites = 0
    for node in ast.walk(tree):
        if not _is_utcnow(node):
            continue
        sites += 1
        parent = parents.get(id(node))
        if isinstance(parent, ast.Call) and parent.func is node and not parent.args and not parent.keywords:
            edits.append((pos(parent.lineno, parent.col_offset),
                          pos(parent.end_lineno, parent.end_col_offset), NEW_CALL))
        else:
            repl = f"lambda: {NEW_CALL}" if isinstance(parent, ast.keyword) else f"(lambda: {NEW_CALL})"
            edits.append((pos(node.lineno, node.col_offset),
                          pos(node.end_lineno, node.end_col_offset), repl))
    if sites:
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "datetime" and node.level == 0:
                names = {a.asname or a.name for a in node.names}
                if "datetime" in names and "timezone" not in names:
                    last = node.names[-1]
                    end = pos(last.end_lineno, last.end_col_offset)
                    edits.append((end, end, ", timezone"))
    return sorted(edits, reverse=True), sites


def rewrite(text: str) -> Tuple[str, int]:
    edits, sites = plan(text)
    for start, end, repl in edits:
        text = text[:start] + repl + text[end:]
    return text, sites


def remaining(repo: Path = REPO) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for p in iter_files(repo):
        try:
            tree = ast.parse(p.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        n = sum(1 for node in ast.walk(tree) if _is_utcnow(node))
        if n:
            out[str(p.relative_to(repo))] = n
    return out


def main(argv: Optional[List[str]] = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if "--check" in argv:
        left = remaining()
        for f, n in left.items():
            print(f"utcnow left: {f} ({n})")
        print(f"{sum(left.values())} datetime.utcnow call sites remain")
        return 1 if left else 0
    files = sites = 0
    for p in iter_files():
        text = p.read_text(encoding="utf-8")
        try:
            new, n = rewrite(text)
        except SyntaxError:
            continue
        if n:
            compile(new, str(p), "exec")  # never write a module that no longer parses
            p.write_text(new, encoding="utf-8")
            files, sites = files + 1, sites + n
    print(f"rewrote {sites} datetime.utcnow call sites in {files} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
