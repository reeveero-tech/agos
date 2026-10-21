#!/usr/bin/env python3
"""AGOS governance gate — enforces the two supreme rules of GOVERNANCE.md.

RULE G1 (Atomic Documented Change):
    Every commit that changes anything MUST, in the same commit:
      * reference a roadmap item id in its message, e.g. ``[R-F-003]``,
        and that id must exist in ROADMAP.md;
      * modify ROADMAP.md      (item status / notes updated)
      * modify PROJECT_STATE.md (current state + "next step" updated)
      * modify CHANGELOG.md    (entry describing what was done)
      * add or modify a worklog file under docs/worklog/

RULE G2 (No Deletion):
    No commit may
      * delete a file              (git status D)
      * rename / move a file       (git status R — a move is a deletion of the old path)
      * remove a public top-level function/class or a public method
        from any Python module (improve it, wrap it or deprecate it instead).

Modes:
    check_commit.py --staged [--msg-file F]   # used by git hooks
    check_commit.py --range BASE..HEAD        # used by CI (checks every commit)
    check_commit.py --commit SHA

Exit code 0 = compliant, 1 = violation (details printed in Arabic + English).
"""
from __future__ import annotations

import argparse
import ast
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
REQUIRED_DOCS = ["ROADMAP.md", "PROJECT_STATE.md", "CHANGELOG.md"]
WORKLOG_PREFIX = "docs/worklog/"
ID_RE = re.compile(r"\[(R-[A-Z0-9]+-\d{3})\]")
EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"


def git(*args: str, check: bool = True) -> str:
    r = subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {r.stderr.strip()}")
    return r.stdout


def public_symbols(source: str) -> set[str]:
    """Public top-level defs/classes and public methods (Class.method)."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()
    out: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and not node.name.startswith("_"):
            out.add(node.name)
            if isinstance(node, ast.ClassDef):
                for sub in node.body:
                    if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)) and (
                        not sub.name.startswith("_") or (sub.name.startswith("__") and sub.name.endswith("__"))
                    ):
                        out.add(f"{node.name}.{sub.name}")
    return out


def blob(rev: str, path: str) -> str | None:
    r = subprocess.run(["git", "show", f"{rev}:{path}"], cwd=REPO, capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


def check(changes: list[tuple[str, str]], message: str, old_rev: str, new_rev: str | None,
          roadmap_text: str, label: str) -> list[str]:
    errors: list[str] = []
    paths = {p for _, p in changes}

    if not changes:
        return errors

    # ---- G2: no deletion / rename -------------------------------------------------
    for status, path in changes:
        if status.startswith("D"):
            errors.append(f"G2: حذف ملف ممنوع / file deletion forbidden: {path}")
        if status.startswith("R"):
            errors.append(f"G2: نقل/إعادة تسمية ممنوع / rename forbidden: {path}")

    for status, path in changes:
        if not path.endswith(".py") or status[0] not in "M":
            continue
        before = blob(old_rev, path)
        if new_rev is None:  # staged content (index)
            r = subprocess.run(["git", "show", f":{path}"], cwd=REPO, capture_output=True, text=True)
            after = r.stdout if r.returncode == 0 else None
        else:
            after = blob(new_rev, path)
        if before is None or after is None:
            continue
        removed = public_symbols(before) - public_symbols(after)
        for sym in sorted(removed):
            errors.append(f"G2: إزالة رمز عام ممنوعة / public symbol removed: {path}::{sym}")

    # ---- G1: atomic documentation ----------------------------------------------------
    ids = ID_RE.findall(message)
    if not ids:
        errors.append("G1: رسالة الالتزام يجب أن تحمل معرّف بند من الخارطة مثل [R-F-001] / "
                      "commit message must reference a roadmap id like [R-F-001]")
    for i in ids:
        if i not in roadmap_text:
            errors.append(f"G1: المعرّف {i} غير موجود في ROADMAP.md / id not found in ROADMAP.md")
    for doc in REQUIRED_DOCS:
        if doc not in paths:
            errors.append(f"G1: يجب تحديث {doc} في نفس الدفعة / {doc} must be updated in the same commit")
    if not any(p.startswith(WORKLOG_PREFIX) for p in paths):
        errors.append("G1: يجب إضافة/تحديث سجل عمل تحت docs/worklog/ / a docs/worklog/ entry is required")

    return [f"[{label}] {e}" for e in errors]


def parse_name_status(out: str) -> list[tuple[str, str]]:
    res = []
    for line in out.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        res.append((parts[0], parts[-1] if parts[0].startswith(("R", "C")) else parts[1]))
        if parts[0].startswith("R"):
            res[-1] = (parts[0], f"{parts[1]} -> {parts[2]}")
    return res


# The last commit before governance was adopted (see GOVERNANCE.md §"نطاق السريان").
GENESIS = "b9ca3e9acd3a777c95e980ae4c893e1f3cea19aa"


def is_pre_governance(sha: str) -> bool:
    """True if sha is GENESIS or one of its ancestors."""
    r = subprocess.run(["git", "merge-base", "--is-ancestor", sha, GENESIS], cwd=REPO, capture_output=True)
    return r.returncode == 0


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--staged", action="store_true")
    g.add_argument("--range")
    g.add_argument("--commit")
    ap.add_argument("--msg-file")
    ap.add_argument("--skip-message", action="store_true",
                    help="pre-commit stage: message is not known yet (checked by commit-msg hook)")
    a = ap.parse_args()

    errors: list[str] = []
    if a.staged:
        changes = parse_name_status(git("diff", "--cached", "--name-status", "-M"))
        message = Path(a.msg_file).read_text(encoding="utf-8") if a.msg_file else ""
        roadmap = subprocess.run(["git", "show", ":ROADMAP.md"], cwd=REPO, capture_output=True, text=True).stdout \
            or (REPO / "ROADMAP.md").read_text(encoding="utf-8")
        head = "HEAD" if subprocess.run(["git", "rev-parse", "--verify", "HEAD"], cwd=REPO,
                                        capture_output=True).returncode == 0 else EMPTY_TREE
        errs = check(changes, message, head, None, roadmap, "staged")
        if a.skip_message:
            errs = [e for e in errs if "G1: رسالة" not in e and "G1: المعرّف" not in e]
        errors += errs
    else:
        commits = [a.commit] if a.commit else git("rev-list", "--reverse", a.range).split()
        # Pre-governance history (GENESIS and its ancestors) is exempt: the rules apply after it.
        commits = [c for c in commits if not is_pre_governance(c)]
        for sha in commits:
            parents = git("rev-list", "--parents", "-n", "1", sha).split()[1:]
            base = parents[0] if parents else EMPTY_TREE
            changes = parse_name_status(git("diff", "--name-status", "-M", base, sha))
            message = git("log", "-1", "--format=%B", sha)
            roadmap = blob(sha, "ROADMAP.md") or ""
            errors += check(changes, message, base, sha, roadmap, sha[:8])

    if errors:
        print("✗ AGOS governance gate failed — راجع GOVERNANCE.md\n")
        for e in errors:
            print("  - " + e)
        return 1
    print("✓ AGOS governance gate passed (G1 atomic documentation, G2 no deletion)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
