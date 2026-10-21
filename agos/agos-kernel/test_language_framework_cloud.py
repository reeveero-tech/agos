#!/usr/bin/env python3
"""Test script for Language, Framework, and Cloud Packs."""
# R-F-002 portable paths (see tools/migrate/portable_paths.py)
import os as _agos_os
from pathlib import Path as _AgosPath
_AGOS_ROOT = _AgosPath(_agos_os.environ.get('AGOS_ROOT') or _AgosPath(__file__).resolve().parents[1])
_AGOS_KERNEL = _AGOS_ROOT / 'agos-kernel'
import sys
sys.path.insert(0, str(_AGOS_KERNEL))

from language_packs.library import LanguagePackLibrary, get_library as get_lang_library
from framework_packs.library import FrameworkPackLibrary, get_library as get_fwk_library
from cloud_packs.library import CloudPackLibrary, get_library as get_cloud_library


def test_language_packs():
    """Test language packs."""
    print("=" * 60)
    print("Testing Language Packs 1-40")
    print("=" * 60)
    
    library = get_lang_library()
    print(f"✓ Language Pack Library initialized")
    print(f"  Total packs: {len(library.packs)}")
    # R-Q-001: تأكيد فعلي — النطاق الموثق LANGUAGE-PACK-000001..000040 = 40
    assert len(library.packs) == 40, len(library.packs)
    
    for i, (name, pack) in enumerate(list(library.packs.items())[:10]):
        print(f"  {i+1}. {pack.metadata.name} ({', '.join(pack.metadata.extensions[:2])})")
        # المفتاح معرف (cpp/react) والاسم معروض (C++/React) — التطابق بالمعرف لا بالاسم
        assert pack.metadata.name, (name, pack.metadata.name)
        assert library.get(name) is pack
    
    print(f"  ... and {len(library.packs) - 10} more")
    
    # Detect language
    python = library.detect("main.py")
    print(f"\n✓ Detected: {python.metadata.name}")
    js = library.detect("app.jsx")
    print(f"✓ Detected: {js.metadata.name}")
    # R-Q-001: الكشف فعلي — الامتداد المعلن يعود بحزمته الصحيحة
    assert python.metadata.name == "Python", python.metadata.name
    assert js.metadata.name == "JavaScript", js.metadata.name
    assert python is not js                       # حزمتان مختلفتان لا نفس المرجع


def test_framework_packs():
    """Test framework packs."""
    print("\n" + "=" * 60)
    print("Testing Framework Packs 1-60")
    print("=" * 60)
    
    library = get_fwk_library()
    print(f"✓ Framework Pack Library initialized")
    print(f"  Total packs: {len(library.packs)}")
    # R-Q-001: تأكيد فعلي — الرصيد الفعلي 59 حزمة (الوثيقة تقول «1-60» — فرق موثق في سجل العمل)
    assert len(library.packs) == 59, len(library.packs)
    
    for i, (name, pack) in enumerate(list(library.packs.items())[:10]):
        print(f"  {i+1}. {pack.metadata.name} ({pack.metadata.category})")
        # المفتاح معرف (react) والاسم معروض (React) — الاسترجاع بالمفتاح يعيد الحزمة نفسها
        assert pack.metadata.name, (name, pack.metadata.name)
        assert library.get(name) is pack
    
    print(f"  ... and {len(library.packs) - 10} more")
    
    # Get framework
    react = library.get("react")
    if react:
        print(f"\n✓ Framework: {react.metadata.name}")
    # R-Q-001: حزمة react موجودة
    assert react is not None, "react framework pack missing"
    assert react.metadata.name == "React", react.metadata.name


def test_cloud_packs():
    """Test cloud packs."""
    print("\n" + "=" * 60)
    print("Testing Cloud Packs 1-30")
    print("=" * 60)
    
    library = get_cloud_library()
    print(f"✓ Cloud Pack Library initialized")
    print(f"  Total packs: {len(library.packs)}")
    # R-Q-001: تأكيد فعلي — النطاق الموثق CLOUD-PACK-000001..000030 = 30
    assert len(library.packs) == 30, len(library.packs)
    
    for i, (name, pack) in enumerate(list(library.packs.items())[:10]):
        print(f"  {i+1}. {pack.metadata.name} ({pack.metadata.category})")
        # المفتاح معرف (react) والاسم معروض (React) — الاسترجاع بالمفتاح يعيد الحزمة نفسها
        assert pack.metadata.name, (name, pack.metadata.name)
        assert library.get(name) is pack
    
    print(f"  ... and {len(library.packs) - 10} more")
    
    # List by category
    paas = library.list_by_category("paas")
    print(f"\n✓ PaaS providers: {[p.metadata.name for p in paas]}")
    # R-Q-001: تصنيف paas غير فارغ وكل أعضائه من الفئة نفسها فعلاً
    assert paas, "paas category is empty"
    assert all(p.metadata.category == "paas" for p in paas)


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("AGOS LANGUAGE, FRAMEWORK & CLOUD PACKS")
    print("LANGUAGE-PACK-000001 to LANGUAGE-PACK-000040")
    print("FRAMEWORK-PACK-000001 to FRAMEWORK-PACK-000060")
    print("CLOUD-PACK-000001 to CLOUD-PACK-000030")
    print("=" * 60)
    
    test_language_packs()
    test_framework_packs()
    test_cloud_packs()
    
    print("\n" + "=" * 60)
    print("ALL TESTS PASSED!")
    print("=" * 60)


if __name__ == "__main__":
    main()