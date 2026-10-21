#!/usr/bin/env python3
"""فاحص التأكيدات الفعلية — R-Q-001.

يفرض معيار البند على مستوى الملف: كل ملف ``test_*.py`` يجب أن يحوي دوال اختبار
وتأكيداً فعلياً واحداً على الأقل داخلها — لا سكربتات طباعة تعبر كاختبارات.

ما يُعد تأكيداً فعلياً:
- ``assert`` بمقارنة/عضوية/استدعاء/اسم (نتيجة عملية — ``assert success`` مشروع).
- ``pytest.raises(...)`` / ``self.assertRaises(...)`` (استثناء متوقع = تأكيد سلوكي).
- استدعاءات ``self.assert*`` على طراز unittest.

ما يُعد شكلياً (لا يُحسب وحده):
- ``assert True`` / ``assert <ثابت رقمي أو نصي>`` — ينجح دائماً.
- ``assert x == x`` (مقارنة ذاتية) — مكافئ لـ``assert True``.

الفحص الساكن أداة كشف أولية لا برهان جودة: اختباراً بلا ``assert`` في دالة واحدة
يُبلَّغ تحذيرياً ولا يُفشل الفاحص (قد يكون التأكيد عبر مساعد أو skip مشروعاً).
الخرق المُفشل: ملف كامل بلا دوال اختبار، أو بلا أي تأكيد فعلي، أو شكلي فقط.

Usage:  python tools/quality/assert_audit.py
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TARGETS = [REPO / "agos" / "agos-kernel", REPO / "tests"]


def _is_literal(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and not isinstance(node.value, bool)


def _statically_true(test: ast.AST) -> bool:
    """مقارنة تُقيَّم ساكناً: x == x أو ثابت == ثابت — تنجح دائماً بلا فحص."""
    if isinstance(test, ast.Compare) and len(test.ops) == 1 \
            and isinstance(test.ops[0], (ast.Eq, ast.Is)):
        left, right = test.left, test.comparators[0]
        if isinstance(left, ast.Name) and isinstance(right, ast.Name):
            return left.id == right.id            # assert x == x
        if isinstance(left, ast.Constant) and isinstance(right, ast.Constant):
            return left.value == right.value      # assert 1 == 1
    return False


def _assert_kind(node: ast.Assert) -> str:
    """صنف تأكيداً واحداً: real / formal."""
    test = node.test
    if isinstance(test, ast.Constant) and test.value is True:
        return "formal"       # assert True
    if _is_literal(test):
        return "formal"       # assert 1 / assert "x"
    if _statically_true(test):
        return "formal"       # assert x == x / assert 1 == 1
    return "real"


def _call_kind(node: ast.Call) -> str | None:
    """صنف استدعاءً: raises/assert* مشروع أم لا شيء."""
    func = node.func
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        receiver = func.value.id
        if func.attr == "raises" and receiver == "pytest":
            return "real"                               # pytest.raises(...)
        if func.attr == "assertRaises" and receiver == "self":
            return "real"                               # self.assertRaises(...)
        if func.attr.startswith("assert") and len(func.attr) > 6 and receiver == "self":
            return "real"                               # self.assertEqual(...)
    return None


def audit_source(source: str) -> dict:
    """فحص مصدر ملف: دوال الاختبار والتأكيدات الفعلية/الشكلية فيه."""
    tree = ast.parse(source)
    fns = [n for n in tree.body
           if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
           and n.name.startswith("test")]
    for cls in tree.body:
        if isinstance(cls, ast.ClassDef):
            fns += [n for n in cls.body if isinstance(n, ast.FunctionDef)
                    and n.name.startswith("test")]
    real = formal = 0
    no_assert_fns = []
    for fn in fns:
        fn_real = fn_formal = 0
        for node in ast.walk(fn):
            if isinstance(node, ast.Assert):
                if _assert_kind(node) == "real":
                    fn_real += 1
                else:
                    fn_formal += 1
            elif isinstance(node, ast.Call):
                if _call_kind(node) == "real":
                    fn_real += 1
        real += fn_real
        formal += fn_formal
        if fn_real == 0 and fn_formal == 0:
            no_assert_fns.append(fn.name)
    return {"test_fns": len(fns), "real": real, "formal": formal,
            "no_assert_fns": no_assert_fns}


def audit_file(path: Path) -> dict:
    source = path.read_text(encoding="utf-8", errors="replace")
    info = audit_source(source)
    try:
        rel = str(path.relative_to(REPO))
    except ValueError:
        rel = str(path)
    info["file"] = rel
    return info


def main() -> int:
    files = sorted({p for t in TARGETS if t.is_dir()
                    for p in t.rglob("test_*.py")})
    violations, warnings, total_real = [], [], 0
    for path in files:
        info = audit_file(path)
        total_real += info["real"]
        if info["test_fns"] == 0:
            violations.append((info["file"], "NO-TESTS", 0))
        elif info["real"] == 0:
            kind = "FORMAL-ONLY" if info["formal"] else "PRINT-ONLY"
            violations.append((info["file"], kind, info["test_fns"]))
        elif info["no_assert_fns"]:
            warnings.append((info["file"], info["no_assert_fns"]))
    print(f"files={len(files)} real_asserts={total_real}")
    if warnings:
        print("\n⚠ دوال اختبار بلا تأكيد مباشر (تأكيد عبر مساعد مسموح — للمراجعة):")
        for f, names in warnings:
            print(f"  - {f}: {', '.join(names)}")
    if violations:
        print("\n✗ خرق معيار R-Q-001 (ملف test_*.py بلا تأكيد فعلي):")
        for f, kind, n in violations:
            print(f"  - {f}: {kind} ({n} test fns)")
        return 1
    print("✓ كل ملفات test_*.py تحوي تأكيدات فعلية")
    return 0


if __name__ == "__main__":
    sys.exit(main())
