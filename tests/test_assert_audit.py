#!/usr/bin/env python3
"""اختبارات فاحص التأكيدات نفسه — R-Q-001.

الفاحص (`tools/quality/assert_audit.py`) يفرض معيار «كل ملف test_*.py يحوي
تأكيداً فعلياً». هذه اختباراته الذاتية: كل قاعدة تصنيف مغطاة بحالة إيجابية وسلبية.
"""
from __future__ import annotations

import sys
from pathlib import Path

_TOOLS = Path(__file__).resolve().parents[1] / "tools" / "quality"
sys.path.insert(0, str(_TOOLS))

from assert_audit import audit_source  # noqa: E402


def test_real_assert_counts():
    r = audit_source(
        "def test_x():\n"
        "    assert compute() == 3, 'mismatch'\n"
        "    assert len(items) > 0\n"
    )
    assert r["real"] == 2 and r["formal"] == 0, r
    assert r["no_assert_fns"] == []


def test_print_only_is_not_enough():
    r = audit_source(
        "def test_x():\n"
        "    print('✓ works')\n"
        "    return compute()\n"
    )
    assert r["real"] == 0 and r["formal"] == 0, r
    assert r["no_assert_fns"] == ["test_x"]


def test_assert_true_is_formal():
    r = audit_source("def test_x():\n    assert True\n")
    assert r["real"] == 0 and r["formal"] == 1, r


def test_assert_literal_is_formal():
    r = audit_source("def test_x():\n    assert 1\n")
    assert r["real"] == 0 and r["formal"] == 1, r


def test_self_comparison_is_formal():
    # assert x == x مكافئ لـ assert True — ينجح دائماً
    r = audit_source("def test_x():\n    x = compute()\n    assert x == x\n")
    assert r["real"] == 0 and r["formal"] == 1, r


def test_bare_name_assert_is_real():
    # assert success تحويل صحيح لنتيجة عملية — يفشل حين تفشل العملية
    r = audit_source("def test_x():\n    success = run()\n    assert success\n")
    assert r["real"] == 1 and r["formal"] == 0, r


def test_pytest_raises_is_real():
    r = audit_source(
        "def test_x():\n"
        "    with pytest.raises(ValueError):\n"
        "        parse('bad')\n"
    )
    assert r["real"] == 1, r


def test_unittest_asserts_are_real():
    r = audit_source(
        "class TestX:\n"
        "    def test_x(self):\n"
        "        self.assertEqual(a, b)\n"
        "        self.assertIn(k, d)\n"
    )
    assert r["real"] == 2, r
    assert r["test_fns"] == 1


def test_async_test_functions_counted():
    r = audit_source(
        "async def test_x():\n"
        "    r = await run()\n"
        "    assert r.status == 'ok'\n"
    )
    assert r["test_fns"] == 1 and r["real"] == 1, r


def test_no_test_functions_reported():
    r = audit_source("def helper():\n    return 1\n")
    assert r["test_fns"] == 0 and r["real"] == 0, r


def test_mixed_formal_and_real_counts_real():
    # ملف شكلي + حقيقي: الفحص على مستوى الملف — وجود حقيقي واحد يكفي
    r = audit_source(
        "def test_a():\n    assert True\n"
        "def test_b():\n    assert compute() == 3\n"
    )
    assert r["real"] == 1 and r["formal"] == 1, r


def test_literal_comparison_is_formal():
    # assert 1 == 1 تُقيَّم ساكناً وتنجح دائماً — شكلية لا فحص
    r = audit_source("def test_x():\n    assert 1 == 1\n")
    assert r["real"] == 0 and r["formal"] == 1, r


def test_random_raises_call_is_not_real():
    # أي استدعاء صفة اسمها raises ليس تأكيداً — فقط pytest.raises/self.assertRaises
    r = audit_source(
        "def test_x():\n"
        "    service.raises()   # ليست pytest.raises\n"
        "    assert check() == 3\n"
    )
    assert r["real"] == 1, r
